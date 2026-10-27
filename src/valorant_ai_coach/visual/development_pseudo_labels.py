"""Development pseudo labels: machine hypotheses never become human evidence.

Caller admission must verify registry anchors and native feature acquisition.
These metadata contracts do not certify pixels, camera identity or Map build.
"""

from __future__ import annotations

import math
from dataclasses import asdict, dataclass, replace
from datetime import datetime
from enum import StrEnum

from .development_learning_dataset import (
    FrameLabel,
    FrameRecord,
    Label,
    LabelOrigin,
    Split,
    Use,
    _is_sha256,
    validate_dataset,
    validate_use,
)
from .development_marker_features import _digest


class PseudoState(StrEnum):
    PSEUDO_CANDIDATE = "PSEUDO_CANDIDATE"
    PSEUDO_ADMITTED_FOR_TRAINING = "PSEUDO_ADMITTED_FOR_TRAINING"
    UNKNOWN = "UNKNOWN"
    HUMAN_CONFIRMED = "HUMAN_CONFIRMED"  # FrameLabel only; never a PseudoLabel.


@dataclass(frozen=True, slots=True)
class AppearanceVote:
    label: Label
    distance: float
    margin: float
    generator_fingerprint: str
    correlation_group: str

    def validate(self) -> None:
        if (
            not isinstance(self.label, Label)
            or any(
                type(v) not in (float, int) or not math.isfinite(v) or not 0 <= v <= 2
                for v in (self.distance, self.margin)
            )
            or not _is_sha256(self.generator_fingerprint)
            or not isinstance(self.correlation_group, str)
            or not self.correlation_group
        ):
            raise ValueError("Finite uncalibrated vote and generator provenance required")


@dataclass(frozen=True, slots=True)
class PseudoPolicy:
    expected_generators: tuple[str, ...]
    training_classes: tuple[Label, ...] = (Label.PLAYER,)
    maximum_distance: float = 0.35
    minimum_margin: float = 0.02
    minimum_diagnostic_support: int = 3
    minimum_observed_precision: float = 0.9

    def validate(self) -> None:
        if (
            not 2 <= len(self.expected_generators) <= 8
            or len(set(self.expected_generators)) != len(self.expected_generators)
            or not all(_is_sha256(v) for v in self.expected_generators)
            or not self.training_classes
            or len(set(self.training_classes)) != len(self.training_classes)
            or self.training_classes != (Label.PLAYER,)
            or type(self.minimum_diagnostic_support) is not int
            or self.minimum_diagnostic_support < 1
            or any(
                type(v) not in (float, int) or not math.isfinite(v)
                for v in (
                    self.maximum_distance,
                    self.minimum_margin,
                    self.minimum_observed_precision,
                )
            )
            or not 0 < self.maximum_distance <= 2
            or not 0 <= self.minimum_margin <= 2
            or not 0 < self.minimum_observed_precision <= 1
        ):
            raise ValueError("Explicit bounded pseudo policy required")

    @property
    def fingerprint(self) -> str:
        self.validate()
        return _digest({"method": "correlated_teacher_pseudo_v1", **asdict(self)})


@dataclass(frozen=True, slots=True)
class AdmissionDiagnostic:
    """A caller-verified HUMAN validation diagnostic, not a probability bound.

    diagnostic_sha256 must identify the actual fixed rule, human labels and
    counts. A hash string or small perfect count alone is not qualification.
    """

    label: Label
    true_positive: int
    false_positive: int
    diagnostic_sha256: str
    policy_fingerprint: str
    split: Split = Split.DEVELOPMENT_VALIDATION

    def validate(self) -> None:
        if (
            not isinstance(self.label, Label)
            or self.label is Label.UNKNOWN
            or self.split is not Split.DEVELOPMENT_VALIDATION
            or any(type(v) is not int or v < 0 for v in (self.true_positive, self.false_positive))
            or not _is_sha256(self.diagnostic_sha256)
            or not _is_sha256(self.policy_fingerprint)
        ):
            raise ValueError("Human validation diagnostic and fixed rule required")


