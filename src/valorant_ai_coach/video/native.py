"""Verified lossless native frames for explicit source windows, including EOF.

No FPS conversion, timestamp rebasing, resizing or lifecycle inference occurs.
The bounded window is explicit; this decoder does not change full HUD sampling.
"""

from __future__ import annotations

import hashlib
import json
import math
import re
import subprocess
import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from fractions import Fraction
from pathlib import Path
from tempfile import TemporaryDirectory
from threading import Event, Timer
from typing import IO, Any, cast

import cv2
import numpy as np
from numpy.typing import NDArray

from .service import VideoProbeError, _subprocess_environment


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


def decoded_source_ticks(log: str, time_base: Fraction) -> tuple[int, ...]:
    bases = re.findall(r'config in time_base:\s*(\d+/\d+)', log)
    frames = re.findall(r'\bn:\s*(\d+)\s+pts:\s*(-?\d+)\s+pts_time:', log)
    if (
        not bases or any(Fraction(base) != time_base for base in bases)
        or not frames or [int(n) for n, _ in frames] != list(range(len(frames)))
    ):
        raise VideoProbeError('native decoder timebase or frame order mismatch')
    ticks = tuple(int(tick) for _, tick in frames)
    if any(b <= a for a, b in zip(ticks, ticks[1:], strict=False)):
        raise VideoProbeError('native decoder PTS must increase strictly')
    return ticks


def _read_exact(stream: IO[bytes], count: int) -> bytes:
    chunks = bytearray()
    while len(chunks) < count:
        data = stream.read(count-len(chunks))
        if not data:
            raise VideoProbeError('native PNG pipe truncated')
        chunks.extend(data)
    return bytes(chunks)


def _write_png_pipe(stream: IO[bytes], directory: Path, max_bytes: int) -> int:
    """Consume encoded PNG frames, enforcing total bytes before each write.

    This is decoder data transport, not process-state polling. No input frame is
    skipped and nothing is published before decoder/PTS/hash verification.
    """
    written, count = 0, 0
    while True:
        signature = stream.read(8)
        if not signature:
            return count
        if len(signature) < 8:
            signature += _read_exact(stream, 8-len(signature))
        if signature != b'\x89PNG\r\n\x1a\n':
            raise VideoProbeError('native PNG pipe signature mismatch')
        path = directory / f'frame_{count+1:06d}.png'
        with path.open('xb') as output:
            def write(data: bytes) -> None:
                nonlocal written
                if written+len(data) > max_bytes:
                    raise VideoProbeError('native PNG storage budget exceeded')
                output.write(data)
                written += len(data)

            write(signature)
            first = True
            while True:
                header = _read_exact(stream, 8)
                length = int.from_bytes(header[:4], 'big')
                kind = header[4:]
                if first and (kind != b'IHDR' or length != 13):
                    raise VideoProbeError('native PNG pipe IHDR mismatch')
                first = False
                write(header)
                if length+4 > max_bytes-written:
                    raise VideoProbeError('native PNG storage budget exceeded')
                remaining = length+4  # Payload plus CRC; bounded chunks in memory.
                while remaining:
                    chunk = _read_exact(stream, min(65536, remaining))
                    write(chunk)
                    remaining -= len(chunk)
                if kind == b'IEND':
                    if length != 0:
                        raise VideoProbeError('native PNG pipe IEND mismatch')
                    break
        count += 1


def _decode_budgeted_pngs(
    command: list[str], directory: Path, log: Any, max_bytes: int, timeout_sec: float,
) -> None:
    """One encoder, blocking byte reads/wait, with timeout and failure cleanup."""
    timed_out = Event()
    with subprocess.Popen(
        [*command, '-f', 'image2pipe', 'pipe:1'], stdout=subprocess.PIPE,
        stderr=log, env=_subprocess_environment(),
    ) as process:
        def timeout() -> None:
            timed_out.set()
            process.kill()

        timer = Timer(timeout_sec, timeout)
        timer.daemon = True
        timer.start()
        try:
            assert process.stdout is not None
            try:
                _write_png_pipe(process.stdout, directory, max_bytes)
            except Exception as error:
                if timed_out.is_set():
                    raise subprocess.TimeoutExpired(command, timeout_sec) from error
                raise
            code = process.wait()
            if timed_out.is_set():
                raise subprocess.TimeoutExpired(command, timeout_sec)
            if code != 0:
                raise subprocess.CalledProcessError(code, command)
        except BaseException:
            process.kill()
            process.wait()
            raise
        finally:
            timer.cancel()


@dataclass(frozen=True, slots=True)
class NativeSourceFrame:
    path: Path
    pts_ticks: int
    time_base: Fraction
    source_epoch: str
    source_video_sha256: str
    encoded_sha256: str
    pixel_sha256: str
    width: int
    height: int

    @property
    def time_sec(self) -> float:
        return float(self.pts_ticks * self.time_base)

    def read_image(self) -> NDArray[np.uint8]:
        if _sha256(self.path) != self.encoded_sha256:
            raise VideoProbeError('native decoded asset changed')
        image = cv2.imread(str(self.path))
        if (
            image is None or image.shape != (self.height, self.width, 3)
            or image.dtype != np.uint8
            or hashlib.sha256(image.tobytes()).hexdigest() != self.pixel_sha256
        ):
            raise VideoProbeError('native decoded pixels changed')
        return cast(NDArray[np.uint8], image)


