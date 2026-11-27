"""Development-only portrait-free reading of the game's own-player minimap highlight.

VALORANT draws the player whose view is on screen with a pale gold ring (and a gold
direction pointer) on the minimap. Allies use teal and enemies red rings. This module
measures that ring geometrically: a closed warm annulus of the marker radius around a
non-warm portrait interior, with no warm blob outside it. It never classifies the
portrait, so it does not depend on the Agent portrait matcher whose rejections cause
most Map position gaps.

The ring identifies *the viewed player*, not the recorder. Ownership comes from the
canonical timeline: only a frame whose camera is SELF and whose life is ALIVE may treat
the ring as the recorder's marker. In a spectator frame the same ring belongs to the
spectated teammate, so the caller must not use it there.

Nothing here is qualified. Results stay ``qualified: false`` and
``position_authority: false``.
"""

from __future__ import annotations

import hashlib
import math
from dataclasses import dataclass
from typing import Any

import cv2
import numpy as np
from numpy.typing import NDArray

VERSION = "development_map_self_ring_v1"

ColorImage = NDArray[np.uint8]

# Pale gold highlight (OpenCV HSV, hue 0-179). Measured on recorder markers:
# hue 22-36, saturation 40-120, value 190-255. Site plates are darker and filled.
_WARM_LOW = (15, 25, 185)
_WARM_HIGH = (40, 115, 255)
_SECTORS = 16


@dataclass(frozen=True)
class RingParameters:
    """Geometry at 1080p; ``scale`` multiplies every radius for other resolutions."""

    ring_inner: float = 6.0
    ring_outer: float = 10.5
    interior: float = 4.0
    halo_inner: float = 13.0
    halo_outer: float = 16.0
    min_sectors: int = 11
    min_opposite_pairs: int = 4
    max_interior_warm: float = 0.30
    max_halo_warm: float = 0.30
    min_separation: float = 6.0
    max_candidates: int = 24
    # The highlight is a pale, bright ring around a textured portrait. Saturated
    # ability icons, flat warm backgrounds and warm text fail one of these.
    max_ring_saturation: float = 100.0
    min_ring_value: float = 205.0
    min_interior_texture: float = 15.0

    def fingerprint(self) -> str:
        text = repr(sorted(self.__dict__.items())) + repr((_WARM_LOW, _WARM_HIGH, _SECTORS))
        return hashlib.sha256(text.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class RingCandidate:
    center_roi_px: tuple[int, int]
    sectors: int
    opposite_pairs: int
    interior_warm: float
    halo_warm: float
    ring_saturation: float
    ring_value: float
    interior_texture: float
    accepted: bool

    def to_dict(self) -> dict[str, Any]:
        return {
            "center_roi_px": list(self.center_roi_px),
            "warm_sectors": self.sectors,
            "opposite_pairs": self.opposite_pairs,
            "interior_warm_fraction": round(self.interior_warm, 4),
            "halo_warm_fraction": round(self.halo_warm, 4),
            "ring_saturation_median": round(self.ring_saturation, 1),
            "ring_value_median": round(self.ring_value, 1),
            "interior_value_std": round(self.interior_texture, 1),
            "accepted": self.accepted,
        }


def warm_mask(roi: ColorImage) -> NDArray[np.uint8]:
    hsv = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV)
    return np.asarray(cv2.inRange(hsv, _WARM_LOW, _WARM_HIGH) > 0, dtype=np.uint8)


def _annulus(radius_in: float, radius_out: float) -> NDArray[np.uint8]:
    size = math.ceil(radius_out)
    ys, xs = np.mgrid[-size:size + 1, -size:size + 1]
    dist = np.hypot(xs, ys)
    return np.asarray((dist >= radius_in) & (dist <= radius_out), dtype=np.uint8)


def _fraction(mask: NDArray[np.uint8], x: int, y: int, r_in: float, r_out: float) -> float:
    size = math.ceil(r_out)
    height, width = mask.shape
    x0, x1 = max(0, x - size), min(width, x + size + 1)
    y0, y1 = max(0, y - size), min(height, y + size + 1)
    ys, xs = np.mgrid[y0:y1, x0:x1]
    dist = np.hypot(xs - x, ys - y)
    region = (dist >= r_in) & (dist <= r_out)
    total = int(region.sum())
    return float(mask[y0:y1, x0:x1][region].sum()) / total if total else 1.0


def _sectors(
    mask: NDArray[np.uint8], x: int, y: int, r_in: float, r_out: float,
) -> NDArray[np.bool_]:
    height, width = mask.shape
    angles = np.arange(_SECTORS) * (math.tau / _SECTORS)
    radii = np.arange(math.ceil(r_in), math.floor(r_out) + 1)[:, None]
    # Half-sector offsets make each sector a wedge rather than a single ray.
    found = np.zeros(_SECTORS, bool)
    for offset in (-0.25, 0.0, 0.25):
        theta = angles + offset * (math.tau / _SECTORS)
        xs = np.rint(x + radii * np.cos(theta)).astype(int)
        ys = np.rint(y + radii * np.sin(theta)).astype(int)
        inside = (xs >= 0) & (xs < width) & (ys >= 0) & (ys < height)
        values = np.zeros(xs.shape, bool)
        values[inside] = mask[ys[inside], xs[inside]] > 0
        found |= values.any(axis=0)
    return found


