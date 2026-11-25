"""Promote shared-timeline candidates to formal Round boundaries, Events and Facts.

The shared one-second timeline (``development_application_timeline_v1``) is the
single source of truth for Round phase, round number, recorder life and camera
state, HUD value candidates and transition candidates. Every row there is a
development candidate. Until this module, nothing turned those candidates into
the formal ``round_start`` / ``round_end`` / ``player_death`` / ``buy_phase`` /
``state_snapshot`` Events and the ``state_snapshots`` that ``RoundAnalyzer`` needs,
so the production evaluation path always received ``provisional`` boundaries and
withheld scoring (0 formal Events, 0 Facts, 0 evaluations).

This module adds the missing promotion step. It is deliberately conservative:

* It never recognises anything itself. It only reads the timeline's own per-second
  states, round-number candidates, HUD value candidates and transition candidates.
* A candidate is promoted only when the gate in ``config/timeline_promotion_v1.json``
  is met, and every promoted item carries the evidence it was promoted from
  (``evidence_refs``, the timeline candidate ids, the bracket of seconds).
* Everything that fails a gate is counted with a reason code in the promotion
  report. Nothing is filled in, interpolated or guessed.
* The promoted items are labelled ``qualification: promoted_from_shared_timeline``.
  They are formal inputs for the evaluation path, but they are still produced from
  DEVELOPMENT recordings: the confidence values are policy constants calibrated on
  development recordings and are not independent qualification results.
"""

from __future__ import annotations

import json
import math
from collections import Counter
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from fractions import Fraction
from pathlib import Path
from statistics import median
from typing import Any

from valorant_ai_coach.events.source_contract import EventSourceContract, Producer
from valorant_ai_coach.knowledge import GameKnowledge, load_game_knowledge
from valorant_ai_coach.resources import resource_path

VERSION = "timeline_formal_promotion_v1"
FORMAL_QUALIFICATION = "promoted_from_shared_timeline"
EVENT_ID_PREFIX = "tl-"
_OBSERVED = "OBSERVED"
_ROUND_BREAKS = frozenset({"ENDED", "INTERMISSION"})
# Snapshot fields that carry a per-field source confidence in round_package_schema_v2
# (hp/armor have no such slot; their reading confidence is kept on the Event).
_SOURCE_CONFIDENCE_FIELDS = frozenset({
    "ally_alive", "enemy_alive", "weapon", "spike_state", "round_time_remaining_sec",
    "utility_available_count", "player_location", "spatial_context",
    "score_ally", "score_enemy",
})
_EVENT_PRODUCERS: Mapping[str, Producer] = {
    "round_start": "hud_analyzer",
    "round_end": "hud_analyzer",
    "player_death": "hud_analyzer",
    "buy_phase": "hud_analyzer",
    "state_snapshot": "derived_event_builder",
}


class PromotionError(ValueError):
    """The timeline cannot be promoted without inventing data."""


# ----------------------------------------------------------------------- policy


@dataclass(frozen=True, slots=True)
class PromotionPolicy:
    max_start_bracket_sec: float
    max_end_bracket_sec: float
    boundary_state_lookup_sec: int
    competing_candidate_merge_sec: float
    no_buy_after_start_sec: int
    max_buy_lookback_sec: int
    max_end_search_after_segment_sec: int
    max_ended_tail_sec: int
    boundary_confidence: float
    death_max_prior_self_gap_sec: int
    death_corroboration_window_sec: int
    death_sustained_spectator_window_sec: int
    death_min_sustained_spectator_observed_sec: int
    death_confidence: float
    buy_min_observed_seconds: int
    buy_confidence: float
    snapshot_min_field_confidence: float
    snapshot_min_interval_sec: int
    hp_range: tuple[int, int]
    armor_range: tuple[int, int]
    score_range: tuple[int, int]
    source_sha256: str = ""

    @classmethod
    def load(cls, path: Path | None = None) -> PromotionPolicy:
        source = path or resource_path("config/timeline_promotion_v1.json")
        raw = json.loads(Path(source).read_text(encoding="utf-8"))
        if raw.get("version") != VERSION:
            raise PromotionError("timeline_promotion_v1.json のversionが一致しません")
        boundary, death = raw["round_boundary"], raw["player_death"]
        buy, snapshot = raw["buy_phase"], raw["state_snapshot"]
        policy = cls(
            max_start_bracket_sec=float(boundary["max_start_bracket_sec"]),
            max_end_bracket_sec=float(boundary["max_end_bracket_sec"]),
            boundary_state_lookup_sec=int(boundary["boundary_state_lookup_sec"]),
            competing_candidate_merge_sec=float(boundary["competing_candidate_merge_sec"]),
            no_buy_after_start_sec=int(boundary["no_buy_after_start_sec"]),
            max_buy_lookback_sec=int(boundary["max_buy_lookback_sec"]),
            max_end_search_after_segment_sec=int(boundary["max_end_search_after_segment_sec"]),
            max_ended_tail_sec=int(boundary["max_ended_tail_sec"]),
            boundary_confidence=float(boundary["confidence"]),
            death_max_prior_self_gap_sec=int(death["max_prior_self_gap_sec"]),
            death_corroboration_window_sec=int(death["corroboration_window_sec"]),
            death_sustained_spectator_window_sec=int(death["sustained_spectator_window_sec"]),
            death_min_sustained_spectator_observed_sec=int(
                death["min_sustained_spectator_observed_sec"]
            ),
            death_confidence=float(death["confidence"]),
            buy_min_observed_seconds=int(buy["min_observed_buy_seconds"]),
            buy_confidence=float(buy["confidence"]),
            snapshot_min_field_confidence=float(snapshot["min_field_confidence"]),
            snapshot_min_interval_sec=int(snapshot["min_interval_sec"]),
            hp_range=(int(snapshot["hp_range"][0]), int(snapshot["hp_range"][1])),
            armor_range=(int(snapshot["armor_range"][0]), int(snapshot["armor_range"][1])),
            score_range=(int(snapshot["score_range"][0]), int(snapshot["score_range"][1])),
            source_sha256=_sha256_of(Path(source)),
        )
        for name in ("boundary_confidence", "death_confidence", "buy_confidence",
                     "snapshot_min_field_confidence"):
            value = getattr(policy, name)
            if not 0.0 < value <= 1.0:
                raise PromotionError(f"{name} は (0, 1] の範囲で指定してください")
        return policy


def _sha256_of(path: Path) -> str:
    import hashlib

    return hashlib.sha256(path.read_bytes()).hexdigest()


# -------------------------------------------------------------- timeline view


@dataclass(frozen=True, slots=True)
class SecondView:
    """The fields of one shared-timeline second this module reads."""

    index: int
    observed: bool
    round_value: str
    round_status: str
    round_no: int | None
    round_candidates: tuple[int, ...]
    life_value: str
    life_status: str
    camera_value: str
    camera_status: str
    evidence_refs: tuple[str, ...]
    hud: Mapping[str, Sequence[Mapping[str, Any]]]
    event_candidates: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class TransitionView:
    """One transition candidate of the shared engine, in recording seconds."""

    event_id: str
    kind: str
    lower: float
    upper: float
    before: str | None
    after: str | None
    membership: tuple[int, ...]
    membership_status: str
    evidence_refs: tuple[str, ...]

    @property
    def bracket(self) -> float:
        return self.upper - self.lower

    @property
    def upper_second(self) -> int:
        return int(math.floor(self.upper))

    @property
    def lower_second(self) -> int:
        return int(math.floor(self.lower))


