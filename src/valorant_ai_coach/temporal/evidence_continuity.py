"""Evidence-bounded continuity rules for the shared development state owner.

This module revises rows supplied by ``DevelopmentGameTimeline``; it is not a
second state engine. Every revision cites retained native observations and keeps
the previous estimate. A revision is made only where general game invariants and
measured displays together exclude the alternatives:

* The displayed score never decreases within one recording and changes exactly
  when a Round is decided. Between two measured phase anchors whose surrounding
  score readings are equal, no Round boundary can have happened, so a BUY-BUY,
  ACTIVE-ACTIVE or ENDED-ENDED bracket keeps that phase. An ACTIVE anchor extends
  only to the last frame still displaying its score; an ENDED anchor extends back
  only to the first frame displaying its own score.
* A one-point score increment after a measured ACTIVE phase is a Round decision
  candidate; a same-score BUY or ENDED to ACTIVE bracket is a Round start
  candidate whose bracket keeps the unobserved purchase phase inside it. Two
  consistent ACTIVE countdown readings narrow that bracket to the frame before
  the projected 1:40 display.
* A spectator panel during ACTIVE/ENDED, without any current owner HUD, remote or
  revival cue, is a non-living recorder hypothesis; living players do not spectate.
  Two such dead anchors in one unchanged-score Round bracket intervening frames
  that show no owner HUD, revival or purchase cue.
* A recorder that is not alive cannot hold the first-person view; every player
  is alive during the purchase phase, and a higher score than at the last death
  proves a respawn before a current owner HUD.

Missing frames, decode breaks, conflicting readings and unexplained gaps stop a
revision. Nothing here issues qualified Facts/Events or recorder ownership.
"""

from __future__ import annotations

from collections.abc import Callable
from copy import deepcopy
from fractions import Fraction
from typing import Any

from .evidence import digest, native_time, source_scope

VERSION = "development_evidence_continuity_v1"
ORIGIN = "evidence_continuity_projection"
# Sanity bounds from the competitive Round format; they only restrict revisions.
PHASE_LIMITS = {"BUY": Fraction(60), "ACTIVE": Fraction(150), "ENDED": Fraction(30)}
SCORE_SEARCH = Fraction(30)
# Displayed combat-phase countdown at a Round start (1:40).
ROUND_SECONDS = 100
CLOCK_WINDOW = Fraction(3)
_PHASE_CUES = {"buy", "result", "intermission"}
_SELF_CUES = {"owner_hud", "remote", "revival"}
_OWN_REASONS = {
    "same_score_phase_bracket",
    "active_score_unchanged",
    "ended_score_already_updated",
    "spectator_view_within_round",
    "dead_bracket_same_round",
    "purchase_phase_all_players_alive",
    "recorder_not_alive_views_another_actor",
    "new_round_since_death_and_current_owner_hud",
    "death_hypothesis_outlived_its_round",
}


def _rows(frame: dict[str, Any], observations: dict[str, Any]) -> list[dict[str, Any]]:
    return [observations[i] for i in frame["observation_ids"]]


def _signals(rows: list[dict[str, Any]], *, strong_only: bool = True) -> set[str]:
    return {
        s for r in rows for s in r["signals"]
        if not strong_only or (
            r["context"].get("unqualified_view_model") is not True
            and r["context"].get("unqualified_round_model") is not True
        )
    }


def _scores(frame: dict[str, Any]) -> set[tuple[int, ...]]:
    return {
        tuple(row["displayed_score"])
        for row in frame.get("round_number", {}).get("score_observations", [])
        if row["eligible"]
    }


def _score_ids(frame: dict[str, Any]) -> list[str]:
    return [
        row["observation_id"]
        for row in frame.get("round_number", {}).get("score_observations", [])
        if row["eligible"]
    ]


def _segments(states: list[dict[str, Any]]) -> list[list[int]]:
    segments: list[list[int]] = []
    for i, frame in enumerate(states):
        if (
            not segments
            or not frame["continuity"].get("carry_allowed", False)
            or source_scope(states[segments[-1][-1]]["sample"]) != source_scope(frame["sample"])
        ):
            segments.append([i])
        else:
            segments[-1].append(i)
    return segments


