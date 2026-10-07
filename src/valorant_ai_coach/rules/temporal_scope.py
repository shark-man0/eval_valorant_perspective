"""Reflect each rule's "what the AI looks at" range (temporal_context) in the logic.

The range only ever *narrows* what the coach is given and what a scored evaluation may
cite. It never adds observations: with no pivot event, or for round / phase / match level
rules, the scope falls back to the whole round. Missing previous-round context for a rule
that needs it makes a scored (good / improve) evaluation of that rule invalid.

Scope is a pure function of (rule config, round package, candidate trigger types), so the
same input always yields the same scope.
"""

from __future__ import annotations

import copy
import json
from collections.abc import Collection, Iterable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from valorant_ai_coach.models import RuleCandidate
from valorant_ai_coach.resources import resource_path
from valorant_ai_coach.schema_validation import ContractValidationError

SCORED_LABELS = frozenset({"good", "improve"})
_TOLERANCE_SEC = 0.05
Window = tuple[float, float]


@dataclass(frozen=True, slots=True)
class AnalysisScope:
    rule_id: str
    level: str
    windows: tuple[Window, ...] = ()
    whole_round: bool = True
    missing_context: tuple[str, ...] = ()

    def contains(self, start: float, end: float) -> bool:
        if self.whole_round:
            return True
        return any(
            start >= low - _TOLERANCE_SEC and end <= high + _TOLERANCE_SEC
            for low, high in self.windows
        )

    def to_prompt(self) -> dict[str, Any]:
        return {
            "level": self.level,
            "scope": "whole_round" if self.whole_round else "event_windows",
            "windows_sec": [{"start_sec": low, "end_sec": high} for low, high in self.windows],
            "missing_context": list(self.missing_context),
        }


class TemporalScopeResolver:
    def __init__(self, rules_by_id: Mapping[str, Mapping[str, Any]] | None = None) -> None:
        if rules_by_id is None:
            path = resource_path("config/valorant_evaluation_rules_v4.json")
            rules = json.loads(Path(path).read_text(encoding="utf-8"))["rules"]
            rules_by_id = {str(rule["id"]): rule for rule in rules}
        self.rules_by_id = rules_by_id

    def resolve(self, candidate: RuleCandidate, package: Mapping[str, Any]) -> AnalysisScope:
        rule = self.rules_by_id.get(candidate.rule_id)
        context = (rule or {}).get("temporal_context") or {}
        level = str(context.get("level_code") or candidate.temporal_level)
        missing: list[str] = []
        if context.get("requires_previous_round_context") and not package.get(
            "previous_round_context"
        ):
            missing.append("previous_round_context")
        windows = self._event_windows(context, candidate, package)
        return AnalysisScope(
            candidate.rule_id,
            level,
            tuple(windows),
            whole_round=not windows,
            missing_context=tuple(missing),
        )

    @staticmethod
    def _event_windows(
        context: Mapping[str, Any], candidate: RuleCandidate, package: Mapping[str, Any]
    ) -> list[Window]:
        span = context.get("event_window_seconds")
        if not span or not candidate.matched_event_types:
            return []
        round_start = float(package["round_window"]["start_sec"])
        round_end = float(package["round_window"]["end_sec"])
        before, after = float(span["before"]), float(span["after"])
        pivots = sorted(
            {
                float(event["time_sec"])
                for event in package.get("events", [])
                if event.get("type") in candidate.matched_event_types
            }
        )
        merged: list[Window] = []
        for pivot in pivots:
            low, high = max(round_start, pivot - before), min(round_end, pivot + after)
            if high <= low:
                continue
            if merged and low <= merged[-1][1]:
                merged[-1] = (merged[-1][0], max(merged[-1][1], high))
            else:
                merged.append((low, high))
        return merged


def union_windows(scopes: Iterable[AnalysisScope]) -> list[Window] | None:
    """Union of windows, or None when any scope needs the whole round."""
    collected: list[Window] = []
    seen = False
    for scope in scopes:
        seen = True
        if scope.whole_round:
            return None
        collected.extend(scope.windows)
    if not seen:
        return None
    collected.sort()
    merged: list[Window] = []
    for low, high in collected:
        if merged and low <= merged[-1][1]:
            merged[-1] = (merged[-1][0], max(merged[-1][1], high))
        else:
            merged.append((low, high))
    return merged


def _inside(time_sec: float, windows: Sequence[Window]) -> bool:
    return any(low <= time_sec <= high for low, high in windows)


def _fact_in_scope(fact: Mapping[str, Any], windows: Sequence[Window]) -> bool:
    time_range = fact.get("time_range")
    if time_range:
        start, end = float(time_range["start_sec"]), float(time_range["end_sec"])
        return any(start <= high and end >= low for low, high in windows)
    if fact.get("time_sec") is not None:
        return _inside(float(fact["time_sec"]), windows)
    return True  # untimed (round-level) facts cannot be scoped; keep them


def scope_round_package(
    package: Mapping[str, Any],
    scopes: Sequence[AnalysisScope],
    *,
    keep_fact_ids: Collection[str] = (),
) -> tuple[dict[str, Any], list[int]]:
    """Return (package limited to the union window, kept frame indexes).

    Nothing is added. Facts a deterministic decision cites stay (their label is binding), and
    events cited by a kept fact stay so provenance remains valid.
    """
    windows = union_windows(scopes)
    frames = package.get("frames", [])
    if windows is None:
        return copy.deepcopy(dict(package)), list(range(len(frames)))
    scoped = copy.deepcopy(dict(package))
    scoped["deterministic_facts"] = [
        fact
        for fact in package.get("deterministic_facts", [])
        if str(fact["fact_id"]) in keep_fact_ids or _fact_in_scope(fact, windows)
    ]
    cited = {
        str(event_id)
        for fact in scoped["deterministic_facts"]
        for event_id in fact.get("provenance_event_ids", [])
    }
    scoped["events"] = [
        event
        for event in package.get("events", [])
        if _inside(float(event["time_sec"]), windows) or str(event["event_id"]) in cited
    ]
    scoped["state_snapshots"] = [
        snapshot
        for snapshot in package.get("state_snapshots", [])
        if _inside(float(snapshot["time_sec"]), windows)
    ]
    kept = [i for i, f in enumerate(frames) if _inside(float(f["time_sec"]), windows)]
    scoped["frames"] = [scoped["frames"][i] for i in kept]
    return scoped, kept


def validate_output_scope(output: Mapping[str, Any], scopes: Mapping[str, AnalysisScope]) -> None:
    """Scored evaluations must respect the rules' analysis scope."""
    for evaluation in output["evaluations"]:
        if evaluation["label"] not in SCORED_LABELS:
            continue
        rule_ids = [str(evaluation["primary_rule_id"])]
        rule_ids += [str(rule_id) for rule_id in evaluation.get("related_rule_ids", [])]
        involved = [scopes[rule_id] for rule_id in rule_ids if rule_id in scopes]
        for scope in involved:
            if scope.missing_context:
                raise ContractValidationError(
                    f"{scope.rule_id} は必要な文脈({', '.join(scope.missing_context)})が無いため"
                    "採点(good/improve)できません"
                )
        if not involved or any(scope.whole_round for scope in involved):
            continue
        interval = evaluation.get("evidence_range")
        if interval is None:
            continue
        start, end = float(interval["start_sec"]), float(interval["end_sec"])
        if not any(scope.contains(start, end) for scope in involved):
            raise ContractValidationError(
                f"{evaluation['evaluation_id']}.evidence_range が評価ルールの分析範囲外です"
            )
