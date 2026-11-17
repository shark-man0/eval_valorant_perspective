"""Development-only check of which rules can fire on real recordings.

Input is a per-match series of knowledge-reader observations (ability HUD and
top match bar, sampled every few seconds). The module derives candidate facts
and events, then checks every rule's trigger and required predicates. Results
are counts of *candidate occurrences* for planning and regression tracking:
nothing here is a formal Fact, Event or evaluation (formal_outputs = 0).
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any

from valorant_ai_coach.knowledge.timeline_view import TimelineView

from ..knowledge.score_reader import score_track
from .recorder_life import (
    Reconciliation,
    RecorderDeath,
    Round,
    _round_of,
    reconcile,
    rounds_from_alive_counts,
    rounds_from_scores,
)
from .round_phases import PhaseRules, PhaseSample, RoundPhases, round_phases
from .side import DEFENSE, RoundOrdinal, SideInference, infer_sides

SELF_VIEW_MIN_SCORE = 0.6
CHARGE_DROP = 0.25
FEED_REPEAT_SEC = 7.0
TEAM_SIZE = 5
BUY_PHASE_MIN_SEC = 20.0  # 5 v 5 held this long after a reset: a real buy phase
MIN_SCORE_ROUNDS = 3  # fewer score-delimited rounds: fall back to boundary sources
CONFIRM_WINDOW_SEC = 12.0


@dataclass(frozen=True)
class FeedKill:
    killer_team: str
    victim_team: str
    victim: str | None
    recorder_killer: bool
    recorder_victim: bool


@dataclass(frozen=True)
class Observation:
    sec: float
    hud_present: bool
    viewed_agent: str | None
    viewed_score: float
    charges: tuple[float, float, float, float]  # C, Q, E, X
    ally_alive: int | None
    enemy_alive: int | None
    spike_planted: bool | None = None
    feed: tuple[FeedKill, ...] | None = None  # None: kill feed not captured
    spike_carried: bool | None = None  # spike header in the viewed inventory
    score: tuple[int | None, int | None] | None = None  # top-bar ally, enemy score
    timer: int | None = None  # round timer seconds (m:ss) in the top bar


@dataclass
class DerivedSample:
    sec: float
    facts: dict[str, Any]
    events: set[str] = field(default_factory=set)


@dataclass
class Derivation:
    samples: list[DerivedSample]
    reconciliation: Reconciliation
    sources: dict[str, str]
    sides: SideInference
    phases: list[RoundPhases]


def _new_feed_kills(series: Sequence[Observation]) -> dict[float, list[FeedKill]]:
    """Kill-feed entries at the sample where each first appears (entries persist)."""
    out: dict[float, list[FeedKill]] = {}
    previous: list[tuple[float, FeedKill]] = []
    for obs in series:
        if obs.feed is None:
            continue
        fresh = []
        for kill in obs.feed:
            key = (kill.killer_team, kill.victim_team, kill.victim, kill.recorder_victim,
                   kill.recorder_killer)
            seen = any(obs.sec - t <= FEED_REPEAT_SEC and key == (
                k.killer_team, k.victim_team, k.victim, k.recorder_victim, k.recorder_killer)
                for t, k in previous)
            if not seen:
                fresh.append(kill)
        if fresh:
            out[obs.sec] = fresh
        previous = [(t, k) for t, k in previous if obs.sec - t <= FEED_REPEAT_SEC]
        previous.extend((obs.sec, k) for k in obs.feed)
    return out


def derive(series: Sequence[Observation], recorder_agent: str | None, recorder_role: str,
           timeline: TimelineView | None = None, *, rounds_per_half: int = 12,
           phase_rules: PhaseRules | None = None,
           additions: Mapping[float, tuple[set[str], dict[str, Any]]] | None = None,
           ) -> Derivation:
    """Candidate facts/events per sample. Facts are omitted (missing) when unobserved.

    With a shared timeline, the recorder's own live view and deaths come from
    it (deaths reconciled per round with the kill feed); without one, from the
    ability HUD and the top bar. Every death is reconciled per round.
    """
    def hud_self(obs: Observation) -> bool:
        return (recorder_agent is not None and obs.hud_present
                and obs.viewed_agent == recorder_agent
                and obs.viewed_score >= SELF_VIEW_MIN_SCORE)

    def self_view(obs: Observation) -> bool:
        if timeline is not None and timeline.state_at(obs.sec) is not None:
            return timeline.self_live(obs.sec)
        return hud_self(obs)

    score_tracks = [score_track([(o.sec, o.score[side] if o.score else None) for o in series])
                    for side in (0, 1)]
    ordinal = RoundOrdinal(*score_tracks)
    bar_rounds = rounds_from_alive_counts([(o.sec, o.ally_alive, o.enemy_alive) for o in series])
    def buy_phase_follows(start: float) -> bool:
        window = [o for o in series if start <= o.sec < start + BUY_PHASE_MIN_SEC + 0.1]
        return (len(window) >= 2 and window[-1].sec - start >= BUY_PHASE_MIN_SEC - 0.1
                and all(o.ally_alive == TEAM_SIZE and o.enemy_alive == TEAM_SIZE
                        for o in window))

    timeline_rounds = timeline.rounds() if timeline is not None else []
    round_numbers: list[int | None] = []
    if timeline_rounds:
        # The shared timeline is the canonical round source: its rounds are used
        # as they are, never patched with this module's own boundary evidence.
        rounds = [Round(r.start, r.end) for r in timeline_rounds]
        round_numbers = [r.number for r in timeline_rounds]
        round_source = "timeline"
    else:
        # No shared timeline export: provisional rounds from the top-bar score
        # (development only, reported separately from timeline rounds).
        rounds = rounds_from_scores(
            score_tracks, resets=[r.start for r in bar_rounds],
            buy_phase_starts=[r.start for r in bar_rounds if buy_phase_follows(r.start)])
        round_source = "provisional_score"
        if len(rounds) < MIN_SCORE_ROUNDS:
            rounds = bar_rounds
            round_source = "provisional_top_bar_reset"

    def ordinal_at(sec: float) -> int | None:
        """Round ordinal (0-based): the timeline's round number when it has
        one, else the provisional score-based ordinal."""
        if round_numbers:
            index = _round_of(rounds, sec)
            number = round_numbers[index] if index is not None else None
            return None if number is None else number - 1
        return ordinal.at(sec)

    feed_kills = _new_feed_kills(series)

    def confirmed_by_view(sec: float) -> bool:
        """A death must be followed by a view that is not the recorder's own.

        The local-player highlight also marks the recorder's own kills, so a
        kill-feed candidate counts only if a later sample in the window shows
        another player's HUD or no live own view.
        """
        window = [o for o in series if sec <= o.sec <= sec + CONFIRM_WINDOW_SEC and o.hud_present]
        return any(not self_view(o) for o in window)

    def recorder_victim(kill: FeedKill) -> bool:
        # The highlight marks the recorder's entry; when the victim portrait was
        # identified it must be the recorder's agent (else it is another entry).
        return kill.recorder_victim and (
            kill.victim is None or recorder_agent is None or kill.victim == recorder_agent)

    highlighted = [sec for sec, kills in feed_kills.items()
                   if any(k.recorder_victim for k in kills)]
    feed_candidates = [sec for sec, kills in feed_kills.items()
                       if any(recorder_victim(k) for k in kills)]
    candidates: dict[str, list[float]] = {
        "kill_feed": [sec for sec in feed_candidates if confirmed_by_view(sec)]}
    unconfirmed = len(feed_candidates) - len(candidates["kill_feed"])
    if timeline is not None:
        candidates["timeline"] = timeline.death_times()
    else:
        hud_deaths = []
        previous: Observation | None = None
        for obs in series:
            if (previous is not None and hud_self(previous) and obs.hud_present
                    and obs.viewed_agent not in (None, recorder_agent)
                    and obs.sec - previous.sec <= 10
                    and _round_of(rounds, previous.sec) == _round_of(rounds, obs.sec)):
                hud_deaths.append(obs.sec)
            previous = obs
        candidates["hud"] = hud_deaths
    # The recorder cannot be dead while the top bar shows the whole ally team
    # alive at the candidate and the next sample (round-transition HUD changes).
    by_sec = {o.sec: index for index, o in enumerate(series)}

    def full_team_alive(sec: float) -> bool:
        index = by_sec.get(sec)
        if index is None:
            return False
        window = series[index:index + 2]
        return len(window) == 2 and all(o.ally_alive == TEAM_SIZE for o in window)

    full_team_drops = 0
    for source in list(candidates):
        kept = [sec for sec in candidates[source] if not full_team_alive(sec)]
        full_team_drops += len(candidates[source]) - len(kept)
        candidates[source] = kept
    # Revive evidence: own live view mid-round (not everyone alive, which would be
    # a fresh round whose reset the round source missed).
    live = [o.sec for o in series if self_view(o) and o.ally_alive is not None
            and o.enemy_alive is not None and o.ally_alive + o.enemy_alive < 10]
    reconciliation = reconcile(
        rounds, candidates,
        self_live_at=timeline.self_live if timeline is not None else None,
        spectating_at=timeline.spectating if timeline is not None else None,
        live_samples=live)
    reconciliation.dropped["kill_feed_unconfirmed"] = unconfirmed
    reconciliation.dropped["kill_feed_other_victim"] = len(highlighted) - len(feed_candidates)
    reconciliation.dropped["full_team_alive"] = full_team_drops
    death_samples: dict[float, RecorderDeath] = {}
    for recorded in reconciliation.deaths:
        later = [o.sec for o in series if o.sec >= recorded.sec - 0.5]
        if later:
            death_samples[later[0]] = recorded
    first_kill_round: set[int] = set()
    # Side: a spike header in the recorder's own live view marks an attack round;
    # the half structure (game knowledge) extends it to the other regulation rounds.
    attack_ordinals = {ordinal_at(o.sec) for o in series
                       if o.spike_carried and self_view(o)} - {None}
    sides = infer_sides(attack_ordinals, rounds_per_half=rounds_per_half)  # type: ignore[arg-type]
    # Phases: score update, buy phase start, combat start and round end, apart.
    phase_rules = phase_rules or PhaseRules(regulation_rounds_per_half=rounds_per_half)
    phases = round_phases([PhaseSample(o.sec, o.timer, ordinal_at(o.sec), o.ally_alive,
                                       o.enemy_alive, o.spike_planted) for o in series],
                          phase_rules)

    def phase_of(sec: float) -> tuple[RoundPhases | None, str | None]:
        """("buy" | "combat" | None) for a time, by the latest phase anchor."""
        for item in reversed(phases):
            if item.combat_start is not None and sec >= item.combat_start:
                end = item.round_end
                return (item, "combat") if end is None or sec <= end else (item, None)
            if item.buy_phase_start is not None and sec >= item.buy_phase_start:
                return item, "buy"
        return None, None

    buy_seen: set[int] = set()

    samples: list[DerivedSample] = []
    previous = None
    previous_self: Observation | None = None
    previous_spike: tuple[int | None, bool] | None = None
    for obs in series:
        facts: dict[str, Any] = {}
        events: set[str] = set()
        own = self_view(obs)
        round_index = _round_of(rounds, obs.sec)
        if recorder_agent is not None:
            facts["player_role"] = recorder_role
        if round_index is not None and (
                previous is None or _round_of(rounds, previous.sec) != round_index):
            events.add("round_start")
        phase_round, phase = phase_of(obs.sec)
        if phase == "buy" and phase_round is not None:
            facts["buy_phase_observed"] = True
            if phase_round.ordinal not in buy_seen:
                buy_seen.add(phase_round.ordinal)
                events.add("buy_phase")
        elif phase == "combat" and phase_round is not None and not obs.spike_planted:
            start = phase_round.combat_start or 0.0
            facts["round_time_remaining_sec"] = (
                obs.timer if obs.timer is not None
                else max(0.0, phase_rules.round_time_limit_sec - (obs.sec - start)))
        side = sides.side(ordinal_at(obs.sec))
        if side is not None:
            facts["side"] = side[0]
            if side[0] == DEFENSE:
                facts["spike_carried_by_player"] = False
        if own and obs.spike_carried:
            facts["spike_carried_by_player"] = True
        bar_ok = obs.ally_alive is not None and obs.enemy_alive is not None
        if bar_ok and obs.ally_alive and obs.enemy_alive:
            ally, enemy = int(obs.ally_alive), int(obs.enemy_alive)
            facts["numbers_state"] = (
                "advantage" if ally > enemy else "disadvantage" if ally < enemy else "even"
            )
            events.add("state_snapshot")
            if own:
                facts["clutch_state"] = ally == 1 and enemy >= 1
        if own and obs.hud_present:
            events.add("ability_state")
            facts["utility_available_count"] = sum(c >= 0.25 for c in obs.charges[:3])
            facts["ultimate_available"] = obs.charges[3] >= 0.6
            facts["player_died"] = False
            if (previous_self is not None and obs.sec - previous_self.sec <= 10
                    and _round_of(rounds, previous_self.sec) == round_index):
                drops = [a - b for a, b in zip(previous_self.charges[:3], obs.charges[:3],
                                               strict=True)]
                if max(drops) >= CHARGE_DROP:
                    events.add("utility_used")
            previous_self = obs
        death = death_samples.get(obs.sec)
        if death is not None:
            events.add("player_death")
            facts["player_died"] = True
            if previous_self is not None and obs.sec - previous_self.sec <= 10:
                # Utilities still charged on the last own-HUD sample before the death.
                facts["utility_available_count"] = sum(
                    c >= 0.25 for c in previous_self.charges[:3])
        kills = feed_kills.get(obs.sec)
        if kills:
            events.add("kill")
            if round_index is not None and round_index not in first_kill_round:
                first_kill_round.add(round_index)
                first = kills[0]
                facts["first_death_by_player"] = first.recorder_victim
                facts["first_kill_by_player"] = first.recorder_killer
        elif obs.feed is None and previous is not None and bar_ok and \
                previous.ally_alive is not None and previous.enemy_alive is not None \
                and obs.sec - previous.sec <= 10 and \
                _round_of(rounds, previous.sec) == round_index:
            # No kill feed captured: team-level kill from an alive-count drop.
            ally_drop = 0 < int(obs.ally_alive or 0) < int(previous.ally_alive)
            enemy_drop = 0 < int(obs.enemy_alive or 0) < int(previous.enemy_alive)
            if ally_drop or enemy_drop:
                events.add("kill")
        if obs.spike_planted is not None:
            facts["spike_planted"] = obs.spike_planted
            facts["objective_state_observed"] = True
            if (obs.spike_planted and previous_spike is not None
                    and previous_spike == (round_index, False)):
                events.update({"spike_planted", "objective_state"})
            previous_spike = (round_index, obs.spike_planted)
        if additions and obs.sec in additions:
            extra_events, extra_facts = additions[obs.sec]
            events |= extra_events
            facts.update(extra_facts)
        samples.append(DerivedSample(obs.sec, facts, events))
        previous = obs
    sources = {"rounds": round_source,
               "self_view": "timeline" if timeline is not None else "ability_hud",
               "deaths": "+".join(sorted(candidates)),
               "side": sides.status}
    sources["phases"] = f"{sum(p.combat_start is not None for p in phases)}/{len(phases)}"
    return Derivation(samples, reconciliation, sources, sides, phases)


def _predicate(value: Any, op: str, expected: Any) -> bool:
    if op == "eq":
        return bool(value == expected)
    if op == "in":
        return value in expected
    if op == "gt":
        return bool(value > expected)
    if op == "gte":
        return bool(value >= expected)
    raise ValueError(f"Unsupported predicate op {op}")


def rule_occurrences(rules: Sequence[dict[str, Any]], samples: Sequence[DerivedSample]
                     ) -> dict[str, int]:
    """Samples where a trigger event and all required predicates hold, per rule."""
    counts = {rule["id"]: 0 for rule in rules}
    for sample in samples:
        for rule in rules:
            trigger = rule["trigger"]
            if not sample.events.intersection(trigger["trigger_event_types"]):
                continue
            ok = True
            for predicate in trigger["required_state_predicates"]:
                key = predicate["fact_key"]
                if key not in sample.facts or not _predicate(
                        sample.facts[key], predicate["op"], predicate["value"]):
                    ok = False
                    break
            if ok:
                counts[rule["id"]] += 1
    return counts
