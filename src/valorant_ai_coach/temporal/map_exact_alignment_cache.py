"""Share stateless exact atlas fits between development passes of one replay."""

from __future__ import annotations

import json
import os
from pathlib import Path
from tempfile import NamedTemporaryFile
from time import monotonic, sleep
from typing import Any, cast

import numpy as np
from numpy.typing import NDArray

from .evidence import digest
from .public_map_pixels import PublicMapPixels
from .replay import read_json


class ExactAlignmentCache:
    def __init__(self, projector: PublicMapPixels, directory: Path | None) -> None:
        self.projector = projector
        self.directory = directory.resolve() if directory is not None else None
        self.hits = self.misses = 0
        if self.directory is not None:
            if any((root / ".git").exists() for root in (self.directory, *self.directory.parents)):
                raise ValueError("Private alignment cache must remain outside Git checkouts")
            self.directory.mkdir(mode=0o700, parents=True, exist_ok=True)

    def inspect(self, image: NDArray[np.uint8], sample: dict[str, Any]) -> dict[str, Any]:
        """Use a prevalidated native image and preserve current-frame geometry only."""
        directory = self.directory
        if directory is None:
            return cast(dict[str, Any], self.projector.inspect_exact(image)["raw"])
        key = digest(["exact_atlas_fit_v1", self.projector.fingerprint, sample["sample_sha256"]])
        path = directory / f"{key}.json"
        if path.exists():
            return self._read(path, key)

        claim = path.with_suffix(".pending")
        try:
            descriptor = os.open(claim, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        except FileExistsError:
            # A crashed worker may leave a claim. Retry independently after a bounded wait.
            deadline = monotonic() + 2
            while claim.exists() and not path.exists() and monotonic() < deadline:
                sleep(0.02)
            if path.exists():
                return self._read(path, key)
            return self._compute(image, path, key)
        else:
            os.close(descriptor)
            try:
                if path.exists():
                    return self._read(path, key)
                return self._compute(image, path, key)
            finally:
                claim.unlink()

    def _read(self, path: Path, key: str) -> dict[str, Any]:
        entry = read_json(path)
        if entry["key"] != key or entry["raw_sha256"] != digest(entry["raw"]):
            raise ValueError("Exact alignment cache entry changed")
        self.hits += 1
        return cast(dict[str, Any], entry["raw"])

    def _compute(self, image: NDArray[np.uint8], path: Path, key: str) -> dict[str, Any]:
        raw = self.projector.inspect_exact(image)["raw"]
        self.misses += 1
        with NamedTemporaryFile(
            mode="w", encoding="utf-8", dir=path.parent, delete=False,
        ) as stream:
            temporary = Path(stream.name)
            try:
                json.dump({"key": key, "raw_sha256": digest(raw), "raw": raw}, stream,
                          ensure_ascii=False, allow_nan=False, separators=(",", ":"))
            except BaseException:
                stream.close()
                temporary.unlink()
                raise
        try:
            os.link(temporary, path)
        except FileExistsError:
            pass  # A parallel detector already stored the same exact fit.
        finally:
            temporary.unlink()
        return cast(dict[str, Any], raw)