@dataclass(frozen=True, slots=True)
class PseudoLabel:
    frame: FrameRecord
    patch_sha256: str
    input_fingerprint: str
    label: Label
    state: PseudoState
    votes: tuple[AppearanceVote, ...]
    policy_fingerprint: str
    generated_at: str
    admission_diagnostic_sha256: str | None = None
    reasons: tuple[str, ...] = ()

    @property
    def ownership(self) -> str:
        return "UNKNOWN"

    @property
    def formal_outputs(self) -> int:
        return 0

    def validate(self) -> None:
        self.frame.validate()
        validate_use(self.frame, Use.PSEUDO_LABEL)
        if (
            not isinstance(self.label, Label)
            or not isinstance(self.state, PseudoState)
            or self.state is PseudoState.HUMAN_CONFIRMED
        ):
            raise ValueError("Pseudo labels cannot become HUMAN_CONFIRMED; retain FrameLabel")
        if (
            not _is_sha256(self.patch_sha256)
            or not _is_sha256(self.policy_fingerprint)
            or self.input_fingerprint
            != _digest({"frame": asdict(self.frame), "patch_sha256": self.patch_sha256})
            or not 2 <= len(self.votes) <= 8
        ):
            raise ValueError("Exact native patch and bounded pseudo provenance required")
        for vote in self.votes:
            vote.validate()
        if (
            len({v.generator_fingerprint for v in self.votes}) != len(self.votes)
            or self.label is not Label.UNKNOWN
            and any(v.label is not self.label for v in self.votes)
        ):
            raise ValueError("Pseudo class must agree with distinct teacher provenance")
        try:
            date = datetime.fromisoformat(self.generated_at)
        except (ValueError, TypeError) as exc:
            raise ValueError("Timezone-aware generator timestamp required") from exc
        if date.utcoffset() is None:
            raise ValueError("Timezone-aware generator timestamp required")
        if (self.state is PseudoState.UNKNOWN) != (self.label is Label.UNKNOWN):
            raise ValueError("UNKNOWN is an exclusion, never a trainable pseudo class")
        if self.state is PseudoState.PSEUDO_ADMITTED_FOR_TRAINING:
            if self.frame.split is not Split.DEVELOPMENT_TRAIN or not _is_sha256(
                self.admission_diagnostic_sha256
            ):
                raise ValueError(
                    "Semantic pseudo training requires development train and diagnostic"
                )
        elif self.admission_diagnostic_sha256 is not None:
            raise ValueError("Only admitted pseudo records carry admission evidence")


def consensus_label(votes: tuple[AppearanceVote, ...], policy: PseudoPolicy) -> Label:
    """Pure diagnostic decision; does not pseudo-label an evaluation source."""
    policy.validate()
    for vote in votes:
        vote.validate()
    if len(votes) != len(policy.expected_generators) or {
        v.generator_fingerprint for v in votes
    } != set(policy.expected_generators):
        raise ValueError("Each distinct expected teacher must supply exactly one vote")
    accepted = (
        len({v.label for v in votes}) == 1
        and votes[0].label is not Label.UNKNOWN
        and all(
            v.distance <= policy.maximum_distance and v.margin >= policy.minimum_margin
            for v in votes
        )
    )
    return votes[0].label if accepted else Label.UNKNOWN


