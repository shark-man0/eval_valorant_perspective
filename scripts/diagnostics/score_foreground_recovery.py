"""Offline same-pixel Score fragments, abstention and native history.

No source decoder, production hook, GT writer or temporal digit filling.
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any

import cv2
import numpy as np

from scripts.diagnostics.hud_feature_contract import validate_frame
from scripts.diagnostics.hud_glyph_learning import score_digits
from scripts.diagnostics.round_lifecycle_evidence import review_scores
from scripts.diagnostics.score_hypotheses import _mask, generate_score_hypotheses
from valorant_ai_coach.hud.score_glyphs import StrictScoreGlyphReader
from valorant_ai_coach.hud.timer_glyphs import ImageU8


def grouped_score(mask: ImageU8, reader: StrictScoreGlyphReader) -> dict[str, Any]:
    """Group original fragments by overlapping x ranges; never bridge pixels.

    The entire foreground is retained, including suspicious pieces. A background
    line joining two digits will normally collapse the groups and fail matching;
    its pixels are never silently removed to manufacture a digit.
    """
    if (
        not isinstance(mask, np.ndarray)
        or mask.dtype != np.uint8
        or mask.ndim != 2
        or mask.size == 0
        or mask.size > 1048576
        or not np.isin(mask, (0, 255)).all()
    ):
        raise ValueError("bounded_binary_fragment_mask_required")
    if np.any(mask[0]) or np.any(mask[-1]) or np.any(mask[:, 0]) or np.any(mask[:, -1]):
        return {"value": None, "reason": "border_foreground"}
    n, labels, stats, _ = cv2.connectedComponentsWithStats(mask, connectivity=8)
    if not 1 <= n - 1 <= 8:
        return {"value": None, "reason": "component_budget_or_empty"}
    groups: list[list[int]] = []
    for i in sorted(range(1, n), key=lambda i: int(stats[i, 0])):
        x, _, w, _, _ = map(int, stats[i])
        if groups and x < max(int(stats[j, 0] + stats[j, 2]) for j in groups[-1]):
            groups[-1].append(i)
        else:
            groups.append([i])
    if len(groups) not in (1, 2):
        return {"value": None, "reason": "group_count", "groups": groups}
    boxes = []
    rankings = []
    for group in groups:
        yy, xx = np.where(np.isin(labels, group))
        x, y, w, h = (
            int(xx.min()),
            int(yy.min()),
            int(xx.max() - xx.min() + 1),
            int(yy.max() - yy.min() + 1),
        )
        boxes.append((x, y, w, h))
        original = np.where(np.isin(labels[y : y + h, x : x + w], group), 255, 0).astype(np.uint8)
        glyph = reader._comparison_image(reader._normalize_known_white(original))
        scores = [
            (
                max(
                    float(cv2.matchTemplate(glyph, ref, cv2.TM_CCOEFF_NORMED)[0, 0]) for ref in refs
                ),
                digit,
            )
            for digit, refs in reader.comparison_templates.items()
        ]
        if any(not np.isfinite(v) for v, _ in scores):
            raise ValueError("nonfinite_fragment_score")
        rankings.append(sorted(scores, reverse=True))
    if len(boxes) == 2:
        (x, y, w, h), (x2, y2, _, hh) = boxes
        if (
            min(h, hh) < 0.8 * max(h, hh)
            or abs(y - y2) > 0.15 * max(h, hh)
            or not 0 < x2 - (x + w) <= max(h, hh)
        ):
            return {"value": None, "reason": "layout", "boxes": boxes}
    valid = all(r[0][0] >= 0.90 and r[0][0] - r[1][0] >= 0.04 for r in rankings)
    text = "".join(r[0][1] for r in rankings)
    if len(text) == 2 and text[0] == "0":
        valid = False
    return {
        "value": text if valid else None,
        "reason": "supported" if valid else "class_support",
        "boxes": boxes,
        "groups": groups,
        "rankings": rankings,
        "foreground_dropped": 0,
        "pixels_synthesized": 0,
    }


def recover_score(roi: ImageU8, reader: StrictScoreGlyphReader) -> dict[str, Any]:
    """Neutral-white subset and fragment grouping, retaining strict acceptance."""
    # Existing bounded generator validates image shape/dtype/budget first.
    if not isinstance(roi, np.ndarray) or roi.ndim != 3 or roi.shape[-1] != 3:
        raise ValueError("native_BGR_Score_crop_required")
    if (
        roi.dtype != np.uint8
        or not roi.size
        or min(roi.shape[:2]) < 8
        or roi.shape[0] * roi.shape[1] > 262144
    ):
        raise ValueError("invalid_fragment_ROI")
    gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
    neutral = (roi.min(axis=2) >= 200) & (roi.max(axis=2).astype(int) - roi.min(axis=2) <= 35)
    selected = np.where(neutral, gray, 0).astype(np.uint8)
    core = StrictScoreGlyphReader(
        reader.templates,
        comparison_preprocessing="gaussian3x3_v1",
        foreground_preprocessing="white200_v1",
    )
    direct = core.read(roi, selected)
    group = grouped_score(_mask(selected, "white"), core)
    # Grouping yielded no additional supported read in the fixed experiment.
    # Retain it as a diagnostic/cross-check, never a group-only numeric rescue.
    value = direct.value
    if group["value"] is not None and value is not None and group["value"] != value:
        value = None
    candidates = generate_score_hypotheses(selected, core, methods=("white",))
    return {
        "value": value,
        "neutral_direct": direct.value,
        "grouped": group,
        "candidate_report": candidates,
        "neutral_native_pixels": int(neutral.sum()),
        "reason": "current_pixel_support"
        if value is not None
        else "insufficient_or_conflicting_support",
        "missing_native_pixels_filled": False,
        "normalization": "existing 2x cubic and glyph normalization, not new source evidence",
        "production_qualified": False,
        "formal_events": [],
    }


class ScoreReadHistory:
    """Reject-only local temporal context; previous text never becomes current.

    Adjacency is a native transport observation, not proof of semantic source
    continuity. No relation is formed across a gap, epoch or an explicit cut.
    """

    def __init__(self) -> None:
        self.previous: dict[str, Any] | None = None
        self.last_direct: dict[str, Any] | None = None
        self.possible_digit_loss = False

    def observe(
        self,
        frame: dict[str, Any],
        *,
        direct: str | None,
        recovery: str | None,
        geometry: bool,
        expected_step: int,
        native_continuity_verified: bool,
        explicit_cut: bool = False,
        foreground_pixels: int | None = None,
    ) -> dict[str, Any]:
        validate_frame(frame)
        for value in [direct, recovery]:
            if value is not None:
                score_digits(value)
        if type(expected_step) is not int or expected_step <= 0:
            raise ValueError("positive_native_step_required")
        if foreground_pixels is not None and (
            type(foreground_pixels) is not int or not 0 <= foreground_pixels <= 262144
        ):
            raise ValueError("bounded_current_foreground_count_required")
        if (
            type(geometry) is not bool
            or type(native_continuity_verified) is not bool
            or type(explicit_cut) is not bool
        ):
            raise ValueError("explicit_temporal_flags_required")
        adjacent = (
            self.previous is not None
            and native_continuity_verified
            and not explicit_cut
            and frame.get("discontinuity", False) is False
            and self.previous.get("discontinuity", False) is False
            and all(
                frame[k] == self.previous[k]
                for k in ["source_id", "source_sha256", "epoch", "time_base"]
            )
            and frame["tick"] - self.previous["tick"] == expected_step
        )
        if not adjacent:
            self.last_direct = None
            self.possible_digit_loss = False
        prior = deepcopy(self.last_direct)
        value = direct if geometry else None
        reason = "direct_current_frame" if value is not None else "current_unknown"
        if value is None and geometry and recovery is not None:
            if (
                adjacent
                and prior is not None
                and self.previous is not None
                and prior["frame"]["tick"] == self.previous["tick"]
                and recovery == prior["value"]
            ):
                value = recovery
                reason = "current_pixel_recovery_with_temporal_agreement"
            else:
                reason = "recovery_without_adjacent_agreement"
        if (
            geometry
            and adjacent
            and prior is not None
            and direct is not None
            and len(prior["value"]) == 2
            and len(direct) == 1
            and prior["value"].endswith(direct)
            and foreground_pixels is not None
            and prior.get("foreground_pixels")
            and foreground_pixels * 4 < prior["foreground_pixels"] * 3
        ):
            self.possible_digit_loss = True
        if direct is not None and len(direct) == 2 and geometry:
            self.possible_digit_loss = False
        if self.possible_digit_loss:
            value = None
            reason = "possible_digit_loss_not_completed_from_history"
        if direct is not None and geometry and not self.possible_digit_loss:
            self.last_direct = {
                "value": direct,
                "frame": deepcopy(frame),
                "foreground_pixels": foreground_pixels,
            }
        self.previous = deepcopy(frame)
        return {
            "frame": deepcopy(frame),
            "current_direct_read": direct,
            "current_value": value,
            "previous_direct_observation": prior,
            "reason": reason,
            "native_adjacent": adjacent,
            "possible_digit_loss": self.possible_digit_loss,
            "display_presence": "UNVERIFIED",
            "visual_source_continuity": "UNVERIFIED",
            "view_owner_state_used_as_Score_truth": False,
            "state": "UNKNOWN" if value is None else "DEVELOPMENT_ONLY",
            "formal_events": [],
        }


def review_visibility(packet: dict[str, Any], response: dict[str, Any]) -> dict[str, Any]:
    """Small extension of existing blind literal review, not a separate GT system."""
    numeric = review_scores(packet, response)
    cases = {c["id"]: c for c in packet["cases"]}
    rows = []
    for answer in response["cases"]:
        c = cases[answer["id"]]
        validate_frame(c["frame"])
        for side in ["left", "right"]:
            state = answer.get(side + "_visibility", "UNKNOWN")
            value = answer.get(side + "_score")
            if (
                state not in {"VISIBLE", "ABSENT", "PARTIAL", "UNKNOWN"}
                or not answer["reviewed"]
                and state != "UNKNOWN"
                or state != "VISIBLE"
                and value is not None
            ):
                raise ValueError("explicit_bound_visibility_without_inferred_digits_required")
            rows.append(
                {
                    "case_id": c["id"],
                    "side": side,
                    "frame": c["frame"],
                    "visibility": state,
                    "literal": value,
                    "origin": "human",
                    "reviewer": response["reviewer"],
                    "reviewed": answer["reviewed"],
                    "approved_gt": False,
                    "formal_events": [],
                }
            )
    return {
        "numeric_contract": numeric,
        "observations": rows,
        "approved_gt": False,
        "qualification_created": False,
        "formal_events": [],
    }
