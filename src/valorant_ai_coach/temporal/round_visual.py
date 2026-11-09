"""Opt-in one-second Round boundary candidates from measured native HUD cues.

This projects observations, not game state. Missing HUD, an unread score, and
recording termination never establish a boundary. Every candidate remains
unqualified and points to exact native samples and observations.
"""

from __future__ import annotations

from collections import defaultdict
from fractions import Fraction
from typing import Any

from .evidence import native_time

VERSION = "development_round_visual_candidates_v1"


def _score(rows: list[dict[str, Any]]) -> tuple[int, int] | None:
    pairs = set()
    for row in rows:
        value = row.get("context", {}).get("score")
        if value is None:
            continue
        if not (isinstance(value, (list, tuple)) and len(value) == 2
                and all(type(x) is int and 0 <= x <= 99 for x in value)):
            continue
        pairs.add(tuple(value))
    return next(iter(pairs)) if len(pairs) == 1 else None


def _explicit_purchase_absence(rows: list[dict[str, Any]]) -> bool:
    """A separately positively matched absence structure, never a failed scan."""
    supported = []
    for row in rows:
        raw = row.get("raw", {})
        ui = raw.get("ui", {})
        if not isinstance(ui, dict):
            continue
        semantic = raw.get("semantic_measurements", {}).get("phase_absence_template", {})
        calibrated = raw.get("calibration", {}).get("calibrated") is True
        structure = (
            (raw.get("round_component_measurement") or {}).get("top_structure_supported") is True
        )
        visible = raw.get("hud_visibility", {})
        occluded = (ui.get("buy_menu_close_anchor_present") is True
                    or ui.get("combat_report_visible") is True
                    or any(c.get("kind") in {"BUY_MENU", "TRACKER"}
                           for c in visible.get("candidates", [])))
        positive = (ui.get("phase_absence_template") is True
                    and ui.get("phase_absence_template_scan_valid") is True
                    and ui.get("phase_absence_template_matcher") == "semantic_text_ncc_v1"
                    and isinstance(ui.get("phase_absence_template_confidence"), (int, float))
                    and not isinstance(ui.get("phase_absence_template_confidence"), bool)
                    and 0.90 <= ui["phase_absence_template_confidence"] <= 1
                    and semantic.get("presence") is True
                    and (calibrated or structure) and not occluded)
        supported.append(positive)
    return bool(supported) and any(supported)


