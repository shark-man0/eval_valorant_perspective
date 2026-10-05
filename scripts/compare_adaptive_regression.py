from __future__ import annotations

import argparse
import bisect
import hashlib
import json
import math
import sys
from collections import Counter
from pathlib import Path
from typing import Any


def sha(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def stable_sha(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(
            value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False
        ).encode()
    ).hexdigest()


def assert_aggregate_only(value: Any) -> None:
    forbidden_keys = {"frame_key", "source_frame_index", "pts", "path", "frame_path"}
    if isinstance(value, dict):
        if forbidden_keys.intersection(value):
            raise ValueError("aggregate output contains a private locator/path field")
        for child in value.values():
            assert_aggregate_only(child)
    elif isinstance(value, list):
        for child in value:
            assert_aggregate_only(child)


def write_aggregate_exclusive(path: Path, value: dict[str, Any]) -> None:
    assert_aggregate_only(value)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8") as output:
        output.write(json.dumps(value, indent=2, ensure_ascii=False, sort_keys=True) + "\n")


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def native_index(table: dict[str, Any]) -> tuple[list[float], list[dict[str, Any]]]:
    rows = table.get("native_frames")
    if not isinstance(rows, list) or not rows:
        raise ValueError("native table must contain at least one frame")
    stream = table.get("stream_index")
    time_num, time_den = table.get("time_base_num"), table.get("time_base_den")
    if any(isinstance(x, bool) or not isinstance(x, int) or x <= 0 for x in (time_num, time_den)):
        raise ValueError("native table time base must be positive integer numerator/denominator")
    if isinstance(stream, bool) or not isinstance(stream, int) or stream < 0:
        raise ValueError("native table stream index must be a nonnegative integer")
    indices, pts = [], []
    times = []
    for row in rows:
        if not isinstance(row, dict):
            raise ValueError("native table frame rows must be objects")
        index, frame_pts = row.get("source_frame_index"), row.get("pts")
        if (
            isinstance(index, bool)
            or not isinstance(index, int)
            or index < 0
            or isinstance(frame_pts, bool)
            or not isinstance(frame_pts, int)
        ):
            raise ValueError("native frame index and PTS must be integers")
        if row.get("stream_index") != stream:
            raise ValueError("native frame stream index disagrees with table")
        try:
            seconds = float(row["best_effort_timestamp_time_sec"])
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError("native frame timestamp must be numeric") from exc
        if not math.isfinite(seconds):
            raise ValueError("native frame timestamp must be finite")
        indices.append(index)
        pts.append(frame_pts)
        times.append(seconds)
    if indices != sorted(indices) or len(set(indices)) != len(indices):
        raise ValueError("native source-frame ordinals must be strictly increasing and unique")
    if pts != sorted(pts) or len(set(pts)) != len(pts):
        raise ValueError("native PTS values must be strictly increasing and unique")
    if times != sorted(times) or len(set(times)) != len(times):
        raise ValueError("native table presentation times must be strictly increasing and unique")
    return times, rows


def bind_observations(
    raw: dict[str, Any], table: dict[str, Any]
) -> tuple[list[dict[str, Any]], dict[int, dict[str, Any]], dict[str, Any]]:
    times, native = native_index(table)
    rows: list[dict[str, Any]] = []
    by_pts: dict[int, dict[str, Any]] = {}
    seen: set[tuple[int, int]] = set()
    max_delta = 0.0
    stream = int(table["stream_index"])
    for ordinal, obs in enumerate(raw["observations"]):
        raw_t = float(obs["time_sec"])
        pos = bisect.bisect_left(times, raw_t)
        choices = [i for i in (pos - 1, pos) if 0 <= i < len(times)]
        match = min(choices, key=lambda i: abs(times[i] - raw_t))
        delta = abs(times[match] - raw_t)
        if delta > 1e-6:
            raise ValueError(
                f"observation {ordinal} does not bind to exact native PTS (delta={delta})"
            )
        max_delta = max(max_delta, delta)
        n = native[match]
        index, pts = int(n["source_frame_index"]), int(n["pts"])
        loc = (stream, pts, index)
        if loc in seen:
            raise ValueError("two observations bind to the same native locator")
        seen.add(loc)
        by_pts[pts] = obs
        q, values = obs.get("quality") or {}, obs.get("values") or {}
        snapshot = {
            "primary_state": obs.get("primary_state"),
            "state_confidence": q.get("state_confidence"),
            "hud_confidence": q.get("hud_confidence"),
            "ownership": values.get("player_specific_hud_valid"),
            "world_eligible": (obs.get("view_context") or {}).get(
                "is_player_world_view_trustworthy", False
            ),
            "reader_values": {
                k: values.get(k)
                for k in (
                    "round_time_remaining_sec",
                    "score_ally",
                    "score_enemy",
                    "ally_alive",
                    "enemy_alive",
                    "hp",
                    "armor",
                    "ammo_current",
                    "ammo_reserve",
                    "weapon_text",
                    "ability_slots",
                    "spike_state",
                    "location_text",
                    "kill_feed_rows",
                    "round_end_text",
                )
            },
            "state_flags": obs.get("state_flags", []),
            "remote_view_type": (obs.get("view_context") or {}).get("remote_view_type"),
            "relevant_roi_confidences": q.get("roi_confidence", {}),
        }
        rows.append({"frame_key": f"{stream}:{pts}:{index}", "snapshot": snapshot})
    return (
        rows,
        by_pts,
        {
            "observation_count": len(rows),
            "unique_native_locators": len(seen),
            "max_abs_time_delta_sec": max_delta,
        },
    )


def usable_times(observations: list[dict[str, Any]], duration: float) -> list[float]:
    """Descriptive reconstruction of RoundPackageBuilder._round_windows' usable filter."""
    positives = {
        "live_first_person",
        "spectator_first_person",
        "remote_control_view",
        "expanded_tactical_map",
    }
    out = set()
    for item in observations:
        q, values = item.get("quality") or {}, item.get("values") or {}
        flags = set(item.get("state_flags") or [])
        t = float(item.get("time_sec", -1))
        conf = q.get("hud_confidence")
        if (
            item.get("primary_state") in positives
            and isinstance(conf, (int, float))
            and not isinstance(conf, bool)
            and conf >= 0.65
            and not flags.intersection({"buy_phase_banner", "round_end_banner"})
            and not values.get("buy_phase_visible", False)
            and 0 <= t <= duration
        ):
            out.add(t)
    return sorted(out)


def round_window_summary(old_raw: dict[str, Any], new_raw: dict[str, Any]) -> dict[str, Any]:
    """Compare every package window and report only causes supported by measured inputs."""

    def packages_by_key(raw: dict[str, Any]) -> dict[tuple[Any, Any], dict[str, Any]]:
        result = {}
        for package in raw.get("round_packages", []):
            key = (package.get("match_id"), package.get("round_no"))
            if key in result:
                raise ValueError("duplicate round package identity")
            result[key] = package
        return result

    old_packages, new_packages = packages_by_key(old_raw), packages_by_key(new_raw)
    old_observations = old_raw.get("observations", [])
    new_observations = new_raw.get("observations", [])
    old_duration = max(
        (float(p.get("source_video", {}).get("duration_sec", 0)) for p in old_packages.values()),
        default=0,
    )
    new_duration = max(
        (float(p.get("source_video", {}).get("duration_sec", 0)) for p in new_packages.values()),
        default=0,
    )

    def describe(
        raw: dict[str, Any],
        package: dict[str, Any],
        observations: list[dict[str, Any]],
        duration: float,
    ) -> dict[str, Any]:
        window = package.get("round_window") or {}
        start, end = float(window.get("start_sec", 0)), float(window.get("end_sec", 0))
        scoped = [o for o in observations if start <= float(o.get("time_sec", -1)) <= end]
        eligible = usable_times(scoped, duration)
        first = eligible[0] if eligible else None
        global_eligible = usable_times(observations, duration)
        global_first = global_eligible[0] if global_eligible else None
        boundary_count = sum(
            e.get("type") in {"round_start", "round_end"}
            and start <= float(e.get("time_sec", -1)) <= end
            for e in raw.get("hud_events", [])
        )
        run_boundary_count = sum(
            e.get("type") in {"round_start", "round_end"} for e in raw.get("hud_events", [])
        )
        start_matches_first = first is not None and abs(first - start) <= 1e-9
        start_matches_global_first = global_first is not None and abs(global_first - start) <= 1e-9
        first_row = next((o for o in scoped if float(o.get("time_sec", -1)) == first), None)
        return {
            "window": {"start_sec": start, "end_sec": end},
            "boundary_event_count": boundary_count,
            "run_boundary_event_count": run_boundary_count,
            "run_package_count": len(raw.get("round_packages", [])),
            "earliest_usable_sample": {
                "present": first is not None,
                "state": first_row.get("primary_state") if first_row else None,
                "hud_confidence": (first_row.get("quality") or {}).get("hud_confidence")
                if first_row
                else None,
                "flags": first_row.get("state_flags", []) if first_row else None,
            },
            "start_matches_earliest_usable_sample": start_matches_first,
            "start_matches_global_earliest_usable_sample": start_matches_global_first,
            "fallback_causality_eligible": (
                len(raw.get("round_packages", [])) == 1
                and run_boundary_count == 0
                and start_matches_global_first
            ),
            "_first_time": global_first,
        }

    common = sorted(old_packages.keys() & new_packages.keys(), key=lambda x: (str(x[0]), str(x[1])))
    comparisons = []
    for match_id, round_no in common:
        old = describe(old_raw, old_packages[(match_id, round_no)], old_observations, old_duration)
        new = describe(new_raw, new_packages[(match_id, round_no)], new_observations, new_duration)
        start_delta = round(new["window"]["start_sec"] - old["window"]["start_sec"], 9)
        end_delta = round(new["window"]["end_sec"] - old["window"]["end_sec"], 9)
        if start_delta == 0 and end_delta == 0:
            cause = "window_bounds_unchanged"
        elif (
            old["fallback_causality_eligible"]
            and new["fallback_causality_eligible"]
            and old["_first_time"] is not None
            and old["_first_time"] != new["_first_time"]
        ):
            old_first_in_new = next(
                (o for o in new_observations if float(o.get("time_sec", -1)) == old["_first_time"]),
                None,
            )
            if old_first_in_new is None:
                cause = "baseline_earliest_usable_sample_removed_from_current_sampling"
            elif old["_first_time"] not in usable_times([old_first_in_new], new_duration):
                cause = "baseline_start_sample_retained_but_fails_current_usable_filter"
            else:
                cause = "fallback_start_difference_not_explained_by_old_first_sample"
        else:
            cause = "boundary_or_nonfallback_difference_requires_review"
        comparisons.append(
            {
                "round_no": round_no,
                "baseline": {k: v for k, v in old.items() if not k.startswith("_")},
                "current": {k: v for k, v in new.items() if not k.startswith("_")},
                "start_delta_sec": start_delta,
                "end_delta_sec": end_delta,
                "measured_cause": cause,
            }
        )
    return {
        "baseline_package_count": len(old_packages),
        "current_package_count": len(new_packages),
        "paired_package_count": len(common),
        "baseline_only_package_count": len(old_packages.keys() - new_packages.keys()),
        "current_only_package_count": len(new_packages.keys() - old_packages.keys()),
        "comparisons": comparisons,
    }


def fact_records(raw: dict[str, Any]) -> list[dict[str, Any]]:
    records = []
    for package in raw.get("round_packages", []):
        for fact in package.get("deterministic_facts", []):
            if fact.get("key") in {"hp", "round_time_remaining_sec"}:
                records.append(
                    {
                        "_package_match_id": package.get("match_id"),
                        "_package_round_no": package.get("round_no"),
                        **fact,
                    }
                )
    return records


def fact_summary(old_raw: dict[str, Any], new_raw: dict[str, Any]) -> dict[str, Any]:
    old_facts, new_facts = fact_records(old_raw), fact_records(new_raw)
    new_times = {float(o["time_sec"]) for o in new_raw["observations"]}

    def semantic(f: dict[str, Any]) -> dict[str, Any]:
        # IDs are generated run-local identifiers, so compare semantic payload only.
        return {
            "package_match_id": f.get("_package_match_id"),
            "package_round_no": f.get("_package_round_no"),
            **{
                k: f.get(k)
                for k in ("key", "value", "confidence", "source", "time_sec", "time_range")
            },
        }

    def signature(f: dict[str, Any]) -> str:
        return json.dumps(
            semantic(f), sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False
        )

    result: dict[str, Any] = {}
    for key in ("hp", "round_time_remaining_sec"):
        old_selected = [f for f in old_facts if f.get("key") == key]
        new_selected = [f for f in new_facts if f.get("key") == key]
        old_counts = Counter(signature(f) for f in old_selected)
        new_counts = Counter(signature(f) for f in new_selected)
        retained = sum((old_counts & new_counts).values())
        lost_counts, gained_counts = old_counts - new_counts, new_counts - old_counts
        lost_facts = []
        remaining_lost = lost_counts.copy()
        for fact in old_selected:
            fact_signature = signature(fact)
            if remaining_lost[fact_signature] > 0:
                lost_facts.append(fact)
                remaining_lost[fact_signature] -= 1
        gained = sum(gained_counts.values())
        lost = sum(lost_counts.values())
        old_slots = {
            (f.get("_package_match_id"), f.get("_package_round_no"), f.get("time_sec"))
            for f in old_selected
        }
        new_slots = {
            (f.get("_package_match_id"), f.get("_package_round_no"), f.get("time_sec"))
            for f in new_selected
        }
        old_by_slot: dict[tuple[Any, Any, Any], Counter[str]] = {}
        new_by_slot: dict[tuple[Any, Any, Any], Counter[str]] = {}
        for f in old_selected:
            slot = (f.get("_package_match_id"), f.get("_package_round_no"), f.get("time_sec"))
            old_by_slot.setdefault(slot, Counter())[signature(f)] += 1
        for f in new_selected:
            slot = (f.get("_package_match_id"), f.get("_package_round_no"), f.get("time_sec"))
            new_by_slot.setdefault(slot, Counter())[signature(f)] += 1
        changed_slots = sum(
            old_by_slot.get(slot, Counter()) != new_by_slot.get(slot, Counter())
            for slot in old_slots & new_slots
        )
        lost_at_removed_sample = sum(
            1
            for f in lost_facts
            if f.get("time_sec") is not None and float(f["time_sec"]) not in new_times
        )
        lost_at_common_sample = lost - lost_at_removed_sample
        result[key] = {
            "baseline_count": len(old_selected),
            "current_count": len(new_selected),
            "semantic_records_retained_unchanged": retained,
            "semantic_records_lost": lost,
            "semantic_records_gained": gained,
            "semantic_slots_changed": changed_slots,
            "lost_at_removed_observation_time": lost_at_removed_sample,
            "lost_at_common_observation_time": lost_at_common_sample,
        }
    return result


def validate_run_inputs(
    raw: dict[str, Any], metadata: dict[str, Any], raw_path: Path, table: dict[str, Any]
) -> None:
    run_meta = metadata.get("metadata")
    if not isinstance(run_meta, dict):
        raise ValueError("run metadata is missing metadata object")
    source_sha = run_meta.get("source_sha256")
    if source_sha != table.get("source_video_sha256"):
        raise ValueError("run metadata source SHA does not match native table")
    if type(run_meta.get("git_is_dirty")) is not bool:
        raise ValueError("run metadata git_is_dirty must be a boolean")
    input_hashes = metadata.get("input_hashes")
    expected_raw_sha = (
        input_hashes.get("raw_processing.json") if isinstance(input_hashes, dict) else None
    )
    if expected_raw_sha != sha(raw_path):
        raise ValueError("raw_processing SHA does not match run metadata input hash")
    if not isinstance(raw.get("observations"), list):
        raise ValueError("raw processing observations must be a list")
    if not isinstance(raw.get("round_packages"), list):
        raise ValueError("raw processing round_packages must be a list")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--old-raw", type=Path, required=True)
    ap.add_argument("--old-metadata", type=Path, required=True)
    ap.add_argument("--new-raw", type=Path, required=True)
    ap.add_argument("--new-metadata", type=Path, required=True)
    ap.add_argument("--native-frame-table", type=Path, required=True)
    ap.add_argument("--output", type=Path, required=True)
    ap.add_argument("--repo", type=Path, required=True)
    args = ap.parse_args()
    table = load_json(args.native_frame_table)
    old_raw, new_raw = load_json(args.old_raw), load_json(args.new_raw)
    old_meta, new_meta = load_json(args.old_metadata), load_json(args.new_metadata)
    validate_run_inputs(old_raw, old_meta, args.old_raw, table)
    validate_run_inputs(new_raw, new_meta, args.new_raw, table)
    source_sha = old_meta["metadata"]["source_sha256"]
    if (
        source_sha != new_meta["metadata"]["source_sha256"]
        or source_sha != table["source_video_sha256"]
    ):
        raise ValueError("source video SHA mismatch")
    old_rows, _old_by_pts, old_bind = bind_observations(old_raw, table)
    new_rows, _new_by_pts, new_bind = bind_observations(new_raw, table)

    def doc(rows: list[dict[str, Any]]) -> dict[str, Any]:
        locators = sorted(r["frame_key"] for r in rows)
        return {
            "manifest_sha256": stable_sha({"source_sha256": source_sha, "locators": locators}),
            "source_sha256": source_sha,
            "frames": rows,
        }

    sys.path.insert(0, str(args.repo / "scripts"))
    from fixed_replay_comparison import compare_adaptive_sampling

    compared = compare_adaptive_sampling(doc(old_rows), doc(new_rows), interpretation="unresolved")
    old_obs, new_obs = old_raw["observations"], new_raw["observations"]
    round_windows = round_window_summary(old_raw, new_raw)
    comparison = {
        "schema_version": 2,
        "runs": {
            "baseline": {
                "run_id": args.old_raw.parent.name,
                "analyzer_commit": old_meta["metadata"]["analyzer_commit"],
                "git_is_dirty": old_meta["metadata"]["git_is_dirty"],
                "raw_sha256": sha(args.old_raw),
                "run_metadata_sha256": sha(args.old_metadata),
                "settings_fingerprint": old_meta["metadata"]["settings_fingerprint"],
                "observation_count": len(old_obs),
            },
            "current": {
                "run_id": args.new_raw.parent.name,
                "analyzer_commit": new_meta["metadata"]["analyzer_commit"],
                "git_is_dirty": new_meta["metadata"]["git_is_dirty"],
                "raw_sha256": sha(args.new_raw),
                "run_metadata_sha256": sha(args.new_metadata),
                "settings_fingerprint": new_meta["metadata"]["settings_fingerprint"],
                "observation_count": len(new_obs),
            },
        },
        "comparison_implementation": {
            "fixed_replay_comparison_sha256": sha(
                args.repo / "scripts" / "fixed_replay_comparison.py"
            ),
            "native_frame_table_sha256": sha(args.native_frame_table),
            "adapter_sha256": sha(Path(__file__)),
            "locator_contract": (
                "stream_index:PTS:zero_based_source_frame_index from exact native table time match"
            ),
        },
        "native_locator_binding": {"baseline": old_bind, "current": new_bind},
        "adaptive_comparison": compared,
        "published_fact_comparison": fact_summary(old_raw, new_raw),
        "round_windows": round_windows,
        "limitations": [
            "Serialized outputs only; no detector replay or frame extraction.",
            "No per-frame identifiers, paths, or timestamps are emitted; locators exist "
            "only in memory for pairing.",
            "Fact identifiers and provenance event IDs are excluded from semantic record equality.",
        ],
    }
    write_aggregate_exclusive(args.output, comparison)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
