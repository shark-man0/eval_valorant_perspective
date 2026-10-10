"""Enforce frame-bound world reviews before diagnostic scene tracking.

Reviews are offline evidence, not a runtime semantic recognizer or producer
qualification. Never infer world ownership from a non-timer rectangle alone.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass

import numpy as np

from scripts.diagnostics.scene_world_chain import ReviewedWorldChain, _validate_resolution


@dataclass(frozen=True)
class FrameWorldReview:
    source_video_sha256: str
    input_pixel_sha256: str
    source_pts_ticks: int
    source_epoch: str
    regions: tuple[tuple[tuple[int, int, int, int], str], ...]
    provenance: str


def approved_world_boxes(image, review, video_hash, epoch):
    if not isinstance(review, FrameWorldReview):
        raise ValueError("explicit frame world review required")
    if (
        review.source_video_sha256 != video_hash
        or review.source_epoch != epoch
        or not isinstance(review.provenance, str)
        or not review.provenance.strip()
        or type(review.source_pts_ticks) is not int
        or review.source_pts_ticks < 0
        or review.input_pixel_sha256 != hashlib.sha256(image.tobytes()).hexdigest()
    ):
        raise ValueError("world review source/pixel/epoch/provenance binding differs")
    if (
        not isinstance(video_hash, str)
        or len(video_hash) != 64
        or any(c not in "0123456789abcdef" for c in video_hash)
        or not isinstance(epoch, str)
        or not epoch.strip()
    ):
        raise ValueError("explicit video SHA256 and source epoch required")
    if not isinstance(review.regions, tuple) or any(
        not isinstance(row, tuple) or len(row) != 2 for row in review.regions
    ):
        raise ValueError("explicit immutable region review entries required")
    seen, approved = set(), []
    for box, status in review.regions:
        if (
            not isinstance(box, tuple)
            or len(box) != 4
            or any(type(v) is not int for v in box)
            or box in seen
        ):
            raise ValueError("unique integral reviewed boxes required")
        seen.add(box)
        _validate_resolution(image, [box], 1)
        if not isinstance(status, str) or status not in {"world_only", "contaminated", "unknown"}:
            raise ValueError("explicit world-only/contaminated/unknown status required")
        if status == "world_only":
            approved.append(box)
    for box, status in review.regions:
        if status != "world_only" and any(
            box[0] < positive[2]
            and box[2] > positive[0]
            and box[1] < positive[3]
            and box[3] > positive[1]
            for positive in approved
        ):
            raise ValueError("contradictory world/nonworld region reviews")
    if len(approved) < 3:
        raise ValueError("at least three reviewed world-only seed regions required")
    return tuple(approved)


class ReviewedSceneDiagnostic:
    """A terminated chain never rejoins, even if a later review is complete."""

    def __init__(self, seed, review, *, source_video_sha256, source_epoch, projected=False):
        self.video_hash = source_video_sha256
        self.epoch = source_epoch
        self.boxes = approved_world_boxes(seed, review, self.video_hash, self.epoch)
        self.previous_tick = review.source_pts_ticks
        self.terminated = False
        if type(projected) is not bool:
            raise ValueError("explicit projected mode boolean required")
        self.projected = projected
        options = {}
        if projected:
            options["world_mask"] = self._mask(seed, self.boxes)
        self.chain = ReviewedWorldChain(
            seed,
            self.boxes,
            support_mode="projected_world" if projected else "adjacent_dense_world",
            dense_footprint="full_valid",
            seed_membership="symmetric_final",
            **options,
        )

    @staticmethod
    def _mask(image, boxes):
        mask = np.zeros(image.shape, bool)
        for x1, y1, x2, y2 in boxes:
            mask[y1:y2, x1:x2] = True
        return mask

    def advance(self, current, review=None, *, discontinuity=False):
        def reject(reason):
            self.terminated = True
            self.chain.tracks.clear()
            self.chain.previous_dense_regions.clear()
            return {
                "reason": reason,
                "descriptive_supported": False,
                "runtime_proof_authorized": False,
            }

        if self.terminated:
            return reject("reviewed_chain_terminated")
        if discontinuity:
            return reject("explicit_source_discontinuity")
        try:
            approved = approved_world_boxes(current, review, self.video_hash, self.epoch)
        except ValueError:
            return reject("current_world_review_missing_or_invalid")
        if review.source_pts_ticks - self.previous_tick != 256:
            return reject("native_gap_or_stale_review")
        if self.projected:
            mask = self._mask(current, approved)
            if not all(mask[y1:y2, x1:x2].all() for x1, y1, x2, y2 in self.boxes):
                return reject("current_seed_footprint_occluded_or_unreviewed")
            result = self.chain.advance(current, current_world=mask)
        else:
            if not set(self.boxes).issubset(approved):
                return reject("current_seed_footprint_occluded_or_unreviewed")
            result = self.chain.advance(current)
        self.previous_tick = review.source_pts_ticks
        if not result["descriptive_supported"]:
            self.terminated = True
        return result
