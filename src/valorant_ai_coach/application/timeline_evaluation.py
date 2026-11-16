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

    The window of Round *n* spans its first to its last second carrying *n*. Seconds in
    that window without *n* are reported as missing. Interleaved readings (a later
    Round number appearing before an earlier one ends) are returned as conflicts and the
    windows are kept as read, so that the Match view reports the overlap instead of the
    bridge choosing one reading.
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
    conflicts: list[dict[str, Any]] = []
    for earlier, later in zip(rounds, rounds[1:], strict=False):
        if later.start_sec < earlier.end_sec:
            conflicts.append(
                {
                    "code": "round_number_interleaved",
                    "rounds": [earlier.round_no, later.round_no],
                    "overlap_seconds": [later.start_sec, min(earlier.end_sec, later.end_sec)],
                }
            )
    return tuple(rounds), tuple(conflicts)


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
        time_sec = item.get("time_sec")
        if isinstance(time_sec, int | float) and not (
            round_.start_sec <= float(time_sec) <= round_.end_sec
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
    analyses = tuple(engine.analyze(package) for package in packages)
    aggregation = (
        MatchAggregator()
        .aggregate(analyses, match_id=match_id, expected_round_numbers=None)
        .to_dict()
    )
    covered = {s for item in rounds for s in range(item.start_sec, item.end_sec)}
    return TimelineEvaluation(
        match_id=match_id,
        rounds=rounds,
        packages=packages,
        analyses=analyses,
        aggregation=aggregation,
        round_timelines=tuple(round_timeline_summary(bundle, item) for item in rounds),
        unsegmented_seconds=len(bundle["seconds"]) - len(covered),
        conflicts=conflicts,
    )


def persist_evaluation(
    repository: SQLiteRepository,
    evaluation: TimelineEvaluation,
    *,
    source_video_path: Path,
    source: Mapping[str, Any],
) -> dict[str, Any]:
    """Store through the same repository rows the GUI and JSON export read."""
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
        "round_timelines": list(evaluation.round_timelines),
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
    evaluation = evaluate_timeline(bundle, match_id=match_id, source_video=source_video)
    stored_view = None
    if database is not None:
        stored_view = persist_evaluation(
            SQLiteRepository(database),
            evaluation,
            source_video_path=source_video_path or timeline_path,
            source=source,
        )
    consistency = check_consistency(evaluation, stored_view)
    report = build_report(
        evaluation, source=source, consistency=consistency, stored=database is not None
    )
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
