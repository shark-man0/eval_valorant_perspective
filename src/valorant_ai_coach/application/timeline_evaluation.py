"""Connect the shared one-second timeline to the evaluation engine (#31, #25, #26).

Before this module the shared timeline reached the Rule Engine only as a smoke check
(``rules/development_timeline.review_timeline`` evaluates one rule against an empty
package). Here the same application bundle goes through the production evaluation
path:

    shared timeline seconds  ->  Round segmentation (round_number candidates)
    ->  Practical Round Packages (provisional boundaries, observed-gap intervals)
    ->  RoundAnalyzer (Fact Builder, selector, Rule Engine, coach)
    ->  MatchAggregator (completeness, per-rule counts, occurrence summaries)
    ->  SQLite repository (same rows the GUI reads)  +  JSON / Markdown report

Safety contract (unchanged by this connection)
----------------------------------------------
* The bundle is ``development_only``. Its Round boundaries are *candidates*, so every
  package carries ``round_lifecycle`` with ``provisional`` endpoints and never a
  ``formal_event_id``. ``RoundAnalyzer`` therefore withholds scoring exactly as for
  Practical Rounds, unless the separately approved #25 policy is passed in.
* No Fact is created here. Facts come only from an explicit ``FactProvider`` (for the
  P0 producers, #32/#155). The default provider supplies none.
* Seconds whose round number is unknown or different are ``missing_intervals``; a
  Round is never stretched over them, and neighbouring Rounds are never used to fill
  them in.
* No verdict, score or confidence is added. Counts are of seconds and candidate
  records, labelled as such.
"""

from __future__ import annotations

import argparse
import json
import os
import re
from collections import Counter
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Protocol

from valorant_ai_coach.facts import FactBuilder
from valorant_ai_coach.rules import DeterministicRuleEngine, RuleSelector
from valorant_ai_coach.rules.policy_runtime import (
    ProvisionalAdmissionTable,
    ProvisionalEvaluationPolicy,
)
from valorant_ai_coach.schema_validation import SchemaValidator
from valorant_ai_coach.storage import SQLiteRepository

from .match_aggregation import MatchAggregator
from .match_aggregation_service import aggregate_saved_match
from .round_analyzer import MockCoachAdapter, RoundAnalysis, RoundAnalyzer

VERSION = "timeline_evaluation_bridge.v1"
DEVELOPMENT_MATCH_PREFIX = "DEV-"
REPORT_KIND = "development_timeline_match_evaluation"
_STATE_DOMAINS: tuple[str, ...] = ("round_state", "life_state", "camera_state")
_SAFE_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,127}$")


class TimelineEvaluationError(ValueError):
    """The bundle cannot be evaluated without inventing data."""


@dataclass(frozen=True, slots=True)
class TimelineRound:
    """One Round as seen on the shared timeline (development candidates only)."""

    round_no: int
    start_sec: int
    end_sec: int  # exclusive
    seconds_with_round_number: int
    missing_intervals: tuple[tuple[int, int], ...]

    @property
    def duration(self) -> int:
        return self.end_sec - self.start_sec

    @property
    def completeness(self) -> float:
        return self.seconds_with_round_number / self.duration if self.duration else 0.0


class FactProvider(Protocol):
    """Hook for development Fact/Event producers (P0 work stays outside this module)."""

    def facts_for(
        self, bundle: Mapping[str, Any], round_: TimelineRound
    ) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        """Return ``(events, deterministic_facts)`` inside ``round_`` (schema v2)."""
        ...


class NoFactProvider:
    def facts_for(
        self, bundle: Mapping[str, Any], round_: TimelineRound
    ) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        del bundle, round_
        return [], []


_EVENT_TYPES: frozenset[str] = frozenset(
    {"state_snapshot", "kill", "player_death", "utility_used", "ability_state"}
)
_EVENT_ACTORS: Mapping[str, str] = {
    "player_death": "player",
    "utility_used": "player",
    "ability_state": "player",
    "kill": "team",
    "state_snapshot": "system",
}


