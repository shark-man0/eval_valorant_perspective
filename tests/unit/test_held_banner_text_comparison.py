import json

import pytest

from scripts.diagnostics import compare_held_banner_text as subject
from scripts.diagnostics.compare_held_banner_text import counts, family
from scripts.e2e.run_dataset_case import sha256_file


def measurement(present):
    return {'score': .96 if present else .50, 'threshold': .90,
            'presence': True if present else None}


def test_positive_negative_and_unknown_labels_do_not_create_absence_or_events():
    result = counts('WON', ['WON 敵チーム全滅', 'LOST チーム全滅', 'unknown', 'absent'],
                    [measurement(True), measurement(False), measurement(True), measurement(True)])
    assert result == {'positive_correct': 1, 'positive_missing': 0, 'negative_rejected': 1,
                      'negative_false_accept': 1, 'unknown_unscored': 1}


def test_miss_and_wrong_family_accept_remain_visible():
    result = counts('LOST', ['LOST', 'WON'], [measurement(False), measurement(True)])
    assert result['positive_missing'] == 1
    assert result['negative_false_accept'] == 1


@pytest.mark.parametrize('change', [{'score': float('nan')}, {'threshold': .89},
                                  {'presence': 'true'}, {'presence': False}])
def test_changed_floor_invalid_score_or_presence_inconsistency_rejected(change):
    row = {**measurement(True), **change}
    with pytest.raises(ValueError):
        counts('WON', ['WON'], [row])


def test_unrecognized_text_is_not_silently_labelled_negative():
    with pytest.raises(ValueError):
        family('購入フェーズ')


@pytest.fixture
def bound_files(tmp_path, monkeypatch):
    page, crop = tmp_path / 'index.html', tmp_path / 'frame_01.png'
    page.write_text('synthetic blind page', encoding='utf-8')
    crop.write_bytes(b'synthetic ROI binding only, not real-video pixels')
    review_path, labels_path = tmp_path / 'review.json', tmp_path / 'labels.json'
    measurement_path, references_path = tmp_path / 'measurement.json', tmp_path / 'references.json'
    review = {'source_video_sha256': 'a' * 64, 'review_html_sha256': sha256_file(page),
              'frames': [{'frame_number': 1, 'held_index': 0,
                          'source_image_sha256': 'b' * 64, 'roi_sha256': sha256_file(crop)}]}
    measured = {'kind': 'frozen_banner_measurement_not_qualification',
                'candidates_reselected': False, 'source_sha256': 'a' * 64,
                'held_hashes': ['b' * 64], 'candidates': [{
                    'candidate_id': 'first', 'held_measurements': [measurement(True)]}]}
    references = {'source_video_sha256': 'a' * 64, 'transcriptions': {'first': 'WON'}}
    for path, value in ((review_path, review), (measurement_path, measured),
                        (references_path, references)):
        path.write_text(json.dumps(value), encoding='utf-8')
    labels = {'kind': 'human_held_banner_transcription_not_boundary_or_adoption',
              'review_sha256': sha256_file(review_path),
              'measurement_sha256': sha256_file(measurement_path),
              'reference_transcription_sha256': sha256_file(references_path),
              'trusted_reply_reference': 'synthetic-not-human-qualification',
              'production_adopted': False, 'source_video_sha256': 'a' * 64,
              'review_html_sha256': sha256_file(page), 'transcriptions': {'1': 'WON'}}
    labels_path.write_text(json.dumps(labels), encoding='utf-8')
    monkeypatch.setattr(subject, '_check_output_privacy', lambda _: None)
    return review_path, labels_path, measurement_path, references_path, tmp_path / 'result.json'


def test_compare_is_read_only_and_produces_only_aggregates(bound_files):
    before = {path: path.read_bytes() for path in bound_files[:4]}
    result = subject.compare(*bound_files)
    assert result['candidates'][0]['positive_correct'] == 1
    assert result['candidate_reselection'] is False
    assert result['events_generated'] == 0
    assert result['qualification_created'] is False
    assert 'transcriptions' not in result and 'frames' not in result
    assert all(path.read_bytes() == raw for path, raw in before.items())
    with pytest.raises(FileExistsError):
        subject.compare(*bound_files)


@pytest.mark.parametrize('changed', ['review', 'measurement', 'reference', 'page', 'crop'])
def test_changed_bindings_cannot_be_compared(bound_files, changed):
    review, _, measurement_path, references, output = bound_files
    path = {'review': review, 'measurement': measurement_path, 'reference': references,
            'page': review.parent / 'index.html', 'crop': review.parent / 'frame_01.png'}[changed]
    path.write_bytes(path.read_bytes() + b' ')
    with pytest.raises(ValueError):
        subject.compare(*bound_files)
    assert not output.exists()
