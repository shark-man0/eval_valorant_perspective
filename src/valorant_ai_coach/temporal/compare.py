"""Fixed-input comparison; display candidates and reviewed roles are not GT events."""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

from .evidence import native_time
from .replay import file_sha, read_json, write_private


def compare(
    *,
    common: dict[str, Any],
    hud: dict[str, Any],
    map_only: dict[str, Any],
    consumer: dict[str, Any],
    supplier: dict[str, Any],
    legacy: dict[str, Any],
    role_review: dict[str, Any],
) -> dict[str, Any]:
    if consumer.get("formal_outputs") != 0:
        raise ValueError("Development Map consumer only")
    current_packets = consumer["map_observations"]
    source_packets = supplier["map_observations"]
    old_packets = [r["observation"] for r in legacy["rows"]]
    current_samples = [p["sample"] for p in current_packets]
    if current_samples != [p["sample"] for p in source_packets] or current_samples != [
        p["sample"] for p in old_packets
    ]:
        raise ValueError("Comparison must use the same ordered exact native Map samples")
    observations_changed = sum(a != b for a, b in zip(current_packets, source_packets, strict=True))
    pools_changed = sum(
        a["pool"] != b["pool"] for a, b in zip(current_packets, old_packets, strict=True)
    )
    common_index = {r["sample"]["sample_sha256"]: r for r in common["frames"]}
    shared = [r for r in hud["frames"] if r["sample"]["sample_sha256"] in common_index]
    hud_changes = sum(
        any(
            r[d]["value"] != common_index[r["sample"]["sample_sha256"]][d]["value"]
            for d in ("round", "life", "camera")
        )
        for r in shared
    )
    hints = common["supplier_boundary_hints"]
    brackets = []
    for hint in hints:
        after, before = hint["after"], hint["before"]
        rows = [
            t
            for t in common["transitions"]
            if t["kind"] == hint["kind"]
            and all(
                t["upper_sample"][k] == after[k]
                for k in ("source_sha256", "native_epoch", "native_time_base")
            )
        ]
        if not rows:
            brackets.append({"kind": hint["kind"], "found": False})
            continue
        chosen = min(rows, key=lambda t: abs(native_time(t["upper_sample"]) - native_time(after)))
        lower, upper = native_time(chosen["lower_sample"]), native_time(chosen["upper_sample"])
        brackets.append(
            {
                "kind": hint["kind"],
                "found": True,
                "overlaps_supplier_bracket": max(lower, native_time(before))
                <= min(upper, native_time(after)),
                "display_upper_endpoint_delta_sec": float(upper - native_time(after)),
            }
        )
    emitted = sum(r.get("current_observation") is not None for r in consumer["records"])
    baseline_positions = sum(r["B"].get("current_observation") is not None for r in legacy["rows"])
    reviewed_self = [
        r
        for r in role_review["reviewed_cases"]
        if r.get("role") == "RECORDER_SELF"
        and r.get("review_scope") == "exact_image_only"
        and r.get("B") == "reviewed_role_match"
    ]
    # The legacy review transport lacks exact sample IDs. All-current-abstention
    # proves those prior selections are lost; otherwise the loss is unmeasured.
    lost = len(reviewed_self) if emitted == 0 else None
    observed = common["summary"]["seconds"] - common["summary"]["missing_second_bins"]
    return {
        "common": common["summary"],
        "hud_only": hud["summary"],
        "map_only": map_only["summary"],
        "shared_hud_state_value_changes": hud_changes,
        "shared_hud_acquisition_frames": len(shared),
        "map_input_observation_changes_due_to_context": observations_changed,
        "legacy_map_candidate_pool_changes": pools_changed,
        "map_exact_native_samples": len(current_samples),
        "legacy_map_selected_candidates": baseline_positions,
        "common_map_selected_candidates": emitted,
        "previous_reviewed_self_role_selections_lost": lost,
        "reviewed_self_role_selection_scope": "exact-image roles only",
        "role_review_join_limitation": "nonzero output needs exact sample review IDs",
        "supplier_display_bracket_comparison": brackets,
        "supplier_display_brackets_found": sum(b["found"] for b in brackets),
        "supplier_display_brackets_overlapped": sum(
            b.get("overlaps_supplier_bracket", False) for b in brackets
        ),
        "source_seconds_with_observations": observed,
        "one_second_accuracy": None,
        "formal_internal_event_timing_error": None,
        "correct_round_boundaries": None,
        "false_round_boundaries": None,
        "self_ownership_accuracy": None,
        "world_position_zone_accuracy": None,
        "recognition_improvement": "NOT_ESTABLISHED",
        "qualification": "NOT_ESTABLISHED",
        "formal_outputs": 0,
        "timings": {
            key: r["reproduction"]
            for key, r in (("common", common), ("hud_only", hud), ("map_only", map_only))
        },
        "learning": common.get("learning_study"),
        "candidate_groups_are_not_verified_event_identity": True,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    for name in (
        "common",
        "hud",
        "map-only",
        "consumer",
        "supplier",
        "legacy",
        "role-review",
        "output",
    ):
        parser.add_argument("--" + name, type=Path, required=True)
    args = parser.parse_args()
    paths = {
        name: getattr(args, name)
        for name in ("common", "hud", "map_only", "consumer", "supplier", "legacy", "role_review")
    }
    result = compare(**{name: read_json(path) for name, path in paths.items()})
    result["input_sha256s"] = {name: file_sha(path) for name, path in paths.items()}
    result["comparison_implementation_sha256"] = file_sha(Path(__file__))
    write_private(args.output, result)
    print(
        {
            "map_samples": result["map_exact_native_samples"],
            "legacy_map_candidates": result["legacy_map_selected_candidates"],
            "common_map_candidates": result["common_map_selected_candidates"],
            "reviewed_self_selections_lost": result["previous_reviewed_self_role_selections_lost"],
            "display_brackets_found": result["supplier_display_brackets_found"],
            "formal_outputs": 0,
        }
    )


if __name__ == "__main__":
    main()
