"""Measure same-population native source links with configured HUD ROIs excluded.

Consumes the private native-source diagnostic, not expected labels. Neither
camera measurements nor timer displays are turned into continuity or events.
"""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

import cv2

from scripts.diagnostics.diagnose_round_lifecycle import sha256_file
from scripts.diagnostics.measure_source_correspondence import load_method, measure
from valorant_ai_coach.hud.calibrate_temporal import _check_output_privacy
from valorant_ai_coach.hud.layout import HudLayout


def numeric_consistency_runs(rows: list[dict]) -> list[dict]:
    """Describe countdown-consistent numeric runs, not source continuity.

    A run spanning the existing 50ms confirmation floor still does not prove
    a game clock, phase transition, source segment or round boundary. Accurate
    visible text and qualified lifecycle-clock semantics are different facts.
    Unknown/weak input is never repaired from a neighbor.
    """
    runs: list[dict] = []
    current: dict | None = None
    prior: tuple[float, float] | None = None
    for row in rows:
        pts, value, score = row["pts_sec"], row.get("timer_sec"), row.get("timer_confidence")
        if type(pts) not in (int, float) or not math.isfinite(pts):
            raise ValueError("finite numeric native source PTS required")
        accepted = (
            type(value) in (int, float) and math.isfinite(value) and value >= 0
            and type(score) in (int, float) and math.isfinite(score) and .90 <= score <= 1
        )
        if not accepted:
            current, prior = None, None
            continue
        compatible = (
            prior is not None and 0 < pts - prior[0] <= 1
            and 0 <= prior[1] - value <= pts - prior[0] + 1
        )
        if current is None or not compatible:
            current = {
                "first_pts_sec": pts, "last_pts_sec": pts, "observation_count": 0,
                "first_numeric_sec": value, "last_numeric_sec": value,
                "minimum_reader_confidence": score, "observed_span_sec": 0.0,
                "meets_50ms_duration_floor": False, "continuity_attested": False,
            }
            runs.append(current)
        current["last_pts_sec"] = pts
        current["last_numeric_sec"] = value
        current["observation_count"] += 1
        current["minimum_reader_confidence"] = min(current["minimum_reader_confidence"], score)
        current["observed_span_sec"] = pts - current["first_pts_sec"]
        current["meets_50ms_duration_floor"] = (
            current["observation_count"] >= 2 and current["observed_span_sec"] >= .05
        )
        prior = (pts, value)
    return runs


def measure_run(video: Path, run_dir: Path, layout_path: Path, method_path: Path,
                roi_names: list[str]) -> dict:
    if not roi_names or len(set(roi_names)) != len(roi_names):
        raise ValueError("distinct configured exclusion ROIs required")
    report_path = run_dir / "results.json"
    paths = (video, report_path, layout_path, method_path)
    hashes = [sha256_file(path) for path in paths]
    source = json.loads(report_path.read_bytes())
    if (source.get("native_pts_coverage_verified") is not True
            or source.get("source_video_sha256") != hashes[0]):
        raise ValueError("verified native source coverage and matching video hash required")
    layout = HudLayout.load(layout_path)
    excluded = []
    for name in roi_names:
        roi = layout.normalized_roi(name)
        excluded.append([roi.x, roi.y, roi.right, roi.bottom])
    method = load_method(method_path)
    windows = []
    for window_index, window in enumerate(source["windows"]):
        rows = window["rows"]
        if len(rows) < 2:
            raise ValueError("at least two native source frames required")
        pairs, frame_hashes = [], []
        previous_image = None
        previous_pts = None
        for index, row in enumerate(rows, 1):
            path = run_dir / f"window-{window_index:03d}" / f"frame_{index:06d}.png"
            frame_hash = sha256_file(path)
            if frame_hash != row["frame_sha256"]:
                raise ValueError("native source frame hash mismatch")
            image = cv2.imread(str(path))
            if image is None:
                raise ValueError("native source image unreadable")
            pts = row["pts_sec"]
            if type(pts) not in (int, float) or not math.isfinite(pts):
                raise ValueError("finite numeric native source PTS required")
            if previous_pts is not None:
                if not pts > previous_pts:
                    raise ValueError("native source PTS must increase strictly")
                pairs.append({
                    "before_pts_sec": previous_pts, "after_pts_sec": pts,
                    "raw": measure(previous_image, image, method),
                    "outside_configured_ui": measure(
                        previous_image, image, method, excluded_bounds_norm=excluded,
                    ),
                })
            previous_image, previous_pts = image, pts
            frame_hashes.append(frame_hash)
        # Detect source mutations during measurement, not just before it.
        for index, expected in enumerate(frame_hashes, 1):
            path = run_dir / f"window-{window_index:03d}" / f"frame_{index:06d}.png"
            if sha256_file(path) != expected:
                raise ValueError("native source frames changed during measurement")
        windows.append({"window_sec": window["window_sec"], "pairs": pairs,
                        "numeric_consistency_runs": numeric_consistency_runs(rows)})
    if hashes != [sha256_file(path) for path in paths]:
        raise ValueError("diagnostic inputs changed during measurement")
    return {
        "scope": __doc__, "source_video_sha256": hashes[0],
        "native_diagnostic_sha256": hashes[1], "hud_layout_sha256": hashes[2],
        "method_sha256": hashes[3], "method": method,
        "exclusion_roi_names": roi_names, "excluded_bounds_norm": excluded,
        "diagnostic_implementation_sha256": sha256_file(Path(__file__)),
        "measurement_implementation_sha256": sha256_file(
            Path(__file__).with_name("measure_source_correspondence.py")
        ),
        "numeric_run_policy": {"minimum_reader_confidence": .90,
                               "maximum_sample_gap_sec": 1.0, "duration_floor_sec": .05,
                               "unknown_input_breaks_run": True,
                               "does_not_prove_source_or_clock_semantics": True},
        "qualification_created": False, "production_changed": False, "windows": windows,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("video", "native-run-dir", "hud-layout", "method", "output"):
        parser.add_argument(f"--{name}", type=Path, required=True)
    parser.add_argument("--exclude-roi", action="append", required=True)
    args = parser.parse_args()
    _check_output_privacy(args.output.resolve())
    result = measure_run(args.video, args.native_run_dir, args.hud_layout,
                         args.method, args.exclude_roi)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"pair_count": sum(len(w["pairs"]) for w in result["windows"]),
                      "qualification_created": False}))


if __name__ == "__main__":
    main()
