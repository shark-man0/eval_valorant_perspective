"""Run the exact development Map workflow for one original recording."""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import cv2
from acquire_native import acquire
from compose_paths import compose_paths
from prepare_native_timeline import prepare

from valorant_ai_coach.application.timeline_evaluation import run as evaluate
from valorant_ai_coach.temporal.map_display import prepare_map_display
from valorant_ai_coach.temporal.map_recorder_path import measured_native_edges
from valorant_ai_coach.temporal.replay import file_sha, read_json, write_private

_SCRIPT_DIR = Path(__file__).resolve().parent


def _run(script, options, flags=()):
    env = {**os.environ, "OMP_NUM_THREADS": "1", "OPENBLAS_NUM_THREADS": "1",
           "VECLIB_MAXIMUM_THREADS": "1"}
    args = [item for name, value in options.items() for item in (f"--{name}", str(value))]
    # Set backend thread counts before running the reusable CLI's entry point.
    bootstrap = (
        "import cv2,os,runpy,sys; cv2.setNumThreads(1); "
        "sys.path.insert(0, os.path.dirname(sys.argv[1])); "
        "sys.argv=sys.argv[1:]; runpy.run_path(sys.argv[0], run_name='__main__')"
    )
    subprocess.run(
        [sys.executable, "-c", bootstrap, str(_SCRIPT_DIR / script), *args, *flags],
        env=env, check=True,
    )


def _compose(reference, learned, timeline, output, *, companion=False):
    report = compose_paths(
        read_json(reference), read_json(learned), read_json(timeline), file_sha(timeline),
        link_corroborated=True, marker_companion=companion,
    )
    write_private(output, {
        **report, "reference_report_sha256": file_sha(reference),
        "learned_report_sha256": file_sha(learned),
    })


