"""Public fixture worker for a packaged GUI test without private recognition assets."""

import argparse
import time
from fractions import Fraction
from pathlib import Path

from valorant_ai_coach.application.map_library import publish_map_package
from valorant_ai_coach.recordings.catalog import RecordingCatalog
from valorant_ai_coach.temporal.application import build_application_timeline
from valorant_ai_coach.temporal.game import DevelopmentGameTimeline
from valorant_ai_coach.temporal.map_recorder_path import VERSION, join_recorder_seconds
from valorant_ai_coach.temporal.map_timeline_report import load_map_timeline
from valorant_ai_coach.temporal.replay import file_sha, write_private


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--video", type=Path)
    source.add_argument("--recording-id")
    parser.add_argument("--confirm-distinct", action="store_true")
    for key in ("catalog", "setup", "workspace", "library", "pause-file"):
        parser.add_argument(f"--{key}", type=Path, required=True)
    args = parser.parse_args()
    catalog = RecordingCatalog(args.catalog)
    recording_id = args.recording_id
    if recording_id is None:
        assert args.confirm_distinct
        recording_id = catalog.register(
            args.video, split="DEVELOPMENT", confirm_distinct=True,
        ).recording_id
    print(f"Map registered recording: {recording_id}", flush=True)
    print("Map workflow phase: acquisition", flush=True)

    if args.setup.stem == "baseline" and args.video is not None:
        limit = time.monotonic() + 20
        while not args.pause_file.is_file():
            if time.monotonic() >= limit:
                raise RuntimeError("Packaged Map smoke did not receive a pause request")
            time.sleep(.05)
        return 75

    recording = catalog.state.recordings[recording_id]
    bundle = args.workspace / "timeline" / "timeline_PRIVATE.json"
    timeline = build_application_timeline(
        DevelopmentGameTimeline().rebuild(),
        source={"video_id": recording_id, "source_sha256": recording.source_sha256,
                "physical_match_id": recording.physical_match_id},
        origin=Fraction(0), duration=Fraction(2),
    )
    if not bundle.is_file():
        write_private(bundle, timeline)
        write_private(bundle.parent / "completion_PRIVATE.json",
                      {"output_sha256s": {bundle.name: file_sha(bundle)}})
    directory = args.workspace / args.setup.stem
    standard = directory / "standard_PRIVATE.json"
    recovered = directory / "recovered_PRIVATE.json"
    report = {"schema": VERSION, "qualified": False, "formal_outputs": 0, "segments": [],
              "timeline_sha256": file_sha(bundle), "interpolated_samples": 0}
    report["second_rows"] = join_recorder_seconds(report, timeline)
    write_private(standard, report)
    write_private(recovered, {**report, "primary_report_sha256": file_sha(standard)})
    write_private(recovered.with_suffix(".display.json"), {
        "schema": "development_map_display_v1", "formal_outputs": 0,
        "report_sha256": file_sha(recovered), "atlases": [],
    })
    policy = directory / "policy_PRIVATE.json"
    write_private(policy, {"catalog": str(catalog.root), "allowed_recording_ids": [recording_id]})
    evaluation = directory / "evaluation_PRIVATE.json"
    write_private(evaluation, {
        "source": {"source_id": recording_id, "physical_match_id": recording.physical_match_id},
        "formal_outputs": 0, "formal_promotion": None,
        "development_map": {"formal_outputs": 0,
                            "summary": load_map_timeline(recovered, bundle, timeline)["summary"]},
    })
    print("Map workflow phase: publication", flush=True)
    publish_map_package(args.library, label="Synthetic smoke", bundle=bundle, policy=policy,
                        standard=standard, recovered=recovered, evaluation=evaluation,
                        variant=args.setup.stem)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
