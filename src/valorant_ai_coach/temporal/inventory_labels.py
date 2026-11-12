"""Optional viewed inventory labels; never selected weapon or owner authority."""

from __future__ import annotations

import re
import unicodedata
from typing import Any

import cv2
import numpy as np

from valorant_ai_coach.hud.readers import ReaderResult
from valorant_ai_coach.hud.templates import TesseractTextReader


def normalize_label(value: str) -> str:
    return re.sub(r"\s+", "", unicodedata.normalize("NFKC", value)).casefold()


class InventoryLabelReader:
    """Reuse text OCR on separate current text lines, retaining every attempt.

    A Profile supplies exact aliases; skin labels, substrings and fuzzy matches
    cannot identify a weapon. Multiple distinct labels abstain. This measures a
    visible inventory label only, not which weapon is held or who owns the HUD.
    """

    def __init__(self, reader: TesseractTextReader, aliases: dict[str, str]) -> None:
        if not aliases or any(not isinstance(k, str) or not k.strip()
                              or not isinstance(v, str) or not v.strip()
                              for k, v in aliases.items()):
            raise ValueError("Explicit nonempty weapon label aliases required")
        self.aliases = {normalize_label(k): v for k, v in aliases.items()}
        if len(self.aliases) != len(aliases):
            raise ValueError("Duplicate normalized weapon label aliases")
        self.reader = reader
        self.last_attempts: list[dict[str, Any]] = []

    def read(self, image: np.ndarray, roi: np.ndarray) -> ReaderResult[str]:
        self.last_attempts = []
        if roi.size == 0:
            return ReaderResult(None, 0, ("inventory_empty",))
        gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY) if roi.ndim == 3 else roi
        height, width = gray.shape
        # Fixed central text area excludes right-edge keybinds; no Source/time
        # inputs and no weapon-specific coordinates.
        left, right = round(.20 * width), round(.75 * width)
        area = gray[:, left:right]
        occupied = np.count_nonzero(area >= 200, axis=1) >= 3
        edges = np.diff(np.pad(occupied.astype(np.int8), (1, 1)))
        matches: list[tuple[str, float]] = []
        for first, last in zip(np.flatnonzero(edges == 1),
                               np.flatnonzero(edges == -1), strict=True):
            top, bottom = int(first), int(last)
            if not max(5, round(height*.012)) <= bottom-top <= max(8, round(height*.06)):
                continue
            top, bottom = max(0, int(top)-3), min(height, int(bottom)+3)
            crop = roi[top:bottom, left:right]
            result = self.reader.read(image, crop)
            label = self.aliases.get(normalize_label(result.value or ""))
            accepted = (label is not None and type(result.confidence) in (float, int)
                        and np.isfinite(result.confidence) and .90 <= result.confidence <= 1
                        and bool(result.sources))
            self.last_attempts.append({"roi_bounds_px": [left, top, right, bottom],
                "text": result.value, "confidence": result.confidence,
                "sources": list(result.sources), "matched_alias": label,
                "accepted": accepted})
            if accepted and label is not None:
                matches.append((label, result.confidence))
        labels = {label for label, _ in matches}
        if len(labels) != 1:
            return ReaderResult(None, 0, ("inventory_label_conflict" if labels
                                          else "inventory_label_unread",))
        return ReaderResult(next(iter(labels)), min(conf for _, conf in matches),
                            ("current_inventory_label", "selected_weapon_unresolved"))
