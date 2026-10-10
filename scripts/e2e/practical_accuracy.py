"""Separate practical time scoring; never imported by production detectors."""
from __future__ import annotations

import math
from typing import Any

from valorant_ai_coach.rounds.boundaries import BoundaryObservation

PRACTICAL_TIME_TOLERANCE_SEC = 0.1


def evaluate_matched_boundary(
    prediction: BoundaryObservation | None, *, truth_kind: str,
    truth_time_sec: float | None,
) -> dict[str, Any]:
    """Score one externally associated boundary; not a multi-event matcher.

    Independent ground truth stays on the evaluator side. Callers must establish
    one-to-one correspondence before calling this function: a nearby observation
    of another kind or a duplicate must never become an extra PASS.
    """
    if truth_kind not in {"round_start", "round_end"}:
        raise ValueError("unsupported ground truth boundary kind")
    if truth_time_sec is not None and (
        type(truth_time_sec) not in (int, float)
        or not math.isfinite(truth_time_sec) or truth_time_sec < 0
    ):
        raise ValueError("ground truth time must be finite and nonnegative")
    result: dict[str, Any] = {
        "status": "NE", "absolute_error_sec": None,
        "tolerance_sec": PRACTICAL_TIME_TOLERANCE_SEC,
        "boundary_status": prediction.boundary_status if prediction else "unknown",
    }
    if truth_time_sec is None:
        result["reason"] = "no_independent_truth_time"
    elif prediction is None or prediction.boundary_status == "unknown":
        result.update(status="FAIL", reason="boundary_unavailable")
    elif prediction.kind != truth_kind:
        result.update(status="FAIL", reason="boundary_kind_mismatch")
    else:
        assert prediction.boundary_time_sec is not None
        error = abs(prediction.boundary_time_sec - truth_time_sec)
        # Absorb floating subtraction error only, never round a predicted time.
        within = error <= PRACTICAL_TIME_TOLERANCE_SEC or math.isclose(
            error, PRACTICAL_TIME_TOLERANCE_SEC, rel_tol=0, abs_tol=1e-12,
        )
        result.update(status="PASS" if within else "FAIL", absolute_error_sec=error,
                      reason="within_practical_tolerance" if within else "time_error")
    return result
