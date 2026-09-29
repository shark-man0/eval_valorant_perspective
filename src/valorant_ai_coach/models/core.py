from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Literal

type FactValue = str | int | float | bool | None


@dataclass(frozen=True, slots=True)
class DeterministicFact:
    fact_id: str
    key: str
    value: FactValue
    confidence: float
    source: Literal["hud", "visual", "event_normalization", "derived_code", "config", "audio"]
    provenance_event_ids: tuple[str, ...] = ()
    time_sec: float | None = None
    time_range: dict[str, float] | None = None

    def to_dict(self) -> dict[str, Any]:
        value = asdict(self)
        value["provenance_event_ids"] = list(self.provenance_event_ids)
        return value


@dataclass(frozen=True, slots=True)
class RuleCandidate:
    rule_id: str
    priority: str
    temporal_level: str
    label_mode: str
    missing_fact_keys: tuple[str, ...] = ()
    matched_event_types: tuple[str, ...] = ()
    supporting_fact_keys: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class RuleDecision:
    rule_id: str
    label: Literal["good", "improve", "unscored"]
    decision_source: Literal["deterministic", "hybrid"]
    confidence: float
    fact_refs: tuple[str, ...]
    reason: str
    missing_information: tuple[str, ...] = ()
    unscored_reason_code: str | None = None
