"""Top match bar: per-team alive portraits and their agent hypotheses.

Game knowledge used: each team has ``team_size`` (5) portrait slots; alive
players' portraits are packed toward the centre timer and dead players'
portraits are removed, and portraits are the agents' official display icons at
small scale. Presence is read from portrait texture: the team band behind an
empty slot is a smooth gradient, a portrait is not. (The status bar under a
portrait is not used: it is dark during buy phase.)

Alive counts are observations of the bar, not of the round: buy-phase,
round-end and spectating screens are all still read, and consumers decide which
timeline states they apply to.
"""

from __future__ import annotations

from dataclasses import dataclass

import cv2
import numpy as np
from numpy.typing import NDArray

from .assets import ReferenceAssets
from .catalog import GameKnowledge

# 1920x1080 reference geometry (top_match_bar ROI starts at x=385, y=0).
BAR_ORIGIN = (385, 0)
ALLY_CENTERS_X = (465, 531, 597, 663, 729)  # outermost first
ENEMY_CENTERS_X = (1193, 1259, 1325, 1391, 1457)  # innermost first
PORTRAIT_CENTER_Y = 47
PORTRAIT_HALF = 21
TEXTURE_HALF = (16, 18)  # half width/height of the texture probe inside a portrait
PRESENT_TEXTURE = 6.0  # mean |Laplacian|; DEVELOPMENT matches: present >= 12, empty <= 1.7


@dataclass(frozen=True)
class TeamReading:
    present: tuple[bool, ...]  # slot order outermost -> innermost for ally, inner->outer enemy
    texture: tuple[float, ...]
    alive: int
    packed: bool  # present slots are contiguous from the centre side (knowledge check)


@dataclass(frozen=True)
class TopBarReading:
    ally: TeamReading
    enemy: TeamReading

    @property
    def consistent(self) -> bool:
        return self.ally.packed and self.enemy.packed

    def numbers_state(self) -> str | None:
        if not self.consistent:
            return None
        if self.ally.alive > self.enemy.alive:
            return "advantage"
        if self.ally.alive < self.enemy.alive:
            return "disadvantage"
        return "even"


def _to_full(crop: NDArray[np.uint8]) -> NDArray[np.uint8]:
    """Upscale a (possibly downscaled) top-bar crop to 1155x100 reference pixels."""
    if crop.shape[1] != 1155:
        crop = np.asarray(cv2.resize(crop, (1155, 100), interpolation=cv2.INTER_LINEAR),
                          dtype=np.uint8)
    return crop


def _texture(laplacian: NDArray[np.float64], cx: int) -> float:
    x = cx - BAR_ORIGIN[0]
    hw, hh = TEXTURE_HALF
    return float(laplacian[PORTRAIT_CENTER_Y - hh:PORTRAIT_CENTER_Y + hh, x - hw:x + hw].mean())


def _packed(present: tuple[bool, ...], centre_last: bool) -> bool:
    ordered = present if not centre_last else tuple(reversed(present))
    # centre-first ordering must look like True...True False...False
    seen_false = False
    for value in ordered:
        if value and seen_false:
            return False
        seen_false |= not value
    return True


def read_top_bar(crop: NDArray[np.uint8], *, threshold: float = PRESENT_TEXTURE
                 ) -> TopBarReading:
    full = _to_full(crop)
    gray = cv2.cvtColor(full, cv2.COLOR_BGR2GRAY).astype(np.float64)
    laplacian = np.abs(cv2.Laplacian(gray, cv2.CV_64F))
    teams = []
    for centers, centre_last in ((ALLY_CENTERS_X, True), (ENEMY_CENTERS_X, False)):
        scores = tuple(_texture(laplacian, cx) for cx in centers)
        present = tuple(score >= threshold for score in scores)
        teams.append(TeamReading(present, scores, sum(present), _packed(present, centre_last)))
    return TopBarReading(*teams)


def portrait_crops(crop: NDArray[np.uint8], reading: TopBarReading
                   ) -> list[tuple[str, int, NDArray[np.uint8]]]:
    """(team, slot, portrait) for present slots, in reference pixels."""
    full = _to_full(crop)
    out = []
    for team, centers, team_reading in (("ally", ALLY_CENTERS_X, reading.ally),
                                        ("enemy", ENEMY_CENTERS_X, reading.enemy)):
        for slot, (cx, present) in enumerate(zip(centers, team_reading.present, strict=True)):
            if not present:
                continue
            x = cx - BAR_ORIGIN[0]
            y = PORTRAIT_CENTER_Y
            out.append((team, slot, full[y - PORTRAIT_HALF:y + PORTRAIT_HALF,
                                         x - PORTRAIT_HALF:x + PORTRAIT_HALF]))
    return out


def portrait_feature(portrait_bgr: NDArray[np.uint8], size: int = 20) -> NDArray[np.float64]:
    """Contrast-normalised colour thumbnail used by portrait identity learners."""
    thumb = cv2.resize(portrait_bgr, (size, size), interpolation=cv2.INTER_AREA)
    lab = cv2.cvtColor(thumb, cv2.COLOR_BGR2LAB).astype(np.float64)
    lab -= lab.mean(axis=(0, 1), keepdims=True)
    lab /= lab.std(axis=(0, 1), keepdims=True) + 1e-6
    return lab.ravel()


def official_portrait_anchors(knowledge: GameKnowledge, assets: ReferenceAssets,
                              size: int = 20) -> tuple[NDArray[np.float64], list[str]]:
    """Zero-shot anchors: official display icons cropped to the head like the top bar."""
    features, labels = [], []
    for agent in knowledge.agents:
        icon = assets.image(agent.asset_id("displayicon"))
        alpha = icon[:, :, 3:4].astype(np.float64) / 255.0
        background = np.array([90, 110, 90], np.float64)  # neutral band colour, BGR
        rgb = (icon[:, :, :3] * alpha + background * (1 - alpha)).astype(np.uint8)
        h, w = rgb.shape[:2]
        for zoom in (0.62, 0.7, 0.78):
            side = int(min(h, w) * zoom)
            x0 = (w - side) // 2
            y0 = int(h * 0.04)
            features.append(portrait_feature(rgb[y0:y0 + side, x0:x0 + side], size))
            labels.append(agent.name)
    return np.vstack(features), labels


# Centre indicator: the round timer is replaced by a red spike icon after a plant.
CENTRE_BOX = (885, 5, 1035, 85)  # 1920x1080 pixels
SPIKE_RED_FILL = 0.04  # DEVELOPMENT: planted >= 0.06, timer < 0.02 on three matches


def spike_planted_indicator(crop: NDArray[np.uint8]) -> tuple[bool, float]:
    """(planted, red fraction) from the top-bar crop's centre indicator."""
    full = _to_full(crop)
    x0, y0, x1, y1 = CENTRE_BOX
    hsv = cv2.cvtColor(full[y0:y1, x0 - BAR_ORIGIN[0]:x1 - BAR_ORIGIN[0]], cv2.COLOR_BGR2HSV)
    red = (((hsv[:, :, 0] < 8) | (hsv[:, :, 0] > 170)) & (hsv[:, :, 1] > 150)
           & (hsv[:, :, 2] > 150))
    fraction = float(red.mean())
    return fraction >= SPIKE_RED_FILL, fraction
