"""Read-only contract view of every rule's temporal / aggregation policy.

The evaluation rules JSON carries policies that the runtime does not (yet) act on. This
module does three things and nothing more:

1. validate the *shape* of those policy values (``RuleTemporalPolicy.from_rule``);
2. expose them as one deterministic table (``TemporalPolicyTable``) for audits and for
   downstream consumers such as the match aggregation;
3. report, for one rule and one Round Package, which context the rule needs and whether
   it is present (``assess_context``).

It never produces a label, a score or a confidence, and it never changes what the
Rule Engine, the TemporalScopeResolver or the coach do. In particular:

* ``display_clip_strategy`` is natural language and is kept verbatim; it is not parsed
  into seconds.
* ``temporal_tolerance_policy``, ``event_window_seconds`` and the clip window are
  different concepts and are not converted into one another.
* ``requires_round_timeline`` is *reported* (``round_timeline_shortfall``) but is not
  turned into a new gate that blocks scoring: the source of truth does not say that it
  should.
"""

from __future__ import annotations

import json
import math
from collections.abc import Iterable, Iterator, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any, TypeGuard

from valorant_ai_coach.resources import resource_path
from valorant_ai_coach.schema_validation import ContractValidationError

from .temporal_scope import (
    PREVIOUS_ROUND_CONTEXT,
    AnalysisScope,
    previous_round_context_missing,
)

TEMPORAL_LEVELS: tuple[str, ...] = ("micro", "local", "phase", "round", "cross_round", "match")
# Levels whose analysis range is always the whole round (never a pivot-event window).
WHOLE_ROUND_LEVELS: frozenset[str] = frozenset({"phase", "round", "cross_round", "match"})

ROUND_TIMELINE_COMPLETE = "complete"
ROUND_TIMELINE_PARTIAL = "partial"
ROUND_TIMELINE_UNAVAILABLE = "unavailable"
ROUND_TIMELINE_UNKNOWN = "unknown"

TIME_SCOPE_EVENT_WINDOWS = "event_windows"
TIME_SCOPE_WHOLE_ROUND_BY_POLICY = "whole_round_by_policy"
TIME_SCOPE_WHOLE_ROUND_FALLBACK = "whole_round_fallback"
TIME_SCOPE_UNKNOWN = "unknown"


def _fail(rule_id: str, message: str) -> ContractValidationError:
    return ContractValidationError(f"{rule_id}: {message}")


def _is_bool(value: Any) -> bool:
    return isinstance(value, bool)


def _is_number(value: Any) -> bool:
    return not isinstance(value, bool) and isinstance(value, int | float)


def _finite_number(value: Any) -> TypeGuard[int | float]:
    return _is_number(value) and math.isfinite(float(value))


def _require_bool(rule_id: str, container: Mapping[str, Any], key: str) -> bool:
    value = container.get(key)
    if not _is_bool(value):
        raise _fail(rule_id, f"{key} はboolである必要があります: {value!r}")
    return bool(value)


def _require_text(rule_id: str, container: Mapping[str, Any], key: str) -> str:
    value = container.get(key)
    if not isinstance(value, str) or not value.strip():
        raise _fail(rule_id, f"{key} は空でない文字列である必要があります: {value!r}")
    return value


def _require_mapping(rule_id: str, container: Mapping[str, Any], key: str) -> Mapping[str, Any]:
    value = container.get(key)
    if not isinstance(value, Mapping):
        raise _fail(rule_id, f"{key} はobjectである必要があります")
    return value


@dataclass(frozen=True, slots=True)
class EventWindow:
    """Seconds of context before / after a pivot event (``event_window_seconds``)."""

    before_sec: float
    after_sec: float