def _measure(
    mask: NDArray[np.uint8], hsv: ColorImage, x: int, y: int, scale: float, p: RingParameters,
) -> RingCandidate:
    r_in, r_out = p.ring_inner * scale, p.ring_outer * scale
    hits = _sectors(mask, x, y, r_in, r_out)
    pairs = int((hits[: _SECTORS // 2] & hits[_SECTORS // 2:]).sum())
    interior = _fraction(mask, x, y, 0.0, p.interior * scale)
    halo = _fraction(mask, x, y, p.halo_inner * scale, p.halo_outer * scale)
    size = math.ceil(r_out)
    height, width = mask.shape
    x0, x1 = max(0, x - size), min(width, x + size + 1)
    y0, y1 = max(0, y - size), min(height, y + size + 1)
    ys, xs = np.mgrid[y0:y1, x0:x1]
    dist = np.hypot(xs - x, ys - y)
    patch = hsv[y0:y1, x0:x1]
    ring_pixels = patch[(dist >= r_in) & (dist <= r_out) & (mask[y0:y1, x0:x1] > 0)]
    inner_pixels = patch[dist <= p.interior * scale]
    saturation = float(np.median(ring_pixels[:, 1])) if len(ring_pixels) else 255.0
    value = float(np.median(ring_pixels[:, 2])) if len(ring_pixels) else 0.0
    texture = float(inner_pixels[:, 2].std()) if len(inner_pixels) else 0.0
    accepted = (
        int(hits.sum()) >= p.min_sectors
        and pairs >= p.min_opposite_pairs
        and interior <= p.max_interior_warm
        and halo <= p.max_halo_warm
        and saturation <= p.max_ring_saturation
        and value >= p.min_ring_value
        and texture >= p.min_interior_texture
    )
    return RingCandidate((int(x), int(y)), int(hits.sum()), pairs, interior, halo,
                         saturation, value, texture, accepted)


def find_rings(
    roi: ColorImage, *, scale: float = 1.0, parameters: RingParameters | None = None,
) -> list[RingCandidate]:
    """Every warm-annulus candidate in the minimap ROI, best first."""
    if roi.ndim != 3 or roi.shape[2] != 3 or roi.dtype != np.uint8:
        raise ValueError("BGR uint8 minimap ROI required")
    if not math.isfinite(scale) or scale <= 0:
        raise ValueError("Positive finite scale required")
    p = parameters or RingParameters()
    mask = warm_mask(roi)
    hsv = np.asarray(cv2.cvtColor(roi, cv2.COLOR_BGR2HSV), dtype=np.uint8)
    r_in, r_out = p.ring_inner * scale, p.ring_outer * scale
    kernel = _annulus(r_in, r_out).astype(np.float32)
    votes = cv2.filter2D(mask.astype(np.float32), cv2.CV_32F, kernel / kernel.sum(),
                         borderType=cv2.BORDER_CONSTANT)
    reach = max(2, round(p.min_separation * scale))
    results: list[RingCandidate] = []
    scored = votes.copy()
    for _ in range(p.max_candidates):
        _, best, _, (x, y) = cv2.minMaxLoc(scored)
        if best < 0.12:
            break
        scored[max(0, y - reach):y + reach + 1, max(0, x - reach):x + reach + 1] = -1
        results.append(_measure(mask, hsv, int(x), int(y), scale, p))
    results.sort(key=lambda c: (not c.accepted, -c.sectors, -c.opposite_pairs, c.interior_warm))
    return results


def read_self_ring(
    roi: ColorImage, *, scale: float = 1.0, parameters: RingParameters | None = None,
) -> dict[str, Any]:
    """Return the unique accepted ring, or an abstention with its reason."""
    p = parameters or RingParameters()
    candidates = find_rings(roi, scale=scale, parameters=p)
    accepted = [c for c in candidates if c.accepted]
    distinct: list[RingCandidate] = []
    for candidate in accepted:
        if all(math.dist(candidate.center_roi_px, other.center_roi_px)
               > p.min_separation * scale for other in distinct):
            distinct.append(candidate)
    result: dict[str, Any] = {
        "method": VERSION,
        "parameters_sha256": p.fingerprint(),
        "candidates": [c.to_dict() for c in candidates[:6]],
        "accepted_count": len(distinct),
        "qualified": False,
        "position_authority": False,
    }
    if len(distinct) == 1:
        result.update(status="UNIQUE", center_roi_px=list(distinct[0].center_roi_px))
    elif distinct:
        result.update(status="AMBIGUOUS", center_roi_px=None)
    else:
        result.update(status="ABSENT", center_roi_px=None)
    return result


def ring_support_at(
    roi: ColorImage, point: tuple[float, float], *, scale: float = 1.0,
    radius: float = 3.0, parameters: RingParameters | None = None,
) -> dict[str, Any]:
    """Best ring evidence within ``radius`` pixels of a point measured elsewhere.

    Used to check, on the canonical pixels, an observation another recognizer made on a
    different decode of the same source frame.
    """
    p = parameters or RingParameters()
    mask = warm_mask(roi)
    hsv = np.asarray(cv2.cvtColor(roi, cv2.COLOR_BGR2HSV), dtype=np.uint8)
    height, width = mask.shape
    best: RingCandidate | None = None
    reach = math.ceil(radius * scale)
    cx, cy = round(point[0]), round(point[1])
    for y in range(cy - reach, cy + reach + 1):
        for x in range(cx - reach, cx + reach + 1):
            if (not (0 <= x < width and 0 <= y < height)
                    or math.dist((x, y), point) > radius * scale):
                continue
            candidate = _measure(mask, hsv, x, y, scale, p)
            if best is None or (candidate.accepted, candidate.sectors, candidate.opposite_pairs) > (
                best.accepted, best.sectors, best.opposite_pairs
            ):
                best = candidate
    return {"method": VERSION, "best": best.to_dict() if best else None,
            "supported": bool(best and best.accepted)}
