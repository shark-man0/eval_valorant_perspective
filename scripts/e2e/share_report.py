"""Create a privacy-filtered, bounded report for sharing E2E results."""

from __future__ import annotations

import hashlib
import json
import re
from collections import Counter
from datetime import datetime
from functools import lru_cache
from pathlib import Path
from typing import Any

MAX_REPORT_BYTES = 128 * 1024
MAX_HISTORY = 20
_SAFE_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:-]{0,79}$")
_SECRETISH = re.compile(
    r"(?i)(sk-[a-z0-9_-]{8,}|gh[pousr]_[a-z0-9]{8,}|bearer|token|secret|api[_-]?key|password|eyj[a-z0-9_.-]{12,})"
)
_CATEGORIES = {
    "missing_point",
    "ordering",
    "state_coverage",
    "state_overreach",
    "state_start_edge",
    "state_end_edge",
    "ownership_coverage",
    "missing_snapshot",
    "snapshot",
    "missing_derived_snapshot",
    "derived",
    "missing_visual_observation",
    "count",
    "attribute_vocab",
    "negative_event",
    "negative_match",
    "negative_state",
    "poison",
    "poison_subset",
    "discontinuity_span",
    "confidence",
    "missing_confidence",
    "runtime_error",
}
_SECTIONS = {
    "missing_point": "HUD",
    "ordering": "round_package",
    "state_coverage": "HUD",
    "state_overreach": "HUD",
    "state_start_edge": "HUD",
    "state_end_edge": "HUD",
    "ownership_coverage": "round_package",
    "missing_snapshot": "round_package",
    "snapshot": "round_package",
    "missing_derived_snapshot": "round_package",
    "derived": "round_package",
    "missing_visual_observation": "Visual",
    "count": "e2e",
    "attribute_vocab": "e2e",
    "negative_event": "negative",
    "negative_match": "negative",
    "negative_state": "negative",
    "poison": "negative",
    "poison_subset": "negative",
    "discontinuity_span": "discontinuity",
    "confidence": "e2e",
    "missing_confidence": "e2e",
    "runtime_error": "e2e",
}


def _safe_id(value: Any) -> str | None:
    return (
        value
        if isinstance(value, str) and _SAFE_ID.fullmatch(value) and not _SECRETISH.search(value)
        else None
    )


def _vocab(value: Any, choices: set[str]) -> str | None:
    return value if isinstance(value, str) and value in choices else None


def _safe_scalar_map(value: Any, keys: set[str]) -> dict | None:
    if not isinstance(value, dict):
        return None
    result = {}
    for key in keys:
        item = value.get(key)
        if key in value and item is None:
            result[key] = None
        elif (
            isinstance(item, bool)
            or _num(item) is not None
            or isinstance(item, str)
            and item in _field_vocabulary(key)
        ):
            result[key] = item
        elif key in {"victim_name", "killer_name"} and item is not None:
            result[key] = "player"
        elif (
            key == "game_timer_display"
            and isinstance(item, str)
            and re.fullmatch(r"[0-9]{1,2}:[0-5][0-9]", item)
        ):
            result[key] = item
    return result or None


_STATES = {
    "live_first_person",
    "spectator_first_person",
    "remote_control_view",
    "buy_menu_open",
    "expanded_tactical_map",
    "unknown",
}
_ACTORS = {"player", "system", "ally", "enemy", "unknown"}
_OWNERS = {"self", "self_dead_ui", "teammate_spectated", "none", "unknown"}
_SOURCES = {
    "hud",
    "visual",
    "world_view",
    "minimap",
    "system",
    "unknown",
    "hud_temporal",
    "visual_analyzer",
    "event_fusion",
}
_FIELDS = {
    "type",
    "observation",
    "actor",
    "owner",
    "view_owner",
    "primary_state",
    "state",
    "time_sec",
    "confidence",
    "hud_confidence",
    "visual_confidence",
    "source",
    "player_hp",
    "hp",
    "armor",
    "ammo_mag",
    "ammo_current",
    "ammo_reserve",
    "score_ally",
    "score_player",
    "score_enemy",
    "ally_alive",
    "enemy_alive",
    "player_alive",
    "game_timer_display",
    "round_timer",
    "round_time_remaining_sec",
    "buy_phase_banner",
    "combat_report_visible",
    "vision_obscured_smoke",
    "spike_planted",
    "zone_id",
    "spectated_hp",
    "spectated_ammo_mag",
    "spectated_ammo_reserve",
    "victim_name",
    "killer_name",
}


