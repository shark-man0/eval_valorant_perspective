"""Compose private v3 boundary GT from frozen, independently approved inputs.

Unreviewed states, ownership and game-evidence discontinuities stay unannotated.
This is not formal pack completion, registration or production recognizer input.
"""
from __future__ import annotations

import argparse
import json
import shutil
from copy import deepcopy
from pathlib import Path

from jsonschema import Draft202012Validator

from scripts.e2e.run_dataset_case import sha256_file
from valorant_ai_coach.hud.calibrate_temporal import _check_output_privacy


def compose(fragments: dict, approval: dict, review: dict, declared_end: dict,
            continuity: dict, schema: dict, observation_policy: dict) -> dict:
    source = fragments["source_video_sha256"]
    if (approval.get("kind") != "independently_approved_score_number_mapping"
            or approval.get("approved_ground_truth") is not True
            or approval.get("production_input") is not False
            or approval.get("review_provenance", {}).get("reviewer") != "human user in current chat"
            or not approval["review_provenance"].get("approval_quote")
            or review.get("kind") != "private_score_number_review_not_gt"
            or review.get("recognizer_outputs_consulted") is not False):
        raise ValueError("explicit independent score-number approval required")
    if any(obj["source_video_sha256"] != source
           for obj in (approval, review, declared_end, continuity)):
        raise ValueError("source identity mismatch")
    if (review["ledger_sha256"] != fragments["ledger_sha256"]
            or declared_end["ledger_sha256"] != fragments["ledger_sha256"]):
        raise ValueError("frozen boundary ledger mismatch")
    numbers = approval["round_numbers"]
    starts = {row["round_id"] for row in fragments["points"]
              if row["point"]["type"] == "round_start"}
    if (starts != set(numbers) or starts != {row["annotation_round_id"] for row in review["items"]}
            or any(type(n) is not int or n < 1 for n in numbers.values())
            or len(set(numbers.values())) != len(numbers)):
        raise ValueError("complete unique human-approved game-round mapping required")
    rounds = {rid: {"round_id": rid, "match_round_number_from_score": n,
                    "clip_censoring": {"start": "independently_approved_boundary",
                                       "end": "independently_approved_boundary"},
                    "point_events": [], "state_intervals": [], "snapshots": [],
                    "round_package_expectations": {"event_count_constraints": []}}
              for rid, n in numbers.items()}
    kinds = {rid: set() for rid in rounds}
    for row in fragments["points"]:
        rid, point = row["round_id"], row["point"]
        kind = point["type"]
        if rid not in rounds or kind not in {"round_start", "round_end"} or kind in kinds[rid]:
            raise ValueError("duplicate or unexpected boundary")
        kinds[rid].add(kind)
        rounds[rid]["point_events"].append(deepcopy(point))
    rid = declared_end["round_id"]
    if (rid not in rounds or "round_end" in kinds[rid]
            or declared_end.get("first_native_onset_verified") is not False
            or declared_end.get("last_absent_sec") is not None):
        raise ValueError("one declared end with no fabricated witness required")
    constraints = declared_end["round_package_expectations"]["event_count_constraints"]
    if len(constraints) != 1 or constraints[0] != {
        "type": "round_end", "actor": "system", "min": 1, "max": 1,
        "window": constraints[0].get("window"),
    }:
        raise ValueError("positive declared-end exact-one contract required")
    rounds[rid]["round_package_expectations"]["event_count_constraints"].extend(
        deepcopy(constraints))
    kinds[rid].add("round_end")
    for rid, row in rounds.items():
        if kinds[rid] != {"round_start", "round_end"}:
            raise ValueError("missing approved boundary")
        # Package-wide constraints catch duplicate boundaries outside the point
        # acceptance window as well. Narrow declared-end count remains separate.
        row["round_package_expectations"]["event_count_constraints"].extend([
            {"type": kind, "actor": "system", "min": 1, "max": 1}
            for kind in ("round_start", "round_end")])
    if (continuity.get("approved_ground_truth") is not True
            or continuity.get("production_input") is not False):
        raise ValueError("explicit scoped continuity approval required")
    segments = []
    for row in continuity["items"]:
        if (row.get("continuity_approval") is not True
                or row.get("continuity_status") != "independently_reviewed_interval"
                or not row.get("approval_quote")):
            raise ValueError("unreviewed source continuity cannot be promoted")
        segments.append({"id": row["review_item_id"],
                         "interval": deepcopy(row["review_window_sec"]),
                         "reason": "Independent human continuous-source playback review; "
                                   "no player ownership or other interval approval inferred"})
    timeline = {"version": "3.0", "fixture_id": approval["video_id"],
                "timebase": {"kind": "container_pts_seconds",
                             "profile": "ground_truth/source_video_profile_v3.json"},
                "known_discontinuities": [],
                "rounds": sorted(rounds.values(),
                                 key=lambda row: row["match_round_number_from_score"]),
                "cross_round_invariants": [], "continuous_segments": segments,
                "observation_policy": deepcopy(observation_policy)}
    Draft202012Validator(schema).validate(timeline)
    return timeline


