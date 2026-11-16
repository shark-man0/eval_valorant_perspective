"""Runtime consumers for the rule policy fields that previously had none (#31, #25).

Three consumers live here. Each one is a pure function of the rule configuration and
its input; none of them creates a new label, score, weight or confidence.

``ProvisionalAdmissionTable`` (#25)
    Classifies every rule as *boundary independent* or not, with machine-readable
    reasons. Only a boundary-independent rule may ever be evaluated inside a Practical
    Round whose start/end is provisional or unknown. The table is always available;
    *using* it to admit scoring is an explicit opt-in (``ProvisionalEvaluationPolicy``)
    that stays off until the coordinator approves it.

``RoundTimelineGate`` (#31 §6-1)
    ``requires_round_timeline`` used to be shown in the UI only. The gate reads it at
    runtime. The default mode ``report_only`` keeps the historical behaviour exactly
    (nothing changes; shortfalls are reported). ``unscore_incomplete`` turns a GOOD /
    IMPROVE of such a rule into UNSCORED when the Round timeline is not complete. That
    mode changes evaluation semantics and therefore requires approval before it is
    enabled anywhere.

``occurrence_summaries`` (#31 §6-6)
    ``aggregate_repeated_occurrences`` / ``summary_required_if_occurrences_at_least``
    become a structured, deterministic summary inside the Match view: counts by label,
    Round numbers and evaluation references. It contains no prose and no verdict; the
    natural-language summary itself remains an approval item.
"""

from __future__ import annotations

import json
from collections.abc import Iterable, Mapping, Sequence
from copy import deepcopy
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from valorant_ai_coach.resources import resource_path

from .temporal_contract import (
    ROUND_TIMELINE_COMPLETE,
    RuleTemporalPolicy,
    TemporalPolicyTable,
    round_timeline_status,
)

# --------------------------------------------------------------------------- #25

# Facts whose value is defined only relative to the Round as a whole (who is alive,
# which side, how long is left, what was bought, what happened first). A rule that
# needs one of them cannot be judged inside a Round whose boundaries are uncertain,
# because the denominator itself is uncertain.
ROUND_CONTEXT_FACT_KEYS: frozenset[str] = frozenset(
    {
        "side",
        "numbers_state",
        "clutch_state",
        "round_time_remaining_sec",
        "spike_planted",
        "spike_carried_by_player",
        "objective_state_observed",
        "site_incoming_damage_risk_observed",
        "first_death_by_player",
        "first_kill_by_player",
        "buy_phase_observed",
        "team_buy_class",
        "player_buy_class",
        "save_context_observed",
        "enemy_eco_likely",
        "ally_entry_active",
        "lurk_context_observed",
        "enemy_spotted_count",
        "ultimate_available",
    }
)
# Trigger events that are themselves Round phases or Round-scoped states.
ROUND_CONTEXT_EVENT_TYPES: frozenset[str] = frozenset(
    {
        "round_start",
        "buy_phase",
        "purchase",
        "save_decision",
        "objective_state",
        "site_state",
        "spike_planted",
        "spike_defuse_started",
        "rotation_started",
        "state_snapshot",
    }
)
SELF_CONTAINED_LEVELS: frozenset[str] = frozenset({"micro", "local"})

REASON_LEVEL = "level_not_self_contained"
REASON_NO_WINDOW = "no_event_window"
REASON_ROUND_TIMELINE = "requires_round_timeline"
REASON_PREVIOUS_ROUND = "requires_previous_round_context"
REASON_MATCH_CONTEXT = "requires_match_context"
REASON_ROUND_FACT = "round_context_fact"
REASON_ROUND_TRIGGER = "round_context_trigger"
REASON_NOT_IN_REGISTRY = "not_in_trigger_registry"


@dataclass(frozen=True, slots=True)
class ProvisionalAdmission:
    """Whether one rule's evidence is self-contained without trusted Round boundaries.

    ``match_aggregated`` marks rules (AIM-02/03/04, MOV-01/02) whose single occurrence is
    self-contained but whose *meaning* is aggregated over the Match. They stay
    admissible per occurrence; the Match view keeps them ``match_context_unverified``.
    """

    rule_id: str
    admissible: bool
    reasons: tuple[str, ...]
    match_aggregated: bool

    def to_dict(self) -> dict[str, Any]:
        return {
            "rule_id": self.rule_id,
            "admissible": self.admissible,
            "reasons": list(self.reasons),
            "match_aggregated": self.match_aggregated,
        }


