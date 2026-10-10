"""Reserved actual-analyzer score validation; no qualification or snapshot admission.

The fixed interval is a diagnostic input range, never a runtime timing rule.
Original source images are reviewed only after predictions. No GT is loaded.
"""
from __future__ import annotations

import hashlib
import json
import shutil
import time
from pathlib import Path

from scripts.diagnostics.inventory_native_exposure import collect_ticks
from scripts.diagnostics.validate_frozen_result_feature import timestamp_ticks
from valorant_ai_coach.hud.analyzers import RealHudAnalyzer
from valorant_ai_coach.hud.global_lifecycle import global_recognizer_fingerprint
from valorant_ai_coach.hud.models import shared_score_evidence
from valorant_ai_coach.video.native import decode_native_window


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def run():
    start = time.perf_counter()
    reports = Path('e2e_reports/match_001')
    reserve_path = reports / 'shared_score_fixed_source_reservation.json'
    output_path = reports / 'shared_score_fixed_source_predictions.json'
    directory = Path('outputs/recognition-investigation/shared-score-fixed-source-validation')
    if reserve_path.exists() or output_path.exists() or directory.exists():
        raise ValueError('new evidence paths required')
    layout = Path('outputs/hud_profiles/round-global-timer-glyph-20261008/hud_layout.json')
    sidecar = layout.parent / 'score-rowcontrast-late-result-diagnostic.templates.json'
    analyzer = RealHudAnalyzer(layout, template_profile_path=sidecar)
    profile, code = analyzer.fingerprint(), global_recognizer_fingerprint()
    old = json.loads((reports / 'frozen_result_late_native_cohort.json').read_text())
    paths = set(old['input_sha256']) | {str(p) for p in reports.glob('*.json')}
    inputs = {}
    exposed = set()
    for name in sorted(paths):
        raw = Path(name).read_bytes()
        inputs[name] = hashlib.sha256(raw).hexdigest()
        value = json.loads(raw)
        exposed.update(collect_ticks(value))
        exposed.update(timestamp_ticks(value))
    for path in (layout, sidecar, Path(__file__)):
        inputs[str(path)] = digest(path)
    ticks = [t for t in range(553, 2670000, 256) if 133.2 <= t / 15360 <= 133.5]
    selected = sorted(set(ticks) - exposed)
    if len(selected) < 3:
        raise ValueError('insufficient known-unexposed source frames; no predictions')
    source_hash = '71d58558559d6f578433ce9f234bf176f76fd5a86657dbfe3eba1e7d36136b06'
    reserve_path.write_text(json.dumps({
        'scope': 'Frozen score-profile source validation, not independent temporal qualification',
        'selection_reason': (
            'Later gameplay background than result-development frames; fixed before scores'
        ),
        'window_sec': [133.2, 133.5], 'source_video_sha256': source_hash,
        'time_base': '1/15360', 'cohort_ticks': ticks, 'selected_review_ticks': selected,
        'known_exposure_excluded_ticks': sorted(set(ticks) & exposed),
        'exhaustive_exposure_proven': False, 'same_video_correlation': True,
        'profile_fingerprint': profile, 'recognizer_fingerprint': code,
        'input_sha256': inputs, 'predictions_made': False,
    }, indent=2) + '\n')
    directory.mkdir()
    # Preserve mutable analysis input before future followup writes.
    shutil.copyfile(reports / 'failure_analysis.json',
                    directory / 'failure-analysis-at-selection.json')
    video = Path('ValorantData/videos/Valorant_09-25-2026_0-37-29-379.mp4')
    options = {'source_video_sha256': source_hash,
               'ffmpeg': shutil.which('ffmpeg'), 'ffprobe': shutil.which('ffprobe')}
    with (
        decode_native_window(video, start_sec=0, end_sec=.09, **options) as prefix,
        decode_native_window(video, start_sec=133.2, end_sec=133.5, **options) as frames,
    ):
        if [f.pts_ticks for f in frames] != ticks:
            raise ValueError('native source coverage differs from reservation')
        result = analyzer.observe_frames((*prefix, *frames), _build_events=False)
        rows = []
        for index, (frame, observation) in enumerate(
            zip(frames, result.observations[len(prefix):], strict=True), 1
        ):
            frame.read_image()
            path = directory / f'frame_{index:02d}.png'
            shutil.copyfile(frame.path, path)
            rows.append({'source_pts_ticks': frame.pts_ticks, 'pts_sec': frame.time_sec,
                         'source_pixel_sha256': frame.pixel_sha256,
                         'frame_sha256': frame.encoded_sha256, 'path': str(path),
                         'reserved_for_review': frame.pts_ticks in selected,
                         'observation': observation,
                         'accepted_shared_scores': shared_score_evidence(observation)})
        prefix_count = len(prefix)
    if (analyzer.fingerprint() != profile or global_recognizer_fingerprint() != code
            or any(digest(path) != value for path, value in inputs.items())):
        raise ValueError('terminal input/profile/code mismatch')
    output_path.write_text(json.dumps({
        'scope': (
            'Actual analyzer source scores; review pending, not qualification or canonical run'
        ),
        'reservation_sha256': digest(reserve_path), 'profile_fingerprint': profile,
        'recognizer_fingerprint': code, 'source_video_sha256': source_hash,
        'rows': rows, 'processed_native_frames': len(rows), 'prefix_frames': prefix_count,
        'prefix_gap_is_not_temporal_evidence': True, 'review_before_predictions': False,
        'qualification_created': False, 'released_events': 0,
        'canonical_current': None, 'canonical_delta': None,
        'wall_clock_sec': time.perf_counter() - start,
    }, indent=2) + '\n')
    print(json.dumps({'processed_native_frames': len(rows), 'reserved': len(selected),
                      'accepted_scores': {key: sum(row['accepted_shared_scores'][key] is not None
                                                   for row in rows)
                                          for key in ('score_ally', 'score_enemy')}}))


if __name__ == '__main__':
    run()
