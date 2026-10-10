"""Opt-in, source-supported semantic banner text; never ownership evidence."""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from typing import Any

import cv2
import numpy as np
from numpy.typing import NDArray

from .round_lifecycle import (
    MAX_SAMPLE_GAP_SEC,
    MIN_START_CONFIRMATION_SEC,
    SEMANTIC_PHASE_CONFIDENCE_KEY,
)
from .weapon_identity import masked_score

MATCHER = "semantic_text_ncc_v1"
SIGNAL_ROIS = {
    "buy_phase_template": "center_phase_banner",
    "round_end_template": "round_end_banner",
    # Separate positively matched absence structure; a failed presence match
    # must never populate this signal. Same support/contrast/NCC requirements.
    "phase_absence_template": "center_phase_banner",
}
CONFIDENCE_KEY = SEMANTIC_PHASE_CONFIDENCE_KEY

ImageU8 = NDArray[np.uint8]


class SemanticTextReference:
    """Require every spatial text group, with at least three source exemplars.

    Masks include glyph foreground and its contrast neighbourhood. Text labels
    and training images belong to the profile; runtime has no PTS or GT input.
    Nonmatches, incomplete glyph groups and undefined NCC remain unknown.
    """

    def __init__(
        self,
        reference: ImageU8,
        mask: ImageU8,
        regions: ImageU8,
        training: Sequence[tuple[str, ImageU8]],
        threshold: float,
    ) -> None:
        if not np.isfinite(threshold) or not 0.90 <= threshold <= 1.0:
            raise ValueError("semantic text requires NCC >= .90")
        if (
            reference.ndim != 2
            or reference.size == 0
            or mask.shape != reference.shape
            or regions.shape != reference.shape
            or not set(np.unique(mask)).issubset({0, 255})
            or np.any((regions > 0) != (mask > 0))
        ):
            raise ValueError("invalid semantic text mask or support regions")
        labels = set(int(value) for value in np.unique(regions))
        count = int(regions.max())
        if count not in (3, 4) or labels != set(range(count + 1)):
            raise ValueError("semantic text requires three or four spatial groups")
        masks = []
        spans = []
        for group in range(1, count + 1):
            selected = regions == group
            if np.count_nonzero(selected) < 32 or float(reference[selected].std()) < 5:
                raise ValueError("semantic text group has insufficient contrast/support")
            xs = np.nonzero(selected)[1]
            spans.append((int(xs.min()), int(xs.max())))
            masks.append(np.asarray(selected, dtype=np.uint8) * 255)
        ordered = sorted(spans)
        if (
            any(a[1] >= b[0] for a, b in zip(ordered, ordered[1:], strict=False))
            or ordered[-1][1] - ordered[0][0] < reference.shape[1] * 0.5
        ):
            raise ValueError("semantic text groups must cover separate portions of the text")
        self.reference = reference.copy()
        self.masks = tuple(masks)
        self.threshold = threshold
        hashes = [frame_hash for frame_hash, _ in training]
        if (
            len(training) < 3
            or len(set(hashes)) != len(hashes)
            or any(re.fullmatch(r"[0-9a-f]{64}", value) is None for value in hashes)
        ):
            raise ValueError("semantic text requires three distinct source-frame hashes")
        self.training_support = sum(self.score(image) >= threshold for _, image in training)
        if self.training_support < 3:
            raise ValueError("semantic text training support insufficient")

    def score(self, image: ImageU8) -> float:
        """Minimum per-group masked NCC; no search or missing-group substitution."""
        return min(masked_score(self.reference, image, mask) for mask in self.masks)

    def measure(self, image: ImageU8) -> dict[str, Any]:
        """Expose rejection evidence, never infer absence from a nonmatch.

        Use the identical scoring function and threshold as ``score``. A
        below-threshold group can mean different text, occlusion or unavailable
        contrast; it cannot authorize a phase-disappearance event.
        """
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY) if image.ndim == 3 else image
        shape_valid = gray.shape == self.reference.shape
        groups: list[dict[str, Any]] = []
        for index, mask in enumerate(self.masks, start=1):
            score = masked_score(self.reference, image, mask)
            contrast = float(gray[mask > 0].std()) if shape_valid else None
            groups.append({
                "group": index,
                "mask_population": int(np.count_nonzero(mask)),
                "current_std": contrast,
                "score": score,
                "reason": (
                    "shape_mismatch" if not shape_valid else
                    "contrast_unavailable" if contrast is not None and contrast < 5 else
                    "matched" if score >= self.threshold else "below_threshold"
                ),
            })
        score = min(group["score"] for group in groups)
        return {
            "matcher": MATCHER,
            "threshold": self.threshold,
            "score": score,
            "groups": groups,
            "presence": True if score >= self.threshold else None,
            "absence_checked": False,
            "runtime_transition_authorized": False,
        }


class SemanticPhaseContext:
    """Corroborate explicit purchase text without claiming player ownership.

    Legacy texture/templates still require their existing score/state context.
    Only source-supported text uses this path. It confirms a phase flag, never
    a round boundary, and cannot carry context across missing evidence or cuts.
    """

    def __init__(self) -> None:
        self._first_time: float | None = None
        self._last_time: float | None = None
        self._confidence = 0.0

    def advance(
        self, time_sec: float, signals: Mapping[str, Any], *, geometry_valid: bool
    ) -> dict[str, Any]:
        score = signals.get("buy_phase_template_confidence")
        valid = (
            geometry_valid
            and np.isfinite(time_sec)
            and signals.get("buy_phase_template") is True
            and signals.get("buy_phase_template_matcher") == MATCHER
            and isinstance(score, (float, int))
            and not isinstance(score, bool)
            and np.isfinite(score)
            and 0.90 <= score <= 1.0
        )
        interrupted = (
            not valid
            or signals.get("content_jump") is True
            or signals.get("discontinuity") is True
            or self._last_time is not None
            and not 0 < time_sec - self._last_time <= MAX_SAMPLE_GAP_SEC
        )
        if interrupted:
            self._first_time = self._last_time = None
            self._confidence = 0.0
        if not valid:
            return {}
        assert isinstance(score, (int, float))
        if self._first_time is None:
            self._first_time = time_sec
            self._confidence = float(score)
        self._confidence = min(self._confidence, float(score))
        self._last_time = time_sec
        if time_sec - self._first_time < MIN_START_CONFIRMATION_SEC:
            return {}
        return {
            "semantic_buy_phase_confirmed": True,
            "semantic_buy_phase_confidence": self._confidence,
            "semantic_buy_phase_source_pts": [self._first_time, time_sec],
        }
