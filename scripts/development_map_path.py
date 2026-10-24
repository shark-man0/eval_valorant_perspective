"""Build a PRIVATE offline path viewer from bounded DEVELOPMENT frame observations.

Run from the source checkout with PYTHONPATH=src. See docs/development_map_paths.md.
This tool accepts already acquired frames and explicit per-frame view evidence;
it never scans a video directory, reads other dataset splits or runs full E2E.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import cv2

from valorant_ai_coach.visual.development_map import DevelopmentMapTimeline
from valorant_ai_coach.visual.development_path_viewer import write_candidate_path_html
from valorant_ai_coach.visual.development_trajectory import analyze_candidate_path


def build(manifest_path: Path, output: Path) -> dict[str, Any]:
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if (manifest.get("source_split") != "DEVELOPMENT"
            or manifest.get("qualification") != "development_only"):
        raise ValueError("Only an explicitly declared DEVELOPMENT acquisition is accepted")
    observations = manifest["observations"]
    if not 1 <= len(observations) <= 5000:
        raise ValueError("Bounded acquisition of 1..5000 observations required")
    profile = json.loads(Path(manifest["profile_path"]).read_text(encoding="utf-8"))
    pipeline = DevelopmentMapTimeline(
        profile,
        inspect_reference_appearances=manifest.get("inspect_reference_appearances") is True,
        coordinate_scope=profile.get("development_coordinate_scope", "legacy_self_eligible"),
    )
    records, frames = [], []
    for observation in observations:
        image = cv2.imread(observation["image_path"])
        if image is None:
            raise ValueError("An explicitly listed input image could not be decoded")
        record = pipeline.observe(
            image, observation["time_sec"], observation["frame_index"],
            view=observation["view"], evidence_kind=manifest["view_evidence_kind"],
            source_id=manifest["source_id"], acquisition_id=manifest["acquisition_id"],
            source_sha256=manifest.get("source_sha256"),
        )
        records.append(record)
        height, width = image.shape[:2]
        thumbnail = cv2.resize(image, (min(960, width), round(height*min(1, 960/width))))
        ok, encoded = cv2.imencode(".jpg", thumbnail, [cv2.IMWRITE_JPEG_QUALITY, 78])
        if not ok:
            raise ValueError("Could not encode private source-frame preview")
        frames.append(encoded.tobytes())
    definition = pipeline.timeline.definition
    assert definition is not None
    bbox = definition.data["coordinate_system"]["reference_map_mask_bbox_within_roi_px"]
    report = analyze_candidate_path(records, reference_size_px=(bbox[2]-bbox[0], bbox[3]-bbox[1]))
    output.mkdir(parents=True, exist_ok=True)
    write_candidate_path_html(
        output/"path_PRIVATE.html", report, reference_png=definition.reference_asset.read_bytes(),
        reference_bbox=tuple(bbox), zones=definition.data["zones"], source_frames_jpeg=frames,
    )
    (output/"observations_PRIVATE.json").write_text(
        json.dumps({"records": records, "trajectory": report}, indent=2, allow_nan=False),
        encoding="utf-8",
    )
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True,
                        help="Private local output directory; never publish its contents")
    args = parser.parse_args()
    cv2.setNumThreads(1)
    build(args.manifest, args.output)
    print("Private candidate-path viewer written; UNKNOWN ownership, no Production facts.")


if __name__ == "__main__":
    main()
