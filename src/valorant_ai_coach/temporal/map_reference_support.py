"""Reject recovered points clearly outside the exact reference artwork."""

from __future__ import annotations

import hashlib
import math
from collections.abc import Sequence
from pathlib import Path

import cv2
import numpy as np
from numpy.typing import NDArray

from .replay import read_json

# Reference-alignment and native-center uncertainty leave the nearby fringe unresolved.
_ATLAS_FRINGE_PX = 12.0


def atlas_distances_for(
    catalog: Path, map_id: str, expected_sha: str,
    verified_references: Sequence[tuple[str, str, Path, str]],
) -> NDArray[np.float32] | None:
    root = catalog.resolve().parent
    relative = next((entry["reference"] for entry in read_json(catalog)["maps"]
                     if entry["id"] == map_id), None)
    path = (root / relative).resolve() if relative is not None else None
    if path is not None and not path.is_relative_to(root):
        raise ValueError("Map reference outside catalog")
    if path is None or not path.is_file():
        path = next((p for _, uid, p, _ in verified_references if uid == map_id), None)
    return read_atlas_void_distances(path, expected_sha) if path is not None else None


def read_atlas_void_distances(path: Path, sha256: str) -> NDArray[np.float32] | None:
    """Measure distance into transparent pixels using the pinned public atlas bytes."""
    data = path.read_bytes()
    if hashlib.sha256(data).hexdigest() != sha256:
        raise ValueError("Map reference artwork changed")
    atlas = cv2.imdecode(np.frombuffer(data, np.uint8), cv2.IMREAD_UNCHANGED)
    if atlas is None or atlas.ndim != 3:
        raise ValueError("Readable Map reference artwork required")
    if atlas.shape[2] != 4 or not np.any(atlas[:, :, 3]):
        return None
    transparent = np.asarray(atlas[:, :, 3] == 0, dtype=np.uint8)
    return np.asarray(cv2.distanceTransform(transparent, cv2.DIST_L2, 5), dtype=np.float32)


def clearly_outside_atlas(
    distances: NDArray[np.float32] | None, coordinate: Sequence[float],
) -> bool:
    x, y = coordinate
    if not (math.isfinite(x) and math.isfinite(y)):
        return True
    if distances is None:
        return False
    round_x, round_y = math.floor(x), math.floor(y)
    height, width = distances.shape
    return (not 0 <= round_x < width or not 0 <= round_y < height
            or bool(distances[round_y, round_x] > _ATLAS_FRINGE_PX))
