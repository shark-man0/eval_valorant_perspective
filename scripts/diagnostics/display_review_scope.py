"""Validate opt-in development display reviews, never GT or production events.

Callers admit DEVELOPMENT sources and verify actual frame bytes before freezing
the trusted packet anchor. Metadata validation cannot certify human attention,
semantic correctness, source admission or independence. No decoder or GT writer.
"""

from __future__ import annotations

import re
from fractions import Fraction
from typing import Any

from scripts.temporal_gt.contract import canonical_hash

FRAME_FIELDS = (
    "source_id",
    "source_sha256",
    "tick",
    "time_base",
    "epoch",
    "encoded_sha256",
    "pixel_sha256",
    "expected_step_ticks",
)
STATES = {"ABSENT", "PRESENT", "PARTIAL", "COMPLETE", "UNKNOWN"}
KINDS = {"RESULT_APPEARANCE", "RESULT_DISAPPEARANCE", "RESULT_COMPLETE", "SCORE_CHANGE"}


def _require(ok: bool, reason: str) -> None:
    if not ok:
        raise ValueError(reason)


def _hash(value: Any) -> bool:
    return isinstance(value, str) and re.fullmatch("[0-9a-f]{64}", value) is not None


def _unique(rows: Any) -> dict[str, dict[str, Any]]:
    _require(isinstance(rows, list), "list required")
    found = {}
    for row in rows:
        _require(
            isinstance(row, dict)
            and isinstance(row.get("id"), str)
            and bool(row["id"])
            and row["id"] not in found,
            "unique IDs required",
        )
        found[row["id"]] = row
    return found


def _frames(case: dict[str, Any]) -> tuple[list[dict[str, Any]], dict[str, int]]:
    indexed = _unique(case.get("frames"))
    _require(bool(indexed), "native frames required")
    identity = set()
    observed = set()
    previous_ticks: dict[str, int] = {}
    rows = list(indexed.values())
    for f in rows:
        _require(
            all(
                isinstance(f.get(k), str) and bool(f[k])
                for k in ("source_id", "epoch", "time_base")
            ),
            "source/epoch/timebase required",
        )
        _require(
            re.fullmatch(r"[1-9][0-9]*/[1-9][0-9]*", f["time_base"]) is not None,
            "positive rational native timebase required",
        )
        _require(
            type(f.get("tick")) is int
            and f["tick"] >= 0
            and type(f.get("expected_step_ticks")) is int
            and f["expected_step_ticks"] > 0,
            "native integer ticks required",
        )
        _require(
            all(_hash(f.get(k)) for k in ("source_sha256", "encoded_sha256", "pixel_sha256")),
            "frame hashes required",
        )
        _require(type(f.get("discontinuity", False)) is bool, "explicit source cut flag required")
        identity.add((f["source_id"], f["source_sha256"], f["time_base"]))
        key = f["epoch"], f["tick"]
        _require(key not in observed, "duplicate native frame identity")
        _require(
            f["tick"] > previous_ticks.get(f["epoch"], -1),
            "increasing PTS within each acquisition required",
        )
        previous_ticks[f["epoch"]] = f["tick"]
        observed.add(key)
    _require(len(identity) == 1, "one source per case required")
    return rows, {f["id"]: i for i, f in enumerate(rows)}


def _interval(
    frames: list[dict[str, Any]], positions: dict[str, int], before: Any, after: Any
) -> list[dict[str, Any]]:
    _require(
        isinstance(before, str)
        and isinstance(after, str)
        and before in positions
        and after in positions,
        "foreign frame reference",
    )
    a, b = positions[before], positions[after]
    _require(a <= b, "ordered observed interval required")
    return frames[a : b + 1]


def _contiguous(rows: list[dict[str, Any]]) -> bool:
    return all(
        a["epoch"] == b["epoch"]
        and not b.get("discontinuity", False)
        and b["tick"] - a["tick"] == b["expected_step_ticks"]
        for a, b in zip(rows, rows[1:], strict=False)
    )


def _score(value: Any) -> bool:
    return (
        isinstance(value, list)
        and len(value) == 2
        and all(v is None or type(v) is int and 0 <= v <= 99 for v in value)
    )


