"""Diagnostic adapter for an unqualified numeric proposal; never a profile kind.

Only explicit injection into private point probes is supported. No setting,
profile schema, native qualification or production factory registers this class.
"""
from __future__ import annotations

import math
import re

import cv2

from scripts.diagnostics.numeric_text_localization import propose
from valorant_ai_coach.hud.readers import ReaderResult


class LocalizedDigitsReader:
    def __init__(self, delegate, *, timer: bool, minimum: float):
        if (type(timer) is not bool or type(minimum) not in (int, float)
                or not math.isfinite(minimum) or not .90 <= minimum <= 1):
            raise ValueError("explicit format and unchanged >=.90 confidence floor required")
        self.delegate, self.timer, self.minimum = delegate, timer, minimum

    def read(self, image, roi):
        gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY) if roi.ndim == 3 else roi
        bounds = propose(gray, timer=self.timer)
        if bounds is None:
            return ReaderResult(None, 0.0, ("diagnostic_numeric_region_unlocalized",))
        left, top, right, bottom = bounds
        result = self.delegate.read(image, gray[top:bottom, left:right])
        pattern = r"[0-9]{1,2}:[0-5][0-9]" if self.timer else r"[0-9]{1,2}"
        if (not isinstance(result, ReaderResult) or not isinstance(result.value, str)
                or re.fullmatch(pattern, result.value) is None
                or type(result.confidence) not in (int, float)
                or not math.isfinite(result.confidence)
                or not self.minimum <= result.confidence <= 1
                or not result.sources
                or any(not isinstance(s, str) or not s.strip() for s in result.sources)):
            return ReaderResult(None, 0.0, ("diagnostic_numeric_result_rejected",))
        # Localization is not an independent numeric crosscheck.
        return ReaderResult(result.value, result.confidence,
                            (*result.sources, "diagnostic_component_rows"), False)


def build_readers(profile) -> dict:
    native, result = profile.build_readers(), {}
    allowed = {"kind", "format", "templates", "minimum_confidence", "psm",
               "whitelist", "executable", "white_text_threshold"}
    for field in ("round_timer", "ally_score", "enemy_score"):
        spec = profile.raw.get("readers", {}).get(field)
        if (not isinstance(spec, dict) or set(spec) - allowed or spec.get("kind") != "digits"
                or spec.get("templates") != {} or field not in native
                or spec.get("format") != ("timer_mmss" if field == "round_timer" else "integer")):
            raise ValueError("wrap only explicit empty-template numeric proposals, not strict ones")
        result[field] = LocalizedDigitsReader(native[field], timer=field == "round_timer",
                                              minimum=spec.get("minimum_confidence"))
    return result
