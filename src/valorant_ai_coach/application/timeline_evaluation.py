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
  P0 producers, #32/#155) or from the formal promotion step
  (``facts/timeline_promotion.TimelinePromoter``), which turns the timeline's own
  candidates into ``confirmed`` boundaries, formal Events and state snapshots only
  where its evidence gates are met. Rounds whose boundaries were not promoted stay
  ``provisional`` and keep withholding scoring.
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
from dataclasses import dataclass, field, replace
from pathlib import Path
from threading import Event
from typing import Any, Protocol

from valorant_ai_coach.facts import FactBuilder
from valorant_ai_coach.facts.second_feature_promotion import (
    SecondFeaturePromoter,
    load_frame_refs,
    load_records,
    records_source_sha256,
)
from valorant_ai_coach.facts.timeline_promotion import (
    EVENT_ID_PREFIX,
    FORMAL_QUALIFICATION,
    PromotionResult,
    RoundPromotion,
    TimelinePromoter,
    TimelineView,
    observation_quality,
    timeline_view_from_replay,
    verify_promotion,
)
from valorant_ai_coach.rules import DeterministicRuleEngine, RuleSelector
from valorant_ai_coach.rules.policy_runtime import (
    DEVELOPMENT_ID_PREFIX,
    SCORED_CONFIDENCE_FLOOR,
    ProvisionalAdmissionTable,
    ProvisionalEvaluationPolicy,
    enforce_confidence_floor,
    split_development_candidates,
)
from valorant_ai_coach.schema_validation import SchemaValidator
from valorant_ai_coach.storage import SQLiteRepository

from .match_aggregation import MatchAggregator
from .match_aggregation_service import PROVISIONAL_PARTIAL_MARKER, aggregate_saved_match
from .round_analyzer import (
    ADMISSION_PROVISIONAL_PARTIAL,
    MockCoachAdapter,
    RoundAnalysis,
    RoundAnalyzer,
    RoundCoach,
)

VERSION = "timeline_evaluation_bridge.v1"
API_NOT_RUN_MESSAGE = "AIコーチ（API）を実行していないため採点していません"
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
    # Set when the formal promotion confirmed both boundaries: the window above is
    # then the formal Round window (buy phase through the ENDED display).
    formal: RoundPromotion | None = None

    @property
    def confirmed(self) -> bool:
        return self.formal is not None and self.formal.confirmed

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
                identifier = f"{DEVELOPMENT_ID_PREFIX}{kind}-{stamp}"
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
                        "fact_id": f"{DEVELOPMENT_ID_PREFIX}{key}-{stamp}",
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
    promotion: PromotionResult | None = None
    second_features: dict[str, Any] | None = None


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
    for index, row in enumerate(rows):
        # Windows are recording seconds; Facts from producers use the same clock.
        stamp = row.get("timestamp", index)
        if isinstance(stamp, bool) or not isinstance(stamp, int | float) or stamp != index:
            raise TimelineEvaluationError("秒行のtimestampが行番号（録画の秒）と一致しません")
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


def _confirmed_boundary(event_id: str) -> dict[str, Any]:
    return {"status": "confirmed", "candidate": None, "formal_event_id": event_id}


def formal_rounds(
    rounds: Sequence[TimelineRound], promotion: PromotionResult, view: TimelineView
) -> tuple[TimelineRound, ...]:
    """Replace each segment window by the formal window where promotion confirmed it."""
    by_round = {item.round_no: item for item in promotion.rounds}
    result: list[TimelineRound] = []
    for item in rounds:
        promoted = by_round.get(item.round_no)
        if promoted is None or not promoted.confirmed:
            result.append(replace(item, formal=promoted))
            continue
        assert promoted.window is not None
        start, end = promoted.window
        quality = observation_quality(view, (start, end), promoted.snapshots)
        result.append(
            TimelineRound(
                round_no=item.round_no,
                start_sec=start,
                end_sec=end,
                seconds_with_round_number=sum(
                    1 for row in view.seconds[start:end] if row.round_no == item.round_no
                ),
                missing_intervals=tuple(
                    (int(gap["start_sec"]), int(gap["end_sec"]))
                    for gap in quality["missing_intervals"]
                ),
                formal=promoted,
            )
        )
    ordered = sorted(result, key=lambda r: r.start_sec)
    for earlier, later in zip(ordered, ordered[1:], strict=False):
        if later.start_sec < earlier.end_sec:
            raise TimelineEvaluationError(
                f"R{earlier.round_no}とR{later.round_no}の正式Round窓が重なっています"
            )
    return tuple(result)


