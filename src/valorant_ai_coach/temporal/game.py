"""Single development owner of Round/life/camera state for HUD and Map.

One-second rows are views over retained exact observations and event brackets.
No path from this module issues Production Facts/Events or qualified ownership.
"""

from __future__ import annotations

from collections import defaultdict
from copy import deepcopy
from enum import StrEnum
from fractions import Fraction
from typing import Any, Literal, TypedDict

from .evidence import digest, freeze_native_sample, is_sha, native_time, source_scope

VERSION = "development_game_timeline_v1"


class RoundState(StrEnum):
    BUY = "BUY"
    ACTIVE = "ACTIVE"
    ENDED = "ENDED"
    INTERMISSION = "INTERMISSION"
    UNKNOWN = "UNKNOWN"


class RecorderLife(StrEnum):
    ALIVE = "ALIVE"
    DEAD = "DEAD"
    DOWNED = "DOWNED"
    UNKNOWN = "UNKNOWN"


class CameraState(StrEnum):
    SELF = "SELF"
    SPECTATOR = "SPECTATOR"
    REMOTE = "REMOTE"
    UNKNOWN = "UNKNOWN"


class MapState(TypedDict):
    observation_present: bool
    candidates: list[dict[str, Any]]
    current_self_position_candidates: list[dict[str, Any]]
    zone_candidates: list[dict[str, Any]]
    marker_associations: list[dict[str, Any]]
    status: Literal["CANDIDATES", "UNKNOWN"]
    reason: str
    ownership: Literal["UNKNOWN"]
    qualified: Literal[False]


DOMAINS = {"round": RoundState, "life": RecorderLife, "camera": CameraState}
SIGNALS = {
    "buy",
    "active",
    "result",
    "intermission",
    "owner_hud",
    "spectator",
    "remote",
    "death",
    "downed",
    "revival",
    "ability_return",
    "report",
    "hud_not_detected",
}


