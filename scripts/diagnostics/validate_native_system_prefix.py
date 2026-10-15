"""Verify a continuous native global-reader entrance, without GT or proofs."""

from __future__ import annotations

import argparse
import hashlib
import json
import time
from pathlib import Path

from scripts.diagnostics.native_score_gaps import summarize_native_score_gaps
from valorant_ai_coach.hud.analyzers import RealHudAnalyzer
from valorant_ai_coach.hud.global_lifecycle import global_recognizer_fingerprint
from valorant_ai_coach.hud.practical_lifecycle import collect_practical_lifecycle
from valorant_ai_coach.video import VideoService


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--video', required=True, type=Path)
    parser.add_argument('--source-sha256', required=True)
    parser.add_argument('--layout', required=True, type=Path)
    parser.add_argument('--start', required=True, type=float)
    parser.add_argument('--end', required=True, type=float)
    parser.add_argument('--native-step-ticks', required=True, type=int)
    parser.add_argument('--output', required=True, type=Path)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument('--include-ui-measurements', action='store_true',
                      help='Unqualified scan measurements only; never system evidence/events')
    mode.add_argument('--practical-input-contract', type=Path,
                      help='Use existing producer-owned practical candidates; never formal events')
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError('preserve existing native diagnostic receipts; choose a new output')
    analyzer = RealHudAnalyzer(args.layout)
    profile_fingerprint = analyzer.fingerprint()
    recognizer_fingerprint = global_recognizer_fingerprint()
    started = time.perf_counter()
    practical = None
    with VideoService().native_window(
        args.video, start_sec=args.start, end_sec=args.end,
        source_video_sha256=args.source_sha256,
    ) as frames:
        if args.practical_input_contract is not None:
            practical = collect_practical_lifecycle(
                analyzer, frames, native_step_ticks=args.native_step_ticks,
                input_contract_path=args.practical_input_contract,
            )
            if practical.confirmed_lifecycle is not None or any(
                b.boundary_status != 'provisional' for b in practical.boundaries
            ):
                raise ValueError('provisional diagnostic requires an unqualified profile')
            rows = practical.source_rows
        else:
            rows = analyzer.observe_native_system_frames(
                frames, native_step_ticks=args.native_step_ticks,
                include_ui_measurements=args.include_ui_measurements,
            )
        encoded_hashes = [frame.encoded_sha256 for frame in frames]
    # Decoder context verifies terminal video integrity before artifact release.
    if (
        profile_fingerprint != analyzer.fingerprint()
        or recognizer_fingerprint != global_recognizer_fingerprint()
    ):
        raise ValueError('native prefix inputs changed during validation')
    elapsed = time.perf_counter() - started
    observations = [row['system_observation'] for row in rows]
    displays = [item['values'].get('round_time_remaining_display') for item in observations]
    report = {
        'scope': 'continuous native development input; no holdout or lifecycle qualification',
        'window_sec': [args.start, args.end],
        'source_video_sha256': args.source_sha256,
        'layout_path': str(args.layout), 'profile_fingerprint': profile_fingerprint,
        'recognizer_fingerprint': recognizer_fingerprint,
        'diagnostic_script_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        'processed_frames': len(rows), 'native_step_ticks': args.native_step_ticks,
        'native_encoded_sha256': encoded_hashes,
        'wall_clock_sec': elapsed, 'frames_per_sec': len(rows) / elapsed,
        'timer_display_accepted': sum(display is not None for display in displays),
        'timer_display_unknown': sum(display is None for display in displays),
        'display_accuracy_reviewed': False,
        'unqualified_ui_measurements_requested': args.include_ui_measurements,
        'practical_candidate_mode': practical is not None,
        'provisional_boundary_count': len(practical.boundaries) if practical else 0,
        'provisional_boundaries': [b.to_dict() for b in practical.boundaries] if practical else [],
        'practical_diagnostics': practical.diagnostics if practical else [],
        'geometry': analyzer.last_calibration_diagnostics,
        'score_gap_summary': summarize_native_score_gaps(rows, args.native_step_ticks),
        'rows': rows,
        'qualification_loaded': analyzer.global_qualification is not None,
        'qualification_created': False,
        'events_released': 0,
        'canonical_current': None, 'canonical_delta': None,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding="utf-8"
    )
    print(json.dumps({key: report[key] for key in (
        'processed_frames', 'wall_clock_sec', 'timer_display_accepted',
        'timer_display_unknown', 'provisional_boundary_count', 'events_released',
    )}))


if __name__ == '__main__':
    main()
