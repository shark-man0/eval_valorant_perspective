"""Kill-feed entries with agent identities from official kill-feed portraits.

Game knowledge used: each entry is a band whose killer half is coloured by the
killer's team (teal = recorder's team, red = opponents) and whose victim half
by the victim's team; the killer portrait sits at the left end, the victim
portrait at the right end, and portraits are the agents' official kill-feed
portraits. The victim portrait is always inside the fixed kill-feed region
(entries are right-aligned); the killer portrait can be cut off by long names,
in which case the killer is left unknown rather than guessed.

Entries are development observations. They become candidate kill events only
after de-duplication over time (an entry stays on screen for several seconds).
"""

from __future__ import annotations

from dataclasses import dataclass

import cv2
import numpy as np
from numpy.typing import NDArray

from .assets import ReferenceAssets
from .catalog import GameKnowledge

FEED_BOX = (1440, 45, 1918, 188)  # x0, y0, x1, y1 in 1920x1080 pixels
MIN_BAND_HEIGHT = 18
BAND_FILL = 0.25
PORTRAIT_SIZES = ((52, 26), (60, 30), (68, 34))  # (w, h) candidates at 1080p
KILLER_MIN_SCORE = 0.7
HIGHLIGHT_FILL = 0.03  # DEVELOPMENT: highlighted entries mostly 0.04-0.13, others <= 0.02
VICTIM_END_WIDTH = 100


@dataclass(frozen=True)
class FeedEntry:
    y: int
    killer_team: str  # "ally" (recorder's team) or "enemy"
    victim_team: str
    killer: str | None
    killer_score: float
    victim: str | None
    victim_score: float
    recorder_victim: bool = False  # local-player highlight on the victim end
    recorder_killer: bool = False  # local-player highlight on the killer end


def _team_masks(hsv: NDArray[np.uint8]) -> tuple[NDArray[np.bool_], NDArray[np.bool_]]:
    hue, sat, val = hsv[:, :, 0], hsv[:, :, 1], hsv[:, :, 2]
    ally = (hue >= 70) & (hue <= 100) & (sat > 80) & (val > 100)
    enemy = ((hue < 8) | (hue > 170)) & (sat > 100) & (val > 120)
    return ally, enemy


def _highlight(hsv: NDArray[np.uint8]) -> NDArray[np.bool_]:
    """The game's local-player frame: saturated yellow."""
    hue, sat, val = hsv[:, :, 0], hsv[:, :, 1], hsv[:, :, 2]
    return (hue >= 20) & (hue <= 35) & (sat > 90) & (val > 150)


def _bands(fill: NDArray[np.float64]) -> list[tuple[int, int]]:
    rows = fill > BAND_FILL
    bands, start = [], None
    for y, on in enumerate([*rows.tolist(), False]):
        if on and start is None:
            start = y
        elif not on and start is not None:
            if y - start >= MIN_BAND_HEIGHT:
                bands.append((start, y))
            start = None
    return bands


class KillFeedReader:
    def __init__(self, knowledge: GameKnowledge, assets: ReferenceAssets) -> None:
        self.names = tuple(agent.name for agent in knowledge.agents)
        self.templates: list[list[NDArray[np.float32]]] = []
        for agent in knowledge.agents:
            icon = assets.image(agent.asset_id("killfeedportrait"))
            alpha = icon[:, :, 3:4].astype(np.float32) / 255.0
            gray = cv2.cvtColor(icon[:, :, :3], cv2.COLOR_BGR2GRAY).astype(np.float32)[:, :, None]
            composed = (gray * alpha + 60.0 * (1 - alpha))[:, :, 0]
            variants = []
            for width, height in PORTRAIT_SIZES:
                small = cv2.resize(composed, (width, height), interpolation=cv2.INTER_AREA)
                variants.append(np.asarray(small, np.float32))
                variants.append(np.asarray(small[:, ::-1], np.float32))  # victims face left
            self.templates.append(variants)

    @staticmethod
    def to_full(crop: NDArray[np.uint8]) -> NDArray[np.uint8]:
        x0, y0, x1, y1 = FEED_BOX
        if crop.shape[:2] != (y1 - y0, x1 - x0):
            crop = np.asarray(cv2.resize(crop, (x1 - x0, y1 - y0), interpolation=cv2.INTER_LINEAR),
                              dtype=np.uint8)
        return crop

    def _match(self, window: NDArray[np.float32]) -> tuple[str | None, float]:
        best, best_name = -1.0, None
        for name, variants in zip(self.names, self.templates, strict=True):
            for template in variants:
                th, tw = template.shape
                if th > window.shape[0] or tw > window.shape[1]:
                    continue
                score = float(cv2.matchTemplate(window, template, cv2.TM_CCOEFF_NORMED).max())
                if score > best:
                    best, best_name = score, name
        return best_name, best

    def read(self, crop: NDArray[np.uint8]) -> list[FeedEntry]:
        full = self.to_full(crop)
        hsv = np.asarray(cv2.cvtColor(full, cv2.COLOR_BGR2HSV), dtype=np.uint8)
        gray = cv2.cvtColor(full, cv2.COLOR_BGR2GRAY).astype(np.float32)
        ally, enemy = _team_masks(hsv)
        yellow = _highlight(hsv)
        entries = []
        for top, bottom in _bands((ally | enemy).mean(axis=1)):
            band = (ally | enemy)[top:bottom]
            columns = np.where(band.mean(axis=0) > 0.3)[0]
            if len(columns) < 40:
                continue
            x0, x1 = int(columns.min()), int(columns.max()) + 1
            span = x1 - x0
            left = slice(x0, x0 + span // 4)
            # Victim name area: just left of the victim portrait (the local
            # player's entry adds a yellow frame and arrow on the right).
            right = slice(max(x0, x1 - 150), max(x0 + 1, x1 - 100))
            def team(columns: slice, top: int = top, bottom: int = bottom) -> str:
                ally_px = ally[top:bottom, columns].sum()
                return "ally" if ally_px >= enemy[top:bottom, columns].sum() else "enemy"

            killer_team, victim_team = team(left), team(right)
            pad = 4
            y0, y1 = max(0, top - pad), min(full.shape[0], bottom + pad)
            victim, victim_score = self._match(
                gray[y0:y1, max(0, x1 - 100):min(full.shape[1], x1 + 4)])
            killer, killer_score = (None, 0.0)
            if x0 > 3:  # killer portrait fully inside the region
                killer, killer_score = self._match(gray[y0:y1, max(0, x0 - 4):x0 + 80])
                if killer_score < KILLER_MIN_SCORE:
                    killer = None
            y0h, y1h = max(0, top - 3), min(full.shape[0], bottom + 3)
            # Entries are right-aligned: the victim end (with the local player's
            # frame and arrow) is the right edge of the region, whatever x1 is.
            right_mark = float(yellow[y0h:y1h, full.shape[1] - VICTIM_END_WIDTH:].mean())
            left_mark = float(yellow[y0h:y1h, max(0, x0 - 12):x0 + 90].mean())
            entries.append(FeedEntry((top + bottom) // 2, killer_team, victim_team,
                                     killer, killer_score, victim, victim_score,
                                     right_mark >= HIGHLIGHT_FILL, left_mark >= HIGHLIGHT_FILL))
        return entries