@lru_cache(maxsize=128)
def _field_vocabulary(key):
    if key in {"primary_state", "state"}:
        return _STATES | {
            "buy_phase_banner",
            "round_end_banner",
            "combat_report_visible",
            "vision_obscured_smoke",
            "vision_obscured_flash",
            "visual_transition",
        }
    if key == "actor":
        return _ACTORS
    if key in {"owner", "view_owner"}:
        return _OWNERS
    if key == "source":
        return _SOURCES
    if key in {"type", "observation"}:
        return {
            "round_start",
            "round_end",
            "kill",
            "player_death",
            "spike_planted",
            "ability_state",
            "status_effect",
            "shot",
            "burst_start",
            "movement_state",
            "preaim_started",
            "peek",
            "info_peek",
            "engagement_start",
            "engagement_end",
            "position_change",
            "position_hold",
            "rotation_started",
            "rotation_completed",
            "utility_used",
            "objective_state",
            "enemy_spotted",
            "enemy_lost",
            "ally_entry_start",
            "ally_enter_site",
            "enemy_reengage",
            "hold_angle",
            "site_state",
            "utility_effect_observed",
            "state_snapshot",
            "muzzle_flash",
        }
    if key == "zone_id":
        root = Path(__file__).resolve().parents[2] / "config/map_zone_v3/config/maps"
        allowed = {"unknown"}
        for path in root.glob("*_map_*.json"):
            data = json.loads(path.read_text(encoding="utf-8"))
            allowed.update(z["zone_id"] for z in data.get("zones", []))
        return allowed
    return set()