def _state_change(kind: str, a: dict[str, Any], z: dict[str, Any]) -> bool:
    present = {"PRESENT", "PARTIAL", "COMPLETE"}
    return bool(
        kind == "RESULT_APPEARANCE"
        and a["result_state"] == "ABSENT"
        and z["result_state"] in present
        or kind == "RESULT_DISAPPEARANCE"
        and a["result_state"] in present
        and z["result_state"] == "ABSENT"
        or kind == "RESULT_COMPLETE"
        and a["result_state"] == "PARTIAL"
        and z["result_state"] == "COMPLETE"
        or kind == "SCORE_CHANGE"
        and a.get("score") is not None
        and z.get("score") is not None
        and None not in a["score"]
        and None not in z["score"]
        and a["score"] != z["score"]
    )


def validate_display_review(
    packet: dict[str, Any], response: dict[str, Any], *, trusted_packet_sha256: str
) -> dict[str, Any]:
    """Keep explicit human state brackets and scope claims as development data.

    Point presence and before/after scores never generate a transition. A
    bracket requires its own claim, reviewed endpoint states, ordered continuous
    native metadata and different pixels. Partial interval coverage is retained;
    it cannot support an interval negative or a count of physical events.
    """
    _require(
        packet.get("kind") == "development_display_review_packet_v2_1"
        and response.get("kind") == "development_display_review_response_v2_1",
        "explicit development display review v2.1 required",
    )
    _require(
        _hash(trusted_packet_sha256)
        and trusted_packet_sha256 == canonical_hash(packet)
        and response.get("packet_sha256") == trusted_packet_sha256,
        "trusted packet binding required",
    )
    _require(
        response.get("origin") == "human"
        and isinstance(response.get("reviewer"), str)
        and bool(response["reviewer"].strip()),
        "human reviewer required",
    )
    _require(
        response.get("internal_End_tick") is None
        and response.get("formal_events") == []
        and response.get("approved_gt", False) is False
        and response.get("qualification_created", False) is False,
        "no internal End, GT approval, qualification or formal event allowed",
    )
    cases, answers = _unique(packet.get("cases")), _unique(response.get("cases"))
    _require(bool(cases) and set(cases) == set(answers), "exact unique review cases required")
    results = []
    for case_id, case in cases.items():
        frames, positions = _frames(case)
        answer = answers[case_id]
        points = _unique(answer.get("points"))
        scopes = _unique(answer.get("scopes"))
        boundaries = _unique(answer.get("boundaries"))
        claims = answer.get("interval_claims")
        _require(isinstance(claims, list), "interval claims required")
        assert isinstance(claims, list)
        observations = []
        point_frames: set[str] = set()
        for p in points.values():
            _require(
                isinstance(p.get("frame_id"), str)
                and p["frame_id"] in positions
                and type(p.get("reviewed")) is bool
                and isinstance(p.get("result_state"), str)
                and p["result_state"] in STATES
                and (p.get("score") is None or _score(p["score"])),
                "valid reviewed point, score or UNKNOWN required",
            )
            _require(p["frame_id"] not in point_frames, "one point response per frame required")
            point_frames.add(p["frame_id"])
            f = frames[positions[p["frame_id"]]]
            observations.append(
                {
                    "id": p["id"],
                    "frame_id": p["frame_id"],
                    "reviewed": p["reviewed"],
                    "claimed_result_state": p["result_state"],
                    "claimed_score": p.get("score"),
                    "result_state": p["result_state"] if p["reviewed"] else "UNKNOWN",
                    "score": p.get("score") if p["reviewed"] else None,
                    "frame": {k: f[k] for k in FRAME_FIELDS},
                    "status": "HUMAN_REPORTED_POINT" if p["reviewed"] else "UNKNOWN",
                }
            )
        scope_records = {}
        for s in scopes.values():
            _require(
                isinstance(s.get("coverage"), str)
                and s["coverage"] in {"FULL", "PARTIAL", "UNKNOWN"}
                and type(s.get("full_interval_reviewed")) is bool,
                "explicit interval review coverage required",
            )
            rows = _interval(frames, positions, s.get("start"), s.get("end"))
            scope_records[s["id"]] = {
                **{k: s[k] for k in ("id", "start", "end", "coverage", "full_interval_reviewed")},
                "native_contiguous": _contiguous(rows),
                "negative_eligible": len(rows) >= 2
                and s["coverage"] == "FULL"
                and s["full_interval_reviewed"]
                and _contiguous(rows),
            }
        brackets, unknown = [], []
        for b in boundaries.values():
            kind = b.get("kind")
            _require(
                isinstance(kind, str)
                and kind in KINDS
                and isinstance(b.get("before"), str)
                and b["before"] in points
                and isinstance(b.get("after"), str)
                and b["after"] in points,
                "explicit known boundary points required",
            )
            assert isinstance(kind, str)
            a, z = points[b["before"]], points[b["after"]]
            rows = _interval(frames, positions, a["frame_id"], z["frame_id"])
            reasons = []
            if len(rows) < 2 or not _contiguous(rows):
                reasons.append("native_discontinuity_or_unordered_boundary")
            if not a["reviewed"] or not z["reviewed"]:
                reasons.append("endpoint_not_human_reviewed")
            if not _state_change(kind, a, z):
                reasons.append("state_or_score_evidence_insufficient")
            if rows[0]["pixel_sha256"] == rows[-1]["pixel_sha256"]:
                reasons.append("identical_pixels_cannot_prove_state_change")
            if reasons:
                unknown.append(
                    {"id": b["id"], "kind": kind, "status": "UNKNOWN", "reasons": reasons}
                )
                continue
            full = any(
                s["negative_eligible"]
                and positions[s["start"]] <= positions[a["frame_id"]]
                and positions[z["frame_id"]] <= positions[s["end"]]
                for s in scope_records.values()
            )
            brackets.append(
                {
                    "id": b["id"],
                    "kind": kind,
                    "before": {k: rows[0][k] for k in FRAME_FIELDS},
                    "after": {k: rows[-1][k] for k in FRAME_FIELDS},
                    "lower_tick": rows[0]["tick"],
                    "upper_tick": rows[-1]["tick"],
                    "time_base": rows[0]["time_base"],
                    "width_seconds": str(
                        (rows[-1]["tick"] - rows[0]["tick"]) * Fraction(rows[0]["time_base"])
                    ),
                    "full_interval_reviewed": full,
                    "internal_End_tick": None,
                    "physical_episode_id": None,
                    "qualified": False,
                }
            )
        negatives = []
        for claim in claims:
            _require(
                isinstance(claim, dict)
                and isinstance(claim.get("kind"), str)
                and claim["kind"] in KINDS
                and isinstance(claim.get("scope_id"), str)
                and claim["scope_id"] in scope_records
                and isinstance(claim.get("occurred"), str)
                and claim.get("occurred") in {"YES", "NO", "UNKNOWN"},
                "explicit typed interval claim required",
            )
            scope = scope_records[claim["scope_id"]]
            included = sorted(
                (
                    p
                    for p in points.values()
                    if p["reviewed"]
                    and positions[scope["start"]]
                    <= positions[p["frame_id"]]
                    <= positions[scope["end"]]
                ),
                key=lambda p: positions[p["frame_id"]],
            )
            contradicts = any(
                _state_change(claim["kind"], a, z)
                for i, a in enumerate(included)
                for z in included[i + 1 :]
            )
            if claim["occurred"] == "NO" and scope["negative_eligible"] and not contradicts:
                negatives.append(
                    {
                        **{k: claim[k] for k in ("kind", "scope_id", "occurred")},
                        "scope": scope,
                        "status": "HUMAN_REPORTED_FULL_INTERVAL",
                        "qualified": False,
                    }
                )
            else:
                if claim["occurred"] == "UNKNOWN":
                    reason = "interval_answer_unknown"
                elif claim["occurred"] == "YES":
                    reason = "positive_interval_claim_not_negative_evidence"
                elif contradicts:
                    reason = "contradictory_reviewed_points"
                else:
                    reason = "no_explicit_full_interval_negative"
                unknown.append(
                    {
                        **{k: claim[k] for k in ("kind", "scope_id", "occurred")},
                        "status": "UNKNOWN",
                        "reasons": [reason],
                    }
                )
        results.append(
            {
                "id": case_id,
                "points": observations,
                "scopes": list(scope_records.values()),
                "brackets": brackets,
                "eligible_interval_negatives": negatives,
                "unknown_claims": unknown,
            }
        )
    return {
        "kind": "development_display_observations_NOT_GT",
        "packet_sha256": trusted_packet_sha256,
        "response_sha256": canonical_hash(response),
        "reviewer": response["reviewer"],
        "cases": results,
        "internal_End_tick": None,
        "formal_events": [],
        "approved_gt": False,
        "qualification_created": False,
        "physical_event_count": None,
        "population_accuracy": None,
    }
