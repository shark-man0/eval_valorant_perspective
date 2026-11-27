"""Separate evidence factors and exact-frame DEVELOPMENT outcome accounting."""

from __future__ import annotations

import hashlib
import json
import math
import re
from collections import Counter
from typing import Any

from .development_position_review import observation_fingerprint


def marker_binding_matches(
    spec: Any, *, source_id: str, source_sha256: str | None,
    recorder_agent_id: str | None, reference_fingerprint: str | None,
) -> bool:
    """An opt-in reviewed marker library may not silently move to another actor/source."""
    if spec is None:
        return True
    return bool(isinstance(spec, dict)
                and spec.get("source_id") == source_id
                and isinstance(recorder_agent_id, str) and bool(recorder_agent_id)
                and spec.get("recorder_agent_id") == recorder_agent_id
                and spec.get("source_sha256") == source_sha256
                and spec.get("reference_fingerprint") == reference_fingerprint
                and all(isinstance(spec.get(k), str)
                        and re.fullmatch(r"[0-9a-f]{64}", spec[k]) is not None
                        for k in ["source_sha256", "reference_fingerprint", "review_sha256"]))


def identity_factors(context: dict[str, Any], recorder: dict[str, Any]) -> dict[str, Any]:
    """Explain current evidence without converting shared HUDs into live/self."""
    alias = recorder.get("actor_alias_evidence") or {}
    return {
        "qualification": "development_only", "ownership": "UNKNOWN",
        "agent_correspondence": recorder.get("association", "UNKNOWN"),
        "screen_context_candidate": context.get("view_candidate", "UNKNOWN"),
        "shared_first_person_hud_observed": any(
            c.get("claim") == "first_person_hud" and c.get("status") == "present"
            for c in context.get("observed_cues", [])),
        "current_actor_alias_support": alias.get("positive_current_alias_support") is True,
        "alias_association": alias.get("alias_association", "UNKNOWN"),
        "marker_reference_binding_valid": recorder.get("marker_reference_binding_valid"),
        "candidate_blocked": context.get("block_position_candidate") is True
                             or recorder.get("block_position_candidate") is True
                             or recorder.get("marker_reference_binding_valid") is False,
        "qualified_current_actor_link": False,
        "qualified_live_recorder_view": False,
        "missing_evidence": ["qualified_unique_recorder_to_current_actor_link",
                             "qualified_current_view_state_recognition"],
    }


def _development(record: dict[str, Any]) -> None:
    if (record.get("qualification") != "development_only"
            or record.get("ownership", {}).get("identity") != "UNKNOWN"
            or record.get("formal_self_position_fact") is not None):
        raise ValueError("Explicit UNKNOWN development records required")


def summarize_reviewed_identity(records: list[dict[str, Any]]) -> dict[str, Any]:
    """Measure candidate support/rejection separately from qualified ownership.

    PURCHASE/DEATH are non-live view labels, not proofs of another account.
    A position missed by appearance alone is not credited as a context rejection.
    Human labels must match frozen predictions; unreviewed/UNKNOWN remain visible.
    """
    groups: dict[str, Counter[str]] = {}
    for record in records:
        _development(record)
        review = record.get("view_review") or {}
        if review and (
            review.get("qualification") != "development_only"
            or review.get("ownership") != "UNKNOWN"
            or review.get("sample_scope") != "this_observation_only"
            or review.get("prediction_sha256") != observation_fingerprint(record)
            or review.get("frame_sha256") != record.get("acquired_frame_sha256")
            or not isinstance(review.get("frame_sha256"), str)
            or re.fullmatch(r"[0-9a-f]{64}", review["frame_sha256"]) is None
            or review.get("human_view_role") not in {
                "SELF_LIVE", "SELF_PURCHASE", "SELF_PHASE_UNKNOWN", "PURCHASE",
                "SPECTATOR", "DEATH", "UNKNOWN"}
        ):
            raise ValueError("Exact frozen frame-view review required")
        role = review.get("human_view_role", "UNREVIEWED")
        count = groups.setdefault(role, Counter())
        context = record.get("ownership_evidence") or {}
        recorder = record.get("recorder_view_evidence") or {}
        supported = recorder.get("positive_view_support") is True
        factors = identity_factors(context, recorder)
        veto = record.get("development_view_veto") or {}
        alias = recorder.get("actor_alias_evidence") or {}
        blocked = (context.get("status") == "observed"
                   and context.get("block_position_candidate") is True) or (
                       recorder.get("status") == "observed"
                       and recorder.get("block_position_candidate") is True
                       and alias.get("status") != "unavailable") or (
                           veto.get("status") == "spectator_ui" and veto.get("veto") is True)
        count["observations"] += 1
        count["automatic_ownership_unknown"] += 1
        count["agent_support"] += recorder.get("positive_agent_association") is True
        count["view_support_candidate"] += supported
        count["current_actor_alias_support"] += factors["current_actor_alias_support"]
        count["context_rejection"] += blocked
        count["authoring_or_unavailable_rejection"] += (
            not blocked and factors["candidate_blocked"])
        count["declared_view_ineligible"] += (
            record["ownership"].get("view_eligible") is False)
        count["map_position_candidates"] += record.get("map_position_norm") is not None
        if role in {"DEATH", "PURCHASE", "SELF_PURCHASE", "SPECTATOR"}:
            count["confirmed_non_live_context_rejection"] += blocked
            count["non_live_view_support_candidate"] += supported
            count["non_live_position_candidate"] += record.get("map_position_norm") is not None
            count["not_rejected_by_context"] += not blocked
        if role == "SELF_LIVE":
            count["reviewed_self_live_support_candidate"] += supported
            count["reviewed_self_live_context_rejection"] += blocked
    return {
        "qualification": "development_only", "ownership": "UNKNOWN",
        "groups": {k: dict(v) for k, v in groups.items()},
        "qualified_self_observations": 0, "qualified_account_misattribution_rate": None,
        "scope": ("Candidate support/context rejection on exact reviewed frames, "
                  "not ownership accuracy"),
    }