class DerivedSampleFactProvider:
    """Connects the P0 producers (#155 ``development_readiness.derive``).

    ``samples`` are its ``DerivedSample`` objects or their JSON form
    (``{"sec", "facts", "events"}``). Each becomes schema-v2 Events and Facts inside
    the Round whose half-open window holds its second. They are development
    candidates: confidence is recorded as 0.0 (unqualified) and every Event carries
    ``qualification: development_only``, so they can be counted by the production
    selector but can never become a scored evaluation.
    """

    SOURCE = "development_readiness.derive"

    def __init__(self, samples: Sequence[Any]) -> None:
        rows: list[tuple[float, dict[str, Any], tuple[str, ...]]] = []
        for sample in samples:
            if isinstance(sample, Mapping):
                sec, facts, events = sample["sec"], sample["facts"], sample["events"]
            else:
                sec, facts, events = sample.sec, sample.facts, sample.events
            rows.append((float(sec), dict(facts), tuple(sorted(events))))
        self.samples = sorted(rows, key=lambda row: row[0])
        self.unsupported_events: Counter[str] = Counter()

    def facts_for(
        self, bundle: Mapping[str, Any], round_: TimelineRound
    ) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        del bundle
        events: list[dict[str, Any]] = []
        facts: list[dict[str, Any]] = []
        for sec, values, kinds in self.samples:
            if not round_.start_sec <= sec < round_.end_sec:
                continue
            stamp = f"{sec:.3f}"
            ids: list[str] = []
            for kind in kinds:
                if kind not in _EVENT_TYPES:
                    self.unsupported_events[kind] += 1
                    continue
                identifier = f"dev-{kind}-{stamp}"
                ids.append(identifier)
                events.append(
                    {
                        "event_id": identifier,
                        "time_sec": sec,
                        "type": kind,
                        "actor": _EVENT_ACTORS[kind],
                        "attributes": {
                            "qualification": "development_only",
                            "producer": self.SOURCE,
                        },
                        "confidence": 0.0,
                    }
                )
            for key, value in sorted(values.items()):
                facts.append(
                    {
                        "fact_id": f"dev-{key}-{stamp}",
                        "key": key,
                        "value": value,
                        "time_sec": sec,
                        "time_range": None,
                        "confidence": 0.0,
                        "source": "derived_code",
                        "provenance_event_ids": list(ids),
                    }
                )
        return events, facts


@dataclass(frozen=True, slots=True)
class TimelineEvaluation:
    match_id: str
    rounds: tuple[TimelineRound, ...]
    packages: tuple[dict[str, Any], ...]
    analyses: tuple[RoundAnalysis, ...]
    aggregation: dict[str, Any]
    round_timelines: tuple[dict[str, Any], ...]
    unsegmented_seconds: int
    conflicts: tuple[dict[str, Any], ...] = field(default_factory=tuple)
    rule_candidates: tuple[dict[str, int], ...] = field(default_factory=tuple)


# ----------------------------------------------------------------- segmentation


def _round_value(row: Mapping[str, Any]) -> int | None:
    summary = row.get("round_number")
    if not isinstance(summary, Mapping) or summary.get("status") != "CANDIDATE":
        return None
    value = summary.get("value")
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        return None
    return value


def _intervals(seconds: Sequence[int]) -> tuple[tuple[int, int], ...]:
    merged: list[list[int]] = []
    for second in sorted(seconds):
        if merged and second == merged[-1][1]:
            merged[-1][1] = second + 1
        else:
            merged.append([second, second + 1])
    return tuple((low, high) for low, high in merged)


