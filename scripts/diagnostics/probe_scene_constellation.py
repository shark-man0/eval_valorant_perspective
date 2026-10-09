"""Measure translation constellations on four existing development poses."""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path

import cv2

from scripts.diagnostics.scene_constellation import measure_constellation, patch_peaks
from scripts.diagnostics.scene_correspondence import _prepare, sha256
from scripts.diagnostics.scene_patch_search import reviewed_patches


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--reference-peak-eligibility", action="store_true")
    args = parser.parse_args()
    if args.output.exists():
        parser.error("new output path required")
    root = Path("e2e_reports/match_001")
    development = root / "scene_world_feature_bank_verified_controls.json"
    cohort = root / "scene_world_feature_holdout_diagnostics.json"
    bindings = {
        str(p): sha256(p)
        for p in [
            development,
            cohort,
            Path(__file__),
            Path(__file__).with_name("scene_patch_search.py"),
            Path(__file__).with_name("scene_correspondence.py"),
            Path(__file__).with_name("scene_constellation.py"),
        ]
    }
    dev, held = json.loads(development.read_bytes()), json.loads(cohort.read_bytes())
    video = Path("ValorantData/videos/Valorant_09-25-2026_0-37-29-379.mp4")
    bindings[str(video)] = sha256(video)
    if not (dev["source_video_sha256"] == held["source_video_sha256"] == bindings[str(video)]):
        raise ValueError("source video mismatch")
    reference_row = next(r for r in dev["references"] if r["id"] == "16")

    def read(path, row):
        bindings[str(path)] = sha256(path)
        if row.get("frame_sha256", bindings[str(path)]) != bindings[str(path)]:
            raise ValueError("image bytes mismatch")
        pixels = cv2.imread(str(path))
        if (
            pixels is None
            or hashlib.sha256(pixels.tobytes()).hexdigest() != row["source_pixel_sha256"]
        ):
            raise ValueError("pixel bytes mismatch")
        return _prepare(pixels)

    reference = read(Path(reference_row["local_path"]), reference_row)
    boxes = reference_row["reviewed_boxes_640x360"]
    patches = reviewed_patches(reference, boxes)
    original_patches = len(patches)
    if args.reference_peak_eligibility:
        # Static reference-only eligibility, never current-image discard. A
        # remaining feature exceeding the current budget still vetoes the pose.
        patches = [p for p in patches if patch_peaks(p[2], reference, boxes) is not None]
    native = Path("outputs/recognition-investigation/native-global-preparation-complete-20261008")
    previous = Path("outputs/recognition-investigation/scene-world-feature-holdout-20261009")
    inputs = [
        ("critical-ui", native / "window-000/frame_000014.png", dev["sets"][0]["rows"][13]),
        ("early-pose", previous / "window-000/frame_000001.png", held["windows"][0]["rows"][0]),
        ("returning-pose", previous / "window-000/frame_000006.png", held["windows"][0]["rows"][5]),
        ("later-pose", previous / "window-001/frame_000001.png", held["windows"][1]["rows"][0]),
    ]
    results = []
    for label, path, row in inputs:
        current = read(path, row)
        metrics, tracks = measure_constellation(reference, current, boxes, patches=patches)
        results.append(
            {
                "label": label,
                "pts_sec": row["pts_sec"],
                "reference_id": "16",
                "reference_patches": len(patches),
                "metrics": metrics,
                "tracks_by_region": dict(Counter(t["region"] for t in tracks)),
            }
        )
    for path, digest in bindings.items():
        if sha256(Path(path)) != digest:
            raise ValueError("terminal binding failed")
    report = {
        "scope": "Development constellations only; not holdout or qualification",
        "reference_selection": "Existing frozen image reference16, no timer/phase input",
        "reference_peak_eligibility": args.reference_peak_eligibility,
        "original_reference_features": original_patches,
        "eligible_reference_features": len(patches),
        "source_video_sha256": dev["source_video_sha256"],
        "rows": results,
        "file_sha256": bindings,
        "runtime_proof_authorized": False,
        "new_runtime_events": 0,
    }
    args.output.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(results))


if __name__ == "__main__":
    main()
