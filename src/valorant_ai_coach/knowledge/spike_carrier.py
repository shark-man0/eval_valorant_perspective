"""Spike carrier: is the viewed player carrying the spike?

Game knowledge used: only attackers can carry the spike, and the carrier's
weapon inventory (right edge of the screen) shows a spike header, an emblem in a
framed box above the weapon list. The emblem is matched with a grayscale
template; the header text is excluded so the reader does not depend on the
client language, and the key-bind letter is excluded so it does not depend on
bindings.

Riot ships no stand-alone image of this HUD element, so the template is built
from DEVELOPMENT recordings by ``scripts/knowledge/build_spike_template.py`` and
kept in the private cache like the official reference images. It is never
committed.

The inventory shows the *viewed* player's items: consumers must restrict a
positive reading to the recorder's own live view.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path

import cv2
import numpy as np

# weapon_inventory ROI in 1920x1080 reference pixels; archives store it at 0.5 scale.
INVENTORY_ROI = (1670, 600, 1918, 1015)
# With a primary weapon the list grows upward and the header can sit above
# y=600, so per-second extraction uses a taller ROI.
TALL_INVENTORY_ROI = (1670, 450, 1918, 1015)
ARCHIVE_SCALE = 0.5
# Search window inside the archive-scale crop (x0, y0, x1, y1). The header sits
# at the top of the crop; the window allows a few pixels of drift.
SEARCH_WINDOW = (40, 0, 124, 110)
# The closest look-alike is the round-countdown hourglass panel. A second,
# negative template of it (also TRAIN-built) is subtracted:
#   score = 2 * ncc(spike) - ncc(hourglass)
# On the TRAIN matches the highest hourglass panel scores 0.673 and the lowest
# spike header 0.683.
CARRIED_MIN_SCORE = 0.68
TEMPLATE_NAME = "spike_carrier_v1.png"
NEGATIVE_NAME = "spike_carrier_v1_hourglass.png"
MANIFEST_NAME = "spike_carrier_v1.json"


class SpikeTemplateUnavailable(RuntimeError):
    """The private spike-header template has not been built on this machine."""


@dataclass(frozen=True)
class SpikeCarrierReading:
    carried: bool
    score: float
    position: tuple[int, int]


def _decode(data: bytes, path: Path) -> np.ndarray:
    image = cv2.imdecode(np.frombuffer(data, np.uint8), cv2.IMREAD_GRAYSCALE)
    if image is None:
        raise SpikeTemplateUnavailable(f"cannot decode {path}")
    return image


class SpikeCarrierReader:
    def __init__(self, template: np.ndarray, negative: np.ndarray | None = None, *,
                 scale: float = ARCHIVE_SCALE) -> None:
        if template.ndim != 2 or (negative is not None and negative.shape != template.shape):
            raise ValueError("templates must be grayscale and of the same size")
        self.template = template.astype(np.float32)
        self.negative = None if negative is None else negative.astype(np.float32)
        self.scale = scale

    @classmethod
    def load(cls, cache_dir: Path) -> SpikeCarrierReader:
        path = cache_dir / "hud_templates" / TEMPLATE_NAME
        manifest = cache_dir / "hud_templates" / MANIFEST_NAME
        if not path.exists() or not manifest.exists():
            raise SpikeTemplateUnavailable(f"missing {path}; run build_spike_template.py")
        meta = json.loads(manifest.read_text(encoding="utf-8"))
        if meta.get("lineage", {}).get("split") != "TRAIN":
            raise SpikeTemplateUnavailable(f"{path} has no TRAIN-only lineage; rebuild it")
        images = []
        for name, key in ((TEMPLATE_NAME, "sha256"), (NEGATIVE_NAME, "negative_sha256")):
            file = path.parent / name
            data = file.read_bytes() if file.exists() else b""
            if hashlib.sha256(data).hexdigest() != meta.get(key):
                raise SpikeTemplateUnavailable(f"{file} does not match its manifest")
            images.append(_decode(data, file))
        return cls(images[0], images[1], scale=float(meta.get("scale", ARCHIVE_SCALE)))

    def read(self, crop: np.ndarray, *,
             roi: tuple[int, int, int, int] = INVENTORY_ROI) -> SpikeCarrierReading:
        """Read an inventory crop taken at ``self.scale`` of ``roi`` (1920x1080 pixels)."""
        if self.scale != ARCHIVE_SCALE:
            factor = ARCHIVE_SCALE / self.scale
            crop = cv2.resize(crop, None, fx=factor, fy=factor, interpolation=cv2.INTER_AREA)
        gray = crop if crop.ndim == 2 else cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
        x0, y0, x1, y1 = SEARCH_WINDOW
        y1 += max(0, round((INVENTORY_ROI[1] - roi[1]) * ARCHIVE_SCALE))
        window = gray[y0:y1, x0:x1].astype(np.float32)
        th, tw = self.template.shape
        if window.shape[0] < th or window.shape[1] < tw:
            return SpikeCarrierReading(False, 0.0, (0, 0))
        result = cv2.matchTemplate(window, self.template, cv2.TM_CCOEFF_NORMED)
        _, best, _, loc = cv2.minMaxLoc(result)
        spike = float(best) if np.isfinite(best) else 0.0
        hourglass = 0.0
        if self.negative is not None:
            negative = cv2.minMaxLoc(cv2.matchTemplate(window, self.negative,
                                                       cv2.TM_CCOEFF_NORMED))[1]
            hourglass = float(negative) if np.isfinite(negative) else 0.0
        score = 2.0 * spike - hourglass if self.negative is not None else spike
        return SpikeCarrierReading(score >= CARRIED_MIN_SCORE, score,
                                   (int(loc[0]) + x0, int(loc[1]) + y0))
