"""Prepare private source-frame evidence for independent review, never confirmed GT.

The schedule is fixed before inspecting recognizer outputs. No analyzer, pack,
labels, expected states or machine-suggested boundaries are loaded.
"""
from __future__ import annotations

import argparse
import html
import json
import math
from decimal import ROUND_CEILING, Decimal
from pathlib import Path

from scripts.e2e.frame_replay import decoder_fingerprints
from scripts.e2e.probe_cache import CachedVideoService
from scripts.e2e.run_dataset_case import sha256_file, valid_id
from valorant_ai_coach.hud.calibrate_temporal import _check_output_privacy
from valorant_ai_coach.video import VideoService


def uniform_schedule(duration: float, step: float) -> list[float]:
    if not all(math.isfinite(x) and x > 0 for x in (duration, step)):
        raise ValueError("positive finite duration and step required")
    count = math.ceil(duration / step)
    if count > 600:
        raise ValueError("overview exceeds 600 frames; increase step")
    return [index * step for index in range(count) if index * step < duration]


def review_schedule(duration: float, step: float, window: list[float] | None) -> list[float]:
    if window is None:
        return uniform_schedule(duration, step)
    start, end = window
    if not all(math.isfinite(x) for x in (duration, start, end)):
        raise ValueError("finite source window required")
    if not 0 <= start < end < duration:
        raise ValueError("review window must be inside source")
    if not math.isfinite(step) or step <= 0:
        raise ValueError("positive finite step required")
    # Subtracting large floats can turn a decimal 0.8-second interval into
    # 0.8000000000000682 and schedule its exclusive endpoint. Decode PTS
    # rounding then correctly rejects that point. Keep the declared decimal
    # schedule exact, without weakening the decoded-PTS interval checks.
    start_decimal, end_decimal, step_decimal = map(lambda v: Decimal(str(v)), (start, end, step))
    count = int(((end_decimal - start_decimal) / step_decimal).to_integral_value(
        rounding=ROUND_CEILING,
    ))
    if count > 600:
        raise ValueError("overview exceeds 600 frames; increase step")
    return [float(point) for index in range(count)
            if (point := start_decimal + index * step_decimal) < end_decimal
            and float(point) < end]


def validate_review_pts(times: list[float], duration: float) -> None:
    """Reject duplicated or unusable decoded evidence, not sparse sampling gaps."""
    if any(not math.isfinite(time) or not 0 <= time < duration for time in times):
        raise ValueError("review evidence has invalid source PTS")
    if any(after <= before for before, after in zip(times, times[1:], strict=False)):
        raise ValueError("review evidence PTS must be distinct and increasing")


def plan_schedule(plan: dict, duration: float, step: float) -> list[float]:
    """Expand source-review tasks only; cannot accept approved GT/event times."""
    if (plan.get("kind") != "private_source_review_plan_not_gt"
            or plan.get("production_input") is not False
            or plan.get("recognizer_outputs_consulted") is not False):
        raise ValueError("source-only private review plan required")
    items = plan.get("items", [])
    if not 1 <= len(items) <= 60:
        raise ValueError("review plan must contain 1 to 60 tasks")
    seen = set()
    schedule = set()
    for row in items:
        identifier = valid_id(row["review_item_id"])
        if identifier in seen:
            raise ValueError("duplicate review task")
        seen.add(identifier)
        if (row.get("approved_ground_truth") is not False
                or row.get("event_time_sec") is not None or row.get("round_id") is not None
                or row.get("continuity_status") != "not_verified"):
            raise ValueError("review task must not contain confirmed GT or continuity")
        schedule.update(review_schedule(duration, step, row["review_window_sec"]))
        if len(schedule) > 2400:
            raise ValueError("batch review exceeds 2400 frames")
    return sorted(schedule)


