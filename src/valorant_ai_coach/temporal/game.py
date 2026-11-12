"""Single development owner of Round/life/camera state for HUD and Map.

One-second rows are views over retained exact observations and event brackets.
No path from this module issues Production Facts/Events or qualified ownership.
"""

from __future__ import annotations

import math
from collections import defaultdict
from copy import deepcopy
from enum import StrEnum
from fractions import Fraction
from pathlib import Path
from typing import Any, Literal, NotRequired, TypedDict

from .evidence import digest, freeze_native_sample, is_sha, native_time, source_scope
from .map_roles import CONTRACT as MAP_ROLE_CONTRACT
from .map_roles import provisional_map_roles, rule_sha256
from .zone_contract import ZONE_CONTEXT_CONTRACT, viewed_zone_candidate

VERSION = "development_game_timeline_v2"


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
    map_name_candidates: NotRequired[list[dict[str, Any]]]
    generic_observation_ids: NotRequired[list[str]]
    observation_present: bool
    candidates: list[dict[str, Any]]
    current_self_position_candidates: list[dict[str, Any]]
    current_recorder_view_evidence_ids: list[str]
    temporal_path_eligible: Literal[False]
    current_view_contract: Literal["development_current_map_v1"]
    zone_candidates: list[dict[str, Any]]
    current_recorder_zone_candidates: list[dict[str, Any]]
    zone_observation_ids: list[str]
    zone_context_contract: Literal["development_zone_context_v1"]
    marker_associations: list[dict[str, Any]]
    status: Literal["CANDIDATES", "UNKNOWN"]
    reason: str
    ownership: Literal["UNKNOWN"]
    qualified: Literal[False]


DOMAINS = {"round": RoundState, "life": RecorderLife, "camera": CameraState}
_REPORT_VIEW_BARRIERS = frozenset({
    "spectator", "remote", "death", "downed", "revival",
    "recorder_elimination_display", "result", "intermission",
})
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
    "recorder_elimination_display",
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
    if (
        context
        and "unqualified_view_model" in context
        and type(context["unqualified_view_model"]) is not bool
    ):
        raise ValueError("unqualified_view_model must be a boolean")
    if (
        context
        and "elimination_display_signature" in context
        and not is_sha(context["elimination_display_signature"])
    ):
        raise ValueError("elimination_display_signature must be a SHA256")
    if context and "unqualified_round_model" in context:
        if type(context["unqualified_round_model"]) is not bool:
            raise ValueError("unqualified_round_model must be a boolean")
        if context["unqualified_round_model"] and (
            not set(signals) <= {"active"}
            or {"score", "timer_seconds"} & set(context)
            or map_candidates
        ):
            raise ValueError("Round model supplies only an unqualified active display claim")
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