@dataclass(frozen=True, slots=True)
class RuleTemporalPolicy:
    """One rule's temporal and aggregation policy, copied from the rules JSON."""

    rule_id: str
    level: str
    event_window: EventWindow | None
    requires_round_timeline: bool
    requires_previous_round_context: bool
    uses_whole_match_aggregation: bool
    display_clip_strategy: str
    candidate_selection: str
    final_label_mode: str
    aggregate_repeated_occurrences: bool
    deduplicate_same_rule_within_seconds: float
    max_display_exemplars_per_match: int
    summary_required_if_occurrences_at_least: int | None

    @property
    def needs_match_context(self) -> bool:
        """True only when the config itself asks for match-wide context.

        ``level == "match"`` and ``uses_whole_match_aggregation`` are different facts
        (AIM-01 is match level; AIM-02 is micro level aggregated over the match). Both
        mean the rule is not judged from one Round alone.
        """
        return self.level == "match" or self.uses_whole_match_aggregation

    @classmethod
    def from_rule(cls, rule: Mapping[str, Any]) -> RuleTemporalPolicy:
        rule_id = rule.get("id")
        if not isinstance(rule_id, str) or not rule_id:
            raise ContractValidationError("ルールにidがありません")
        context = _require_mapping(rule_id, rule, "temporal_context")
        level = context.get("level_code")
        if level not in TEMPORAL_LEVELS:
            raise _fail(rule_id, f"temporal_context.level_code が不正です: {level!r}")
        window = cls._event_window(rule_id, context)
        if window is not None and level in WHOLE_ROUND_LEVELS:
            raise _fail(
                rule_id,
                f"level={level} はラウンド全体を見るため event_window_seconds を持てません",
            )
        automation = _require_mapping(rule_id, rule, "automation_policy")
        aggregation = _require_mapping(rule_id, rule, "aggregation_policy")
        within = aggregation.get("deduplicate_same_rule_within_seconds")
        if not _finite_number(within) or float(within) < 0:
            raise _fail(
                rule_id,
                "aggregation_policy.deduplicate_same_rule_within_seconds は"
                f"0以上の有限値である必要があります: {within!r}",
            )
        maximum = aggregation.get("max_display_exemplars_per_match")
        if isinstance(maximum, bool) or not isinstance(maximum, int) or maximum < 1:
            raise _fail(
                rule_id,
                "aggregation_policy.max_display_exemplars_per_match は"
                f"1以上の整数である必要があります: {maximum!r}",
            )
        summary = aggregation.get("summary_required_if_occurrences_at_least")
        if summary is not None and (
            isinstance(summary, bool) or not isinstance(summary, int) or summary < 1
        ):
            raise _fail(
                rule_id,
                "aggregation_policy.summary_required_if_occurrences_at_least は"
                f"nullまたは1以上の整数である必要があります: {summary!r}",
            )
        return cls(
            rule_id=rule_id,
            level=str(level),
            event_window=window,
            requires_round_timeline=_require_bool(rule_id, context, "requires_round_timeline"),
            requires_previous_round_context=_require_bool(
                rule_id, context, "requires_previous_round_context"
            ),
            uses_whole_match_aggregation=_require_bool(
                rule_id, context, "uses_whole_match_aggregation"
            ),
            display_clip_strategy=_require_text(rule_id, context, "display_clip_strategy"),
            candidate_selection=_require_text(rule_id, automation, "candidate_selection"),
            final_label_mode=_require_text(rule_id, automation, "final_label_mode"),
            aggregate_repeated_occurrences=_require_bool(
                rule_id, aggregation, "aggregate_repeated_occurrences"
            ),
            deduplicate_same_rule_within_seconds=float(within),
            max_display_exemplars_per_match=maximum,
            summary_required_if_occurrences_at_least=summary,
        )

    @staticmethod
    def _event_window(rule_id: str, context: Mapping[str, Any]) -> EventWindow | None:
        raw = context.get("event_window_seconds")
        if raw is None:
            return None
        if not isinstance(raw, Mapping):
            raise _fail(rule_id, "event_window_seconds はnullまたはobjectである必要があります")
        before, after = raw.get("before"), raw.get("after")
        if not (_finite_number(before) and _finite_number(after)):
            raise _fail(rule_id, "event_window_seconds.before/after は有限の数値が必要です")
        if float(before) < 0 or float(after) < 0:
            raise _fail(rule_id, "event_window_seconds.before/after は0以上である必要があります")
        if float(before) + float(after) <= 0:
            raise _fail(rule_id, "event_window_seconds の幅が0です")
        return EventWindow(float(before), float(after))

    def to_row(self) -> dict[str, Any]:
        """JSON-safe, order-stable representation (used by the audit document)."""
        return {
            "rule_id": self.rule_id,
            "level": self.level,
            "event_window_seconds": (
                None
                if self.event_window is None
                else {"before": self.event_window.before_sec, "after": self.event_window.after_sec}
            ),
            "requires_round_timeline": self.requires_round_timeline,
            "requires_previous_round_context": self.requires_previous_round_context,
            "uses_whole_match_aggregation": self.uses_whole_match_aggregation,
            "display_clip_strategy": self.display_clip_strategy,
            "automation_policy": {
                "candidate_selection": self.candidate_selection,
                "final_label_mode": self.final_label_mode,
            },
            "aggregation_policy": {
                "aggregate_repeated_occurrences": self.aggregate_repeated_occurrences,
                "deduplicate_same_rule_within_seconds": self.deduplicate_same_rule_within_seconds,
                "max_display_exemplars_per_match": self.max_display_exemplars_per_match,
                "summary_required_if_occurrences_at_least": (
                    self.summary_required_if_occurrences_at_least
                ),
            },
        }


