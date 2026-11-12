"""Round context for the shared engine's unqualified event candidates."""

from __future__ import annotations

from copy import deepcopy
from fractions import Fraction
from typing import Any

from .evidence import native_time, source_scope

_ROUND_BREAKS = {"BUY", "ENDED", "INTERMISSION"}
ROUND_CONTEXT_SECONDS = Fraction(10)
_EVENTS = {
    "round_start", "round_end", "death", "death_hypothesis", "spectator",
    "return", "return_hypothesis", "view_target_change", "downed", "revival",
}


def _sample_id(frame: dict[str, Any]) -> str:
    return str(frame["sample"]["sample_sha256"])


def _scores(frame: dict[str, Any]) -> set[tuple[int, ...]]:
    return {
        tuple(row["displayed_score"])
        for row in frame["round_number"]["score_observations"] if row["eligible"]
    }


def _same_start(
    earlier: dict[str, Any], later: dict[str, Any], frames: list[dict[str, Any]], budget: Fraction
) -> bool:
    if source_scope(earlier["sample"]) != source_scope(later["sample"]):
        return False
    if _sample_id(earlier) == _sample_id(later):
        return bool(earlier["round"]["value"] == "ACTIVE")
    token = earlier["round_token"]
    return bool(
        token and later["round_token"] == token
        and earlier["round"]["value"] == later["round"]["value"] == "ACTIVE"
        and native_time(later["sample"]) - native_time(earlier["sample"]) <= budget
        and all(
            frame["round_token"] == token
            and frame["continuity"]["carry_allowed"]
            and frame["round"]["value"] not in _ROUND_BREAKS
            for frame in frames[1:]
        )
        and len(set().union(*(_scores(frame) for frame in frames))) <= 1
    )


def group_round_starts(
    events: list[dict[str, Any]], states: list[dict[str, Any]], budget: Fraction
) -> None:
    """Fold witnesses in one observed BUY context, preserving the first bracket."""
    positions = {_sample_id(frame): index for index, frame in enumerate(states)}
    retained: list[dict[str, Any]] = []
    last_by_scope: dict[tuple[str, ...], tuple[int, dict[str, Any]]] = {}
    for event in events:
        sample = event["upper_sample"]
        current = positions.get(sample["sample_sha256"])
        if event["kind"] != "round_start" or current is None:
            retained.append(event)
            continue
        scope = source_scope(sample)
        previous = last_by_scope.get(scope)
        if previous is not None:
            first, representative = previous
            if first <= current and _same_start(
                states[first], states[current], states[first:current + 1], budget
            ):
                if "round_start_witnesses" not in representative:
                    representative["round_start_witnesses"] = [deepcopy(representative)]
                representative["round_start_witnesses"].append(deepcopy(event))
                representative["evidence_ids"] = sorted(
                    set(representative["evidence_ids"]) | set(event["evidence_ids"])
                )
                representative["round_start_group_basis"] = "same_observed_round_context"
                continue
        retained.append(event)
        last_by_scope[scope] = current, event
    events[:] = retained


def _endpoint(
    states: list[dict[str, Any]], index: int | None, direction: int, budget: Fraction
) -> dict[str, Any]:
    if index is None:
        return {"candidates": [], "evidence_ids": [], "samples": [], "basis": "missing_endpoint"}
    frame = states[index]
    number = frame["round_number"]
    candidates = set(number["candidates"])
    evidence = set(number["evidence_ids"])
    samples = [frame["sample"]]
    basis = "endpoint_score_and_phase"
    token = frame["round_token"]
    when = native_time(frame["sample"])
    # A nearby direct reading can support the endpoint only inside an observed
    # Round token. Current conflicting scores remain competing observations.
    if token and number["value"] is None and len(_scores(frame)) <= 1:
        cursor = index + direction
        previous = index
        while 0 <= cursor < len(states):
            nearby = states[cursor]
            link = states[max(cursor, previous)]["continuity"]
            if (
                source_scope(nearby["sample"]) != source_scope(frame["sample"])
                or nearby["round_token"] != token
                or not link["carry_allowed"]
                or abs(native_time(nearby["sample"]) - when) > budget
                or nearby["round"]["value"] == "INTERMISSION"
                or nearby["round"]["value"] == "ENDED"
                and frame["round"]["value"] != "ENDED"
                or direction > 0 and nearby["round"]["value"] == "BUY"
                and frame["round"]["value"] != "BUY"
                or len(_scores(nearby)) > 1
            ):
                break
            value = nearby["round_number"]["value"]
            if value is not None:
                if not candidates or value in candidates:
                    candidates = {value}
                    evidence.update(nearby["round_number"]["evidence_ids"])
                    samples.append(nearby["sample"])
                    basis = "bounded_direct_score_in_same_round"
                else:
                    candidates.add(value)
                    evidence.update(nearby["round_number"]["evidence_ids"])
                    samples.append(nearby["sample"])
                    basis = "conflicting_endpoint_and_nearby_round"
                break
            previous, cursor = cursor, cursor + direction
    return {
        "candidates": sorted(candidates), "evidence_ids": sorted(evidence),
        "samples": samples, "basis": basis,
    }