def _state(row: Mapping[str, Any], domain: str) -> tuple[str, str]:
    state = row.get(domain)
    if not isinstance(state, Mapping):
        return "UNKNOWN", "UNKNOWN"
    return str(state.get("value", "UNKNOWN")), str(state.get("status", "UNKNOWN"))


def _round_number(row: Mapping[str, Any]) -> tuple[int | None, tuple[int, ...]]:
    summary = row.get("round_number")
    if not isinstance(summary, Mapping):
        return None, ()
    candidates = tuple(
        int(v) for v in summary.get("candidates", [])
        if isinstance(v, int) and not isinstance(v, bool) and v > 0
    )
    value = summary.get("value")
    if (
        summary.get("status") != "CANDIDATE"
        or isinstance(value, bool)
        or not isinstance(value, int)
        or value < 1
    ):
        return None, candidates
    return value, candidates


class TimelineView:
    """Read-only, validated view over an application bundle's seconds and events."""

    def __init__(self, bundle: Mapping[str, Any]) -> None:
        rows = bundle.get("seconds")
        if not isinstance(rows, list) or not rows:
            raise PromotionError("共通タイムラインのsecondsが空です")
        self.seconds: list[SecondView] = []
        for index, row in enumerate(rows):
            stamp = row.get("timestamp", index)
            if isinstance(stamp, bool) or not isinstance(stamp, int | float) or stamp != index:
                raise PromotionError("秒行のtimestampが行番号と一致しません")
            round_value, round_status = _state(row, "round_state")
            life_value, life_status = _state(row, "life_state")
            camera_value, camera_status = _state(row, "camera_state")
            round_no, candidates = _round_number(row)
            hud_raw = row.get("hud_observations")
            hud: dict[str, Sequence[Mapping[str, Any]]] = {}
            if isinstance(hud_raw, Mapping):
                for key, value in hud_raw.items():
                    if isinstance(value, Mapping) and isinstance(value.get("candidates"), list):
                        hud[str(key)] = [c for c in value["candidates"] if isinstance(c, Mapping)]
            self.seconds.append(
                SecondView(
                    index=index,
                    observed=bool(row.get("observation_present", False)),
                    round_value=round_value,
                    round_status=round_status,
                    round_no=round_no,
                    round_candidates=candidates,
                    life_value=life_value,
                    life_status=life_status,
                    camera_value=camera_value,
                    camera_status=camera_status,
                    evidence_refs=tuple(str(r) for r in row.get("evidence_refs", [])),
                    hud=hud,
                    event_candidates=tuple(str(e) for e in row.get("event_candidates", [])),
                )
            )
        self.transitions: list[TransitionView] = []
        events = bundle.get("events")
        if isinstance(events, Mapping):
            for event_id, event in events.items():
                if not isinstance(event, Mapping):
                    continue
                lower, upper = event.get("lower_timestamp"), event.get("upper_timestamp")
                if not (
                    isinstance(lower, int | float) and isinstance(upper, int | float)
                    and not isinstance(lower, bool) and not isinstance(upper, bool)
                    and math.isfinite(lower) and math.isfinite(upper)
                ):
                    continue
                native = event.get("native_transition")
                before = after = None
                if isinstance(native, Mapping):
                    before = str(native["before"]) if native.get("before") is not None else None
                    after = str(native["after"]) if native.get("after") is not None else None
                membership = event.get("round_membership")
                if not isinstance(membership, Mapping) and isinstance(native, Mapping):
                    membership = native.get("round_membership")
                members: tuple[int, ...] = ()
                status = "UNKNOWN"
                if isinstance(membership, Mapping):
                    members = tuple(
                        int(v) for v in membership.get("candidates", [])
                        if isinstance(v, int) and not isinstance(v, bool)
                    )
                    status = str(membership.get("status", "UNKNOWN"))
                self.transitions.append(
                    TransitionView(
                        event_id=str(event_id),
                        kind=str(event.get("kind", "")),
                        lower=float(lower),
                        upper=float(upper),
                        before=before,
                        after=after,
                        membership=members,
                        membership_status=status,
                        evidence_refs=tuple(str(r) for r in event.get("evidence_refs", [])),
                    )
                )
        self.transitions.sort(key=lambda t: (t.upper, t.lower, t.event_id))

    def __len__(self) -> int:
        return len(self.seconds)

    def row(self, index: int) -> SecondView | None:
        return self.seconds[index] if 0 <= index < len(self.seconds) else None