def segment_rounds(
    bundle: Mapping[str, Any],
) -> tuple[tuple[TimelineRound, ...], tuple[dict[str, Any], ...]]:
    """Group recording seconds by their round-number candidate.

    The window of Round *n* is half-open: from its first second carrying *n* to one
    past its last. Seconds in that window without *n* are reported as missing.
    Interleaved readings are reported as conflicts and the contested seconds are
    removed from both Rounds, so windows never overlap and no second belongs to two
    Rounds.
    """
    rows = bundle["seconds"]
    seconds_by_round: dict[int, list[int]] = {}
    for index, row in enumerate(rows):
        value = _round_value(row)
        if value is not None:
            seconds_by_round.setdefault(value, []).append(index)
    rounds: list[TimelineRound] = []
    for round_no in sorted(seconds_by_round):
        present = seconds_by_round[round_no]
        start, end = present[0], present[-1] + 1
        known = set(present)
        rounds.append(
            TimelineRound(
                round_no=round_no,
                start_sec=start,
                end_sec=end,
                seconds_with_round_number=len(present),
                missing_intervals=_intervals([s for s in range(start, end) if s not in known]),
            )
        )
    # No two Rounds may share a second. Where readings interleave, the contested
    # seconds are cut from *both* windows (neither reading is chosen) and reported.
    conflicts: list[dict[str, Any]] = []
    bounds = {item.round_no: [item.start_sec, item.end_sec] for item in rounds}
    for index, earlier in enumerate(rounds):
        for later in rounds[index + 1 :]:
            low = max(bounds[earlier.round_no][0], bounds[later.round_no][0])
            high = min(bounds[earlier.round_no][1], bounds[later.round_no][1])
            if low >= high:
                continue
            conflicts.append(
                {
                    "code": "round_number_interleaved",
                    "rounds": [earlier.round_no, later.round_no],
                    "contested_seconds": [low, high],
                }
            )
            bounds[earlier.round_no][1] = min(bounds[earlier.round_no][1], low)
            bounds[later.round_no][0] = max(bounds[later.round_no][0], high)
    trimmed: list[TimelineRound] = []
    for item in rounds:
        start, end = bounds[item.round_no]
        present = [s for s in seconds_by_round[item.round_no] if start <= s < end]
        if end <= start or not present:
            conflicts.append({"code": "round_dropped_after_trim", "rounds": [item.round_no]})
            continue
        start, end = present[0], present[-1] + 1
        known = set(present)
        trimmed.append(
            TimelineRound(
                round_no=item.round_no,
                start_sec=start,
                end_sec=end,
                seconds_with_round_number=len(present),
                missing_intervals=_intervals([s for s in range(start, end) if s not in known]),
            )
        )
    ordered = sorted(trimmed, key=lambda item: item.start_sec)
    for earlier, later in zip(ordered, ordered[1:], strict=False):
        if later.start_sec < earlier.end_sec:  # pragma: no cover - guarded above
            raise TimelineEvaluationError("Round区間の重複を解消できませんでした")
    return tuple(trimmed), tuple(conflicts)


# ---------------------------------------------------------------- Round Package


def _boundary(kind: str, time_sec: float, bundle: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "status": "provisional",
        "candidate": {
            "kind": kind,
            "boundary_status": "provisional",
            "boundary_time_sec": float(time_sec),
            "confirmation_time_sec": None,
            "evidence_times_sec": [float(time_sec)],
            "confidence": None,
            "provenance": {
                "source": "shared_timeline_round_number_candidate",
                "bundle_version": str(bundle.get("version")),
                "qualification": "development_only",
            },
        },
        "formal_event_id": None,
    }


def build_round_package(
    bundle: Mapping[str, Any],
    round_: TimelineRound,
    *,
    match_id: str,
    source_video: Mapping[str, Any],
    fact_provider: FactProvider | None = None,
) -> dict[str, Any]:
    events, facts = (fact_provider or NoFactProvider()).facts_for(bundle, round_)
    for item in [*events, *facts]:
        span = item.get("time_range")
        times = (
            [float(span["start_sec"]), float(span["end_sec"])]
            if isinstance(span, Mapping)
            else [float(item["time_sec"])] if isinstance(item.get("time_sec"), int | float)
            else []
        )
        # Half-open membership [start, end): a boundary second belongs to the later
        # Round only, so one Fact/Event can never sit in two Round Packages.
        if any(not round_.start_sec <= value < round_.end_sec for value in times[:1]) or any(
            not round_.start_sec < value <= round_.end_sec for value in times[1:]
        ):
            raise TimelineEvaluationError(
                f"R{round_.round_no}: FactProviderの出力がRound窓の外にあります"
            )
    return {
        "schema_version": "2.0",
        "match_id": match_id,
        "round_no": round_.round_no,
        "source_video": dict(source_video),
        "round_window": {"start_sec": float(round_.start_sec), "end_sec": float(round_.end_sec)},
        "round_meta": {
            "side": "unknown",
            "map": "unknown",
            "player_agent": "unknown",
            "player_role": "unknown",
            "round_result": "unknown",
            "score_before": None,
            "economy_context": None,
        },
        "observation_quality": {
            # The existing Practical contract: with uncertain boundaries the Round
            # denominator is unknown, so no confidence and no completeness is claimed
            # (SchemaValidator enforces 0). The measured share of seconds carrying this
            # Round's number is reported separately (round_timelines), never here.
            "hud_confidence": 0.0,
            "visual_confidence": 0.0,
            "timeline_completeness": 0.0,
            "missing_intervals": [
                {"start_sec": float(low), "end_sec": float(high)}
                for low, high in round_.missing_intervals
            ],
        },
        "events": list(events),
        "state_snapshots": [],
        "deterministic_facts": list(facts),
        "frames": [],
        "previous_round_context": None,
        "round_lifecycle": {
            "mode": "practical",
            "observed_round_no": None,
            "start": _boundary("round_start", round_.start_sec, bundle),
            "end": _boundary("round_end", round_.end_sec, bundle),
        },
    }


