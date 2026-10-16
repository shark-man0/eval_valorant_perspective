"""Compare frozen canonical traces under original and ±0.1 boundary timing policy."""
from __future__ import annotations

import argparse
import hashlib
import json
import time
from collections import Counter
from pathlib import Path

from scripts.e2e.boundary_time_policy import POLICY_VERSION, number
from tests.e2e.evaluate_saved_trace import evaluate_trace


def counts(report: dict) -> dict:
    found = Counter(row['status'] for row in report['assertion_results'])
    return {key: found[key] for key in ('pass', 'fail', 'not_evaluated')}


def compare(pack: Path, trace_path: Path) -> dict:
    paths = [trace_path, pack/'tests/reference_evaluator.py',
             pack/'tests/generated/e2e_assertions_v3.json',
             pack/'ground_truth/timeline_ground_truth_v3.json',
             pack/'ground_truth/evaluation_policy_v3.json',
             pack/'schemas/e2e_output_trace_schema_v1.json',
             Path(__file__), Path(__file__).with_name('boundary_time_policy.py'),
             Path(__file__).resolve().parents[2]/'tests/e2e/evaluate_saved_trace.py']
    inputs = {p: hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}
    trace = json.loads(trace_path.read_text(encoding='utf-8'))
    started = time.perf_counter()
    previous = evaluate_trace(pack, trace)
    canonical_sec = time.perf_counter()-started
    started = time.perf_counter()
    current = evaluate_trace(pack, trace, boundary_timing_profile=POLICY_VERSION)
    practical_sec = time.perf_counter()-started
    if any(hashlib.sha256(p.read_bytes()).hexdigest() != digest for p, digest in inputs.items()):
        raise ValueError('evaluation inputs changed during comparison')
    before, after = counts(previous), counts(current)
    changes = [
        {'assertion_id': b['assertion_id'], 'group': b['group'],
         'previous': a['status'], 'current': b['status']}
        for a, b in zip(previous['assertion_results'], current['assertion_results'], strict=True)
        if a['status'] != b['status']
    ]
    windows = {row['assertion_id']: row for row in current['boundary_timing_policy']['windows']}
    assertions = json.loads((pack/'tests/generated/e2e_assertions_v3.json').read_text(
        encoding='utf-8'))
    diagnostics = []
    for req in assertions['required_point_events']:
        if req['id'] not in windows:
            continue
        row = windows[req['id']]
        start, end = map(number, row['raw_evidence_bracket'])
        matched = [e for e in trace['events'] if
                   (e.get('round_id'), e.get('type'), e.get('actor')) ==
                   (req['round_id'], req['type'], req['actor'])]
        diagnostics.append({**row, 'events': [
            {'time_sec': e['time_sec'],
             'distance_to_raw_bracket_sec': float(max(start-number(e['time_sec']),
                                                      number(e['time_sec'])-end, 0)),
             'distance_to_canonical_window_sec': float(max(
                 number(row['canonical_window'][0])-number(e['time_sec']),
                 number(e['time_sec'])-number(row['canonical_window'][1]), 0)),
             'provenance_present': bool(e.get('attributes', {}).get('evidence_provenance'))}
            for e in matched]})
    return {
        'version': 'boundary-timing-comparison-v1', 'timing_policy': POLICY_VERSION,
        'scope': 'Frozen trace re-evaluation only; no new recognition or qualification',
        'inputs': [{'role': str(p.relative_to(pack)) if p.is_relative_to(pack) else p.name,
                    'sha256': digest} for p, digest in inputs.items()],
        'canonical': previous, 'practical': current,
        'counts': {'previous': before, 'current': after,
                   'delta': {k: after[k]-before[k] for k in before}},
        'changed_assertions': changes, 'boundary_diagnostics': diagnostics,
        'evaluation_runtime_sec': {'canonical': canonical_sec, 'practical': practical_sec},
        'recognizer_changed': False, 'sampler_changed': False,
        'validation_pack_modified': False, 'production_adoption': False,
        'new_full_e2e_executed': False,
        'qualification_warning': 'Timing PASS assumes a valid producer event; does not attest '
                                 'current code/profile qualification or independent GT review.',
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--pack', type=Path, required=True)
    parser.add_argument('--trace', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args(argv)
    if args.output.exists():
        raise FileExistsError('preserve prior results: use a new output path')
    # Never overwrite a source artifact even if an output path aliases an input.
    report = compare(args.pack.resolve(), args.trace.resolve())
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open('x', encoding='utf-8') as output:
        json.dump(report, output, indent=2, allow_nan=False)
        output.write('\n')
    print(json.dumps({'timing_policy': POLICY_VERSION, **report['counts'],
                      'changed_assertions': report['changed_assertions']}))
    return 0  # Successful comparison is not an all-assertions acceptance result.


if __name__ == '__main__':
    raise SystemExit(main())
