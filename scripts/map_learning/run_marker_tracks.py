"""Prepare exact episode pixels and run a separately supplied Map tracker."""

from __future__ import annotations

import argparse
import os
import shutil
import sys
from fractions import Fraction
from pathlib import Path
from tempfile import TemporaryDirectory

import cv2
import numpy as np
from checkpoints import pin
from workflow import _source_lock

from valorant_ai_coach.application.map_job_control import phase, run_interruptible
from valorant_ai_coach.application.map_library import attach_map_tracker, verified_map_package
from valorant_ai_coach.recordings.catalog import RecordingCatalog
from valorant_ai_coach.temporal.camera_panel import NATIVE_TIME_BASE, decode_samples
from valorant_ai_coach.temporal.evidence import digest, freeze_native_sample
from valorant_ai_coach.temporal.map_recorder_export import _pixels_match
from valorant_ai_coach.temporal.map_timeline_report import load_map_timeline
from valorant_ai_coach.temporal.map_view_episodes import map_view_episodes
from valorant_ai_coach.temporal.replay import SourcePolicy, file_sha, read_json


def _private(path: Path) -> Path:
    root = path.resolve()
    if any((p / ".git").exists() for p in (root, *root.parents)):
        raise ValueError("Tracking work and pixel caches must stay outside Git")
    return root


def episode_inputs(timeline, reference, adaptive, baseline, paths, *, whole_episode,
                   previous=None):
    operable = set(reference["comparison_evidence"]["operable_sample_refs"])
    unresolved = set(reference["comparison_evidence"]["unresolved_portrait_sample_refs"])
    unresolved.intersection_update(adaptive["comparison_evidence"]["unresolved_portrait_sample_refs"])
    eligible = operable & unresolved
    already_observed = {
        row["timestamp"] for row in previous["second_rows"] if row["recorder_map_observations"]
    } if previous is not None else set()
    targets = {
        key for row, current in zip(timeline["seconds"], baseline["second_rows"], strict=True)
        if row["sample_refs"] and set(row["sample_refs"]) <= eligible
        and not current["recorder_map_observations"] and row["timestamp"] not in already_observed
        for key in row["sample_refs"]
    }
    selected = set()
    for episode in map_view_episodes(timeline):
        samples = episode.current_samples
        matches = [i for i, key in enumerate(samples) if key in targets]
        if not matches:
            continue
        if whole_episode:
            selected.update(samples)
        else:
            for index in matches:
                selected.update(samples[max(0, index - 2):index + 3])
    if not selected <= paths.keys():
        raise ValueError("The frozen native manifest is missing part of a tracking episode")
    return targets, selected


def _verified_override(path, sample):
    if not path.is_file():
        return False
    if path.is_symlink():
        raise ValueError("Pixel cache contains a redirected file")
    image = cv2.imdecode(np.frombuffer(path.read_bytes(), np.uint8), cv2.IMREAD_COLOR)
    if image is None or not _pixels_match(image, sample):
        raise ValueError("Cached frame pixels differ from the frozen observation")
    return True


def _cache_pixels(root, samples, video, record, catalog, *, reserve):
    if {Fraction(s["native_time_base"]) for s in samples} != {NATIVE_TIME_BASE}:
        raise ValueError("Selective restoration requires the native decoder's 1/15360 clock")
    if shutil.disk_usage(root).free <= reserve:
        raise ValueError("Tracking pixel cache would exceed the storage reserve")
    catalog.record_exposure(record, "development_use", "Map tracking pixel restoration")
    if file_sha(video) != samples[0]["source_sha256"]:
        raise ValueError("Original recording differs from the tracking source")
    missing = []
    for sample, image in decode_samples(video, samples, missing):
        if shutil.disk_usage(root).free <= reserve:
            raise ValueError("Tracking pixel cache reached the storage reserve")
        with TemporaryDirectory(dir=root) as temporary:
            frame = Path(temporary) / "frame.png"
            encoded, content = cv2.imencode(".png", image, [cv2.IMWRITE_PNG_COMPRESSION, 1])
            if not encoded:
                raise ValueError("Could not write the verified tracking pixels")
            frame.write_bytes(content.tobytes())
            destination = root / f"{sample['sample_sha256']}.png"
            try:
                os.link(frame, destination)
            except FileExistsError:
                _verified_override(destination, sample)
    if file_sha(video) != samples[0]["source_sha256"]:
        raise ValueError("Original recording changed during tracking pixel restoration")
    return len(missing)


