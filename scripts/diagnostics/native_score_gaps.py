"""Bounded input-gap statistics; never bridge reads or release lifecycle events."""

from __future__ import annotations

import re
from collections import Counter
from fractions import Fraction

from valorant_ai_coach.hud.global_lifecycle import _score


def _summary(counts: Counter[str], reasons: Counter[str]) -> dict:
    return {
        "scope": "unqualified_native_input_availability_only",
        "counts": {key: counts[key] for key in (
            "frames", "source_break_resets", "paired_score_accepted",
            "paired_score_unavailable", "adjacent_score_changes",
            "nonadjacent_score_changes", "change_gap_frames",
        )},
        "change_gap_reasons": dict(sorted(reasons.items())),
        "continuity_proven": False,
        "qualification_created": False,
        "events_released": 0,
    }


def summarize_native_score_gaps(rows: list[dict], step: int) -> dict:
    """Require one contiguous native entrance; report no pixels, values or times.

    A change observed on opposite sides of a gap is explicitly NOT an adjacent
    transition. Missing confidence is not accepted evidence. A detected source
    break resets history, even when the decoder cadence itself is unchanged.
    These statistics do not certify continuity, an active round or a boundary.
    """
    if type(step) is not int or step <= 0:
        raise ValueError("positive native step required")
    if not rows:
        return _summary(Counter(), Counter())
    first = rows[0]
    time_base = Fraction(first["source_time_base"])
    if time_base <= 0:
        raise ValueError("positive native time base required")
    identity = tuple(first[key] for key in (
        "source_video_sha256", "source_epoch", "source_time_base", "input_fingerprint"
    ))
    if not identity[1] or any(
        re.fullmatch(r"[0-9a-f]{64}", str(identity[index])) is None
        for index in (0, 3)
    ):
        raise ValueError("complete native identity required")
    counts: Counter[str] = Counter()
    reasons: Counter[str] = Counter()
    previous_tick = None
    previous_pair = None
    gap: Counter[str] = Counter()
    for row in rows:
        tick = row["source_pts_ticks"]
        if (
            tuple(row[key] for key in (
                "source_video_sha256", "source_epoch", "source_time_base", "input_fingerprint"
            )) != identity
            or type(tick) is not int
            or (previous_tick is not None and tick - previous_tick != step)
            or re.fullmatch(r"[0-9a-f]{64}", str(row.get("source_pixel_sha256"))) is None
        ):
            raise ValueError("contiguous native source provenance required")
        previous_tick = tick
        counts["frames"] += 1
        observation = row["system_observation"]
        values = observation["values"]
        quality = observation["quality"]
        confidence = quality.get("roi_confidence", {})
        ui = row.get("system_measurements", {}).get("native_ui", {})
        if ui.get("content_jump") is True or ui.get("discontinuity") is True:
            counts["source_break_resets"] += 1
            previous_pair = None
            gap.clear()
            continue
        accepted = [
            type(values.get(key)) is int and values[key] >= 0
            and bool(_score(confidence.get(conf_key)))
            for key, conf_key in (
                ("score_ally", "score_ally_value"),
                ("score_enemy", "score_enemy_value"),
            )
        ]
        if not all(accepted):
            counts["paired_score_unavailable"] += 1
            if previous_pair is not None:
                reason = (
                    "geometry_unavailable" if "calibration_required" in quality.get("notes", [])
                    else "both_scores_unavailable" if not any(accepted)
                    else "ally_score_unavailable" if not accepted[0]
                    else "enemy_score_unavailable"
                )
                gap[reason] += 1
            continue
        counts["paired_score_accepted"] += 1
        pair = (values["score_ally"], values["score_enemy"])
        if previous_pair is not None and pair != previous_pair:
            if gap:
                counts["nonadjacent_score_changes"] += 1
                counts["change_gap_frames"] += sum(gap.values())
                reasons.update(gap)
            else:
                counts["adjacent_score_changes"] += 1
        previous_pair = pair
        gap.clear()
    return _summary(counts, reasons)
