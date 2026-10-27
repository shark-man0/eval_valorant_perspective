"""Reuse exact-observation human annotations without relabeling machine output."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

from .development_learning_dataset import (
    FrameLabel,
    FrameRecord,
    LabelOrigin,
    _is_sha256,
    validate_dataset,
)
from .development_marker_features import _digest


def observation_key(frame: FrameRecord) -> str:
    """Bind native identity and patch ROI, not changing experiment bookkeeping."""
    frame.validate()
    fields = asdict(frame)
    fields.pop("extraction_fingerprint")
    fields.pop("exposure_fingerprint")
    fields.pop("source_acceptance")
    return _digest(fields)


@dataclass(frozen=True, slots=True)
class HumanReviewReference:
    frame: FrameRecord
    annotation: FrameLabel
    review_sha256: str
    prediction_visibility: str
    prior_usage_sha256: tuple[str, ...] = ()
    click_uncertainty: str = "UNMEASURED"

    def validate(self) -> None:
        if (
            self.annotation.origin is not LabelOrigin.HUMAN_CONFIRMED
            or not _is_sha256(self.review_sha256)
            or self.prediction_visibility
            not in {"PREDICTION_BLIND", "PREDICTION_EXPOSED", "UNKNOWN"}
            or not all(_is_sha256(v) for v in self.prior_usage_sha256)
            or self.click_uncertainty != "UNMEASURED"
        ):
            raise ValueError("Existing human review provenance and unmeasured click error required")
        validate_dataset([self.frame], [self.annotation])


class HumanLabelInventory:
    """Caller verifies real private review evidence; hashes alone do not prove it.

    Identical references are deduplicated; conflicting human labels fail closed.
    Same-looking frames at a different PTS/acquisition do not inherit annotations.
    Unknown human labels remain distinct from unreviewed and OUT_OF_SCOPE items.
    """

    def __init__(self, references: list[HumanReviewReference]) -> None:
        if not 1 <= len(references) <= 4096:
            raise ValueError("Bounded existing human review references required")
        self._references: dict[str, list[HumanReviewReference]] = {}
        for reference in references:
            reference.validate()
            key = observation_key(reference.frame)
            bucket = self._references.setdefault(key, [])
            if bucket and bucket[0].annotation.label is not reference.annotation.label:
                raise ValueError("Conflicting human annotations for the exact observation")
            bucket.append(reference)
        unique = [bucket[0] for bucket in self._references.values()]
        self._native_frames = tuple(r.frame for r in unique)
        validate_dataset([r.frame for r in unique], [r.annotation for r in unique])
        self.fingerprint = _digest([asdict(r) for r in references])
        self.summary = {
            "input_references": len(references),
            "unique_human_labels": len(unique),
            "duplicate_references_removed": len(references) - len(unique),
            "counts_by_split": {
                s: sum(r.frame.split.value == s for r in unique)
                for s in sorted({r.frame.split.value for r in unique})
            },
            "human_reconfirmed_by_code": 0,
            "ownership": "UNKNOWN",
            "formal_outputs": 0,
        }

    def lookup(self, frame: FrameRecord, *, out_of_scope: bool = False) -> dict[str, Any]:
        frame.validate()
        validate_dataset((*self._native_frames, frame))
        if type(out_of_scope) is not bool:
            raise ValueError("Explicit evaluation-scope flag required")
        known = self._references.get(observation_key(frame), [])
        return {
            "status": "OUT_OF_SCOPE"
            if out_of_scope
            else ("HUMAN_CONFIRMED" if known else "UNREVIEWED"),
            "annotation": known[0].annotation if known and not out_of_scope else None,
            "review_references": tuple(known),
            "inventory_fingerprint": self.fingerprint,
            "click_uncertainty": "UNMEASURED",
            "ownership": "UNKNOWN",
            "formal_outputs": 0,
        }