def observation(
    *,
    sample: dict[str, Any],
    producer: str,
    signals: list[str],
    raw: dict[str, Any],
    context: dict[str, Any] | None = None,
    continuity: dict[str, Any] | None = None,
    map_candidates: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Normalize supplier evidence; a caller's signals are unqualified claims."""
    frozen = freeze_native_sample(sample)
    if not is_sha(producer) or not isinstance(signals, list) or not set(signals) <= SIGNALS:
        raise ValueError("Known observation signals and producer fingerprint required")
    row = {
        "sample": frozen,
        "producer_fingerprint": producer,
        "signals": sorted(set(signals)),
        "raw": deepcopy(raw),
        "context": deepcopy(context or {}),
        "continuity": deepcopy(continuity or {}),
        "map_candidates": deepcopy(map_candidates or []),
        "qualification": "development_only",
    }
    row["observation_id"] = digest(row)
    return row


def _estimate(
    value: str = "UNKNOWN",
    *,
    alternatives: list[str] | None = None,
    reason: str = "unobserved",
    evidence: list[str] | None = None,
    origin: str = "temporal_inference",
) -> dict[str, Any]:
    return {
        "value": value,
        "hypotheses": sorted(set(alternatives or [value])),
        "reason": reason,
        "evidence_ids": sorted(set(evidence or [])),
        "origin": origin,
        "uncertainty": "unresolved" if value == "UNKNOWN" else "development_unqualified",
    }


def continuity_between(
    prior: dict[str, Any] | None, current: dict[str, Any], *, max_gap: Fraction
) -> dict[str, Any]:
    """Acquisition proximity allows bounded inference; it never proves game continuity."""
    sample = current["sample"]
    cues = [r["continuity"] for r in current["observations"]]
    broken = any(
        c.get("discontinuity") is True
        or c.get("source_discontinuity") is True
        or c.get("decode_ok") is False
        or c.get("content_break_confirmed") is True
        for c in cues
    )
    if prior is None:
        reason, carry = "first_observation", False
    elif source_scope(prior["sample"]) != source_scope(sample):
        reason, carry = "source_or_epoch_change", False
    elif broken:
        reason, carry = "confirmed_break_or_decode_failure", False
    elif not 0 < native_time(sample) - native_time(prior["sample"]) <= max_gap:
        reason, carry = "uncovered_gap", False
    elif any(
        prior["fingerprints"][kind] != config
        for kind, config in current["fingerprints"].items()
        if kind in prior["fingerprints"]
    ):
        reason, carry = "producer_or_profile_change", False
    else:
        reason, carry = "bounded_native_context", True
    return {
        "carry_allowed": carry,
        "reason": reason,
        "acquisition": "discontinuous" if broken else "compatible" if carry else "UNKNOWN",
        "semantic": "UNKNOWN",
        "confirmed_cut": any(c.get("content_break_confirmed") is True for c in cues),
        "duplicate_pixels": bool(
            prior and sample["native_pixel_sha256"] == prior["sample"]["native_pixel_sha256"]
        ),
    }


class DevelopmentGameTimeline:
    """Replayable evidence ledger with deterministic offline revision.

    Update/retract by observation ID then rebuild; consumers use one revision.
    Multiple producers at one physical frame are fused before temporal inference.
    Short UI dropouts retain a hypothesis; missing current coordinates never fill.
    """

    def __init__(
        self, *, max_carry_seconds: Fraction = Fraction(2), future_seconds: Fraction = Fraction(3)
    ) -> None:
        if max_carry_seconds <= 0 or future_seconds <= 0:
            raise ValueError("Positive finite windows required")
        self.max_carry = max_carry_seconds
        self.future = future_seconds
        self._observations: dict[str, dict[str, Any]] = {}
        self._revision = 0
        self._history: list[dict[str, Any]] = []
        self._last: dict[str, Any] | None = None

    def add(self, row: dict[str, Any]) -> None:
        expected = observation(
            sample=row["sample"],
            producer=row["producer_fingerprint"],
            signals=row["signals"],
            raw=row["raw"],
            context=row["context"],
            continuity=row["continuity"],
            map_candidates=row["map_candidates"],
        )
        if expected != row:
            raise ValueError("Observation contract/digest mismatch")
        self._observations[row["observation_id"]] = deepcopy(row)

    def retract(self, observation_id: str) -> None:
        del self._observations[observation_id]

    def rebuild(self) -> dict[str, Any]:
        grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for obs in self._observations.values():
            grouped[obs["sample"]["sample_sha256"]].append(obs)
        frames = []
        physical: dict[tuple[Any, ...], dict[str, Any]] = {}
        for rows in grouped.values():
            sample = deepcopy(rows[0]["sample"])
            key = (*source_scope(sample), sample["native_pts_tick"])
            if key in physical and physical[key] != sample:
                raise ValueError("Conflicting pixels at exact source/epoch/PTS")
            physical[key] = sample
            rows.sort(key=lambda r: r["observation_id"])
            frames.append(
                {
                    "sample": sample,
                    "observations": rows,
                    "signals": sorted({s for r in rows for s in r["signals"]}),
                    "fingerprints": {
                        kind: sorted(
                            {
                                (
                                    r["producer_fingerprint"],
                                    str(r["context"].get("profile_fingerprint", "")),
                                )
                                for r in rows
                                if r["context"].get("stream_kind", "generic") == kind
                            }
                        )
                        for kind in {r["context"].get("stream_kind", "generic") for r in rows}
                    },
                }
            )
        frames.sort(key=lambda f: (source_scope(f["sample"]), native_time(f["sample"])))
        self._revision += 1
        states: list[dict[str, Any]] = []
        transitions: list[dict[str, Any]] = []
        boundary_candidates: list[dict[str, Any]] = []
        prior: dict[str, Any] | None = None
        last_direct: dict[str, tuple[Fraction, dict[str, Any]]] = {}
        round_token: str | None = None
        self_token: str | None = None
        death_latch: str | None = None
        last_dead: dict[str, Any] | None = None
        last_alive: dict[str, Any] | None = None
        last_score_frame: dict[str, Any] | None = None
        last_clock: tuple[Fraction, int, tuple[int, int] | None] | None = None
        for i, frame in enumerate(frames):
            link = continuity_between(prior, frame, max_gap=self.max_carry)
            same = bool(prior and source_scope(prior["sample"]) == source_scope(frame["sample"]))
            if link["carry_allowed"] and prior is not None:
                frame["fingerprints"] = {**prior["fingerprints"], **frame["fingerprints"]}
            if not link["carry_allowed"]:
                last_direct = {}
                last_clock = None
                last_score_frame = None
                round_token, self_token = None, None
                death_latch, last_alive, last_dead = None, None, None
            ids = [r["observation_id"] for r in frame["observations"]]
            signals = set(frame["signals"])
            now = native_time(frame["sample"])
            current = {domain: _estimate() for domain in DOMAINS}
            choices: dict[str, list[str]] = {
                "round": [
                    state
                    for signal, state in (
                        ("buy", "BUY"),
                        ("active", "ACTIVE"),
                        ("result", "ENDED"),
                        ("intermission", "INTERMISSION"),
                    )
                    if signal in signals
                ],
                "life": [
                    state
                    for signal, state in (
                        ("owner_hud", "ALIVE"),
                        ("death", "DEAD"),
                        ("downed", "DOWNED"),
                    )
                    if signal in signals
                ],
                "camera": [
                    state
                    for signal, state in (
                        ("owner_hud", "SELF"),
                        ("spectator", "SPECTATOR"),
                        ("remote", "REMOTE"),
                    )
                    if signal in signals
                ],
            }
            # A small active clock remains contextually ACTIVE below the buy-clock
            # ambiguity range only when its observed countdown and score agree.
            clocks = {
                r["context"]["timer_seconds"]
                for r in frame["observations"]
                if r["context"].get("timer_seconds") is not None
            }
            clock = next(iter(clocks)) if len(clocks) == 1 else None
            if (
                clock is not None
                and last_clock is not None
                and states
                and states[-1]["round"]["value"] == "ACTIVE"
                and not choices["round"]
                and self._score(frame) == last_clock[2]
                and 0 <= last_clock[1] - clock <= float(now - last_clock[0]) + 1
            ):
                choices["round"] = ["ACTIVE"]
            if clock is not None:
                last_clock = now, clock, self._score(frame)
            # A score update requires future measured result support, not PTS proximity.
            score = self._score(frame)
            score_before = last_score_frame
            if (
                score_before is not None
                and now - native_time(score_before["sample"]) > self.max_carry
            ):
                score_before = None
            prior_score = self._score(score_before)
            end_support: list[str] = []
            if (
                same
                and link["carry_allowed"]
                and score
                and prior_score
                and score_before is not None
                and (
                    score[0] >= prior_score[0]
                    and score[1] >= prior_score[1]
                    and sum(score) - sum(prior_score) == 1
                )
            ):
                confirmation = None
                forward_prior = frame
                for j in range(i, len(frames)):
                    later = frames[j]
                    if (
                        source_scope(later["sample"]) != source_scope(frame["sample"])
                        or native_time(later["sample"]) - now > self.future
                    ):
                        break
                    if (
                        j > i
                        and not continuity_between(forward_prior, later, max_gap=self.max_carry)[
                            "carry_allowed"
                        ]
                    ):
                        break
                    forward_prior = {
                        **later,
                        "fingerprints": {**forward_prior["fingerprints"], **later["fingerprints"]},
                    }
                    if "result" in later["signals"]:
                        end_support.extend(r["observation_id"] for r in later["observations"])
                        if confirmation is None:
                            confirmation = later["sample"]
                boundary = {
                    "kind": "round_end",
                    "lower_sample": score_before["sample"],
                    "upper_sample": frame["sample"],
                    "internal_game_event_time": None,
                }
                boundary["candidate_id"] = digest(boundary)
                boundary_candidates.append(
                    {
                        **boundary,
                        "status": "context_supported" if end_support else "pending",
                        "confirmation_sample": confirmation,
                        "evidence_ids": ids
                        + end_support
                        + [r["observation_id"] for r in score_before["observations"]],
                    }
                )
                if end_support:
                    end_support.extend(r["observation_id"] for r in score_before["observations"])
                    choices["round"] = ["ENDED"]
            if score is not None:
                last_score_frame = frame
            for domain, values in choices.items():
                if len(set(values)) > 1:
                    current[domain] = _estimate(
                        alternatives=values,
                        reason="conflicting_observations",
                        evidence=ids,
                        origin="observation_projection",
                    )
                    last_direct.pop(domain, None)
                elif values:
                    current[domain] = _estimate(
                        values[0],
                        evidence=ids + end_support,
                        reason="score_change_and_later_result"
                        if end_support and domain == "round"
                        else "current_observation",
                        origin="temporal_inference"
                        if end_support and domain == "round"
                        else "observation_projection",
                    )
                    last_direct[domain] = now, deepcopy(current[domain])
                elif domain in last_direct and now - last_direct[domain][0] <= self.max_carry:
                    current[domain] = deepcopy(last_direct[domain][1])
                    current[domain].update(
                        reason="bounded_missing_observation",
                        origin="temporal_inference",
                        uncertainty="continuation_unverified",
                    )
            previous_state = states[-1] if states and link["carry_allowed"] else None
            previous_round = previous_state["round"]["value"] if previous_state else "UNKNOWN"
            if current["round"]["value"] == "BUY" and previous_round != "BUY":
                round_token = digest({"buy": frame["sample"]["sample_sha256"]})
                self_token = None
            returned = False
            if "owner_hud" in signals and death_latch:
                reentry = bool(round_token and previous_round == "BUY")
                if "revival" in signals or reentry:
                    death_latch = None
                    returned = True
                else:
                    current["life"] = _estimate(
                        alternatives=["DEAD", "ALIVE"],
                        reason="return_edge_unobserved",
                        evidence=ids,
                    )
                    current["camera"] = _estimate(
                        alternatives=["SELF", "SPECTATOR"],
                        reason="return_edge_unobserved",
                        evidence=ids,
                    )
                    last_direct.pop("life", None)
                    last_direct.pop("camera", None)
            if current["life"]["value"] in {"DEAD", "DOWNED"} and signals & {"death", "downed"}:
                death_latch = current["life"]["value"]
                last_dead = frame["sample"]
            if "spectator" in signals and not death_latch:
                # Preserve competing life explanations. Spectator UI is a camera observation.
                current["life"] = _estimate(
                    alternatives=["DEAD", "UNKNOWN"],
                    reason="spectator_death_hypothesis",
                    evidence=ids,
                )
                last_direct.pop("life", None)
            elif (
                death_latch and "owner_hud" not in signals and current["life"]["value"] == "UNKNOWN"
            ):
                current["life"] = _estimate(
                    death_latch,
                    reason="observed_death_latch",
                    evidence=ids + (states[-1]["life"]["evidence_ids"] if states else []),
                )
            if (
                "report" in signals
                and "hud_not_detected" in signals
                and not signals & {"owner_hud", "spectator", "remote", "death", "downed"}
            ):
                current["life"] = _estimate(
                    reason="unresolved_report_and_missing_hud", evidence=ids
                )
                current["camera"] = _estimate(
                    reason="unresolved_report_and_missing_hud", evidence=ids
                )
                last_direct.pop("life", None)
                last_direct.pop("camera", None)
            if (
                current["life"]["value"] == "ALIVE"
                and current["camera"]["value"] == "SELF"
                and "owner_hud" in signals
            ):
                last_alive = frame["sample"]
                self_token = round_token
            frame_state = {
                "sample": frame["sample"],
                **current,
                "continuity": link,
                "observation_ids": ids,
                "round_token": round_token,
                "self_view_round_token": self_token,
                "tracking_epoch": digest(
                    {
                        "scope": source_scope(frame["sample"]),
                        "reset_at": frame["sample"]["sample_sha256"],
                    }
                )
                if not link["carry_allowed"]
                else states[-1]["tracking_epoch"],
                "qualification": "development_only",
                "ownership": "UNKNOWN",
            }
            frame_state["transition_hypotheses"] = []
            if (
                previous_state
                and last_alive is not None
                and previous_state["life"]["value"] == "ALIVE"
                and previous_state["camera"]["value"] == "SELF"
                and current["camera"]["value"] == "SPECTATOR"
            ):
                frame_state["transition_hypotheses"].append(
                    {
                        "kind": "recorder_death",
                        "status": "competing_hypothesis",
                        "lower_sample": last_alive,
                        "upper_sample": frame["sample"],
                        "internal_game_event_time": None,
                        "alternatives": ["death_to_spectator", "owner_link_unresolved"],
                        "evidence_ids": previous_state["life"]["evidence_ids"] + ids,
                        "qualified": False,
                    }
                )
            if returned and last_dead is not None:
                transitions.append(
                    {
                        "kind": "return",
                        "domain": "life",
                        "before": "DEAD_OR_DOWNED",
                        "after": "ALIVE",
                        "lower_sample": last_dead,
                        "upper_sample": frame["sample"],
                        "evidence_ids": ids,
                        "internal_game_event_time": None,
                        "status": "development_candidate",
                        "last_alive_sample": None,
                    }
                )
            if previous_state:
                for domain in DOMAINS:
                    before, after = previous_state[domain]["value"], current[domain]["value"]
                    if before != after:
                        kind = (
                            "round_start"
                            if domain == "round" and before == "BUY" and after == "ACTIVE"
                            else "round_end"
                            if domain == "round"
                            and after == "ENDED"
                            and (before == "ACTIVE" or bool(end_support))
                            else "death"
                            if domain == "life" and before == "ALIVE" and after == "DEAD"
                            else "spectator"
                            if domain == "camera" and after == "SPECTATOR"
                            else "state_change"
                        )
                        transitions.append(
                            {
                                "kind": kind,
                                "domain": domain,
                                "before": before,
                                "after": after,
                                "lower_sample": score_before["sample"]
                                if kind == "round_end" and end_support and score_before
                                else previous_state["sample"],
                                "upper_sample": frame["sample"],
                                "evidence_ids": sorted(
                                    set(
                                        previous_state[domain]["evidence_ids"]
                                        + current[domain]["evidence_ids"]
                                    )
                                ),
                                "internal_game_event_time": None,
                                "status": "development_candidate",
                                "last_alive_sample": last_alive if kind == "spectator" else None,
                            }
                        )
            candidates = [deepcopy(c) for r in frame["observations"] for c in r["map_candidates"]]
            gate = (
                current["life"]["value"] == "ALIVE"
                and current["camera"]["value"] == "SELF"
                and current["round"]["value"] in {"BUY", "ACTIVE"}
            )
            self_candidates = []
            if gate:
                for record in frame["observations"]:
                    packet = record["raw"]
                    selected = packet.get("initial_candidate_index")
                    if (
                        packet.get("schema") == "map_consumer_provisional_v1"
                        and packet.get("pool", {}).get("candidates") == record["map_candidates"]
                        and type(selected) is int
                        and 0 <= selected < len(record["map_candidates"])
                    ):
                        self_candidates.append(deepcopy(record["map_candidates"][selected]))
            frame_state["map"] = {
                "observation_present": bool(candidates)
                or any(
                    r["raw"].get("schema") == "map_consumer_provisional_v1"
                    for r in frame["observations"]
                ),
                "zone_candidates": [
                    c["zone_candidate"]
                    for c in candidates
                    if isinstance(c.get("zone_candidate"), dict)
                ],
                "marker_associations": [
                    deepcopy(a)
                    for r in frame["observations"]
                    for a in r["raw"].get("marker_associations", [])
                ],
                "candidates": candidates,
                "current_self_position_candidates": self_candidates,
                "status": "CANDIDATES" if candidates else "UNKNOWN",
                "reason": "common_state_allows_development_candidates"
                if gate
                else "self_state_unresolved",
                "ownership": "UNKNOWN",
                "qualified": False,
            }
            states.append(frame_state)
            prior = frame
        # Bounded bidirectional reconciliation: only fill a missing same-state hypothesis.
        # No smoothing across a conflict, reset, life edge or camera edge.
        self._reconcile(states)
        acquisition_seconds = self._seconds(states)
        result = {
            "version": VERSION,
            "revision": self._revision,
            "observations": deepcopy(list(self._observations.values())),
            "frames": states,
            "transitions": transitions,
            "boundary_candidates": boundary_candidates,
            "round_candidate_groups": self._round_candidate_groups(transitions),
            "seconds": self._common_seconds(acquisition_seconds),
            "acquisition_seconds": acquisition_seconds,
            "qualified_facts": [],
            "qualified_events": [],
            "formal_outputs": 0,
        }
        changed = []
        if self._last:
            old = {s["sample"]["sample_sha256"]: s for s in self._last["frames"]}
            changed = [
                s["sample"]["sample_sha256"]
                for s in states
                if s["sample"]["sample_sha256"] in old and s != old[s["sample"]["sample_sha256"]]
            ]
        self._history.append(
            {
                "revision": self._revision,
                "input_fingerprint": digest(sorted(self._observations)),
                "revised_sample_ids": changed,
                "candidate_statuses": {c["candidate_id"]: c["status"] for c in boundary_candidates},
            }
        )
        result["revision_history"] = deepcopy(self._history)
        self._last = {"frames": deepcopy(states)}
        return result

    @staticmethod
    def _score(frame: dict[str, Any] | None) -> tuple[int, int] | None:
        scores = (
            {
                tuple(r["context"]["score"])
                for r in frame["observations"]
                if r["context"].get("score") is not None
            }
            if frame
            else set()
        )
        return next(iter(scores)) if len(scores) == 1 else None

    def _reconcile(self, states: list[dict[str, Any]]) -> None:
        for domain in DOMAINS:
            anchor: dict[str, Any] | None = None
            missing: list[dict[str, Any]] = []
            for state in states:
                est = state[domain]
                if not state["continuity"]["carry_allowed"]:
                    anchor, missing = None, []
                if est["reason"] == "conflicting_observations":
                    anchor, missing = None, []
                elif est["value"] == "UNKNOWN":
                    if est["reason"] == "unobserved":
                        missing.append(state)
                    else:
                        anchor, missing = None, []
                else:
                    if (
                        anchor
                        and anchor[domain]["value"] == est["value"]
                        and native_time(state["sample"]) - native_time(anchor["sample"])
                        <= self.future
                    ):
                        for item in missing:
                            item[domain] = _estimate(
                                est["value"],
                                reason="bracketed_same_state_hypothesis",
                                evidence=anchor[domain]["evidence_ids"] + est["evidence_ids"],
                            )
                            item[domain]["uncertainty"] = "continuation_unverified"
                    anchor, missing = state, []

    @staticmethod
    def _seconds(states: list[dict[str, Any]]) -> list[dict[str, Any]]:
        scopes: dict[tuple[str, ...], list[dict[str, Any]]] = defaultdict(list)
        for state in states:
            scopes[source_scope(state["sample"])].append(state)
        seconds = []
        for scope, rows in scopes.items():
            bins: dict[int, list[dict[str, Any]]] = defaultdict(list)
            for row in rows:
                bins[int(native_time(row["sample"]) // 1)].append(row)
            if max(bins) - min(bins) > 100_000:
                raise ValueError("Timeline extent exceeds development bound")
            for second in range(min(bins), max(bins) + 1):
                items = bins.get(second, [])
                summary: dict[str, Any] = {
                    "source_scope": list(scope),
                    "second": second,
                    "sample_ids": [r["sample"]["sample_sha256"] for r in items],
                    "observation_present": bool(items),
                    "coverage": "sampled_points_only",
                    "map_observation_count": sum(r["map"]["observation_present"] for r in items),
                }
                for domain in DOMAINS:
                    values = sorted({r[domain]["value"] for r in items}) or ["UNKNOWN"]
                    summary[domain] = {
                        "value": values[0] if len(values) == 1 else "UNKNOWN",
                        "within_second_states": values,
                        "last_observed_state": items[-1][domain]["value"] if items else "UNKNOWN",
                    }
                seconds.append(summary)
        return seconds

    @staticmethod
    def _round_candidate_groups(transitions: list[dict[str, Any]]) -> list[dict[str, Any]]:
        # Overlapping display brackets are possible repeats across acquisitions,
        # never independent events merely because their acquisition IDs differ.
        groups: list[dict[str, Any]] = []
        rows = [t for t in transitions if t["kind"] in {"round_start", "round_end"}]
        rows.sort(
            key=lambda t: (
                t["upper_sample"]["source_sha256"],
                t["kind"],
                native_time(t["lower_sample"]),
            )
        )
        for row in rows:
            lower, upper = native_time(row["lower_sample"]), native_time(row["upper_sample"])
            key = row["upper_sample"]["source_sha256"], row["kind"]
            if (
                groups
                and tuple(groups[-1]["source_and_kind"]) == key
                and lower <= Fraction(groups[-1]["upper_time"])
            ):
                group = groups[-1]
                group["members"].append(row)
                group["upper_time"] = str(max(upper, Fraction(group["upper_time"])))
            else:
                groups.append(
                    {
                        "source_and_kind": list(key),
                        "lower_time": str(lower),
                        "upper_time": str(upper),
                        "members": [row],
                        "semantics": "overlapping_evidence_brackets_not_verified_event_identity",
                    }
                )
        return groups

    @staticmethod
    def _common_seconds(acquisitions: list[dict[str, Any]]) -> list[dict[str, Any]]:
        # One Source-native clock, parallel acquisition evidence lanes. No state
        # carries between lanes; no absent interval is counted as a negative.
        sources: dict[tuple[str, str, str], dict[int, list[dict[str, Any]]]] = {}
        for acquisition in acquisitions:
            scope = acquisition["source_scope"]
            key = scope[0], scope[1], scope[4]
            sources.setdefault(key, {}).setdefault(acquisition["second"], []).append(acquisition)
        result = []
        for key, bins in sorted(sources.items()):
            if max(bins) - min(bins) > 100_000:
                raise ValueError("Common Source clock exceeds development extent bound")
            for second in range(min(bins), max(bins) + 1):
                views = bins.get(second, [])
                row: dict[str, Any] = {
                    "source_id": key[0],
                    "source_sha256": key[1],
                    "native_time_base": key[2],
                    "second": second,
                    "acquisition_views": views,
                    "observation_present": any(v["observation_present"] for v in views),
                    "sample_ids": sorted({s for v in views for s in v["sample_ids"]}),
                    "coverage": "sampled_points_only",
                    "map_observation_count": sum(v["map_observation_count"] for v in views),
                }
                for domain in DOMAINS:
                    values = sorted({s for v in views for s in v[domain]["within_second_states"]})
                    values = values or ["UNKNOWN"]
                    row[domain] = {
                        "value": values[0] if len(values) == 1 else "UNKNOWN",
                        "within_second_states": values,
                        "acquisition_consensus": len(values) == 1,
                    }
                result.append(row)
        return result


def map_context(
    frame_state: dict[str, Any], *, producer_fingerprint: str, revision: str
) -> dict[str, Any]:
    """Connect to Map supplier's provisional consumer, without declaring continuity."""
    if not is_sha(producer_fingerprint) or not revision:
        raise ValueError("Common producer fingerprint/revision required")
    result = {
        "schema": "map_consumer_provisional_v1",
        "sample_sha256": frame_state["sample"]["sample_sha256"],
        "origin": "common_engine",
        "producer_fingerprint": producer_fingerprint,
        "revision": revision,
        "tracking_epoch": frame_state["tracking_epoch"],
        "round_state": frame_state["round"]["value"],
        "recorder_life": frame_state["life"]["value"],
        "camera": frame_state["camera"]["value"],
        "recorder_correspondence": "supported"
        if frame_state["life"]["value"] == "ALIVE" and frame_state["camera"]["value"] == "SELF"
        else "UNKNOWN",
        "source_continuity": "UNKNOWN",
        "round_token": frame_state["round_token"],
        "self_view_round_token": frame_state["self_view_round_token"],
        "evidence_sha256s": frame_state["observation_ids"],
        "qualification": "development_only",
        "ownership": "UNKNOWN",
        "formal_outputs": 0,
    }
    result["context_sha256"] = digest(result)
    return result
