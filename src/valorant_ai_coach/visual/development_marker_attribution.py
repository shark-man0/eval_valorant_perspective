"""Exact-native-frame marker roles, distinct from view state and ownership.

Private callers retain source images and human annotations. Neither a reviewed
role nor candidate agreement qualifies a recorder-to-camera link. This module
has no Production Fact/Event dependency and does not estimate missing positions.
"""

from __future__ import annotations

import hashlib
import json
import math
import re
from collections import Counter
from fractions import Fraction
from typing import Any


def _digest(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, allow_nan=False,
                                     separators=(",", ":")).encode("utf-8")).hexdigest()


def _sha(value: Any) -> bool:
    return isinstance(value, str) and re.fullmatch(r"[0-9a-f]{64}", value) is not None


def _point(value: Any, size: list[int]) -> bool:
    return (isinstance(value, (list, tuple)) and len(value) == 2
            and all(isinstance(p, (int, float)) and not isinstance(p, bool)
                    and math.isfinite(p) and 0 <= p < side
                    for p, side in zip(value, size, strict=True)))


def freeze_native_sample(record: dict[str, Any], *,
                         frame_size_px: tuple[int, int]) -> dict[str, Any]:
    """Bind one sampled image, not an approximate timestamp or whole episode."""
    if (len(frame_size_px) != 2
            or any(not isinstance(n, int) or isinstance(n, bool) or n <= 0
                   for n in frame_size_px)):
        raise ValueError("Positive integer frame dimensions required")
    fields = ("source_id", "source_sha256", "acquisition_id", "native_epoch",
              "native_pts_tick", "native_time_base", "acquired_frame_sha256",
              "native_pixel_sha256")
    sample = {key: record.get(key) for key in fields}
    if (not all(_sha(sample[key]) for key in (
            "source_sha256", "acquired_frame_sha256", "native_pixel_sha256"))
            or not all(isinstance(sample[key], str) and bool(sample[key])
                       for key in ("source_id", "acquisition_id", "native_epoch"))
            or sample["acquisition_id"] != sample["native_epoch"]
            or not isinstance(sample["native_pts_tick"], int)
            or isinstance(sample["native_pts_tick"], bool)
            or not isinstance(sample["native_time_base"], str)):
        raise ValueError("Complete source/native/image identity required")
    try:
        base = Fraction(sample["native_time_base"])
    except (ValueError, ZeroDivisionError) as exc:
        raise ValueError("Positive rational native time base required") from exc
    if base <= 0:
        raise ValueError("Positive rational native time base required")
    sample["native_time_base"] = str(base)
    sample["frame_size_px"] = list(frame_size_px)
    sample["sample_sha256"] = _digest(sample)
    return sample


def assess_marker_attribution(
    sample: dict[str, Any], prediction: dict[str, Any], review: dict[str, Any] | None,
) -> dict[str, Any]:
    """Score a selected candidate only against exact, explicit human markers.

    Unmatched or overlapping annotations remain UNKNOWN. Absence of an annotated
    marker is not a negative label. No role propagates between frames. A human
    episode ID is optional; acquisition epochs never imply independent episodes.
    """
    size = sample.get("frame_size_px", [])
    if not isinstance(size, list) or len(size) != 2:
        raise ValueError("Frozen native sample required")
    frozen = freeze_native_sample(sample, frame_size_px=tuple(size))
    if (sample != frozen or prediction.get("sample_sha256") != frozen["sample_sha256"]
            or prediction.get("qualification") != "development_only"
            or prediction.get("ownership") != "UNKNOWN"
            or not _sha(prediction.get("method_fingerprint"))
            or not isinstance(prediction.get("explicit_context_rejection"), bool)):
        raise ValueError("Exact development prediction/sample binding required")
    point = prediction.get("center_frame_px")
    if point is not None and not _point(point, size):
        raise ValueError("Finite in-frame candidate required")
    if point is not None and prediction["explicit_context_rejection"]:
        raise ValueError("A rejected observation may not expose a selected candidate")
    result = {
        "qualification": "development_only", "ownership": "UNKNOWN",
        "sample_sha256": frozen["sample_sha256"],
        "method_fingerprint": prediction["method_fingerprint"],
        "source_id": frozen["source_id"], "source_sha256": frozen["source_sha256"],
        "native_time": str(Fraction(frozen["native_pts_tick"])
                           * Fraction(frozen["native_time_base"])),
        "frame_sha256": frozen["acquired_frame_sha256"],
        "prediction_sha256": _digest(prediction),
        "outcome": "HUMAN_UNREVIEWED", "candidate_role": "UNREVIEWED",
        "candidate_present": point is not None,
        "explicit_context_rejection": prediction["explicit_context_rejection"],
        "confirmed_non_live_rejection": False, "review_sha256": None,
        "purpose": "evaluation", "independent_episode_id": None,
        "human_view_state": "UNREVIEWED",
        "position_error_px": None, "map_position_error": None, "zone_error": None,
        "formal_outputs": 0,
    }
    if review is None:
        return result
    if (review.get("sample_sha256") != frozen["sample_sha256"]
            or review.get("status") != "human_confirmed"
            or review.get("sample_scope") != "this_image_only"
            or review.get("purpose") not in {"evaluation", "reference_authoring", "triage"}
            or review.get("view_state") not in {
                "SELF_LIVE", "PURCHASE", "DEATH", "SPECTATOR", "UNKNOWN"}
            or not isinstance(review.get("markers"), list)
            or len(review["markers"]) > 32
            or (review.get("independent_episode_id") is not None and (
                not isinstance(review["independent_episode_id"], str)
                or not review["independent_episode_id"]))):
        raise ValueError("Explicit exact-frame human marker review required")
    hits = []
    for marker in review["markers"]:
        tolerance = marker.get("tolerance_px")
        if (marker.get("role") not in {"SELF", "TEAMMATE", "SPECTATED", "OTHER", "UNKNOWN"}
                or not _point(marker.get("center_frame_px"), size)
                or not isinstance(tolerance, (int, float)) or isinstance(tolerance, bool)
                or not math.isfinite(tolerance) or not 0 < tolerance <= 16):
            raise ValueError("Human marker center, role and bounded tolerance required")
        if point is not None and math.dist(point, marker["center_frame_px"]) <= tolerance:
            hits.append(marker)
    result.update(review_sha256=_digest(review), purpose=review["purpose"],
                  independent_episode_id=review.get("independent_episode_id"),
                  human_view_state=review["view_state"],
                  outcome="UNKNOWN", candidate_role="UNKNOWN")
    if point is None:
        result["outcome"] = ("EXPLICIT_REJECTION" if prediction["explicit_context_rejection"]
                             else "NO_CANDIDATE")
        result["confirmed_non_live_rejection"] = (
            prediction["explicit_context_rejection"]
            and review["view_state"] in {"SPECTATOR", "DEATH", "PURCHASE"})
    elif len(hits) == 1:
        result["candidate_role"] = hits[0]["role"]
        result["outcome"] = "REVIEWED_CANDIDATE" if hits[0]["role"] != "UNKNOWN" else "UNKNOWN"
        result["position_error_px"] = math.dist(point, hits[0]["center_frame_px"])
    return result