def classify_provisional_admission(
    policy: RuleTemporalPolicy, registry_rule: Mapping[str, Any] | None
) -> ProvisionalAdmission:
    reasons: list[str] = []
    if registry_rule is None:
        reasons.append(REASON_NOT_IN_REGISTRY)
    if policy.level not in SELF_CONTAINED_LEVELS:
        reasons.append(REASON_LEVEL)
    if policy.event_window is None:
        reasons.append(REASON_NO_WINDOW)
    if policy.requires_round_timeline:
        reasons.append(REASON_ROUND_TIMELINE)
    if policy.requires_previous_round_context:
        reasons.append(REASON_PREVIOUS_ROUND)
    if policy.level == "match":
        reasons.append(REASON_MATCH_CONTEXT)
    if registry_rule is not None:
        keys = {
            str(item.get("fact_key"))
            for item in registry_rule.get("required_state_predicates", [])
            if isinstance(item, Mapping)
        } | {str(key) for key in registry_rule.get("supporting_fact_keys", [])}
        reasons.extend(
            f"{REASON_ROUND_FACT}:{key}" for key in sorted(keys & ROUND_CONTEXT_FACT_KEYS)
        )
        triggers = {str(item) for item in registry_rule.get("trigger_event_types", [])}
        reasons.extend(
            f"{REASON_ROUND_TRIGGER}:{kind}"
            for kind in sorted(triggers & ROUND_CONTEXT_EVENT_TYPES)
        )
    return ProvisionalAdmission(
        rule_id=policy.rule_id,
        admissible=not reasons,
        reasons=tuple(reasons),
        match_aggregated=policy.uses_whole_match_aggregation,
    )


class ProvisionalAdmissionTable:
    """Deterministic 44-rule classification; identical for every Round and Match."""

    def __init__(
        self,
        policies: TemporalPolicyTable,
        registry_rules: Mapping[str, Mapping[str, Any]],
    ) -> None:
        self._rows = {
            policy.rule_id: classify_provisional_admission(
                policy, registry_rules.get(policy.rule_id)
            )
            for policy in policies
        }

    @classmethod
    def load(
        cls, rules_path: Path | None = None, registry_path: Path | None = None
    ) -> ProvisionalAdmissionTable:
        registry = json.loads(
            Path(
                registry_path or resource_path("config/rule_trigger_registry_v2.json")
            ).read_text(encoding="utf-8")
        )
        return cls(TemporalPolicyTable.load(rules_path), registry["rules"])

    def get(self, rule_id: str) -> ProvisionalAdmission | None:
        return self._rows.get(rule_id)

    def admissible_rule_ids(self) -> frozenset[str]:
        return frozenset(rule_id for rule_id, row in self._rows.items() if row.admissible)

    def rows(self) -> list[ProvisionalAdmission]:
        return [self._rows[key] for key in sorted(self._rows)]

    def to_rows(self) -> list[dict[str, Any]]:
        return [row.to_dict() for row in self.rows()]


@dataclass(frozen=True, slots=True)
class ProvisionalEvaluationPolicy:
    """Opt-in admission of boundary-independent rules inside provisional Rounds.

    ``enabled`` defaults to False and the application never turns it on by itself. When
    enabled, a candidate is admitted only if (1) the table marks the rule admissible,
    (2) a pivot event of the rule lies inside the observed part of the Round window
    (an event-window scope, never the whole-round fallback) and (3) every fact the
    deterministic decision cites lies inside that scope. Everything else is dropped,
    exactly as before.
    """

    table: ProvisionalAdmissionTable
    enabled: bool = False

    def admits(self, rule_id: str) -> bool:
        row = self.table.get(rule_id)
        return self.enabled and row is not None and row.admissible


# ---------------------------------------------------------------------- #31 §6-1

GATE_REPORT_ONLY = "report_only"
GATE_UNSCORE_INCOMPLETE = "unscore_incomplete"
GATE_MODES: tuple[str, ...] = (GATE_REPORT_ONLY, GATE_UNSCORE_INCOMPLETE)
ROUND_TIMELINE_GATE_REASON = "round_timeline_not_complete"


@dataclass(frozen=True, slots=True)
class GateRecord:
    evaluation_id: str
    rule_id: str
    round_timeline: str
    action: str

    def to_dict(self) -> dict[str, str]:
        return {
            "evaluation_id": self.evaluation_id,
            "rule_id": self.rule_id,
            "round_timeline": self.round_timeline,
            "action": self.action,
        }