def build_round_package(
    bundle: Mapping[str, Any],
    round_: TimelineRound,
    *,
    match_id: str,
    source_video: Mapping[str, Any],
    fact_provider: FactProvider | None = None,
    view: TimelineView | None = None,
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
    formal = round_.formal if round_.confirmed else None
    if formal is not None:
        assert formal.start is not None and formal.end is not None
        if view is None:
            view = TimelineView(bundle)
        start_id = f"tl-round_start-R{round_.round_no}-{formal.start.time_sec}"
        end_id = f"tl-round_end-R{round_.round_no}-{formal.end.time_sec}"
        formal_ids = {str(e["event_id"]) for e in formal.events}
        if start_id not in formal_ids or end_id not in formal_ids:  # pragma: no cover
            raise TimelineEvaluationError("昇格したRound境界のEventが見つかりません")
        lifecycle = {
            "mode": "practical",
            "observed_round_no": None,
            "start": _confirmed_boundary(start_id),
            "end": _confirmed_boundary(end_id),
        }
        quality = observation_quality(
            view, (round_.start_sec, round_.end_sec), formal.snapshots
        )
        all_events = [*(dict(e) for e in formal.events), *events]
        snapshots = [dict(snapshot) for snapshot in formal.snapshots]
        meta = {
            "side": str(formal.round_meta.get("side", "unknown")),
            "map": "unknown",
            "player_agent": str(formal.round_meta.get("player_agent", "unknown")),
            "player_role": str(formal.round_meta.get("player_role", "unknown")),
            "round_result": str(formal.round_meta.get("round_result", "unknown")),
            "score_before": formal.round_meta.get("score_before"),
            "economy_context": None,
        }
    else:
        lifecycle = {
            "mode": "practical",
            "observed_round_no": None,
            "start": _boundary("round_start", round_.start_sec, bundle),
            "end": _boundary("round_end", round_.end_sec, bundle),
        }
        quality = {
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
        }
        all_events = list(events)
        snapshots = []
        meta = {
            "side": "unknown",
            "map": "unknown",
            "player_agent": "unknown",
            "player_role": "unknown",
            "round_result": "unknown",
            "score_before": None,
            "economy_context": None,
        }
    return {
        "schema_version": "2.0",
        "match_id": match_id,
        "round_no": round_.round_no,
        "source_video": dict(source_video),
        "round_window": {"start_sec": float(round_.start_sec), "end_sec": float(round_.end_sec)},
        "round_meta": meta,
        "observation_quality": quality,
        "events": all_events,
        "state_snapshots": snapshots,
        "deterministic_facts": list(facts),
        "frames": [],
        "previous_round_context": None,
        "round_lifecycle": lifecycle,
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
        "boundary_status": "confirmed" if round_.confirmed else "provisional",
    }


# ------------------------------------------------------------------- evaluation


def default_round_analyzer(
    *,
    provisional_policy: ProvisionalEvaluationPolicy | None = None,
    coach: RoundCoach | None = None,
) -> RoundAnalyzer:
    """Local, deterministic analyzer: no API, no network, no frames (unless ``coach``)."""
    registry = json.loads(
        Path(_resource("config/rule_trigger_registry_v2.json")).read_text(encoding="utf-8")
    )
    selector = RuleSelector(registry)
    return RoundAnalyzer(
        fact_builder=FactBuilder(),
        selector=selector,
        rule_engine=DeterministicRuleEngine(),
        coach=coach or MissingFactAbstentionCoach(MockCoachAdapter(), selector),
        validator=SchemaValidator(),
        provisional_policy=provisional_policy,
    )


class MissingFactAbstentionCoach:
    """Explicit UNSCORED for candidates whose allow_unscored facts are missing.

    The offline (mock) coach only produces labels for the observation patterns it
    knows. For a candidate rule that the production selector admitted with missing
    ``allow_unscored`` facts (e.g. UTL-01 without ``utility_available_count``), the
    mock stays silent, which the stored result would show as "no evaluation". The
    agreed policy (2026-10-07) is to emit an explicit UNSCORED with the missing facts
    instead of "0 evaluations". Candidates whose predicates are all satisfied and
    which the inner coach left neutral are not touched (registry ``neutral`` rule).
    Never used in front of the API coach: there the model decides.
    """

    def __init__(self, inner: RoundCoach, selector: RuleSelector) -> None:
        self.inner = inner
        self.selector = selector
        self.rule_defs = {
            item["id"]: item
            for item in json.loads(
                Path(_resource("config/valorant_evaluation_rules_v4.json")).read_text(
                    encoding="utf-8"
                )
            )["rules"]
        }

    def evaluate(
        self,
        round_package: dict[str, Any],
        candidate_rule_ids: list[str],
        *,
        frame_paths: list[Path] | None = None,
        deterministic_decisions: dict[str, dict[str, Any]] | None = None,
        analysis_scopes: dict[str, dict[str, Any]] | None = None,
        cancel_event: Event | None = None,
    ) -> dict[str, Any]:
        output = self.inner.evaluate(
            round_package,
            candidate_rule_ids,
            frame_paths=frame_paths,
            deterministic_decisions=deterministic_decisions,
            analysis_scopes=analysis_scopes,
            cancel_event=cancel_event,
        )
        # Without the API coach no GOOD/IMPROVE is formal unless the deterministic rule
        # engine decided that very label. Anything else the offline evaluator scored is
        # kept as UNSCORED ("AI coach not run"), never stored as a coaching result.
        decided = deterministic_decisions or {}
        guarded = []
        for item in output.get("evaluations", []):
            decision = decided.get(str(item.get("primary_rule_id")))
            if item.get("label") in {"good", "improve"} and not (
                decision is not None and decision.get("label") == item["label"]
            ):
                item = {
                    **item,
                    "label": "unscored",
                    "decision_source": "deterministic",
                    "clip_id": None,
                    "display_clip": None,
                    "improvement": None,
                    "fact_refs": [],
                    "evidence": [],
                    "evidence_range": None,
                    "confidence": 0.0,
                    "missing_information": [API_NOT_RUN_MESSAGE],
                    "unscored_reason_code": "other",
                }
            guarded.append(item)
        output["evaluations"] = guarded
        covered = {
            str(item.get("primary_rule_id")) for item in output.get("evaluations", [])
        } | {
            str(rule_id)
            for item in output.get("evaluations", [])
            for rule_id in item.get("related_rule_ids", [])
        }
        for candidate in self.selector.select(round_package):
            if (
                candidate.rule_id not in candidate_rule_ids
                or candidate.rule_id in covered
                or not candidate.missing_fact_keys
            ):
                continue
            rule = self.rule_defs.get(candidate.rule_id, {})
            output["evaluations"].append(
                {
                    "evaluation_id": (
                        f"abstain-{round_package['match_id']}-R{round_package['round_no']}-"
                        f"{candidate.rule_id}"
                    ),
                    "clip_id": None,
                    "primary_rule_id": candidate.rule_id,
                    "related_rule_ids": [],
                    "label": "unscored",
                    "decision_source": "deterministic",
                    "fact_refs": [],
                    "concept_tags": list(rule.get("concept_tags", [])),
                    "title": f"{rule.get('item', candidate.rule_id)}の評価",
                    "situation": (
                        "正式Fact/Eventからトリガーは観測されましたが、判定に必要な事実が不足しています"
                    ),
                    "reason": "必要な事実が観測できないため採点を保留しました",
                    "improvement": None,
                    "confidence": 0.0,
                    "evidence": [],
                    "evidence_range": None,
                    "display_clip": None,
                    "missing_information": [
                        f"{key} を観測できません" for key in candidate.missing_fact_keys
                    ],
                    "unscored_reason_code": "missing_required_fact",
                }
            )
        return output


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


def _apply_confidence_floor(analysis: RoundAnalysis, validator: SchemaValidator) -> RoundAnalysis:
    """D-1b floor for every stored evaluation, the same as the video pipeline."""
    output = dict(analysis.output)
    evaluations = [enforce_confidence_floor(item) for item in output.get("evaluations", [])]
    if evaluations == list(output.get("evaluations", [])):
        return analysis
    output["evaluations"] = evaluations
    validator.validate_ai_output(output, round_package=analysis.round_package)
    return replace(analysis, output=output)


def evaluate_timeline(
    bundle: Mapping[str, Any],
    *,
    match_id: str,
    source_video: Mapping[str, Any],
    analyzer: RoundAnalyzer | None = None,
    fact_provider: FactProvider | None = None,
    promoter: TimelinePromoter | None = None,
    second_features: tuple[Sequence[Any], str | None] | None = None,
    frame_refs: Mapping[float, str] | None = None,
    motion_frames: Sequence[Any] | None = None,
) -> TimelineEvaluation:
    _require_development_bundle(bundle)
    if not _SAFE_ID.match(match_id):
        raise TimelineEvaluationError(
            "match_idには英数字・ハイフン・アンダースコアだけを使用できます"
        )
    rounds, conflicts = segment_rounds(bundle)
    engine = analyzer or default_round_analyzer()
    promotion: PromotionResult | None = None
    view: TimelineView | None = None
    feature_report: dict[str, Any] | None = None
    if second_features is not None and promoter is None:
        raise TimelineEvaluationError("特徴量の昇格には共通タイムラインの昇格が必要です")
    if promoter is not None:
        view = TimelineView(bundle)
        promotion = promoter.promote(
            bundle, [(item.round_no, item.start_sec, item.end_sec) for item in rounds]
        )
        if second_features is not None:
            records, records_sha256 = second_features
            feature_report = SecondFeaturePromoter().augment(
                bundle, promotion, records, records_sha256=records_sha256,
                frame_refs=frame_refs, motion_frames=motion_frames,
            ).to_dict()
        rounds = formal_rounds(rounds, promotion, view)
    packages = tuple(
        build_round_package(
            bundle, item, match_id=match_id, source_video=source_video,
            fact_provider=fact_provider, view=view,
        )
        for item in rounds
    )
    _require_single_membership(packages)
    analyses = tuple(
        _apply_confidence_floor(engine.analyze(package), engine.validator)
        for package in packages
    )
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
        promotion=promotion,
        second_features=feature_report,
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
    checkpoint: dict[str, Any] = {
        "completed_rounds": numbers,
        "failed_rounds": [],
        "round_diagnostics": {},
        "qualification": "development_only",
        "origin": VERSION,
        "canonical_evaluation_set": "full_post_dedup_v1",
    }
    if any(item.admission == ADMISSION_PROVISIONAL_PARTIAL for item in evaluation.analyses):
        # Same marker the pipeline writes: rows from an opt-in (#25) analyzer are only
        # restored by the stored-match view when the run declares it.
        checkpoint["provisional_evaluation"] = PROVISIONAL_PARTIAL_MARKER
    repository.save_job_checkpoint(evaluation.match_id, "completed", checkpoint)
    repository.update_match_status(evaluation.match_id, "completed")
    return aggregate_saved_match(repository, evaluation.match_id)


def _without_time_scope(rules: Any) -> Any:
    if not isinstance(rules, list):
        return rules
    return [
        {
            **rule,
            "context_by_round": [
                {key: value for key, value in row.items() if key != "time_scope"}
                for row in rule.get("context_by_round", [])
            ],
        }
        for rule in rules
    ]


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
        unscoped = not (stored_aggregation.get("storage_provenance") or {}).get(
            "candidate_scopes_restored", True
        )
        for key in ("rounds", "rules", "evaluations", "occurrence_summaries"):
            stored_value, live_value = stored_aggregation.get(key), in_memory.get(key)
            if key == "rules" and unscoped:
                # The stored view declares that it does not restore candidate time
                # scopes (it never infers them); compare everything else.
                stored_value, live_value = _without_time_scope(stored_value), (
                    _without_time_scope(live_value)
                )
            if stored_value != live_value:
                problems.append({"code": "stored_view_differs", "field": key})
        if stored_aggregation.get("completeness", {}).get("status") != in_memory["completeness"][
            "status"
        ]:
            problems.append({"code": "stored_view_differs", "field": "completeness.status"})
    return problems


def _rule_outputs(evaluation: TimelineEvaluation) -> dict[str, dict[str, int]]:
    """Per-rule counts of stored evaluations by label (primary rule only)."""
    counts: dict[str, Counter[str]] = {}
    for analysis in evaluation.analyses:
        for item in analysis.output.get("evaluations", []):
            counts.setdefault(str(item["primary_rule_id"]), Counter())[str(item["label"])] += 1
    return {rule: dict(sorted(c.items())) for rule, c in sorted(counts.items())}


def scorability(evaluation: TimelineEvaluation) -> dict[str, Any]:
    """Which candidate rules could be scored, decided without any API call.

    Per confirmed Round and selected candidate rule:

    * ``deterministic_decided``: the deterministic rule engine produced the label.
    * ``ready_for_api``: every required fact is present at or above the 0.55 floor;
      the label needs the AI coach (``llm_contextual``), which was not run here.
    * ``low_confidence``: required facts are present but one is below the floor.
    * ``missing_facts``: a required fact is not observed (stored as UNSCORED).
    """
    registry = json.loads(
        Path(_resource("config/rule_trigger_registry_v2.json")).read_text(encoding="utf-8")
    )["rules"]
    per_rule: dict[str, Counter[str]] = {}
    missing: dict[str, Counter[str]] = {}
    for analysis in evaluation.analyses:
        if analysis.admission != "confirmed":
            continue
        facts = analysis.round_package.get("deterministic_facts", [])
        best: dict[str, float] = {}
        for fact in facts:
            key = str(fact["key"])
            best[key] = max(best.get(key, 0.0), float(fact["confidence"]))
        for candidate in analysis.candidates:
            rule = registry.get(candidate.rule_id, {})
            required = [str(p["fact_key"]) for p in rule.get("required_state_predicates", [])]
            if candidate.rule_id in analysis.deterministic_decisions:
                status = "deterministic_decided"
            elif candidate.missing_fact_keys:
                status = "missing_facts"
                missing.setdefault(candidate.rule_id, Counter()).update(
                    candidate.missing_fact_keys
                )
            elif any(best.get(key, 0.0) < SCORED_CONFIDENCE_FLOOR for key in required):
                status = "low_confidence"
            else:
                status = "ready_for_api"
            per_rule.setdefault(candidate.rule_id, Counter())[status] += 1
    totals: Counter[str] = Counter()
    for counts in per_rule.values():
        totals.update(counts)
    return {
        "method": "offline_fact_sufficiency",
        "note": "ready_for_api is not a label: the AI coach decides it",
        "totals": dict(sorted(totals.items())),
        "rules_ready_for_api": sorted(
            rule for rule, c in per_rule.items() if c.get("ready_for_api")
        ),
        "rules_deterministic_decided": sorted(
            rule for rule, c in per_rule.items() if c.get("deterministic_decided")
        ),
        "per_rule": {rule: dict(sorted(c.items())) for rule, c in sorted(per_rule.items())},
        "missing_fact_keys": {
            rule: dict(sorted(c.items())) for rule, c in sorted(missing.items())
        },
    }


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
    formal_counts = [split_development_candidates(package)[1] for package in evaluation.packages]
    formal_events = sum(item["formal_events"] for item in formal_counts)
    promoted_events = [
        event for package in evaluation.packages for event in package.get("events", [])
        if str(event.get("event_id", "")).startswith(EVENT_ID_PREFIX)
    ]
    result_tiers = {
        # dev- candidates: excluded from scoring and storage.
        "development": {
            "events": sum(item["development_events"] for item in formal_counts),
            "facts": sum(item["development_facts"] for item in formal_counts),
        },
        # tl- Events promoted from the shared timeline under development-calibrated
        # evidence conditions; GOOD/IMPROVE only from the Rule Engine (or a real API run).
        "promoted_from_shared_timeline": {
            "events": len(promoted_events),
            "events_labelled": sum(
                1 for event in promoted_events
                if (event.get("attributes") or {}).get("qualification") == FORMAL_QUALIFICATION
            ),
        },
        # Needs a pass on unexposed recordings; none exist yet.
        "independently_qualified": {"events": 0, "facts": 0},
    }
    formal_facts = sum(
        len(analysis.round_package.get("deterministic_facts", []))
        for analysis in evaluation.analyses
    )
    rule_outputs = _rule_outputs(evaluation)
    return {
        "version": VERSION,
        "kind": REPORT_KIND,
        "qualification": "development_only",
        "formal_outputs": 0,
        "formal_promotion": (
            None if evaluation.promotion is None else evaluation.promotion.report()
        ),
        "second_feature_promotion": evaluation.second_features,
        "scorability": scorability(evaluation),
        "result_tiers": result_tiers,
        "formal_input_counts": {
            "qualification": FORMAL_QUALIFICATION,
            "formal_events": formal_events,
            "formal_facts_after_fact_builder": formal_facts,
            "state_snapshots": sum(
                len(package.get("state_snapshots", [])) for package in evaluation.packages
            ),
            "rounds_confirmed": sum(1 for item in evaluation.rounds if item.confirmed),
        },
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
        "rule_outputs": rule_outputs,
        "rules_with_output": len(rule_outputs),
        "rules_with_scored_output": sum(
            1 for counts in rule_outputs.values() if counts.get("good") or counts.get("improve")
        ),
        "round_timelines": [
            {**row, "rule_candidate_counts": counts, "fact_counts": formal}
            for row, counts, formal in zip(
                evaluation.round_timelines,
                evaluation.rule_candidates or [{}] * len(evaluation.round_timelines),
                formal_counts,
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
            "Formal Events/Facts promoted from the shared DEVELOPMENT timeline, routed "
            "through the production evaluation path. The recordings are development "
            "data; this is not an independent qualification result."
        ),
    }


def render_markdown(report: Mapping[str, Any]) -> str:
    aggregation = report["match_aggregation"]
    promotion = report.get("formal_promotion") or {}
    formal = report.get("formal_input_counts", {})
    lines = [
        f"# 共通タイムライン評価接続レポート（{report['match_id']}）",
        "",
        "共通タイムラインの候補を証拠条件つきで正式Fact/Eventへ昇格し、正式評価経路へ通した"
        "結果です。開発用録画に対する結果であり、独立評価の結果ではありません。",
        "",
        f"- 区切ったRound数: {report['rounds_segmented']}"
        f"（境界確定 {formal.get('rounds_confirmed', 0)}）",
        f"- 正式Event: {formal.get('formal_events', 0)}"
        f"（内訳 {promotion.get('formal_event_counts', {})}）",
        f"- 正式Fact（FactBuilder後）: {formal.get('formal_facts_after_fact_builder', 0)}",
        f"- state_snapshot: {formal.get('state_snapshots', 0)}",
        f"- Roundに属さない秒数: {report['unsegmented_seconds']}",
        f"- Roundの扱い: {report['round_admission']}",
        f"- 評価件数 GOOD/IMPROVE/UNSCORED: "
        f"{report['evaluation_counts']['good']}/{report['evaluation_counts']['improve']}/"
        f"{report['evaluation_counts']['unscored']}",
        f"- 評価出力のあるルール数: {report.get('rules_with_output', 0)}"
        f"（GOOD/IMPROVEあり {report.get('rules_with_scored_output', 0)}）",
        f"- 昇格を見送った理由: {promotion.get('abstentions', {})}",
        f"- 却下した候補: {promotion.get('rejected_candidates', {})}",
        f"- Match完全性: {aggregation['completeness']['status']}"
        f"（理由: {', '.join(aggregation['completeness']['blocking_reasons']) or 'なし'}）",
        f"- 整合性の問題: {len(report['consistency_problems'])}件",
        "",
        "| Round | 境界 | 窓(秒) | Round番号のある秒 | 欠落区間 | 正式Event | round_state "
        "| life_state | camera_state | 候補ルール | 評価 |",
        "|---:|---|---|---:|---:|---:|---|---|---|---|---|",
    ]
    outputs_by_round: dict[int, Counter[str]] = {}
    for row in aggregation.get("evaluations", []):
        outputs_by_round.setdefault(int(row["round_no"]), Counter())[str(row["label"])] += 1
    for row in report["round_timelines"]:
        states = row["state_seconds"]

        def fmt(domain: str, states: Mapping[str, Any] = states) -> str:
            return ", ".join(f"{k} {v}" for k, v in states[domain].items())

        labels = outputs_by_round.get(int(row["round_no"]), Counter())
        lines.append(
            f"| {row['round_no']} | {row.get('boundary_status', 'provisional')} | "
            f"{row['window_seconds'][0]}–{row['window_seconds'][1]} | "
            f"{row['seconds_with_round_number']} | {len(row['missing_intervals'])} | "
            f"{row.get('fact_counts', {}).get('formal_events', 0)} | "
            f"{fmt('round_state')} | {fmt('life_state')} | {fmt('camera_state')} | "
            f"{', '.join(row.get('rule_candidate_counts', {}))} | "
            f"{labels.get('good', 0)}/{labels.get('improve', 0)}/{labels.get('unscored', 0)} |"
        )
    if report.get("rule_outputs"):
        lines += ["", "| ルール | GOOD | IMPROVE | UNSCORED |", "|---|---:|---:|---:|"]
        for rule, counts in report["rule_outputs"].items():
            lines.append(
                f"| {rule} | {counts.get('good', 0)} | {counts.get('improve', 0)} | "
                f"{counts.get('unscored', 0)} |"
            )
    if map_review := report.get("development_map"):
        summary = map_review["summary"]
        lines.extend([
            "", "## 開発用Map観測", "",
            f"位置候補 {summary['seconds_with_position']}秒、観測エッジ "
            f"{summary['seconds_with_native_edge']}秒、位置不明 {summary['unknown_seconds']}秒。",
            f"本人選択候補 {summary['seconds_with_recorder_selection']}秒、補助観測のみ "
            f"{summary['seconds_with_support_only']}秒、"
            f"本人選択候補のZone競合 {summary['seconds_with_conflicting_selected_zones']}秒。",
            "秒数は観測の存在を表します。Zone滞在時間と評価スコアは算出対象外です。",
        ])
    return "\n".join(lines) + "\n"


def _write_private(path: Path, text: str) -> None:
    with open(path, "x", encoding="utf-8", opener=lambda p, f: os.open(p, f, 0o600)) as stream:
        stream.write(text)


def load_bundle(timeline_path: Path | None, replay_path: Path | None) -> dict[str, Any]:
    """Read an application bundle, or project a replay export into the bundle shape."""
    if (timeline_path is None) == (replay_path is None):
        raise TimelineEvaluationError("--timeline か --replay のどちらか一方を指定してください")
    if timeline_path is not None:
        if timeline_path.suffix == ".gz":
            import gzip

            with gzip.open(timeline_path, "rt", encoding="utf-8") as stream:
                loaded = json.load(stream)
        else:
            loaded = json.loads(timeline_path.read_text(encoding="utf-8"))
        if not isinstance(loaded, dict):
            raise TimelineEvaluationError("共通タイムラインのJSONがオブジェクトではありません")
        return loaded
    assert replay_path is not None
    replay = json.loads(replay_path.read_text(encoding="utf-8"))
    if not isinstance(replay, dict):
        raise TimelineEvaluationError("replay のJSONがオブジェクトではありません")
    return timeline_view_from_replay(replay)


def _motion_frames(path: Path | None, source: Mapping[str, Any]) -> list[Any] | None:
    """#169 60 fps engagement frames, only for the timeline's own source video."""
    if path is None:
        return None
    from valorant_ai_coach.rules.engagement_motion import load_motion_frames

    first = next(
        (line for line in path.read_text(encoding="utf-8").splitlines() if line.strip()), None
    )
    sha = None if first is None else (json.loads(first).get("sample") or {}).get("source_sha256")
    if not sha or sha != source.get("source_sha256"):
        raise TimelineEvaluationError(
            "交戦区間フレームと共通タイムラインの元動画（SHA-256）が一致しません"
        )
    return load_motion_frames(path)


def openai_coach(model: str) -> RoundCoach:
    """The production API coach for the bridge (needs OPENAI_API_KEY or the stored key)."""
    from valorant_ai_coach.ai.coach import OpenAICoach
    from valorant_ai_coach.settings import SettingsStore

    api_key = os.environ.get("OPENAI_API_KEY") or SettingsStore().get_api_key()
    if not api_key:
        raise TimelineEvaluationError("--coach openai にはOpenAI APIキーが必要です")
    rules = json.loads(
        Path(_resource("config/valorant_evaluation_rules_v4.json")).read_text(encoding="utf-8")
    )
    return OpenAICoach(
        api_key=api_key,
        model=model,
        rules_by_id={item["id"]: item for item in rules["rules"]},
        validator=SchemaValidator(),
    )


def run(
    *,
    timeline_path: Path | None,
    output: Path,
    match_id: str,
    database: Path | None = None,
    source_video_path: Path | None = None,
    derived_samples: Path | None = None,
    replace_development: bool = False,
    replay_path: Path | None = None,
    promote: bool = True,
    promotion_policy: Path | None = None,
    coach: RoundCoach | None = None,
    second_features_path: Path | None = None,
    development_map_path: Path | None = None,
    engagement_motion_path: Path | None = None,
    ammo_path: Path | None = None,
) -> dict[str, Any]:
    bundle = load_bundle(timeline_path, replay_path)
    _require_development_bundle(bundle)
    if output.exists():
        raise TimelineEvaluationError("新しい出力ディレクトリを指定してください")
    development_map = None
    if development_map_path is not None:
        if timeline_path is None:
            raise TimelineEvaluationError("開発用Mapレポートには対応する --timeline が必要です")
        from valorant_ai_coach.temporal.map_timeline_report import load_map_timeline

        development_map = load_map_timeline(development_map_path, timeline_path, bundle)
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
        loaded = json.loads(derived_samples.read_text(encoding="utf-8"))
        # Either the bare list of samples or {"meta": ..., "samples": [...]}.
        provider = DerivedSampleFactProvider(
            loaded["samples"] if isinstance(loaded, Mapping) else loaded
        )
    promoter = None
    if promote:
        from valorant_ai_coach.facts.timeline_promotion import PromotionPolicy

        promoter = TimelinePromoter(PromotionPolicy.load(promotion_policy))
    features = None
    if second_features_path is not None:
        features = (
            load_records(second_features_path, ammo_path),
            records_source_sha256(second_features_path),
        )
    evaluation = evaluate_timeline(
        bundle,
        match_id=match_id,
        source_video=source_video,
        analyzer=default_round_analyzer(coach=coach),
        fact_provider=provider,
        promoter=promoter,
        second_features=features,
        frame_refs=load_frame_refs(second_features_path) if second_features_path else None,
        motion_frames=_motion_frames(engagement_motion_path, source),
    )
    stored_view = None
    if database is not None:
        stored_view = persist_evaluation(
            SQLiteRepository(database),
            evaluation,
            source_video_path=source_video_path or timeline_path or replay_path or output,
            source=source,
            replace_development=replace_development,
        )
    consistency = check_consistency(evaluation, stored_view)
    report = build_report(
        evaluation, source=source, consistency=consistency, stored=database is not None
    )
    if development_map is not None:
        from valorant_ai_coach.temporal.map_timeline_report import summarize_map_seconds

        map_rows = development_map["rows"]
        report["development_map"] = {
            "qualification": "development_only",
            "formal_outputs": 0,
            "summary": development_map["summary"],
            "round_windows": [
                {"round_no": round_.round_no, "boundary_confirmed": round_.confirmed,
                 **summarize_map_seconds([
                     map_rows[timestamp] for timestamp in range(round_.start_sec, round_.end_sec)
                     if bundle["seconds"][timestamp]["round_number"]["value"] == round_.round_no
                 ])}
                for round_ in evaluation.rounds
            ],
        }
    if evaluation.promotion is not None:
        report["independent_signal_checks"] = verify_promotion(bundle, evaluation.promotion)
    report["fact_provider"] = None if provider is None else {
        "name": provider.SOURCE,
        "samples": len(provider.samples),
        "unsupported_event_types": dict(sorted(provider.unsupported_events.items())),
    }
    report["input"] = {
        "kind": "replay_projection" if replay_path is not None else "application_bundle",
        "projection": bundle.get("projection"),
        "coach": type(coach).__name__ if coach is not None else "MissingFactAbstentionCoach(Mock)",
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
    evaluate.add_argument("--timeline", type=Path, help="application bundle (.json / .json.gz)")
    evaluate.add_argument("--replay", type=Path,
                          help="replay の events_and_states JSON（HUD値なしの射影）")
    evaluate.add_argument("--output", type=Path, required=True)
    evaluate.add_argument("--match-id", required=True)
    evaluate.add_argument("--database", type=Path)
    evaluate.add_argument("--source-video", type=Path)
    evaluate.add_argument("--derived-samples", type=Path,
                          help="#155 development_readiness.derive の出力（JSON）")
    evaluate.add_argument("--replace-development", action="store_true")
    evaluate.add_argument("--no-promotion", action="store_true",
                          help="正式昇格を行わず、従来どおり全Roundを暫定境界のまま通す")
    evaluate.add_argument("--promotion-policy", type=Path,
                          help="config/timeline_promotion_v1.json の代替")
    evaluate.add_argument("--second-features", type=Path,
                          help="#155 extract_second_features.py の出力（.jsonl / .jsonl.gz）")
    evaluate.add_argument("--ammo", type=Path,
                          help="#169 extract_second_features.py --ammo-only の出力（予備弾数）")
    evaluate.add_argument("--engagement-motion", type=Path,
                          help="#169 extract_engagement_motion.py の出力（初弾のフレーム特定）")
    evaluate.add_argument("--development-map-report", type=Path,
                          help="同じタイムラインから出力した開発用Map観測レポート")
    evaluate.add_argument("--coach", choices=("mock", "openai"), default="mock")
    evaluate.add_argument("--model", default="gpt-4o-mini", help="--coach openai のモデルID")
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
        replay_path=args.replay,
        promote=not args.no_promotion,
        promotion_policy=args.promotion_policy,
        coach=openai_coach(args.model) if args.coach == "openai" else None,
        second_features_path=args.second_features,
        development_map_path=args.development_map_report,
        engagement_motion_path=args.engagement_motion,
        ammo_path=args.ammo,
    )
    print(
        json.dumps(
            {
                "rounds_segmented": report["rounds_segmented"],
                "rounds_confirmed": report["formal_input_counts"]["rounds_confirmed"],
                "formal_events": report["formal_input_counts"]["formal_events"],
                "formal_facts": report["formal_input_counts"]["formal_facts_after_fact_builder"],
                "unsegmented_seconds": report["unsegmented_seconds"],
                "evaluation_counts": report["evaluation_counts"],
                "rules_with_output": report["rules_with_output"],
                "completeness": report["match_aggregation"]["completeness"]["status"],
                "consistency_problems": len(report["consistency_problems"]),
            },
            ensure_ascii=False,
        )
    )
    return 1 if report["consistency_problems"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