def round_timeline_summary(bundle: Mapping[str, Any], round_: TimelineRound) -> dict[str, Any]:
    """Seconds per development state and candidate kinds inside one Round window."""
    rows = bundle["seconds"][round_.start_sec : round_.end_sec]
    events = bundle.get("events", {})
    kinds: Counter[str] = Counter()
    seen: set[str] = set()
    for row in rows:
        for ref in row.get("event_candidates", []):
            if ref in seen or ref not in events:
                continue
            seen.add(ref)
            kinds[str(events[ref].get("kind"))] += 1
    return {
        "round_no": round_.round_no,
        "window_seconds": [round_.start_sec, round_.end_sec],
        "seconds_with_round_number": round_.seconds_with_round_number,
        "measured_share_with_round_number": round(round_.completeness, 6),
        "missing_intervals": [list(item) for item in round_.missing_intervals],
        "state_seconds": {
            domain: dict(
                sorted(Counter(str(row[domain]["value"]) for row in rows).items())
            )
            for domain in _STATE_DOMAINS
        },
        "event_candidate_counts": dict(sorted(kinds.items())),
        "qualification": "development_only",
    }


# ------------------------------------------------------------------- evaluation


def default_round_analyzer(
    *, provisional_policy: ProvisionalEvaluationPolicy | None = None
) -> RoundAnalyzer:
    """Local, deterministic analyzer: no API, no network, no frames."""
    registry = json.loads(
        Path(_resource("config/rule_trigger_registry_v2.json")).read_text(encoding="utf-8")
    )
    return RoundAnalyzer(
        fact_builder=FactBuilder(),
        selector=RuleSelector(registry),
        rule_engine=DeterministicRuleEngine(),
        coach=MockCoachAdapter(),
        validator=SchemaValidator(),
        provisional_policy=provisional_policy,
    )


def _resource(relative: str) -> Path:
    from valorant_ai_coach.resources import resource_path

    return Path(resource_path(relative))


def _require_development_bundle(bundle: Mapping[str, Any]) -> None:
    if (
        bundle.get("qualification") != "development_only"
        or bundle.get("formal_outputs") != 0
        or not isinstance(bundle.get("seconds"), list)
        or not bundle["seconds"]
    ):
        raise TimelineEvaluationError("development_onlyの共通タイムライン（正式出力0）が必要です")


def _require_single_membership(packages: Sequence[Mapping[str, Any]]) -> None:
    owners: dict[str, int] = {}
    for package in packages:
        for kind, key in (("events", "event_id"), ("deterministic_facts", "fact_id")):
            for item in package.get(kind, []):
                identifier = f"{kind}:{item[key]}"
                if identifier in owners:
                    raise TimelineEvaluationError(
                        f"{item[key]} がR{owners[identifier]}とR{package['round_no']}の"
                        "両方に属しています"
                    )
                owners[identifier] = int(package["round_no"])


def evaluate_timeline(
    bundle: Mapping[str, Any],
    *,
    match_id: str,
    source_video: Mapping[str, Any],
    analyzer: RoundAnalyzer | None = None,
    fact_provider: FactProvider | None = None,
) -> TimelineEvaluation:
    _require_development_bundle(bundle)
    if not _SAFE_ID.match(match_id):
        raise TimelineEvaluationError(
            "match_idには英数字・ハイフン・アンダースコアだけを使用できます"
        )
    rounds, conflicts = segment_rounds(bundle)
    engine = analyzer or default_round_analyzer()
    packages = tuple(
        build_round_package(
            bundle, item, match_id=match_id, source_video=source_video,
            fact_provider=fact_provider,
        )
        for item in rounds
    )
    _require_single_membership(packages)
    analyses = tuple(engine.analyze(package) for package in packages)
    aggregation = (
        MatchAggregator()
        .aggregate(analyses, match_id=match_id, expected_round_numbers=None)
        .to_dict()
    )
    covered = {s for item in rounds for s in range(item.start_sec, item.end_sec)}
    # Development counts: which rules the production selector would consider on the
    # supplied candidates. Not evaluations; scoring stays withheld for these Rounds.
    candidates = tuple(
        dict(sorted(Counter(
            item.rule_id for item in engine.selector.select(engine.fact_builder.enrich(package))
        ).items()))
        for package in packages
    )
    return TimelineEvaluation(
        match_id=match_id,
        rounds=rounds,
        packages=packages,
        analyses=analyses,
        aggregation=aggregation,
        round_timelines=tuple(round_timeline_summary(bundle, item) for item in rounds),
        unsegmented_seconds=len(bundle["seconds"]) - len(covered),
        conflicts=conflicts,
        rule_candidates=candidates,
    )