class RoundTimelineGate:
    """Runtime consumer of ``requires_round_timeline``.

    ``report_only`` (default) returns the output unchanged and lists which scored
    evaluations *would* be affected. ``unscore_incomplete`` (approval required) rewrites
    them as UNSCORED: label, clip and improvement are cleared, ``missing_information``
    names the timeline status, ``unscored_reason_code`` is ``missing_required_fact`` and
    the original confidence is kept (never raised).
    """

    def __init__(self, policies: TemporalPolicyTable, mode: str = GATE_REPORT_ONLY) -> None:
        if mode not in GATE_MODES:
            raise ValueError(f"unsupported round timeline gate mode: {mode!r}")
        self.policies = policies
        self.mode = mode

    def apply(
        self, output: Mapping[str, Any], package: Mapping[str, Any]
    ) -> tuple[dict[str, Any], tuple[GateRecord, ...]]:
        value = deepcopy(dict(output))
        timeline = round_timeline_status(package)
        if timeline == ROUND_TIMELINE_COMPLETE:
            return value, ()
        records: list[GateRecord] = []
        for item in value.get("evaluations", []):
            if not isinstance(item, dict) or item.get("label") not in {"good", "improve"}:
                continue
            policy = self.policies.get(str(item.get("primary_rule_id")))
            if policy is None or not policy.requires_round_timeline:
                continue
            if self.mode == GATE_UNSCORE_INCOMPLETE:
                item["label"] = "unscored"
                item["clip_id"] = None
                item["display_clip"] = None
                item["improvement"] = None
                item["unscored_reason_code"] = "missing_required_fact"
                missing = [str(text) for text in item.get("missing_information", [])]
                note = f"{ROUND_TIMELINE_GATE_REASON}:{timeline}"
                if note not in missing:
                    missing.append(note)
                item["missing_information"] = missing
                action = "unscored"
            else:
                action = "reported"
            records.append(
                GateRecord(str(item.get("evaluation_id")), policy.rule_id, timeline, action)
            )
        return value, tuple(records)


# ---------------------------------------------------------------------- #31 §6-6

OCCURRENCE_SUMMARY_VERSION = "occurrence_summary.v1"


def occurrence_summaries(
    rules: Sequence[Mapping[str, Any]], evaluations: Iterable[Mapping[str, Any]]
) -> list[dict[str, Any]]:
    """Structured repeated-occurrence summary for rules that ask for one.

    ``rules`` are ``MatchAggregation.to_dict()["rules"]`` rows, ``evaluations`` the
    matching ``evaluations`` refs. Only rules with ``aggregate_repeated_occurrences`` are
    listed. ``summary_required`` is True when the primary occurrences reach the
    configured threshold. Counts are of evaluation records, exactly like the rest of the
    Match view, and the summary carries no text and no judgement.
    """

    refs_by_id = {
        str(ref.get("evaluation_id")): ref for ref in evaluations if isinstance(ref, Mapping)
    }
    result: list[dict[str, Any]] = []
    for rule in rules:
        if rule.get("aggregate_repeated_occurrences") is not True:
            continue
        counts = {key: int(value) for key, value in dict(rule.get("counts", {})).items()}
        occurrences = sum(counts.values())
        threshold = rule.get("summary_required_if_occurrences_at_least")
        ids = [str(value) for value in rule.get("primary_evaluation_ids", [])]
        times = sorted(
            
                float(ref["evidence_range"]["start_sec"])
                for ref in (refs_by_id.get(evaluation_id) for evaluation_id in ids)
                if isinstance(ref, Mapping)
                and isinstance(ref.get("evidence_range"), Mapping)
                and isinstance(ref["evidence_range"].get("start_sec"), int | float)
            
        )
        result.append(
            {
                "schema_version": OCCURRENCE_SUMMARY_VERSION,
                "rule_id": rule.get("rule_id"),
                "occurrences": occurrences,
                "counts": counts,
                "threshold": threshold,
                "summary_required": isinstance(threshold, int)
                and not isinstance(threshold, bool)
                and occurrences >= threshold,
                "rounds": list(rule.get("rounds_as_primary", [])),
                "evaluation_ids": ids,
                "evidence_start_seconds": times,
                "match_context_unverified": rule.get("match_context_unverified"),
                "text": None,
                "text_status": "requires_approval",
            }
        )
    return result
