import json
from copy import deepcopy

import pytest

from scripts.diagnostics.hud_failure_corpus import build, index_rows, review_queue
from tests.unit.test_round_lifecycle_evidence import chain


def test_scope_cannot_promote_global_unknown_or_supply_missing_read():
    rows = chain()
    rows[2]['geometry_consistent'] = False
    rows[2]['geometry_diagnostic'] = {'reasons': ['insufficient_anchors']}
    rows[2]['scope_diagnostic'] = {'status': 'TOP_STRUCTURE_SUPPORTED'}
    before = deepcopy(rows)
    r = index_rows(rows)
    assert r['lifecycle']['chains'][0]['status'] == 'UNKNOWN'
    assert r['observation_categories']['geometry:insufficient_anchors'] == 1
    assert all(c['human_label'] == 'UNKNOWN' for c in r['cases'])
    assert not r['approved_gt'] and not r['unreviewed_is_negative']
    assert rows == before


def test_unanalysed_frames_are_not_failures_or_negatives():
    rows = chain()
    rows[0]['analysed'] = False
    r = index_rows(rows)
    assert r['unanalysed_native_rows'] == 1
    assert not any(c['tick'] == rows[0]['tick'] for c in r['cases'])


def test_result_ocr_failure_is_distinct_from_region_failure_and_geometry_rejection():
    rows = chain()
    rows[3]['result'] = {'value': None, 'confidence': 0,
                         'region': {'bounds': [1, 1, 20, 20], 'reason': 'proposal'}}
    rows[4]['geometry_consistent'] = False
    r = index_rows(rows)
    assert r['observation_categories']['result:ocr_unread_with_region_proposal'] == 1
    assert r['observation_categories']['timer:accepted_text_geometry_rejected'] == 1


def test_epoch_replay_reuses_case_identity_without_stitching_boundaries():
    rows = chain()
    replay = deepcopy(rows)
    for f in replay:
        f['epoch'] = 'second'
    r = index_rows(rows + replay)
    assert len(r['cases']) == len(rows) * 6
    assert all(len(c['occurrences']) == 2 for c in r['cases'])
    assert not r['lifecycle']['cross_epoch_association']
    assert len(r['lifecycle']['chains']) == 1


@pytest.mark.parametrize('fault', ['unregistered', 'evaluation', 'mixed'])
def test_source_gate_rejects_before_indexing_or_exposure(tmp_path, monkeypatch, fault):
    import scripts.diagnostics.hud_failure_corpus as module
    rows = chain()
    source = {'video_id': rows[0]['source_id'], 'source_sha256': rows[0]['source_sha256']}
    allowed = [] if fault in ('unregistered', 'evaluation') else [source]
    monkeypatch.setattr(module, 'development_sources', lambda _: allowed)
    monkeypatch.setattr(module, '_check_output_privacy', lambda _: None)
    calls = []
    monkeypatch.setattr(module, 'append_exposure', lambda *a, **k: calls.append(a))
    if fault == 'mixed':
        rows[-1]['source_sha256'] = 'b' * 64
    p = tmp_path / 'input.json'
    p.write_text(json.dumps({'source_id': source['video_id'],
                             'source_sha256': source['source_sha256'], 'rows': rows}))
    output = tmp_path / 'output.json'
    with pytest.raises(ValueError, match='DEVELOPMENT'):
        build(tmp_path, [p], output)
    assert not output.exists() and not calls


def test_existing_output_is_not_overwritten(tmp_path, monkeypatch):
    import scripts.diagnostics.hud_failure_corpus as module
    monkeypatch.setattr(module, '_check_output_privacy', lambda _: None)
    p = tmp_path / 'output.json'
    p.write_text('original')
    with pytest.raises(ValueError, match='new private output'):
        build(tmp_path, [], p)
    assert p.read_text() == 'original'


def test_review_queue_is_bounded_deduplicated_and_fair_across_sources():
    rows = chain()
    for f in rows:
        f['path'] = 'local.png'
    first = index_rows(rows)
    second_rows = deepcopy(rows)
    for f in second_rows:
        f['source_id'] = 'second'
        f['source_sha256'] = 'b' * 64
    second = index_rows(second_rows)
    queue = review_queue([first, first, second], budget=4)
    assert len(queue) == len({c['case_id'] for c in queue}) == 4
    assert [c['source_id'] for c in queue] == ['dev', 'second', 'dev', 'second']
    assert all(c['human_label'] == 'UNKNOWN' for c in queue)


def test_successful_build_preserves_native_input_and_records_each_source(tmp_path, monkeypatch):
    import scripts.diagnostics.hud_failure_corpus as module
    rows = chain()
    source = {'video_id': rows[0]['source_id'], 'source_sha256': rows[0]['source_sha256']}
    monkeypatch.setattr(module, 'development_sources', lambda _: [source])
    monkeypatch.setattr(module, '_check_output_privacy', lambda _: None)
    calls = []
    monkeypatch.setattr(module, 'append_exposure', lambda *a, **k: calls.append(k['source_id']))
    p = tmp_path / 'input.json'
    p.write_text(json.dumps({'source_id': source['video_id'],
                             'source_sha256': source['source_sha256'], 'rows': rows}))
    before = p.read_bytes()
    report = build(tmp_path, [p], tmp_path/'output.json')
    assert p.read_bytes() == before and calls == [source['video_id']]
    status = report['corpora'][0]['lifecycle']['chains'][0]['status']
    assert status == 'DEVELOPMENT_LIFECYCLE_CANDIDATE'
    assert report['formal_events'] == [] and not report['qualification_created']