def run(args):
    started = time.monotonic()
    output = args.output.resolve()
    if any((root / ".git").exists() for root in (output, *output.parents)):
        raise ValueError("Private Map outputs must remain outside Git checkouts")
    output.mkdir(parents=True, mode=0o700, exist_ok=False)
    acquisition = args.acquisition
    if acquisition is None:
        cache = args.frame_cache or output / "native_frames"
        acquire(args.policy_path, args.source_sha256, cache, hwaccel=args.hwaccel,
                lossless_webp=args.lossless_webp, png_compression=args.png_compression)
        acquisition = cache / "verified_acquisition_PRIVATE.json"
    receipt = read_json(acquisition)
    if receipt["sha256"] != args.source_sha256:
        raise ValueError("Acquisition is for a different recording")
    timeline_root = output / "timeline"
    cv2.setNumThreads(1)
    prepare(
        policy_path=args.policy_path, acquisition=acquisition, hud_config=args.hud_config,
        spectator_label=args.spectator_label, camera_hint=args.camera_hint, output=timeline_root,
    )
    print(f"Timeline ready: {len(receipt['frames'])} exact native observations", flush=True)
    bundle = timeline_root / "timeline_PRIVATE.json"
    frame_manifest = timeline_root / "map_frames_PRIVATE.json"
    shared = {
        "bundle-path": bundle, "frame-manifest": frame_manifest, "policy-path": args.policy_path,
        "catalog": args.map_catalog, "layout": args.layout,
        "knowledge-asset-cache": args.asset_cache,
        "zones-path": args.zones_path,
        "registration": ("recording-anchors-contrast" if args.contrast_registration
                         else "recording-anchors"),
    }
    cache_options = (
        {} if args.no_shared_alignment_cache else {"exact-alignment-cache": output / "exact_fits"}
    )
    plans = {
        "reference": (
            {"learned-stage": "reference"},
            ("--path-quality", "--training-evidence") if args.training_candidates
            else ("--path-quality",),
        ),
        "adaptive": (
            {"learned-stage": "both", "models-directory": args.models_directory,
             "threshold": args.threshold},
            ("--path-quality", "--refine-center", "--recording-portraits"),
        ),
    }
    if args.portrait_mode == "reference":
        plans["adaptive"] = ({"learned-stage": "marker", "models-directory": args.models_directory,
                              "threshold": args.threshold}, ("--path-quality",))
    if args.companion_models_directory is not None:
        plans["companion"] = (
            {**plans["adaptive"][0], "marker-models-directory": args.companion_models_directory,
             "threshold": args.companion_threshold}, plans["adaptive"][1],
        )
    if args.compare_without_portraits:
        plans["without_portraits"] = (plans["adaptive"][0], ("--path-quality", "--refine-center"))

    reports = {name: output / f"map_{name}_PRIVATE.json" for name in plans}

    def replay(name):
        started = time.monotonic()
        options, flags = plans[name]
        stage_options = {**shared, **cache_options, **options, "output": reports[name]}
        if args.verify_adjacent_learning and options["learned-stage"] == "both":
            flags = (*flags, "--verify-adjacent-learning")
        if args.screen_atlas_void:
            flags = (*flags, "--screen-atlas-void")
        _run("export_paths.py", stage_options, flags)
        elapsed = time.monotonic() - started
        print(f"Map stage {name}: {elapsed:.2f} seconds", flush=True)
        return name, elapsed

    with ThreadPoolExecutor(max_workers=args.jobs) as pool:
        timings = dict(pool.map(replay, plans))
    reference, adaptive = reports["reference"], reports["adaptive"]
    standard = output / "map_standard_PRIVATE.json"
    _compose(reference, adaptive, bundle, standard)
    if "without_portraits" in reports:
        _compose(reference, reports["without_portraits"], bundle,
                 output / "map_standard_without_portraits_PRIVATE.json")
    final = output / "map_recovered_PRIVATE.json"
    recovery_options = {
        "bundle-path": bundle, "frame-manifest": frame_manifest,
        "policy-path": args.policy_path, "map-catalog": args.map_catalog,
        "layout": args.layout, "asset-cache": args.asset_cache, "zones-path": args.zones_path,
        "models-directory": args.models_directory, "threshold": args.threshold,
        "primary-report": standard, "reference-report": reference, "output": final,
        **cache_options,
    }
    if "companion" in reports:
        composed = output / "map_companion_composed_PRIVATE.json"
        _compose(adaptive, reports["companion"], bundle, composed, companion=True)
        recovery_options.update({"companion-report": composed, "companion-baseline": adaptive})
    recovery_started = time.monotonic()
    flags = ("--strict-recovery-tracking",) if args.strict_recovery_tracking else ()
    _run("recover_gaps.py", recovery_options, flags)
    timings["recovery"] = time.monotonic() - recovery_started
    displays = [prepare_map_display(path, args.map_catalog, args.zones_path)
                for path in (standard, final)]
    standard_result, recovered = read_json(standard), read_json(final)
    if not measured_native_edges(standard_result) <= measured_native_edges(recovered):
        raise ValueError("Recovery removed a standard native edge")
    baseline = evaluate(timeline_path=bundle, output=output / "analysis_standard",
                        match_id="map-development", development_map_path=standard, promote=False)
    analysis = evaluate(timeline_path=bundle, output=output / "analysis_recovered",
                        match_id="map-development", development_map_path=final, promote=False)
    if {k: v for k, v in baseline.items() if k != "development_map"} != {
        k: v for k, v in analysis.items() if k != "development_map"
    }:
        raise ValueError("Map output changed the timeline assessment")
    completion = read_json(timeline_root / "completion_PRIVATE.json")
    report = {
        "schema": "development_map_recording_run_v1", "formal_map_outputs": 0,
        "source_sha256": args.source_sha256,
        "native_frames": completion["native_frames"],
        "one_second_rows": completion["one_second_rows"],
        "decode_seconds": receipt["elapsed_decode_seconds"],
        "decode_reused": args.acquisition is not None,
        "map_options": {
            "registration": shared["registration"],
            "verify_adjacent_learning": args.verify_adjacent_learning,
            "strict_recovery_tracking": args.strict_recovery_tracking,
            "zone_catalog_sha256": file_sha(args.zones_path),
        },
        "run_wall_seconds": time.monotonic() - started,
        "timeline_seconds": completion["elapsed_seconds"], "map_pass_seconds": timings,
        "standard": standard_result["operable_coverage"],
        "recovered": recovered["operable_coverage"],
        "output_sha256s": {str(path.relative_to(output)): file_sha(path)
                            for path in (bundle, frame_manifest, standard, final, *displays)},
    }
    write_private(output / "run_PRIVATE.json", report)
    print({k: report[k] for k in ("standard", "recovered")}, flush=True)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("policy-path", "hud-config", "spectator-label", "map-catalog", "layout",
                 "asset-cache", "zones-path", "models-directory", "output"):
        parser.add_argument(f"--{name}", type=Path, required=True)
    parser.add_argument("--source-sha256", required=True)
    parser.add_argument("--camera-hint", type=Path)
    parser.add_argument("--threshold", type=float, required=True)
    parser.add_argument("--acquisition", type=Path)
    parser.add_argument("--frame-cache", type=Path)
    parser.add_argument("--hwaccel")
    parser.add_argument("--lossless-webp", action="store_true")
    parser.add_argument("--png-compression", type=int, default=1)
    parser.add_argument("--companion-models-directory", type=Path)
    parser.add_argument("--companion-threshold", type=float)
    parser.add_argument("--compare-without-portraits", action="store_true")
    parser.add_argument("--no-shared-alignment-cache", action="store_true")
    parser.add_argument("--training-candidates", action="store_true")
    parser.add_argument("--screen-atlas-void", action="store_true")
    parser.add_argument("--verify-adjacent-learning", action="store_true")
    parser.add_argument("--contrast-registration", action="store_true")
    parser.add_argument("--strict-recovery-tracking", action="store_true")
    parser.add_argument("--portrait-mode", choices=("two-head", "reference"), default="two-head")
    parser.add_argument("--jobs", type=int, default=2)
    args = parser.parse_args()
    if (args.companion_models_directory is None) != (args.companion_threshold is None):
        parser.error("Supply a companion checkpoint and its calibrated threshold together")
    if args.portrait_mode == "reference" and (
        args.companion_models_directory is not None or args.compare_without_portraits
        or args.verify_adjacent_learning
    ):
        parser.error("Companion and recording-portrait ablations require the two-head mode")
    if not 1 <= args.jobs <= 4:
        parser.error("--jobs must be between 1 and 4")
    if args.acquisition is not None and (args.frame_cache or args.hwaccel or args.lossless_webp):
        parser.error("--acquisition is already decoded")
    os.umask(0o077)
    run(args)


if __name__ == "__main__":
    main()
