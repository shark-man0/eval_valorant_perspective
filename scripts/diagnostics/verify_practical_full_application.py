"""Whole Practical HUD/Visual application validation using verified native archive.

Only native lifecycle collection is replayed from its hash-bound current-code
archive. The unchanged production sampler and real HUD/Visual recognizers run
fresh. Production FactBuilder, RoundAnalyzer, persistence and resume follow.
This is not a canonical E2E or qualification; no GT is supplied to processing.
"""
from __future__ import annotations

import argparse
import json
import time
from collections import Counter
from dataclasses import asdict
from pathlib import Path
from typing import Any

from scripts.diagnostics.verify_practical_frame_processing import load_verified_archive
from scripts.diagnostics.verify_practical_saved_pipeline import ForbiddenCoach, digest
from valorant_ai_coach.bootstrap import build_services
from valorant_ai_coach.diagnostics.runtime_timing import RuntimeTimingCollector
from valorant_ai_coach.hud.practical_lifecycle import validated_practical_boundaries
from valorant_ai_coach.settings import AppSettings, SettingsStore
from valorant_ai_coach.ui.backend import BackendFacade


def write_json(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, default=str) + '\n',
                    encoding='utf-8')


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('video', 'archive', 'verification-report', 'input-contract',
                 'layout', 'templates', 'output-directory'):
        parser.add_argument(f'--{name}', type=Path, required=True)
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
    pipeline = services.pipeline
    processor = pipeline.hud_video_processor
    if processor is None:
        raise ValueError('real production processor required')
    validated_practical_boundaries(
        analysis, source_video_sha256=report['source_video_sha256'],
        profile_fingerprint=processor.analyzer._base_fingerprint(),
    )
    pipeline.round_analyzer.coach = ForbiddenCoach()
    original_process = processor.process
    captured: dict[str, Any] = {}

    def process_with_verified_archive(**kwargs: Any) -> Any:
        if captured or kwargs.get('boundary_mode') != 'practical':
            raise AssertionError('one fresh Practical processing invocation required')
        options = kwargs.pop('native_lifecycle_options')
        if options.unedited_input_contract_path != args.input_contract.resolve():
            raise ValueError('application source contract differs from archive contract')
        result = original_process(**kwargs, practical_lifecycle=analysis)
        captured['result'] = result
        # Persist fresh reader diagnostics before downstream processing. No
        # recognizer output is used as ground truth or qualification here.
        write_json(args.output_directory / 'fresh_processing.json', {
            'observations': result.observations, 'hud_events': result.hud_events,
            'visual_events': result.visual_events,
            'visual_observations': result.visual_observations,
            'zone_resolutions': result.zone_resolutions,
            'round_packages': result.round_packages, 'diagnostics': result.diagnostics,
        })
        return result

    # Explicit offline native transport injection only. The real common
    # processor still executes acquisition, both HUD passes and Visual analysis.
    processor.process = process_with_verified_archive
    collector = RuntimeTimingCollector()
    started = time.perf_counter()
    with collector:
        initial = pipeline.analyze_video(args.video, match_id='practical-full-application')
    initial_sec = time.perf_counter() - started
    if initial.errors or not initial.rounds or 'result' not in captured:
        raise AssertionError(f'fresh application processing failed: {initial.errors}')
    result = captured['result']
    if any(r.output['evaluations'] for r in initial.rounds) or initial.clips:
        raise AssertionError('uncertain contexts produced scores/clips')
    initial.analysis_json.replace(args.output_directory / 'initial_analysis.json')
    stored = services.repository.list_round_packages(initial.match_id)
    started = time.perf_counter()
    resumed = pipeline.resume_analysis(initial.match_id)
    resume_sec = time.perf_counter() - started
    if (resumed.errors or len(resumed.rounds) != len(initial.rounds)
            or any(not r.output['analysis_id'].startswith('RESTORED-') for r in resumed.rounds)
            or stored != services.repository.list_round_packages(initial.match_id)):
        raise AssertionError('fresh Practical Package restore failed')
    if any(r.output['evaluations'] for r in resumed.rounds) or resumed.clips:
        raise AssertionError('resume promoted uncertain context')
    validated_practical_boundaries(
        analysis, source_video_sha256=digest(args.video),
        profile_fingerprint=processor.analyzer._base_fingerprint(),
    )
    if digest(args.archive) != report['artifact_hashes']['native_analysis.json']:
        raise ValueError('terminal archive changed')
    summary = {
        'scope': __doc__, 'source_video_sha256': report['source_video_sha256'],
        'archive_sha256': digest(args.archive),
        'profile_fingerprint': analysis.profile_fingerprint,
        'recognizer_fingerprint': analysis.recognizer_fingerprint,
        'processed_frames': result.sampled_frame_count,
        'primary_states': dict(Counter(o['primary_state'] for o in result.observations)),
        'hud_event_count': len(result.hud_events),
        'visual_event_count': len(result.visual_events),
        'map_resolution_record_count': len(result.zone_resolutions),
        'map_resolved_count': sum(bool(z.get('zone_id')) for z in result.zone_resolutions),
        'package_count': len(stored), 'restored_package_count': len(resumed.rounds),
        'scored_evaluations': 0, 'coach_invocations': 0, 'clips': 0,
        'initial_status': initial.status, 'resume_status': resumed.status,
        'initial_wall_sec': initial_sec, 'resume_wall_sec': resume_sec,
        'frames_per_sec': result.sampled_frame_count / initial_sec,
        'runtime': collector.snapshot(),
        'gui_data_views': [asdict(BackendFacade._round_partition_view(p)) for p in stored],
        'canonical_e2e_reexecuted': False, 'independent_precision_verified': False,
        'limitations': ['Native collection reuses a verified archive; no GUI acquisition',
                        'Source-wide HUD/Visual analysis uses the unchanged production sampler',
                        'No canonical evaluator, independent point labels or qualification'],
    }
    write_json(args.output_directory / 'summary.json', summary)
    print(json.dumps({k: summary[k] for k in ('processed_frames', 'package_count',
                                            'restored_package_count', 'initial_wall_sec')}))


if __name__ == '__main__':
    main()
