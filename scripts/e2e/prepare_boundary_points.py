"""Prepare schema-valid private v3 point fragments from explicit reviewed witnesses.

This transfers witness annotations, not infers absence from frame proximity.
Unknown brackets are rejected; no production analysis or formal registration.
"""
from __future__ import annotations

import argparse
import json
import math
import shutil
from pathlib import Path

from jsonschema import Draft202012Validator

from scripts.e2e.run_dataset_case import sha256_file
from valorant_ai_coach.hud.calibrate_temporal import _check_output_privacy


def catalog(review_root: Path, identity: tuple) -> dict:
    result = {}
    for manifest in sorted(review_root.glob("*/review_evidence.json")):
        digest = sha256_file(manifest)
        record = json.loads(manifest.read_text(encoding="utf-8"))
        if sha256_file(manifest) != digest:
            raise ValueError("source manifest changed during cataloging")
        if ((record.get("video_id"), record.get("source_video_sha256")) != identity
                or record.get("kind") != "source_overview_not_gt"
                or record.get("source_hash_verified_after_extraction") is not True
                or record.get("recognizer_outputs_consulted") is not False):
            continue
        for frame in record["frames"]:
            result.setdefault(frame["source_frame_pts"], []).append(
                (manifest, {**frame, "_catalog_manifest_sha256": digest}))
    return result


def prepare(ledger: dict, witnesses: dict, frames: dict, policy: dict) -> tuple[list, list]:
    if (ledger.get("production_input") is not False
            or ledger.get("kind") != "private_approved_boundary_ledger_not_validation_pack"
            or witnesses.get("production_input") is not False
            or (ledger["video_id"], ledger["source_video_sha256"]) != (
                witnesses["video_id"], witnesses["source_video_sha256"])):
        raise ValueError("private approved source identity required")
    markers = {(r["round_id"], r["boundary_kind"]): r for r in ledger["boundaries"]}
    points, bindings, seen = [], [], set()
    for number, kind, absent, present in witnesses["pairs"]:
        if (type(number) is not int or number < 1 or kind not in {"round_start", "round_end"}
                or any(type(x) not in (int, float) or not math.isfinite(x)
                       for x in (absent, present)) or not 0 <= absent < present):
            raise ValueError("explicit finite ordered witnesses required")
        rid = f"sample_round_{number}"
        key = (rid, kind)
        if key in seen or key not in markers or markers[key]["approved_time_sec"] != present:
            raise ValueError("witness pair duplicates or changes an approved marker")
        seen.add(key)
        marker = markers[key]
        if marker["approved_record"].get("first_native_onset_verified") is False:
            raise ValueError("unobservable onset cannot be converted to a point bracket")
        paths = []
        for timestamp in (absent, present):
            candidates = frames.get(timestamp, [])
            if not candidates or len({f["evidence_frame_sha256"] for _, f in candidates}) != 1:
                raise ValueError(f"missing or ambiguous source witness at {timestamp}")
            manifest, frame = candidates[0]
            manifest_hash = sha256_file(manifest)
            if manifest_hash != frame.get("_catalog_manifest_sha256", manifest_hash):
                raise ValueError("source manifest changed after cataloging")
            image = (manifest.parent / frame["image"]).resolve()
            if (not image.is_relative_to(manifest.parent.resolve())
                    or sha256_file(image) != frame["evidence_frame_sha256"]):
                raise ValueError("source witness image integrity failed")
            name = f"assets/reference_frames/{rid}_{kind}_{timestamp:.6f}s.jpg"
            paths.append(name)
            bindings.append({"evidence_path": name, "source_path": str(image),
                             "source_frame_pts": timestamp,
                             "requested_sec": frame["requested_sec"],
                             "sha256": frame["evidence_frame_sha256"],
                             "source_manifest_path": str(manifest.resolve()),
                             "source_manifest_sha256": manifest_hash})
        points.append({"round_id": rid, "point": {
            "id": f"{rid}_{kind}", "kind": "point_event", "type": kind, "actor": "system",
            "evidence_bracket": {"last_absent_sec": absent, "first_present_sec": present},
            "tolerance_before_sec": policy["defaults"]["point_event_before_sec"],
            "tolerance_after_sec": policy["defaults"]["point_event_after_sec"],
            "facts": {}, "evidence": paths, "required_event_attributes": {},
        }})
    return points, bindings


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("ledger", "witnesses", "review-root", "canonical-pack", "output"):
        parser.add_argument(f"--{name}", type=Path, required=True)
    args = parser.parse_args()
    _check_output_privacy(args.output.resolve())
    if args.output.exists():
        raise FileExistsError("use a new private staging directory")
    policy_path = args.canonical_pack / "ground_truth/evaluation_policy_v3.json"
    schema_path = args.canonical_pack / "schemas/e2e_ground_truth_schema_v3.json"
    inputs = {p: sha256_file(p) for p in (args.ledger, args.witnesses, policy_path, schema_path)}
    ledger = json.loads(args.ledger.read_text(encoding="utf-8"))
    witnesses = json.loads(args.witnesses.read_text(encoding="utf-8"))
    if witnesses["ledger_sha256"] != inputs[args.ledger]:
        raise ValueError("witnesses are not bound to this approved ledger")
    points, bindings = prepare(
        ledger, witnesses, catalog(args.review_root, (ledger["video_id"],
                                                     ledger["source_video_sha256"])),
        json.loads(policy_path.read_text(encoding="utf-8")))
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    validator = Draft202012Validator({"$ref": "#/$defs/point_event", "$defs": schema["$defs"]})
    for row in points:
        validator.validate(row["point"])
    if any(sha256_file(p) != digest for p, digest in inputs.items()):
        raise ValueError("preparation inputs changed")
    args.output.mkdir(parents=True)
    for binding in bindings:
        destination = args.output / binding["evidence_path"]
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(binding["source_path"], destination)
        if sha256_file(destination) != binding["sha256"]:
            raise ValueError("copied evidence hash mismatch")
    if any(sha256_file(Path(b["source_manifest_path"])) != b["source_manifest_sha256"]
           or sha256_file(Path(b["source_path"])) != b["sha256"] for b in bindings):
        raise ValueError("source evidence changed during copying")
    report = {"kind": "private_v3_boundary_point_fragments_not_complete_pack",
              "source_video_sha256": ledger["source_video_sha256"],
              "ledger_sha256": inputs[args.ledger], "witnesses_sha256": inputs[args.witnesses],
              "schema_sha256": inputs[schema_path], "policy_sha256": inputs[policy_path],
              "points": points, "evidence_bindings": bindings,
              "production_input": False, "formal_pack_completed": False}
    (args.output / "point_fragments.json").write_text(
        json.dumps(report, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    print(f"Prepared {len(points)} v3 point fragments and {len(bindings)} unchanged source assets")


if __name__ == "__main__":
    main()