def _complete_failure_details(row, req, trace):
    category = row["category"]
    expected = _safe_scalar_map(req.get("expected"), _FIELDS) or {}
    expected.update(_safe_scalar_map(req, _FIELDS - {"time_sec"}) or {})
    if req.get("field") in _FIELDS:
        expected.update(_safe_scalar_map({req["field"]: req.get("expected")}, _FIELDS) or {})
    expected.update(_safe_scalar_map(req.get("required_event_attributes"), _FIELDS) or {})
    for key in (
        "must_not_emit_matching",
        "must_not_state_match",
        "must_not_update_player_fields_to",
        "must_not_match_snapshot_subset",
    ):
        cleaned = _safe_scalar_map(req.get(key), _FIELDS)
        if cleaned:
            expected[key] = cleaned
    if isinstance(req.get("must_not_emit_player_event_types"), list):
        expected["must_not_emit_player_event_types"] = [
            value
            for value in req["must_not_emit_player_event_types"]
            if isinstance(value, str) and value in _field_vocabulary("type")
        ]
    if "must_not_span_temporal_features" in req:
        expected["temporal_feature_must_not_span_interval"] = True
    if category == "ordering":
        expected["before_then_after"] = True
    for key in ("min", "max", "min_core_coverage"):
        if _num(req.get(key)) is not None:
            expected[key] = req[key]
    row["expected"] = expected or None
    group = (
        "state_intervals"
        if category.startswith("state_") or category == "negative_state"
        else "ownership_intervals"
        if category == "ownership_coverage"
        else "snapshots"
        if "snapshot" in category or category in {"derived", "poison", "poison_subset"}
        else "visual_observations"
        if category == "missing_visual_observation"
        else "temporal_features"
        if category == "discontinuity_span"
        else "events"
    )
    candidates = []
    target = _num(req.get("time_sec"))
    window = row["interval"]
    if target is not None:
        tol = _num(req.get("tolerance_sec")) or 0
        window = [target - tol, target + tol]
    for value in trace.get(group, []):
        if req.get("round_id") is not None and value.get("round_id") != req["round_id"]:
            continue
        t, iv = _num(value.get("time_sec")), value.get("interval")
        if window:
            if t is not None and not window[0] <= t <= window[1]:
                continue
            if t is None and not (
                isinstance(iv, list)
                and len(iv) == 2
                and all(_num(x) is not None for x in iv)
                and iv[0] <= window[1]
                and iv[1] >= window[0]
            ):
                continue
        candidates.append(value)
    if category == "count":
        row["actual"] = {
            "count": sum(
                v.get("type") == req.get("type") and v.get("actor") == req.get("actor")
                for v in candidates
            )
        }
    elif candidates:
        chosen = (
            min(candidates, key=lambda x: abs(x.get("time_sec", target or 0) - target))
            if target is not None
            else candidates[0]
        )
        actual = _safe_scalar_map(chosen, _FIELDS) or {}
        actual.update(_safe_scalar_map(chosen.get("attributes"), _FIELDS) or {})
        iv = chosen.get("interval")
        if isinstance(iv, list) and len(iv) == 2 and all(_num(x) is not None for x in iv):
            actual["interval"] = iv
        row["actual"] = actual or None
        row["actor"] = _vocab(chosen.get("actor"), _ACTORS) or row["actor"]
        row["screen_state"] = _vocab(chosen.get("primary_state", chosen.get("state")), _STATES)
        row["view_owner"] = _vocab(chosen.get("view_owner", chosen.get("owner")), _OWNERS)
        row["confidence"] = chosen.get("confidence", chosen.get("hud_confidence"))
        row["confidence"] = _num(row["confidence"])
        row["source"] = _vocab(actual.get("source"), _SOURCES) or "reference_evaluator"
    else:
        row["actual"] = None
    row["screen_state"] = _vocab(row["screen_state"], _STATES)
    row["context_only"] = True  # nearest row is context, not a claimed matching detection
    if req.get("field") == "zone_id" or (
        isinstance(req.get("expected"), dict) and "zone_id" in req["expected"]
    ):
        row["section"] = "map_zone"


def _num(value: Any) -> int | float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    if value != value or value in (float("inf"), float("-inf")):
        return None
    return value


