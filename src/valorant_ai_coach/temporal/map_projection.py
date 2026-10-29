"""Read current Map hypotheses from the shared engine without state or paths.

This development consumer projects the engine's native MapState and Source-second
views. It never infers Round/life/camera, declares semantic continuity, propagates
positions, qualifies ownership or connects endpoints. Raw marker candidates and
all competing/unassigned evidence remain available in the original timeline.
"""

from __future__ import annotations

import argparse
from collections import defaultdict
from copy import deepcopy
from pathlib import Path
from typing import Any

from .evidence import digest, freeze_native_sample, native_time
from .game import observation
from .replay import SourcePolicy, file_sha, read_json, write_private

VERSION = "development_current_map_projection_v1"


def project_current_map(timeline: dict[str, Any]) -> dict[str, Any]:
    if (
        timeline.get("version") != "development_game_timeline_v2"
        or timeline.get("formal_outputs") != 0
        or timeline.get("qualified_facts") != []
        or timeline.get("qualified_events") != []
    ):
        raise ValueError("Unqualified shared timeline required")
    observations = {}
    for row in timeline["observations"]:
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
            raise ValueError("Original observation digest mismatch")
        observations[row["observation_id"]] = row
    rows = []
    bins: dict[tuple[Any, ...], list[dict[str, Any]]] = defaultdict(list)
    for frame in timeline["frames"]:
        sample = freeze_native_sample(frame["sample"])
        # Only original Map samples become Map output rows. A shared pixel alias
        # in another acquisition is not another native Map observation.
        exact_map = [
            observations[k]
            for k in frame["observation_ids"]
            if k in observations
            and observations[k]["sample"] == sample
            and observations[k]["raw"].get("schema") == "map_consumer_provisional_v1"
        ]
        if not exact_map:
            continue
        state = frame["map"]
        if (
            state.get("temporal_path_eligible") is not False
            or state.get("current_view_contract") != "development_current_map_v1"
        ):
            raise ValueError("Current-only shared MapState required")
        owner_ids = state["current_recorder_view_evidence_ids"]
        current_keys = (
            "source_id",
            "source_sha256",
            "native_pts_tick",
            "native_time_base",
            "native_pixel_sha256",
            "frame_size_px",
        )
        if any(
            k not in observations
            or "owner_hud" not in observations[k]["signals"]
            or any(observations[k]["sample"][key] != sample[key] for key in current_keys)
            for k in owner_ids
        ):
            raise ValueError("Original current owner evidence required")
        if state["current_self_position_candidates"] and not owner_ids:
            raise ValueError("Current candidates require shared current-view evidence")
        pool = [c for r in exact_map for c in r["map_candidates"]]
        if any(c not in pool for c in state["current_self_position_candidates"]):
            raise ValueError("Current candidates must belong to the exact native Map pool")
        result = {
            "sample": deepcopy(sample),
            "current_position_hypotheses": deepcopy(state["current_self_position_candidates"]),
            "marker_candidate_pool": deepcopy(pool),
            "zone_candidates": deepcopy(state["zone_candidates"]),
            "current_view_evidence_ids": list(owner_ids),
            "Map_observation_ids": [r["observation_id"] for r in exact_map],
            "common_states": {d: deepcopy(frame[d]) for d in ("round", "life", "camera")},
            "reason": state["reason"],
            "semantic_continuity": "UNKNOWN",
            "temporal_path_eligible": False,
            "path": None,
            "ownership": "UNKNOWN",
            "qualification": "development_only",
            "formal_outputs": 0,
        }
        rows.append(result)
        key = sample["source_id"], sample["source_sha256"], sample["native_time_base"], int(
            native_time(sample) // 1
        )
        bins[key].append(result)
    seconds = []
    for second in timeline["seconds"]:
        key = tuple(second[k] for k in ("source_id", "source_sha256", "native_time_base", "second"))
        current = bins.get(key, [])
        seconds.append(
            {
                **{
                    k: second[k]
                    for k in ("source_id", "source_sha256", "native_time_base", "second")
                },
                "common_states": {d: deepcopy(second[d]) for d in ("round", "life", "camera")},
                "Map_observation_present": bool(current),
                "native_Map_views": deepcopy(current),
                "current_position_hypotheses": [
                    {"sample": deepcopy(r["sample"]), "candidate": deepcopy(c)}
                    for r in current
                    for c in r["current_position_hypotheses"]
                ],
                "position_status": "CANDIDATES"
                if any(r["current_position_hypotheses"] for r in current)
                else "UNKNOWN",
                "coverage": "sampled_points_only",
                "continuous_occupancy": "UNKNOWN",
                "path": None,
            }
        )
    return {
        "version": VERSION,
        "shared_timeline_revision": timeline["revision"],
        "rows": rows,
        "seconds": seconds,
        "summary": {
            "native_Map_samples": len(rows),
            "current_candidate_samples": sum(bool(r["current_position_hypotheses"]) for r in rows),
            "Source_second_rows": len(seconds),
            "UNKNOWN_position_second_bins": sum(r["position_status"] == "UNKNOWN" for r in seconds),
            "verified_correct_positions": None,
            "verified_correct_Zones": None,
        },
        "ownership": "UNKNOWN",
        "qualification": "development_only",
        "formal_outputs": 0,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("policy", "timeline", "output"):
        parser.add_argument("--" + name, type=Path, required=True)
    args = parser.parse_args()
    policy = SourcePolicy(read_json(args.policy))
    input_sha = file_sha(args.timeline)
    timeline = read_json(args.timeline)
    for row in timeline["observations"]:
        policy.admit(freeze_native_sample(row["sample"]))
    for frame in timeline["frames"]:
        policy.admit(freeze_native_sample(frame["sample"]))
    result = project_current_map(timeline)
    if input_sha != file_sha(args.timeline):
        raise ValueError("Shared timeline changed during projection")
    result["reproduction"] = {
        "timeline_sha256": input_sha,
        "policy_sha256": file_sha(args.policy),
        "code_sha256": file_sha(Path(__file__)),
        "common_code_sha256s": timeline["reproduction"]["code_sha256s"],
        "projection_sha256": digest(result),
        "new_video_decodes": 0,
        "protected_media_accesses": 0,
    }
    write_private(args.output, result)


if __name__ == "__main__":
    main()
