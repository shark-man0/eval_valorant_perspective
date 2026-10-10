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
        "--support-mode",
        choices=("world_features", "dense_world", "adjacent_dense_world"),
        default="world_features",
    )
    parser.add_argument("--extra-row2", action="store_true")
    parser.add_argument("--resolution", choices=("canonical", "native"), default="canonical")
    parser.add_argument("--stage-diagnostics", action="store_true")
    parser.add_argument("--dense-footprint", choices=("interior", "full_valid"), default="interior")
    parser.add_argument("--model-audit", action="store_true")
    parser.add_argument(
        "--seed-membership", choices=("ransac_mask", "symmetric_final"), default="ransac_mask"
    )
    args = parser.parse_args()
    if args.extra_row2 and args.archive != "stable":
        parser.error("extra row2 has only been reviewed on the stable archive")
    if args.dense_footprint == "full_valid" and args.support_mode != "adjacent_dense_world":
        parser.error("full-valid footprint requires explicit adjacent dense mode")
    if args.seed_membership != "ransac_mask" and args.support_mode != "adjacent_dense_world":
        parser.error("final membership requires explicit adjacent dense mode")
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
    if args.model_audit:
        p = Path(__file__).with_name("scene_camera_model_audit.py")
        bindings[str(p)] = sha256(p)
    for name in (
        "scene_domains.py", "scene_tracking.py", "scene_episode.py",
        "scene_references.py", "scene_reference_matching.py",
    ):
        p = Path("src/valorant_ai_coach/hud") / name
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
    scale = 3 if args.resolution == "native" else 1
    input_boxes = [tuple(v * scale for v in box) for box in boxes]
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
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY) if scale == 3 else _prepare(image)
            stage_rows = [] if args.stage_diagnostics else None
            model_rows = [] if args.model_audit else None
            if chain is None:
                chain = ReviewedWorldChain(
                    gray,
                    input_boxes,
                    support_mode=args.support_mode,
                    scale=scale,
                    dense_footprint=args.dense_footprint,
                    seed_membership=args.seed_membership,
                )
                result = {
                    "reason": "reviewed_seed_only",
                    "seed_features": chain.seed_features,
                    "descriptive_supported": False,
                    "runtime_proof_authorized": False,
                }
            else:
                result = chain.advance(gray, region_sink=stage_rows, model_sink=model_rows)
            rows.append(
                {
                    "pts_sec": row["pts_sec"],
                    "source_pts_ticks": row["source_pts_ticks"],
                    "frame_sha256": digest,
                    "source_pixel_sha256": row["source_pixel_sha256"],
                    "image_result": result,
                }
            )
            if args.stage_diagnostics:
                rows[-1]["region_stage_diagnostics"] = stage_rows
            if model_rows:
                rows[-1]["camera_model_input"] = model_rows[0]
            previous_tick = row["source_pts_ticks"]
    if args.model_audit:
        from scripts.diagnostics.scene_camera_model_audit import audit_world_models

        # Shadow RNG/fitting runs only after the complete original chain is done.
        for row in rows:
            if row.get("camera_model_input") is not None:
                row["camera_model_audit"] = audit_world_models(
                    row["camera_model_input"], scale=scale
                )
    for p, digest in bindings.items():
        if sha256(Path(p)) != digest:
            raise ValueError("terminal binding changed")
    report = {
        "scope": "Reviewed world identity chain; all development, not qualification",
        "source_video_sha256": dev["source_video_sha256"],
        "input_archive": args.archive,
        "support_mode": args.support_mode,
        "dense_footprint": args.dense_footprint,
        "seed_membership": args.seed_membership,
        "extra_row2": args.extra_row2,
        "resolution": args.resolution,
        "image_size": [640 * scale, 360 * scale],
        "spatial_parameter_scale": scale,
        "ncc_floor": 0.90,
        "stage_diagnostics": args.stage_diagnostics,
        "model_audit": args.model_audit,
        "seed_region_diagnostics": chain.seed_region_diagnostics
        if args.stage_diagnostics
        else None,
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
