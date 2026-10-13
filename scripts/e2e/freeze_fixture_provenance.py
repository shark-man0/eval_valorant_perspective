"""Freeze private independent review provenance after reproducing the staged GT.

Only evaluator-side artifacts are read. This does not qualify a recognizer or
register an incomplete dataset. Archived JSON and human quotes remain private.
"""
from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path

from scripts.diagnostics.assemble_approved_boundary_ledger import assemble
from scripts.e2e.assemble_pack_stage import actor_negatives
from scripts.e2e.compose_boundary_timeline import compose, merge_states
from scripts.e2e.declared_end_contract import constraint
from scripts.e2e.prepare_boundary_points import catalog, prepare
from scripts.e2e.prepare_state_negatives import fragments
from scripts.e2e.validate_fixture import digest, load, validate, validate_source
from valorant_ai_coach.hud.calibrate_temporal import _check_output_privacy


def verify_policy_approval(approval: dict, policy: dict, fixture_id: str) -> None:
    if (approval.get("video_id") != fixture_id
            or approval.get("policy_version") != policy["version"]
            or approval.get("question_reference") != policy["approval_reference"]
            or approval.get("human_response") != "match_002専用の版付き評価修正を承認"
            or approval.get("production_recognizer_input") is not False):
        raise ValueError("explicit versioned evaluator policy approval required")