def source_playback_html(video: Path, window: list[float]) -> str:
    """Link the original local recording; playback is not continuity certification."""
    start, end = window
    if not all(math.isfinite(value) for value in window) or not 0 <= start < end:
        raise ValueError("finite ordered source playback window required")
    uri = html.escape(video.resolve().as_uri() + f"#t={start:.6f},{end:.6f}", quote=True)
    return (
        '<section><h2>Original local source playback — NOT continuity proof</h2>'
        f'<p>Source time {start:.6f}–{end:.6f} s. Review this interval separately '
        'for overlays, capture pauses and discontinuities. Display/timer/score '
        'agreement alone does not prove continuity. No automatic approval.</p>'
        f'<video controls preload="none" style="width:100%" src="{uri}"></video>'
        f'<p><a href="{uri}">Open original source interval</a> if embedded playback '
        'is unavailable. This private page references the original file; it does '
        'not copy, encode or upload video. A browser may require local-file access.</p></section>'
    )


def review_html(rows: list[dict], playback: str = "") -> str:
    cards = []
    for row in rows:
        filename = html.escape(row["image"], quote=True)
        cards.append(
            f'<figure><a href="{filename}"><img src="{filename}" loading="lazy"></a>'
            f'<figcaption>PTS {row["source_frame_pts"]:.6f} s — '
            'unreviewed source evidence</figcaption></figure>'
        )
    return (
        '<!doctype html><html lang="en"><meta charset="utf-8">'
        '<title>Private source overview — NOT ground truth</title>'
        '<style>body{background:#222;color:#eee;font:16px sans-serif}'
        'main{display:grid;grid-template-columns:repeat(2,1fr)}'
        'figure{margin:8px}img{width:100%}</style>'
        '<h1>Unreviewed source evidence — NOT ground truth</h1>'
        '<p>Fixed-time overview only. Sparse frames do not prove boundaries or continuity. '
        'Click for full resolution. Requires separate continuous-window review and '
        'independent approval. No recognizer output was consulted.</p>'
        + playback + '<main>' + ''.join(cards) + '</main></html>'
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--video", type=Path, required=True)
    parser.add_argument("--video-id", required=True)
    parser.add_argument("--source-sha256", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--cache-dir", type=Path, default=Path("outputs/e2e_cache"))
    parser.add_argument("--step", type=float, default=30)
    parser.add_argument("--include-source-playback", action="store_true",
                        help="Private HTML references original local video; no encoding or upload")
    scope = parser.add_mutually_exclusive_group()
    scope.add_argument("--window", type=float, nargs=2,
                        help="Optional source-time review window; never an expected boundary")
    scope.add_argument("--review-plan", type=Path,
                       help="Private source-only tasks; never GT or an Analyzer input")
    args = parser.parse_args()
    video_id = valid_id(args.video_id)
    output = args.output.resolve()
    _check_output_privacy(output)
    if output.exists():
        parser.error("review output must be a new private directory")
    before = sha256_file(args.video)
    if before != args.source_sha256:
        raise ValueError("source hash mismatch")
    service = VideoService()
    probe_fp, _ = decoder_fingerprints(service.ffprobe_path)
    video = CachedVideoService(service, args.cache_dir / "probe", before, probe_fp)
    metadata = video.probe(args.video)
    plan_hash = sha256_file(args.review_plan) if args.review_plan else None
    plan = json.loads(args.review_plan.read_text(encoding="utf-8")) if args.review_plan else None
    if args.review_plan and sha256_file(args.review_plan) != plan_hash:
        raise ValueError("source review plan changed while reading")
    if plan and (plan.get("source_video_sha256") != before
                 or plan.get("video_id") != video_id):
        raise ValueError("review plan source identity mismatch")
    schedule = (plan_schedule(plan, metadata.duration_sec, args.step) if plan is not None
                else review_schedule(metadata.duration_sec, args.step, args.window))
    output.mkdir(parents=True, exist_ok=False)
    print(f"Extracting {len(schedule)} fixed-schedule native source frames", flush=True)
    frames = []
    for offset in range(0, len(schedule), 600):
        folder = output / "frames" if plan is None else output / f"frames_{offset // 600:02d}"
        frames.extend(video.extract_frames(args.video, schedule[offset:offset + 600], folder,
                                           metadata=metadata, max_dimension=None))
        print(f"Decoded {len(frames)}/{len(schedule)} source frames", flush=True)
    if len(frames) != len(schedule):
        raise ValueError("incomplete source overview; do not treat as reviewable")
    validate_review_pts([frame.time_sec for frame in frames], metadata.duration_sec)
    if args.window and any(not args.window[0] <= frame.time_sec < args.window[1]
                           for frame in frames):
        raise ValueError("decoded review PTS outside requested source window")
    if plan is not None:
        for requested, frame in zip(schedule, frames, strict=True):
            owners = [row for row in plan["items"]
                      if row["review_window_sec"][0] <= requested < row["review_window_sec"][1]]
            if not owners or any(not row["review_window_sec"][0] <= frame.time_sec
                                 < row["review_window_sec"][1] for row in owners):
                raise ValueError("decoded batch PTS outside owning review window")
        if sha256_file(args.review_plan) != plan_hash:
            raise ValueError("source review plan changed during extraction")
    if sha256_file(args.video) != before:
        raise ValueError("source changed while extracting review evidence")
    rows = [
        {"requested_sec": requested, "source_frame_pts": frame.time_sec,
         "evidence_frame_sha256": sha256_file(frame.path),
         "image": frame.path.relative_to(output).as_posix(),
         "annotation_status": "unreviewed"}
        for requested, frame in zip(schedule, frames, strict=True)
    ]
    report = {
        "schema_version": 1, "kind": "source_overview_not_gt",
        "video_id": video_id, "source_video_sha256": before,
        "schedule": {"kind": "uniform_source_time", "step_sec": args.step,
                     "window": args.window},
        "source_hash_verified_after_extraction": True,
        "recognizer_outputs_consulted": False, "independent_review_status": "pending",
        "frames": rows, "annotations": [],
        "source_playback_available": args.include_source_playback,
        "window_continuity_certified": False,
    }
    if plan is not None:
        report["schedule"] = {"kind": "private_source_review_windows", "step_sec": args.step,
                              "plan_sha256": plan_hash, "window": None}
        report["review_tasks"] = plan["items"]
        report["window_continuity_certified"] = False
    (output / "review_evidence.json").write_text(
        json.dumps(report, indent=2, allow_nan=False) + "\n", encoding="utf-8",
    )
    if plan is None:
        playback = (source_playback_html(args.video, args.window or [0, metadata.duration_sec])
                    if args.include_source_playback else "")
        page = review_html(rows, playback)
    else:
        task_dir = output / "tasks"
        task_dir.mkdir()
        links = []
        for task in plan["items"]:
            start, end = task["review_window_sec"]
            task_rows = [dict(row, image="../" + row["image"]) for row in rows
                         if start <= row["requested_sec"] < end]
            name = valid_id(task["review_item_id"]) + ".html"
            playback = (source_playback_html(args.video, [start, end])
                        if args.include_source_playback else "")
            (task_dir / name).write_text(review_html(task_rows, playback), encoding="utf-8")
            links.append(f'<li><a href="tasks/{name}">{html.escape(task["review_item_id"])}</a>'
                         f' {start}–{end} s: {html.escape(task["notes"])}</li>')
        page = ('<!doctype html><meta charset="utf-8"><h1>Private batch source review — NOT GT</h1>'
                '<p>Separate source windows. No inferred continuity, events or approval.</p><ol>'
                + ''.join(links) + '</ol>')
    (output / "index.html").write_text(page, encoding="utf-8")
    print(f"Prepared {len(rows)} source frames; no GT has been approved", flush=True)


if __name__ == "__main__":
    main()