def summarize_marker_attribution(results: list[dict[str, Any]]) -> dict[str, Any]:
    """One method at a time; duplicate native observations cannot inflate counts."""
    seen = set()
    methods = set()
    counts: Counter[str] = Counter()
    outcomes: Counter[str] = Counter()
    episodes = set()
    episode_outcomes: dict[tuple[str, str, str], set[str]] = {}
    for result in results:
        if (result.get("qualification") != "development_only"
                or result.get("ownership") != "UNKNOWN" or result.get("formal_outputs") != 0):
            raise ValueError("Development-only attribution results required")
        key = result["source_sha256"], result["native_time"]
        if key in seen:
            raise ValueError("Duplicate source/native observation in method denominator")
        seen.add(key)
        methods.add(result["method_fingerprint"])
        if len(methods) > 1:
            raise ValueError("Summarize each frozen method separately")
        counts["observations"] += 1
        if result["purpose"] != "evaluation":
            counts["fitting_observations"] += 1
            continue
        counts["evaluation_observations"] += 1
        outcome = result["outcome"]
        if outcome == "REVIEWED_CANDIDATE":
            outcome = result["candidate_role"]+"_CANDIDATE"
        outcomes[outcome] += 1
        counts["human_unreviewed"] += result["outcome"] == "HUMAN_UNREVIEWED"
        counts["candidate_not_detected"] += (not result["candidate_present"]
                                              and not result["explicit_context_rejection"])
        counts["explicit_context_rejections"] += result["explicit_context_rejection"]
        counts["confirmed_non_live_rejections"] += result["confirmed_non_live_rejection"]
        counts["self_position_candidates"] += result["candidate_role"] == "SELF"
        counts["teammate_candidates_if_used_as_self"] += result["candidate_role"] == "TEAMMATE"
        counts["spectated_candidates_if_used_as_self"] += result["candidate_role"] == "SPECTATED"
        counts["other_position_candidates"] += result["candidate_role"] == "OTHER"
        counts["unknown_candidate_role"] += (result["candidate_present"]
                                               and result["candidate_role"] == "UNKNOWN")
        counts["human_self_live_observations"] += result.get("human_view_state") == "SELF_LIVE"
        counts["self_live_context_rejections"] += (result.get("human_view_state") == "SELF_LIVE"
                                                    and result["explicit_context_rejection"])
        episode = result["independent_episode_id"]
        if episode is None or result["review_sha256"] is None:
            counts["observations_without_episode_review"] += 1
        else:
            ekey = result["source_sha256"], episode, result["purpose"]
            episodes.add(ekey)
            episode_outcomes.setdefault(ekey, set()).add(result["candidate_role"])
    return {
        **{key: counts[key] for key in (
            "observations", "evaluation_observations", "fitting_observations",
            "human_unreviewed", "candidate_not_detected", "explicit_context_rejections",
            "confirmed_non_live_rejections", "self_position_candidates",
            "teammate_candidates_if_used_as_self", "spectated_candidates_if_used_as_self",
            "other_position_candidates", "unknown_candidate_role",
            "human_self_live_observations", "self_live_context_rejections",
            "observations_without_episode_review")},
        "outcome_counts": dict(outcomes),
        "ownership_unknown": len(results), "formal_misattributions": 0,
        "independent_episodes_reviewed": len(episodes),
        "episodes_with_teammate_candidate": sum("TEAMMATE" in roles
                                                for roles in episode_outcomes.values()),
        "qualified_ownership_accuracy": None, "population_misattribution_rate": None,
        "scope": "Exact reviewed candidates; unreviewed/fitting are not correct negatives",
    }
