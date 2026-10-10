"""Audit every reviewed domain against saved camera models, without refitting."""

from __future__ import annotations

import argparse
import hashlib
import json
import time
from pathlib import Path

import cv2

from scripts.diagnostics.scene_correspondence import _prepare
from scripts.diagnostics.scene_domain_ambiguity import domain_displacement_audit
from scripts.diagnostics.scene_joint_domains import joint_domain_audit


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("declaration", "result", "profile", "output"):
        parser.add_argument(f"--{name}", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise ValueError("refuse to overwrite evidence")
    declaration = json.loads(args.declaration.read_text())
    paths = [Path(p) for p in declaration["bindings"]] + [
        args.declaration,
        args.result,
        args.profile,
        Path(__file__),
        Path("scripts/diagnostics/scene_domain_ambiguity.py"),
        Path("scripts/diagnostics/scene_joint_domains.py"),
        Path("src/valorant_ai_coach/hud/scene_domains.py"),
    ]
    bindings = {str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}
    if any(bindings[p] != digest for p, digest in declaration["bindings"].items()):
        raise ValueError("frozen inputs changed")
    profile = json.loads(args.profile.read_text())
    references = {r["id"]: r for r in profile["references"]}
    saved = json.loads(args.result.read_text())
    started = time.perf_counter()
    rows = []
    for row in saved["rows"]:
        original = row["result"]
        audited = {
            "reference_id": row["reference_id"],
            "image": row["image"],
            "original_reason": original["reason"],
            "original_proposal": original["diagnostic_initialization_proposed"],
            "original_model": original["model"],
        }
        if original["model"] is None:
            rows.append({**audited, "domain_audit": None, "joint": None})
            continue
        reference = references[row["reference_id"]]
        source = _prepare(cv2.imread(str(args.profile.parent / reference["asset"])))
        current = _prepare(cv2.imread(row["image"]))
        measurements = []
        boxes = reference["world_boxes_640x360"]
        domains = domain_displacement_audit(
            source,
            current,
            boxes,
            original["model"],
            offset_sink=measurements,
            allowed_current_boxes=declaration["current_search_boxes_640x360"],
        )
        joint = joint_domain_audit(boxes, original["model"], measurements)
        if original["domains"] is not None and (
            original["domains"] != domains or original["joint"] != joint
        ):
            raise ValueError("previously measured domain result changed")
        rows.append(
            {
                **audited,
                "domain_audit": domains,
                "joint": joint,
                "complete_measurement_count": len(measurements),
            }
        )
    if bindings != {str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}:
        raise ValueError("terminal binding mismatch")
    args.output.write_text(
        json.dumps(
            {
                "scope": "passive fixed-camera whole-domain audit; no acceptance override",
                "bindings": bindings,
                "terminal_bindings_match": True,
                "rows": rows,
                "wall_clock_sec": time.perf_counter() - started,
                "qualification_created": False,
                "runtime_proof_authorized": False,
            },
            indent=2,
        )
        + "\n"
    )
    for row in rows:
        print(json.dumps({k: v for k, v in row.items() if k != "domain_audit"}))


if __name__ == "__main__":
    main()