def _round_number(state: dict[str, Any], rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Current score/phase candidates; no event count or previous-number carry."""
    scores = []
    for row in rows:
        score = row["context"].get("score")
        if score is None:
            continue
        valid = (
            isinstance(score, (list, tuple))
            and len(score) == 2
            and all(type(v) is int and 0 <= v <= 99 for v in score)
            and row["continuity"].get("decode_ok") is not False
        )
        scores.append(
            {
                "observation_id": row["observation_id"],
                "sample": deepcopy(row["sample"]),
                "producer_fingerprint": row["producer_fingerprint"],
                "displayed_score": deepcopy(score),
                "eligible": valid,
            }
        )
    pairs = {tuple(r["displayed_score"]) for r in scores if r["eligible"]}
    phase = state["round"]
    current_phase = (
        phase["value"] in {"BUY", "ACTIVE"}
        and phase["origin"] == "observation_projection"
        and phase["hypotheses"] == [phase["value"]]
    )
    unambiguous = bool(
        len(pairs) == 1 and all(r["eligible"] for r in scores) and current_phase
    )
    candidates = sorted(
        {
            n
            for pair in pairs
            for n in ([sum(pair) + 1] if unambiguous else [sum(pair), sum(pair) + 1])
            if n > 0
        }
    )
    reason = (
        "current_score_and_buy_or_active"
        if unambiguous
        else "score_unobserved"
        if not scores
        else "invalid_score_observation"
        if not all(r["eligible"] for r in scores)
        else "conflicting_current_scores"
        if len(pairs) != 1
        else "score_update_or_round_phase_unresolved"
    )
    return {
        "contract": "development_round_number_v1",
        "value": candidates[0] if unambiguous else None,
        "candidates": candidates,
        "status": "CANDIDATE" if unambiguous else "AMBIGUOUS" if candidates else "UNKNOWN",
        "reason": reason,
        "uncertainty": "unqualified_score_reading" if unambiguous else reason,
        "unknown_possible": True,
        "evidence_ids": sorted({r["observation_id"] for r in scores} | set(phase["evidence_ids"])),
        "phase": phase["value"],
        "phase_evidence_ids": list(phase["evidence_ids"]),
        "score_observations": scores,
        "qualification": "development_only",
        "qualified": False,
    }


def round_number_summary(estimates: list[dict[str, Any]]) -> dict[str, Any]:
    """Retain unknown samples and parallel acquisitions in a second-bin view."""
    values = {e["value"] for e in estimates}
    candidates = sorted({n for e in estimates for n in e["candidates"]})
    resolved = len(values) == 1 and None not in values
    reason = (
        "unqualified_sample_consensus"
        if resolved
        else "unobserved_second_bin"
        if not estimates
        else "unresolved_or_conflicting_samples"
    )
    return {
        "contract": "development_round_number_v1",
        "value": next(iter(values)) if resolved else None,
        "candidates": candidates,
        "status": "CANDIDATE" if resolved else "AMBIGUOUS" if candidates else "UNKNOWN",
        "reason": reason,
        "uncertainty": "unqualified_score_reading" if resolved else reason,
        "unknown_possible": True,
        "evidence_ids": sorted({i for e in estimates for i in e["evidence_ids"]}),
        "qualification": "development_only",
        "qualified": False,
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
        self,
        *,
        max_carry_seconds: Fraction = Fraction(2),
        future_seconds: Fraction = Fraction(3),
        fuse_exact_native_evidence: bool = False,
        forward_only: bool = False,
        mark_round_transition_gaps: bool = False,
        report_view_bridge: bool = False,
        buy_clock_expiry: bool = False,
        provisional_map_roles: bool = False,
        active_clock_bridge: bool = False,
        return_display_tail: bool = False,
        current_hp_return_candidate: bool = False,
        current_menu_return_candidate: bool = False,
        buy_clock_tail: bool = False,
        practical_visual_state: bool = False,
    ) -> None:
        if max_carry_seconds <= 0 or future_seconds <= 0:
            raise ValueError("Positive finite windows required")
        self.max_carry = max_carry_seconds
        self.future = future_seconds
        if type(fuse_exact_native_evidence) is not bool:
            raise ValueError("Explicit current-pixel fusion boolean required")
        self.fuse_exact_native_evidence = fuse_exact_native_evidence
        if type(forward_only) is not bool or type(mark_round_transition_gaps) is not bool:
            raise ValueError("Explicit temporal comparison flags required")
        if forward_only and mark_round_transition_gaps:
            raise ValueError("Transition brackets require offline future observations")
        self.forward_only = forward_only
        self.mark_round_transition_gaps = mark_round_transition_gaps
        if type(report_view_bridge) is not bool or (forward_only and report_view_bridge):
            raise ValueError("Report view reconciliation requires explicit offline mode")
        self.report_view_bridge = report_view_bridge
        if type(buy_clock_expiry) is not bool or (forward_only and buy_clock_expiry):
            raise ValueError("BUY clock reconciliation requires explicit offline mode")
        self.buy_clock_expiry = buy_clock_expiry
        if type(provisional_map_roles) is not bool:
            raise ValueError("Explicit provisional Map role mode required")
        self.provisional_map_roles = provisional_map_roles
        if type(active_clock_bridge) is not bool or (forward_only and active_clock_bridge):
            raise ValueError("ACTIVE clock bridge requires explicit offline mode")
        self.active_clock_bridge = active_clock_bridge
        if type(return_display_tail) is not bool or (forward_only and return_display_tail):
            raise ValueError("Return display tail requires explicit offline mode")
        self.return_display_tail = return_display_tail
        if (
            type(current_hp_return_candidate) is not bool
            or current_hp_return_candidate and (forward_only or not return_display_tail)
        ):
            raise ValueError("Current HP return candidate requires offline return display tail")
        self.current_hp_return_candidate = current_hp_return_candidate
        if (
            type(current_menu_return_candidate) is not bool
            or current_menu_return_candidate and (forward_only or not return_display_tail)
        ):
            raise ValueError("Current menu return candidate requires offline return display tail")
        self.current_menu_return_candidate = current_menu_return_candidate
        if type(buy_clock_tail) is not bool or (forward_only and buy_clock_tail):
            raise ValueError("BUY clock tail requires explicit offline mode")
        self.buy_clock_tail = buy_clock_tail
        if type(practical_visual_state) is not bool:
            raise ValueError("Explicit practical visual state mode required")
        self.practical_visual_state = practical_visual_state
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
        if self.fuse_exact_native_evidence:
            self._fuse_current_pixels(frames)
        if any(
            r["context"].get("unqualified_round_model") is True
            for frame in frames for r in frame["observations"]
        ):
            # Future-result/score helpers also inspect frame observations. Keep
            # research Round claims out of that entire Rule evidence graph.
            for frame in frames:
                frame["all_observation_ids"] = [
                    r["observation_id"] for r in frame["observations"]
                ]
                frame["observations"] = [
                    r for r in frame["observations"]
                    if r["context"].get("unqualified_round_model") is not True
                ]
                rows = frame["observations"]
                frame["signals"] = sorted({s for r in rows for s in r["signals"]})
                frame["fingerprints"] = {
                    kind: sorted({
                        (
                            r["producer_fingerprint"],
                            str(r["context"].get("profile_fingerprint", "")),
                        )
                        for r in rows if r["context"].get("stream_kind", "generic") == kind
                    })
                    for kind in {r["context"].get("stream_kind", "generic") for r in rows}
                }
            if self.fuse_exact_native_evidence:
                self._fuse_current_pixels(frames)
        self._revision += 1
        states: list[dict[str, Any]] = []
        transitions: list[dict[str, Any]] = []
        boundary_candidates: list[dict[str, Any]] = []
        prior: dict[str, Any] | None = None
        last_direct: dict[str, tuple[Fraction, dict[str, Any]]] = {}
        round_token: str | None = None
        round_progress_since_buy = False
        self_token: str | None = None
        death_latch: str | None = None
        death_round_token: str | None = None
        pending_elimination: dict[str, Any] | None = None
        last_alive_evidence: list[str] = []
        last_dead: dict[str, Any] | None = None
        last_alive: dict[str, Any] | None = None
        last_score_frame: dict[str, Any] | None = None
        last_clock: tuple[Fraction, int, tuple[int, int] | None] | None = None
        last_round_support: dict[str, Any] | None = None
        seen_elimination_displays: set[str] = set()
        for i, frame in enumerate(frames):
            link = continuity_between(prior, frame, max_gap=self.max_carry)
            same = bool(prior and source_scope(prior["sample"]) == source_scope(frame["sample"]))
            # Display identity survives unread gaps and Round changes. It is
            # not physical-event identity; identical later cards stay ambiguous.
            if not same or any(
                r["continuity"].get(key) is True
                for r in frame["observations"]
                for key in ("content_break_confirmed", "source_discontinuity", "discontinuity")
            ):
                seen_elimination_displays = set()
            if link["carry_allowed"] and prior is not None:
                frame["fingerprints"] = {**prior["fingerprints"], **frame["fingerprints"]}
            if not link["carry_allowed"]:
                last_direct = {}
                last_clock = None
                last_score_frame = None
                last_round_support = None
                round_token, self_token = None, None
                round_progress_since_buy = False
                death_latch, last_alive, last_dead = None, None, None
                death_round_token = None
                pending_elimination = None
                last_alive_evidence = []
            all_ids = frame.get("all_observation_ids", [
                r["observation_id"] for r in frame["observations"]
            ])
            # Research Round claims are projected after lifecycle inference.
            # They cannot advance Rule tokens, death/return context or Map gates.
            rule_rows = [
                r for r in frame["observations"]
                if r["context"].get("unqualified_round_model") is not True
            ]
            ids = [r["observation_id"] for r in rule_rows]
            signals = {s for r in rule_rows for s in r["signals"]}
            display_ids = {
                r["context"]["elimination_display_signature"]
                for r in frame["observations"]
                if "recorder_elimination_display" in r["signals"]
                and "elimination_display_signature" in r["context"]
            }
            fresh_display_ids = display_ids - seen_elimination_displays
            unbound_legacy_display = any(
                "recorder_elimination_display" in r["signals"]
                and r["context"].get("unqualified_view_model") is not True
                and "elimination_display_signature" not in r["context"]
                for r in frame["observations"]
            )
            strong_owner_rows = [
                r
                for r in frame["observations"]
                if "owner_hud" in r["signals"]
                and r["context"].get("unqualified_view_model") is not True
            ]
            weak_owner_only = "owner_hud" in signals and not strong_owner_rows
            weak_camera_only = any(
                r["context"].get("unqualified_view_model") is True
                and set(r["signals"]) & {"owner_hud", "spectator", "remote"}
                for r in frame["observations"]
            ) and not any(
                r["context"].get("unqualified_view_model") is not True
                and set(r["signals"]) & {"owner_hud", "spectator", "remote"}
                for r in frame["observations"]
            )
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
                    if self.forward_only and j > i:
                        break
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
                    choices["round"] = (
                        ["ENDED"]
                        if set(choices["round"]) <= {"ACTIVE", "ENDED"}
                        else sorted(set(choices["round"]) | {"ENDED"})
                    )
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
                    if (
                        domain == "life"
                        and values[0] == "ALIVE"
                        and weak_owner_only
                        or domain == "camera"
                        and weak_camera_only
                    ):
                        current[domain]["hypotheses"] = sorted(
                            {values[0], "UNKNOWN"}
                            | ({"REMOTE"} if domain == "camera" and values[0] == "SELF" else set())
                        )
                        current[domain]["uncertainty"] = "unqualified_learned_view_candidate"
                    last_direct[domain] = now, deepcopy(current[domain])
                elif domain in last_direct and now - last_direct[domain][0] <= self.max_carry:
                    current[domain] = deepcopy(last_direct[domain][1])
                    current[domain].update(
                        reason="bounded_missing_observation",
                        origin="temporal_inference",
                        uncertainty="continuation_unverified",
                    )
            previous_state = states[-1] if states and link["carry_allowed"] else None
            if current["round"]["value"] in {"ACTIVE", "ENDED", "INTERMISSION"}:
                round_progress_since_buy = True
            if current["round"]["value"] == "BUY" and (
                round_token is None or round_progress_since_buy
            ):
                round_token = digest({"buy": frame["sample"]["sample_sha256"]})
                round_progress_since_buy = False
                self_token = None
            returned = False
            if "owner_hud" in signals and death_latch:
                reentry = bool(
                    current["round"]["value"] in {"BUY", "ACTIVE"}
                    and round_token
                    and round_token != death_round_token
                )
                unopposed_self = (
                    current["life"]["value"] == "ALIVE" and current["camera"]["value"] == "SELF"
                )
                if unopposed_self and ("revival" in signals or reentry):
                    death_latch = None
                    death_round_token = None
                    returned = True
                else:
                    current["life"] = _estimate(
                        alternatives=[*current["life"]["hypotheses"], death_latch, "ALIVE"],
                        reason="return_edge_unobserved",
                        evidence=ids,
                    )
                    current["camera"] = _estimate(
                        alternatives=[*current["camera"]["hypotheses"], "SELF", "SPECTATOR"],
                        reason="return_edge_unobserved",
                        evidence=ids,
                    )
                    last_direct.pop("life", None)
                    last_direct.pop("camera", None)
            if current["life"]["value"] in {"DEAD", "DOWNED"} and signals & {"death", "downed"}:
                death_latch = current["life"]["value"]
                death_round_token = round_token
                last_dead = frame["sample"]
            if "spectator" in signals and not death_latch:
                # Preserve competing life explanations. Spectator UI is a camera observation.
                current["life"] = _estimate(
                    alternatives=["DEAD", "UNKNOWN"]
                    + (["ALIVE"] if "owner_hud" in signals else []),
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
            # A measured recorder alias in a victim column is stronger than
            # Report/spectator alone, but does not qualify normal death. Keep a
            # competing temporal elimination hypothesis separate from the direct
            # death/downed latch and all formal Fact/Event collections.
            if death_latch or "remote" in signals:
                pending_elimination = None
            if (
                pending_elimination is None
                and not death_latch
                and "recorder_elimination_display" in signals
                and (fresh_display_ids or unbound_legacy_display)
                and current["camera"]["value"] == "SPECTATOR"
                and last_alive is not None
                and round_token is not None
                and self_token == round_token
            ):
                later_downed_ids: list[str] = []
                forward_prior = frame
                for later in frames[i + 1 :]:
                    if self.forward_only:
                        break
                    if (
                        source_scope(later["sample"]) != source_scope(frame["sample"])
                        or native_time(later["sample"]) - now > self.future
                        or not continuity_between(forward_prior, later, max_gap=self.max_carry)[
                            "carry_allowed"
                        ]
                    ):
                        break
                    forward_prior = {
                        **later,
                        "fingerprints": {**forward_prior["fingerprints"], **later["fingerprints"]},
                    }
                    if "downed" in later["signals"]:
                        later_downed_ids = [r["observation_id"] for r in later["observations"]]
                        break
                candidate = {
                    "kind": "death_hypothesis",
                    "domain": "life",
                    "before": "ALIVE",
                    "after": "DEAD_OR_DOWNED_HYPOTHESIS",
                    "lower_sample": last_alive,
                    "upper_sample": frame["sample"],
                    "evidence_ids": sorted(set(last_alive_evidence + ids + later_downed_ids)),
                    "internal_game_event_time": None,
                    "status": "competing_unqualified_hypothesis",
                    "alternatives": ["DEAD", "DOWNED", "UNKNOWN"],
                    "normal_kill_qualified": False,
                }
                candidate["candidate_id"] = digest(
                    {
                        "kind": "recorder_elimination_hypothesis",
                        "lower_sample": last_alive,
                        "upper_sample": frame["sample"],
                    }
                )
                if display_ids:
                    candidate["display_signatures"] = sorted(fresh_display_ids)
                    candidate["display_identity_semantics"] = "not_physical_event_identity"
                transitions.append(candidate)
                pending_elimination = {
                    "candidate": candidate,
                    "round_token": round_token,
                    "last_spectator_sample": frame["sample"],
                    "life_value": "DOWNED" if later_downed_ids else "DEAD",
                }
            if pending_elimination is not None:
                candidate = pending_elimination["candidate"]
                if "spectator" in signals:
                    pending_elimination["last_spectator_sample"] = frame["sample"]
                current_self = (
                    "owner_hud" in signals
                    and current["life"]["value"] == "ALIVE"
                    and current["camera"]["value"] == "SELF"
                )
                next_round = bool(round_token and round_token != pending_elimination["round_token"])
                if current_self and (next_round or "revival" in signals):
                    transitions.append(
                        {
                            "kind": "return_hypothesis",
                            "domain": "life",
                            "before": "DEAD_OR_DOWNED_HYPOTHESIS",
                            "after": "ALIVE",
                            "lower_sample": pending_elimination["last_spectator_sample"],
                            "upper_sample": frame["sample"],
                            "linked_elimination_candidate_id": candidate["candidate_id"],
                            "evidence_ids": sorted(set(candidate["evidence_ids"] + ids)),
                            "internal_game_event_time": None,
                            "status": "competing_unqualified_hypothesis",
                        }
                    )
                    pending_elimination = None
                elif current_self:
                    current["life"] = _estimate(
                        alternatives=["ALIVE", "DEAD", "DOWNED", "UNKNOWN"],
                        reason="candidate_return_edge_unobserved",
                        evidence=ids,
                    )
                    last_direct.pop("life", None)
                elif current["life"]["value"] == "UNKNOWN":
                    current["life"] = _estimate(
                        "UNKNOWN" if next_round else pending_elimination["life_value"],
                        alternatives=["ALIVE", "DEAD", "UNKNOWN"]
                        if next_round
                        else ["DEAD", "DOWNED", "UNKNOWN"],
                        reason="next_round_return_unobserved"
                        if next_round
                        else "victim_display_and_owned_spectator_hypothesis",
                        evidence=candidate["evidence_ids"] + ids,
                    )
                    current["life"]["uncertainty"] = "competing_unqualified_life_hypothesis"
            if (
                current["life"]["value"] == "ALIVE"
                and current["camera"]["value"] == "SELF"
                and "owner_hud" in signals
            ):
                last_alive = frame["sample"]
                self_token = round_token
                last_alive_evidence = list(current["life"]["evidence_ids"])
            frame_state = {
                "sample": frame["sample"],
                **current,
                "continuity": link,
                "observation_ids": all_ids,
                "current_pixel_evidence_links": deepcopy(
                    frame.get("current_pixel_evidence_links", [])
                ),
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
                            if domain == "life"
                            and before == "ALIVE"
                            and after == "DEAD"
                            and "death" in signals
                            else "spectator"
                            if domain == "camera" and after == "SPECTATOR"
                            else "state_change"
                        )
                        lower_sample = (
                            score_before["sample"]
                            if kind == "round_end" and end_support and score_before
                            else previous_state["sample"]
                        )
                        carried_lower = None
                        if (
                            kind in {"round_start", "round_end"}
                            and not (kind == "round_end" and end_support and score_before)
                            and previous_state[domain]["reason"] == "bounded_missing_observation"
                            and last_round_support is not None
                            and last_round_support["value"] == before
                        ):
                            # Carry is a hypothesis, not a new before-state
                            # observation that can narrow an event bracket.
                            lower_sample = last_round_support["sample"]
                            carried_lower = previous_state["sample"]
                        transition = {
                            "kind": kind,
                            "domain": domain,
                            "before": before,
                            "after": after,
                            "lower_sample": lower_sample,
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
                        if carried_lower is not None:
                            transition["carried_before_sample"] = carried_lower
                            transition["lower_sample_basis"] = "last_current_round_support"
                        transitions.append(transition)
            candidates = [deepcopy(c) for r in frame["observations"] for c in r["map_candidates"]]
            gate = (
                current["life"]["value"] == "ALIVE"
                and current["camera"]["value"] == "SELF"
                and bool(strong_owner_rows)
                and not signals
                & {"spectator", "remote", "death", "downed", "result", "intermission"}
                and not set(current["round"]["hypotheses"]) & {"ENDED", "INTERMISSION"}
                and not any(
                    r["continuity"].get("decode_ok") is False for r in frame["observations"]
                )
            )
            # A current unqualified view can support a current candidate with
            # Round UNKNOWN. It does not establish a Round token, semantic
            # continuity, a path, or identity from a carried life/camera estimate.
            current_owner_evidence = sorted(
                r["observation_id"]
                for r in frame["observations"]
                if gate
                and "owner_hud" in r["signals"]
                and r["context"].get("unqualified_view_model") is not True
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
            map_zones = []
            for candidate in candidates:
                supplied = []
                for zone_field in ("zone_candidate", "zone_resolution"):
                    value = candidate.get(zone_field)
                    if isinstance(value, dict) and value not in supplied:
                        supplied.append(value)
                map_zones.extend(deepcopy(supplied))
            viewed_zones = [
                zone_candidate
                for row in frame["observations"]
                if (zone_candidate := viewed_zone_candidate(row)) is not None
            ]
            current_zones = []
            if gate:
                for candidate in viewed_zones:
                    # Keep original acquisition provenance. Raw exact-pixel
                    # aliases are not promoted into another acquisition's Zone.
                    if candidate["sample"] != frame["sample"]:
                        continue
                    associated = deepcopy(candidate)
                    associated["zone_subject"] = "current_recorder_hypothesis"
                    associated["current_recorder_view_evidence_ids"] = current_owner_evidence
                    current_zones.append(associated)
            generic_maps = [r for r in frame["observations"]
                            if r["raw"].get("schema") == "development_generic_map_pixels_v1"]
            map_zones.extend(
                {**deepcopy(z), "sample": deepcopy(r["sample"]),
                 "evidence_refs": [r["observation_id"]]}
                for r in generic_maps for z in r["raw"].get("zone_candidates", [])
            )
            frame_state["map"] = {
                "observation_present": bool(candidates)
                or bool(viewed_zones)
                or any(
                    r["raw"].get("schema")
                    in {"map_consumer_provisional_v1", "development_hud_zone_measurement_v1",
                        "development_generic_map_pixels_v1"}
                    for r in frame["observations"]
                ),
                "zone_candidates": map_zones + viewed_zones,
                "current_recorder_zone_candidates": current_zones,
                "zone_observation_ids": sorted(
                    r["observation_id"]
                    for r in frame["observations"]
                    if r["raw"].get("schema") == "development_hud_zone_measurement_v1"
                ),
                "zone_context_contract": ZONE_CONTEXT_CONTRACT,
                "marker_associations": [
                    deepcopy(a)
                    for r in frame["observations"]
                    for a in r["raw"].get("marker_associations", [])
                ],
                "candidates": candidates,
                "current_self_position_candidates": self_candidates,
                "current_recorder_view_evidence_ids": current_owner_evidence,
                "temporal_path_eligible": False,
                "current_view_contract": "development_current_map_v1",
                "status": "CANDIDATES" if candidates or map_zones or viewed_zones else "UNKNOWN",
                "reason": "current_recorder_view_supports_development_candidates"
                if gate
                else "self_state_unresolved",
                "ownership": "UNKNOWN",
                "qualified": False,
            }
            if generic_maps:
                frame_state["map"]["map_name_candidates"] = [
                    {**deepcopy(c), "sample": deepcopy(r["sample"]),
                     "evidence_refs": [r["observation_id"]]}
                    for r in generic_maps for c in r["raw"].get("map_name_candidates", [])
                ]
                frame_state["map"]["generic_observation_ids"] = [
                    r["observation_id"] for r in generic_maps
                ]

            if display_ids & seen_elimination_displays:
                frame_state["previously_seen_elimination_display_signatures"] = sorted(
                    display_ids & seen_elimination_displays
                )
            seen_elimination_displays.update(display_ids)
            states.append(frame_state)
            if len(set(choices["round"])) == 1:
                last_round_support = {"value": current["round"]["value"], "sample": frame["sample"]}
            elif choices["round"]:
                last_round_support = None
            prior = frame
        # Bounded bidirectional reconciliation: only fill a missing same-state hypothesis.
        # No smoothing across a conflict, reset, life edge or camera edge.
        if not self.forward_only:
            self._reconcile(states)
        if self.mark_round_transition_gaps:
            self._mark_round_transition_gaps(states, transitions)
        view_projections = self._reconcile_report_views(states) if self.report_view_bridge else []
        clock_projections = (
            self._reconcile_buy_clock_expiry(states) if self.buy_clock_expiry else []
        )
        clock_tails = (
            self._reconcile_buy_clock_tail(states, transitions) if self.buy_clock_tail else []
        )
        active_clocks = self._reconcile_active_clocks(states) if self.active_clock_bridge else []
        return_tails = (
            self._reconcile_return_display_tails(states) if self.return_display_tail else []
        )
        round_projections = []
        for state in states:
            rows = [self._observations[i] for i in state["observation_ids"]]
            weak = [
                r for r in rows
                if r["context"].get("unqualified_round_model") is True
                and "active" in r["signals"]
            ]
            if weak:
                before = deepcopy(state["round"])
                evidence = sorted({r["observation_id"] for r in weak})
                state["round_model_hypotheses"] = {
                    "value": "ACTIVE", "hypotheses": ["ACTIVE", "UNKNOWN"],
                    "evidence_ids": evidence, "qualified": False,
                    "input_samples": [r["sample"] for r in weak],
                    "scope": "current_pixels_only_no_lifecycle_authority",
                }
                if before["value"] == "UNKNOWN" and before["reason"] == "unobserved":
                    state["round"] = _estimate(
                        "ACTIVE", alternatives=["ACTIVE", "UNKNOWN"],
                        reason="unqualified_round_shape_candidate", evidence=evidence,
                        origin="observation_projection",
                    )
                    state["round"]["uncertainty"] = "unqualified_learned_round_candidate"
                    state["round"]["rule_estimate"] = before
                round_projections.append({
                    "sample": state["sample"], "before": before,
                    "after": deepcopy(state["round"]), "evidence_ids": evidence,
                    "kind": "current_round_estimate_revision_not_event", "qualified": False,
                })
            state["round_number"] = _round_number(
                state, rows
            )
            if self.provisional_map_roles:
                state["map"]["provisional_recorder_position_hypotheses"] = provisional_map_roles(
                    state, rows
                )
        if any(r["raw"].get("schema") == "development_composite_view_pixels_v1"
               for r in self._observations.values()):
            from .composite_view import attach_composite_views

            attach_composite_views(states, self._observations)
        visual_history: list[dict[str, Any]] = []
        superseded_transitions: list[dict[str, Any]] = []
        if self.practical_visual_state:
            from .event_round import (
                ROUND_CONTEXT_SECONDS,
                attach_event_round_context,
                group_round_starts,
            )
            from .visual_state import (
                apply_visual_state,
                merge_visual_events,
                reconcile_visual_transitions,
            )

            visual_history, visual_events = apply_visual_state(
                states, self._observations, _estimate
            )
            superseded_transitions = reconcile_visual_transitions(transitions, states)
            merge_visual_events(transitions, visual_events)
            for state in states:
                rows = [self._observations[i] for i in state["observation_ids"]]
                state["round_number"] = _round_number(state, rows)
                if self.provisional_map_roles:
                    state["map"]["provisional_recorder_position_hypotheses"] = (
                        provisional_map_roles(state, rows)
                    )
            group_round_starts(transitions, states, self.future)
            attach_event_round_context(transitions, states, ROUND_CONTEXT_SECONDS)
        acquisition_seconds = self._seconds(states)
        result: dict[str, Any] = {
            "version": VERSION,
            "configuration": {"fuse_exact_native_evidence": self.fuse_exact_native_evidence},
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
        if self.forward_only or self.mark_round_transition_gaps:
            result["configuration"].update(
                forward_only=self.forward_only,
                mark_round_transition_gaps=self.mark_round_transition_gaps,
            )
        if self.practical_visual_state:
            from .replay import file_sha

            result["configuration"]["practical_visual_state"] = (
                "development_practical_visual_state_v1"
            )
            result["configuration"]["practical_visual_rule_sha256"] = file_sha(
                Path(__file__).with_name("visual_state.py")
            )
            result["configuration"]["event_round_rule_sha256"] = file_sha(
                Path(__file__).with_name("event_round.py")
            )
            result["visual_state_projection_history"] = visual_history
            result["superseded_transition_candidates"] = superseded_transitions
        if round_projections:
            result["round_model_projection_history"] = round_projections
        if self.buy_clock_expiry:
            result["configuration"]["buy_clock_expiry"] = "development_buy_clock_expiry_v1"
            result["buy_clock_projection_history"] = clock_projections
        if self.active_clock_bridge:
            result["configuration"]["active_clock_bridge"] = "development_active_clock_chain_v1"
            result["active_clock_projection_history"] = active_clocks
        if self.return_display_tail:
            result["configuration"]["return_display_tail"] = "development_return_display_tail_v1"
            result["return_display_tail_projection_history"] = return_tails
        if self.current_hp_return_candidate:
            result["configuration"]["current_hp_return_candidate"] = (
                "development_current_view_hp_return_candidate_v1"
            )
        if self.current_menu_return_candidate:
            result["configuration"]["current_menu_return_candidate"] = (
                "development_current_menu_return_candidate_v1"
            )
        if self.buy_clock_tail:
            result["configuration"]["buy_clock_tail"] = "development_buy_clock_tail_v1"
            result["buy_clock_tail_projection_history"] = clock_tails
        if self.provisional_map_roles:
            result["configuration"]["provisional_map_roles"] = MAP_ROLE_CONTRACT
            result["configuration"]["provisional_map_roles_rule_sha256"] = rule_sha256()
        if self.report_view_bridge:
            result["configuration"]["report_view_bridge"] = "development_report_view_bridge_v2"
            result["configuration"]["max_report_bridge_seconds"] = "10"
            result["configuration"]["max_abstaining_view_gap_seconds"] = str(self.max_carry)
            result["report_view_projection_history"] = view_projections
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
    def _fuse_current_pixels(frames: list[dict[str, Any]]) -> None:
        """Reuse exact current measurements, never another epoch's inferred state.

        Source/hash, original integer PTS/timebase, pixels and dimensions must all
        match. Acquisitions remain separate for temporal carry. Aliased evidence
        is one observation, not independent confirmation or semantic continuity.
        """
        groups: dict[tuple[Any, ...], list[dict[str, Any]]] = defaultdict(list)
        for frame in frames:
            sample = frame["sample"]
            broken = any(
                r["continuity"].get(key) is True
                for r in frame["observations"]
                for key in ("discontinuity", "source_discontinuity", "content_break_confirmed")
            ) or any(r["continuity"].get("decode_ok") is False for r in frame["observations"])
            if broken:
                continue
            key = tuple(
                sample[k]
                for k in (
                    "source_id",
                    "source_sha256",
                    "native_pts_tick",
                    "native_time_base",
                    "native_pixel_sha256",
                )
            ) + (tuple(sample["frame_size_px"]),)
            groups[key].append(frame)
        for group in groups.values():
            rows = {r["observation_id"]: r for f in group for r in f["observations"]}
            for frame in group:
                frame["observations"] = sorted(rows.values(), key=lambda r: r["observation_id"])
                frame["signals"] = sorted({s for r in frame["observations"] for s in r["signals"]})
                # Each acquisition owns its producer/profile stream. A second
                # exact-pixel observer appearing is not a configuration change
                # in the first observer. Changes within either origin still reset.
                origin_streams = {
                    (source_scope(r["sample"]), r["context"].get("stream_kind", "generic"))
                    for r in frame["observations"]
                }
                frame["fingerprints"] = {
                    digest({"scope": scope, "stream_kind": kind}): sorted(
                        {
                            (
                                r["producer_fingerprint"],
                                str(r["context"].get("profile_fingerprint", "")),
                            )
                            for r in frame["observations"]
                            if source_scope(r["sample"]) == scope
                            and r["context"].get("stream_kind", "generic") == kind
                        }
                    )
                    for scope, kind in origin_streams
                }
                frame["current_pixel_evidence_links"] = [
                    {
                        "observation_id": r["observation_id"],
                        "original_sample_sha256": r["sample"]["sample_sha256"],
                        "current_sample_sha256": frame["sample"]["sample_sha256"],
                        "criterion": "exact_Source_native_PTS_timebase_pixels_dimensions",
                        "independent_confirmation": False,
                        "semantic_continuity": "UNKNOWN",
                    }
                    for r in frame["observations"]
                    if r["sample"]["sample_sha256"] != frame["sample"]["sample_sha256"]
                ]

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

    def _reconcile_return_display_tails(self, states: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Bracket a stale victim display with a later direct next-Round return.

        A current weak SELF view is only a competing camera hypothesis. The
        default return-tail option keeps the earlier values UNKNOWN. A second
        explicit option may select an unqualified ALIVE/SELF candidate when a
        current HP component and later direct return are both present. Neither
        path establishes the return time or gains lifecycle, Map, or formal
        ownership authority.
        """
        history = []
        for index, frame in enumerate(states):
            if (
                frame["life"]["value"] != "DEAD"
                or frame["life"]["reason"] != "victim_display_and_owned_spectator_hypothesis"
                or frame["camera"]["value"] != "UNKNOWN"
                or frame["round_token"] is None
            ):
                continue
            rows = [self._observations[i] for i in frame["observation_ids"]]
            signals = {s for row in rows for s in row["signals"]}
            if signals & {"spectator", "remote", "death", "downed", "revival", "owner_hud"}:
                continue
            weak_self = [
                row
                for row in rows
                if row["context"].get("unqualified_view_model") is True
                and row["raw"].get("camera_hypothesis") == "SELF"
            ]
            if not weak_self:
                continue
            current_score = self._score({"observations": rows})
            confirmation = None
            for later in states[index + 1 :]:
                elapsed = native_time(later["sample"]) - native_time(frame["sample"])
                if (
                    source_scope(later["sample"]) != source_scope(frame["sample"])
                    or elapsed > self.future + 1
                    or not later["continuity"]["carry_allowed"]
                ):
                    break
                later_rows = [self._observations[i] for i in later["observation_ids"]]
                later_signals = {s for row in later_rows for s in row["signals"]}
                later_score = self._score({"observations": later_rows})
                if (
                    later_signals
                    & {
                        "spectator",
                        "remote",
                        "death",
                        "downed",
                        "revival",
                        "result",
                        "intermission",
                    }
                    or current_score is not None
                    and later_score is not None
                    and later_score != current_score
                ):
                    break
                if (
                    later["round_token"] != frame["round_token"]
                    and later["round"]["value"] == "BUY"
                    and later["round"]["reason"] == "current_observation"
                    and later["life"]["value"] == "ALIVE"
                    and later["camera"]["value"] == "SELF"
                    and "buy" in later_signals
                    and "owner_hud" in later_signals
                ):
                    confirmation = later
                    break
            if confirmation is None:
                continue
            before_life, before_camera = deepcopy(frame["life"]), deepcopy(frame["camera"])
            evidence = sorted(
                set(
                    frame["life"]["evidence_ids"]
                    + [row["observation_id"] for row in weak_self]
                    + confirmation["life"]["evidence_ids"]
                )
            )
            current_hp = self.current_hp_return_candidate and any(
                self._current_view_hp_support(row) for row in weak_self
            )
            menu_rows = [
                row for row in rows
                if self.current_menu_return_candidate
                and self._current_menu_support(row, frame["sample"])
            ]
            positive = current_hp or bool(menu_rows)
            if menu_rows:
                evidence = sorted(set(evidence) | {r["observation_id"] for r in menu_rows})
            positive_reason = (
                "current_self_hp_and_next_round_return_candidate" if current_hp
                else "current_menu_and_next_round_return_candidate"
            )
            frame["life"] = _estimate(
                "ALIVE" if positive else "UNKNOWN",
                alternatives=["ALIVE", "DEAD", "DOWNED", "UNKNOWN"],
                reason=positive_reason if positive else "next_round_self_return_bracket_candidate",
                evidence=evidence,
            )
            frame["life"].update(
                forward_estimate=before_life,
                uncertainty="current_view_owner_and_return_time_unverified"
                if positive else "return_time_and_victim_display_age_unverified",
            )
            frame["camera"] = _estimate(
                "SELF" if positive else "UNKNOWN",
                alternatives=["SELF", "SPECTATOR", "REMOTE", "UNKNOWN"],
                reason=positive_reason
                if positive else "weak_current_self_and_next_round_return_candidate",
                evidence=evidence,
            )
            frame["camera"].update(
                forward_estimate=before_camera,
                uncertainty="current_view_owner_unverified",
            )
            history_record = {
                    "sample": frame["sample"],
                    "before_life": before_life,
                    "after_life": deepcopy(frame["life"]),
                    "before_camera": before_camera,
                    "after_camera": deepcopy(frame["camera"]),
                    "confirmation_sample": confirmation["sample"],
                    "evidence_ids": evidence,
                    "qualified": False,
                    "internal_game_event_time": None,
                    "lifecycle_authority": False,
                    "Map_authority": False,
            }
            if self.current_hp_return_candidate:
                history_record["current_view_hp_support"] = current_hp
            if self.current_menu_return_candidate:
                history_record["current_menu_geometry_evidence_ids"] = [
                    row["observation_id"] for row in menu_rows
                ]
            history.append(history_record)
        return history

    @staticmethod
    def _current_menu_support(row: dict[str, Any], sample: dict[str, Any]) -> bool:
        """Consume current image geometry only; it never certifies an owner.

        The image observer owns detection thresholds. A native pixel alias may
        supply current evidence, but it cannot supply temporal continuity.
        """
        raw = row["raw"]
        measurement = raw.get("menu_grid_measurement")
        if not isinstance(measurement, dict):
            return False
        keys = (
            "source_id", "source_sha256", "native_pts_tick", "native_time_base",
            "native_pixel_sha256", "frame_size_px",
        )
        score = measurement.get("score")
        return bool(
            row["context"].get("stream_kind") == "hud_menu_geometry"
            and raw.get("schema") == "development_buy_menu_grid_geometry_v1"
            and measurement.get("schema") == raw["schema"]
            and measurement.get("supported") is True
            and measurement.get("status") == "CANDIDATE"
            and measurement.get("geometry_scope") == "current_pixel_menu_overlay_only"
            and all(measurement.get(k) is False for k in (
                "owner_authority", "camera_authority", "phase_authority", "qualified"
            ))
            and all(row["sample"][k] == sample[k] for k in keys)
            and isinstance(score, (int, float))
            and not isinstance(score, bool)
            and math.isfinite(score)
            and 0 <= score <= 1
        )

    @staticmethod
    def _current_view_hp_support(row: dict[str, Any]) -> bool:
        """Require current HP and weak view components together."""
        raw = row["raw"]
        hp = raw.get("view_hp")
        if not (
            raw.get("camera_hypothesis") == "SELF"
            and raw.get("current_HUD_component_supported") is True
            and raw.get("owner_hypothesis_exclusions") == ["combat_report_visible"]
            and raw.get("owned_verb_phrase") is None
            and isinstance(hp, dict)
        ):
            return False
        value, confidence = hp.get("display"), hp.get("confidence")
        return bool(
            isinstance(value, str)
            and value.isascii()
            and value.isdigit()
            and 1 <= int(value) <= 150
            and isinstance(confidence, (int, float))
            and not isinstance(confidence, bool)
            and math.isfinite(confidence)
            and confidence >= .90
        )


    def _reconcile_buy_clock_tail(
        self, states: list[dict[str, Any]], transitions: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        """Expose a carried BUY at timer expiry inside a witnessed start gap.

        Timer zero does not prove ACTIVE. A direct BUY/ACTIVE bracket and the
        same current score narrow the question to a phase candidate only.
        The original carry remains inspectable and no event bracket changes.
        """
        by_sample = {s["sample"]["sample_sha256"]: s for s in states}

        def score(frame: dict[str, Any]) -> tuple[int, int] | None:
            rows = [
                self._observations[i]
                for i in frame["observation_ids"]
                if self._observations[i]["context"].get("unqualified_round_model") is not True
            ]
            value = self._score({"observations": rows})
            return (
                value
                if (
                    value is not None
                    and len(value) == 2
                    and all(type(v) is int and 0 <= v <= 99 for v in value)
                )
                else None
            )

        history = []
        for transition in transitions:
            if transition["kind"] != "round_start":
                continue
            lower = by_sample.get(transition["lower_sample"]["sample_sha256"])
            upper = by_sample.get(transition["upper_sample"]["sample_sha256"])
            if (
                lower is None
                or upper is None
                or source_scope(lower["sample"]) != source_scope(upper["sample"])
            ):
                continue
            lower_score, upper_score = score(lower), score(upper)
            if lower_score is None or lower_score != upper_score:
                continue
            if (
                native_time(upper["sample"]) - native_time(lower["sample"])
                > self.max_carry + self.future
            ):
                continue
            for frame in states:
                if (
                    source_scope(frame["sample"]) != source_scope(lower["sample"])
                    or not native_time(lower["sample"])
                    < native_time(frame["sample"])
                    < native_time(upper["sample"])
                    or frame["round"]["value"] != "BUY"
                    or frame["round"]["reason"] != "bounded_missing_observation"
                    or score(frame) != lower_score
                ):
                    continue
                rows = [
                    self._observations[i]
                    for i in frame["observation_ids"]
                    if self._observations[i]["context"].get("unqualified_round_model") is not True
                ]
                clocks = {
                    r["context"]["timer_seconds"]
                    for r in rows
                    if type(r["context"].get("timer_seconds")) is int
                }
                if len(clocks) != 1 or next(iter(clocks)) not in {0, 1}:
                    continue
                before = deepcopy(frame["round"])
                evidence = sorted(
                    set(
                        transition["evidence_ids"]
                        + [
                            r["observation_id"]
                            for r in rows
                            if r["context"].get("timer_seconds") in {0, 1}
                        ]
                    )
                )
                frame["round"] = _estimate(
                    alternatives=["BUY", "ACTIVE", "UNKNOWN"],
                    reason="buy_clock_expiry_inside_round_start_bracket",
                    evidence=evidence,
                )
                frame["round"].update(
                    forward_estimate=before, uncertainty="phase_at_clock_expiry_unverified"
                )
                history.append(
                    {
                        "sample": frame["sample"],
                        "before": before,
                        "after": deepcopy(frame["round"]),
                        "lower_sample": lower["sample"],
                        "upper_sample": upper["sample"],
                        "evidence_ids": evidence,
                        "qualified": False,
                        "internal_game_event_time": None,
                        "lifecycle_authority": False,
                        "Map_authority": False,
                    }
                )
        return history


    def _reconcile_active_clocks(self, states: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Recover a phase candidate from an anchored, measured countdown chain.

        Missing displays never become clock measurements. Revisions need a
        current numeric clock and a later decreasing measurement; they have no
        lifecycle/Map/event authority. Score and native continuity alone are
        insufficient to establish that the game clock ran without a pause.
        """
        def scores_of(frame: dict[str, Any]) -> set[tuple[int, ...]]:
            return {tuple(self._observations[i]["context"]["score"])
                    for i in frame["observation_ids"]
                    if self._observations[i]["context"].get("unqualified_round_model") is not True
                    and isinstance(self._observations[i]["context"].get("score"), (tuple, list))}

        def measured(frame: dict[str, Any]) -> tuple[int, tuple[int, ...]] | None:
            rows = [self._observations[i] for i in frame["observation_ids"]
                    if self._observations[i]["context"].get("unqualified_round_model") is not True]
            clocks = {r["context"]["timer_seconds"] for r in rows
                      if type(r["context"].get("timer_seconds")) is int}
            scores = scores_of(frame)
            if len(clocks) != 1 or len(scores) != 1:
                return None
            clock, score = next(iter(clocks)), next(iter(scores))
            return (clock, score) if (0 < clock < 600 and len(score) == 2
                and all(type(v) is int and 0 <= v <= 99 for v in score)) else None

        def barrier(frame: dict[str, Any]) -> bool:
            return (not frame["continuity"]["carry_allowed"]
                    or frame["round"]["reason"] == "conflicting_observations"
                    or any(set(self._observations[i]["signals"]) & {"buy", "result", "intermission"}
                           for i in frame["observation_ids"]))

        chain: list[dict[str, Any]] = []
        history = []
        for index, frame in enumerate(states):
            now, value = native_time(frame["sample"]), measured(frame)
            prior_value = measured(chain[-1]) if chain else None
            expected_score = prior_value[1] if prior_value is not None else None
            if chain and (source_scope(chain[-1]["sample"]) != source_scope(frame["sample"])
                          or barrier(frame)
                          or any(s != expected_score for s in scores_of(frame))
                          or (prior_value is not None
                              and now - native_time(chain[-1]["sample"]) > prior_value[0] + 1)):
                chain = []
            direct = (frame["round"]["value"] == "ACTIVE"
                      and frame["round"]["origin"] == "observation_projection"
                      and frame["round"]["reason"] == "current_observation"
                      and any("active" in self._observations[i]["signals"]
                              and self._observations[i]["context"].get(
                                  "unqualified_round_model") is not True
                              for i in frame["observation_ids"]))
            if direct and value and not barrier(frame):
                chain = [frame]
                continue
            if not chain or value is None:
                continue
            prior = chain[-1]
            previous = measured(prior)
            assert previous is not None
            gap = now - native_time(prior["sample"])
            if value[1] != previous[1] or value[0] > previous[0]:
                chain = []
                continue
            if value[0] == previous[0] and gap <= 1:
                continue
            if not (gap > 0
                    and previous[0] - value[0] > 0 and abs(previous[0] - value[0] - gap) <= 1):
                chain = []
                continue
            chain.append(frame)
            if frame["round"]["value"] != "UNKNOWN" or frame["round"]["reason"] != "unobserved":
                continue
            confirmation = None
            for later in states[index + 1:]:
                elapsed = native_time(later["sample"]) - now
                if (source_scope(later["sample"]) != source_scope(frame["sample"])
                        or elapsed > self.future or barrier(later)
                        or any(s != value[1] for s in scores_of(later))):
                    break
                observed = measured(later)
                if observed is None:
                    continue
                if observed[1] != value[1] or observed[0] > value[0]:
                    break
                if value[0] - observed[0] > 0 and abs(value[0] - observed[0] - elapsed) <= 1:
                    confirmation = later
                    break
            if confirmation is None:
                continue
            before = deepcopy(frame["round"])
            evidence = sorted({i for f in chain + [confirmation] for i in f["observation_ids"]})
            frame["round"] = _estimate(
                "ACTIVE", alternatives=["ACTIVE", "BUY", "UNKNOWN"], evidence=evidence,
                reason="measured_active_clock_chain_candidate",
            )
            frame["round"].update(forward_estimate=before,
                                  uncertainty="clock_chain_phase_and_pause_unverified")
            history.append({"sample": frame["sample"], "before": before,
                            "after": deepcopy(frame["round"]),
                            "anchor_sample": chain[0]["sample"],
                            "previous_clock_sample": prior["sample"],
                            "clock_seconds": value[0],
                            "confirmation_sample": confirmation["sample"],
                            "chain_evidence_ids": evidence, "qualified": False,
                            "internal_game_event_time": None,
                            "lifecycle_authority": False, "Map_authority": False})
        return history

    def _reconcile_buy_clock_expiry(self, states: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """A post-inference phase hypothesis, without event/token/Map authority.

        Two observed decreasing BUY clocks bound an expected expiry, allowing
        one second for display quantization. A nearby direct ACTIVE witness is
        still required. Native time is not proof that the game clock ran; BUY
        and UNKNOWN remain explicit alternatives (for pauses/unread evidence).
        """
        history = []
        clocks: list[tuple[dict[str, Any], int, tuple[int, ...]]] = []
        last_buy: dict[str, Any] | None = None

        def rows_of(frame: dict[str, Any]) -> list[dict[str, Any]]:
            return [self._observations[i] for i in frame["observation_ids"]
                    if self._observations[i]["context"].get("unqualified_round_model") is not True]

        def score_of(rows: list[dict[str, Any]]) -> tuple[int, ...] | None:
            scores = {tuple(r["context"]["score"]) for r in rows
                      if isinstance(r["context"].get("score"), (list, tuple))}
            if len(scores) != 1:
                return None
            score = next(iter(scores))
            return score if len(score) == 2 and all(type(v) is int and 0 <= v <= 99
                                                  for v in score) else None

        for index, frame in enumerate(states):
            rows = rows_of(frame)
            signals = {s for row in rows for s in row["signals"]}
            score = score_of(rows)
            if not frame["continuity"]["carry_allowed"] or signals & {
                "active", "result", "intermission"
            } or (clocks and score is not None and score != clocks[-1][2]):
                clocks, last_buy = [], None
            if "buy" in signals:
                if frame["round"]["reason"] != "current_observation":
                    clocks, last_buy = [], None
                    continue
                last_buy = frame
                values = {r["context"]["timer_seconds"] for r in rows if "buy" in r["signals"]
                          and type(r["context"].get("timer_seconds")) is int
                          and r["context"]["timer_seconds"] >= 0}
                if len(values) == 1 and score is not None:
                    clocks.append((frame, next(iter(values)), score))
                    clocks = clocks[-2:]
                continue
            if (frame["round"]["value"] != "BUY"
                    or frame["round"]["reason"] != "bounded_missing_observation"
                    or len(clocks) != 2 or last_buy is None):
                continue
            (a, av, ascore), (b, bv, bscore) = clocks
            now = native_time(frame["sample"])
            clock_gap = native_time(b["sample"]) - native_time(a["sample"])
            elapsed = now - native_time(b["sample"])
            if not (ascore == bscore and 0 < clock_gap <= self.max_carry
                    and av > bv and abs(Fraction(av - bv) - clock_gap) <= 1
                    and bv + 1 <= elapsed <= self.max_carry + self.future):
                continue
            confirmation = None
            for later in states[index + 1:]:
                if (source_scope(later["sample"]) != source_scope(frame["sample"])
                        or native_time(later["sample"]) - now > self.future
                        or not later["continuity"]["carry_allowed"]):
                    break
                later_rows = rows_of(later)
                later_signals = {s for row in later_rows for s in row["signals"]}
                later_score = score_of(later_rows)
                if (later_signals & {"buy", "result", "intermission"}
                        or later_score is not None and later_score != bscore
                        or later["round"]["reason"] == "conflicting_observations"):
                    break
                if ("active" in later_signals and later_score == bscore
                        and later["round"]["origin"] == "observation_projection"
                        and later["round"]["reason"] == "current_observation"
                        and later["round"]["value"] == "ACTIVE"):
                    confirmation = later
                    break
            if confirmation is None:
                continue
            before = deepcopy(frame["round"])
            ids = sorted({i for witness in [a, b, last_buy, frame, confirmation]
                          for i in witness["observation_ids"]})
            frame["round"] = _estimate(
                "ACTIVE", alternatives=["ACTIVE", "BUY", "UNKNOWN"],
                reason="expired_buy_clock_and_later_active_candidate", evidence=ids,
            )
            frame["round"].update(
                uncertainty="game_clock_progress_and_pause_unverified",
                forward_estimate=before,
            )
            history.append({
                "sample": frame["sample"], "before": before, "after": deepcopy(frame["round"]),
                "clock_samples": [a["sample"], b["sample"]],
                "clock_display_seconds": [av, bv], "confirmation_sample": confirmation["sample"],
                "kind": "round_clock_estimate_revision_not_event", "qualified": False,
                "internal_game_event_time": None, "lifecycle_authority": False,
                "Map_authority": False,
            })
        return history

    @staticmethod
    def _mark_round_transition_gaps(
        states: list[dict[str, Any]], transitions: list[dict[str, Any]]
    ) -> None:
        """Replace an unverified carry within a measured edge with alternatives.

        Neither side is selected as the true state of an unread native frame.
        Existing direct observations, candidate brackets and all life/camera
        states are retained. The original forward estimate remains inspectable.
        """
        for transition in transitions:
            pair = {"round_start": ("BUY", "ACTIVE"), "round_end": ("ACTIVE", "ENDED")}.get(
                transition["kind"]
            )
            if pair is None:
                continue
            lower, upper = transition["lower_sample"], transition["upper_sample"]
            for frame in states:
                if (
                    source_scope(frame["sample"]) != source_scope(lower)
                    or source_scope(upper) != source_scope(lower)
                    or not native_time(lower) < native_time(frame["sample"]) < native_time(upper)
                    or frame["round"]["reason"] != "bounded_missing_observation"
                ):
                    continue
                original = deepcopy(frame["round"])
                frame["round"] = _estimate(
                    alternatives=list(pair),
                    reason="bracketed_round_transition_candidate",
                    evidence=transition["evidence_ids"],
                )
                frame["round"].update(
                    uncertainty="boundary_within_observation_gap",
                    forward_estimate=original,
                    transition_bracket={
                        "lower_sample": lower,
                        "upper_sample": upper,
                        "internal_game_event_time": None,
                    },
                )

    def _report_view_support(self, frame: dict[str, Any]) -> tuple[bool, bool]:
        """Current pixels may support a weak view; report age stays unresolved."""
        rows = [self._observations[i] for i in frame["observation_ids"]]
        signals = {s for r in rows for s in r["signals"]}
        if signals & _REPORT_VIEW_BARRIERS:
            return False, False
        views = [r for r in rows if r["context"].get("unqualified_view_model") is True]
        if len(views) != 1:
            return False, False
        raw = views[0]["raw"]
        if not (
            raw.get("current_HUD_component_supported") is True
            and raw.get("owner_hypothesis_exclusions") == ["combat_report_visible"]
            and raw.get("owned_verb_phrase") is None
        ):
            return False, False
        hp = raw.get("view_hp") or {}
        if not isinstance(hp, dict):
            hp = {}
        value, confidence = hp.get("display"), hp.get("confidence")
        accepted = (isinstance(confidence, (float, int)) and not isinstance(confidence, bool)
                    and math.isfinite(confidence) and confidence >= .90)
        parsed_hp = (int(value) if isinstance(value, str) and value.isascii()
                     and value.isdigit() and accepted else None)
        if parsed_hp is not None and not 1 <= parsed_hp <= 150:
            return False, False
        camera = raw.get("camera_hypothesis")
        if camera == "UNKNOWN":
            classifiers = raw.get("classifiers")
            if not isinstance(classifiers, dict) or not all(
                isinstance(classifiers.get(name), dict)
                and classifiers[name].get("value") == "UNKNOWN"
                for name in ["centroid", "three_prototypes"]
            ):
                return False, False
            # An explicit classifier abstention is missing evidence. It may
            # preserve bounded context, but must never support filling itself.
            return True, False
        return (True, parsed_hp is not None) if camera == "SELF" else (False, False)

    def _reconcile_report_views(self, states: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Reconcile current report-blocked SELF pixels between direct anchors.

        This post-inference candidate cannot advance lifecycle rules or Map
        attribution. Missing HP stays unfilled; explicit contrary evidence
        rejects the span. Native proximity alone never authorizes a revision.
        """
        history: list[dict[str, Any]] = []
        anchor: dict[str, Any] | None = None
        pending: list[tuple[dict[str, Any], bool]] = []
        score: tuple[int, int] | None = None
        last_current_self: Fraction | None = None
        for frame in states:
            rows = [self._observations[i] for i in frame["observation_ids"]]
            current_score = self._score({"observations": rows})
            if anchor and (
                not frame["continuity"]["carry_allowed"]
                or source_scope(frame["sample"]) != source_scope(anchor["sample"])
                or native_time(frame["sample"]) - native_time(anchor["sample"]) > 10
                or frame["round_token"] != anchor["round_token"]
                or (score is not None and current_score is not None and current_score != score)
            ):
                anchor, pending, score, last_current_self = None, [], None, None
            barrier = any(set(r["signals"]) & _REPORT_VIEW_BARRIERS for r in rows)
            direct = not barrier and bool(frame["round_token"]) and frame["round"]["value"] in {
                "BUY", "ACTIVE"
            } and all(
                frame[d]["value"] == value and frame[d]["origin"] == "observation_projection"
                for d, value in [("life", "ALIVE"), ("camera", "SELF")]
            )
            if direct:
                if anchor:
                    abstaining = [deepcopy(target["sample"]) for target, _ in pending if any(
                        self._observations[i]["context"].get("unqualified_view_model") is True
                        and self._observations[i]["raw"].get("camera_hypothesis") == "UNKNOWN"
                        for i in target["observation_ids"]
                    )]
                    for target, hp_supported in pending:
                        if not hp_supported:
                            continue
                        current_ids = [i for i in target["observation_ids"]
                                       if self._observations[i]["context"].get(
                                           "unqualified_view_model") is True]
                        evidence = sorted(set(current_ids
                            + anchor["life"]["evidence_ids"] + anchor["camera"]["evidence_ids"]
                            + frame["life"]["evidence_ids"] + frame["camera"]["evidence_ids"]))
                        for domain, value, alternatives in [
                            ("life", "ALIVE", ["ALIVE", "DEAD", "UNKNOWN"]),
                            ("camera", "SELF", ["SELF", "SPECTATOR", "REMOTE", "UNKNOWN"]),
                        ]:
                            if target[domain]["value"] != "UNKNOWN":
                                continue
                            before = deepcopy(target[domain])
                            target[domain] = _estimate(
                                value, alternatives=alternatives, evidence=evidence,
                                reason="current_self_pixels_and_bounded_view_anchors",
                                origin="temporal_inference",
                            )
                            target[domain].update(
                                uncertainty="unqualified_report_view_continuation",
                                forward_estimate=before,
                            )
                            history.append({
                                "sample": target["sample"], "domain": domain,
                                "before": before, "after": deepcopy(target[domain]),
                                "lower_sample": anchor["sample"], "upper_sample": frame["sample"],
                                "abstaining_view_samples": deepcopy(abstaining),
                                "kind": "view_estimate_revision_not_event", "qualified": False,
                                "Map_authority": False,
                            })
                anchor, pending, score = frame, [], current_score
                last_current_self = native_time(frame["sample"])
                continue
            compatible, supported = self._report_view_support(frame)
            current_self = any(
                r["context"].get("unqualified_view_model") is True
                and r["raw"].get("camera_hypothesis") == "SELF" for r in rows
            )
            if not compatible or any(
                frame[d]["value"] not in {"UNKNOWN", value}
                or (frame[d]["value"] == "UNKNOWN" and frame[d]["reason"] not in {
                    "unobserved", "unresolved_report_and_missing_hud"
                })
                for d, value in [("life", "ALIVE"), ("camera", "SELF")]
            ) or frame["round"]["value"] in {"ENDED", "INTERMISSION"} or (
                frame["round"]["reason"] == "conflicting_observations"
            ) or (
                anchor is not None and not current_self and (
                    last_current_self is None
                    or native_time(frame["sample"]) - last_current_self > self.max_carry
                )
            ):
                anchor, pending, score, last_current_self = None, [], None, None
            elif anchor:
                pending.append((frame, supported))
                if current_self:
                    last_current_self = native_time(frame["sample"])
                if current_score is not None:
                    score = current_score
        return history

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
                            if (
                                anchor[domain]["uncertainty"]
                                == "unqualified_learned_view_candidate"
                                or est["uncertainty"] == "unqualified_learned_view_candidate"
                            ):
                                item[domain]["hypotheses"] = sorted(
                                    set(anchor[domain]["hypotheses"]) | set(est["hypotheses"])
                                )
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
                        "hypotheses": sorted({h for r in items for h in r[domain]["hypotheses"]})
                        or ["UNKNOWN"],
                        "uncertainties": sorted({r[domain]["uncertainty"] for r in items})
                        or ["unresolved"],
                        "reasons": sorted({r[domain]["reason"] for r in items})
                        or ["unobserved_second_bin"],
                        "evidence_ids": sorted(
                            {e for r in items for e in r[domain]["evidence_ids"]}
                        ),
                    }
                summary["round_number"] = round_number_summary([r["round_number"] for r in items])
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
                        "hypotheses": sorted({h for v in views for h in v[domain]["hypotheses"]})
                        or ["UNKNOWN"],
                        "uncertainties": sorted(
                            {u for v in views for u in v[domain]["uncertainties"]}
                        )
                        or ["unresolved"],
                        "reasons": sorted({r for v in views for r in v[domain]["reasons"]})
                        or ["unobserved_second_bin"],
                        "evidence_ids": sorted(
                            {e for v in views for e in v[domain]["evidence_ids"]}
                        ),
                    }
                row["round_number"] = round_number_summary([v["round_number"] for v in views])
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
        if frame_state["life"]["value"] == "ALIVE"
        and frame_state["camera"]["value"] == "SELF"
        and frame_state["life"]["hypotheses"] == ["ALIVE"]
        and frame_state["camera"]["hypotheses"] == ["SELF"]
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
