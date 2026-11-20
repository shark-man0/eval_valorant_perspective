"""Read private HUD crop archives written by ``scripts/knowledge/extract_hud_crops.py``."""

from __future__ import annotations

import json
import zipfile
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import cv2
import numpy as np
from numpy.typing import NDArray


@dataclass(frozen=True)
class CropSample:
    sec: float
    crops: dict[str, NDArray[np.uint8]]


class CropArchive:
    def __init__(self, path: Path) -> None:
        self.path = path
        self._zip = zipfile.ZipFile(path)
        self.meta: dict[str, Any] = json.loads(self._zip.read("index.json"))
        self._members: dict[tuple[str, float], str] = {}
        for name in self._zip.namelist():
            if "/" not in name:
                continue
            region, file_name = name.split("/", 1)
            stem = file_name.rsplit(".", 1)[0]
            self._members[(region, round(float(stem), 1))] = name

    @property
    def video_id(self) -> str:
        return str(self.meta["video_id"])

    @property
    def regions(self) -> tuple[str, ...]:
        return tuple(sorted({region for region, _ in self._members}))

    def seconds(self) -> list[float]:
        return sorted({sec for _, sec in self._members})

    def crop(self, region: str, sec: float) -> NDArray[np.uint8] | None:
        name = self._members.get((region, round(sec, 1)))
        if name is None:
            return None
        data = np.frombuffer(self._zip.read(name), np.uint8)
        image = cv2.imdecode(data, cv2.IMREAD_COLOR)
        return None if image is None else np.asarray(image, dtype=np.uint8)

    def iter_samples(self, regions: tuple[str, ...]) -> Iterator[CropSample]:
        for sec in self.seconds():
            crops = {}
            for region in regions:
                image = self.crop(region, sec)
                if image is not None:
                    crops[region] = image
            if crops:
                yield CropSample(sec, crops)

    def close(self) -> None:
        self._zip.close()