def timeline_view_from_replay(replay: Mapping[str, Any]) -> dict[str, Any]:
    """Project a replay export (``events_and_states``) into the bundle shape.

    The replay harness stores the shared engine's native per-sample states and
    transition candidates without the HUD value suppliers. This projection bins the
    engine's own states by recording second with the same functions the application
    bundle uses (``_state`` / ``round_number_summary`` of ``temporal.application``), so
    it yields Round boundaries, deaths and buy phases but no HUD value snapshots.
    It introduces no new state logic.
    """
    from valorant_ai_coach.temporal.application import _state as application_state
    from valorant_ai_coach.temporal.evidence import native_time
    from valorant_ai_coach.temporal.game import round_number_summary

    if replay.get("formal_outputs") != 0:
        raise PromotionError("formal_outputs=0 の replay が必要です")
    states = replay.get("native_states")
    events = replay.get("events")
    if not isinstance(states, list) or not states or not isinstance(events, list):
        raise PromotionError("replay に native_states / events が必要です")
    # Recording origin: the events carry recording seconds next to native samples.
    origin: Fraction | None = None
    for event in events:
        stamp = event.get("lower_timestamp")
        sample = event.get("lower_sample")
        if isinstance(stamp, int | float) and isinstance(sample, dict):
            origin = native_time(sample) - Fraction(str(stamp))
            break
    if origin is None:
        origin = min(native_time(s["sample"]) for s in states)
    times = [native_time(s["sample"]) - origin for s in states]
    duration = max(times) + 1
    bins: dict[int, list[dict[str, Any]]] = {}
    for state, when in zip(states, times, strict=True):
        second = int(when // 1)
        if second < 0:
            raise PromotionError("replay のサンプルが録画開始より前です")
        bins.setdefault(second, []).append(dict(state))
    seconds: list[dict[str, Any]] = []
    total = int(math.ceil(duration))
    bundle_events: dict[str, dict[str, Any]] = {}
    event_bins: dict[int, list[str]] = {}
    for index, event in enumerate(events):
        lower, upper = event.get("lower_timestamp"), event.get("upper_timestamp")
        if not isinstance(lower, int | float) or not isinstance(upper, int | float):
            continue
        event_id = f"replay-{index:05d}"
        domain = {"round_start": "round", "round_end": "round", "spectator": "camera",
                  "death": "life", "return": "life"}.get(str(event.get("kind")), "round")
        endpoints = event.get("endpoint_states") or [{}, {}]
        before = str(endpoints[0].get(domain) or "UNKNOWN")
        after = str(endpoints[-1].get(domain) or "UNKNOWN")
        bundle_events[event_id] = {
            "kind": event.get("kind"),
            "status": "CANDIDATE",
            "lower_timestamp": float(lower),
            "upper_timestamp": float(upper),
            "native_transition": {
                "before": None if before == "UNKNOWN" else before,
                "after": None if after == "UNKNOWN" else after,
            },
            "round_membership": event.get("round_membership"),
            "evidence_refs": [],
            "qualified": False,
        }
        for second in range(max(0, int(lower // 1)), min(total, int(upper // 1) + 1)):
            event_bins.setdefault(second, []).append(event_id)
    for second in range(total):
        frames = sorted(bins.get(second, []), key=lambda f: native_time(f["sample"]))
        seconds.append(
            {
                "timestamp": second,
                "observation_present": bool(frames),
                "round_state": application_state(frames, "round") if frames
                else {"value": "UNKNOWN", "status": "UNKNOWN", "evidence_refs": []},
                "round_number": round_number_summary([f["round_number"] for f in frames]),
                "life_state": application_state(frames, "life") if frames
                else {"value": "UNKNOWN", "status": "UNKNOWN", "evidence_refs": []},
                "camera_state": application_state(frames, "camera") if frames
                else {"value": "UNKNOWN", "status": "UNKNOWN", "evidence_refs": []},
                "hud_observations": {},
                "event_candidates": list(dict.fromkeys(event_bins.get(second, []))),
                "evidence_refs": sorted({r for f in frames for r in f.get("observation_ids", [])}),
            }
        )
    first = states[0]["sample"]
    return {
        "version": "development_application_timeline_v1",
        "qualification": "development_only",
        "formal_outputs": 0,
        "projection": "replay_events_and_states_without_hud_values",
        "source": {
            "source_id": first.get("source_id"),
            "source_sha256": first.get("source_sha256"),
            "physical_match_id": replay.get("physical_match_id") or first.get("source_id"),
        },
        "recording": {"duration_seconds": str(duration), "end_timestamp": float(duration)},
        "seconds": seconds,
        "events": bundle_events,
    }


# --------------------------------------------------------------- promotion data


@dataclass(frozen=True, slots=True)
class PromotedBoundary:
    kind: str
    time_sec: int
    bracket: tuple[float, float]
    candidate_id: str | None
    basis: str
    evidence_refs: tuple[str, ...]


@dataclass(slots=True)
class RoundPromotion:
    """Everything promoted for one Round, with the abstentions explained."""

    round_no: int
    segment: tuple[int, int]
    start: PromotedBoundary | None = None
    end: PromotedBoundary | None = None
    window: tuple[int, int] | None = None
    events: list[dict[str, Any]] = field(default_factory=list)
    snapshots: list[dict[str, Any]] = field(default_factory=list)
    round_meta: dict[str, Any] = field(default_factory=dict)
    abstentions: Counter[str] = field(default_factory=Counter)
    rejected: Counter[str] = field(default_factory=Counter)

    @property
    def confirmed(self) -> bool:
        return self.start is not None and self.end is not None and self.window is not None


@dataclass(frozen=True, slots=True)
class PromotionResult:
    rounds: tuple[RoundPromotion, ...]
    policy: PromotionPolicy

    def report(self) -> dict[str, Any]:
        kinds: Counter[str] = Counter()
        abstentions: Counter[str] = Counter()
        rejected: Counter[str] = Counter()
        for item in self.rounds:
            kinds.update(str(event["type"]) for event in item.events)
            abstentions.update(item.abstentions)
            rejected.update(item.rejected)
        return {
            "version": VERSION,
            "qualification": FORMAL_QUALIFICATION,
            "policy_sha256": self.policy.source_sha256,
            "rounds_total": len(self.rounds),
            "rounds_confirmed": sum(1 for r in self.rounds if r.confirmed),
            "rounds_start_only": sum(
                1 for r in self.rounds if r.start is not None and r.end is None
            ),
            "rounds_end_only": sum(
                1 for r in self.rounds if r.end is not None and r.start is None
            ),
            "formal_events": sum(len(r.events) for r in self.rounds),
            "formal_event_counts": dict(sorted(kinds.items())),
            "state_snapshots": sum(len(r.snapshots) for r in self.rounds),
            "round_results": dict(sorted(Counter(
                str(r.round_meta.get("round_result", "unknown")) for r in self.rounds
            ).items())),
            "abstentions": dict(sorted(abstentions.items())),
            "rejected_candidates": dict(sorted(rejected.items())),
            "rounds": [
                {
                    "round_no": r.round_no,
                    "segment": list(r.segment),
                    "window": list(r.window) if r.window else None,
                    "start": _boundary_dict(r.start),
                    "end": _boundary_dict(r.end),
                    "events": dict(sorted(Counter(str(e["type"]) for e in r.events).items())),
                    "state_snapshots": len(r.snapshots),
                    "round_result": r.round_meta.get("round_result"),
                    "score_before": r.round_meta.get("score_before"),
                    "abstentions": dict(sorted(r.abstentions.items())),
                    "rejected_candidates": dict(sorted(r.rejected.items())),
                }
                for r in self.rounds
            ],
        }


def _boundary_dict(boundary: PromotedBoundary | None) -> dict[str, Any] | None:
    if boundary is None:
        return None
    return {
        "time_sec": boundary.time_sec,
        "bracket": list(boundary.bracket),
        "basis": boundary.basis,
        "candidate_id": boundary.candidate_id,
    }


# ------------------------------------------------------------------- promoter


class TimelinePromoter:
    """Apply the promotion gates to one application bundle."""

    def __init__(
        self,
        policy: PromotionPolicy | None = None,
        *,
        source_contract: EventSourceContract | None = None,
        knowledge: GameKnowledge | None = None,
    ) -> None:
        self.policy = policy or PromotionPolicy.load()
        # Weapon names are resolved by the shared game knowledge base (#96), in any
        # language it carries; an unresolved HUD reading is rejected, never guessed.
        self.knowledge = knowledge or load_game_knowledge()
        # Same formula as game_rules_v1 derived_bounds.max_round_duration_sec.
        self.max_round_duration_sec = int(
            self.knowledge.rule("round_time_limit_sec")
            + self.knowledge.rule("spike_detonation_sec")
            + self.knowledge.rule("spike_plant_sec")
        )
        self.contract = source_contract or EventSourceContract.load(
            resource_path("config/event_source_contract_v1.json")
        )

    # -- entry point --------------------------------------------------------

    def promote(
        self, bundle: Mapping[str, Any], segments: Sequence[tuple[int, int, int]]
    ) -> PromotionResult:
        """``segments`` are ``(round_no, start_sec, end_sec)`` from the bridge's segmentation."""
        view = TimelineView(bundle)
        ordered = sorted(segments, key=lambda s: s[1])
        numbers = [s[0] for s in ordered]
        if len(set(numbers)) != len(numbers):
            raise PromotionError("Round番号が重複しています")
        rounds: list[RoundPromotion] = []
        previous_end = 0
        for position, (round_no, seg_start, seg_end) in enumerate(ordered):
            next_start = ordered[position + 1][1] if position + 1 < len(ordered) else len(view)
            # Never search before the previous Round's own segment ended, even when
            # that Round was not confirmed: a candidate there belongs to it, not here.
            previous_end = max(previous_end, ordered[position - 1][2] if position else 0)
            item = RoundPromotion(round_no=round_no, segment=(seg_start, seg_end))
            item.start = self._promote_start(view, item, seg_start, seg_end, previous_end)
            item.end = self._promote_end(view, item, seg_start, seg_end, next_start)
            if item.start is not None and item.end is not None:
                if item.end.time_sec <= item.start.time_sec:
                    item.abstentions["end_not_after_start"] += 1
                    item.start = item.end = None
                else:
                    item.window = self._window(view, item, previous_end, next_start)
            if item.confirmed:
                assert item.window is not None and item.start is not None and item.end is not None
                previous_end = item.window[1]
                self._emit_boundaries(item)
                self._promote_buy_phase(view, item)
                self._promote_deaths(view, item)
                self._promote_snapshots(view, item)
                item.round_meta = self._round_meta(view, item)
                for event in item.events:
                    self.contract.validate_event(event, _EVENT_PRODUCERS[str(event["type"])])
            else:
                item.round_meta = {"round_result": "unknown", "score_before": None}
            rounds.append(item)
        return PromotionResult(rounds=tuple(rounds), policy=self.policy)

    # -- Round boundaries ------------------------------------------------------

    def _transition_candidates(
        self, view: TimelineView, kind: str, round_no: int, low: int, high: int
    ) -> list[TransitionView]:
        """Transitions of ``kind`` whose upper second lies in [low, high] and whose
        round membership does not contradict ``round_no``."""
        found: list[TransitionView] = []
        for item in view.transitions:
            if item.kind != kind or not low <= item.upper_second <= high:
                continue
            if item.membership and round_no not in item.membership:
                continue
            found.append(item)
        return found

    def _state_near(
        self, view: TimelineView, second: int, domain: str, wanted: str, direction: int
    ) -> SecondView | None:
        """The first row at/after (direction=+1) or at/before (-1) ``second`` within the
        lookup budget whose ``domain`` value is ``wanted`` (observed or inferred)."""
        for offset in range(self.policy.boundary_state_lookup_sec + 1):
            row = view.row(second + direction * offset)
            if row is None:
                break
            value, status = {
                "round": (row.round_value, row.round_status),
                "life": (row.life_value, row.life_status),
                "camera": (row.camera_value, row.camera_status),
            }[domain]
            if value == wanted and status != "UNKNOWN":
                return row
        return None

    def _observed_round_near(
        self, view: TimelineView, second: int, direction: int
    ) -> SecondView | None:
        """The nearest row with an OBSERVED round phase, within the lookup budget."""
        for offset in range(self.policy.boundary_state_lookup_sec + 1):
            row = view.row(second + direction * offset)
            if row is None:
                break
            if row.round_status == _OBSERVED:
                return row
        return None

    def _select_candidate(
        self, candidates: list[TransitionView], item: RoundPromotion, label: str
    ) -> TransitionView | None:
        if not candidates:
            return None
        candidates = sorted(candidates, key=lambda c: (c.upper, c.bracket))
        first = candidates[0]
        competing = [
            c for c in candidates[1:]
            if c.upper - first.upper > self.policy.competing_candidate_merge_sec
        ]
        if competing:
            item.abstentions[f"{label}_competing_candidates"] += 1
            return None
        return first

    def _promote_start(
        self, view: TimelineView, item: RoundPromotion, seg_start: int, seg_end: int,
        previous_end: int,
    ) -> PromotedBoundary | None:
        label = "round_start"
        candidates = self._transition_candidates(
            view, label, item.round_no, previous_end, seg_end - 1
        )
        admitted: list[TransitionView] = []
        for candidate in candidates:
            if candidate.bracket > self.policy.max_start_bracket_sec:
                item.rejected[f"{label}_bracket_too_wide"] += 1
                continue
            if candidate.after not in {None, "ACTIVE"} or candidate.before not in {None, "BUY"}:
                item.rejected[f"{label}_not_buy_to_active"] += 1
                continue
            # The nearest *observed* phase on each side must be BUY before and ACTIVE
            # after: an inferred one-second flicker inside the buy phase is not a start.
            active = self._observed_round_near(view, candidate.upper_second, +1)
            buy = self._observed_round_near(view, candidate.lower_second, -1)
            if (
                active is None or buy is None
                or active.round_value != "ACTIVE" or buy.round_value != "BUY"
            ):
                item.rejected[f"{label}_phase_not_corroborated"] += 1
                continue
            if any(
                row.round_value == "BUY" and row.round_status == _OBSERVED
                and row.round_no in {None, item.round_no}
                for row in view.seconds[
                    candidate.upper_second + 1:
                    candidate.upper_second + 1 + self.policy.no_buy_after_start_sec
                ]
            ):
                item.rejected[f"{label}_buy_observed_after_start"] += 1
                continue
            if buy.round_no not in {None, item.round_no} or active.round_no not in {
                None, item.round_no
            }:
                item.rejected[f"{label}_round_number_mismatch"] += 1
                continue
            admitted.append(candidate)
        if not candidates:
            # The shared engine emitted no transition here; fall back to its own
            # per-second states when both endpoints were observed (never inferred).
            pair = self._observed_state_pair(
                view, item, "BUY", "ACTIVE", previous_end, seg_end - 1,
                self.policy.max_start_bracket_sec,
            )
            if pair is not None:
                return PromotedBoundary(
                    kind=label,
                    time_sec=pair[1].index,
                    bracket=(float(pair[0].index), float(pair[1].index)),
                    candidate_id=None,
                    basis="shared_timeline_observed_state_pair_buy_to_active",
                    evidence_refs=tuple(
                        dict.fromkeys([*pair[0].evidence_refs, *pair[1].evidence_refs])
                    ),
                )
        chosen = self._select_candidate(admitted, item, label)
        if chosen is None:
            if not admitted:
                item.abstentions[f"{label}_no_admitted_candidate"] += 1
            return None
        return PromotedBoundary(
            kind=label,
            time_sec=chosen.upper_second,
            bracket=(chosen.lower, chosen.upper),
            candidate_id=chosen.event_id,
            basis="shared_timeline_transition_buy_to_active_with_observed_phase",
            evidence_refs=chosen.evidence_refs,
        )

    def _promote_end(
        self, view: TimelineView, item: RoundPromotion, seg_start: int, seg_end: int,
        next_start: int,
    ) -> PromotedBoundary | None:
        label = "round_end"
        # After the recorder dies the round number is often unreadable until the
        # result display, so the end is searched past the segment, bounded by the
        # next Round and the cap; the gap must not show another Round (below).
        if item.start is not None:
            # A combat phase cannot outlast the game's own limit (#96 game rules).
            cap = item.start.time_sec + self.max_round_duration_sec + math.ceil(
                self.policy.max_end_bracket_sec
            )
        else:
            cap = seg_end - 1 + self.policy.max_end_search_after_segment_sec
        high = min(next_start - 1, cap, len(view) - 1)
        candidates = self._transition_candidates(view, label, item.round_no, seg_start, high)
        admitted: list[TransitionView] = []
        for candidate in candidates:
            if candidate.bracket > self.policy.max_end_bracket_sec:
                item.rejected[f"{label}_bracket_too_wide"] += 1
                continue
            if candidate.after not in {None, "ENDED"}:
                item.rejected[f"{label}_not_to_ended"] += 1
                continue
            ended = self._state_near(view, candidate.upper_second, "round", "ENDED", +1)
            if ended is None:
                item.rejected[f"{label}_phase_not_corroborated"] += 1
                continue
            if ended.round_no not in {None, item.round_no}:
                item.rejected[f"{label}_round_number_mismatch"] += 1
                continue
            if self._other_round_in_gap(view, item.round_no, seg_end, candidate.lower_second):
                item.rejected[f"{label}_other_round_in_gap"] += 1
                continue
            # The end must come after some ACTIVE play of this Round.
            active_before = any(
                row.round_value == "ACTIVE" and row.round_status != "UNKNOWN"
                for row in view.seconds[seg_start:candidate.upper_second]
            )
            if not active_before:
                item.rejected[f"{label}_no_active_before"] += 1
                continue
            admitted.append(candidate)
        if not candidates:
            pair = self._observed_state_pair(
                view, item, "ACTIVE", "ENDED", seg_start, high,
                self.policy.max_end_bracket_sec,
            )
            if pair is not None and not self._other_round_in_gap(
                view, item.round_no, seg_end, pair[0].index
            ):
                return PromotedBoundary(
                    kind=label,
                    time_sec=pair[1].index,
                    bracket=(float(pair[0].index), float(pair[1].index)),
                    candidate_id=None,
                    basis="shared_timeline_observed_state_pair_active_to_ended",
                    evidence_refs=tuple(
                        dict.fromkeys([*pair[0].evidence_refs, *pair[1].evidence_refs])
                    ),
                )
        chosen = self._select_candidate(admitted, item, label)
        if chosen is None:
            if not admitted:
                item.abstentions[f"{label}_no_admitted_candidate"] += 1
            return None
        return PromotedBoundary(
            kind=label,
            time_sec=chosen.upper_second,
            bracket=(chosen.lower, chosen.upper),
            candidate_id=chosen.event_id,
            basis="shared_timeline_transition_to_ended_with_observed_phase",
            evidence_refs=chosen.evidence_refs,
        )

    def _observed_state_pair(
        self, view: TimelineView, item: RoundPromotion, before: str, after: str,
        low: int, high: int, max_bracket: float,
    ) -> tuple[SecondView, SecondView] | None:
        """First observed ``before`` -> observed ``after`` step of this Round in
        [low, high] with only unresolved seconds between, at most ``max_bracket``
        apart. At least one endpoint must read this Round's number, and neither may
        read another. Two or more such steps are competing evidence: abstain."""
        pairs: list[tuple[SecondView, SecondView]] = []
        last_before: SecondView | None = None
        for row in view.seconds[max(0, low):min(len(view), high + 1)]:
            if row.round_status == _OBSERVED and row.round_value == before:
                last_before = row
                continue
            if row.round_status == _OBSERVED and row.round_value == after:
                if (
                    last_before is not None
                    and row.index - last_before.index <= max_bracket
                    and {last_before.round_no, row.round_no} <= {None, item.round_no}
                    and item.round_no in {last_before.round_no, row.round_no}
                ):
                    pairs.append((last_before, row))
                last_before = None
                continue
            # Unresolved seconds and inferred continuations of ``before`` keep the
            # observed endpoint (the bracket still runs from the observed second).
            if row.round_value not in {"UNKNOWN", before}:
                last_before = None
        if len(pairs) > 1:
            item.abstentions[f"{before.lower()}_to_{after.lower()}_competing_state_pairs"] += 1
            return None
        return pairs[0] if pairs else None

    @staticmethod
    def _other_round_in_gap(view: TimelineView, round_no: int, low: int, high: int) -> bool:
        """Whether any second in [low, high) shows another Round or an observed buy phase."""
        for row in view.seconds[max(0, low):max(0, high)]:
            if row.round_no not in {None, round_no}:
                return True
            if row.round_value == "BUY" and row.round_status == _OBSERVED:
                return True
        return False

    def _window(
        self, view: TimelineView, item: RoundPromotion, previous_end: int, next_start: int
    ) -> tuple[int, int] | None:
        assert item.start is not None and item.end is not None
        start = item.start.time_sec
        # Walk back over the buy phase: BUY or unresolved seconds that carry no other
        # Round's number, never past the previous Round's window or the lookback cap.
        while start - 1 >= previous_end and item.start.time_sec - (start - 1) <= (
            self.policy.max_buy_lookback_sec
        ):
            row = view.row(start - 1)
            if row is None:
                break
            if row.round_value not in {"BUY", "UNKNOWN"}:
                break
            if row.round_no not in {None, item.round_no} or any(
                c != item.round_no for c in row.round_candidates
            ):
                break
            start -= 1
        end = item.end.time_sec + 1
        while end < next_start and end - item.end.time_sec <= self.policy.max_ended_tail_sec:
            row = view.row(end)
            if row is None or row.round_value != "ENDED":
                break
            if row.round_no not in {None, item.round_no}:
                break
            end += 1
        start = min(start, item.segment[0])
        if end < item.segment[1]:
            item.abstentions["segment_extends_past_round_end"] += 1
            return None
        if start >= end or start < previous_end or end > next_start:
            item.abstentions["window_conflict"] += 1
            return None
        return start, end

    def _emit_boundaries(self, item: RoundPromotion) -> None:
        assert item.start is not None and item.end is not None
        for boundary in (item.start, item.end):
            item.events.append(
                self._event(
                    boundary.kind,
                    item.round_no,
                    boundary.time_sec,
                    actor="system",
                    confidence=self.policy.boundary_confidence,
                    attributes={
                        "boundary_bracket_sec": list(boundary.bracket),
                        "promotion_rule": boundary.basis,
                    },
                    evidence_refs=boundary.evidence_refs,
                    candidate_ids=(boundary.candidate_id,) if boundary.candidate_id else (),
                )
            )

    # -- buy phase --------------------------------------------------------------

    def _promote_buy_phase(self, view: TimelineView, item: RoundPromotion) -> None:
        assert item.window is not None and item.start is not None
        rows = [
            row for row in view.seconds[item.window[0]:item.start.time_sec]
            if row.round_value == "BUY" and row.round_status == _OBSERVED
        ]
        if len(rows) < self.policy.buy_min_observed_seconds:
            item.abstentions["buy_phase_insufficient_observed_seconds"] += 1
            return
        first = rows[0]
        item.events.append(
            self._event(
                "buy_phase",
                item.round_no,
                first.index,
                actor="system",
                confidence=self.policy.buy_confidence,
                attributes={
                    "team_plan": None,
                    "observed_buy_seconds": len(rows),
                    "promotion_rule": "shared_timeline_observed_buy_phase_before_round_start",
                },
                evidence_refs=tuple(dict.fromkeys(r for row in rows for r in row.evidence_refs)),
            )
        )

    # -- recorder death -----------------------------------------------------------

    def _promote_deaths(self, view: TimelineView, item: RoundPromotion) -> None:
        assert item.window is not None and item.start is not None and item.end is not None
        low, high = item.start.time_sec, item.end.time_sec
        spectators = [
            t for t in view.transitions
            if t.kind == "spectator" and low < t.upper_second <= high
            and (not t.membership or item.round_no in t.membership)
        ]
        returns = [
            t for t in view.transitions
            if t.kind == "return" and low < t.upper_second <= high
        ]
        promoted_at: int | None = None
        for candidate in spectators:
            if candidate.after not in {None, "SPECTATOR"}:
                item.rejected["player_death_not_to_spectator"] += 1
                continue
            if promoted_at is not None and not any(
                promoted_at < r.upper_second <= candidate.upper_second for r in returns
            ):
                item.rejected["player_death_duplicate_spectator_in_round"] += 1
                continue
            spectating = self._state_near(view, candidate.upper_second, "camera", "SPECTATOR", +1)
            if spectating is None:
                item.rejected["player_death_camera_not_corroborated"] += 1
                continue
            prior = self._last_self_alive(view, candidate.lower_second, low)
            if prior is None:
                item.rejected["player_death_no_prior_self_alive"] += 1
                continue
            if not self._death_corroborated(view, candidate, high):
                item.rejected["player_death_life_not_corroborated"] += 1
                continue
            promoted_at = candidate.upper_second
            item.events.append(
                self._event(
                    "player_death",
                    item.round_no,
                    candidate.upper_second,
                    actor="player",
                    confidence=self.policy.death_confidence,
                    attributes={
                        "boundary_bracket_sec": [candidate.lower, candidate.upper],
                        "last_self_alive_sec": prior.index,
                        "promotion_rule": (
                            "shared_timeline_self_to_spectator_with_dead_life_corroboration"
                        ),
                        "evidence_provenance": {"elimination_coverage": "self_death_only"},
                    },
                    evidence_refs=tuple(dict.fromkeys(
                        [*candidate.evidence_refs, *prior.evidence_refs, *spectating.evidence_refs]
                    )),
                    candidate_ids=(candidate.event_id,),
                )
            )
        if promoted_at is None and spectators:
            item.abstentions["player_death_no_admitted_candidate"] += 1

    def _last_self_alive(
        self, view: TimelineView, second: int, floor: int
    ) -> SecondView | None:
        lowest = max(floor, second - self.policy.death_max_prior_self_gap_sec)
        for index in range(second, lowest - 1, -1):
            row = view.row(index)
            if row is None:
                break
            if (row.camera_value, row.camera_status) == ("SELF", _OBSERVED) and (
                row.life_value, row.life_status
            ) == ("ALIVE", _OBSERVED):
                return row
        return None

    def _death_corroborated(
        self, view: TimelineView, candidate: TransitionView, high: int
    ) -> bool:
        """SELF->SPECTATOR during live play is a death only if the switch is backed by
        a DEAD life state, the engine's own death hypothesis, or a sustained observed
        spectator view with no observed SELF view in between (in VALORANT the camera
        leaves the recorder's own view mid-Round only when the recorder dies)."""
        stop = min(high, candidate.upper_second + self.policy.death_corroboration_window_sec)
        for index in range(candidate.upper_second, stop + 1):
            row = view.row(index)
            if row is None:
                break
            if row.life_value in {"DEAD", "DOWNED"}:
                return True
            if row.camera_value == "SELF" and row.camera_status == _OBSERVED:
                break
        if any(
            t.kind in {"death", "death_hypothesis", "recorder_death"}
            and t.lower_second <= candidate.upper_second <= t.upper_second + 1
            for t in view.transitions
        ):
            return True
        observed = 0
        sustained_stop = min(
            high, candidate.upper_second + self.policy.death_sustained_spectator_window_sec
        )
        for index in range(candidate.upper_second, sustained_stop + 1):
            row = view.row(index)
            if row is None:
                break
            if row.camera_value == "SELF" and row.camera_status == _OBSERVED:
                return False
            if (row.camera_value, row.camera_status) == ("SPECTATOR", _OBSERVED):
                observed += 1
        return observed >= self.policy.death_min_sustained_spectator_observed_sec

    # -- HUD state snapshots -----------------------------------------------------------

    def _promote_snapshots(self, view: TimelineView, item: RoundPromotion) -> None:
        assert item.window is not None and item.start is not None and item.end is not None
        previous: dict[str, Any] | None = None
        previous_at = -10**9
        for row in view.seconds[item.window[0]:item.window[1]]:
            if (row.camera_value, row.camera_status) != ("SELF", _OBSERVED) or (
                row.life_value, row.life_status
            ) != ("ALIVE", _OBSERVED):
                continue
            fields, confidences, refs = self._snapshot_fields(row, item, in_active=(
                item.start.time_sec <= row.index < item.end.time_sec
            ))
            if not fields:
                continue
            stable = {k: v for k, v in fields.items() if k != "round_time_remaining_sec"}
            changed = previous is None or stable != previous
            if not changed and row.index - previous_at < self.policy.snapshot_min_interval_sec:
                continue
            snapshot: dict[str, Any] = {
                "time_sec": float(row.index),
                "ally_alive": None,
                "enemy_alive": None,
                "hp": fields.get("hp"),
                "armor": fields.get("armor"),
                "weapon": fields.get("weapon"),
                "spike_state": "unknown",
                "round_time_remaining_sec": fields.get("round_time_remaining_sec"),
                "utility_available_count": None,
                "player_location": {"zone_id": None, "zone_name": None},
                "known_enemy_locations": [],
                "spatial_context": {
                    "cover_available": None,
                    "escape_route_available": None,
                    "line_of_sight_state": "unknown",
                    "exposed_directions_count": None,
                    "view_target_zone_id": None,
                },
                "score_ally": fields.get("score_ally"),
                "score_enemy": fields.get("score_enemy"),
                "source_confidence": {
                    k: v for k, v in confidences.items() if k in _SOURCE_CONFIDENCE_FIELDS
                },
            }
            item.snapshots.append(snapshot)
            item.events.append(
                self._event(
                    "state_snapshot",
                    item.round_no,
                    row.index,
                    actor="system",
                    confidence=min(confidences.values()),
                    attributes={
                        "fields": sorted(fields),
                        "field_confidence": dict(sorted(confidences.items())),
                        "promotion_rule": (
                            "shared_timeline_hud_values_in_observed_self_alive_second"
                        ),
                    },
                    evidence_refs=refs,
                )
            )
            previous, previous_at = stable, row.index

    def _snapshot_fields(
        self, row: SecondView, item: RoundPromotion, *, in_active: bool
    ) -> tuple[dict[str, Any], dict[str, float], tuple[str, ...]]:
        fields: dict[str, Any] = {}
        confidences: dict[str, float] = {}
        refs: list[str] = []

        def candidate(name: str) -> tuple[Any, float, str] | None:
            items = row.hud.get(name, [])
            readings = [
                (c.get("value"), float(c["confidence"]), str(c.get("evidence_ref", "")))
                for c in items
                if isinstance(c.get("confidence"), int | float)
                and not isinstance(c.get("confidence"), bool)
                and float(c["confidence"]) >= self.policy.snapshot_min_field_confidence
            ]
            if not readings:
                return None
            values = {json.dumps(r[0], sort_keys=True, ensure_ascii=False) for r in readings}
            if len(values) != 1:
                item.rejected[f"snapshot_{name}_conflicting_readings"] += 1
                return None
            return min(readings, key=lambda r: r[1])

        def integer(value: Any, bounds: tuple[int, int]) -> int | None:
            text = str(value).strip() if value is not None else ""
            if not text.isascii() or not text.isdigit():
                return None
            number = int(text)
            return number if bounds[0] <= number <= bounds[1] else None

        hp = candidate("hp")
        if hp is not None:
            value = integer(hp[0], self.policy.hp_range)
            if value is None:
                item.rejected["snapshot_hp_out_of_range"] += 1
            else:
                fields["hp"], confidences["hp"] = value, hp[1]
                refs.append(hp[2])
        armor = candidate("armor")
        if armor is not None:
            value = integer(armor[0], self.policy.armor_range)
            if value is None:
                item.rejected["snapshot_armor_out_of_range"] += 1
            else:
                fields["armor"], confidences["armor"] = value, armor[1]
                refs.append(armor[2])
        weapon = candidate("weapon")
        if weapon is not None:
            resolved = self.knowledge.weapon(str(weapon[0]).strip())
            name = resolved.name if resolved is not None else None
            if name is None:
                item.rejected["snapshot_weapon_unmapped"] += 1
            else:
                fields["weapon"], confidences["weapon"] = name, weapon[1]
                refs.append(weapon[2])
        if in_active:
            timer = candidate("timer")
            if timer is not None:
                seconds = _clock_seconds(timer[0])
                if seconds is None:
                    item.rejected["snapshot_timer_unreadable"] += 1
                else:
                    fields["round_time_remaining_sec"] = seconds
                    confidences["round_time_remaining_sec"] = timer[1]
                    refs.append(timer[2])
        ally, enemy = candidate("ally_score"), candidate("enemy_score")
        if ally is not None and enemy is not None:
            a = integer(ally[0], self.policy.score_range)
            e = integer(enemy[0], self.policy.score_range)
            if a is None or e is None:
                item.rejected["snapshot_score_out_of_range"] += 1
            elif a + e != item.round_no - 1:
                item.rejected["snapshot_score_inconsistent_with_round"] += 1
            else:
                fields["score_ally"], fields["score_enemy"] = a, e
                confidences["score_ally"], confidences["score_enemy"] = ally[1], enemy[1]
                refs.extend([ally[2], enemy[2]])
        return fields, confidences, tuple(dict.fromkeys(r for r in refs if r))

    # -- round meta -------------------------------------------------------------------------

    def _round_meta(self, view: TimelineView, item: RoundPromotion) -> dict[str, Any]:
        assert item.window is not None and item.start is not None and item.end is not None
        before = self._consensus_score(
            view.seconds[item.window[0]:item.start.time_sec], item.round_no - 1
        )
        after = self._consensus_score(
            view.seconds[item.end.time_sec:item.window[1]], item.round_no
        )
        result = "unknown"
        if before is not None and after is not None:
            if after == (before[0] + 1, before[1]):
                result = "win"
            elif after == (before[0], before[1] + 1):
                result = "loss"
            else:
                item.rejected["round_result_score_step_inconsistent"] += 1
        else:
            item.abstentions["round_result_scores_unavailable"] += 1
        return {
            "round_result": result,
            "score_before": {"ally": before[0], "enemy": before[1]} if before else None,
        }

    def _consensus_score(
        self, rows: Iterable[SecondView], expected_sum: int
    ) -> tuple[int, int] | None:
        pairs: Counter[tuple[int, int]] = Counter()
        for row in rows:
            ally = [c for c in row.hud.get("ally_score", [])
                    if isinstance(c.get("confidence"), int | float)
                    and float(c["confidence"]) >= self.policy.snapshot_min_field_confidence]
            enemy = [c for c in row.hud.get("enemy_score", [])
                     if isinstance(c.get("confidence"), int | float)
                     and float(c["confidence"]) >= self.policy.snapshot_min_field_confidence]
            if len(ally) != 1 or len(enemy) != 1:
                continue
            a, e = str(ally[0].get("value")), str(enemy[0].get("value"))
            if not (a.isdigit() and e.isdigit()):
                continue
            pair = (int(a), int(e))
            if sum(pair) == expected_sum:
                pairs[pair] += 1
        if len(pairs) != 1:
            return None
        return next(iter(pairs))

    # -- event factory -------------------------------------------------------------------------

    @staticmethod
    def _event(
        kind: str,
        round_no: int,
        second: int,
        *,
        actor: str,
        confidence: float,
        attributes: Mapping[str, Any],
        evidence_refs: Sequence[str],
        candidate_ids: Sequence[str] = (),
    ) -> dict[str, Any]:
        return {
            "event_id": f"{EVENT_ID_PREFIX}{kind}-R{round_no}-{second}",
            "time_sec": float(second),
            "type": kind,
            "actor": actor,
            "attributes": {
                "qualification": FORMAL_QUALIFICATION,
                "producer": VERSION,
                **dict(attributes),
                "evidence_provenance": {
                    **dict(attributes.get("evidence_provenance", {})),
                    "source": "shared_timeline",
                    "evidence_refs": list(evidence_refs),
                    "timeline_candidate_ids": list(candidate_ids),
                },
            },
            "confidence": round(float(confidence), 4),
        }


def _clock_seconds(value: Any) -> int | None:
    text = str(value).strip() if value is not None else ""
    parts = text.split(":")
    if len(parts) != 2 or not all(p.isascii() and p.isdigit() for p in parts):
        return None
    minute, second = int(parts[0]), int(parts[1])
    if minute > 9 or second >= 60:
        return None
    return 60 * minute + second


def observation_quality(view: TimelineView, window: tuple[int, int],
                        snapshots: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    """Package-level quality for a confirmed Round, measured from the timeline.

    ``timeline_completeness`` is the share of seconds in the window with any native
    observation. ``hud_confidence`` is the median source confidence of the promoted
    snapshot fields times the share of seconds with a promoted snapshot opportunity
    (an observed SELF/ALIVE second); with no promoted HUD value it is 0. There is no
    visual producer, so ``visual_confidence`` stays 0.
    """
    rows = view.seconds[window[0]:window[1]]
    duration = max(1, len(rows))
    missing = [row.index for row in rows if not row.observed]
    readable = sum(
        1 for row in rows
        if (row.camera_value, row.camera_status) == ("SELF", _OBSERVED)
        and (row.life_value, row.life_status) == ("ALIVE", _OBSERVED)
    )
    confidences = [
        float(v) for s in snapshots for v in s.get("source_confidence", {}).values()
    ]
    hud = round(median(confidences) * readable / duration, 4) if confidences else 0.0
    return {
        "hud_confidence": hud,
        "visual_confidence": 0.0,
        "timeline_completeness": round(1 - len(missing) / duration, 4),
        "missing_intervals": [
            {"start_sec": float(low), "end_sec": float(high)}
            for low, high in _intervals(missing)
        ],
    }


def _intervals(seconds: Sequence[int]) -> list[tuple[int, int]]:
    merged: list[list[int]] = []
    for second in sorted(seconds):
        if merged and second == merged[-1][1]:
            merged[-1][1] = second + 1
        else:
            merged.append([second, second + 1])
    return [(low, high) for low, high in merged]


# ------------------------------------------------- independent-signal verification


def verify_promotion(
    bundle: Mapping[str, Any], result: PromotionResult, *, min_confidence: float = 0.9
) -> dict[str, Any]:
    """Check promoted items against HUD signals the promotion gates did not use.

    The development recordings carry no human labels, so each promoted
    item is checked against an independent reading instead:

    * ``round_start``: the HUD round timer read within 5 s after the promoted start
      must still show at least 1:35 (the combat timer starts at 1:40). All readings
      below 1:30 is a false start; no reading is ``undetermined``.
    * ``round_end``: no observed ACTIVE second reading this Round's number may
      follow the promoted end inside the Round window.
    * ``round_result``: the next Round's consensus HUD score (from its own seconds)
      must equal this Round's score before plus the promoted result.
    * ``player_death``: no observed SELF view with an observed ALIVE life state and a
      readable HP above 0 may follow the death (3 s grace) inside the Round window.

    Counts are ``correct`` / ``false`` / ``undetermined`` per item kind, plus the
    abstained Rounds. These are consistency checks against other readers of the
    same recording, not an independent qualification.
    """
    view = TimelineView(bundle)
    counts: dict[str, Counter[str]] = {
        kind: Counter() for kind in ("round_start", "round_end", "round_result", "player_death")
    }
    failures: list[dict[str, Any]] = []
    rounds = sorted(result.rounds, key=lambda r: r.segment[0])
    has_hud = any(row.hud for row in view.seconds)

    def readings(row: SecondView, name: str) -> list[Any]:
        return [
            c.get("value") for c in row.hud.get(name, [])
            if isinstance(c.get("confidence"), int | float)
            and float(c["confidence"]) >= min_confidence
        ]

    for position, item in enumerate(rounds):
        if not item.confirmed:
            counts["round_start"]["abstained" if item.start is None else "unconfirmed"] += 1
            counts["round_end"]["abstained" if item.end is None else "unconfirmed"] += 1
            continue
        assert item.start is not None and item.end is not None and item.window is not None
        # round_start vs. the combat timer.
        timers = [
            seconds
            for row in view.seconds[item.start.time_sec:item.start.time_sec + 6]
            for value in readings(row, "timer")
            if (seconds := _clock_seconds(value)) is not None
        ]
        if not timers:
            counts["round_start"]["undetermined"] += 1
        elif max(timers) >= 95:
            counts["round_start"]["correct"] += 1
        elif max(timers) < 90:
            counts["round_start"]["false"] += 1
            failures.append({"kind": "round_start", "round_no": item.round_no,
                             "time_sec": item.start.time_sec, "timers": timers[:6]})
        else:
            counts["round_start"]["undetermined"] += 1
        # round_end vs. later ACTIVE seconds of the same Round.
        later_active = [
            row.index for row in view.seconds[item.end.time_sec + 1:item.window[1]]
            if row.round_value == "ACTIVE" and row.round_status == _OBSERVED
            and row.round_no == item.round_no
        ]
        if later_active:
            counts["round_end"]["false"] += 1
            failures.append({"kind": "round_end", "round_no": item.round_no,
                             "time_sec": item.end.time_sec, "active_after": later_active[:5]})
        else:
            counts["round_end"]["correct"] += 1
        # round_result vs. the next Round's own score readings.
        outcome = item.round_meta.get("round_result")
        before = item.round_meta.get("score_before")
        following = rounds[position + 1] if position + 1 < len(rounds) else None
        if outcome not in {"win", "loss"} or not isinstance(before, Mapping) or following is None:
            counts["round_result"]["undetermined"] += 1
        else:
            pairs: Counter[tuple[int, int]] = Counter()
            for row in view.seconds[following.segment[0]:following.segment[1]]:
                ally, enemy = readings(row, "ally_score"), readings(row, "enemy_score")
                if len(ally) == 1 and len(enemy) == 1 and str(ally[0]).isdigit() and str(
                    enemy[0]
                ).isdigit():
                    pair = (int(ally[0]), int(enemy[0]))
                    if sum(pair) == item.round_no:
                        pairs[pair] += 1
            if not pairs:
                counts["round_result"]["undetermined"] += 1
            else:
                observed = pairs.most_common(1)[0][0]
                expected = (
                    (int(before["ally"]) + 1, int(before["enemy"]))
                    if outcome == "win"
                    else (int(before["ally"]), int(before["enemy"]) + 1)
                )
                if observed == expected:
                    counts["round_result"]["correct"] += 1
                else:
                    counts["round_result"]["false"] += 1
                    failures.append({"kind": "round_result", "round_no": item.round_no,
                                     "expected": list(expected), "observed": list(observed)})
        # player_death vs. later live own view with HP (needs HUD values: a replay
        # projection has none, so its deaths stay undetermined).
        for event in item.events:
            if not has_hud:
                if event["type"] == "player_death":
                    counts["player_death"]["undetermined"] += 1
                continue
            if event["type"] != "player_death":
                continue
            second = int(event["time_sec"])
            alive_again = [
                row.index for row in view.seconds[second + 3:item.end.time_sec]
                if (row.camera_value, row.camera_status) == ("SELF", _OBSERVED)
                and (row.life_value, row.life_status) == ("ALIVE", _OBSERVED)
                and any(str(v).isdigit() and int(str(v)) > 0 for v in readings(row, "hp"))
            ]
            observed_after = any(
                row.camera_status == _OBSERVED
                for row in view.seconds[second + 1:item.end.time_sec + 1]
            )
            if alive_again and (event.get("attributes") or {}).get(
                "revive_corroborated_by_top_bar"
            ) is True:
                # A death, then a revive the top bar confirms (#167 second features).
                counts["player_death"]["revived"] += 1
            elif alive_again:
                counts["player_death"]["false"] += 1
                failures.append({"kind": "player_death", "round_no": item.round_no,
                                 "time_sec": second, "alive_after": alive_again[:5]})
            elif observed_after:
                counts["player_death"]["correct"] += 1
            else:
                counts["player_death"]["undetermined"] += 1
    return {
        "method": "independent_hud_signal_consistency",
        "qualification": "development_only_not_human_labelled",
        "counts": {kind: dict(sorted(c.items())) for kind, c in counts.items()},
        "failures": failures,
    }
