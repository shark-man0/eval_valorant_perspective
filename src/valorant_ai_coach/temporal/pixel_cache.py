"""Private, stateless pixel-observation cache for development acquisition.

Native decoding and Source admission remain the caller's responsibility.
Only canonical JSON pixel measurements are cached, never inferred states,
labels, initialization or qualified outputs. Cache use changes no measurement.
"""

from __future__ import annotations

import hashlib
import json
import os
import sqlite3
from copy import deepcopy
from pathlib import Path
from typing import TYPE_CHECKING, Any

import numpy as np

from .evidence import digest, is_sha
from .replay import file_sha

if TYPE_CHECKING:
    from .match import PixelObserver


class CachedPixelObserver:
    """Observe already decoded BGR pixels; keys contain no Source/time/roster."""

    def __init__(self, observer: PixelObserver, path: Path) -> None:
        if not is_sha(observer.fingerprint) or not isinstance(observer.bindings, dict):
            raise ValueError("Bound parent pixel observer required")
        self.observer = observer
        self.path = path.expanduser().resolve()
        if any((p / ".git").exists() for p in self.path.parents):
            raise ValueError("Private pixel cache outside Git required")
        self.path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        self._parent_identity = digest([observer.fingerprint, observer.bindings])
        self.bindings = deepcopy(observer.bindings)
        self.bindings["pixel_cache"] = {
            "schema": "development_pixel_measurement_cache_v1",
            "parent_fingerprint": observer.fingerprint,
            "parent_bindings_sha256": digest(observer.bindings),
            "code_sha256": file_sha(Path(__file__)),
            "measurement_encoding": "canonical_JSON",
            "recognition_state_authority": False,
        }
        self.fingerprint = digest(self.bindings)
        self.stats = {"hits": 0, "misses": 0}
        self._db: sqlite3.Connection | None = None

    def _connection(self) -> sqlite3.Connection:
        if self._db is None:
            if not self.path.exists():
                os.close(os.open(self.path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600))
            self._db = sqlite3.connect(self.path)
            self._db.execute(
                "CREATE TABLE IF NOT EXISTS pixels (namespace TEXT, pixel_key TEXT, "
                "payload TEXT NOT NULL, payload_sha TEXT NOT NULL, "
                "PRIMARY KEY(namespace,pixel_key))"
            )
            self._db.commit()
        return self._db

    def inspect(self, image: np.typing.NDArray[np.uint8]) -> dict[str, Any]:
        if (image.dtype != np.uint8 or image.ndim != 3 or image.shape[2] != 3
                or image.shape[0] <= 0 or image.shape[1] <= 0):
            raise ValueError("Decoded uint8 BGR pixels required")
        if digest([self.observer.fingerprint, self.observer.bindings]) != self._parent_identity:
            raise ValueError("Pixel observer bindings changed")
        key = digest([list(image.shape), str(image.dtype),
                      hashlib.sha256(image.tobytes()).hexdigest()])
        db = self._connection()
        row = db.execute(
            "SELECT payload,payload_sha FROM pixels WHERE namespace=? AND pixel_key=?",
            (self.fingerprint, key),
        ).fetchone()
        if row is not None:
            payload, expected = row
            if hashlib.sha256(payload.encode("utf-8")).hexdigest() != expected:
                raise ValueError("Pixel cache payload integrity mismatch")
            self.stats["hits"] += 1
        else:
            # The public observation transport is JSON. Normalize equally on
            # misses and hits; no runtime cache counters enter observations.
            payload = json.dumps(self.observer.inspect(image), sort_keys=True,
                                 ensure_ascii=False, allow_nan=False, separators=(",", ":"))
            expected = hashlib.sha256(payload.encode("utf-8")).hexdigest()
            db.execute("INSERT INTO pixels VALUES (?,?,?,?)",
                       (self.fingerprint, key, payload, expected))
            db.commit()
            self.stats["misses"] += 1
        value: Any = json.loads(payload)
        if not isinstance(value, dict):
            raise ValueError("Pixel measurement object required")
        return value

    def close(self) -> None:
        if self._db is not None:
            self._db.close()
            self._db = None