def persist_evaluation(
    repository: SQLiteRepository,
    evaluation: TimelineEvaluation,
    *,
    source_video_path: Path,
    source: Mapping[str, Any],
    replace_development: bool = False,
) -> dict[str, Any]:
    """Store through the same repository rows the GUI and JSON export read.

    Development evaluations live in their own ``DEV-`` namespace and never replace a
    formal analysis: an existing Match is only replaced when this bridge created it,
    and only with ``replace_development=True``.
    """
    if not evaluation.match_id.startswith(DEVELOPMENT_MATCH_PREFIX):
        raise TimelineEvaluationError(
            f"開発用評価のmatch_idは{DEVELOPMENT_MATCH_PREFIX}で始めてください"
        )
    existing = repository.get_match(evaluation.match_id)
    if existing is not None:
        origin = (existing.get("metadata") or {}).get("origin")
        if origin != VERSION:
            raise TimelineEvaluationError("既存の正式解析結果は上書きできません")
        if not replace_development:
            raise TimelineEvaluationError(
                "同じmatch_idの開発用評価があります（置き換える場合は明示してください）"
            )
    repository.create_match(
        evaluation.match_id,
        source_video_path,
        metadata={
            "origin": VERSION,
            "qualification": "development_only",
            "source_id": source.get("source_id"),
            "physical_match_id": source.get("physical_match_id"),
        },
        status="analyzing",
    )
    repository.reset_match_analysis(evaluation.match_id)
    for analysis in evaluation.analyses:
        repository.save_round_package(analysis.round_package)
        repository.save_analysis_result(analysis.output)
    numbers = sorted(item.round_no for item in evaluation.rounds)
    repository.save_job_checkpoint(
        evaluation.match_id,
        "completed",
        {
            "completed_rounds": numbers,
            "failed_rounds": [],
            "round_diagnostics": {},
            "qualification": "development_only",
            "origin": VERSION,
            "canonical_evaluation_set": "full_post_dedup_v1",
        },
    )
    repository.update_match_status(evaluation.match_id, "completed")
    return aggregate_saved_match(repository, evaluation.match_id)


def check_consistency(
    evaluation: TimelineEvaluation, stored_aggregation: Mapping[str, Any] | None = None
) -> list[dict[str, Any]]:
    """Every view of the same Match must agree on Rounds, labels and evaluation ids."""
    problems: list[dict[str, Any]] = []
    in_memory = evaluation.aggregation
    output_ids = sorted(
        str(item["evaluation_id"])
        for analysis in evaluation.analyses
        for item in analysis.output.get("evaluations", [])
    )
    aggregation_ids = sorted(str(item["evaluation_id"]) for item in in_memory["evaluations"])
    if output_ids != aggregation_ids:
        problems.append(
            {"code": "evaluation_ids_differ", "views": ["round_outputs", "aggregation"]}
        )
    label_totals = Counter(
        str(item["label"])
        for analysis in evaluation.analyses
        for item in analysis.output.get("evaluations", [])
    )
    round_totals: Counter[str] = Counter()
    for row in in_memory["rounds"]:
        if row["status"] == "included":
            round_totals.update({k: int(v) for k, v in row["label_counts"].items()})
    for label in ("good", "improve", "unscored"):
        if label_totals.get(label, 0) != round_totals.get(label, 0):
            problems.append({"code": "label_count_differs", "label": label})
    rule_totals: Counter[str] = Counter()
    for rule in in_memory["rules"]:
        rule_totals.update({k: int(v) for k, v in rule["counts"].items()})
    for label in ("good", "improve", "unscored"):
        if rule_totals.get(label, 0) != label_totals.get(label, 0):
            problems.append({"code": "rule_count_differs", "label": label})
    timeline_rounds = [item.round_no for item in evaluation.rounds]
    package_rounds = [int(p["round_no"]) for p in evaluation.packages]
    aggregation_rounds = [int(r["round_no"]) for r in in_memory["rounds"]]
    if not timeline_rounds == package_rounds == aggregation_rounds:
        problems.append({"code": "round_numbers_differ"})
    for item, package in zip(evaluation.rounds, evaluation.packages, strict=True):
        window = package["round_window"]
        if (window["start_sec"], window["end_sec"]) != (item.start_sec, item.end_sec):
            problems.append({"code": "round_window_differs", "round_no": item.round_no})
    if stored_aggregation is not None:
        for key in ("rounds", "rules", "evaluations", "occurrence_summaries"):
            if stored_aggregation.get(key) != in_memory.get(key):
                problems.append({"code": "stored_view_differs", "field": key})
        if stored_aggregation.get("completeness", {}).get("status") != in_memory["completeness"][
            "status"
        ]:
            problems.append({"code": "stored_view_differs", "field": "completeness.status"})
    return problems