def _anchor(estimate: dict[str, Any], values: set[str]) -> bool:
    """A measured estimate; short unverified carries never bound a revision."""
    return bool(
        estimate["value"] in values
        and estimate["hypotheses"] == [estimate["value"]]
        and estimate["reason"] not in _OWN_REASONS
        and estimate["uncertainty"] != "continuation_unverified"
    )


class _Reviser:
    def __init__(self, estimate: Callable[..., dict[str, Any]]) -> None:
        self.estimate = estimate
        self.history: list[dict[str, Any]] = []

    def __call__(
        self, frame: dict[str, Any], domain: str, value: str, alternatives: list[str],
        evidence: list[str], reason: str,
    ) -> None:
        before = deepcopy(frame[domain])
        after = self.estimate(
            value, alternatives=alternatives, reason=reason,
            evidence=[*before["evidence_ids"], *evidence], origin=ORIGIN,
        )
        after.update(
            rule_estimate=before,
            uncertainty="unresolved" if value == "UNKNOWN"
            else "unqualified_evidence_continuity_candidate",
        )
        frame[domain] = after
        self.history.append({
            "sample": deepcopy(frame["sample"]), "domain": domain, "before": before,
            "after": deepcopy(after), "evidence_ids": sorted(set(evidence)), "reason": reason,
            "qualified": False,
        })


def _nearest_score(
    states: list[dict[str, Any]], segment: list[int], position: int, step: int
) -> tuple[tuple[int, ...] | None, int | None]:
    """Nearest single score reading from a segment position, within a bounded window."""
    origin = native_time(states[segment[position]]["sample"])
    k = position
    while 0 <= k < len(segment):
        frame = states[segment[k]]
        if abs(native_time(frame["sample"]) - origin) > SCORE_SEARCH:
            return None, None
        scores = _scores(frame)
        if len(scores) > 1:
            return None, None
        if scores:
            return next(iter(scores)), k
        k += step
    return None, None


def _readings(states: list[dict[str, Any]], segment: list[int], lo: int, hi: int) -> set[Any]:
    out: set[Any] = set()
    for k in range(lo, hi + 1):
        out |= _scores(states[segment[k]])
    return out


def _clock(frame: dict[str, Any], observations: dict[str, Any]) -> tuple[int, list[str]] | None:
    rows = [r for r in _rows(frame, observations) if r["context"].get("timer_seconds") is not None]
    values = {r["context"]["timer_seconds"] for r in rows}
    if len(values) != 1:
        return None
    value = next(iter(values))
    return (value, [r["observation_id"] for r in rows]) if type(value) is int else None


def _clock_lower(
    states: list[dict[str, Any]], observations: dict[str, Any], segment: list[int],
    a: int, b: int,
) -> tuple[int, list[str], int] | None:
    """Narrow a start bracket by the measured ACTIVE countdown at its upper anchor.

    A second, consistent countdown reading within a few seconds guards against a
    single misread. Returns the latest segment position still before the start.
    """
    upper = states[segment[b]]
    first = _clock(upper, observations)
    if first is None or not ROUND_SECONDS - 10 <= first[0] <= ROUND_SECONDS:
        return None
    t_b = native_time(upper["sample"])
    support = None
    for k in range(b + 1, len(segment)):
        frame = states[segment[k]]
        dt = native_time(frame["sample"]) - t_b
        if dt > CLOCK_WINDOW:
            break
        later = _clock(frame, observations)
        if later is not None and dt > 0 and abs((first[0] - later[0]) - dt) <= 1:
            support = later
            break
    if support is None:
        return None
    start_not_after = t_b - (ROUND_SECONDS - first[0]) - 1
    lower = None
    for k in range(b - 1, a - 1, -1):
        if native_time(states[segment[k]]["sample"]) <= start_not_after:
            lower = k
            break
    if lower is None:
        return None
    return lower, first[1] + support[1], first[0]


def _event(kind: str, low: dict[str, Any], high: dict[str, Any], evidence: list[str],
           basis: str, interval: tuple[dict[str, Any], dict[str, Any]]) -> dict[str, Any]:
    """``interval`` is the anchor pair that can contain only this one boundary."""
    result = {
        "kind": kind, "lower_sample": deepcopy(low["sample"]),
        "upper_sample": deepcopy(high["sample"]), "evidence_ids": sorted(set(evidence)),
        "status": "unqualified_evidence_continuity_candidate", "basis": basis,
        "single_boundary_interval": {
            "lower_sample": deepcopy(interval[0]["sample"]),
            "upper_sample": deepcopy(interval[1]["sample"]),
        },
        "internal_game_event_time": None, "qualified": False,
    }
    result["candidate_id"] = digest(result)
    return result


