"""Stage private v3 fixtures with original or explicit match_002 evaluator policy.

No old fixture GT, aliases, source images or player context are copied. The
formal validator/registration gate remains absent until qualification is done.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import math
import shutil
from pathlib import Path

from jsonschema import Draft202012Validator

from scripts.e2e.match002_confidence_evaluator_v1 import POLICY_VERSION
from scripts.e2e.run_dataset_case import sha256_file
from valorant_ai_coach.hud.calibrate_temporal import _check_output_privacy


def actor_negatives(contract: dict, actors: list[str], duration: float) -> list[dict]:
    if type(duration) not in (int, float) or not math.isfinite(duration) or duration <= 0:
        raise ValueError("finite source duration required")
    rows = []
    for kind in ("round_start", "round_end"):
        allowed = contract["events"][kind]["allowed_actors"]
        if allowed != ["system"] or "system" not in actors:
            raise ValueError("existing system-only lifecycle contract required")
        for actor in actors:
            if actor not in allowed:
                rows.append({"id": f"NEG-CONTRACT-{kind}-{actor}", "window": [0, duration],
                             "reason": "Existing Event Source Contract requires system actor",
                             "must_not_emit_matching": {"type": kind, "actor": actor}})
    return rows


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("timeline-stage", "source-stage", "canonical-pack", "output"):
        parser.add_argument(f"--{name}", type=Path, required=True)
    parser.add_argument("--confidence-policy", choices=[POLICY_VERSION])
    args = parser.parse_args()
    output = args.output.resolve()
    _check_output_privacy(output)
    if output.exists():
        raise FileExistsError("use a new private pack-stage directory")

    def load(path: Path) -> dict:
        return json.loads(path.read_text(encoding="utf-8"))

    if args.confidence_policy and load(
            args.timeline_stage / "timeline_ground_truth_v3.json")["fixture_id"] != "match_002":
        raise ValueError("versioned confidence policy is restricted to match_002")
    bindings_path = args.timeline_stage / "evidence_bindings.json"
    bindings = load(bindings_path)
    profile = load(args.source_stage / "source_video_profile_v3.json")
    sidecar = load(args.source_stage / "frame_pts_sidecar_v3.json")
    provenance = load(args.source_stage / "provenance.json")
    if (provenance["point_fragments_sha256"] != sha256_file(bindings_path)
            or provenance.get("source_hash_verified_after_probe") is not True
            or provenance["source_sha256"] != profile["sha256"]
            or bindings["source_video_sha256"] != profile["sha256"]):
        raise ValueError("verified combined source provenance required")
    assets = {row["evidence_path"] for row in bindings["evidence_bindings"]}
    if (len(assets) != len(bindings["evidence_bindings"])
            or assets != {row["evidence_path"] for row in sidecar["entries"]}
            or len(assets) != len(sidecar["entries"])):
        raise ValueError("one exact PTS entry per source asset required")
    files = {
        "ground_truth/timeline_ground_truth_v3.json":
            args.timeline_stage / "timeline_ground_truth_v3.json",
        "ground_truth/negative_assertions_v3.json":
            args.timeline_stage / "negative_assertions_v3.json",
        "ground_truth/source_video_profile_v3.json":
            args.source_stage / "source_video_profile_v3.json",
        "ground_truth/frame_pts_sidecar_v3.json":
            args.source_stage / "frame_pts_sidecar_v3.json",
        "ground_truth/evaluation_policy_v3.json":
            args.canonical_pack / "ground_truth/evaluation_policy_v3.json",
    }
    for name in ("schemas/e2e_ground_truth_schema_v3.json",
                 "schemas/negative_assertions_schema_v3.json", "schemas/e2e_inputs_schema_v3.json",
                 "schemas/e2e_output_trace_schema_v1.json",
                 "contracts/event_attribute_vocab_v1.json",
                 "tests/build_assertions.py", "tests/reference_evaluator.py"):
        files[name] = args.canonical_pack / name
    repository = Path(__file__).resolve().parents[2]
    files["contracts/event_source_contract_v1.json"] = (
        repository / "config/event_source_contract_v1.json")
    files["schemas/round_package_schema_v2.json"] = (
        repository / "schemas/round_package_schema_v2.json")
    if args.confidence_policy:
        files["tests/reference_evaluator_v3_base.py"] = files["tests/reference_evaluator.py"]
        files["tests/reference_evaluator.py"] = (
            repository / "scripts/e2e/match002_confidence_evaluator_v1.py")
    hashes = {path: sha256_file(path) for path in files.values()}
    hashes[bindings_path] = sha256_file(bindings_path)
    hashes[args.source_stage / "provenance.json"] = sha256_file(
        args.source_stage / "provenance.json")
    output.mkdir(parents=True)
    for name, path in files.items():
        destination = output / name
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(path, destination)
        if sha256_file(destination) != hashes[path]:
            raise ValueError("framework or source metadata copy changed")
    root = args.timeline_stage.resolve()
    for row in bindings["evidence_bindings"]:
        image, destination = (root / row["evidence_path"]).resolve(), (
            output / row["evidence_path"]).resolve()
        if (not image.is_relative_to(root) or not destination.is_relative_to(output)
                or sha256_file(image) != row["sha256"]):
            raise ValueError("escaped or changed source image")
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(image, destination)
        if sha256_file(destination) != row["sha256"]:
            raise ValueError("source image copy changed")
    inputs = {"version": "3.0", "source_video": {
        "filename": profile["source_filename"], "sha256": profile["sha256"]},
        "player_context": {"player_name": "unknown", "agent": "unknown",
                           "provenance": "No session identity supplied; never imported from GT"},
        "audio_policy": {"analyze_audio": False, "preserve_all_tracks": True,
                         "semantic_audio_ground_truth": False},
        "forbidden_runtime_inputs": ["ground_truth timestamps", "expected events",
                                     "expected labels", "reference-frame filenames"]}
    Draft202012Validator(load(output / "schemas/e2e_inputs_schema_v3.json")).validate(inputs)
    (output / "inputs").mkdir()
    (output / "inputs/e2e_inputs_v3.json").write_text(
        json.dumps(inputs, indent=2) + "\n", encoding="utf-8")
    negative_path = output / "ground_truth/negative_assertions_v3.json"
    negatives = load(negative_path)
    actors = load(output / "schemas/round_package_schema_v2.json")["$defs"]["event"][
        "properties"]["actor"]["enum"]
    negatives["assertions"].extend(actor_negatives(
        load(output / "contracts/event_source_contract_v1.json"), actors, profile["duration_sec"]))
    Draft202012Validator(load(output / "schemas/negative_assertions_schema_v3.json")).validate(
        negatives)
    negative_path.write_text(json.dumps(negatives, indent=2) + "\n", encoding="utf-8")
    spec = importlib.util.spec_from_file_location("private_pack_compiler",
                                                output / "tests/build_assertions.py")
    assert spec is not None and spec.loader is not None
    compiler = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(compiler)
    assertions = compiler.build()
    (output / "tests/generated").mkdir()
    (output / "tests/generated/e2e_assertions_v3.json").write_text(
        json.dumps(assertions, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    if any(sha256_file(path) != digest for path, digest in hashes.items()):
        raise ValueError("staging inputs changed")
    if any(sha256_file(root / row["evidence_path"]) != row["sha256"]
           for row in bindings["evidence_bindings"]):
        raise ValueError("source images changed during staging")
    timeline = load(output / "ground_truth/timeline_ground_truth_v3.json")
    manifest = {"version": "3.0", "name": f"valorant_e2e_{timeline['fixture_id']}_v3",
                "source_sha256": profile["sha256"], "qualification_status": "staging_only",
                "formal_pack_completed": False, "reference_frame_count": len(assets),
                "canonical_ground_truth": "ground_truth/timeline_ground_truth_v3.json",
                "generated_assertions": "tests/generated/e2e_assertions_v3.json",
                "files": {p.relative_to(output).as_posix(): sha256_file(p)
                          for p in sorted(output.rglob("*")) if p.is_file()
                          and "__pycache__" not in p.parts}}
    if args.confidence_policy:
        manifest["confidence_policy"] = {
            "version": POLICY_VERSION, "fixture_id": "match_002",
            "base_evaluator_sha256": sha256_file(output / "tests/reference_evaluator_v3_base.py"),
            "native_schema_sha256": sha256_file(output / "schemas/round_package_schema_v2.json"),
            "approval_reference": "call_4761db3ce4aa458a9a7f2fee43c9fda7:0"}
    (output / "MANIFEST.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    # No tests/validate_pack.py: the existing runner cannot register an unfinished
    # fixture merely because it already has a manifest-shaped staging descriptor.
    print(f"Staged {len(timeline['rounds'])} Rounds and {len(assets)} source images; "
          "formal validator/registration still gated")


if __name__ == "__main__":
    main()
