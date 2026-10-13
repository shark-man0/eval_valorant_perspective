"""Seal an independently reviewed private evaluation fixture, not a recognizer.

Existing GT/assertions are copied unchanged. Runtime qualification and actual
positive E2E remain separate gates. No private files are added to Git.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import shutil
from pathlib import Path

from scripts.e2e.assemble_pack_stage import actor_negatives
from scripts.e2e.audit_lifecycle_fixture import audit
from scripts.e2e.compose_boundary_timeline import compose, merge_states
from scripts.e2e.freeze_fixture_provenance import verify_policy_approval
from scripts.e2e.validate_fixture import digest, load, validate, validate_source
from valorant_ai_coach.hud.calibrate_temporal import _check_output_privacy

ENTRYPOINT = '''"""Private match_002 evaluation fixture validator; not runtime qualification."""
import argparse
import sys
from pathlib import Path

parser = argparse.ArgumentParser()
parser.add_argument("--project-root", type=Path, required=True)
parser.add_argument("--source-video", type=Path)
args = parser.parse_args()
repository = args.project_root.resolve()
if repository.name == "src":
    repository = repository.parent
sys.path.insert(0, str(repository))
sys.path.insert(0, str(repository / "src"))
from scripts.e2e.finalize_fixture import validate_complete
validate_complete(Path(__file__).resolve().parents[1], repository, args.source_video)
print("Independent evaluation fixture verified; runtime qualification not asserted")
'''


def archive_inputs(archive: Path) -> tuple[dict, dict]:
    archive = archive.resolve()
    receipt = load(archive / "provenance.json")
    if (receipt.get("production_input") is not False
            or receipt.get("recognizer_qualified") is not False
            or receipt.get("formal_pack_completed") is not False
            or receipt.get("source_verified_before_and_after") is not True):
        raise ValueError("verified independent provenance archive required")
    values, inventory = {}, {"provenance.json", "freezer.py"}
    for role, row in receipt["inputs"].items():
        path = (archive / row["file"]).resolve()
        if (not path.is_relative_to(archive) or path.name in inventory
                or digest(path) != row["sha256"]):
            raise ValueError("archive input changed, duplicated or escaped")
        inventory.add(path.relative_to(archive).as_posix())
        values[role] = load(path)
    if ({p.relative_to(archive).as_posix() for p in archive.rglob("*") if p.is_file()}
            != inventory or digest(archive / "freezer.py") != receipt["freezer_sha256"]):
        raise ValueError("archive inventory or recipe changed")
    return receipt, values


def verify_approved_gt(pack: Path, archive: Path, canonical: Path) -> dict:
    receipt, values = archive_inputs(archive)
    manifest = load(pack / "MANIFEST.json")
    timeline = load(pack / "ground_truth/timeline_ground_truth_v3.json")
    if (receipt["source_sha256"] != manifest["source_sha256"]
            or receipt["fixture_id"] != timeline["fixture_id"]):
        raise ValueError("archive fixture/source mismatch")
    ledger = values["ledger"]
    if (receipt["reviewed_boundaries"] != len(ledger["boundaries"])
            or len(ledger["boundaries"]) != 2 * len(timeline["rounds"])
            or receipt["reviewed_state_cores"] != len(values["state_approval"]["items"])):
        raise ValueError("review coverage mismatch")
    for index, row in enumerate(ledger["inputs"]):
        if receipt["inputs"][f"boundary_approval_{index}"]["sha256"] != row["sha256"]:
            raise ValueError("human approval fingerprint mismatch")
    if manifest.get("confidence_policy"):
        verify_policy_approval(values["confidence_approval"], manifest["confidence_policy"],
                               timeline["fixture_id"])
    rebuilt = compose(values["points"], values["score_approval"], values["score_review"],
                      values["declared_end"], values["continuity"],
                      load(canonical / "schemas/e2e_ground_truth_schema_v3.json"),
                      timeline["observation_policy"])
    rebuilt, negatives = merge_states(
        rebuilt, values["states"], receipt["source_sha256"],
        load(canonical / "schemas/e2e_ground_truth_schema_v3.json"),
        load(canonical / "schemas/negative_assertions_schema_v3.json"))
    native = load(pack / "schemas/round_package_schema_v2.json")
    negatives["assertions"].extend(actor_negatives(
        load(pack / "contracts/event_source_contract_v1.json"),
        native["$defs"]["event"]["properties"]["actor"]["enum"],
        load(pack / "ground_truth/source_video_profile_v3.json")["duration_sec"]))
    if (rebuilt != timeline
            or negatives != load(pack / "ground_truth/negative_assertions_v3.json")):
        raise ValueError("Pack differs from frozen independent GT")
    return receipt


def validate_complete(pack: Path, repository: Path, source_video: Path | None = None) -> None:
    canonical = repository / "ValorantData/valorant_e2e_validation_pack_v3"
    validate(pack, canonical)
    manifest = load(pack / "MANIFEST.json")
    if (manifest.get("formal_pack_completed") is not True
            or manifest.get("qualification_status") != "independent_evaluation_fixture_only"):
        raise ValueError("Pack is not finalized as an evaluation fixture")
    for name, expected in manifest["validation_tools"].items():
        path = (repository / name).resolve()
        if not path.is_relative_to(repository.resolve()) or digest(path) != expected:
            raise ValueError("versioned validation tool changed")
    archive = pack / "review_provenance"
    receipt = verify_approved_gt(pack, archive, canonical)
    old = load(pack / "stage_manifest.json")
    if digest(pack / "stage_manifest.json") != receipt["stage_manifest_sha256"]:
        raise ValueError("frozen stage identity changed")
    if any(digest(pack / name) != expected for name, expected in old["files"].items()):
        raise ValueError("staged fixture changed during finalization")
    spec = importlib.util.spec_from_file_location("final_pack_evaluator",
                                                pack / "tests/reference_evaluator.py")
    assert spec is not None and spec.loader is not None
    evaluator = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(evaluator)
    audit(load(pack / "tests/generated/e2e_assertions_v3.json"), evaluator.evaluate,
          load(pack / "schemas/e2e_output_trace_schema_v1.json"))
    production = repository / "src"
    if not production.is_dir():
        raise ValueError("production source root required for GT leakage check")
    forbidden = ("timeline_ground_truth_v3", "e2e_assertions_v3.json", "frame_pts_sidecar_v3",
                 manifest["source_sha256"])
    if any(any(token in path.read_text(encoding="utf-8") for token in forbidden)
           for path in production.rglob("*.py")):
        raise ValueError("possible private GT leakage into production code")
    if source_video is not None:
        validate_source(pack, source_video)


def finalize(stage: Path, archive: Path, source_video: Path, output: Path,
             repository: Path) -> None:
    _check_output_privacy(output.resolve())
    if output.exists():
        raise FileExistsError("use a new private finalized Pack directory")
    canonical = repository / "ValorantData/valorant_e2e_validation_pack_v3"
    validate(stage, canonical)
    receipt = verify_approved_gt(stage, archive, canonical)
    stage_hash = digest(stage / "MANIFEST.json")
    if stage_hash != receipt["stage_manifest_sha256"]:
        raise ValueError("provenance archive is bound to a different stage")
    validate_source(stage, source_video)
    shutil.copytree(stage, output, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
    shutil.copyfile(stage / "MANIFEST.json", output / "stage_manifest.json")
    shutil.copytree(archive, output / "review_provenance")
    (output / "tests/validate_pack.py").write_text(ENTRYPOINT, encoding="utf-8")
    manifest = load(output / "MANIFEST.json")
    manifest.update(formal_pack_completed=True,
                    qualification_status="independent_evaluation_fixture_only")
    modules = ("finalize_fixture", "validate_fixture", "audit_lifecycle_fixture",
               "compose_boundary_timeline", "assemble_pack_stage", "freeze_fixture_provenance",
               "match002_confidence_evaluator_v1")
    manifest["validation_tools"] = {
        f"scripts/e2e/{name}.py": digest(repository / f"scripts/e2e/{name}.py") for name in modules}
    manifest["files"] = {p.relative_to(output).as_posix(): digest(p)
                         for p in sorted(output.rglob("*")) if p.is_file()
                         and p.name != "MANIFEST.json" and "__pycache__" not in p.parts}
    (output / "MANIFEST.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    validate_complete(output, repository, source_video)
    if digest(stage / "MANIFEST.json") != stage_hash:
        raise ValueError("original stage changed during finalization")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("stage", "archive", "source-video", "output"):
        parser.add_argument(f"--{name}", type=Path, required=True)
    args = parser.parse_args()
    finalize(args.stage, args.archive, args.source_video, args.output,
             Path(__file__).resolve().parents[2])
    print("Independent private evaluation Pack finalized; runtime qualification not asserted")


if __name__ == "__main__":
    main()
