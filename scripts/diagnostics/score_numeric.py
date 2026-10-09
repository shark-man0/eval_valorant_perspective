"""Private score candidate replay. No qualification, identity or lifecycle claims."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import cv2
import numpy as np

from valorant_ai_coach.hud.readers import ReaderResult
from valorant_ai_coach.hud.templates import SubregionReader
from valorant_ai_coach.hud.timer_glyphs import StrictTimerGlyphReader


class DiagnosticScoreReader(StrictTimerGlyphReader):
    """Frozen white200/Gaussian3x3 hypothesis with a distinct integer grammar.

    All ten classes compete. Never infer score from timer, previous value,
    round, phase or expected labels. Segmentation rejects rather than repairing.
    """

    def __init__(self, templates):
        super().__init__(templates)
        self.comparison_templates = {
            digit: tuple(cv2.GaussianBlur(ref, (3, 3), 0) for ref in refs)
            for digit, refs in self.templates.items()
        }

    def read(self, image, roi):
        del image
        if (
            not isinstance(roi, np.ndarray) or roi.dtype != np.uint8 or not roi.size
            or roi.ndim not in (2, 3) or (roi.ndim == 3 and roi.shape[2] != 3)
            or min(roi.shape[:2]) < 2
        ):
            return self._reject("strict_score_invalid_roi")
        gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY) if roi.ndim == 3 else roi
        if float(gray.std()) < 1:
            return self._reject("strict_score_low_contrast_roi")
        enlarged = cv2.resize(gray, None, fx=2, fy=2, interpolation=cv2.INTER_CUBIC)
        _, mask = cv2.threshold(enlarged, 200, 255, cv2.THRESH_BINARY)
        if np.any(mask[0]) or np.any(mask[-1]) or np.any(mask[:, 0]) or np.any(mask[:, -1]):
            return self._reject("strict_score_foreground_touches_roi_border")
        count, _, stats, _ = cv2.connectedComponentsWithStats(mask, connectivity=8)
        components = sorted(
            [(int(x), int(y), int(w), int(h)) for x, y, w, h, area in stats[1:count]
             if area > 0], key=lambda component: component[0],
        )
        if len(components) not in (1, 2):
            return self._reject("strict_score_expected_one_or_two_digits")
        if len(components) == 2:
            (x1, y1, w1, h1), (x2, y2, _, h2) = components
            if (
                min(h1, h2) < .8 * max(h1, h2)
                or abs(y1 - y2) > .15 * max(h1, h2)
                or not 0 < x2 - (x1 + w1) <= max(h1, h2)
            ):
                return self._reject("strict_score_digit_layout_inconsistent")
        text, scores = [], []
        for x, y, width, height in components:
            glyph = cv2.GaussianBlur(self._normalize_known_white(mask[y:y + height, x:x + width]),
                                     (3, 3), 0)
            ranked = []
            for digit, references in self.comparison_templates.items():
                matches = [float(cv2.matchTemplate(glyph, ref, cv2.TM_CCOEFF_NORMED)[0, 0])
                           for ref in references]
                if not all(np.isfinite(value) for value in matches):
                    return self._reject("strict_score_nonfinite_glyph_score")
                ranked.append((max(matches), digit))
            ranked.sort(reverse=True)
            best, digit = ranked[0]
            if best < self.THRESHOLD:
                return self._reject("strict_score_glyph_below_0_90")
            if best - ranked[1][0] < self.CLASS_MARGIN:
                return self._reject("strict_score_glyph_competitor_gap_below_0_04")
            text.append(digit)
            scores.append(best)
        display = "".join(text)
        if len(display) == 2 and display.startswith("0"):
            return self._reject("strict_score_leading_zero")
        return ReaderResult(display, min(scores),
                            ("strict_score_glyphs", "comparison_gaussian3x3_v1",
                             "foreground_white200_v1"))


def load_score_candidate(path: Path):
    """Require the frozen declaration; hash its bytes and every used reference."""
    path = path.resolve()
    encoded = path.read_bytes()
    raw = json.loads(encoded)
    readers = raw.get("readers", {})
    if set(readers) != {"ally_score", "enemy_score"}:
        raise ValueError("diagnostic score candidate requires exactly both score roles")
    digest = hashlib.sha256(encoded)
    result = {}
    for role, spec in sorted(readers.items()):
        if (
            spec.get("kind") != "strict_score_glyphs"
            or type(spec.get("glyph_threshold")) not in (int, float)
            or spec["glyph_threshold"] != .90
            or type(spec.get("glyph_margin")) not in (int, float)
            or spec["glyph_margin"] != .04
            or spec.get("comparison_preprocessing") != "gaussian3x3_v1"
            or spec.get("foreground_preprocessing") != "white200_v1"
            or set(spec.get("templates", {})) != set("0123456789")
        ):
            raise ValueError("unsupported frozen score candidate declaration")
        bounds = spec.get("subregion_norm")
        if (
            not isinstance(bounds, list) or len(bounds) != 4
            or any(type(value) not in (int, float) or not np.isfinite(value) for value in bounds)
            or not 0 <= bounds[0] < bounds[2] <= 1
            or not 0 <= bounds[1] < bounds[3] <= 1
        ):
            raise ValueError("invalid score subregion bounds")
        templates = {}
        for digit, name in sorted(spec["templates"].items()):
            if not isinstance(name, str):
                raise ValueError("invalid score reference path")
            asset = (path.parent / name).resolve()
            if not asset.is_relative_to(path.parent):
                raise ValueError("score reference leaves candidate directory")
            data = asset.read_bytes()
            digest.update(role.encode() + digit.encode() + hashlib.sha256(data).digest())
            image = cv2.imdecode(np.frombuffer(data, np.uint8), cv2.IMREAD_GRAYSCALE)
            if image is None:
                raise ValueError("unreadable score reference")
            templates[digit] = [image]
        result[role] = SubregionReader(DiagnosticScoreReader(templates), tuple(bounds))
    return result, digest.hexdigest()
