"""Fail-closed data lineage and physical-match split contract for map learning.

This contract records development provenance only. It never authorizes ownership
or formal game facts. Physical-match identity is caller-supplied and conservative:
uncertain sources must share a leakage_group_id.
"""

from __future__ import annotations

import math
import re
from collections.abc import Iterable
from dataclasses import dataclass
from enum import StrEnum
from fractions import Fraction

QUALIFICATION = "development_only"
OWNERSHIP = "UNKNOWN"
FORMAL_OUTPUTS = 0
_SHA256 = re.compile(r"[0-9a-f]{64}\Z")


def _is_sha256(value: object) -> bool:
    return isinstance(value, str) and _SHA256.fullmatch(value) is not None


class Split(StrEnum):
    SSL_TRAIN = "SSL_TRAIN"
    DEVELOPMENT_TRAIN = "DEVELOPMENT_TRAIN"
    DEVELOPMENT_VALIDATION = "DEVELOPMENT_VALIDATION"
    DEVELOPMENT_FROZEN_TEST = "DEVELOPMENT_FROZEN_TEST"


class Use(StrEnum):
    SSL = "SSL"
    SUPERVISED_TRAIN = "SUPERVISED_TRAIN"
    PSEUDO_LABEL = "PSEUDO_LABEL"
    SELECT = "SELECT"
    EVALUATE = "EVALUATE"
    HUMAN_REVIEW = "HUMAN_REVIEW"


class Label(StrEnum):
    PLAYER = "PLAYER"
    DEATH_MARKER = "DEATH_MARKER"
    UI = "UI"
    BACKGROUND = "BACKGROUND"
    UNKNOWN = "UNKNOWN"


class LabelOrigin(StrEnum):
    HUMAN_CONFIRMED = "human_confirmed"
    UNLABELED = "unlabeled"
    PSEUDO = "pseudo"


@dataclass(frozen=True, slots=True)
class SourceAcceptance:
    """Accepted source-development receipt and independently trusted file hashes."""

    accepted: bool
    manifest_sha256: str
    allocation_sha256: str
    trusted_manifest_sha256: str
    trusted_allocation_sha256: str

    def validate(self) -> None:
        if self.accepted is not True:
            raise ValueError("accepted source-development receipt required")
        for name in ("manifest_sha256", "allocation_sha256",
                     "trusted_manifest_sha256", "trusted_allocation_sha256"):
            value = getattr(self, name)
            if not _is_sha256(value):
                raise ValueError(f"valid {name} required")
        if self.manifest_sha256 != self.trusted_manifest_sha256:
            raise ValueError("manifest trusted hash mismatch")
        if self.allocation_sha256 != self.trusted_allocation_sha256:
            raise ValueError("allocation trusted hash mismatch")


@dataclass(frozen=True, slots=True)
class FrameRecord:
    source_sha256: str
    acquisition_id: str
    native_epoch: str
    native_pts_tick: int
    native_time_base: str
    frame_sha256: str
    pixel_sha256: str
    frame_size_px: tuple[int, int]
    roi_xywh: tuple[float, float, float, float]
    extraction_fingerprint: str
    exposure_fingerprint: str
    leakage_group_id: str
    split: Split
    source_acceptance: SourceAcceptance

    def validate(self) -> None:
        self.source_acceptance.validate()
        for name in ("source_sha256", "frame_sha256", "pixel_sha256"):
            if not _is_sha256(getattr(self, name)):
                raise ValueError(f"valid {name} required")
        for name in ("extraction_fingerprint", "exposure_fingerprint"):
            if not _is_sha256(getattr(self, name)):
                raise ValueError(f"valid {name} required")
        if any(not isinstance(v, str) or not v for v in (
                self.acquisition_id, self.native_epoch, self.leakage_group_id)):
            raise ValueError("acquisition, epoch and leakage group required")
        if (not isinstance(self.native_pts_tick, int) or isinstance(self.native_pts_tick, bool)):
            raise ValueError("integer native PTS ticks required")
        try:
            time_base = Fraction(self.native_time_base)
        except (ValueError, ZeroDivisionError) as exc:
            raise ValueError("positive rational native time base required") from exc
        if time_base <= 0 or str(time_base) != self.native_time_base:
            raise ValueError("canonical positive rational native time base required")
        if (len(self.frame_size_px) != 2 or any(
                not isinstance(v, int) or isinstance(v, bool) or v <= 0
                for v in self.frame_size_px)):
            raise ValueError("positive integer frame dimensions required")
        if len(self.roi_xywh) != 4 or any(
                isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v)
                for v in self.roi_xywh):
            raise ValueError("finite ROI required")
        x, y, width, height = self.roi_xywh
        frame_width, frame_height = self.frame_size_px
        if (x < 0 or y < 0 or width <= 0 or height <= 0
                or x + width > frame_width or y + height > frame_height):
            raise ValueError("ROI must be positive and inside the source frame")
        if not isinstance(self.split, Split):
            raise ValueError("known physical-match split required")


@dataclass(frozen=True, slots=True)
class FrameLabel:
    frame_sha256: str
    label: Label
    origin: LabelOrigin
    roi_xywh: tuple[float, float, float, float] | None = None

    def validate(self) -> None:
        if not _is_sha256(self.frame_sha256):
            raise ValueError("valid label frame hash required")
        if not isinstance(self.label, Label) or not isinstance(self.origin, LabelOrigin):
            raise ValueError("known label and distinct label origin required")
        if self.roi_xywh is not None and (
                len(self.roi_xywh) != 4
                or any(isinstance(v, bool) or not isinstance(v, (int, float))
                       or not math.isfinite(v) for v in self.roi_xywh)):
            raise ValueError("finite label ROI required")
        if self.roi_xywh is not None:
            x, y, width, height = self.roi_xywh
            if x < 0 or y < 0 or width <= 0 or height <= 0:
                raise ValueError("positive label ROI required")


