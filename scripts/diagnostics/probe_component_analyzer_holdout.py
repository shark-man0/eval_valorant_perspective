"""Fixed existing image holdouts through actual analyzer; never temporal qualification.

JPEG timestamps retain their original precision. The native geometric prefix
does not make these isolated JPEG images a native continuous sequence. Reviewed
labels are used only after prediction and are never given to the analyzer.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import time
from pathlib import Path

from valorant_ai_coach.hud.analyzers import RealHudAnalyzer
from valorant_ai_coach.hud.global_lifecycle import global_recognizer_fingerprint
from valorant_ai_coach.hud.models import timer_display_evidence
from valorant_ai_coach.video import FrameSample, VideoService

ROOT = Path('outputs/recognition-investigation')
TIMER_SELECTION = ROOT / 'timer-gaussian-fresh-holdout/selection.json'
TIMER_LABELS = ROOT / 'timer-gaussian-fresh-holdout/blind-labels.json'
PHASE_SELECTION = ROOT / 'phase-evidence/structural-text/fresh-holdout-selection.json'
PREVIOUS = Path('e2e_reports/match_001/unedited_component_holdout_replay.json')


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--video', type=Path, required=True)
    parser.add_argument('--layout', type=Path, required=True)
    parser.add_argument('--templates', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--component', choices=('both', 'timer', 'phase'), default='both')
    args = parser.parse_args()
    if args.output.exists():
        raise ValueError('new output required')
    paths = (TIMER_SELECTION, TIMER_LABELS, PHASE_SELECTION, PREVIOUS)
    bound = {p: p.read_bytes() for p in paths}
    selection = json.loads(bound[TIMER_SELECTION])
    previous = json.loads(bound[PREVIOUS])
    labels = json.loads(bound[TIMER_LABELS])
    if labels['selection_sha256'] != hashlib.sha256(bound[TIMER_SELECTION]).hexdigest():
        raise ValueError('review/selection binding mismatch')
    cohorts = {
        'timer': [
            {'path': Path(r['source_frame']), 'time_sec': r['time_sec'],
             'frame_sha256': r['source_file_sha256']}
            for r in selection['observations']
        ],
        'phase': [
            {'path': Path(selected['frame']), 'time_sec': reviewed['pts_sec'],
             'frame_sha256': reviewed['frame_sha256']}
            for selected, reviewed in zip(
                json.loads(bound[PHASE_SELECTION]), previous['phase']['rows'], strict=True,
            )
        ],
    }
    if args.component != 'both':
        cohorts = {args.component: cohorts[args.component]}
    for cohort in cohorts.values():
        for row in cohort:
            if digest(row['path']) != row['frame_sha256']:
                raise ValueError('reviewed source image changed')
    source_hash = selection['source_video_sha256']
    if previous['source_video_sha256'] != source_hash:
        raise ValueError('holdout sources differ')
    code = global_recognizer_fingerprint()
    predictions = {}
    profile = None
    started = time.perf_counter()
    for name, cases in cohorts.items():
        diagnostics = []
        analyzer = RealHudAnalyzer(args.layout, template_profile_path=args.templates,
                                   diagnostic_sink=diagnostics.append)
        current_profile = analyzer.fingerprint()
        if profile is not None and current_profile != profile:
            raise ValueError('cohort profile mismatch')
        profile = current_profile
        cohort_started = time.perf_counter()
        with VideoService().native_window(
            args.video, start_sec=0, end_sec=.10, source_video_sha256=source_hash,
            png_prediction='up', max_png_bytes=20_000_000,
        ) as prefix:
            frames = [FrameSample(r['time_sec'], r['path']) for r in cases]
            measured = analyzer.observe_frames((*prefix, *frames), _build_events=False)
            offset = len(prefix)
            predictions[name] = {
                'prefix_frames': offset, 'prefix_gap_not_temporal_evidence': True,
                'rows': [
                    {'image': str(case['path']), 'frame_sha256': case['frame_sha256'],
                     'pts_sec': case['time_sec'], 'observation': observation,
                     'native_ui_measurements': scan,
                     'geometry_calibrated': diagnostic['geometry_calibrated'],
                     'phase_measurement': diagnostic['semantic_text_measurements'].get(
                         'buy_phase_template', {}),
                     'phase_signals': {
                         key: value for key, value in diagnostic['signals'].items()
                         if key.startswith(('buy_phase_template', 'semantic_buy_phase'))
                     }}
                    for case, observation, scan, diagnostic in zip(
                        cases, measured.observations[offset:],
                        measured.native_ui_measurements[offset:], diagnostics[offset:], strict=True,
                    )
                ],
                'wall_clock_sec': time.perf_counter() - cohort_started,
            }
            for frame in prefix:
                frame.read_image()
        if analyzer.fingerprint() != profile:
            raise ValueError('terminal analyzer profile changed')
    if (global_recognizer_fingerprint() != code
            or any(p.read_bytes() != raw for p, raw in bound.items())
            or any(digest(r['path']) != r['frame_sha256']
                   for cases in cohorts.values() for r in cases)):
        raise ValueError('terminal code/review/image binding changed')
    # Score only the existing fixed labels after predictions are complete.
    timer_counts = dict(correct=0, unknown=0, wrong=0)
    for row, label in zip(predictions.get('timer', {}).get('rows', []),
                          labels['observations'] if 'timer' in predictions else [], strict=True):
        display = timer_display_evidence(row['observation']['values'])
        actual = display['display'] if display else None
        expected = label['timer_text']
        outcome = 'unknown' if actual is None else 'correct' if actual == expected else 'wrong'
        row.update(reviewed_display=expected, actual_display=actual, outcome=outcome)
        timer_counts[outcome] += 1
    phase_counts = dict(positive_correct=0, positive_unknown=0, negative_false_accepts=0,
                        negative_rejected=0, invalid_scans=0)
    phase_reader_counts = dict(positive_correct=0, positive_unknown=0,
                               negative_false_accepts=0, negative_rejected=0)
    for row, label in zip(predictions.get('phase', {}).get('rows', []),
                          previous['phase']['rows'] if 'phase' in predictions else [], strict=True):
        obs = row['observation']
        accepted = 'buy_phase_banner' in obs['state_flags']
        scan_valid = row['native_ui_measurements']['phase_scan_valid'] is True
        expected = label['expected_present']
        outcome = ('positive_correct' if accepted else 'positive_unknown') if expected else (
            'negative_false_accepts' if accepted else 'negative_rejected')
        phase_counts[outcome] += 1
        phase_counts['invalid_scans'] += int(not scan_valid)
        reader_accepted = row['phase_measurement'].get('presence') is True
        reader_outcome = ('positive_correct' if reader_accepted else 'positive_unknown') if (
            expected) else ('negative_false_accepts' if reader_accepted else 'negative_rejected')
        phase_reader_counts[reader_outcome] += 1
        row.update(expected_present=expected, accepted=accepted, scan_valid=scan_valid,
                   outcome=outcome, reader_accepted=reader_accepted, reader_outcome=reader_outcome)
    old_timer = previous['timer']['previous']
    old_phase = previous['phase']['previous']
    result = {
        'scope': __doc__, 'source_video_sha256': source_hash,
        'profile_fingerprint': profile, 'recognizer_fingerprint': code,
        'diagnostic_script_sha256': digest(Path(__file__)),
        'input_sha256': {str(p): hashlib.sha256(raw).hexdigest() for p, raw in bound.items()},
        'cohorts': predictions,
        'comparison': {
            'timer': {k: {'previous': old_timer[k], 'current': v, 'delta': v - old_timer[k]}
                      for k, v in timer_counts.items()} if 'timer' in predictions else None,
            'phase': {k: {'previous': old_phase.get(k), 'current': v,
                          'delta': v - old_phase[k] if k in old_phase else None}
                      for k, v in phase_counts.items()} if 'phase' in predictions else None,
            'phase_raw_reader': {
                k: {'previous': old_phase.get(k), 'current': v,
                    'delta': v - old_phase[k] if k in old_phase else None}
                for k, v in phase_reader_counts.items()
            } if 'phase' in predictions else None,
        },
        'comparison_scope': ('Previous phase metrics describe isolated raw-reader matches; '
                             'current phase metrics describe classified temporal flags. '
                             'Only phase_raw_reader is a like-for-like reader comparison.'),
        'processed_holdout_images': sum(len(c) for c in cohorts.values()),
        'continuous_temporal_validation': False, 'real_qualification_created': False,
        'native_jpeg_source_pts_verified': False, 'natural_timer_absence_controls': False,
        'released_events': 0, 'canonical_current': None, 'canonical_delta': None,
        'previous_comparable_runtime': None, 'runtime_delta': None,
        'wall_clock_sec': time.perf_counter() - started,
    }
    args.output.write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps({'timer': timer_counts if 'timer' in predictions else None,
                      'phase_flags': phase_counts if 'phase' in predictions else None,
                      'phase_raw_reader': phase_reader_counts if 'phase' in predictions else None,
                      'images': result['processed_holdout_images'],
                      'wall_clock_sec': result['wall_clock_sec']}))


if __name__ == '__main__':
    main()
