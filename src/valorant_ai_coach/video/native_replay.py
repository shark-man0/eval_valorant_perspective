"""Bounded-memory native replay from a SHA-bound source, without PNG retention.

All source frames are first decoded and verified before exposing frame handles.
Each subsequent decoder pass must reproduce those pixels and the complete PTS
sequence. No analyzer state is reset by these storage-level replay passes.
"""
from __future__ import annotations

import hashlib
import json
import math
import subprocess
import uuid
from collections import OrderedDict
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field
from fractions import Fraction
from pathlib import Path
from tempfile import TemporaryDirectory
from threading import Timer
from typing import Any

import numpy as np
from numpy.typing import NDArray

from .native import NativeSourceFrame, _sha256, decoded_source_ticks
from .service import VideoProbeError, _subprocess_environment


class _RawPass:
    def __init__(self, owner: _ReplaySource) -> None:
        self.owner = owner
        self.position = 0
        self.log_path = owner.directory / 'replay.log'
        self.log = self.log_path.open('w', encoding='utf-8')
        command = [owner.ffmpeg, '-hide_banner', '-loglevel', 'info', '-threads', '1',
                   '-copyts', '-i', str(owner.video), '-an', '-sn', '-dn', '-map', '0:v:0',
                   '-vf', 'showinfo', '-fps_mode', 'passthrough', '-threads', '1',
                   '-pix_fmt', 'bgr24', '-f', 'rawvideo', 'pipe:1']
        try:
            self.process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=self.log,
                                            env=_subprocess_environment())
        except BaseException:
            self.log.close()
            raise

    def read(self) -> NDArray[np.uint8]:
        assert self.process.stdout is not None
        timer = Timer(self.owner.timeout, self.process.kill)
        timer.daemon = True
        timer.start()
        try:
            data = bytearray()
            while len(data) < self.owner.frame_bytes:
                part = self.process.stdout.read(self.owner.frame_bytes - len(data))
                if not part:
                    raise VideoProbeError('native replay frame truncated')
                data.extend(part)
            image = np.frombuffer(data, dtype=np.uint8).reshape(
                self.owner.height, self.owner.width, 3,
            )
            self.position += 1
            return image
        finally:
            timer.cancel()

    def verify_end(self) -> None:
        assert self.process.stdout is not None
        timer = Timer(self.owner.timeout, self.process.kill)
        timer.daemon = True
        timer.start()
        try:
            if self.process.stdout.read(1):
                raise VideoProbeError('native replay has extra decoded frames')
            if self.process.wait(timeout=self.owner.timeout) != 0:
                raise VideoProbeError('native replay decoder failed')
            self.log.flush()
            ticks = decoded_source_ticks(self.log_path.read_text(encoding='utf-8'),
                                         self.owner.time_base)
            if ticks != self.owner.ticks:
                raise VideoProbeError('native replay PTS coverage changed')
            if _sha256(self.owner.video) != self.owner.source_hash:
                raise VideoProbeError('native replay source changed')
        finally:
            timer.cancel()
            self.close()

    def close(self) -> None:
        if self.process.poll() is None:
            self.process.kill()
        self.process.wait(timeout=self.owner.timeout)
        if self.process.stdout is not None:
            self.process.stdout.close()
        self.log.close()


