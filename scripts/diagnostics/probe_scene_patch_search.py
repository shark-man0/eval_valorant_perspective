"""Compare crop-local LK against reciprocal non-UI world-patch search.

All inputs are existing native image archives. Previous holdout is development
for this redesign; no qualification, timer/phase reader or event is generated.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import time
from pathlib import Path

import cv2

from scripts.diagnostics.scene_correspondence import _prepare, sha256
from scripts.diagnostics.scene_patch_search import reviewed_patches, search_reviewed_world
from scripts.diagnostics.scene_world_feature_support import common_world_feature_support


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        parser.error("new report path required")
    started = time.perf_counter()
    root = Path("e2e_reports/match_001")
    bindings = {}

    def bind(path):
        digest = sha256(path)
        if str(path) in bindings and bindings[str(path)] != digest:
            raise ValueError("input changed")
        bindings[str(path)] = digest
        return digest

    def read_image(path, row):
        digest = bind(path)
        if "frame_sha256" in row and digest != row["frame_sha256"]:
            raise ValueError("source image hash mismatch")
        image = cv2.imread(str(path))
        if (
            image is None
            or hashlib.sha256(image.tobytes()).hexdigest() != row["source_pixel_sha256"]
        ):
            raise ValueError("source pixel mismatch")
        return _prepare(image)

    dev_path = root / "scene_world_feature_bank_verified_controls.json"
    held_path = root / "scene_world_feature_holdout_diagnostics.json"
    bind(dev_path)
    bind(held_path)
    dev, held = json.loads(dev_path.read_bytes()), json.loads(held_path.read_bytes())
    if dev["source_video_sha256"] != held["source_video_sha256"]:
        raise ValueError("source mismatch")
    video = Path("ValorantData/videos/Valorant_09-25-2026_0-37-29-379.mp4")
    if bind(video) != dev["source_video_sha256"]:
        raise ValueError("video hash mismatch")
    for name in (
        "scene_patch_search.py",
        "scene_world_feature_support.py",
        "scene_correspondence.py",
    ):
        bind(Path(__file__).with_name(name))
    bind(Path(__file__))
    references = {}
    for row in dev["references"]:
        gray = read_image(Path(row["local_path"]), row)
        boxes = row["reviewed_boxes_640x360"]
        references[row["id"]] = (gray, boxes, reviewed_patches(gray, boxes))
    specs = []
    native_root = Path(
        "outputs/recognition-investigation/native-global-preparation-complete-20261008"
    )
    for window in dev["sets"]:
        index = window["window_index"]
        specs.append((f"original-{index}", native_root / f"window-{index:03}", window["rows"]))
    held_root = Path("outputs/recognition-investigation/scene-world-feature-holdout-20261009")
    for index, window in enumerate(held["windows"]):
        specs.append((f"former-holdout-{index}", held_root / f"window-{index:03}", window["rows"]))
    results = []
    for label, directory, source_rows in specs:
        previous_metrics, previous_tracks, previous_pixel, previous_tick = {}, {}, None, None
        rows = []
        for index, row in enumerate(source_rows):
            current = read_image(directory / f"frame_{index + 1:06}.png", row)
            if previous_tick is not None and row["source_pts_ticks"] - previous_tick != 256:
                raise ValueError("native continuity missing")
            metrics, tracks, support = {}, {}, {}
            for key, (reference, boxes, patches) in references.items():
                metrics[key], tracks[key] = search_reviewed_world(
                    reference, current, boxes, patches=patches
                )
                if previous_pixel is not None:
                    match = common_world_feature_support(
                        previous_tracks[key], tracks[key], previous_metrics[key], metrics[key]
                    )
                    if match["distributed_descriptive_support"]:
                        support[key] = match
            duplicate = row["source_pixel_sha256"] == previous_pixel
            rows.append(
                {
                    "pts_sec": row["pts_sec"],
                    "source_pts_ticks": row["source_pts_ticks"],
                    "frame_sha256": bindings[str(directory / f"frame_{index + 1:06}.png")],
                    "source_pixel_sha256": row["source_pixel_sha256"],
                    "previous_supported": row["link_supported_descriptive"],
                    "current_supported": bool(support) and not duplicate,
                    "duplicate_pixel_veto": duplicate,
                    "reference_measurements": metrics,
                    "shared_reference_support": support,
                    "runtime_proof_authorized": False,
                }
            )
            previous_metrics, previous_tracks = metrics, tracks
            previous_pixel, previous_tick = row["source_pixel_sha256"], row["source_pts_ticks"]
        results.append(
            {
                "label": label,
                "frames": len(rows),
                "links": len(rows) - 1,
                "previous_supported": sum(r["previous_supported"] for r in rows),
                "current_supported": sum(r["current_supported"] for r in rows),
                "rows": rows,
            }
        )
    for path, expected in bindings.items():
        if sha256(Path(path)) != expected:
            raise ValueError("terminal binding failed")
    report = {
        "scope": "Development only; previously heldout images now development; no qualification",
        "source_video_sha256": dev["source_video_sha256"],
        "sets": results,
        "file_sha256": bindings,
        "runtime_proof_authorized": False,
        "qualification_created": False,
        "new_runtime_events": 0,
        "canonical_current": None,
        "wall_clock_seconds": time.perf_counter() - started,
    }
    args.output.write_text(json.dumps(report, indent=2) + "\n")
    print(
        json.dumps({r["label"]: [r["previous_supported"], r["current_supported"]] for r in results})
    )


if __name__ == "__main__":
    main()
