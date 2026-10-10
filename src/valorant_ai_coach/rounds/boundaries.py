"""Round segmentation evidence, separate from the formal event contract."""
from __future__ import annotations

import math
from copy import deepcopy
from dataclasses import asdict, dataclass
from typing import Any, Literal

from valorant_ai_coach.hud.round_lifecycle import BoundaryDecision

BoundaryStatus = Literal["confirmed", "provisional", "unknown"]


def _time(value: Any) -> bool:
    return type(value) in (int, float) and math.isfinite(value) and value >= 0


@dataclass(frozen=True)
class BoundaryObservation:
    """Persist uncertainty without making an unqualified round_start/end event.

    A boundary timestamp must be an actual evidence timestamp. Confirmation is
    allowed arbitrarily later: the practical accuracy tolerance is evaluator
    policy, never a confirmation timeout. Source/temporal validity is established
    by the producer; this model checks transport consistency only.
    """

    kind: Literal["round_start", "round_end"]
    boundary_status: BoundaryStatus
    boundary_time_sec: float | None
    confirmation_time_sec: float | None
    evidence_times_sec: tuple[float, ...]
    confidence: float | None
    provenance: dict[str, Any]

    def __post_init__(self) -> None:
        if self.kind not in {"round_start", "round_end"}:
            raise ValueError("unsupported round boundary kind")
        if self.boundary_status not in {"confirmed", "provisional", "unknown"}:
            raise ValueError("unsupported round boundary status")
        if not isinstance(self.provenance, dict) or not self.provenance:
            raise ValueError("boundary provenance or unknown reason required")
        if self.boundary_status == "unknown":
            if (self.boundary_time_sec is not None or self.confirmation_time_sec is not None
                    or self.evidence_times_sec or self.confidence is not None):
                raise ValueError("unknown boundary cannot manufacture a timestamp or confidence")
        else:
            if (not _time(self.boundary_time_sec) or not self.evidence_times_sec
                    or any(not _time(t) for t in self.evidence_times_sec)
                    or tuple(sorted(set(self.evidence_times_sec))) != self.evidence_times_sec
                    or self.boundary_time_sec not in self.evidence_times_sec):
                raise ValueError("ordered distinct source evidence must include boundary time")
            if self.confirmation_time_sec is not None and (
                not _time(self.confirmation_time_sec)
                or self.confirmation_time_sec not in self.evidence_times_sec
                or self.confirmation_time_sec < self.boundary_time_sec
            ):
                raise ValueError("confirmation must be a later source evidence time")
            if self.confidence is not None and (
                type(self.confidence) not in (int, float)
                or not math.isfinite(self.confidence) or not 0 <= self.confidence <= 1
            ):
                raise ValueError("confidence must remain finite and bounded")
        object.__setattr__(self, "provenance", deepcopy(self.provenance))

    @classmethod
    def provisional_from_decision(cls, decision: BoundaryDecision) -> BoundaryObservation:
        """Preserve an existing composite candidate; never promote qualification."""
        proof = deepcopy(decision.attributes.get("evidence_provenance", {}))
        confirmation = proof.get("confirmation_pts_sec")
        times = proof.get("pts_sec", [])
        if not isinstance(times, (list, tuple)):
            raise ValueError("candidate evidence times required")
        evidence = list(times)
        evidence.append(decision.time_sec)
        if confirmation is not None:
            evidence.append(confirmation)
        if any(not _time(t) for t in evidence):
            raise ValueError("invalid candidate evidence timestamp")
        return cls(decision.kind, "provisional", decision.time_sec, confirmation,
                   tuple(sorted(set(evidence))), decision.confidence, proof)

    def to_dict(self) -> dict[str, Any]:
        result = asdict(self)
        result["evidence_times_sec"] = list(self.evidence_times_sec)
        return result

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> BoundaryObservation:
        expected = set(cls.__dataclass_fields__)
        if not isinstance(value, dict) or set(value) != expected:
            raise ValueError("invalid stored boundary fields")
        evidence = value["evidence_times_sec"]
        if not isinstance(evidence, (list, tuple)):
            raise ValueError("stored boundary evidence must be a sequence")
        return cls(**{**value, "evidence_times_sec": tuple(evidence)})
