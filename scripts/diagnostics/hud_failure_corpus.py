"""Private, source-gated HUD case index from existing native observations.

No decoder, fitting, labels or global-geometry override. New recordings must
first pass existing Source-only registration, allocation and Exposure gates.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from scripts.diagnostics.analyze_personal_candidates import development_sources
from scripts.diagnostics.register_private_sources import write_private
from scripts.diagnostics.round_lifecycle_evidence import lifecycle
from scripts.diagnostics.round_transition_evidence import _score, _segments, _text, _witness, _word
from scripts.e2e.run_dataset_case import read_json, sha256_file
from scripts.temporal_gt.contract import canonical_hash
from scripts.temporal_gt.review_session import append_exposure
from valorant_ai_coach.hud.calibrate_temporal import _check_output_privacy


def index_rows(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Keep per-channel cases and native witnesses; no unreviewed negatives.

    Case identity excludes acquisition epoch so identical pixels can be found
    again. Occurrences retain epoch and diagnostics, and are never stitched
    together into a boundary. Native consistency is checked by existing code.
    """
    _segments(rows)
    report = lifecycle(rows)
    cases: dict[str, dict[str, Any]] = {}
    counts: Counter[str] = Counter()
    unobserved = 0
    for f in rows:
        if f.get('analysed') is False:
            unobserved += 1
            continue
        geometry = f.get('geometry_diagnostic', {})
        categories = {'geometry': ['global_structure_supported'] if f['geometry_consistent']
                      else geometry.get('reasons') or ['geometry_unknown']}
        for field in ('ally_score', 'enemy_score', 'timer', 'result'):
            read = f[field]
            value = _word(f) if field == 'result' else _text(read)
            categories[field] = (['accepted_text_not_GT'] if value is not None else
                                 read.get('sources') or
                                 [read.get('region', {}).get('reason') or 'read_unknown'])
            if value is not None and not f['geometry_consistent']:
                categories[field] = categories[field] + ['accepted_text_geometry_rejected']
            if field == 'result' and value is None and read.get('region', {}).get('bounds'):
                categories[field] = categories[field] + ['ocr_unread_with_region_proposal']
        categories['purchase'] = ['purchase_observed' if f.get('buy_phase') is True else
                                  'purchase_not_detected_NOT_negative' if
                                  f.get('buy_phase') is False else 'purchase_unobserved']
        for role, reasons in categories.items():
            identity = {k: f[k] for k in ('source_sha256', 'tick', 'time_base', 'pixel_sha256')}
            key = canonical_hash({**identity, 'role': role})
            case = cases.setdefault(key, {'case_id': key, 'source_id': f['source_id'],
                                         **identity, 'role': role, 'occurrences': [],
                                         'human_label': 'UNKNOWN'})
            occurrence = {'frame': _witness(f), 'reasons': reasons,
                          'geometry_consistent': f['geometry_consistent'],
                          'geometry_diagnostic': geometry,
                          'score_pair': _score(f), 'read': f.get(role),
                          'path': f.get('path'), 'scope_diagnostic': f.get('scope_diagnostic')}
            case['occurrences'].append(occurrence)
            counts.update(role + ':' + str(reason) for reason in reasons)
    return {'kind': 'private_HUD_failure_corpus_NOT_GT', 'cases': list(cases.values()),
            'observation_categories': dict(sorted(counts.items())),
            'unanalysed_native_rows': unobserved, 'lifecycle': report,
            'formal_events': [], 'approved_gt': False, 'qualification_created': False,
            'unreviewed_is_negative': False}


def build(session: Path, inputs: list[Path], output: Path) -> dict[str, Any]:
    """Reuse current registry gates and Exposure journal; reject overwrites."""
    _check_output_privacy(output.resolve())
    if output.exists():
        raise ValueError('new private output required')
    allowed = {(s['video_id'], s['source_sha256']) for s in development_sources(session)}
    frozen = []
    for path in inputs:
        digest = sha256_file(path)
        data = read_json(path)
        identity = data['source_id'], data['source_sha256']
        if identity not in allowed or any(
            (f['source_id'], f['source_sha256']) != identity for f in data['rows']
        ):
            raise ValueError('registered DEVELOPMENT source binding required')
        frozen.append((path, digest, data))
    if not frozen or len({str(p.resolve()) for p, _, _ in frozen}) != len(frozen):
        raise ValueError('unique nonempty inputs required')
    corpora = []
    for path, digest, data in frozen:
        corpus = index_rows(data['rows'])
        corpus.update(input_sha256=digest, source_id=data['source_id'],
                      source_sha256=data['source_sha256'])
        if sha256_file(path) != digest:
            raise ValueError('input changed while indexing')
        corpora.append(corpus)
    for path, digest, _ in frozen:
        if sha256_file(path) != digest:
            raise ValueError('input changed while indexing')
    result = {'kind': 'private_multi_source_HUD_corpus_NOT_GT', 'corpora': corpora,
              'review_queue': review_queue(corpora),
              'implementation_sha256': sha256_file(Path(__file__)),
              'formal_events': [], 'approved_gt': False, 'qualification_created': False}
    write_private(output, result)
    for source_id in sorted({d['source_id'] for _, _, d in frozen}):
        append_exposure(session, 'prediction', output,
                        'Private native HUD case index; categories are diagnostics, not labels, '
                        'negative GT or qualification. No cross-epoch boundary association.',
                        source_id=source_id)
    return result


def review_queue(corpora: list[dict[str, Any]], *, budget: int = 24) -> list[dict[str, Any]]:
    """One per source/channel/reason stratum, bounded and deterministically fair.

    This prediction-targeted queue supports DEVELOPMENT review, not independent
    discovery or qualification. A source with many failures cannot consume the
    entire budget. Repeated pixels do not request duplicate human work.
    """
    if type(budget) is not int or not 1 <= budget <= 200:
        raise ValueError('review budget must be 1..200')
    strata: dict[tuple[str, str, str], dict[str, Any]] = {}
    for corpus in corpora:
        for case in sorted(corpus['cases'], key=lambda c: (c['tick'], c['case_id'])):
            for occurrence in case['occurrences']:
                if not occurrence['path']:
                    continue
                for reason in occurrence['reasons']:
                    key = case['source_id'], case['role'], reason
                    strata.setdefault(key, {'case_id': case['case_id'], 'source_id': key[0],
                                            'role': key[1], 'reason': reason,
                                            'frame': occurrence['frame'],
                                            'path': occurrence['path'],
                                            'human_label': 'UNKNOWN'})
    by_channel: dict[str, dict[str, list[dict[str, Any]]]] = defaultdict(
        lambda: defaultdict(list))
    for key, value in sorted(strata.items()):
        channel = by_channel[key[0]][key[1]]
        if not any(c['case_id'] == value['case_id'] for c in channel):
            channel.append(value)
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for source, channels in sorted(by_channel.items()):
        for depth in range(max(map(len, channels.values()))):
            for _, channel in sorted(channels.items()):
                if depth < len(channel):
                    grouped[source].append(channel[depth])
    queue: list[dict[str, Any]] = []
    seen: set[str] = set()
    while any(grouped.values()) and len(queue) < budget:
        for source in sorted(grouped):
            if not grouped[source] or len(queue) >= budget:
                continue
            item = grouped[source].pop(0)
            if item['case_id'] not in seen:
                queue.append(item)
                seen.add(item['case_id'])
    return queue


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--review-session', type=Path, required=True)
    parser.add_argument('--input', type=Path, action='append', required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    build(args.review_session, args.input, args.output)


if __name__ == '__main__':
    main()