def _round_pass(
    states: list[dict[str, Any]], observations: dict[str, Any], segment: list[int],
    revise: _Reviser, events: list[dict[str, Any]],
) -> None:
    anchors = [
        k for k, i in enumerate(segment)
        if _anchor(states[i]["round"], {"BUY", "ACTIVE", "ENDED"})
    ]
    for a, b in zip(anchors, anchors[1:], strict=False):
        if b - a < 2:
            continue  # Adjacent anchors: the main loop already owns that edge.
        low, high = states[segment[a]], states[segment[b]]
        pa, pb = low["round"]["value"], high["round"]["value"]
        inner = [segment[k] for k in range(a + 1, b)]
        # Unqualified candidates agreeing with the earlier anchor may lie in
        # between; they are neither anchors nor revised. Anything else stops.
        if any(
            not (
                states[i]["round"]["value"] == "UNKNOWN"
                and states[i]["round"]["reason"] == "unobserved"
                or states[i]["round"]["value"] == pa
            )
            or _signals(_rows(states[i], observations)) & _PHASE_CUES
            for i in inner
        ):
            continue
        targets = [i for i in inner if states[i]["round"]["value"] == "UNKNOWN"]
        span = native_time(high["sample"]) - native_time(low["sample"])
        left, left_at = _nearest_score(states, segment, a, -1)
        right, right_at = _nearest_score(states, segment, b, 1)
        if left is None or left_at is None:
            continue
        evidence = low["round"]["evidence_ids"] + high["round"]["evidence_ids"]
        unchanged = bool(
            right is not None and right == left
            and not _readings(states, segment, a, b) - {left}
        )
        bracket_ids = [
            x for k in (left_at, right_at) if k is not None
            for x in _score_ids(states[segment[k]])
        ]
        if pa == pb and span <= PHASE_LIMITS[pa] and unchanged:
            for i in targets:
                revise(states[i], "round", pa, [pa], evidence + bracket_ids,
                       "same_score_phase_bracket")
            continue
        # ENDED already shows the next Round's score; the same score while ACTIVE
        # means exactly that next Round started in between (purchase unobserved).
        if unchanged and pb == "ACTIVE" and (
            pa == "BUY" and span <= PHASE_LIMITS["BUY"]
            or pa == "ENDED" and span <= PHASE_LIMITS["ENDED"] + PHASE_LIMITS["BUY"]
        ):
            basis = ("same_score_purchase_to_active_bracket" if pa == "BUY"
                     else "same_score_result_to_active_bracket")
            lower, ids = low, evidence + bracket_ids
            narrowed = _clock_lower(states, observations, segment, a, b)
            if narrowed is not None:
                lower = states[segment[narrowed[0]]]
                ids = ids + narrowed[1]
                basis += "+active_countdown_projection"
            event = _event("round_start", lower, high, ids, basis, (low, high))
            if narrowed is not None:
                event["countdown_projection"] = {
                    "displayed_seconds": narrowed[2], "round_seconds": ROUND_SECONDS,
                    "basis": "two_consistent_countdown_readings",
                }
            events.append(event)
            continue
        if pa != "ACTIVE" or span > PHASE_LIMITS["ACTIVE"]:
            continue
        # ACTIVE persists while its score is still displayed. The last such frame
        # may already show a Round result, so it stays unrevised.
        last_same, changed_at = a, None
        for k in range(a + 1, b + 1):
            scores = _scores(states[segment[k]])
            if len(scores) > 1:
                break
            if scores == {left}:
                last_same = k
            elif scores:
                changed_at = k
                break
        if changed_at is None:
            continue
        for k in range(a + 1, last_same):
            if states[segment[k]]["round"]["value"] == "UNKNOWN":
                revise(states[segment[k]], "round", "ACTIVE", ["ACTIVE"],
                       evidence + _score_ids(states[segment[last_same]]),
                       "active_score_unchanged")
        new = next(iter(_scores(states[segment[changed_at]])))
        if (
            len(new) != len(left) or any(n < o for n, o in zip(new, left, strict=True))
            or sum(new) - sum(left) != 1
            or _readings(states, segment, changed_at, b) - {new}
        ):
            continue
        upper = states[segment[changed_at]]
        events.append(_event(
            "round_end", states[segment[last_same]], upper,
            evidence + _score_ids(states[segment[last_same]]) + _score_ids(upper),
            "measured_active_phase_and_one_point_score_increment", (low, high),
        ))
        if pb == "ENDED" and right == new and all(
            states[segment[k]]["round"]["value"] == "UNKNOWN" for k in range(changed_at, b)
        ):
            for k in range(changed_at, b):
                revise(states[segment[k]], "round", "ENDED", ["ENDED"],
                       high["round"]["evidence_ids"] + _score_ids(upper),
                       "ended_score_already_updated")