def _groups(observations: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[tuple[Any, ...], list[dict[str, Any]]] = defaultdict(list)
    for row in observations:
        if row.get("qualification") != "development_only":
            raise ValueError("Unqualified native Round observations required")
        sample = row["sample"]
        key = (sample["source_id"], sample["source_sha256"], sample["native_epoch"],
               sample["acquisition_id"], sample["native_pts_tick"], sample["native_time_base"],
               sample["native_pixel_sha256"])
        grouped[key].append(row)
    result = []
    for rows in grouped.values():
        sample = rows[0]["sample"]
        broken = any(any(row.get("continuity", {}).get(k) is True for k in
                         ("content_break_confirmed", "source_discontinuity", "discontinuity"))
                     or row.get("continuity", {}).get("decode_ok") is False
                     for row in rows)
        result.append({"sample": sample, "time": native_time(sample), "rows": rows,
                       "signals": {s for row in rows for s in row.get("signals", [])},
                       "score": _score(rows), "broken": broken,
                       "purchase_absent": _explicit_purchase_absence(rows)})
    return sorted(result, key=lambda x: (x["sample"]["source_id"],
                   x["sample"]["source_sha256"], x["sample"]["native_epoch"],
                   x["sample"]["acquisition_id"], x["time"]))


def round_visual_candidates(
    observations: list[dict[str, Any]], *, origin: Fraction = Fraction(0),
    max_start_gap: Fraction = Fraction(5), result_score_window: Fraction = Fraction(20),
) -> dict[str, Any]:
    """Emit observed onset candidates; duplicate result/score support is folded.

    A start needs observed buy followed by positive active display or separately
    positively matched purchase-caption absence. A failed presence scan alone is
    UNKNOWN. The score cue is only a one-point monotonic increase; unread/conflicting scores
    are unknown, not zero. A new source/epoch or wide gap resets all context.
    """
    if origin < 0 or max_start_gap <= 0 or result_score_window <= 0:
        raise ValueError("Positive native observation windows required")
    candidates: list[dict[str, Any]] = []
    prior: dict[str, Any] | None = None
    last_buy: dict[str, Any] | None = None
    last_end: dict[str, Any] | None = None
    for current in _groups(observations):
        sample = current["sample"]
        same = bool(prior and all(sample[k] == prior["sample"][k]
                    for k in ("source_id", "source_sha256", "native_epoch",
                              "acquisition_id", "native_time_base", "frame_size_px")))
        gap = current["time"] - prior["time"] if same and prior else None
        if current["broken"] or not same or gap is None or gap <= 0 or gap > max_start_gap:
            last_buy = None
            if (not same or last_end is None
                    or current["time"] - last_end["time"] > result_score_window):
                last_end = None
            prior = None
        if current["broken"]:
            continue
        if "buy" in current["signals"]:
            last_buy = current
            last_end = None
        start_cue = ("purchase_display_to_active_display"
                     if "active" in current["signals"] else
                     "purchase_display_to_explicit_absence"
                     if current["purchase_absent"] else None)
        if (start_cue is not None and "buy" not in current["signals"]
                and "result" not in current["signals"]
                and not {"report", "spectator", "remote"} & current["signals"]
                and last_buy is not None
                and 0 < current["time"] - last_buy["time"] <= max_start_gap):
            previous = last_buy
            candidates.append(_candidate("start", start_cue, previous, current, origin))
            last_buy = None
            last_end = None
        result_onset = "result" in current["signals"] and (
            prior is None or "result" not in prior["signals"])
        score_increment = bool(prior and prior["score"] and current["score"]
                               and all(
                                   b >= a for a, b in zip(
                                       prior["score"], current["score"], strict=True))
                               and sum(current["score"]) - sum(prior["score"]) == 1)
        if result_onset or score_increment:
            cue = "result_display_onset" if result_onset else "score_increment"
            if (last_end is not None and same
                    and current["time"] - last_end["time"] <= result_score_window):
                # One observed ending may have both a banner and a delayed score.
                candidate = candidates[-1]
                if candidate["kind"] == "end":
                    candidate["support_cues"] = sorted(set(candidate["support_cues"] + [cue]))
                    candidate["support_observation_ids"] = sorted(set(
                        candidate["support_observation_ids"]
                        + [r["observation_id"] for r in current["rows"]]))
                    last_end = current
            else:
                candidates.append(_candidate("end", cue, prior, current, origin))
                last_end = current
        prior = current
    return {"version": VERSION, "qualification": "development_only", "formal_outputs": 0,
            "unknown_possible": True, "candidates": candidates}


def _candidate(kind: str, cue: str, prior: dict[str, Any] | None,
               current: dict[str, Any], origin: Fraction) -> dict[str, Any]:
    lower = prior["time"] if prior else current["time"]
    return {"kind": kind, "candidate_second": int((current["time"] - origin) // 1),
            "lower_native_seconds": str(lower), "upper_native_seconds": str(current["time"]),
            "support_cues": [cue], "sample_sha256": current["sample"]["sample_sha256"],
            "support_observation_ids": sorted(r["observation_id"] for r in current["rows"]),
            "qualification": "development_only", "formal_outputs": 0}


def attach_round_visual_candidates(bundle: dict[str, Any]) -> None:
    """Attach an advisory projection to an existing development application bundle."""
    if bundle.get("qualification") != "development_only" or bundle.get("formal_outputs") != 0:
        raise ValueError("Development application timeline required")
    result = round_visual_candidates(list(bundle["observations"].values()),
                                     origin=Fraction(bundle["recording"]["native_origin_seconds"]))
    bundle["round_visual_candidates"] = result
    for second in bundle["seconds"]:
        second["round_visual_candidates"] = []
    for candidate in result["candidates"]:
        index = candidate["candidate_second"]
        if 0 <= index < len(bundle["seconds"]):
            bundle["seconds"][index]["round_visual_candidates"].append(candidate)
