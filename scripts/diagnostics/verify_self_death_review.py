"""Verify source-pixel identity of a human review without claiming recognition.

Usage: python scripts/diagnostics/verify_self_death_review.py --video local.mp4
Only the chosen pixels/source hash are verified. Human semantic claims remain
noncanonical review annotations and are never passed to a runtime recognizer.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path

DEFAULT_REPORT = (
    Path(__file__).resolve().parents[2]
    / "e2e_reports/match_001/self_death_visual_role_review_20261016.json"
)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as src:
        for block in iter(lambda: src.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def validate_manifest(report: dict) -> None:
    if (report.get("schema_version") != 1
            or report.get("kind") != "source_bound_human_visual_role_review_not_a_qualification"):
        raise ValueError("unsupported independent visual review format")
    meta = report.get("source")
    rows = report.get("frames")
    if not isinstance(meta, dict) or not isinstance(rows, list) or not rows:
        raise ValueError("source and nonempty frame list required")
    for name in ("sha256",):
        if not isinstance(meta.get(name), str) or not re.fullmatch(
            r"[0-9a-f]{64}", meta[name]
        ):
            raise ValueError("invalid source SHA")
    last = -1
    for row in rows:
        if (not isinstance(row, dict)
                or type(row.get("frame_index")) is not int
                or row["frame_index"] <= last
                or not isinstance(row.get("bgr_pixel_sha256"), str)
                or re.fullmatch(r"[0-9a-f]{64}", row["bgr_pixel_sha256"]) is None):
            raise ValueError("invalid, unsorted or duplicate frame binding")
        last = row["frame_index"]


def check_review(video: Path, report: dict) -> dict[str, object]:
    validate_manifest(report)
    meta = report["source"]
    if video.is_symlink() or not video.is_file():
        raise ValueError("video unavailable or symlink")
    if video.stat().st_size != meta["size_bytes"] or sha256_file(video) != meta["sha256"]:
        raise ValueError("source size or SHA-256 mismatch")
    import cv2

    cap = cv2.VideoCapture(str(video))
    if not cap.isOpened():
        raise ValueError("cannot open original source")
    count = 0
    try:
        for row in report["frames"]:
            cap.set(cv2.CAP_PROP_POS_FRAMES, row["frame_index"])
            ok, image = cap.read()
            if not ok or image is None or image.size == 0:
                raise ValueError(f"frame unavailable at {row['frame_index']}")
            digest = hashlib.sha256(image.tobytes(order="C")).hexdigest()
            if digest != row["bgr_pixel_sha256"]:
                raise ValueError(f"decoded pixel hash mismatch at {row['frame_index']}")
            count += 1
    finally:
        cap.release()
    return {
        "video_sha_verified": True,
        "frames_verified": count,
        "semantic_qualification": False,
        "formal_events_emitted": 0,
        "strict_pass_gain": "unmeasured",
    }


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--video", required=True, type=Path)
    p.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    args = p.parse_args()
    report = json.loads(args.report.read_text(encoding="utf-8"))
    print(json.dumps(check_review(args.video, report), sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
