"""Build the common development timeline from a verified native acquisition."""

from __future__ import annotations

import argparse
import hashlib
import time
from fractions import Fraction
from pathlib import Path

import cv2
import numpy as np
from acquire_native import development_source
from job_control import check_pause

from valorant_ai_coach.rules.development_timeline import review_timeline
from valorant_ai_coach.temporal.application import build_application_timeline, write_timeline_csv
from valorant_ai_coach.temporal.camera_panel import (
    CameraHintReference,
    LabelReference,
    camera_rows,
    measure_frame,
)
from valorant_ai_coach.temporal.evidence import digest, freeze_native_sample
from valorant_ai_coach.temporal.game import DevelopmentGameTimeline, observation
from valorant_ai_coach.temporal.match import frame_observations
from valorant_ai_coach.temporal.match_observer import ProfileHudObserver
from valorant_ai_coach.temporal.replay import file_sha, read_json, write_private

_VIEW_VETOES = {
    "report": ("combat_report_visible",),
    "remote": ("cypher_camera_template", "sova_drone_template", "skye_trailblazer_template",
               "other_remote_view_template"),
    "result": ("round_end_template",),
}


def prepare(
    *, policy_path: Path, acquisition: Path, hud_config: Path, spectator_label: Path, output: Path,
    camera_hint: Path | None = None,
):
    start = time.monotonic()
    receipt = read_json(acquisition)
    scope = file_sha(acquisition)
    policy, source = development_source(policy_path, receipt["sha256"])
    if (source["video_id"] != receipt["source"] or receipt["native_pts_parity"] is not True
            or receipt["verified_source_before_after"] is not True):
        raise ValueError("An exact admitted native acquisition is required")
    if any((p / ".git").exists() for p in (output.resolve(), *output.resolve().parents)):
        raise ValueError("Private timeline output must remain outside Git checkouts")
    output.mkdir(parents=True, mode=0o700, exist_ok=False)
    label = LabelReference.load(spectator_label)
    hint = CameraHintReference.load(camera_hint) if camera_hint is not None else None
    hud = ProfileHudObserver(hud_config)
    producer = digest({"profile": hud.fingerprint, "method": "current_profile_view_veto_v1"})
    base = Fraction(receipt["base"])
    duration = Fraction(receipt["duration"])
    if base <= 0 or duration <= 0 or not receipt["frames"]:
        raise ValueError("A nonempty native acquisition with a valid clock is required")
    measurements = []
    views = {}
    frame_paths = {}
    previous_bin = -1
    for index, (tick, path) in enumerate(receipt["frames"]):
        if index % 32 == 0:
            check_pause()
        if index and index % 2500 == 0:
            print(f"Measured {index} of {len(receipt['frames'])} native frames", flush=True)
        elapsed = (tick - receipt["origin"]) * base
        bin_index = int(5 * elapsed)
        if not 0 <= elapsed < duration or bin_index <= previous_bin:
            raise ValueError("Expected at most one increasing native sample per 5 Hz bin")
        previous_bin = bin_index
        contents = Path(path).read_bytes()
        image = cv2.imdecode(np.frombuffer(contents, np.uint8), cv2.IMREAD_COLOR)
        if image is None:
            raise ValueError("Unreadable native recording frame")
        sample = freeze_native_sample({
            "source_id": source["video_id"], "source_sha256": source["source_sha256"],
            "acquisition_id": scope, "native_epoch": scope, "native_pts_tick": tick,
            "native_time_base": str(base), "frame_size_px": list(image.shape[:2][::-1]),
            "acquired_frame_sha256": hashlib.sha256(contents).hexdigest(),
            "native_pixel_sha256": hashlib.sha256(image.tobytes()).hexdigest(),
        })
        policy.admit(sample)
        key = sample["sample_sha256"]
        frame_paths[key] = {"sample": sample, "path": path}
        measurements.append((sample, measure_frame(image, label, camera=hint)))
        if index % 50 == 0:
            views[key] = frame_observations(hud.inspect(image), sample, hud.fingerprint)
            continue
        ui = hud.profile.detect_signals(image, hud.layout, context={}, semantic_diagnostics={})
        veto = [tag for tag, keys in _VIEW_VETOES.items() if any(ui.get(k) is True for k in keys)]
        if ui.get("spectator_detector_checked") and ui.get("spectator_panel_present"):
            veto.append("spectator")
        views[key] = [observation(
            sample=sample, producer=producer, signals=veto,
            raw={"ui": ui, "qualified": False, "formal_outputs": 0},
            context={"stream_kind": "existing_profile_veto_only"},
        )]
    panel = camera_rows(measurements, label, camera=hint)
    for record in panel["observations"]:
        views[record["sample"]["sample_sha256"]].append(record)
    engine = DevelopmentGameTimeline(
        fuse_exact_native_evidence=True, practical_visual_state=True, report_view_bridge=True,
        measured_view_precedence=True, evidence_continuity=True,
    )
    for observations in views.values():
        for row in observations:
            engine.add(row)
    timeline = build_application_timeline(
        engine.rebuild(), source=source, duration=duration,
        origin=receipt["origin"] * base,
    )
    if (timeline["formal_outputs"] != 0
            or set(timeline["native_frames"]) != frame_paths.keys()):
        raise ValueError("Common timeline did not retain the exact development observations")
    timeline_path = output / "timeline_PRIVATE.json"
    frame_path = output / "map_frames_PRIVATE.json"
    evaluation_path = output / "evaluation_PRIVATE.json"
    csv_path = output / "timeline_1s_PRIVATE.csv"
    write_private(timeline_path, timeline)
    write_private(frame_path, {"frames": list(frame_paths.values())})
    write_private(evaluation_path, review_timeline(timeline))
    write_timeline_csv(csv_path, timeline["seconds"])
    write_private(output / "completion_PRIVATE.json", {
        "output_sha256s": {path.name: file_sha(path)
                           for path in (timeline_path, frame_path, evaluation_path, csv_path)},
        "acquisition_sha256": scope,
        "native_frames": len(frame_paths), "one_second_rows": len(timeline["seconds"]),
        "elapsed_seconds": time.monotonic() - start, "formal_outputs": 0,
    })


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("policy-path", "acquisition", "hud-config", "spectator-label", "output"):
        parser.add_argument(f"--{name}", type=Path, required=True)
    parser.add_argument("--camera-hint", type=Path)
    cv2.setNumThreads(1)
    prepare(**vars(parser.parse_args()))


if __name__ == "__main__":
    main()