def _iso_datetime(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    return value if parsed.tzinfo is not None else None


def _clean_history_entry(item: Any) -> dict | None:
    if not isinstance(item, dict) or not re.fullmatch(
        r"[a-fA-F0-9]{64}", str(item.get("history_key", ""))
    ):
        return None
    old_meta = item.get("metadata") if isinstance(item.get("metadata"), dict) else {}
    old_result = item.get("result") if isinstance(item.get("result"), dict) else {}
    clean_meta = {
        "video_id": _safe_id(old_meta.get("video_id")),
        "source_sha256": old_meta.get("source_sha256")
        if isinstance(old_meta.get("source_sha256"), str)
        and re.fullmatch(r"[a-fA-F0-9]{64}", old_meta["source_sha256"])
        else None,
        "analyzer_commit": old_meta.get("analyzer_commit")
        if isinstance(old_meta.get("analyzer_commit"), str)
        and re.fullmatch(r"[a-fA-F0-9]{7,40}", old_meta["analyzer_commit"])
        else None,
        "git_is_dirty": old_meta.get("git_is_dirty")
        if isinstance(old_meta.get("git_is_dirty"), bool)
        else None,
        "executed_at": _iso_datetime(old_meta.get("executed_at")),
        "validation_pack": _safe_id(old_meta.get("validation_pack")),
        "validation_pack_sha256": old_meta.get("validation_pack_sha256")
        if isinstance(old_meta.get("validation_pack_sha256"), str)
        and re.fullmatch(r"[a-fA-F0-9]{64}", old_meta["validation_pack_sha256"])
        else None,
        "git_dirty_fingerprint": old_meta.get("git_dirty_fingerprint")
        if isinstance(old_meta.get("git_dirty_fingerprint"), str)
        and re.fullmatch(r"[a-fA-F0-9]{64}", old_meta["git_dirty_fingerprint"])
        else None,
        "settings_fingerprint": old_meta.get("settings_fingerprint")
        if isinstance(old_meta.get("settings_fingerprint"), str)
        and re.fullmatch(r"[a-fA-F0-9]{64}", old_meta["settings_fingerprint"])
        else None,
    }
    status = (
        old_result.get("status")
        if old_result.get("status") in ("pass", "fail", "unknown")
        else "unknown"
    )
    result = {
        "status": status,
        "schema_valid": old_result.get("schema_valid")
        if isinstance(old_result.get("schema_valid"), bool)
        else None,
        "failure_count": _num(old_result.get("failure_count")),
        "negative_assertion_count": _num(old_result.get("negative_assertion_count")),
        "error_code": _safe_id(old_result.get("error_code")),
    }
    return {
        "history_key": item["history_key"],
        "metadata": clean_meta,
        "result": result,
        "failure_count": _num(item.get("failure_count")),
    }


def _trace_counts(trace: dict) -> dict:
    return {
        key: len(value) if isinstance(value, list) else None
        for key, value in (
            (k, trace.get(k))
            for k in (
                "events",
                "state_intervals",
                "ownership_intervals",
                "snapshots",
                "visual_observations",
                "temporal_features",
            )
        )
    }


def _failure_rows(evaluation: dict, assertions: dict, trace: dict) -> list[dict]:
    rows = []
    required = {}
    for group in (
        "required_point_events",
        "required_state_intervals",
        "required_ownership_intervals",
        "required_snapshots",
        "derived_assertions",
        "required_visual_observations",
        "negative_assertions",
        "event_count_constraints",
        "ordering_constraints",
    ):
        for index, item in enumerate(
            assertions.get(group, []) if isinstance(assertions.get(group, []), list) else []
        ):
            ident = (
                _safe_id(item.get("id", f"{group}-{index:03d}")) if isinstance(item, dict) else None
            )
            if ident:
                required[ident] = item
    failures = evaluation.get("failures") if isinstance(evaluation, dict) else None
    if not isinstance(failures, list):
        failures = []
    for failure in failures[:300]:
        if not isinstance(failure, str):
            continue
        parts = failure.split(":")
        category = parts[0] if parts and parts[0] in _CATEGORIES else "runtime_error"
        ident = next((p for p in parts[1:] if _safe_id(p) and p in required), None)
        if category == "ordering":
            ident = next(
                (
                    key
                    for key, req in required.items()
                    if "before" in req
                    and "after" in req
                    and failure == f"ordering:{req['before']}>={req['after']}"
                ),
                None,
            )
        if category == "count" and ident is None:
            # Evaluator's canonical count diagnostic carries round and event type.
            ident = next(
                (
                    key
                    for key, req in required.items()
                    if req in assertions.get("event_count_constraints", [])
                    and len(parts) > 2
                    and req.get("round_id") == parts[1]
                    and req.get("type") == parts[2]
                ),
                None,
            )
        req = required.get(ident, {}) if ident else {}
        interval = (
            req.get("acceptance_window")
            or req.get("core_interval")
            or req.get("outer_interval")
            or req.get("window")
        )
        if not (isinstance(interval, list) and len(interval) == 2) or not all(
            _num(x) is not None for x in interval
        ):
            interval = None
        time_sec = _num(req.get("time_sec"))
        if time_sec is None and interval is None:
            # Recover a time only from a matching, bounded assertion specification.
            time_sec = _num(req.get("time_sec"))
        section = _SECTIONS[category]
        expected = None
        actual = None
        if category == "snapshot" and isinstance(req.get("expected"), dict):
            expected = _safe_scalar_map(
                req["expected"],
                {
                    "score_ally",
                    "score_enemy",
                    "round_timer",
                    "spike_planted",
                    "ally_alive",
                    "enemy_alive",
                    "primary_state",
                    "state",
                    "owner",
                },
            )
            actual = _find_actual(trace.get("snapshots", []), req)
        elif category == "derived" and isinstance(req, dict):
            expected = _safe_scalar_map(
                {req.get("field"): req.get("expected")},
                {
                    "score_ally",
                    "score_enemy",
                    "round_timer",
                    "spike_planted",
                    "ally_alive",
                    "enemy_alive",
                    "primary_state",
                    "state",
                    "owner",
                },
            )
            actual = _find_actual(trace.get("snapshots", []), req, field=req.get("field"))
        elif category in ("missing_point", "missing_visual_observation", "count"):
            expected = _safe_scalar_map(
                {"type": req.get("type"), "observation": req.get("observation")},
                {"type", "observation"},
            )
            actual = _find_actual(
                trace.get("events", [])
                if category != "missing_visual_observation"
                else trace.get("visual_observations", []),
                req,
            )
        row = {
            "assertion_id": ident,
            "category": category,
            "expected": expected,
            "actual": actual,
            "time_sec": time_sec,
            "interval": interval if interval else None,
            "actor": _vocab(req.get("actor"), {"player", "system"}),
            "screen_state": _safe_id(req.get("state")),
            "view_owner": _vocab(
                req.get("owner"), {"self", "self_dead_ui", "teammate_spectated", "none"}
            ),
            "confidence": _num((actual or {}).get("confidence"))
            if isinstance(actual, dict)
            else None,
            "source": "reference_evaluator",
            "diagnostic_codes": [category],
            "section": section,
        }
        # A small count-only neighborhood helps distinguish missing data from mismatches.
        if interval:
            lo, hi = interval
            nearby = 0
            for group in (
                "events",
                "state_intervals",
                "ownership_intervals",
                "snapshots",
                "visual_observations",
            ):
                for item in (
                    trace.get(group, [])[:10000] if isinstance(trace.get(group), list) else []
                ):
                    t = _num(item.get("time_sec")) if isinstance(item, dict) else None
                    iv = item.get("interval") if isinstance(item, dict) else None
                    if (t is not None and lo <= t <= hi) or (
                        isinstance(iv, list)
                        and len(iv) == 2
                        and all(_num(x) is not None for x in iv)
                        and iv[0] <= hi
                        and iv[1] >= lo
                    ):
                        nearby += 1
            row["nearby_trace_row_count"] = nearby
        _complete_failure_details(row, req, trace)
        rows.append(row)
    return rows


def _find_actual(rows: Any, req: dict, field: str | None = None) -> dict | None:
    """Return safe scalar details from at most one nearest matching trace row."""
    if not isinstance(rows, list):
        return None
    target = _num(req.get("time_sec"))
    tolerance = _num(req.get("tolerance_sec")) or 0.0
    window = req.get("acceptance_window")
    candidates = []
    for row in rows[:10000]:
        if not isinstance(row, dict):
            continue
        time = _num(row.get("time_sec"))
        if target is not None and time is not None and abs(time - target) > tolerance:
            continue
        if (
            isinstance(window, list)
            and len(window) == 2
            and time is not None
            and not window[0] <= time <= window[1]
        ):
            continue
        candidates.append(row)
    if not candidates:
        return None
    chosen = (
        min(candidates, key=lambda row: abs((_num(row.get("time_sec")) or 0) - target))
        if target is not None
        else candidates[0]
    )
    allowed = {
        "type",
        "actor",
        "observation",
        "state",
        "owner",
        "time_sec",
        "confidence",
        "score_ally",
        "score_enemy",
        "round_timer",
        "spike_planted",
        "ally_alive",
        "enemy_alive",
        "primary_state",
        field,
    }
    return _safe_scalar_map(chosen, allowed - {None})


def _aggregates(raw: dict, trace: dict, evaluation: dict, assertions: dict) -> dict:
    def size(key):
        val = raw.get(key)
        return len(val) if isinstance(val, list) else None

    hud_obs = raw.get("observations")
    unknown_hud = (
        sum(not isinstance(x, dict) or x.get("primary_state") == "unknown" for x in hud_obs)
        if isinstance(hud_obs, list)
        else None
    )
    zones = raw.get("zone_resolutions")
    resolved = (
        sum(isinstance(x, dict) and x.get("zone_id") is not None for x in zones)
        if isinstance(zones, list)
        else None
    )
    unknown_zones = len(zones) - resolved if isinstance(zones, list) else None
    negatives = assertions.get("negative_assertions", [])
    negative_ids = (
        {_safe_id(x.get("id")) for x in negatives if isinstance(x, dict)}
        if isinstance(negatives, list)
        else set()
    )
    negative_ids.discard(None)
    failed_negative = {
        row["assertion_id"]
        for row in _failure_rows(evaluation, assertions, trace)
        if row["section"] == "negative" and row["assertion_id"]
    }
    discontinuity = sum(
        row["category"] == "discontinuity_span"
        for row in _failure_rows(evaluation, assertions, trace)
    )
    return {
        "hud": {
            "observations": size("observations"),
            "unknown": unknown_hud,
            "states": len(
                {
                    x.get("primary_state")
                    for x in hud_obs
                    if isinstance(x, dict) and _safe_id(x.get("primary_state"))
                }
            )
            if isinstance(hud_obs, list)
            else None,
        },
        "visual": {
            "observations": size("visual_observations"),
            "events": size("visual_events"),
            "missing_expected": sum(
                row["category"] == "missing_visual_observation"
                for row in _failure_rows(evaluation, assertions, trace)
            ),
        },
        "map_zone": {
            "resolved": resolved,
            "unknown": unknown_zones,
            "zones": len(
                {
                    x.get("zone_id")
                    for x in zones
                    if isinstance(x, dict) and _safe_id(x.get("zone_id"))
                }
            )
            if isinstance(zones, list)
            else None,
        },
        "round_package": {"rounds": size("round_packages")},
        "e2e": {
            "passed": 1
            if evaluation.get("pass") is True
            else (0 if evaluation.get("pass") is False else None),
            "failed": 0
            if evaluation.get("pass") is True
            else (1 if evaluation.get("pass") is False else None),
        },
        "negative": {
            "passed": len(negative_ids - failed_negative),
            "failed": len(negative_ids & failed_negative),
            "assertions": len(negative_ids),
        },
        "discontinuity": {"violations": discontinuity},
    }


def export_report(
    *, raw: dict, trace: dict, evaluation: dict, assertions: dict, metadata: dict, output_dir: Path
) -> Path:
    """Write summary.json, README.md and bounded history.json; return summary path."""
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    # Only explicitly named, format-checked metadata crosses the share boundary.
    meta = {
        "video_id": _safe_id(metadata.get("video_id")),
        "source_sha256": metadata.get("source_sha256")
        if isinstance(metadata.get("source_sha256"), str)
        and re.fullmatch(r"[a-fA-F0-9]{64}", metadata["source_sha256"])
        else None,
        "analyzer_commit": metadata.get("analyzer_commit")
        if isinstance(metadata.get("analyzer_commit"), str)
        and re.fullmatch(r"[a-fA-F0-9]{7,40}", metadata["analyzer_commit"])
        else None,
        "git_is_dirty": metadata.get("git_is_dirty")
        if isinstance(metadata.get("git_is_dirty"), bool)
        else None,
        "executed_at": _iso_datetime(metadata.get("executed_at")),
        "validation_pack": _safe_id(metadata.get("validation_pack")),
        "validation_pack_sha256": metadata.get("validation_pack_sha256")
        if isinstance(metadata.get("validation_pack_sha256"), str)
        and re.fullmatch(r"[a-fA-F0-9]{64}", metadata["validation_pack_sha256"])
        else None,
        "git_dirty_fingerprint": metadata.get("git_dirty_fingerprint")
        if isinstance(metadata.get("git_dirty_fingerprint"), str)
        and re.fullmatch(r"[a-fA-F0-9]{64}", metadata["git_dirty_fingerprint"])
        else None,
        "settings_fingerprint": metadata.get("settings_fingerprint")
        if isinstance(metadata.get("settings_fingerprint"), str)
        and re.fullmatch(r"[a-fA-F0-9]{64}", metadata["settings_fingerprint"])
        else None,
    }
    error_code = _safe_id(metadata.get("error_code"))
    passed = (
        evaluation.get("pass") is True
        and evaluation.get("schema_valid") is True
        and not evaluation.get("failures")
        and not error_code
    )
    failure_rows = _failure_rows(evaluation, assertions, trace)
    if error_code:
        failure_rows.append(
            {
                "assertion_id": None,
                "category": "runtime_error",
                "expected": None,
                "actual": None,
                "time_sec": None,
                "interval": None,
                "actor": None,
                "screen_state": None,
                "view_owner": None,
                "confidence": None,
                "source": "runner",
                "diagnostic_codes": ["runtime_error"],
                "section": "e2e",
            }
        )
    counts = _trace_counts(trace)
    aggregates = _aggregates(raw, trace, evaluation, assertions)
    messages = [f for f in evaluation.get("failures", []) if isinstance(f, str)]
    outcomes = evaluation.get("assertion_results")
    evaluated = evaluation.get("schema_valid") is True and not error_code
    aggregates["e2e"] = {
        "passed": sum(x["status"] == "pass" for x in outcomes)
        if evaluated and isinstance(outcomes, list)
        else None,
        "failed": sum(x["status"] == "fail" for x in outcomes)
        if evaluated and isinstance(outcomes, list)
        else None,
        "not_evaluated": sum(x["status"] == "not_evaluated" for x in outcomes)
        if evaluated and isinstance(outcomes, list)
        else None,
        "count_unit": "assertion_records; multiple failed fields count once",
        "failure_message_count": len(messages) if evaluated else None,
        "failures_by_category": dict(
            Counter(
                f.split(":", 1)[0] if f.split(":", 1)[0] in _CATEGORIES else "runtime_error"
                for f in messages
            )
        ),
    }
    negative_ids = {x.get("id") for x in assertions.get("negative_assertions", [])}
    negative_categories = {
        "negative_event",
        "negative_match",
        "negative_state",
        "poison",
        "poison_subset",
        "discontinuity_span",
    }
    failed_ids = {
        f.split(":")[1]
        for f in messages
        if len(f.split(":")) >= 2 and f.split(":")[0] in negative_categories
    }
    aggregates["negative"] = {
        "passed": len(negative_ids - failed_ids) if evaluated else None,
        "failed": len(negative_ids & failed_ids) if evaluated else None,
        "assertions": len(negative_ids),
    }
    aggregates["negative_assertions"] = aggregates["negative"]
    aggregates["discontinuity"] = {
        "violations": sum(f.startswith("discontinuity_span:") for f in messages)
        if evaluated
        else None
    }
    aggregates["known_discontinuities"] = aggregates["discontinuity"]
    if isinstance(raw.get("observations"), list):
        aggregates["hud"]["detected_states"] = dict(
            Counter(
                _vocab(x.get("primary_state"), _STATES) or "unknown" for x in raw["observations"]
            )
        )
        aggregates["hud"]["unknown"] = aggregates["hud"]["detected_states"].get("unknown", 0)
    if isinstance(raw.get("round_packages"), list):
        aggregates["round_package"]["event_count"] = sum(
            len(x.get("events", [])) for x in raw["round_packages"]
        )
    aggregates["round_package"]["round_count"] = aggregates["round_package"]["rounds"]
    aggregates["visual"]["missing_expected"] = [
        row["assertion_id"]
        for row in failure_rows
        if row["category"] == "missing_visual_observation"
    ]
    if isinstance(raw.get("zone_resolutions"), list):
        aggregates["map_zone"]["zones"] = sorted(
            {
                x["zone_id"]
                for x in raw["zone_resolutions"]
                if x.get("zone_id") in _field_vocabulary("zone_id")
            }
        )[:64]
    sections = {
        name: {
            "status": "fail"
            if any(x["section"] == name for x in failure_rows)
            else ("pass" if passed else "unknown"),
            "failure_count": sum(x["section"] == name for x in failure_rows),
        }
        for name in (
            "HUD",
            "Visual",
            "map_zone",
            "round_package",
            "e2e",
            "negative",
            "discontinuity",
        )
    }
    sections["map_zone"]["status"] = (
        "unknown" if not counts.get("events") else sections["map_zone"]["status"]
    )
    summary = {
        "schema_version": 1,
        "metadata": meta,
        "result": {
            "status": "pass" if passed and not error_code else "fail",
            "schema_valid": evaluation.get("schema_valid")
            if isinstance(evaluation, dict) and isinstance(evaluation.get("schema_valid"), bool)
            else None,
            "failure_count": _num(evaluation.get("failure_count"))
            if isinstance(evaluation, dict)
            else None,
            "negative_assertion_count": _num(evaluation.get("negative_assertion_count"))
            if isinstance(evaluation, dict)
            else None,
            "error_code": error_code,
        },
        "counts": counts,
        "sections": sections,
        "failures": failure_rows,
        "privacy": {
            "player_names": "normalized_to_player_or_omitted",
            "free_text_and_unknown_labels": "omitted",
            "images": "opt_in_manual_privacy_review_required",
        },
        **aggregates,
        "evidence_files": [
            name
            for name in metadata.get("evidence_files", [])[:10]
            if isinstance(name, str)
            and re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,79}", name)
            and not _SECRETISH.search(name)
            and name not in (".", "..")
        ]
        if isinstance(metadata.get("evidence_files", []), list)
        else [],
    }
    path = output_dir / "summary.json"
    if len(messages) > 300:
        summary["result"]["detail_truncated"] = True
    encoded = json.dumps(summary, ensure_ascii=False, indent=2, allow_nan=False) + "\n"
    if len(encoded.encode("utf-8")) > MAX_REPORT_BYTES:
        summary["failures"] = failure_rows[:30]
        summary["result"]["detail_truncated"] = True
        encoded = json.dumps(summary, ensure_ascii=False, indent=2, allow_nan=False) + "\n"
    if len(encoded.encode("utf-8")) > MAX_REPORT_BYTES:
        raise ValueError("share report exceeds size limit")
    path.write_text(encoded, encoding="utf-8")
    (output_dir / "README.md").write_text(
        "# E2E shared report\n\nThis directory contains a privacy-filtered summary only. "
        "The source video and full analyzer outputs are not included. `git_is_dirty=true` means "
        "the analyzer working tree had local changes when this run was recorded.\n",
        encoding="utf-8",
    )
    history_path = output_dir / "history.json"
    try:
        history = json.loads(history_path.read_text(encoding="utf-8"))
        if not isinstance(history, list):
            history = []
    except (OSError, ValueError):
        history = []
    key_parts = [
        meta.get(k)
        for k in ("video_id", "source_sha256", "analyzer_commit", "validation_pack_sha256")
    ]
    hist_key_values = key_parts + [
        metadata.get("git_dirty_fingerprint")
        if isinstance(metadata.get("git_dirty_fingerprint"), str)
        and re.fullmatch(r"[a-fA-F0-9]{64}", metadata["git_dirty_fingerprint"])
        else None,
        metadata.get("settings_fingerprint")
        if isinstance(metadata.get("settings_fingerprint"), str)
        and re.fullmatch(r"[a-fA-F0-9]{64}", metadata["settings_fingerprint"])
        else None,
    ]
    history_key = hashlib.sha256(
        json.dumps(hist_key_values, separators=(",", ":")).encode()
    ).hexdigest()
    entry = {
        "history_key": history_key,
        "metadata": meta,
        "result": summary["result"],
        "failure_count": summary["result"]["failure_count"],
    }
    history = [
        clean
        for x in history
        if (clean := _clean_history_entry(x)) is not None
        and clean.get("history_key") != history_key
    ]
    history.append(entry)
    history_path.write_text(
        json.dumps(history[-MAX_HISTORY:], ensure_ascii=False, indent=2, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    return path