class TemporalPolicyTable:
    """Validated, id-sorted collection of every rule's :class:`RuleTemporalPolicy`."""

    def __init__(self, policies: Iterable[RuleTemporalPolicy]) -> None:
        by_id: dict[str, RuleTemporalPolicy] = {}
        for policy in policies:
            if policy.rule_id in by_id:
                raise ContractValidationError(f"ルールidが重複しています: {policy.rule_id}")
            by_id[policy.rule_id] = policy
        self._by_id = dict(sorted(by_id.items()))

    @classmethod
    def from_config(cls, rule_config: Mapping[str, Any]) -> TemporalPolicyTable:
        rules = rule_config.get("rules")
        if not isinstance(rules, list):
            raise ContractValidationError("ルール設定にrules配列がありません")
        return cls(RuleTemporalPolicy.from_rule(rule) for rule in rules)

    @classmethod
    def load(cls, path: Path | None = None) -> TemporalPolicyTable:
        source = path or resource_path("config/valorant_evaluation_rules_v4.json")
        return cls.from_config(json.loads(Path(source).read_text(encoding="utf-8")))

    def get(self, rule_id: str) -> RuleTemporalPolicy | None:
        return self._by_id.get(rule_id)

    def __iter__(self) -> Iterator[RuleTemporalPolicy]:
        return iter(self._by_id.values())

    def __len__(self) -> int:
        return len(self._by_id)

    def __contains__(self, rule_id: object) -> bool:
        return rule_id in self._by_id

    @property
    def rule_ids(self) -> tuple[str, ...]:
        return tuple(self._by_id)

    def to_rows(self) -> list[dict[str, Any]]:
        return [policy.to_row() for policy in self]

    def validate_registry_alignment(self, registry_rules: Mapping[str, Mapping[str, Any]]) -> None:
        """Rule JSON and trigger registry must describe the same rules and levels.

        ``TemporalScopeResolver`` reads the level from the rules JSON while
        ``FramePlanner`` reads it from the registry candidate, so a disagreement would
        make two parts of the pipeline treat one rule at two different levels.
        """
        problems: list[str] = []
        missing_in_registry = sorted(set(self._by_id) - set(registry_rules))
        missing_in_rules = sorted(set(registry_rules) - set(self._by_id))
        if missing_in_registry:
            problems.append(f"registryにないルール: {missing_in_registry}")
        if missing_in_rules:
            problems.append(f"ルール設定にないregistryルール: {missing_in_rules}")
        for rule_id in sorted(set(self._by_id) & set(registry_rules)):
            registry_level = registry_rules[rule_id].get("temporal_level")
            if registry_level != self._by_id[rule_id].level:
                problems.append(
                    f"{rule_id}: levelが不一致 rules={self._by_id[rule_id].level!r} "
                    f"registry={registry_level!r}"
                )
        if problems:
            raise ContractValidationError("; ".join(problems))


