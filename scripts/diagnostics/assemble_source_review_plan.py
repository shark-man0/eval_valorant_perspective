"""Link private human/developer source observations to hashed frames, never GT.

This is annotation preparation only. No Analyzer, expected-state pack or
recognizer profile is loaded. A review interval is not an event timestamp.
"""
from __future__ import annotations

import argparse
import html
import json
import math
from pathlib import Path

from scripts.diagnostics.prepare_boundary_review import validate_review_pts
from scripts.e2e.run_dataset_case import sha256_file
from valorant_ai_coach.hud.calibrate_temporal import _check_output_privacy


def assemble(evidence: dict, observations: list[dict]) -> dict:
    if evidence.get("kind") != "source_overview_not_gt" or evidence.get(
        "recognizer_outputs_consulted"
    ) is not False or evidence.get("source_hash_verified_after_extraction") is not True:
        raise ValueError("independent source evidence required")
    frames = evidence["frames"]
    times = [row["source_frame_pts"] for row in frames]
    if not times:
        raise ValueError("source evidence is empty")
    validate_review_pts(times, max(times) + 1)
    index = dict(zip(times, frames, strict=True))
    rows = []
    for number, observation in enumerate(observations):
        start, end = observation["review_window_sec"]
        if not all(math.isfinite(x) for x in (start, end)) or not start < end:
            raise ValueError("ordered finite review endpoints required")
        if start not in index or end not in index:
            raise ValueError("review endpoints must reference extracted source frames")
        if observation["kind"] not in {
            "start_review", "result_display_review", "unobserved_end_review",
            "obscuration_review", "match_end_review",
        } or not isinstance(observation["notes"], str):
            raise ValueError("invalid observation")
        rows.append({
            "review_item_id": f"source_review_{number + 1:03d}",
            "kind": observation["kind"], "notes": observation["notes"],
            "review_window_sec": [start, end], "event_time_sec": None,
            "round_id": None, "annotation_status": "candidate_pending_independent_review",
            "continuity_status": "not_verified", "approved_ground_truth": False,
            "evidence": [{"source_frame_pts": time,
                          "evidence_frame_sha256": index[time]["evidence_frame_sha256"]}
                         for time in (start, end)],
        })
    return {
        "kind": "private_source_review_plan_not_gt", "video_id": evidence["video_id"],
        "source_video_sha256": evidence["source_video_sha256"],
        "recognizer_outputs_consulted": False, "production_input": False,
        "independent_review_status": "pending", "items": rows,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--evidence", type=Path, required=True)
    parser.add_argument("--observations", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    output = args.output.resolve()
    _check_output_privacy(output)
    if output.exists():
        raise FileExistsError("use a new private output directory")
    evidence = json.loads(args.evidence.read_text(encoding="utf-8"))
    # Source evidence images must still agree with the frozen extraction record.
    for frame in evidence["frames"]:
        path = (args.evidence.parent / frame["image"]).resolve()
        if not path.is_relative_to(args.evidence.parent.resolve()) or (
            sha256_file(path) != frame["evidence_frame_sha256"]
        ):
            raise ValueError("source evidence image integrity failed")
    report = assemble(evidence, json.loads(args.observations.read_text(encoding="utf-8")))
    report["evidence_manifest_sha256"] = sha256_file(args.evidence)
    report["observation_input_sha256"] = sha256_file(args.observations)
    output.mkdir(parents=True)
    # UTF-8 JSON is an application-owned diagnostic artifact.
    (output / "review_plan.json").write_text(json.dumps(report, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    cards = []
    frames_by_time = {frame["source_frame_pts"]: frame for frame in evidence["frames"]}
    for row in report["items"]:
        links = []
        for point in row["evidence"]:
            time = point["source_frame_pts"]
            image = args.evidence.parent / frames_by_time[time]["image"]
            uri = html.escape(image.resolve().as_uri(), quote=True)
            links.append(f'<a href="{uri}">PTS {time:.6f}<br>'
                         f'<img src="{uri}" loading="lazy" width="480"></a>')
        cards.append(f'<li>{html.escape(row["review_item_id"])} — '
                     f'{html.escape(row["kind"])} {row["review_window_sec"]} s: '
                     f'{html.escape(row["notes"])}<div>{" ".join(links)}</div></li>')
    (output / "index.html").write_text(
        '<!doctype html><meta charset="utf-8"><h1>Private review plan — NOT GT</h1>'
        '<p>Intervals are review tasks, not event times or continuous evidence. '
        'All items require closer source review and independent approval.</p><ol>'
        + ''.join(cards) + '</ol>', encoding="utf-8",
    )
    print(f'Prepared {len(report["items"])} private review tasks; no GT generated')


if __name__ == "__main__":
    main()
