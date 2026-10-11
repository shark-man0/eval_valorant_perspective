"""Bounded continuous real HUD/visual processing with verified archived lifecycle.

Offline archive replay is explicit; it is not a production recognition cache.
Package extents come from whole-source lifecycle, but observations cover only the
requested interval. This does not evaluate canonical assertions or precision.
"""
from __future__ import annotations

import argparse
import json
import time
from collections import Counter
from pathlib import Path

from scripts.diagnostics.verify_practical_saved_pipeline import digest
from valorant_ai_coach.bootstrap import build_services
from valorant_ai_coach.hud.global_lifecycle import global_recognizer_fingerprint
from valorant_ai_coach.hud.practical_lifecycle import (
    PracticalLifecycleAnalysis,
    validated_practical_boundaries,
)
from valorant_ai_coach.hud.unedited_input import UneditedInputContract
from valorant_ai_coach.rounds.boundaries import BoundaryObservation
from valorant_ai_coach.settings import AppSettings, SettingsStore
from valorant_ai_coach.video import FrameSample


def load_verified_archive(
    video: Path, archive_path: Path, verification_report: Path, input_contract: Path,
) -> tuple[PracticalLifecycleAnalysis, dict[str, object]]:
    """Offline replay binding shared by bounded and whole-application diagnostics."""
    report = json.loads(verification_report.read_bytes())
    archive = json.loads(archive_path.read_bytes())
    if (digest(archive_path) != report['artifact_hashes']['native_analysis.json']
            or digest(video) != report['source_video_sha256']
            or global_recognizer_fingerprint() != report['recognizer_fingerprint']
            or archive['qualification_file_sha256'] is not None):
        raise ValueError('archive binding changed or qualified archive unsupported')
    contract = UneditedInputContract.load(
        input_contract, source_video_sha256=report['source_video_sha256'],
    )
    analysis = PracticalLifecycleAnalysis(
        source_rows=tuple(archive['source_rows']),
        boundaries=tuple(BoundaryObservation.from_dict(b) for b in archive['boundaries']),
        diagnostics=tuple(archive['diagnostics']),
        native_step_ticks=archive['native_step_ticks'], input_contract=contract,
        input_contract_path=input_contract,
        profile_fingerprint=archive['profile_fingerprint'],
        recognizer_fingerprint=archive['recognizer_fingerprint'],
    )
    if contract.fingerprint != report['input_contract_sha256']:
        raise ValueError('input contract hash changed')
    return analysis, report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('video', 'archive', 'verification-report', 'input-contract',
                 'layout', 'templates', 'output-directory'):
        parser.add_argument(f'--{name}', type=Path, required=True)
    parser.add_argument('--start-sec', type=float, required=True)
    parser.add_argument('--end-sec', type=float, required=True)
    args = parser.parse_args()
    analysis, report = load_verified_archive(
        args.video, args.archive, args.verification_report, args.input_contract,
    )
    args.output_directory.mkdir(parents=True, exist_ok=False)
    settings = AppSettings(
        data_dir=args.output_directory / 'app', hud_mode='real', mock_ai=True,
        hud_layout_path=str(args.layout.resolve()),
        hud_template_profile_path=str(args.templates.resolve()),
        round_boundary_mode='practical',
        unedited_input_contract_path=str(args.input_contract.resolve()),
    )
    services = build_services(SettingsStore(args.output_directory / 'settings.json'),
                              settings=settings)
    processor = services.pipeline.hud_video_processor
    if processor is None:
        raise ValueError('real production processor required')
    validated_practical_boundaries(
        analysis, source_video_sha256=report['source_video_sha256'],
        profile_fingerprint=processor.analyzer._base_fingerprint(),
    )
    metadata = processor.video.probe(args.video)
    expected = {r['source_pts_ticks']: r for r in analysis.source_rows
                if args.start_sec <= r['source_pts_sec'] < args.end_sec}
    started = time.perf_counter()
    with processor.video.native_window(
        args.video, start_sec=args.start_sec, end_sec=args.end_sec,
        source_video_sha256=report['source_video_sha256'], png_prediction='up',
        max_png_bytes=2 * 1024**3,
    ) as native:
        if set(expected) != {f.pts_ticks for f in native}:
            raise ValueError('continuous decoder coverage differs from archive')
        for frame in native:
            row = expected[frame.pts_ticks]
            if (row['source_pixel_sha256'] != frame.pixel_sha256
                    or row['source_time_base'] != str(frame.time_base)):
                raise ValueError('native pixels/timebase differ from archive')
        samples = [FrameSample(f.time_sec, f.path, f.pts_ticks, str(f.time_base),
                               f.source_video_sha256, f.encoded_sha256) for f in native]
        result = processor.process_frames(
            metadata, 'practical-continuous-diagnostic', samples,
            boundary_mode='practical', practical_lifecycle=analysis,
            require_detected_rounds=False,
        )
    if digest(args.video) != report['source_video_sha256']:
        raise ValueError('terminal source changed')
    packages = list(result.round_packages)
    summary = {
        'scope': __doc__, 'source_video_sha256': report['source_video_sha256'],
        'archive_sha256': digest(args.archive),
        'recognizer_fingerprint': global_recognizer_fingerprint(),
        'requested_interval_sec': [args.start_sec, args.end_sec],
        'processed_frames': result.sampled_frame_count,
        'wall_sec': time.perf_counter() - started,
        'observation_count': len(result.observations),
        'primary_states': dict(Counter(r['primary_state'] for r in result.observations)),
        'hud_event_count': len(result.hud_events),
        'visual_event_count': len(result.visual_events),
        'visual_observation_count': len(result.visual_observations),
        'package_count': len(packages), 'diagnostics': result.diagnostics,
        'canonical_e2e_reexecuted': False, 'precision_verified': False,
        'limitations': ['Only requested native interval receives fresh HUD/visual recognition',
                        'Whole-source boundary provenance; package extents may exceed interval',
                        'No canonical assertion or independent point-time evaluation'],
    }
    for filename, value in (('summary.json', summary),
                            ('packages.json', {'round_packages': packages})):
        (args.output_directory / filename).write_text(
            json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8',
        )
    print(json.dumps({k: summary[k] for k in ('processed_frames', 'package_count', 'wall_sec')}))


if __name__ == '__main__':
    main()
