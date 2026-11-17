"""Read the bottom-centre ability HUD with official ability icons.

The ability HUD shows the *viewed* player's four abilities in C, Q, E, X order
(game knowledge, see ``game_rules_v1.json``). Official icons are white
silhouettes; matching them at HUD scale ranks which agent the HUD belongs to.
Charge bars under each icon give per-slot availability without any agent
knowledge.

Outputs are observations of the viewed HUD. While spectating, the HUD belongs
to the spectated player, so the recorder's agent is only established by
aggregating over time (see :func:`identify_agent`), and never by one frame.
"""

from __future__ import annotations

import math
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field

import cv2
import numpy as np
from numpy.typing import NDArray

from .assets import ReferenceAssets
from .catalog import HUD_ABILITY_KEYS, GameKnowledge

# 1920x1080 reference geometry of the ability strip and its four slots.
STRIP_BOX = (745, 975, 1175, 1062)  # x0, y0, x1, y1
SLOT_CENTERS_X = (790, 903, 1015, 1128)  # C, Q, E, X
ICON_CENTER_Y = 1003
ICON_SEARCH_HALF = (34, 30)  # half width/height of the search window around a slot
BAR_BOX = ((-36, 1037 - 1003), (36, 1047 - 1003))  # relative to (slot x, icon y)
ICON_SIZES = (40, 44, 48, 52)


@dataclass(frozen=True)
class SlotReading:
    key: str
    charge_fraction: float  # 0..1 share of the bar showing the charge colour
    icon_brightness: float  # mean of the brightest icon pixels (0..255)


@dataclass(frozen=True)
class FrameReading:
    """Per-frame ability HUD reading. ``agent_scores`` aligns with ``agent_uuids``."""

    hud_present: bool
    agent_uuids: tuple[str, ...]
    agent_scores: NDArray[np.float64]
    slot_scores: dict[str, NDArray[np.float64]]
    slots: tuple[SlotReading, ...]

    def ranked(self, k: int = 3) -> list[tuple[str, float]]:
        order = np.argsort(-self.agent_scores)[:k]
        return [(self.agent_uuids[i], float(self.agent_scores[i])) for i in order]

    @property
    def utility_available_count(self) -> int:
        return sum(s.charge_fraction >= 0.25 for s in self.slots if s.key != "X")

    @property
    def ultimate_ready(self) -> bool:
        return any(s.key == "X" and s.charge_fraction >= 0.6 for s in self.slots)


@dataclass
class AgentIdentification:
    agent_uuid: str | None
    status: str  # IDENTIFIED / ABSTAIN / NO_HUD
    frames_used: int
    top: list[tuple[str, float]] = field(default_factory=list)
    margin: float = 0.0
    vote_share: float = 0.0
    basis: str = "hud_majority"  # or "timeline_self_live"


def _icon_template(bgra: NDArray[np.uint8], size: int) -> NDArray[np.float32]:
    alpha = bgra[:, :, 3].astype(np.float32) / 255.0
    luminance = cv2.cvtColor(bgra[:, :, :3], cv2.COLOR_BGR2GRAY).astype(np.float32) / 255.0
    shape = alpha * luminance
    ys, xs = np.nonzero(shape > 0.05)
    if len(xs) == 0:
        raise ValueError("Empty icon")
    # Official icons are padded differently; normalize to the glyph's bounding box.
    x0, x1, y0, y1 = xs.min(), xs.max() + 1, ys.min(), ys.max() + 1
    side = max(x1 - x0, y1 - y0)
    canvas = np.zeros((side, side), np.float32)
    oy, ox = (side - (y1 - y0)) // 2, (side - (x1 - x0)) // 2
    canvas[oy:oy + y1 - y0, ox:ox + x1 - x0] = shape[y0:y1, x0:x1]
    return np.asarray(cv2.resize(canvas, (size, size), interpolation=cv2.INTER_AREA),
                      dtype=np.float32)


def _prepare(gray: NDArray[np.float32]) -> NDArray[np.float32]:
    """Suppress the scene behind the HUD: keep bright thin structures (white glyphs)."""
    background = cv2.morphologyEx(gray, cv2.MORPH_OPEN, np.ones((15, 15), np.uint8))
    return np.asarray(np.clip(gray - background, 0, None), dtype=np.float32)