def compare_stationary_review(
    records: list[dict[str, Any]], review: dict[str, Any], *,
    reference_size_px: tuple[float, float], max_gap_sec: float = .3,
) -> dict[str, Any]:
    """Measure observed spread in a human-reviewed stationary sample set.

    This measures estimator variation, not absolute accuracy or an error bound.
    Missing points and acquisition/context/time breaks split the measurements.
    Every selected observation, including a miss, must be frozen in the review.
    """
    if (not records or len(records) > 200 or len(reference_size_px) != 2
            or any(not isinstance(x, (int, float)) or isinstance(x, bool)
                   or not math.isfinite(x) or x <= 0 for x in (*reference_size_px, max_gap_sec))
            or review.get("status") != "human_confirmed"
            or review.get("label_origin") != "source_stationary_sample_review"
            or review.get("not_used_for_fitting") is not True
            or review.get("sample_scope") != "listed_observations_only"
            or review.get("prediction_sha256") != [observation_fingerprint(r) for r in records]
            or review.get("frame_sha256") != [r.get("acquired_frame_sha256") for r in records]
            or any(not isinstance(x, str) or re.fullmatch(r"[0-9a-f]{64}", x) is None
                   for x in review.get("frame_sha256", []))):
        raise ValueError("Independent stationary review of exact sampled frames required")
    groups: list[list[tuple[float, float]]] = []
    previous = None
    missing = 0
    for record in records:
        _development(record)
        point = record.get("map_position_norm")
        time = record.get("time_sec")
        frame = record.get("frame_index")
        if (not isinstance(time, (int, float)) or isinstance(time, bool)
                or not math.isfinite(time) or time < 0 or not isinstance(frame, int)
                or isinstance(frame, bool) or frame < 0):
            raise ValueError("Finite source time and integer frame required")
        key = tuple(record.get(k) for k in (
            "source_id", "acquisition_id", "context_sha256", "map_id", "geometry_version"))
        if any(not isinstance(k, str) or not k for k in key):
            raise ValueError("Source/acquisition/geometry context required")
        if point is None:
            missing += 1
            previous = None
            continue
        if (not isinstance(point, (list, tuple)) or len(point) != 2
                or any(not isinstance(p, (int, float)) or isinstance(p, bool)
                       or not math.isfinite(p) or not 0 <= p <= 1 for p in point)):
            raise ValueError("Finite normalized candidate required")
        if (previous is None or key != previous[0] or frame <= previous[2]
                or not 0 < time - previous[1] <= max_gap_sec + 1e-9):
            groups.append([])
        groups[-1].append((point[0]*reference_size_px[0], point[1]*reference_size_px[1]))
        previous = key, time, frame
    runs = []
    for points in groups:
        mean = tuple(sum(p[k] for p in points)/len(points) for k in range(2))
        runs.append({
            "position_observations": len(points),
            "diameter_reference_px": max(math.dist(a, b) for a in points for b in points),
            "rms_about_mean_reference_px": math.sqrt(
                sum(math.dist(p, mean)**2 for p in points)/len(points)),
            "spread_measured": len(points) >= 2,
        })
    return {
        "qualification": "development_only", "ownership": "UNKNOWN",
        "reviewed_observations": len(records), "missing_positions": missing,
        "review_sha256": hashlib.sha256(json.dumps(
            review, sort_keys=True, allow_nan=False).encode("utf-8")).hexdigest(),
        "runs": runs, "absolute_position_accuracy": "unmeasured",
        "transferable_error_bound_reference_px": None,
        "scope": ("Spread of observed candidates only, no interpolation or "
                  "continuous stationary claim"),
    }
