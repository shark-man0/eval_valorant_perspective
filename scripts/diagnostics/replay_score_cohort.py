"""Replay frozen score observations by source-image hash, without review labels.

This uses nominal layout coordinates, not a fabricated geometry calibration.
It is a reader reproducibility diagnostic, not canonical E2E qualification.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import cv2
import numpy as np

from scripts.diagnostics.score_numeric import load_score_candidate
from valorant_ai_coach.hud.calibrate_temporal import _check_output_privacy
from valorant_ai_coach.hud.layout import HudLayout


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def replay(layout_path: Path, candidate: Path, manifest_path: Path, frames_root: Path):
    layout_hash, manifest_hash = sha256(layout_path), sha256(manifest_path)
    layout = HudLayout.load(layout_path)
    if layout.reference_resolution is None:
        raise ValueError("nominal field replay requires reference resolution")
    readers, fingerprint = load_score_candidate(candidate)
    manifest = json.loads(manifest_path.read_bytes())
    rows = [(index, row) for index, window in enumerate(manifest["windows"])
            if window.get("split") == "holdout" for row in window["rows"]]
    if not rows or len(rows) > 4096:
        raise ValueError("bounded nonempty frozen holdout required")
    targets = {row["frame_sha256"] for _, row in rows}
    assets = {}
    for path in sorted(frames_root.rglob("*")):
        if path.is_file() and path.suffix.lower() in {".jpg", ".png"}:
            digest = sha256(path)
            if digest in targets:
                assets.setdefault(digest, path)
    if targets != set(assets):
        raise ValueError("frozen source image missing or hash changed")
    width, height = layout.reference_resolution
    results = []
    for index, row in rows:
        # The selector's PTS binding is checked, but is never a reader input.
        numerator, denominator = (int(value) for value in row["time_base"].split("/"))
        if numerator <= 0 or denominator <= 0 or (
            type(row["source_pts_ticks"]) is not int
            or not np.isfinite(row["pts_sec"])
            or abs(row["source_pts_ticks"] * numerator / denominator - row["pts_sec"]) > 1e-7
        ):
            raise ValueError("invalid frozen source PTS binding")
        image = cv2.imdecode(np.frombuffer(assets[row["frame_sha256"]].read_bytes(), np.uint8),
                             cv2.IMREAD_COLOR)
        if image is None or image.shape[:2] != (height, width):
            raise ValueError("source frame resolution does not match nominal layout")
        for role, reader in readers.items():
            x1, y1, x2, y2 = layout.normalized_roi(role).pixel_bounds(width, height)
            result = reader.read(image, image[y1:y2, x1:x2])
            results.append({
                "window_index": index, "source_pts_ticks": row["source_pts_ticks"],
                "pts_sec": row["pts_sec"], "frame_sha256": row["frame_sha256"],
                "role": role, "value": result.value, "confidence": result.confidence,
                "sources": list(result.sources),
            })
    if (
        sha256(layout_path) != layout_hash or sha256(manifest_path) != manifest_hash
        or load_score_candidate(candidate)[1] != fingerprint
        or any(sha256(path) != digest for digest, path in assets.items())
    ):
        raise ValueError("frozen replay input changed")
    return {
        "scope": "source field diagnostic; nominal geometry; no labels, events or adoption",
        "source_video_sha256": manifest["source_video_sha256"],
        "manifest_sha256": manifest_hash, "layout_sha256": layout_hash,
        "score_candidate_fingerprint": fingerprint,
        "diagnostic_implementation_sha256": sha256(Path(__file__)),
        "score_implementation_sha256": sha256(Path(__file__).with_name("score_numeric.py")),
        "geometry_calibration_claimed": False, "observations": results,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("video", "layout", "candidate", "manifest", "frames-root", "output"):
        parser.add_argument(f"--{name}", type=Path, required=True)
    args = parser.parse_args()
    _check_output_privacy(args.output.resolve())
    manifest = json.loads(args.manifest.read_bytes())
    if sha256(args.video) != manifest["source_video_sha256"]:
        raise ValueError("source video binding mismatch")
    result = replay(args.layout, args.candidate, args.manifest, args.frames_root)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"readings": len(result["observations"]),
                      "accepted": sum(row["value"] is not None for row in result["observations"]),
                      "geometry_calibration_claimed": False}))


if __name__ == "__main__":
    main()
