"""Verify production downstream processing of archived real Practical Packages.

Archive injection uses the existing fixture HUD boundary, not new recognition.
No collector, player/visual recognition or canonical evaluator is rerun here.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import time
from dataclasses import asdict
from pathlib import Path

from valorant_ai_coach.bootstrap import build_services
from valorant_ai_coach.hud.analyzers import MockHudAnalyzer, RealHudAnalyzer
from valorant_ai_coach.hud.global_lifecycle import global_recognizer_fingerprint
from valorant_ai_coach.hud.unedited_input import UneditedInputContract
from valorant_ai_coach.settings import AppSettings, SettingsStore
from valorant_ai_coach.ui.backend import BackendFacade


def digest(path: Path) -> str:
    result = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            result.update(block)
    return result.hexdigest()


class ForbiddenCoach:
    """Diagnostic assertion: uncertain packages must not call either AI or mock AI."""

    def evaluate(self, *args: object, **kwargs: object) -> object:
        raise AssertionError('Uncertain Practical package attempted coach evaluation')


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('video', 'packages', 'verification-report', 'input-contract',
                 'layout', 'templates', 'output-directory'):
        parser.add_argument(f'--{name}', type=Path, required=True)
    args = parser.parse_args()
    report = json.loads(args.verification_report.read_bytes())
    if (digest(args.packages) != report['artifact_hashes']['global_packages.json']
            or digest(args.video) != report['source_video_sha256']
            or global_recognizer_fingerprint() != report['recognizer_fingerprint']):
        raise ValueError('archived package, source or recognizer binding changed')
    contract = UneditedInputContract.load(
        args.input_contract, source_video_sha256=report['source_video_sha256'],
    )
    if contract.fingerprint != report['input_contract_sha256']:
        raise ValueError('input assurance changed')
    reader = RealHudAnalyzer(args.layout, template_profile_path=args.templates)
    if reader._base_fingerprint() != report['profile_fingerprint']:
        raise ValueError('archived reader profile changed')
    packages = json.loads(args.packages.read_bytes())['round_packages']
    match_ids = {p['match_id'] for p in packages}
    if len(match_ids) != 1:
        raise ValueError('one nonempty source match required')
    match_id = next(iter(match_ids))
    args.output_directory.mkdir(parents=True, exist_ok=False)
    settings = AppSettings(data_dir=args.output_directory / 'app', hud_mode='real',
                           hud_layout_path=str(args.layout.resolve()), mock_ai=True,
                           round_boundary_mode='practical',
                           unedited_input_contract_path=str(args.input_contract.resolve()))
    services = build_services(SettingsStore(args.output_directory / 'settings.json'),
                              settings=settings)
    pipeline = services.pipeline
    # Feed verified existing Packages without reinterpreting source values.
    # This is an explicit offline integration test, not a runtime cache entrance.
    pipeline.hud_video_processor = None
    pipeline.hud = MockHudAnalyzer(packages)
    pipeline.round_analyzer.coach = ForbiddenCoach()
    started = time.perf_counter()
    initial = pipeline.analyze_video(args.video, match_id=match_id)
    initial_sec = time.perf_counter() - started
    if initial.errors or len(initial.rounds) != len(packages):
        raise AssertionError('archived Practical processing failed')
    initial.analysis_json.replace(args.output_directory / 'initial_analysis.json')
    stored = services.repository.list_round_packages(match_id)
    for original, saved in zip(packages, stored, strict=True):
        if (saved['round_lifecycle'] != original['round_lifecycle']
                or saved['state_snapshots'] != original['state_snapshots']
                or saved['events'] != original['events']):
            raise AssertionError('observed lifecycle/snapshots/events changed in storage')
    started = time.perf_counter()
    resumed = pipeline.resume_analysis(match_id)
    resume_sec = time.perf_counter() - started
    if (resumed.errors or len(resumed.rounds) != len(packages)
            or any(not r.output['analysis_id'].startswith('RESTORED-') for r in resumed.rounds)):
        raise AssertionError('saved Practical rounds were not restored')
    if any(r.output['evaluations'] for r in (*initial.rounds, *resumed.rounds)):
        raise AssertionError('uncertain context produced scored evaluations')
    if initial.clips or resumed.clips:
        raise AssertionError('uncertain context produced coaching clips')
    if stored != services.repository.list_round_packages(match_id):
        raise AssertionError('resume changed stored Packages')
    if digest(args.video) != report['source_video_sha256']:
        raise ValueError('terminal source changed')
    summary = {
        'scope': __doc__, 'source_video_sha256': report['source_video_sha256'],
        'recognizer_fingerprint': report['recognizer_fingerprint'],
        'input_sha256': {str(p): digest(p) for p in
                         (args.packages, args.verification_report, args.input_contract)},
        'package_count': len(stored), 'initial_status': initial.status,
        'resume_status': resumed.status, 'restored_round_count': len(resumed.rounds),
        'scored_evaluations': 0, 'coach_invocations': 0, 'clips': 0,
        'source_recognition_reexecuted': False, 'canonical_e2e_reexecuted': False,
        'gui_data_views': [asdict(BackendFacade._round_partition_view(p)) for p in stored],
        'initial_wall_sec': initial_sec, 'resume_wall_sec': resume_sec,
        'limitations': ['Archived global Packages only; not fresh player/visual analysis',
                        'Fixture-boundary injection does not validate GUI video acquisition',
                        'Qt rendering not executed by this command'],
    }
    with (args.output_directory / 'summary.json').open('x', encoding='utf-8') as stream:
        json.dump(summary, stream, ensure_ascii=False, indent=2)
        stream.write('\n')
    print(json.dumps({key: summary[key] for key in
                      ('package_count', 'restored_round_count', 'scored_evaluations',
                       'initial_wall_sec', 'resume_wall_sec')}))


if __name__ == '__main__':
    main()