def build_report(
    evaluation: TimelineEvaluation,
    *,
    source: Mapping[str, Any],
    consistency: Sequence[Mapping[str, Any]],
    stored: bool,
) -> dict[str, Any]:
    labels = Counter(
        str(item["label"])
        for analysis in evaluation.analyses
        for item in analysis.output.get("evaluations", [])
    )
    admissions = Counter(analysis.admission for analysis in evaluation.analyses)
    return {
        "version": VERSION,
        "kind": REPORT_KIND,
        "qualification": "development_only",
        "formal_outputs": 0,
        "match_id": evaluation.match_id,
        "source": {
            "source_id": source.get("source_id"),
            "physical_match_id": source.get("physical_match_id"),
        },
        "rounds_segmented": len(evaluation.rounds),
        "unsegmented_seconds": evaluation.unsegmented_seconds,
        "segmentation_conflicts": list(evaluation.conflicts),
        "round_admission": dict(sorted(admissions.items())),
        "evaluation_counts": {
            label: labels.get(label, 0) for label in ("good", "improve", "unscored")
        },
        "round_timelines": [
            {**row, "rule_candidate_counts": counts}
            for row, counts in zip(
                evaluation.round_timelines,
                evaluation.rule_candidates or [{}] * len(evaluation.round_timelines),
                strict=True,
            )
        ],
        "rule_candidate_totals": dict(sorted(sum(
            (Counter(counts) for counts in evaluation.rule_candidates), Counter()
        ).items())),
        "match_aggregation": evaluation.aggregation,
        "stored_in_repository": stored,
        "consistency_problems": list(consistency),
        "scope": (
            "Development candidates routed through the production evaluation path. "
            "Not a coaching score and not recognition accuracy."
        ),
    }


def render_markdown(report: Mapping[str, Any]) -> str:
    aggregation = report["match_aggregation"]
    lines = [
        f"# 共通タイムライン評価接続レポート（{report['match_id']}）",
        "",
        "開発候補を正式評価経路へ通した結果です。採点やcoaching評価ではありません。",
        "",
        f"- 区切ったRound数: {report['rounds_segmented']}",
        f"- Roundに属さない秒数: {report['unsegmented_seconds']}",
        f"- Roundの扱い: {report['round_admission']}",
        f"- 評価件数 GOOD/IMPROVE/UNSCORED: "
        f"{report['evaluation_counts']['good']}/{report['evaluation_counts']['improve']}/"
        f"{report['evaluation_counts']['unscored']}",
        f"- Match完全性: {aggregation['completeness']['status']}"
        f"（理由: {', '.join(aggregation['completeness']['blocking_reasons']) or 'なし'}）",
        f"- 整合性の問題: {len(report['consistency_problems'])}件",
        "",
        "| Round | 窓(秒) | Round番号のある秒 | 欠落区間 | round_state | life_state "
        "| camera_state |",
        "|---:|---|---:|---:|---|---|---|",
    ]
    for row in report["round_timelines"]:
        states = row["state_seconds"]

        def fmt(domain: str, states: Mapping[str, Any] = states) -> str:
            return ", ".join(f"{k} {v}" for k, v in states[domain].items())

        lines.append(
            f"| {row['round_no']} | {row['window_seconds'][0]}–{row['window_seconds'][1]} | "
            f"{row['seconds_with_round_number']} | {len(row['missing_intervals'])} | "
            f"{fmt('round_state')} | {fmt('life_state')} | {fmt('camera_state')} |"
        )
    return "\n".join(lines) + "\n"


