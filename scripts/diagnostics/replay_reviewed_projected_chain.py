"""Replay declared native images and offline world reviews with frozen code.

This runner emits development diagnostics, never qualification, lifecycle
boundaries or trusted runtime scene evidence. It consumes no Validation Pack.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import time
from pathlib import Path

import cv2

from scripts.diagnostics.scene_correspondence import _prepare, sha256
from scripts.diagnostics.scene_world_review_gate import FrameWorldReview, ReviewedSceneDiagnostic
from scripts.diagnostics.validate_scene_chain_cohort import (
    verify_bindings,
    verify_shared_tracking_code,
    verify_ticks,
)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--declaration", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        parser.error("new output required; never overwrite a terminal replay")
    started = time.perf_counter()
    freeze = json.loads(args.declaration.read_bytes())
    bindings = dict(freeze["file_sha256"])
    bindings[str(args.declaration)] = sha256(args.declaration)
    runner = str(Path(__file__).relative_to(Path.cwd()))
    if bindings.get(runner) != sha256(Path(__file__)):
        raise ValueError("runner must be frozen before replay")
    if bindings.get(freeze["source_video"]) != freeze["source_video_sha256"]:
        raise ValueError("source video needs explicit frozen binding")
    verify_bindings(bindings)
    verify_shared_tracking_code(bindings)
    annotations = freeze["reviews"]
    verify_ticks([r["source_pts_ticks"] for r in annotations])
    rows, tracker = [], None
    for annotation in annotations:
        path = Path(annotation["local_path"])
        if bindings.get(str(path)) != annotation["frame_sha256"]:
            raise ValueError("all native PNGs need explicit frozen binding")
        native = cv2.imread(str(path))
        if (
            native is None
            or hashlib.sha256(native.tobytes()).hexdigest() != annotation["source_pixel_sha256"]
        ):
            raise ValueError("native source pixel binding differs")
        image = _prepare(native)
        review = FrameWorldReview(
            freeze["source_video_sha256"],
            hashlib.sha256(image.tobytes()).hexdigest(),
            annotation["source_pts_ticks"],
            freeze["source_epoch"],
            tuple((tuple(box), status) for box, status in annotation["regions"]),
            annotation["provenance"],
        )
        if tracker is None:
            tracker = ReviewedSceneDiagnostic(
                image,
                review,
                source_video_sha256=freeze["source_video_sha256"],
                source_epoch=freeze["source_epoch"],
                projected=True,
            )
            result = {
                "reason": "reviewed_seed_only",
                "descriptive_supported": False,
                "runtime_proof_authorized": False,
            }
        else:
            result = tracker.advance(image, review)
        rows.append(
            {
                "pts_sec": annotation["source_pts_ticks"] / 15360,
                "source_pts_ticks": annotation["source_pts_ticks"],
                "frame_sha256": annotation["frame_sha256"],
                "image_result": result,
            }
        )
    verify_bindings(bindings)
    report = {
        "scope": "Frozen projected-world development replay; no qualification or runtime evidence",
        "source_video_sha256": freeze["source_video_sha256"],
        "native_frames": len(rows),
        "adjacent_links": len(rows) - 1,
        "supported_links": sum(r["image_result"]["descriptive_supported"] for r in rows),
        "rows": rows,
        "file_sha256": bindings,
        "qualification_created": False,
        "new_runtime_events": 0,
        "canonical_current": None,
        "wall_clock_seconds": time.perf_counter() - started,
    }
    with args.output.open("x", encoding="utf-8") as stream:
        stream.write(json.dumps(report, indent=2) + "\n")
    print(
        json.dumps(
            {
                k: report[k]
                for k in (
                    "native_frames",
                    "adjacent_links",
                    "supported_links",
                    "wall_clock_seconds",
                )
            }
        )
    )


if __name__ == "__main__":
    main()