def _previous_round_on_return(
    states: list[dict[str, Any]], low: int, high: int, budget: Fraction
) -> int | None:
    before, after = states[low], states[high]
    destination = after["round_number"]["value"]
    if (
        low >= high or type(destination) is not int or destination <= 1
        or before["round"]["value"] != "ENDED" or after["round"]["value"] != "BUY"
        or not before["round_token"] or not after["round_token"]
        or before["round_token"] == after["round_token"]
        or native_time(after["sample"]) - native_time(before["sample"]) > budget
    ):
        return None
    scores = _scores(after)
    if len(scores) != 1 or _scores(before) != scores:
        return None
    # Same settled score at the ending and directly observed next BUY.
    # An ACTIVE frame, another token or an inconsistent score breaks the link.
    for frame in states[low + 1:high + 1]:
        if (
            not frame["continuity"]["carry_allowed"]
            or frame["round"]["value"] in {"ACTIVE", "INTERMISSION"}
            or frame["round_token"] not in {before["round_token"], after["round_token"]}
            or not _scores(frame) <= scores
        ):
            return None
    return destination - 1


def attach_event_round_context(
    events: list[dict[str, Any]], states: list[dict[str, Any]], budget: Fraction
) -> None:
    """Annotate event endpoints without changing native time or state estimates."""
    positions = {_sample_id(frame): index for index, frame in enumerate(states)}
    for event in events:
        if event["kind"] not in _EVENTS:
            continue
        low = positions.get(event["lower_sample"]["sample_sha256"])
        high = positions.get(event["upper_sample"]["sample_sha256"])
        if (
            source_scope(event["lower_sample"]) != source_scope(event["upper_sample"])
            or low is not None and high is not None and low > high
        ):
            low = high = None
        source = _endpoint(states, low, -1, budget)
        destination = _endpoint(states, high, 1, budget)
        if (
            event["kind"] in {"return", "return_hypothesis"}
            and low is not None and high is not None
        ):
            previous = _previous_round_on_return(states, low, high, budget)
            if previous is not None and previous in source["candidates"]:
                source = {
                    "candidates": [previous],
                    "evidence_ids": sorted(
                        set(source["evidence_ids"]) | set(destination["evidence_ids"])
                    ),
                    "samples": [*source["samples"], states[high]["sample"]],
                    "basis": "settled_ending_score_and_observed_next_buy",
                }
        left, right = set(source["candidates"]), set(destination["candidates"])
        if event["kind"] == "round_end":
            membership = left or right
        elif event["kind"] in {"return", "return_hypothesis", "round_start"}:
            membership = right
        else:
            membership = (left & right) or (left | right)
        crosses_round = bool(left and right and left.isdisjoint(right))
        if crosses_round and event["kind"] not in {"return", "return_hypothesis"}:
            membership = left | right
        event["round_membership"] = {
            "contract": "development_event_round_context_v1",
            "source": source, "destination": destination,
            "candidates": sorted(membership),
            "status": "UNKNOWN" if not membership else
            "CANDIDATE" if len(membership) == 1 else "AMBIGUOUS",
            "cross_round_candidate": crosses_round,
            "evidence_ids": sorted(set(source["evidence_ids"]) | set(destination["evidence_ids"])),
            "unknown_possible": True, "qualified": False,
        }
