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
# The countdown may be read for this long after the first ACTIVE anchor.
CLOCK_SEARCH = Fraction(60)
# The score display can follow the Round decision: on the ten DEVELOPMENT matches
# the result banner preceded the first updated score by at most 3 s. Old-score
# frames this close to the update are not assumed undecided.
DECISION_DISPLAY_LEAD = Fraction(5)
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
    "active_countdown_since_projected_start",
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


def _countdown_start(
    states: list[dict[str, Any]], observations: dict[str, Any], segment: list[int],
    b: int, score: tuple[int, ...],
) -> tuple[Fraction, list[str], int] | None:
    """Project a Round start from the measured ACTIVE countdown after anchor ``b``.

    The first frame (within ``CLOCK_SEARCH``) whose countdown reading is confirmed
    by a second consistent reading a few seconds later fixes the start at
    ``t - (ROUND_SECONDS - shown)``. Frames up to it must keep the same score and
    show no phase cue, so the countdown belongs to the same Round.
    """
    t_b = native_time(states[segment[b]]["sample"])
    for k in range(b, len(segment)):
        frame = states[segment[k]]
        t_k = native_time(frame["sample"])
        if t_k - t_b > CLOCK_SEARCH:
            return None
        if _signals(_rows(frame, observations)) & _PHASE_CUES or _scores(frame) - {score}:
            return None
        first = _clock(frame, observations)
        if first is None or not 30 <= first[0] <= ROUND_SECONDS:
            continue
        for m in range(k + 1, len(segment)):
            later_frame = states[segment[m]]
            dt = native_time(later_frame["sample"]) - t_k
            if dt > CLOCK_WINDOW:
                break
            later = _clock(later_frame, observations)
            if later is not None and dt > 0 and abs((first[0] - later[0]) - dt) <= 1:
                return t_k - (ROUND_SECONDS - first[0]), first[1] + later[1], first[0]
    return None


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
            lower, upper, ids = low, high, evidence + bracket_ids
            projected = _countdown_start(states, observations, segment, b, left)
            if projected is not None:
                start, clock_ids, shown = projected
                before = [k for k in range(a, b)
                          if native_time(states[segment[k]]["sample"]) <= start - 1]
                after = [k for k in range(a + 1, b + 1)
                         if native_time(states[segment[k]]["sample"]) >= start + 1]
                if before and after and before[-1] < after[0]:
                    lower = states[segment[before[-1]]]
                    upper = states[segment[after[0]]]
                    ids = ids + clock_ids
                    basis += "+active_countdown_projection"
                    # The countdown proves the Round has run since the projected start.
                    for k in range(after[0], b):
                        frame = states[segment[k]]
                        if frame["round"]["value"] == "UNKNOWN":
                            revise(frame, "round", "ACTIVE", ["ACTIVE"],
                                   high["round"]["evidence_ids"] + clock_ids,
                                   "active_countdown_since_projected_start")
                else:
                    projected = None
            event = _event("round_start", lower, upper, ids, basis, (low, high))
            if projected is not None:
                event["countdown_projection"] = {
                    "displayed_seconds": shown, "round_seconds": ROUND_SECONDS,
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
        # The Round is known undecided only at a measured ACTIVE cue, or at an
        # old-score frame earlier than the score update by the display lead.
        t_change = native_time(states[segment[changed_at]]["sample"])
        undecided = a
        for k in range(a + 1, last_same + 1):
            frame = states[segment[k]]
            cues = _signals(_rows(frame, observations))
            if "result" in cues:
                break
            if "active" in cues or native_time(frame["sample"]) <= t_change - DECISION_DISPLAY_LEAD:
                undecided = k
        for k in range(a + 1, undecided + 1):
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
        for k in range(undecided + 1, changed_at):
            if "result" in _signals(_rows(states[segment[k]], observations)):
                upper = states[segment[k]]
                break
        events.append(_event(
            "round_end", states[segment[undecided]], upper,
            evidence + _score_ids(states[segment[undecided]]) + _score_ids(upper),
            "measured_active_phase_and_one_point_score_increment", (low, high),
        ))
        if pb == "ENDED" and right == new and all(
            states[segment[k]]["round"]["value"] == "UNKNOWN" for k in range(changed_at, b)
        ):
            for k in range(changed_at, b):
                revise(states[segment[k]], "round", "ENDED", ["ENDED"],
                       high["round"]["evidence_ids"] + _score_ids(upper),
                       "ended_score_already_updated")


def _new_round_seen(
    states: list[dict[str, Any]], segment: list[int], since: int, now: int,
    starts: list[tuple[Fraction, Fraction]],
) -> bool:
    """A measured purchase phase or a Round start bracket lies after the death."""
    t0 = native_time(states[segment[since]]["sample"])
    t1 = native_time(states[segment[now]]["sample"])
    if any(t0 <= lo and hi <= t1 for lo, hi in starts):
        return True
    return any(
        _anchor(states[segment[k]]["round"], {"BUY"}) for k in range(since + 1, now + 1)
    )


def _respawned(frame: dict[str, Any], weak: set[str]) -> bool:
    """Current owner HUD inside a measured BUY/ACTIVE phase, with no death cue."""
    return bool(
        "owner_hud" in weak
        and not weak & {
            "spectator", "remote", "death", "downed", "report",
            "recorder_elimination_display",
        }
        and frame["round"]["value"] in {"BUY", "ACTIVE"}
        and "UNKNOWN" not in frame["round"]["hypotheses"]
        and frame["camera"]["value"] in {"SELF", "UNKNOWN"}
    )


def _life_pass(
    states: list[dict[str, Any]], observations: dict[str, Any], segment: list[int],
    revise: _Reviser, starts: list[tuple[Fraction, Fraction]],
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
            or states[i]["camera"]["value"] in {"SELF", "REMOTE"}
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
    dead_at = 0
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
                dead_at = k
            continue
        current, _ = _nearest_score(states, segment, k, -1)
        if (
            dead_score is not None and current is not None
            and frame["life"]["value"] == "UNKNOWN"
            and frame["life"]["reason"] in {
                "return_edge_unobserved", "candidate_return_edge_unobserved"
            }
            and _respawned(frame, weak)
            and len(current) == len(dead_score)
            and all(c >= d for c, d in zip(current, dead_score, strict=True))
            and sum(current) > sum(dead_score)
            and _new_round_seen(states, segment, dead_at, k, starts)
        ):
            revise(frame, "life", "ALIVE", ["ALIVE"],
                   _score_ids(frame) + frame["camera"]["evidence_ids"],
                   "new_round_since_death_and_current_owner_hud")
    # An open death hypothesis cannot outlive the Round it was raised in: after a
    # higher score every player has respawned. Without a fresh death cue the
    # stale value is withdrawn; with a current owner HUD the recorder is alive.
    run_score: tuple[int, ...] | None = None
    run_at = 0
    for k, i in enumerate(segment):
        frame = states[i]
        life = frame["life"]
        if not (life["value"] == "DEAD" and "UNKNOWN" in life["hypotheses"]):
            if life["value"] != "UNKNOWN":
                run_score = None
            continue
        current, _ = _nearest_score(states, segment, k, -1)
        if run_score is None:
            run_score, run_at = current, k
            continue
        weak = _signals(_rows(frame, observations), strong_only=False)
        if (
            current is None or len(current) != len(run_score)
            or any(c < d for c, d in zip(current, run_score, strict=True))
            or sum(current) <= sum(run_score)
            or weak & {"death", "downed", "recorder_elimination_display", "spectator"}
        ):
            continue
        if _respawned(frame, weak) and _new_round_seen(states, segment, run_at, k, starts):
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
    transitions: list[dict[str, Any]] | None = None,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Return revision history and added unqualified event candidates."""
    revise = _Reviser(estimate)
    events: list[dict[str, Any]] = []
    for segment in _segments(states):
        _round_pass(states, observations, segment, revise, events)
        starts = [
            (native_time(e["lower_sample"]), native_time(e["upper_sample"]))
            for e in [*(transitions or []), *events] if e["kind"] == "round_start"
        ]
        _life_pass(states, observations, segment, revise, starts)
    _demote_current_view_maps(states, revise.history)
    _widen_score_display_ends(states, observations, transitions or [])
    _relocate_revised_edges(states, transitions or [])
    return revise.history, events


def _relocate_revised_edges(
    states: list[dict[str, Any]], transitions: list[dict[str, Any]]
) -> None:
    """Move a named edge whose lower frame already holds the edge's after-state.

    A revision or an earlier carry can show that the change happened before the
    rule edge. The edge moves to the first frame of that run, with the rule edge
    kept under ``rule_transition``.
    """
    index = {f["sample"]["sample_sha256"]: i for i, f in enumerate(states)}
    for event in transitions:
        domain = event.get("domain")
        if event["kind"] in {"state_change", "round_start", "round_end"} or domain not in {
            "round", "life", "camera"
        }:
            continue
        lo = index.get(event["lower_sample"]["sample_sha256"])
        if lo is None:
            continue
        after = event.get("after")
        if states[lo][domain]["value"] != after:
            continue
        m = lo
        while (
            m > 0 and states[m - 1][domain]["value"] == after
            and states[m]["continuity"].get("carry_allowed", False)
            and source_scope(states[m - 1]["sample"]) == source_scope(states[m]["sample"])
        ):
            m -= 1
        if m == 0 or not states[m]["continuity"].get("carry_allowed", False):
            continue
        event["rule_transition"] = deepcopy(event)
        event["lower_sample"] = deepcopy(states[m - 1]["sample"])
        event["upper_sample"] = deepcopy(states[m]["sample"])
        event["before"] = states[m - 1][domain]["value"]
        event["evidence_ids"] = sorted(set(event["evidence_ids"])
                                       | set(states[m][domain]["evidence_ids"]))
        event["edge_basis"] = "earliest_frame_of_revised_run"


def _widen_score_display_ends(
    states: list[dict[str, Any]], observations: dict[str, Any],
    transitions: list[dict[str, Any]],
) -> None:
    """Move score-update end brackets back to the last frame known undecided.

    An existing end edge whose lower frame is only the last old-score display may
    already follow the decision. Its lower bound moves to the latest measured
    ACTIVE cue, or old-score frame earlier than the update by the display lead.
    The rule's own lower sample is kept.
    """
    index = {f["sample"]["sample_sha256"]: i for i, f in enumerate(states)}
    for event in transitions:
        if event["kind"] != "round_end" or "basis" in event:
            continue
        lo = index.get(event["lower_sample"]["sample_sha256"])
        hi = index.get(event["upper_sample"]["sample_sha256"])
        if lo is None or hi is None:
            continue
        if _signals(_rows(states[lo], observations)) & {"active", "result"}:
            continue  # Already a measured ACTIVE (or result) frame.
        if states[hi]["round"]["reason"] != "score_change_and_later_result":
            continue
        t_hi = native_time(states[hi]["sample"])
        score = _scores(states[lo])
        k = lo
        while k > 0:
            prev = states[k - 1]
            if (
                not prev["continuity"].get("carry_allowed", False) and k - 1 != lo
                or not states[k]["continuity"].get("carry_allowed", False)
                or source_scope(prev["sample"]) != source_scope(states[lo]["sample"])
                or _scores(prev) - score
                or _signals(_rows(prev, observations)) & {"result", "buy", "intermission"}
            ):
                k = -1
                break
            k -= 1
            cues = _signals(_rows(states[k], observations))
            if "active" in cues or native_time(states[k]["sample"]) <= t_hi - DECISION_DISPLAY_LEAD:
                break
        if k < 0 or k == lo:
            continue
        event["rule_lower_sample"] = deepcopy(event["lower_sample"])
        event["lower_sample"] = deepcopy(states[k]["sample"])
        event["lower_sample_basis"] = "score_display_lead"


def _demote_current_view_maps(
    states: list[dict[str, Any]], history: list[dict[str, Any]]
) -> None:
    """Current recorder-view Map candidates require a living first-person view."""
    revised = {h["sample"]["sample_sha256"] for h in history}
    for frame in states:
        current = frame.get("map", {})
        if frame["sample"]["sample_sha256"] not in revised or not (
            current.get("current_self_position_candidates")
            or current.get("current_recorder_view_evidence_ids")
        ):
            continue
        if (
            frame["life"]["value"] == "ALIVE" and frame["camera"]["value"] == "SELF"
            and not set(frame["round"]["hypotheses"]) & {"ENDED", "INTERMISSION"}
        ):
            continue
        current["continuity_superseded_current_view"] = {
            "current_self_position_candidates": current.get(
                "current_self_position_candidates", []),
            "current_recorder_view_evidence_ids": current.get(
                "current_recorder_view_evidence_ids", []),
            "reason": current.get("reason"),
        }
        current["current_self_position_candidates"] = []
        current["current_recorder_view_evidence_ids"] = []
        current["reason"] = "current_view_gate_failed_after_continuity_revision"


def summarize(history: list[dict[str, Any]]) -> dict[str, Any]:
    """Counts of revised frames; withdrawn values are abstentions, not verified errors."""
    by_reason: dict[str, int] = {}
    withdrawn = 0
    for h in history:
        key = f'{h["domain"]}:{h["reason"]}'
        by_reason[key] = by_reason.get(key, 0) + 1
        if h["after"]["value"] == "UNKNOWN" and h["before"]["value"] != "UNKNOWN":
            withdrawn += 1
    return {
        "revised_frames_by_rule": dict(sorted(by_reason.items())),
        "withdrawn_to_unknown_frames": withdrawn,
        "withdrawn_meaning": "abstention_not_a_verified_error_count",
        "qualified": False,
    }


CONSISTENCY_RULES = (
    "dead_recorder_holds_first_person_view",
    "living_recorder_spectates",
    "dead_recorder_in_purchase_phase",
    "current_view_map_without_living_first_person_view",
    "edge_endpoint_disagrees_with_frame_state",
)


def consistency_violations(timeline: dict[str, Any]) -> dict[str, int]:
    """Count shared-state contradictions across frames, Map and edges."""
    counts = dict.fromkeys(CONSISTENCY_RULES, 0)
    points = {}
    for f in timeline["frames"]:
        points[f["sample"]["sample_sha256"]] = f
        life, camera, rnd = f["life"]["value"], f["camera"]["value"], f["round"]["value"]
        if life == "DEAD" and camera in {"SELF", "REMOTE"}:
            counts["dead_recorder_holds_first_person_view"] += 1
        if life == "ALIVE" and camera == "SPECTATOR":
            counts["living_recorder_spectates"] += 1
        if life == "DEAD" and rnd == "BUY":
            counts["dead_recorder_in_purchase_phase"] += 1
        current = f.get("map", {})
        if current.get("current_self_position_candidates") and not (
            life == "ALIVE" and camera == "SELF"
        ):
            counts["current_view_map_without_living_first_person_view"] += 1
    for e in timeline["transitions"]:
        domain = e.get("domain")
        if e["kind"] not in {"state_change", "spectator"} or domain not in {
            "round", "life", "camera"
        }:
            continue
        lower = points.get(e["lower_sample"]["sample_sha256"])
        upper = points.get(e["upper_sample"]["sample_sha256"])
        if lower is None or upper is None:
            continue
        if (e.get("before") != lower[domain]["value"]
                or e.get("after") != upper[domain]["value"]):
            counts["edge_endpoint_disagrees_with_frame_state"] += 1
    return counts


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