def _write_private(path: Path, text: str) -> None:
    with open(path, "x", encoding="utf-8", opener=lambda p, f: os.open(p, f, 0o600)) as stream:
        stream.write(text)


def run(
    *,
    timeline_path: Path,
    output: Path,
    match_id: str,
    database: Path | None = None,
    source_video_path: Path | None = None,
    derived_samples: Path | None = None,
    replace_development: bool = False,
) -> dict[str, Any]:
    bundle = json.loads(timeline_path.read_text(encoding="utf-8"))
    _require_development_bundle(bundle)
    if output.exists():
        raise TimelineEvaluationError("新しい出力ディレクトリを指定してください")
    source = dict(bundle.get("source") or {})
    recording = bundle.get("recording") or {}
    source_video = {
        # The private path is not copied into the report; the package keeps an
        # opaque reference unless a real path is supplied for the GUI.
        "path": (
            str(source_video_path)
            if source_video_path
            else f"private:{source.get('source_id')}"
        ),
        "fps": 1.0,
        "width": 1,
        "height": 1,
        "duration_sec": float(recording.get("end_timestamp") or len(bundle["seconds"])),
    }
    provider = None
    if derived_samples is not None:
        provider = DerivedSampleFactProvider(
            json.loads(derived_samples.read_text(encoding="utf-8"))
        )
    evaluation = evaluate_timeline(
        bundle, match_id=match_id, source_video=source_video, fact_provider=provider
    )
    stored_view = None
    if database is not None:
        stored_view = persist_evaluation(
            SQLiteRepository(database),
            evaluation,
            source_video_path=source_video_path or timeline_path,
            source=source,
            replace_development=replace_development,
        )
    consistency = check_consistency(evaluation, stored_view)
    report = build_report(
        evaluation, source=source, consistency=consistency, stored=database is not None
    )
    report["fact_provider"] = None if provider is None else {
        "name": provider.SOURCE,
        "samples": len(provider.samples),
        "unsupported_event_types": dict(sorted(provider.unsupported_events.items())),
    }
    output.mkdir(parents=True, mode=0o700)
    _write_private(
        output / "match_evaluation_PRIVATE.json",
        json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False) + "\n",
    )
    _write_private(output / "match_evaluation_PRIVATE.md", render_markdown(report))
    return report


def admission_table_rows() -> list[dict[str, Any]]:
    return ProvisionalAdmissionTable.load().to_rows()


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="command", required=True)
    evaluate = sub.add_parser("evaluate", help="共通タイムラインを評価経路へ通す")
    evaluate.add_argument("--timeline", type=Path, required=True)
    evaluate.add_argument("--output", type=Path, required=True)
    evaluate.add_argument("--match-id", required=True)
    evaluate.add_argument("--database", type=Path)
    evaluate.add_argument("--source-video", type=Path)
    evaluate.add_argument("--derived-samples", type=Path,
                          help="#155 development_readiness.derive の出力（JSON）")
    evaluate.add_argument("--replace-development", action="store_true")
    sub.add_parser("admission-table", help="#25 境界非依存ルールの分類表を出力")
    args = parser.parse_args(argv)
    if args.command == "admission-table":
        print(json.dumps(admission_table_rows(), ensure_ascii=False, indent=2))
        return 0
    report = run(
        timeline_path=args.timeline,
        output=args.output,
        match_id=args.match_id,
        database=args.database,
        source_video_path=args.source_video,
        derived_samples=args.derived_samples,
        replace_development=args.replace_development,
    )
    print(
        json.dumps(
            {
                "rounds_segmented": report["rounds_segmented"],
                "unsegmented_seconds": report["unsegmented_seconds"],
                "evaluation_counts": report["evaluation_counts"],
                "completeness": report["match_aggregation"]["completeness"]["status"],
                "consistency_problems": len(report["consistency_problems"]),
            },
            ensure_ascii=False,
        )
    )
    return 1 if report["consistency_problems"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