def _life_pass(
    states: list[dict[str, Any]], observations: dict[str, Any], segment: list[int],
    revise: _Reviser,
) -> None:
    for i in segment:
        frame = states[i]
        rows = _rows(frame, observations)
        strong, weak = _signals(rows), _signals(rows, strong_only=False)
        # A measured spectator panel, or three separately measured cues together:
        # the learned spectator view, the combat report and the recorder's alias
        # in the elimination display. None of them alone is a death.
        combined = bool(
            "report" in strong
            and "spectator" in weak
            and "recorder_elimination_display" in weak
        )
        if (
            frame["life"]["value"] == "UNKNOWN"
            and frame["camera"]["value"] == "SPECTATOR"
            and ("spectator" in strong or combined)
            and not weak & (_SELF_CUES | {"buy", "death", "downed"})
            and frame["round"]["value"] in {"ACTIVE", "ENDED"}
        ):
            revise(frame, "life", "DEAD", ["DEAD", "DOWNED"],
                   [r["observation_id"] for r in rows
                    if set(r["signals"]) & {"spectator", "report", "recorder_elimination_display"}]
                   + frame["camera"]["evidence_ids"] + frame["round"]["evidence_ids"],
                   "spectator_view_within_round")
    anchors = [k for k, i in enumerate(segment) if states[i]["life"]["value"] == "DEAD"
               and "UNKNOWN" not in states[i]["life"]["hypotheses"]]
    for a, b in zip(anchors, anchors[1:], strict=False):
        if b - a < 2:
            continue
        low, high = states[segment[a]], states[segment[b]]
        if native_time(high["sample"]) - native_time(low["sample"]) > PHASE_LIMITS["ACTIVE"]:
            continue
        inner = [segment[k] for k in range(a + 1, b)]
        if any(
            states[i]["life"]["value"] != "UNKNOWN"
            or _signals(_rows(states[i], observations), strong_only=False)
            & (_SELF_CUES | {"buy"})
            or states[i]["round"]["value"] in {"BUY", "INTERMISSION"}
            for i in inner
        ):
            continue
        left, _ = _nearest_score(states, segment, a, -1)
        right, _ = _nearest_score(states, segment, b, 1)
        if left is None or left != right or _readings(states, segment, a, b) - {left}:
            continue
        for i in inner:
            revise(states[i], "life", "DEAD", ["DEAD", "DOWNED"],
                   low["life"]["evidence_ids"] + high["life"]["evidence_ids"],
                   "dead_bracket_same_round")
    # A displayed score above the one shown at the last dead anchor proves that
    # a new Round, and therefore a respawn, happened in between.
    dead_score: tuple[int, ...] | None = None
    for k, i in enumerate(segment):
        frame = states[i]
        weak = _signals(_rows(frame, observations), strong_only=False)
        life = frame["life"]
        if life["value"] == "DEAD" and "UNKNOWN" not in life["hypotheses"]:
            # Only a measured death fixes the Round; latched copies carry it on.
            if (
                life["reason"] != "observed_death_latch"
                and life["uncertainty"] != "continuation_unverified"
            ):
                dead_score, _ = _nearest_score(states, segment, k, -1)
            continue
        current, _ = _nearest_score(states, segment, k, -1)
        if (
            dead_score is not None and current is not None
            and frame["life"]["value"] == "UNKNOWN"
            and frame["life"]["reason"] in {
                "return_edge_unobserved", "candidate_return_edge_unobserved"
            }
            and "owner_hud" in weak
            and not weak & {
                "spectator", "remote", "death", "downed", "report",
                "recorder_elimination_display",
            }
            and len(current) == len(dead_score)
            and all(c >= d for c, d in zip(current, dead_score, strict=True))
            and sum(current) > sum(dead_score)
        ):
            revise(frame, "life", "ALIVE", ["ALIVE"],
                   _score_ids(frame) + frame["camera"]["evidence_ids"],
                   "new_round_since_death_and_current_owner_hud")
    # An open death hypothesis cannot outlive the Round it was raised in: after a
    # higher score every player has respawned. Without a fresh death cue the
    # stale value is withdrawn; with a current owner HUD the recorder is alive.
    run_score: tuple[int, ...] | None = None
    for k, i in enumerate(segment):
        frame = states[i]
        life = frame["life"]
        if not (life["value"] == "DEAD" and "UNKNOWN" in life["hypotheses"]):
            if life["value"] != "UNKNOWN":
                run_score = None
            continue
        current, _ = _nearest_score(states, segment, k, -1)
        if run_score is None:
            run_score = current
            continue
        weak = _signals(_rows(frame, observations), strong_only=False)
        if (
            current is None or len(current) != len(run_score)
            or any(c < d for c, d in zip(current, run_score, strict=True))
            or sum(current) <= sum(run_score)
            or weak & {"death", "downed", "recorder_elimination_display", "spectator"}
        ):
            continue
        if "owner_hud" in weak and not weak & {"remote", "report"}:
            revise(frame, "life", "ALIVE", ["ALIVE"],
                   _score_ids(frame) + frame["camera"]["evidence_ids"],
                   "new_round_since_death_and_current_owner_hud")
        else:
            revise(frame, "life", "UNKNOWN", ["UNKNOWN", "ALIVE", "DEAD"],
                   _score_ids(frame), "death_hypothesis_outlived_its_round")
    for i in segment:
        frame = states[i]
        weak = _signals(_rows(frame, observations), strong_only=False)
        # A recorder that is not alive cannot hold the first-person view.
        if (
            frame["camera"]["value"] == "UNKNOWN"
            and frame["life"]["value"] == "DEAD"
            and "UNKNOWN" not in frame["life"]["hypotheses"]
            and not weak & _SELF_CUES
        ):
            revise(frame, "camera", "SPECTATOR", ["SPECTATOR"], frame["life"]["evidence_ids"],
                   "recorder_not_alive_views_another_actor")
        if (
            frame["life"]["value"] == "UNKNOWN"
            and frame["round"]["value"] == "BUY"
            and "UNKNOWN" not in frame["round"]["hypotheses"]
            and frame["camera"]["value"] != "SPECTATOR"
            and not weak & {"spectator", "remote", "death", "downed"}
        ):
            revise(frame, "life", "ALIVE", ["ALIVE"], frame["round"]["evidence_ids"],
                   "purchase_phase_all_players_alive")