class _ReplaySource:
    def __init__(self, video: Path, source_hash: str, ffmpeg: str, directory: Path,
                 ticks: tuple[int, ...], time_base: Fraction, width: int, height: int,
                 max_buffer_bytes: int, timeout: float) -> None:
        self.video, self.source_hash, self.ffmpeg = video, source_hash, ffmpeg
        self.directory, self.ticks, self.time_base = directory, ticks, time_base
        self.width, self.height, self.timeout = width, height, timeout
        self.frame_bytes = width * height * 3
        if type(max_buffer_bytes) is not int or max_buffer_bytes < self.frame_bytes * 3:
            raise ValueError('native replay requires a buffer for at least three raw frames')
        # Reserve two frames for transient read/copy allocations. Never cache a
        # whole recording even if the caller supplies a large storage allowance.
        self.cache_limit = min(4, max_buffer_bytes // self.frame_bytes - 2)
        self.cache: OrderedDict[int, NDArray[np.uint8]] = OrderedDict()
        self.hashes: list[str] = []
        self.active: _RawPass | None = None
        self.closed = False

    def measure(self) -> None:
        stream = _RawPass(self)
        try:
            for _ in self.ticks:
                image = stream.read()
                self.hashes.append(hashlib.sha256(image.tobytes()).hexdigest())
            stream.verify_end()
        except BaseException:
            stream.close()
            raise

    def read(self, index: int) -> NDArray[np.uint8]:
        if self.closed:
            raise VideoProbeError('native replay frame used after context exit')
        try:
            if index not in self.cache:
                if self.active is not None and index < self.active.position:
                    self.finish()
                if self.active is None:
                    self.active = _RawPass(self)
                while self.active.position <= index:
                    position = self.active.position
                    image = self.active.read()
                    if hashlib.sha256(image.tobytes()).hexdigest() != self.hashes[position]:
                        raise VideoProbeError('native replay pixels changed')
                    self.cache[position] = image
                    while len(self.cache) > self.cache_limit:
                        self.cache.popitem(last=False)
                if self.active.position == len(self.ticks):
                    self.active.verify_end()
                    self.active = None
            image = self.cache[index]
            if hashlib.sha256(image.tobytes()).hexdigest() != self.hashes[index]:
                raise VideoProbeError('native replay cached pixels changed')
            return image.copy()
        except BaseException:
            self.abort()
            raise

    def finish(self) -> None:
        if self.active is not None:
            try:
                while self.active.position < len(self.ticks):
                    position = self.active.position
                    image = self.active.read()
                    if hashlib.sha256(image.tobytes()).hexdigest() != self.hashes[position]:
                        raise VideoProbeError('native replay terminal pixels changed')
                self.active.verify_end()
            finally:
                self.active.close()
                self.active = None
        if _sha256(self.video) != self.source_hash:
            raise VideoProbeError('native replay source changed during consumption')

    def abort(self) -> None:
        if self.active is not None:
            self.active.close()
            self.active = None
        self.cache.clear()
        self.closed = True


@dataclass(frozen=True)
class ReplayNativeSourceFrame(NativeSourceFrame):
    """Path/encoded hash identify the original source video, not a PNG asset."""
    owner: _ReplaySource = field(repr=False, compare=False)
    source_index: int

    def read_image(self) -> NDArray[np.uint8]:
        return self.owner.read(self.source_index)


@contextmanager
def decode_native_replay(
    video: Path, *, source_video_sha256: str, ffmpeg: str, ffprobe: str,
    max_buffer_bytes: int = 64 * 1024 * 1024, timeout_sec: float = 1800,
) -> Iterator[tuple[ReplayNativeSourceFrame, ...]]:
    """Verify and replay the physical source origin through EOF, without FPS conversion."""
    if (type(timeout_sec) not in (int, float) or not math.isfinite(timeout_sec)
            or timeout_sec <= 0):
        raise ValueError("native replay timeout must be finite and positive")
    video = video.resolve()
    if _sha256(video) != source_video_sha256:
        raise VideoProbeError('native replay source SHA256 mismatch')
    result = subprocess.run(
        [ffprobe, '-v', 'error', '-threads', '1', '-select_streams', 'v:0',
         '-show_streams', '-show_frames',
         '-show_entries', 'stream=time_base,width,height:frame=best_effort_timestamp',
         '-of', 'json', str(video)], capture_output=True, text=True, encoding="utf-8", check=True,
        timeout=timeout_sec, env=_subprocess_environment(),
    )
    document: dict[str, Any] = json.loads(result.stdout)
    stream = document['streams'][0]
    ticks = tuple(int(f['best_effort_timestamp']) for f in document['frames'])
    time_base = Fraction(stream['time_base'])
    width, height = int(stream['width']), int(stream['height'])
    if (len(ticks) < 2 or ticks[0] < 0 or time_base <= 0 or width <= 0 or height <= 0
            or any(b <= a for a, b in zip(ticks, ticks[1:], strict=False))):
        raise VideoProbeError('native replay source metadata/PTS invalid')
    with TemporaryDirectory(prefix='valorant-native-replay-') as temporary:
        owner = _ReplaySource(video, source_video_sha256, ffmpeg, Path(temporary), ticks,
                              time_base, width, height, max_buffer_bytes, timeout_sec)
        try:
            owner.measure()
            epoch = uuid.uuid4().hex
            frames = tuple(ReplayNativeSourceFrame(
                video, tick, time_base, epoch, source_video_sha256, source_video_sha256,
                owner.hashes[index], width, height, owner, index,
            ) for index, tick in enumerate(ticks))
            yield frames
            owner.finish()
        finally:
            owner.abort()