def validate_dataset(frames: Iterable[FrameRecord], labels: Iterable[FrameLabel] = ()) -> None:
    """Validate immutable lineage and reject physical/frame leakage across splits."""
    rows = tuple(frames)
    seen_groups: dict[str, Split] = {}
    seen_sources: dict[str, Split] = {}
    seen_frames: dict[str, Split] = {}
    seen_pixels: dict[str, Split] = {}
    for row in rows:
        row.validate()
        for identity, table in ((row.leakage_group_id, seen_groups),
                                (row.source_sha256, seen_sources),
                                (row.frame_sha256, seen_frames),
                                (row.pixel_sha256, seen_pixels)):
            prior = table.setdefault(identity, row.split)
            if prior != row.split:
                raise ValueError("physical group or duplicate frame crosses splits")
    known_rois: dict[str, set[tuple[float, float, float, float]]] = {}
    for row in rows:
        known_rois.setdefault(row.frame_sha256, set()).add(row.roi_xywh)
    labeled_observations: set[
        tuple[str, tuple[float, float, float, float]]
    ] = set()
    for label in labels:
        label.validate()
        frame_rois = known_rois.get(label.frame_sha256)
        if not frame_rois:
            raise ValueError("label must bind an included source frame")
        if label.roi_xywh is None:
            if len(frame_rois) != 1:
                raise ValueError("label ROI is ambiguous for this native frame")
            label_roi = next(iter(frame_rois))
        else:
            label_roi = label.roi_xywh
            if label_roi not in frame_rois:
                raise ValueError("label ROI must bind an included frame ROI")
        observation = label.frame_sha256, label_roi
        if observation in labeled_observations:
            raise ValueError("one explicit label record per frame ROI required")
        labeled_observations.add(observation)
        frame = next(row for row in rows if row.frame_sha256 == label.frame_sha256
                     and row.roi_xywh == label_roi)
        if (label.origin is LabelOrigin.PSEUDO
                and frame.split is Split.DEVELOPMENT_FROZEN_TEST):
            raise ValueError("frozen test cannot receive pseudo labels")
        if label.origin is LabelOrigin.UNLABELED and label.label is not Label.UNKNOWN:
            raise ValueError("unlabeled rows must remain UNKNOWN")
        if label.origin is LabelOrigin.PSEUDO and label.label is Label.UNKNOWN:
            # UNKNOWN is an exclusion marker, not a trainable pseudo-class.
            continue
        if label.origin is LabelOrigin.HUMAN_CONFIRMED and label.label is Label.UNKNOWN:
            continue


def validate_use(
    frame: FrameRecord,
    use: Use,
    label: FrameLabel | None = None,
    *,
    dataset_frames: Iterable[FrameRecord] | None = None,
) -> None:
    """Authorize only split-appropriate learning, selection, review, or evaluation."""
    frame.validate()
    if not isinstance(use, Use):
        raise ValueError("known data use required")
    if label is not None:
        label.validate()
        if label.frame_sha256 != frame.frame_sha256:
            raise ValueError("label/frame binding mismatch")
        if label.roi_xywh is not None and label.roi_xywh != frame.roi_xywh:
            raise ValueError("label ROI/frame ROI mismatch")
        if label.roi_xywh is None:
            if dataset_frames is None:
                full_frame = (0.0, 0.0, float(frame.frame_size_px[0]),
                              float(frame.frame_size_px[1]))
                if frame.roi_xywh != full_frame:
                    raise ValueError("label ROI or complete dataset context required")
            else:
                related = tuple(row for row in dataset_frames
                                if row.frame_sha256 == frame.frame_sha256)
                rois = {row.roi_xywh for row in related}
                if len(rois) > 1:
                    raise ValueError("label ROI is ambiguous for this native frame")
                if not rois or rois != {frame.roi_xywh}:
                    raise ValueError("label ROI must bind an included frame ROI")
    if use is Use.HUMAN_REVIEW:
        return
    if use is Use.SSL and label is not None:
        raise ValueError("SSL use must not consume semantic labels")
    if frame.split is Split.DEVELOPMENT_FROZEN_TEST:
        if use is not Use.EVALUATE:
            raise ValueError("frozen test permits human review and evaluation only")
        if (label is None or label.origin is not LabelOrigin.HUMAN_CONFIRMED
                or label.label is Label.UNKNOWN):
            raise ValueError("frozen evaluation requires separately confirmed human labels")
        return
    if use is Use.EVALUATE:
        raise ValueError("evaluation is reserved for frozen test")
    if use is Use.SELECT and frame.split is not Split.DEVELOPMENT_VALIDATION:
        raise ValueError("model selection requires development validation")
    if use is Use.SSL and frame.split is not Split.SSL_TRAIN:
        raise ValueError("SSL training requires SSL_TRAIN")
    if use is Use.PSEUDO_LABEL and frame.split not in {
            Split.SSL_TRAIN, Split.DEVELOPMENT_TRAIN}:
        raise ValueError("pseudo labeling is unavailable for this split")
    if use is Use.SUPERVISED_TRAIN:
        if frame.split is not Split.DEVELOPMENT_TRAIN:
            raise ValueError("supervised training requires development train")
        if (label is None or label.origin is not LabelOrigin.HUMAN_CONFIRMED
                or label.label is Label.UNKNOWN):
            raise ValueError(
                "semantic supervised training requires human-confirmed non-UNKNOWN label"
            )
    if (use is Use.PSEUDO_LABEL and label is not None
            and label.origin is LabelOrigin.HUMAN_CONFIRMED):
        raise ValueError("human labels cannot be relabeled as pseudo")