def apply_evidence_continuity(
    states: list[dict[str, Any]], observations: dict[str, Any],
    estimate: Callable[..., dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Return revision history and added unqualified event candidates."""
    revise = _Reviser(estimate)
    events: list[dict[str, Any]] = []
    for segment in _segments(states):
        _round_pass(states, observations, segment, revise, events)
        _life_pass(states, observations, segment, revise)
    return revise.history, events


def merge_continuity_events(
    existing: list[dict[str, Any]], added: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    """Add only boundaries that no existing same-kind candidate already brackets.

    The anchor interval of an added event contains exactly one Round boundary of
    its kind, so any existing candidate overlapping it is the same boundary.
    """
    kept = []
    for event in added:
        span = event["single_boundary_interval"]
        lo, hi = native_time(span["lower_sample"]), native_time(span["upper_sample"])
        if any(
            e["kind"] == event["kind"]
            and source_scope(e["upper_sample"]) == source_scope(event["upper_sample"])
            and native_time(e["lower_sample"]) - 1 <= hi
            and lo <= native_time(e["upper_sample"]) + 1
            for e in existing
        ):
            continue
        existing.append(event)
        kept.append(event)
    existing.sort(key=lambda e: (source_scope(e["upper_sample"]), native_time(e["upper_sample"])))
    return kept
