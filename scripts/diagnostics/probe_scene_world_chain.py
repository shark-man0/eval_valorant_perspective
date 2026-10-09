"""Follow a reviewed background seed through a complete 36-native-frame prefix.

All inputs are development. Never reseed a terminated chain or generate a
qualification/event; timestamps only verify native source coverage.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import time
from pathlib import Path

import cv2

from scripts.diagnostics.scene_correspondence import SCALED_BACKGROUND_BOXES, _prepare, sha256
from scripts.diagnostics.scene_world_chain import ReviewedWorldChain


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--archive", choices=("prefix", "stable"), default="prefix")
    parser.add_argument(
        "--support-mode", choices=("world_features", "dense_world"), default="world_features"
    )
    parser.add_argument("--extra-row2", action="store_true")
    args = parser.parse_args()
    if args.extra_row2 and args.archive != "stable":
        parser.error("extra row2 has only been reviewed on the stable archive")
    if args.output.exists():
        parser.error("new output path required")
    started = time.perf_counter()
    root = Path("e2e_reports/match_001")
    paths = [
        root / "scene_world_feature_holdout_diagnostics.json",
        root / "scene_world_feature_bank_verified_controls.json",
    ]
    bindings = {str(p): sha256(p) for p in paths}
    held, dev = [json.loads(p.read_bytes()) for p in paths]
    video = Path("ValorantData/videos/Valorant_09-25-2026_0-37-29-379.mp4")
    bindings[str(video)] = sha256(video)
    if not (held["source_video_sha256"] == dev["source_video_sha256"] == bindings[str(video)]):
        raise ValueError("source video mismatch")
    for name in (
        "probe_scene_world_chain.py",
        "scene_world_chain.py",
        "scene_correspondence.py",
        "scene_patch_search.py",
    ):
        p = Path(__file__).with_name(name)
        bindings[str(p)] = sha256(p)
    folders = [
        Path("outputs/recognition-investigation/scene-world-feature-holdout-20261009/window-000"),
        Path(
            "outputs/recognition-investigation/native-global-preparation-complete-20261008/window-000"
        ),
    ]
    source_rows = [held["windows"][0]["rows"], dev["sets"][0]["rows"]]
    if args.archive == "stable":
        # Separate explicit diagnostic input, never reacquisition in the failed prefix.
        folders, source_rows = folders[1:], source_rows[1:]
    boxes = list(SCALED_BACKGROUND_BOXES)
    if args.extra_row2:
        boxes.append((10, 250, 83, 290))
        review = Path(
            "outputs/recognition-investigation/scene-world-chain-20261009/row2-candidate-review.png"
        )
        bindings[str(review)] = sha256(review)
    chain = None
    rows = []
    previous_tick = None
    for folder, input_rows in zip(folders, source_rows, strict=True):
        for index, row in enumerate(input_rows):
            p = folder / f"frame_{index + 1:06}.png"
            digest = sha256(p)
            bindings[str(p)] = digest
            if row.get("frame_sha256", digest) != digest:
                raise ValueError("PNG binding changed")
            image = cv2.imread(str(p))
            if (
                image is None
                or hashlib.sha256(image.tobytes()).hexdigest() != row["source_pixel_sha256"]
            ):
                raise ValueError("pixel binding changed")
            if row["time_base"] != "1/15360" or (
                previous_tick is not None and row["source_pts_ticks"] - previous_tick != 256
            ):
                raise ValueError("native prefix gap; do not bridge or restart")
            gray = _prepare(image)
            if chain is None:
                chain = ReviewedWorldChain(gray, boxes, support_mode=args.support_mode)
                result = {
                    "reason": "reviewed_seed_only",
                    "seed_features": chain.seed_features,
                    "descriptive_supported": False,
                    "runtime_proof_authorized": False,
                }
            else:
                result = chain.advance(gray)
            rows.append(
                {
                    "pts_sec": row["pts_sec"],
                    "source_pts_ticks": row["source_pts_ticks"],
                    "frame_sha256": digest,
                    "source_pixel_sha256": row["source_pixel_sha256"],
                    "image_result": result,
                }
            )
            previous_tick = row["source_pts_ticks"]
    for p, digest in bindings.items():
        if sha256(Path(p)) != digest:
            raise ValueError("terminal binding changed")
    report = {
        "scope": "Reviewed world identity chain; all development, not qualification",
        "source_video_sha256": dev["source_video_sha256"],
        "input_archive": args.archive,
        "support_mode": args.support_mode,
        "extra_row2": args.extra_row2,
        "seed_review_provenance": (
            "First PNG reviewed in full context: six crops show wall/crack, "
            "outside timer/phase and arms/knife. Only source patch identities are world-tagged."
        ),
        "reviewed_seed_boxes_640x360": [list(b) for b in boxes],
        "native_frames": len(rows),
        "adjacent_links": len(rows) - 1,
        "supported_links": sum(r["image_result"]["descriptive_supported"] for r in rows),
        "rows": rows,
        "file_sha256": bindings,
        "runtime_proof_authorized": False,
        "qualification_created": False,
        "new_runtime_events": 0,
        "canonical_current": None,
        "wall_clock_seconds": time.perf_counter() - started,
    }
    args.output.write_text(json.dumps(report, indent=2) + "\n")
    print(
        json.dumps(
            {
                "frames": len(rows),
                "links": len(rows) - 1,
                "support": report["supported_links"],
                "seconds": report["wall_clock_seconds"],
            }
        )
    )


if __name__ == "__main__":
    main()
