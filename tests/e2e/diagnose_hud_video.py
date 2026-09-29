"""Uniform source-video HUD probes, not an accuracy or temporal-event test.

No labelled assets or validation-pack inputs are read. Every frame is analysed
independently: widely spaced samples must not imply continuous player actions.
"""
from __future__ import annotations

import argparse
import json
import math
import sys
from importlib import import_module
from pathlib import Path

APP_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(APP_ROOT / "src"))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-video", required=True, type=Path)
    parser.add_argument("--layout", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--step-sec", type=float, default=30.0)
    args = parser.parse_args()
    if not math.isfinite(args.step_sec) or args.step_sec <= 0:
        parser.error("--step-sec must be positive and finite")
    args.output.mkdir(parents=True, exist_ok=True)
    analyzer = import_module("valorant_ai_coach.hud").RealHudAnalyzer(args.layout)
    video = import_module("valorant_ai_coach.video").VideoService()
    load_frame = import_module("valorant_ai_coach.hud.readers").load_frame
    metadata = video.probe(args.source_video)
    count = math.ceil(metadata.duration_sec / args.step_sec)
    if count > 100:
        parser.error("Diagnostic sampling is limited to 100 frames; increase --step-sec")
    frames = video.extract_frames(
        args.source_video, [i * args.step_sec for i in range(count)],
        args.output / "frames", max_dimension=None, metadata=metadata,
    )
    records = []
    for frame in frames:
        result = analyzer.observe_frames([frame], video_metadata=metadata)
        image = load_frame(frame)
        height, width = image.shape[:2]
        readers = {}
        for name, reader in analyzer.readers.items():
            if name not in analyzer.layout.regions:
                continue
            x1, y1, x2, y2 = analyzer.layout.normalized_roi(name).pixel_bounds(width, height)
            raw = reader.read(image, image[y1:y2, x1:x2])
            readers[name] = {
                "value": raw.value, "confidence": raw.confidence, "sources": raw.sources,
            }
        records.append({
            "pts_sec": frame.time_sec, "frame": str(frame.path.resolve()),
            "observation": result.observations[0],
            "calibration_reasons": result.calibration.reasons,
            "unaccepted_reader_probes": readers,
            "diagnostics": result.diagnostics,
        })
        print(f"{frame.time_sec:.6f}: {result.observations[0]['primary_state']}", flush=True)
    report = {
        "scope": "Independent uniform HUD probes; not E2E acceptance or temporal evidence",
        "source_video": str(args.source_video.resolve()),
        "profile_fingerprint": analyzer.template_profile.fingerprint(args.layout)
        if analyzer.template_profile else None,
        "records": records,
    }
    (args.output / "hud_diagnostics.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
