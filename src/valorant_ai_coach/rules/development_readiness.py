"""Development-only check of which rules can fire on real recordings.

Input is a per-match series of knowledge-reader observations (ability HUD and
top match bar, sampled every few seconds). The module derives candidate facts
and events, then checks every rule's trigger and required predicates. Results
are counts of *candidate occurrences* for planning and regression tracking:
nothing here is a formal Fact, Event or evaluation (formal_outputs = 0).
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
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
from .side import (
    ATTACK,
    DEFENSE,
    RoundOrdinal,
    SideInference,
    SideObservation,
    infer_sides,
    outcome_sides,
)

SELF_VIEW_MIN_SCORE = 0.6
CHARGE_DROP = 0.25
FEED_REPEAT_SEC = 7.0
TEAM_SIZE = 5
HUD_SWITCH_HOLD_SEC = 3.0
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
    spike_score: float | None = None  # the spike reader's score for that reading
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


END_ALIVE_MAX_GAP_SEC = 1.5  # alive counts must be read this close to the round end
MAX_END_GAP_SEC = 3.0  # the spike end must be bracketed this tightly
WINNER_WINDOW_SEC = 60.0  # score reads used to tell which team won the round
TIMEOUT_TIMER_MAX = 1  # combat clock at 0:01 or 0:00 with nobody planting
TIMEOUT_MIN_COMBAT_SEC = 95.0  # ... at least this long after combat started (limit 100 s)
CLEAR_SPIKE_SCORE = 0.9
SPIKE_OFF_HOLD = 3  # samples the planted indicator must stay off
SPIKE_END_SCORE_SEC = 40.0


def _planted_round_outcomes(
        series: Sequence[Observation], phases: Sequence[RoundPhases],
        tracks: Sequence[Sequence[tuple[float, int]]],
        ordinal_at: Callable[[float], int | None],
) -> list[tuple[int, str | None, float | None, float | None, float | None, float | None,
                bool]]:
    """Per planted round: winner, plant interval, spike-indicator-off interval and
    whether both teams were still alive when the indicator went off.

    The planted-spike indicator goes off when the spike detonates or is defused
    (or the round ends), and it is read every sample, so it dates the end of
    the spike far better than the score, which is often unreadable for a while.
    The winner is the team whose score rises by one across that moment.
    """
    out: list[tuple[int, str | None, float | None, float | None, float | None,
                    float | None, bool]] = []
    for phase in phases:
        rows = [o for o in series if ordinal_at(o.sec) == phase.ordinal]
        start = next((i for i, o in enumerate(rows) if o.spike_planted), None)
        if start is None or start == 0 or rows[start - 1].spike_planted is not False:
            continue
        plant_lo, plant_hi = rows[start - 1].sec, rows[start].sec
        # The indicator must stay off (it flickers under overlays).
        stop = next((i for i in range(start + 1, len(rows) - SPIKE_OFF_HOLD + 1)
                     if all(r.spike_planted is False for r in rows[i:i + SPIKE_OFF_HOLD])),
                    None)
        if stop is None:
            continue
        off_lo, off_hi = rows[stop - 1].sec, rows[stop].sec
        if off_hi - off_lo > MAX_END_GAP_SEC:
            continue
        around = [o for o in series
                  if off_lo - END_ALIVE_MAX_GAP_SEC <= o.sec <= off_hi + END_ALIVE_MAX_GAP_SEC + 1
                  and o.ally_alive is not None and o.enemy_alive is not None]
        both = bool(around) and all(o.ally_alive and o.enemy_alive for o in around)
        # A detonation or a defuse ends the round at once: the new score must be
        # read shortly after the indicator goes off.
        winner = None
        for name, track in zip(("ally", "enemy"), tracks, strict=True):
            before = [v for sec, v in track
                      if plant_lo - WINNER_WINDOW_SEC <= sec <= off_hi]
            after = [v for sec, v in track if off_hi <= sec <= off_hi + SPIKE_END_SCORE_SEC]
            if before and after and after[0] == before[-1] + 1:
                winner = name if winner is None else None
        out.append((phase.ordinal, winner, plant_lo, plant_hi, off_lo, off_hi, both))
    return out


def _round_winner(tracks: Sequence[Sequence[tuple[float, int]]], lo: float, hi: float
                  ) -> str | None:
    winner = None
    for name, track in zip(("ally", "enemy"), tracks, strict=True):
        before = [v for sec, v in track if lo - WINNER_WINDOW_SEC <= sec <= hi]
        after = [v for sec, v in track if hi <= sec <= hi + WINNER_WINDOW_SEC]
        if before and after and after[0] == before[-1] + 1:
            winner = name if winner is None else None
    return winner


def _timeout_sides(series: Sequence[Observation], phases: Sequence[RoundPhases],
                   tracks: Sequence[Sequence[tuple[float, int]]],
                   ordinal_at: Callable[[float], int | None]) -> list[SideObservation]:
    """Rounds that ran out of time with no plant: only defenders win those."""
    out = []
    for phase in phases:
        if phase.combat_start is None:
            continue
        rows = [o for o in series if ordinal_at(o.sec) == phase.ordinal
                and o.sec >= phase.combat_start]
        if any(o.spike_planted for o in rows):
            continue
        # The combat clock must actually have run down (not a buy countdown).
        expiry = next((o for o in rows if o.timer is not None and o.timer <= TIMEOUT_TIMER_MAX
                       and o.sec - phase.combat_start >= TIMEOUT_MIN_COMBAT_SEC), None)
        if expiry is None:
            continue
        around = [o for o in series if expiry.sec - 1 <= o.sec <= expiry.sec + 4
                  and o.ally_alive is not None and o.enemy_alive is not None]
        if not around or not all(o.ally_alive and o.enemy_alive for o in around):
            continue
        winner = _round_winner(tracks, expiry.sec, expiry.sec + 4)
        if winner is None:
            continue
        out.append(SideObservation(phase.ordinal, DEFENSE if winner == "ally" else ATTACK,
                                   "timeout_win"))
    return out


def derive(series: Sequence[Observation], recorder_agent: str | None, recorder_role: str,
           timeline: TimelineView | None = None, *, rounds_per_half: int = 12,
           phase_rules: PhaseRules | None = None,
           additions: Mapping[float, tuple[set[str], dict[str, Any]]] | None = None,
           spike_detonation_sec: float = 45.0,
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
        # The other view must hold (one misread frame is not enough at 1 s sampling).
        for index, obs in enumerate(window):
            if self_view(obs):
                continue
            held = [o for o in window[index:] if o.sec - obs.sec <= HUD_SWITCH_HOLD_SEC]
            if not any(self_view(o) for o in held) and (
                    held[-1].sec - obs.sec >= HUD_SWITCH_HOLD_SEC - 0.5 or len(held) == 1):
                return True
        return False

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

        def other_view_holds(index: int) -> bool:
            """Another agent's HUD for ``HUD_SWITCH_HOLD_SEC`` (a one-frame misread
            at a high sampling rate is not a death)."""
            start = series[index].sec
            span = [o for o in series[index:] if o.sec - start <= HUD_SWITCH_HOLD_SEC]
            return all(o.viewed_agent != recorder_agent for o in span if o.hud_present)

        for index, obs in enumerate(series):
            if (previous is not None and hud_self(previous) and obs.hud_present
                    and obs.viewed_agent not in (None, recorder_agent)
                    and obs.sec - previous.sec <= 10
                    and _round_of(rounds, previous.sec) == _round_of(rounds, obs.sec)
                    and other_view_holds(index)):
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
    # A round counts as a spike-carrier observation with two sightings in the
    # recorder's own view, or one clear one (borderline single frames are the
    # look-alike panels the spike reader cannot fully rule out).
    sightings: dict[int, list[float]] = {}
    for o in series:
        seen_in = ordinal_at(o.sec)
        if o.spike_carried and self_view(o) and seen_in is not None:
            sightings.setdefault(seen_in, []).append(o.spike_score or 0.0)
    attack_ordinals = {seen for seen, scores in sightings.items()
                       if len(scores) >= 2 or max(scores) >= CLEAR_SPIKE_SCORE}
    # Phases: score update, buy phase start, combat start and round end, apart.
    phase_rules = phase_rules or PhaseRules(regulation_rounds_per_half=rounds_per_half)
    phases = round_phases([PhaseSample(o.sec, o.timer, ordinal_at(o.sec), o.ally_alive,
                                       o.enemy_alive, o.spike_planted) for o in series],
                          phase_rules)
    side_observations: list[SideObservation] = [
        SideObservation(o, ATTACK, "spike_carried") for o in attack_ordinals
        if o is not None]
    side_observations += outcome_sides(
        _planted_round_outcomes(series, phases, score_tracks, ordinal_at),
        detonation_sec=spike_detonation_sec)
    side_observations += _timeout_sides(series, phases, score_tracks, ordinal_at)
    sides = infer_sides(side_observations, rounds_per_half=rounds_per_half)

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