def replay(args):
    paths = verified_map_package(args.receipt)
    workspace = _private(args.workspace)
    bundle = read_json(paths["bundle"])
    source = bundle["source"]
    raw_policy = read_json(paths["policy"])
    policy = SourcePolicy(raw_policy)
    admitted = policy.allowed[source["source_sha256"]]
    catalog_path = Path(raw_policy["catalog"])
    catalog = RecordingCatalog(catalog_path)
    record = catalog.state.recordings[admitted["video_id"]]
    split = record.learning.get("split")
    if record.split != "DEVELOPMENT" or split not in {"TRAIN", "DEV_COMPARISON", "VALIDATION"}:
        raise ValueError("Tracking requires an admitted DEVELOPMENT learning split")

    bundle_sha = file_sha(paths["bundle"])
    manifest_sha = file_sha(args.manifest)
    base_path = paths["recovered"]
    reference, adaptive, baseline = [
        read_json(path) for path in (args.reference, args.adaptive, base_path)
    ]
    reference_sha = file_sha(args.reference)
    for result in (reference, adaptive, baseline):
        if (result.get("qualified") is not False or result.get("formal_outputs") != 0
                or result.get("timeline_sha256") != bundle_sha
                or result.get("frame_manifest_sha256") != manifest_sha):
            raise ValueError("The development Map inputs use different native observations")
    if baseline.get("reference_report_sha256") != reference_sha:
        raise ValueError("The original recovered result must bind the reference replay")

    previous = None
    if args.exclude_covered:
        load_map_timeline(args.exclude_covered, paths["bundle"], bundle)
        previous = read_json(args.exclude_covered)
        if previous.get("reference_report_sha256") != reference_sha:
            raise ValueError("The previous comparison must share the original reference")

    native, files = bundle["native_frames"], {}
    for row in read_json(args.manifest)["frames"]:
        sample = freeze_native_sample(row["sample"])
        key = sample["sample_sha256"]
        if key in files or native.get(key, {}).get("sample") != sample:
            raise ValueError("Native manifest sample differs from the original timeline")
        files[key] = Path(row["path"])
    targets, selected = episode_inputs(
        bundle, reference, adaptive, baseline, files, whole_episode=args.whole_episode,
        previous=previous,
    )
    overrides = (_private(args.overrides) if args.overrides else
                 workspace / "pixels" / digest([source["source_sha256"], manifest_sha]))
    context = getattr(args, "context_pixels", None)
    context_frames = {}
    if context is not None:
        context_doc = read_json(context)
        if (context_doc.get("schema") != "development_map_marker_context_v1"
                or context_doc.get("timeline_sha256") != bundle_sha
                or context_doc.get("source_sha256") != source["source_sha256"]
                or context_doc.get("formal_outputs") != 0
                or args.layout is None
                or context_doc.get("layout_sha256") != file_sha(args.layout)):
            raise ValueError("The minimap context differs from the frozen timeline or layout")
        for key, row in context_doc["frames"].items():
            if key not in selected:
                continue
            frame = (context.parent / row["file"]).resolve()
            if (not frame.is_relative_to(context.parent.resolve())
                    or file_sha(frame) != row["crop_sha256"]
                    or row["native_pixel_sha256"] != native[key]["sample"]["native_pixel_sha256"]):
                raise ValueError("The minimap context pixels changed")
            context_frames[key] = row
    available, missing = {}, {}
    for key in sorted(selected):
        sample = native[key]["sample"]
        if key in context_frames:
            available[key] = "verified_minimap_cache"
        elif files[key].is_file():
            if file_sha(files[key]) != sample["acquired_frame_sha256"]:
                raise ValueError("An original native frame file has changed")
            available[key] = "native"
        elif _verified_override(overrides / f"{key}.png", sample):
            available[key] = "verified_pixel_cache"
        else:
            missing[key] = sample
    if missing and args.restore_native:
        overrides.mkdir(parents=True, exist_ok=True, mode=0o700)
        phase("tracking_pixels")
        samples = sorted(missing.values(), key=lambda sample: sample["native_pts_tick"])
        if args.max_new_frames:
            samples = samples[:args.max_new_frames]
        _cache_pixels(overrides, samples, Path(admitted["managed_path"]),
                      admitted["video_id"], catalog, reserve=args.reserve_gib * 2**30)
        for key, sample in missing.items():
            if _verified_override(overrides / f"{key}.png", sample):
                available[key] = "verified_pixel_cache"

    identity = {
        "bundle_sha256": bundle_sha, "frame_manifest_sha256": manifest_sha,
        "reference_sha256": reference_sha, "adaptive_sha256": file_sha(args.adaptive),
        "incumbent_sha256": file_sha(base_path), "whole_episode": args.whole_episode,
        "available_sample_refs": sorted(available), "selected_sample_refs": sorted(selected),
    }
    plan = {
        "schema": "development_map_marker_replay_plan_v1", "timeline_sha256": bundle_sha,
        "formal_outputs": 0, "sample_refs": sorted(targets), **identity,
        "native_available": sum(value == "native" for value in available.values()),
        "cache_available": sum(value == "verified_pixel_cache" for value in available.values()),
        "missing": len(selected) - len(available),
    }
    plan_dir = workspace / "plans" / digest(plan)
    plan_dir.mkdir(mode=0o700, parents=True, exist_ok=True)
    pin(plan_dir / "targets_PRIVATE.json", plan)
    print(f"Tracking pixels: {len(available)} / {len(selected)} verified", flush=True)
    if context is not None:
        identity["context_pixels_sha256"] = file_sha(context)
    if args.replay_script is None:
        return plan_dir / "targets_PRIVATE.json"

    if not (args.asset_cache and args.map_catalog and args.layout):
        raise ValueError("Tracker execution needs a pinned asset cache, Map catalog and layout")
    runner = args.replay_script.resolve(strict=True)
    options = {
        "recording-catalog": catalog_path, "recording-id": admitted["video_id"], "split": split,
        "bundle": paths["bundle"], "manifest": args.manifest, "reference": args.reference,
        "adaptive": args.adaptive, "incumbent": base_path, "asset-cache": args.asset_cache,
        "map-catalog": args.map_catalog, "layout": args.layout, "pixel-overrides": overrides,
    }
    for option in ("context-pixels", "match-profile"):
        file = getattr(args, option.replace("-", "_"), None)
        if file is not None:
            options[option] = file
            identity[f"{option}_sha256"] = file_sha(file)
    for flag in ("long-ownership", "contrast-registration"):
        identity[flag] = bool(getattr(args, flag.replace("-", "_"), False))
    if args.alignment_cache:
        alignment = _private(args.alignment_cache)
        if not alignment.is_dir():
            raise ValueError("The exact alignment cache is missing")
        options["alignment-cache"] = alignment
        identity["alignment_cache"] = str(alignment)
    if args.exclude_covered:
        options["exclude-covered"] = args.exclude_covered
        identity["exclude_covered_sha256"] = file_sha(args.exclude_covered)
    for name, path in {
        "map_catalog": args.map_catalog, "layout": args.layout, "asset_index":
        args.asset_cache / "index.json", "runner": runner,
        "association": runner.with_name("marker_tracks.py"),
    }.items():
        identity[f"{name}_sha256"] = file_sha(path)
    for sibling in runner.parent.glob("*.py"):
        identity[f"worker:{sibling.name}"] = file_sha(sibling)
    output = workspace / "runs" / digest(identity)
    output.mkdir(mode=0o700, parents=True, exist_ok=True)
    completion = output / "completion_PRIVATE.json"
    report, proposals = (output / f"{name}_PRIVATE.json" for name in ("tracked", "proposals"))
    with _source_lock(output / "workflow.lock"):
        if completion.is_file():
            pin(completion, {
                "report_sha256": file_sha(report), "proposals_sha256": file_sha(proposals),
            })
            return report
        with TemporaryDirectory(dir=output) as temporary:
            stage = Path(temporary)
            stage_report, stage_proposals = stage / report.name, stage / proposals.name
            options.update(output=stage_report, proposals=stage_proposals)
            command = [sys.executable, str(runner)]
            command.extend(
                str(item) for key, value in options.items() for item in (f"--{key}", value)
            )
            if args.whole_episode:
                command.append("--whole-episode")
            command.extend(f"--{flag}" for flag in ("long-ownership", "contrast-registration")
                           if identity[flag])
            phase("tracking")
            env = {**os.environ, "OMP_NUM_THREADS": "1", "OPENBLAS_NUM_THREADS": "1"}
            run_interruptible(command, env=env)
            load_map_timeline(stage_report, paths["bundle"], bundle)
            staged = read_json(stage_report)["multi_marker_replay"]
            if (staged.get("formal_outputs") != 0
                    or staged["input_sha256s"].get("incumbent") != identity["incumbent_sha256"]):
                raise ValueError("Tracking result differs from the planned original result")
            stage_report.replace(report)
            stage_proposals.replace(proposals)
            pin(completion, {
                "report_sha256": file_sha(report), "proposals_sha256": file_sha(proposals),
            })
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("receipt", "manifest", "reference", "adaptive", "workspace"):
        parser.add_argument(f"--{name}", required=True, type=Path)
    for name in ("overrides", "replay-script", "asset-cache", "map-catalog", "layout",
                 "exclude-covered", "alignment-cache", "context-pixels", "match-profile",
                 "library"):
        parser.add_argument(f"--{name}", type=Path)
    parser.add_argument("--whole-episode", action="store_true")
    parser.add_argument("--long-ownership", action="store_true")
    parser.add_argument("--contrast-registration", action="store_true")
    parser.add_argument("--restore-native", action="store_true")
    parser.add_argument("--reserve-gib", type=int, default=12)
    parser.add_argument("--max-new-frames", type=int, default=0,
                        help="Restore at most this many missing frames per run (0 is unbounded)")
    args = parser.parse_args()
    if args.reserve_gib < 1:
        parser.error("At least 1 GiB of reserved storage is required")
    if args.max_new_frames < 0:
        parser.error("The frame restoration limit must be nonnegative")
    os.umask(0o077)
    cv2.setNumThreads(1)
    result = replay(args)
    if args.library is not None and args.replay_script is not None:
        attach_map_tracker(args.library, args.receipt, result)
    print("Tracking artifact prepared:", result.name)


if __name__ == "__main__":
    main()