@contextmanager
def decode_native_window(
    video: Path,
    *,
    start_sec: float,
    end_sec: float | None,
    source_video_sha256: str,
    ffmpeg: str,
    ffprobe: str,
    timeout_sec: float = 1800,
    png_prediction: str = "none",
    max_png_bytes: int | None = None,
) -> Iterator[tuple[NativeSourceFrame, ...]]:
    """Decode all native frames in an explicit interval or to EOF (end_sec=None).

    Interior endpoints require probe coverage on both sides. start_sec=0
    explicitly requests the physical source origin, including a nonzero first
    PTS; end_sec=None requests decoder/probe EOF rather than an inferred end.
    No incremental streaming is provided: files are buffered until verification.
    No frame reaches the consumer
    before decoder completion, exact native PTS coverage and source hash checks.
    Lossless files live only inside this context and are removed on any exit.
    """
    if (
        type(start_sec) not in (int, float) or not math.isfinite(start_sec)
        or start_sec < 0
        or (end_sec is not None and (type(end_sec) not in (int, float)
            or not math.isfinite(end_sec) or end_sec <= start_sec))
        or type(timeout_sec) not in (int, float)
        or not math.isfinite(timeout_sec) or timeout_sec <= 0
        or not isinstance(source_video_sha256, str)
        or re.fullmatch(r'[0-9a-f]{64}', source_video_sha256) is None
    ):
        raise ValueError('finite explicit window and source SHA256 required')
    if png_prediction not in {'none', 'up'}:
        raise ValueError('native PNG prediction must be none or up')
    if max_png_bytes is not None and (type(max_png_bytes) is not int or max_png_bytes <= 0):
        raise ValueError('positive explicit native PNG storage budget required')
    video = Path(video).resolve()
    if _sha256(video) != source_video_sha256:
        raise VideoProbeError('native source video SHA256 mismatch')

    def probe(arguments: list[str]) -> dict[str, Any]:
        result = subprocess.run(
            [ffprobe, '-v', 'error', '-select_streams', 'v:0', *arguments,
             '-of', 'json', str(video)],
            capture_output=True, text=True, check=True, timeout=timeout_sec,
            env=_subprocess_environment(),
        )
        data: dict[str, Any] = json.loads(result.stdout)
        return data

    stream = probe(['-show_streams', '-show_entries', 'stream=time_base,width,height'])[
        'streams'
    ][0]
    time_base = Fraction(stream['time_base'])
    width, height = int(stream['width']), int(stream['height'])
    if time_base <= 0 or width <= 0 or height <= 0:
        raise VideoProbeError('native source geometry/timebase unavailable')
    probe_end = '' if end_sec is None else str(end_sec + 1.0)
    frames = probe([
        '-read_intervals', f'{max(0.0, start_sec - 1.0)}%{probe_end}',
        '-show_frames', '-show_entries', 'frame=best_effort_timestamp',
    ])['frames']
    probed = tuple(int(frame['best_effort_timestamp']) for frame in frames)
    if (
        not probed or (start_sec != 0 and float(probed[0] * time_base) > start_sec)
        or (end_sec is not None and float(probed[-1] * time_base) <= end_sec)
        or any(b <= a for a, b in zip(probed, probed[1:], strict=False))
    ):
        raise VideoProbeError('native probe must cover both sides of interior window')
    if start_sec == 0 and probed[0] < 0:
        raise VideoProbeError('negative native source origin requires explicit support')
    expected = tuple(t for t in probed if float(t * time_base) >= start_sec
                     and (end_sec is None or float(t * time_base) <= end_sec))
    if len(expected) < 2:
        raise VideoProbeError('native window requires at least two source frames')
    with TemporaryDirectory(prefix='valorant-native-') as temporary:
        directory = Path(temporary)
        log_path = directory / 'decode.log'
        filters = (f'select=gte(t\\,{start_sec}),showinfo' if end_sec is None else
                   f'trim=end={end_sec + 1.0},'
                   f'select=between(t\\,{start_sec}\\,{end_sec}),showinfo')
        with log_path.open('w', encoding='utf-8') as log:
            command = [
                ffmpeg, '-hide_banner', '-loglevel', 'info', '-threads', '1',
                '-noaccurate_seek', '-seek_timestamp', '1', '-ss', str(start_sec),
                '-copyts', '-i', str(video), '-an', '-sn', '-dn', '-map', '0:v:0',
                '-vf', filters,
                '-fps_mode', 'passthrough',
                '-threads', '1', '-compression_level', '1', '-pred', png_prediction,
                '-start_number', '1', '-c:v', 'png',
            ]
            if max_png_bytes is None:
                subprocess.run(
                    [*command, str(directory / 'frame_%06d.png')],
                    stdout=subprocess.DEVNULL, stderr=log, check=True, timeout=timeout_sec,
                    env=_subprocess_environment(),
                )
            else:
                _decode_budgeted_pngs(command, directory, log, max_png_bytes, timeout_sec)
        actual = decoded_source_ticks(log_path.read_text(encoding='utf-8'), time_base)
        paths = sorted(directory.glob('frame_*.png'))
        if actual != expected or len(paths) != len(expected):
            raise VideoProbeError('decoded frames differ from all native source PTS')
        if _sha256(video) != source_video_sha256:
            raise VideoProbeError('native source video changed during decode')
        epoch = uuid.uuid4().hex
        decoded = []
        for path, tick in zip(paths, actual, strict=True):
            encoded_sha256 = _sha256(path)
            image = cv2.imread(str(path))
            if image is None or image.shape != (height, width, 3):
                raise VideoProbeError('native decoded geometry mismatch')
            decoded.append(NativeSourceFrame(
                path, tick, time_base, epoch, source_video_sha256, encoded_sha256,
                hashlib.sha256(image.tobytes()).hexdigest(), width, height,
            ))
        try:
            yield tuple(decoded)
        finally:
            if _sha256(video) != source_video_sha256:
                raise VideoProbeError('native source video changed during consumption')