def round_timeline_status(package: Mapping[str, Any]) -> str:
    """How much of the Round's timeline was observed, from ``observation_quality`` only.

    ``0`` completeness is what ``RoundPackageBuilder`` writes when a round boundary was
    not observed (the denominator is unknown), so it is reported as unavailable rather
    than as a measured fraction. Nothing is inferred when the field is absent or
    malformed.
    """
    quality = package.get("observation_quality")
    if not isinstance(quality, Mapping):
        return ROUND_TIMELINE_UNKNOWN
    completeness = quality.get("timeline_completeness")
    intervals = quality.get("missing_intervals")
    if (
        isinstance(completeness, bool)
        or not isinstance(completeness, int | float)
        or not math.isfinite(completeness)
        or not isinstance(intervals, list)
    ):
        return ROUND_TIMELINE_UNKNOWN
    if float(completeness) == 0.0:
        return ROUND_TIMELINE_UNAVAILABLE
    if float(completeness) >= 1.0 and not intervals:
        return ROUND_TIMELINE_COMPLETE
    return ROUND_TIMELINE_PARTIAL


@dataclass(frozen=True, slots=True)
class ContextAssessment:
    """Which context one rule needs for one Round, and what is missing.

    This is information for a consumer. It does not alter any evaluation, and none of
    the fields is a judgement about whether the play was good.
    """

    rule_id: str
    level: str
    needs_match_context: bool
    needs_previous_round_context: bool
    needs_round_timeline: bool
    missing_context: tuple[str, ...]
    round_timeline: str
    round_timeline_shortfall: bool
    time_scope: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "rule_id": self.rule_id,
            "level": self.level,
            "needs_match_context": self.needs_match_context,
            "needs_previous_round_context": self.needs_previous_round_context,
            "needs_round_timeline": self.needs_round_timeline,
            "missing_context": list(self.missing_context),
            "round_timeline": self.round_timeline,
            "round_timeline_shortfall": self.round_timeline_shortfall,
            "time_scope": self.time_scope,
        }


def assess_context(
    policy: RuleTemporalPolicy,
    package: Mapping[str, Any],
    scope: AnalysisScope | None = None,
) -> ContextAssessment:
    """Describe the context ``policy`` needs against ``package`` (no new judgement)."""
    missing: tuple[str, ...] = (
        (PREVIOUS_ROUND_CONTEXT,)
        if policy.requires_previous_round_context and previous_round_context_missing(package)
        else ()
    )
    timeline = round_timeline_status(package)
    if scope is None:
        time_scope = TIME_SCOPE_UNKNOWN
    elif not scope.whole_round:
        time_scope = TIME_SCOPE_EVENT_WINDOWS
    elif policy.event_window is None:
        time_scope = TIME_SCOPE_WHOLE_ROUND_BY_POLICY
    else:
        # A windowed rule that still got the whole round: no pivot event matched, so the
        # time range of the evaluated moment is *not* pinned down.
        time_scope = TIME_SCOPE_WHOLE_ROUND_FALLBACK
    return ContextAssessment(
        rule_id=policy.rule_id,
        level=policy.level,
        needs_match_context=policy.needs_match_context,
        needs_previous_round_context=policy.requires_previous_round_context,
        needs_round_timeline=policy.requires_round_timeline,
        missing_context=missing,
        round_timeline=timeline,
        round_timeline_shortfall=(
            policy.requires_round_timeline and timeline != ROUND_TIMELINE_COMPLETE
        ),
        time_scope=time_scope,
    )
