"""Audit saved evidence bindings; does not generate lifecycle qualification."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from valorant_ai_coach.hud.analyzers import RealHudAnalyzer
from valorant_ai_coach.hud.global_lifecycle import global_recognizer_fingerprint
from valorant_ai_coach.hud.unedited_input import UneditedInputContract


def digest(path: Path) -> str:
    result = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            result.update(block)
    return result.hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--video', type=Path, required=True)
    parser.add_argument('--layout', type=Path, required=True)
    parser.add_argument('--input-contract', type=Path, required=True)
    parser.add_argument('--report', type=Path, action='append', required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise ValueError('new output required')
    source_hash = digest(args.video)
    contract = UneditedInputContract.load(
        args.input_contract, source_video_sha256=source_hash,
    )
    analyzer = RealHudAnalyzer(args.layout)
    profile = analyzer.fingerprint()
    code = global_recognizer_fingerprint()
    records = []
    initial_hashes = {str(args.input_contract): digest(args.input_contract)}
    for path in args.report:
        initial_hashes[str(path)] = digest(path)
        report = json.loads(path.read_text())
        dependencies = report.get('input_sha256', {})
        if not isinstance(dependencies, dict):
            raise ValueError(f'invalid dependency mapping: {path}')
        checks = []
        for name, expected in dependencies.items():
            dependency = Path(name)
            actual = digest(dependency) if dependency.is_file() else None
            checks.append({'path': name, 'expected_sha256': expected,
                           'actual_sha256': actual, 'matches': actual == expected})
            if actual is not None:
                initial_hashes[name] = actual
        records.append({
            'report': str(path), 'report_sha256': initial_hashes[str(path)],
            'scope': report.get('scope'),
            'source_matches': report.get('source_video_sha256') == source_hash,
            'profile_matches': (report.get('profile_fingerprint') == profile
                                if 'profile_fingerprint' in report else None),
            'code_matches': report.get('recognizer_fingerprint') == code,
            'contract_matches': (report.get('input_contract_sha256') == contract.fingerprint
                                 if 'input_contract_sha256' in report else None),
            'dependency_checks': checks,
            'qualification_created': report.get('qualification_created'),
            'released_events': report.get('released_events'),
        })
    # Recheck the complete audit inputs before publication. Historical report
    # bindings are reported as historical; never rewrite or resign them.
    if (digest(args.video) != source_hash or analyzer.fingerprint() != profile
            or global_recognizer_fingerprint() != code
            or any(digest(Path(name)) != value for name, value in initial_hashes.items())):
        raise ValueError('audit input changed before terminal verification')
    result = {
        'scope': 'Evidence inventory only; matching fingerprints are not qualification.',
        'source_video_sha256': source_hash,
        'profile_fingerprint': profile, 'recognizer_fingerprint': code,
        'input_contract_sha256': contract.fingerprint, 'reports': records,
        'qualification_created': False, 'released_events': 0,
        'qualification_rules': {
            'required_components': ['timer', 'purchase_phase', 'ui_transition'],
            'minimum_distinct_hashes_per_split': 3,
            'minimum_correct_holdout_cases_per_component': 3,
            'holdout_wrong': 0, 'negative_false_positive': 0,
            'aggregate_splits_must_be_disjoint': True,
            'no_independent_episode_count_requirement_in_current_loader': True,
        },
        'limitations': [
            'Does not verify image labels or classify reports as independent holdout.',
            'Distinct hashes do not prove independent temporal episodes.',
            'A bootstrap negative with no prior phase does not test stale preparation.',
            'Historical code mismatch cannot be repaired by resigning the report.',
            'No edit-exclusion image proof is required for the explicit assured source.',
        ],
        'canonical_current': None, 'canonical_delta': None,
    }
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps({'reports': len(records),
                      'current_code_matches': sum(r['code_matches'] for r in records),
                      'dependency_mismatches': sum(
                          not c['matches'] for r in records for c in r['dependency_checks']),
                      'qualification_created': False}))


if __name__ == '__main__':
    main()