def generate_candidate(
    frame: FrameRecord,
    patch_sha256: str,
    votes: tuple[AppearanceVote, ...],
    *,
    policy: PseudoPolicy,
    generated_at: str,
) -> PseudoLabel:
    """Generate a hypothesis, never admission or a human-confirmed label."""
    frame.validate()
    validate_use(frame, Use.PSEUDO_LABEL)
    label = consensus_label(votes, policy)
    record = PseudoLabel(
        frame,
        patch_sha256,
        _digest({"frame": asdict(frame), "patch_sha256": patch_sha256}),
        label,
        PseudoState.UNKNOWN if label is Label.UNKNOWN else PseudoState.PSEUDO_CANDIDATE,
        votes,
        policy.fingerprint,
        generated_at,
        reasons=("teacher_disagreement_or_rejection",) if label is Label.UNKNOWN else (),
    )
    record.validate()
    return record


def validation_diagnostic(
    frames: list[FrameRecord],
    labels: list[FrameLabel],
    votes: list[tuple[AppearanceVote, ...]],
    *,
    policy: PseudoPolicy,
    label: Label,
) -> AdmissionDiagnostic:
    """Compute rule support from separate HUMAN validation records only."""
    if (
        not 1 <= len(frames) <= 4096
        or len(frames) != len(labels)
        or len(frames) != len(votes)
        or not isinstance(label, Label)
        or label is Label.UNKNOWN
    ):
        raise ValueError("Paired bounded human validation examples required")
    validate_dataset(frames, labels)
    for frame, human in zip(frames, labels, strict=True):
        validate_use(frame, Use.SELECT, human, dataset_frames=frames)
        if human.origin is not LabelOrigin.HUMAN_CONFIRMED or human.label is Label.UNKNOWN:
            raise ValueError("Admission diagnosis requires human-confirmed semantic labels")
    predictions = [consensus_label(v, policy) for v in votes]
    tp = sum(p is label and h.label is label for p, h in zip(predictions, labels, strict=True))
    fp = sum(p is label and h.label is not label for p, h in zip(predictions, labels, strict=True))
    digest = _digest(
        {
            "frames": [asdict(f) for f in frames],
            "human_labels": [asdict(h) for h in labels],
            "votes": [[asdict(v) for v in row] for row in votes],
            "policy": policy.fingerprint,
            "class": label.value,
        }
    )
    return AdmissionDiagnostic(label, tp, fp, digest, policy.fingerprint)


def admit_candidate(
    record: PseudoLabel,
    *,
    policy: PseudoPolicy,
    diagnostic: AdmissionDiagnostic,
) -> PseudoLabel:
    """Bounded development admission; correlated agreement does not establish GT."""
    record.validate()
    diagnostic.validate()
    if (
        record.policy_fingerprint != policy.fingerprint
        or diagnostic.policy_fingerprint != policy.fingerprint
    ):
        raise ValueError("Pseudo generator/admission policy changed")
    if consensus_label(record.votes, policy) is not record.label:
        raise ValueError("Pseudo class no longer meets fixed teacher policy")
    if record.state is PseudoState.PSEUDO_ADMITTED_FOR_TRAINING:
        if record.admission_diagnostic_sha256 != diagnostic.diagnostic_sha256:
            raise ValueError("Cannot silently replace pseudo admission evidence")
        return record
    support = diagnostic.true_positive + diagnostic.false_positive
    precision = diagnostic.true_positive / support if support else 0.0
    reasons = list(record.reasons)
    if record.state is PseudoState.UNKNOWN:
        reasons.append("unknown_not_admitted")
    if record.frame.split is not Split.DEVELOPMENT_TRAIN:
        reasons.append("semantic_training_split_disallowed")
    if record.label not in policy.training_classes:
        reasons.append("class_excluded_from_pseudo_training")
    if (
        diagnostic.label is not record.label
        or support < policy.minimum_diagnostic_support
        or precision < policy.minimum_observed_precision
    ):
        reasons.append("insufficient_human_validation_diagnostic")
    if reasons:
        return replace(record, reasons=tuple(dict.fromkeys(reasons)))
    result = replace(
        record,
        state=PseudoState.PSEUDO_ADMITTED_FOR_TRAINING,
        admission_diagnostic_sha256=diagnostic.diagnostic_sha256,
    )
    result.validate()
    return result