def merge_states(timeline: dict, states: dict, source_sha: str,
                 schema: dict, negative_schema: dict) -> tuple[dict, dict]:
    if (states.get("kind") != "private_v3_source_state_fragments_not_complete_pack"
            or states.get("production_input") is not False
            or states["source_video_sha256"] != source_sha):
        raise ValueError("source-bound private state fragments required")
    result = deepcopy(timeline)
    by_round = {row["round_id"]: row for row in result["rounds"]}
    ids = {item["id"] for row in result["rounds"]
           for group in ("point_events", "state_intervals", "snapshots", "ownership_intervals",
                         "visual_observations") for item in row.get(group, [])}
    for row in states["states"]:
        rid, state = row["round_id"], row["state_interval"]
        if rid not in by_round or state["id"] in ids:
            raise ValueError("unknown Round or duplicate annotation identity")
        a, b = state["core_interval"]
        c, d = state["outer_interval"]
        if not 0 <= c <= a < b <= d:
            raise ValueError("invalid state core/outer interval containment")
        ids.add(state["id"])
        by_round[rid]["state_intervals"].append(deepcopy(state))
    negatives = deepcopy(states["negatives"])
    negative_ids = [row["id"] for row in negatives["assertions"]]
    if len(set(negative_ids)) != len(negative_ids):
        raise ValueError("duplicate negative assertion identity")
    Draft202012Validator(schema).validate(result)
    Draft202012Validator(negative_schema).validate(negatives)
    if any(row["window"][0] > row["window"][1] for row in negatives["assertions"]):
        raise ValueError("reversed negative window")
    return result, negatives


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("point-fragments", "score-approval", "declared-end", "continuity",
                 "canonical-pack", "output"):
        parser.add_argument(f"--{name}", type=Path, required=True)
    parser.add_argument("--state-fragments", type=Path)
    args = parser.parse_args()
    output = args.output.resolve()
    _check_output_privacy(output)
    if output.exists():
        raise FileExistsError("use a new private timeline directory")
    approval = json.loads(args.score_approval.read_text(encoding="utf-8"))
    review_path = (args.score_approval.parent / approval["review_batch_file"]).resolve()
    if not review_path.is_relative_to(args.score_approval.parent.resolve()):
        raise ValueError("escaped review batch path")
    schema_path = args.canonical_pack / "schemas/e2e_ground_truth_schema_v3.json"
    policy_path = args.canonical_pack / "ground_truth/evaluation_policy_v3.json"
    paths = [args.point_fragments, args.score_approval, args.declared_end, args.continuity,
             review_path, schema_path, policy_path]
    negative_schema_path = args.canonical_pack / "schemas/negative_assertions_schema_v3.json"
    if args.state_fragments:
        paths.extend([args.state_fragments, negative_schema_path])
    hashes = {p: sha256_file(p) for p in paths}
    review = json.loads(review_path.read_text(encoding="utf-8"))
    if (hashes[review_path] != approval["review_batch_sha256"]
            or hashes[args.point_fragments] != review["fragments_sha256"]):
        raise ValueError("mutated approved review inputs")
    def load(path: Path) -> dict:
        return json.loads(path.read_text(encoding="utf-8"))

    for record in (load(args.point_fragments), load(args.declared_end)):
        if (record["schema_sha256"] != hashes[schema_path]
                or record["policy_sha256"] != hashes[policy_path]):
            raise ValueError("prepared fragment schema/policy differs from canonical inputs")
    observation_policy = {
        "utility_used": "Unannotated in boundary composition; no utility event inferred "
                        "from smoke onset. Existing source contract remains unchanged.",
        "shot_granularity": "Unannotated in boundary composition; existing burst-start "
                            "contract unchanged. No per-bullet counts asserted.",
    }
    timeline = compose(load(args.point_fragments), approval, review, load(args.declared_end),
                       load(args.continuity), load(schema_path), observation_policy)
    negatives = None
    bindings = []
    source_assets = []
    if args.state_fragments:
        state_record = load(args.state_fragments)
        if (state_record["inputs"][schema_path.name] != hashes[schema_path]
                or state_record["inputs"][negative_schema_path.name]
                != hashes[negative_schema_path]):
            raise ValueError("state fragment schema hashes differ from canonical schemas")
        timeline, negatives = merge_states(
            timeline, state_record, approval["source_video_sha256"],
            load(schema_path), load(negative_schema_path))
        seen = set()
        for record_path in (args.point_fragments, args.state_fragments):
            root = record_path.parent.resolve()
            for binding in load(record_path)["evidence_bindings"]:
                name = binding["evidence_path"]
                image = (root / name).resolve()
                if (name in seen or not image.is_relative_to(root)
                        or sha256_file(image) != binding["sha256"]):
                    raise ValueError("duplicate, escaped or changed source asset")
                seen.add(name)
                bindings.append(deepcopy(binding))
                source_assets.append(image)
    if any(sha256_file(p) != digest for p, digest in hashes.items()):
        raise ValueError("inputs changed during composition")
    output.mkdir(parents=True)
    if args.state_fragments:
        for binding, image in zip(bindings, source_assets, strict=True):
            destination = (output / binding["evidence_path"]).resolve()
            if not destination.is_relative_to(output):
                raise ValueError("escaped copied asset path")
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(image, destination)
            if sha256_file(destination) != binding["sha256"]:
                raise ValueError("copied evidence changed")
        if any(sha256_file(image) != binding["sha256"]
               for binding, image in zip(bindings, source_assets, strict=True)):
            raise ValueError("source evidence changed during copying")
        if any(sha256_file(p) != digest for p, digest in hashes.items()):
            raise ValueError("composition inputs changed during copying")
        (output / "evidence_bindings.json").write_text(json.dumps({
            "source_video_sha256": approval["source_video_sha256"],
            "evidence_bindings": bindings, "production_input": False,
            "formal_pack_completed": False,
        }, indent=2) + "\n", encoding="utf-8")
        (output / "negative_assertions_v3.json").write_text(
            json.dumps(negatives, indent=2) + "\n", encoding="utf-8")
    (output / "timeline_ground_truth_v3.json").write_text(
        json.dumps(timeline, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    (output / "provenance.json").write_text(json.dumps({
        "inputs": {p.name: digest for p, digest in hashes.items()},
        "formal_pack_completed": False, "production_input": False,
        "unannotated": ["player ownership", "other unreviewed state intervals",
                        "unreviewed game-evidence discontinuities including capture pause",
                        "exact score-update timing", "native first onset for declared end"],
        "no_known_discontinuities_does_not_certify_continuity": True,
    }, indent=2) + "\n", encoding="utf-8")
    print(f'Composed {len(timeline["rounds"])} approved Round boundary records; '
          'not a complete pack')


if __name__ == "__main__":
    main()