def verify_chain(pack: Path, canonical: Path, paths: dict[str, Path], review_root: Path) -> dict:
    validate(pack, canonical)
    paths = dict(paths)
    initial_hashes = {name: digest(path) for name, path in paths.items()}
    timeline = load(pack / "ground_truth/timeline_ground_truth_v3.json")
    ledger = load(paths["ledger"])
    source = ledger["source_video_sha256"]
    if ledger["video_id"] != timeline["fixture_id"]:
        raise ValueError("approval ledger fixture mismatch")
    approvals = []
    for index, row in enumerate(ledger["inputs"]):
        path = (paths["ledger"].parent / row["file"]).resolve()
        if not path.is_relative_to(paths["ledger"].parent.resolve()) or digest(path) != row[
                "sha256"]:
            raise ValueError("frozen boundary approval changed or escaped")
        paths[f"boundary_approval_{index}"] = path
        approvals.append(path)
        approval = load(path)
        if "review_batch" in approval:
            ref = approval["review_batch"]
            batch = (path.parent / ref["file"]).resolve()
            if not batch.is_relative_to(path.parent) or digest(batch) != ref["sha256"]:
                raise ValueError("boundary batch changed or escaped")
            paths[f"boundary_batch_{index}"] = batch
    if assemble(approvals, len(timeline["rounds"])) != ledger:
        raise ValueError("approved ledger no longer reproduces from human records")
    hashes = {name: digest(path) for name, path in paths.items()}
    if any(hashes[name] != value for name, value in initial_hashes.items()):
        raise ValueError("review input changed before provenance audit")
    evaluator_policy = load(pack / "MANIFEST.json").get("confidence_policy")
    if evaluator_policy:
        if "confidence_approval" not in paths:
            raise ValueError("explicit versioned evaluator policy approval required")
        verify_policy_approval(load(paths["confidence_approval"]), evaluator_policy,
                               timeline["fixture_id"])
    schema = load(canonical / "schemas/e2e_ground_truth_schema_v3.json")
    policy = load(canonical / "ground_truth/evaluation_policy_v3.json")
    schema_hash = digest(canonical / "schemas/e2e_ground_truth_schema_v3.json")
    policy_hash = digest(canonical / "ground_truth/evaluation_policy_v3.json")
    points, witnesses = load(paths["points"]), load(paths["witnesses"])
    declared, states = load(paths["declared_end"]), load(paths["states"])
    if (points["ledger_sha256"] != hashes["ledger"]
            or witnesses["ledger_sha256"] != hashes["ledger"]
            or points["witnesses_sha256"] != hashes["witnesses"]
            or declared["ledger_sha256"] != hashes["ledger"]):
        raise ValueError("point/declared-end provenance mismatch")
    for record in (points, declared):
        if record["schema_sha256"] != schema_hash or record["policy_sha256"] != policy_hash:
            raise ValueError("canonical Schema/policy fingerprint changed")
    rebuilt_points, point_bindings = prepare(
        ledger, witnesses, catalog(review_root, (ledger["video_id"], source)), policy)
    if rebuilt_points != points["points"] or point_bindings != points["evidence_bindings"]:
        raise ValueError("point fragments differ from approved source witnesses")
    markers = [row for row in ledger["boundaries"]
               if row["round_id"] == declared["round_id"] and row["boundary_kind"] == "round_end"]
    if (len(markers) != 1 or declared["round_package_expectations"]["event_count_constraints"]
            != [constraint(markers[0], policy)]):
        raise ValueError("declared end changed from human approval")
    state_approval, state_evidence = load(paths["state_approval"]), load(paths["state_evidence"])
    if (state_approval["review_evidence_sha256"] != hashes["state_evidence"]
            or state_approval["review_plan_sha256"] != state_evidence["schedule"]["plan_sha256"]
            or states["inputs"][paths["state_approval"].name] != hashes["state_approval"]
            or states["inputs"][paths["state_evidence"].name] != hashes["state_evidence"]):
        raise ValueError("state approval/evidence provenance changed")
    rebuilt_states, negatives, state_bindings = fragments(state_approval, state_evidence)
    if (rebuilt_states != states["states"] or negatives != states["negatives"]
            or state_bindings != states["evidence_bindings"]):
        raise ValueError("state fragments no longer reproduce from independent approval")
    score_approval = load(paths["score_approval"])
    score_review = load(paths["score_review"])
    if (score_approval["review_batch_sha256"] != hashes["score_review"]
            or score_review["fragments_sha256"] != hashes["points"]):
        raise ValueError("score review binding changed")
    rebuilt = compose(points, score_approval, load(paths["score_review"]), declared,
                      load(paths["continuity"]), schema, timeline["observation_policy"])
    rebuilt, negative = merge_states(
        rebuilt, states, source, schema,
        load(canonical / "schemas/negative_assertions_schema_v3.json"))
    profile = load(pack / "ground_truth/source_video_profile_v3.json")
    native = load(pack / "schemas/round_package_schema_v2.json")
    negative["assertions"].extend(actor_negatives(
        load(pack / "contracts/event_source_contract_v1.json"),
        native["$defs"]["event"]["properties"]["actor"]["enum"], profile["duration_sec"]))
    if (rebuilt != timeline or negative != load(pack / "ground_truth/negative_assertions_v3.json")
            or profile["sha256"] != source):
        raise ValueError("staged GT/negatives differ from independent source chain")
    for binding in point_bindings + state_bindings:
        if digest(pack / binding["evidence_path"]) != binding["sha256"]:
            raise ValueError("Pack evidence differs from reviewed source asset")
    if any(digest(paths[name]) != value for name, value in hashes.items()):
        raise ValueError("review inputs changed during provenance audit")
    return {"source_sha256": source, "fixture_id": ledger["video_id"],
            "reviewed_boundaries": len(ledger["boundaries"]),
            "reviewed_state_cores": len(state_approval["items"]),
            "production_input": False, "recognizer_qualified": False,
            "formal_pack_completed": False,
            "inputs": {name: {"path": str(paths[name]), "sha256": value}
                       for name, value in hashes.items()}}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("pack", "canonical-pack", "review-root", "ledger", "witnesses", "points",
                 "score-approval", "score-review", "declared-end", "continuity", "states",
                 "state-approval", "state-evidence", "source-video", "output"):
        parser.add_argument(f"--{name}", type=Path, required=True)
    parser.add_argument("--confidence-approval", type=Path)
    args = parser.parse_args()
    recipe = Path(__file__)
    recipe_hash = digest(recipe)
    output = args.output.resolve()
    _check_output_privacy(output)
    if output.exists():
        raise FileExistsError("use a new private provenance archive")
    keys = ("ledger", "witnesses", "points", "score_approval", "score_review", "declared_end",
            "continuity", "states", "state_approval", "state_evidence")
    if args.confidence_approval:
        keys += ("confidence_approval",)
    stage_hash = digest(args.pack / "MANIFEST.json")
    report = verify_chain(args.pack, args.canonical_pack,
                          {key: getattr(args, key) for key in keys}, args.review_root)
    validate_source(args.pack, args.source_video, "ffprobe")
    validate(args.pack, args.canonical_pack)
    if digest(args.pack / "MANIFEST.json") != stage_hash:
        raise ValueError("staged Pack changed during provenance freeze")
    if digest(recipe) != recipe_hash:
        raise ValueError("freezer code changed during audit")
    output.mkdir(parents=True)
    for name, entry in report["inputs"].items():
        destination = output / f"{name}.json"
        source = Path(entry.pop("path"))
        if digest(source) != entry["sha256"]:
            raise ValueError("approval changed before archiving")
        shutil.copyfile(source, destination)
        if digest(destination) != entry["sha256"] or digest(source) != entry["sha256"]:
            raise ValueError("approval changed during archiving")
        entry["file"] = destination.name
    report["stage_manifest_sha256"] = stage_hash
    shutil.copyfile(recipe, output / "freezer.py")
    if digest(output / "freezer.py") != recipe_hash or digest(recipe) != recipe_hash:
        raise ValueError("freezer code changed during archiving")
    report["freezer_sha256"] = recipe_hash
    report["source_verified_before_and_after"] = True
    (output / "provenance.json").write_text(json.dumps(report, indent=2, allow_nan=False) + "\n",
                                           encoding="utf-8")
    print("Frozen independent review chain; no runtime qualification or registration")


if __name__ == "__main__":
    main()
