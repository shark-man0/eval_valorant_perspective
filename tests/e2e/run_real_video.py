"""Run the native real HUD/visual pipeline and export evaluator inputs.

Example:
  python tests/e2e/run_real_video.py --source-video /path/clip.mp4 --output /tmp/valorant-e2e

This runner never loads the validation pack's ground_truth, assets, assertions,
or fixtures. It uses the bundled production HUD layout unless one is supplied.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from dataclasses import asdict
from importlib import import_module
from pathlib import Path
from types import SimpleNamespace
from typing import Any

# Make the checked-out application importable without requiring an editable
# install; this also makes the command independent of the caller's cwd.
APP_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(APP_ROOT / "src"))
sys.path.insert(0, str(APP_ROOT / "tests" / "e2e"))

build_services = import_module("valorant_ai_coach.bootstrap").build_services
resource_path = import_module("valorant_ai_coach.resources").resource_path
settings_module = import_module("valorant_ai_coach.settings")
AppSettings, SettingsStore = settings_module.AppSettings, settings_module.SettingsStore
to_e2e_trace = import_module("trace_adapter").to_e2e_trace


def _write_json(path: Path, value: Any) -> None:
    serialized = json.dumps(
        value,
        ensure_ascii=False,
        indent=2,
        allow_nan=False,
        default=lambda item: str(item) if isinstance(item, Path) else item,
    )
    path.write_text(serialized + "\n", encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    source_group = parser.add_mutually_exclusive_group(required=True)
    source_group.add_argument("--source-video", type=Path)
    source_group.add_argument("--from-raw", type=Path,
                              help="Adapt a prior raw_processing.json without rerunning video CV")
    parser.add_argument("--output", required=True, type=Path,
                        help="Directory for raw_processing.json and e2e_trace.json")
    parser.add_argument("--hud-layout", "--layout", dest="hud_layout", type=Path,
                        help="Optional calibrated HUD layout JSON")
    parser.add_argument("--visual-profile", type=Path,
                        help="Optional visual runtime profile JSON")
    parser.add_argument("--manual-map-id", default="")
    parser.add_argument("--map-client-build", default="")
    parser.add_argument("--ffmpeg-bin")
    parser.add_argument("--ffprobe-bin")
    args = parser.parse_args(argv)

    output = args.output.expanduser().resolve()
    output.mkdir(parents=True, exist_ok=True)
    if args.from_raw:
        raw_path = args.from_raw.expanduser().resolve()
        raw = json.loads(raw_path.read_text(encoding="utf-8"))
        if raw.get("status") != "complete":
            raise ValueError(f"Raw processing result is not complete: {raw_path}")
        trace = to_e2e_trace(SimpleNamespace(**raw))
        _write_json(output / "e2e_trace.json", trace)
        print(f"Adapted native raw processing into {output / 'e2e_trace.json'}")
        return 0

    source = args.source_video.expanduser().resolve()
    data_dir = output / "runtime_data"
    settings = AppSettings(
        data_dir=data_dir,
        ffmpeg_path=args.ffmpeg_bin or os.environ.get("FFMPEG_BIN", "ffmpeg"),
        ffprobe_path=args.ffprobe_bin or os.environ.get("FFPROBE_BIN", "ffprobe"),
        hud_mode="real",
        mock_ai=True,
        hud_layout_path=(
            str(args.hud_layout.expanduser().resolve())
            if args.hud_layout
            else str(resource_path("config/hud_layout_1080p_v3.json"))
        ),
        visual_profile_path=(
            str(args.visual_profile.expanduser().resolve()) if args.visual_profile else ""
        ),
        manual_map_id=args.manual_map_id,
        map_client_build=args.map_client_build,
        visual_semantic_enabled=False,
    )
    store = SettingsStore(output / "runner-settings.json")
    raw: dict[str, Any] = {
        "status": "starting",
        "source_video": str(source),
        "runtime_mode": {"hud_mode": "real", "visual_semantic_enabled": False,
                         "coach_mode": "mock", "ground_truth_loaded": False},
        "round_id_mapping": (
            "Native RoundPackage order N is named sample_round_N for the evaluator. "
            "No ground-truth boundary or timestamp is consulted."
        ),
    }
    try:
        services = build_services(store, settings=settings)
        metadata = services.video.probe(source)
        processor = services.pipeline.hud_video_processor
        if processor is None:
            raise RuntimeError("Real HudVideoProcessor was not configured")
        result = processor.process(metadata=metadata, match_id="e2e-runtime",
                                   output_dir=output / "processing_frames",
                                   progress_cb=lambda fraction, message: print(
                                       f"[{fraction:5.1%}] {message}", flush=True))
        # Raw export is the processor's own objects, before trace adaptation.
        raw.update({
            "status": "complete",
            "video_metadata": asdict(metadata),
            "sampled_frame_count": result.sampled_frame_count,
            "round_packages": list(result.round_packages),
            "observations": list(result.observations),
            "hud_events": list(result.hud_events),
            "visual_events": list(result.visual_events),
            "visual_observations": list(result.visual_observations),
            "visual_candidates": list(result.visual_candidates),
            "zone_resolutions": list(result.zone_resolutions),
            "diagnostics": list(result.diagnostics),
            "hud_calibration_diagnostics": result.calibration_diagnostics,
            "evidence_frames": [asdict(frame) for frame in result.evidence_frames],
        })
        _write_json(output / "raw_processing.json", raw)
        _write_json(output / "e2e_trace.json", to_e2e_trace(result))
        print(f"Wrote native processing and E2E trace under {output}")
        return 0
    except Exception as exc:
        # Keep calibration/runtime failures inspectable without substituting fake
        # detections. The empty trace is schema-shaped but evaluator scores will fail.
        raw.update({"status": "error", "error_type": type(exc).__name__, "error": str(exc)})
        if "processor" in locals() and processor is not None:
            raw["hud_calibration_diagnostics"] = getattr(
                processor.analyzer, "last_calibration_diagnostics", {})
        _write_json(output / "raw_processing.json", raw)
        _write_json(output / "e2e_trace.json", {
            "events": [], "state_intervals": [], "ownership_intervals": [],
            "snapshots": [], "visual_observations": [], "temporal_features": [],
        })
        print(f"Real processing failed: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