class AbilityHudReader:
    """Rank agents for one ability-HUD crop using official icons."""

    def __init__(self, knowledge: GameKnowledge, assets: ReferenceAssets,
                 sizes: Sequence[int] = ICON_SIZES) -> None:
        self.knowledge = knowledge
        self.agent_uuids = tuple(agent.uuid for agent in knowledge.agents)
        self.sizes = tuple(sizes)
        self.templates: dict[str, list[list[NDArray[np.float32]]]] = {}
        for key in HUD_ABILITY_KEYS:
            per_agent = []
            for agent in knowledge.agents:
                ability = agent.abilities[key]
                icon = assets.image(ability.asset_id)
                per_agent.append([_prepare(_icon_template(icon, s)) for s in self.sizes])
            self.templates[key] = per_agent

    @staticmethod
    def strip_from_frame(frame_bgr: NDArray[np.uint8]) -> NDArray[np.uint8]:
        h, w = frame_bgr.shape[:2]
        if (w, h) != (1920, 1080):
            frame_bgr = np.asarray(
                cv2.resize(frame_bgr, (1920, 1080), interpolation=cv2.INTER_AREA), dtype=np.uint8)
        x0, y0, x1, y1 = STRIP_BOX
        return frame_bgr[y0:y1, x0:x1]

    def match_window(self, window: NDArray[np.float32], template_key: str
                     ) -> NDArray[np.float64]:
        """Best normalized correlation of ``window`` with each agent's ``template_key`` icon."""
        scores = np.full(len(self.agent_uuids), -1.0)
        if window.std() <= 1e-4:
            return scores
        for index, variants in enumerate(self.templates[template_key]):
            best = -1.0
            for template in variants:
                th, tw = template.shape
                if th > window.shape[0] or tw > window.shape[1]:
                    continue
                result = cv2.matchTemplate(window, template, cv2.TM_CCOEFF_NORMED)
                best = max(best, float(result.max()))
            scores[index] = best
        return scores

    def slot_windows(self, strip_bgr: NDArray[np.uint8]) -> dict[str, NDArray[np.float32]]:
        x0, y0, _, _ = STRIP_BOX
        gray = cv2.cvtColor(strip_bgr, cv2.COLOR_BGR2GRAY).astype(np.float32) / 255.0
        prepared = _prepare(gray)
        hw, hh = ICON_SEARCH_HALF
        windows = {}
        for key, cx in zip(HUD_ABILITY_KEYS, SLOT_CENTERS_X, strict=True):
            sx, sy = cx - x0, ICON_CENTER_Y - y0
            windows[key] = prepared[max(0, sy - hh):sy + hh, max(0, sx - hw):sx + hw]
        return windows

    def read(self, strip_bgr: NDArray[np.uint8]) -> FrameReading:
        x0, y0, _, _ = STRIP_BOX
        gray = cv2.cvtColor(strip_bgr, cv2.COLOR_BGR2GRAY).astype(np.float32) / 255.0
        prepared = _prepare(gray)
        hsv = cv2.cvtColor(strip_bgr, cv2.COLOR_BGR2HSV)
        slot_scores: dict[str, NDArray[np.float64]] = {}
        slots: list[SlotReading] = []
        bright_slots = 0
        for key, cx in zip(HUD_ABILITY_KEYS, SLOT_CENTERS_X, strict=True):
            sx, sy = cx - x0, ICON_CENTER_Y - y0
            hw, hh = ICON_SEARCH_HALF
            window = prepared[max(0, sy - hh):sy + hh, max(0, sx - hw):sx + hw]
            slot_scores[key] = self.match_window(window, key)
            (bx0, by0), (bx1, by1) = BAR_BOX
            bar = hsv[max(0, sy + by0):sy + by1, max(0, sx + bx0):sx + bx1]
            # Charge colour: saturated teal/green (OpenCV hue ~70-95).
            charged = (bar[:, :, 0] >= 65) & (bar[:, :, 0] <= 100) & (bar[:, :, 1] >= 90) & (
                bar[:, :, 2] >= 120)
            column_charged = charged.mean(axis=0) >= 0.3 if bar.size else np.zeros(0, bool)
            fraction = float(column_charged.mean()) if column_charged.size else 0.0
            icon = gray[max(0, sy - 22):sy + 22, max(0, sx - 24):sx + 24]
            top = np.sort(icon.ravel())[-max(1, icon.size // 20):] if icon.size else np.zeros(1)
            brightness = float(top.mean() * 255)
            bright_slots += brightness > 150
            slots.append(SlotReading(key, fraction, brightness))
        stacked = np.vstack([slot_scores[k] for k in HUD_ABILITY_KEYS])
        agent_scores = stacked.mean(axis=0)
        hud_present = bool(stacked.max() > 0.35)
        return FrameReading(hud_present, self.agent_uuids, agent_scores, slot_scores, tuple(slots))


def identify_agent(readings: Iterable[FrameReading], *, min_frames: int = 20,
                   min_margin: float = 0.03, min_vote_share: float = 0.4,
                   self_live: Sequence[bool] | None = None) -> AgentIdentification:
    """Aggregate per-frame rankings into the recorder's agent, or abstain.

    With ``self_live`` (aligned with ``readings``, from the shared timeline's
    SELF + ALIVE state) only the recorder's own live frames vote, so spectated
    teammates' HUDs are excluded by the timeline rather than outvoted. When the
    timeline gives fewer than ``min_frames`` such frames, or none is supplied,
    all HUD frames vote: the recorder controls their own HUD for most of a
    match while spectated teammates rotate. A weak majority or a small score
    margin abstains rather than guesses.
    """
    readings = list(readings)
    basis = "hud_majority"
    if self_live is not None:
        if len(self_live) != len(readings):
            raise ValueError("self_live must align with readings")
        own = [r for r, live in zip(readings, self_live, strict=True) if live and r.hud_present]
        if len(own) >= min_frames:
            readings, basis = own, "timeline_self_live"
    usable = [r for r in readings if r.hud_present]
    if len(usable) < min_frames:
        return AgentIdentification(None, "NO_HUD", len(usable), basis=basis)
    uuids = usable[0].agent_uuids
    votes = np.zeros(len(uuids))
    totals = np.zeros(len(uuids))
    for reading in usable:
        votes[int(np.argmax(reading.agent_scores))] += 1
        totals += reading.agent_scores
    order = np.argsort(-votes)
    share = votes[order[0]] / len(usable)
    mean = totals / len(usable)
    margin = float(mean[order[0]] - np.max(np.delete(mean, order[0])))
    top = [(uuids[i], float(votes[i] / len(usable))) for i in order[:3]]
    identified = share >= min_vote_share and margin >= min_margin and math.isfinite(margin)
    return AgentIdentification(
        uuids[order[0]] if identified else None,
        "IDENTIFIED" if identified else "ABSTAIN",
        len(usable), top, margin, float(share), basis,
    )
