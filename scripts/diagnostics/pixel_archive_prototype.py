"""Rejected native pixel-cache prototype; no production adoption or recognition.

Fixed key images and XOR deltas preserve every byte. The index keeps original
source metadata; codec key images are not lifecycle resets. This is an internal
cache, with no loader for externally supplied archives or recognition results.
"""
from __future__ import annotations

import hashlib
import os
import re
import zlib
from dataclasses import dataclass
from pathlib import Path
from typing import BinaryIO

import numpy as np
from numpy.typing import NDArray

from valorant_ai_coach.video.native import NativeSourceFrame, _sha256
from valorant_ai_coach.video.service import VideoProbeError

KEY_INTERVAL = 16


@dataclass(frozen=True)
class _Record:
    source: NativeSourceFrame
    offset: int
    length: int
    encoded_sha256: str


@dataclass(frozen=True)
class ArchivedNativeSourceFrame(NativeSourceFrame):
    archive: NativePixelArchive
    archive_index: int

    def read_image(self) -> NDArray[np.uint8]:
        expected = self.archive.frames[self.archive_index]
        if self != expected:
            raise VideoProbeError('native archive frame binding changed')
        return self.archive.read_image(self.archive_index)


class NativePixelArchive:
    """Single-epoch cache with explicit disk budget and one decoded image cached.

    Append only verified decoder-owned frames. Before seal no consumer frames
    exist. Sealed frame descriptors survive multiple sequential analyzer passes.
    Every read verifies the full dependency chain, even when decoded pixels are
    cached. Returned arrays cannot mutate that cache. verify() checks the whole
    sealed file, including unconsumed records or appended bytes, at terminal use.
    The caller owns temporary-directory cleanup and source-video verification.
    """

    def __init__(self, path: Path, *, max_bytes: int) -> None:
        if type(max_bytes) is not int or max_bytes <= 0:
            raise ValueError('positive explicit native cache budget required')
        self.path = Path(path)
        self.max_bytes = max_bytes
        self._writer: BinaryIO | None = self.path.open('xb')
        self._records: list[_Record] = []
        self._previous: NDArray[np.uint8] | None = None
        self._cached: tuple[int, NDArray[np.uint8]] | None = None
        self._sealed_sha256: str | None = None
        self._failed = False
        self.frames: tuple[ArchivedNativeSourceFrame, ...] = ()
        self.size_bytes = 0

    def append(self, source: NativeSourceFrame) -> None:
        if self._writer is None or self._failed:
            raise VideoProbeError('native archive is sealed or failed')
        self._failed = True  # Any interrupted/rejected append poisons the buffer.
        if (not isinstance(source, NativeSourceFrame)
                or type(source.pts_ticks) is not int or source.pts_ticks < 0
                or not source.source_epoch or source.time_base <= 0
                or re.fullmatch(r'[0-9a-f]{64}', source.source_video_sha256) is None):
            raise VideoProbeError('native archive source identity unavailable')
        image = source.read_image()
        if (image.dtype != np.uint8 or image.shape != (source.height, source.width, 3)
                or hashlib.sha256(image.tobytes()).hexdigest() != source.pixel_sha256):
            raise VideoProbeError('native archive source pixels unavailable')
        if self._records:
            first, prior = self._records[0].source, self._records[-1].source
            if (source.source_epoch != first.source_epoch
                    or source.source_video_sha256 != first.source_video_sha256
                    or source.time_base != first.time_base
                    or (source.width, source.height) != (first.width, first.height)
                    or source.pts_ticks <= prior.pts_ticks):
                self._failed = True
                raise VideoProbeError('native archive requires one ordered source epoch')
        if self._previous is None or len(self._records) % KEY_INTERVAL == 0:
            raw = image.tobytes()
        else:
            raw = np.bitwise_xor(image, self._previous).tobytes()
        encoded = zlib.compress(raw, level=1)
        if self.size_bytes + len(encoded) > self.max_bytes:
            self._failed = True
            raise VideoProbeError('native archive storage budget exceeded')
        self._writer.write(encoded)
        self._records.append(_Record(source, self.size_bytes, len(encoded),
                                     hashlib.sha256(encoded).hexdigest()))
        self.size_bytes += len(encoded)
        self._previous = image.copy()
        self._failed = False

    def seal(self) -> tuple[ArchivedNativeSourceFrame, ...]:
        if self._writer is None or self._failed or not self._records:
            raise VideoProbeError('nonempty successful native archive required')
        self._writer.flush()
        os.fsync(self._writer.fileno())
        self._writer.close()
        self._writer = None
        self._previous = None
        self._sealed_sha256 = _sha256(self.path)
        self.frames = tuple(ArchivedNativeSourceFrame(
            self.path, item.source.pts_ticks, item.source.time_base,
            item.source.source_epoch, item.source.source_video_sha256,
            item.encoded_sha256, item.source.pixel_sha256,
            item.source.width, item.source.height, self, index,
        ) for index, item in enumerate(self._records))
        return self.frames

    def read_image(self, index: int) -> NDArray[np.uint8]:
        if self._sealed_sha256 is None or self._failed:
            raise VideoProbeError('native archive is not sealed')
        if type(index) is not int or not 0 <= index < len(self._records):
            raise VideoProbeError('native archive index out of range')
        if self.path.stat().st_size != self.size_bytes:
            raise VideoProbeError('native archive size changed')
        base = (index // KEY_INTERVAL)*KEY_INTERVAL
        chain = self._records[base:index+1]
        payloads = []
        with self.path.open('rb') as stream:
            for record in chain:
                stream.seek(record.offset)
                payload = stream.read(record.length)
                if hashlib.sha256(payload).hexdigest() != record.encoded_sha256:
                    raise VideoProbeError('native archive dependency changed')
                payloads.append(payload)
        image: NDArray[np.uint8] | None = None
        begin = base
        if self._cached is not None and base <= self._cached[0] <= index:
            begin = self._cached[0]+1
            image = self._cached[1]
        for position in range(begin, index+1):
            record = self._records[position]
            size = record.source.width*record.source.height*3
            decoder = zlib.decompressobj()
            raw = decoder.decompress(payloads[position-base], size+1)
            if (len(raw) != size or not decoder.eof or decoder.unused_data
                    or decoder.unconsumed_tail):
                raise VideoProbeError('native archive decoded length mismatch')
            decoded = np.frombuffer(raw, dtype=np.uint8).reshape(
                record.source.height, record.source.width, 3,
            )
            if position == base:
                image = decoded.copy()
            elif image is None:
                raise VideoProbeError('native archive delta parent unavailable')
            else:
                image = np.bitwise_xor(decoded, image)
            if hashlib.sha256(image.tobytes()).hexdigest() != record.source.pixel_sha256:
                raise VideoProbeError('native archive decoded pixels changed')
        if image is None:
            raise VideoProbeError('native archive pixels unavailable')
        if hashlib.sha256(image.tobytes()).hexdigest() != self._records[index].source.pixel_sha256:
            raise VideoProbeError('native archive cached pixels changed')
        image.flags.writeable = False
        self._cached = (index, image)
        return image.copy()

    def verify(self) -> None:
        if self._sealed_sha256 is None or _sha256(self.path) != self._sealed_sha256:
            raise VideoProbeError('native archive terminal bytes changed')

    def close(self) -> None:
        if self._writer is not None:
            self._writer.close()
            self._writer = None
        self._previous = None
        self._cached = None
