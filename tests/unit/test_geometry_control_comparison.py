import json

import cv2
import numpy as np
import pytest
from test_geometry_blind_review import external_review  # noqa: F401

from scripts.diagnostics import compare_geometry_controls as subject
from scripts.diagnostics.prepare_geometry_review import prepare
from scripts.e2e.run_dataset_case import sha256_file


def test_counts_separate_positive_negative_unknown_and_unreviewed():
    rows = [
        {'labels': ['visible'] * 3, 'accepted': True},
        {'labels': ['visible'] * 3, 'accepted': False},
        {'labels': ['absent', 'visible', 'unknown'], 'accepted': False},
        {'labels': ['absent', 'visible', 'unknown'], 'accepted': True},
        {'labels': ['unknown'] * 3, 'accepted': True},
        {'labels': ['unreviewed'] * 3, 'accepted': True},
        {'labels': ['misaligned', 'visible', 'unknown'], 'accepted': True},
    ]
    assert subject.control_counts(rows) == {
        'positive_accepted': 1, 'positive_missing': 1, 'negative_rejected': 1,
        'negative_false_accept': 1, 'unknown_unscored': 1, 'unreviewed_unscored': 1,
        'misaligned_unscored': 1}


@pytest.mark.parametrize('row', [
    {'labels': ['visible'] * 2, 'accepted': True},
    {'labels': ['invented'] * 3, 'accepted': True},
    {'labels': ['visible'] * 3, 'accepted': None},
    {'labels': ['visible'] * 3, 'accepted': 1},
])
def test_counts_reject_incomplete_labels_or_inferred_decisions(row):
    with pytest.raises(ValueError):
        subject.control_counts([row])


@pytest.fixture
def reviewed(request):
    candidate, pool, partition, review = request.getfixturevalue('external_review')
    profile_path = candidate / 'hud_layout.templates.json'
    profile = json.loads(profile_path.read_text(encoding='utf-8'))
    profile['anchors'].pop('top_match_bar')
    for spec in profile['anchors'].values():
        spec['search_region'] = [0, 0, 1, 1]
    profile_path.write_text(json.dumps(profile), encoding='utf-8')
    fingerprint = candidate / 'candidate_fingerprint.json'
    frozen = json.loads(fingerprint.read_text(encoding='utf-8'))
    frozen[profile_path.name] = sha256_file(profile_path)
    fingerprint.write_text(json.dumps(frozen), encoding='utf-8')
    pool_path = pool / 'candidate_report.json'
    data = json.loads(pool_path.read_text(encoding='utf-8'))
    for i in range(2, 5):
        path = pool / f'validation_frames/frame{i}.jpg'
        assert cv2.imwrite(str(path), np.full((100, 160, 3), 10 + 10 * i, np.uint8))
        data['validation_frames'].append({'sha256': sha256_file(path),
                                          'source_frame_pts': i + 1.5})
    pool_path.write_text(json.dumps(data), encoding='utf-8')
    prepare(candidate, review, source_pool=pool, partition=partition)
    names = sorted(profile['anchors'])
    labels_path = review.parent / 'human_labels.json'
    labels_path.write_text(json.dumps({
        'kind': 'human_geometry_control_labels_not_identity_or_adoption',
        'review_sha256': sha256_file(review / 'review.json'),
        'review_html_sha256': sha256_file(review / 'index.html'),
        'trusted_reply_reference': 'synthetic_test_not_real_human_review',
        'production_adopted': False,
        'labels': {str(i): dict.fromkeys(names, label) for i, label in enumerate(
            ('absent', 'visible', 'unknown', 'unreviewed'), 1)},
    }), encoding='utf-8')
    return candidate, pool, review, labels_path, partition, review.parent / 'comparison.json'


def test_bound_review_comparison_is_local_and_never_adopts(reviewed):
    result = subject.compare(*reviewed)
    assert result['sample_count'] == result['unique_source_image_count'] == 4
    for matcher in ('raw', 'gradient'):
        assert result['counts'][matcher]['frames'] == {
            'positive_accepted': 0, 'positive_missing': 1, 'negative_rejected': 1,
            'negative_false_accept': 0, 'unknown_unscored': 1, 'unreviewed_unscored': 1,
            'misaligned_unscored': 0}
    assert result['production_adopted'] is False
    assert result['qualification_created'] is False
    assert result['identity_evidence_generated'] is False
    assert result['natural_negative_qualification_completed'] is False
    assert result['events_generated'] == 0
    assert result['human_authorship_requires_external_trusted_record'] is True
    assert 'source_frame_pts' not in json.dumps(result)
    assert str(reviewed[0].parent) not in json.dumps(result)
    with pytest.raises(FileExistsError):
        subject.compare(*reviewed)


def test_labels_never_select_images_or_enter_matcher(reviewed, monkeypatch):
    calls = []
    original = subject.edge_anchors

    def spy(image, layout, profile):
        calls.append(image.copy())
        return original(image, layout, profile)

    monkeypatch.setattr(subject, 'edge_anchors', spy)
    subject.compare(*reviewed)
    assert len(calls) == 4  # unknown and unreviewed are still measured
    labels_path = reviewed[3]
    labels = json.loads(labels_path.read_text(encoding='utf-8'))
    for row in labels['labels'].values():
        for name in row:
            row[name] = 'unknown'
    labels_path.write_text(json.dumps(labels), encoding='utf-8')
    subject.compare(*reviewed[:-1], reviewed[-1].with_name('different_labels.json'))
    assert len(calls) == 8
    assert all(np.array_equal(a, b) for a, b in zip(calls[:4], calls[4:], strict=True))


@pytest.mark.parametrize('change', [
    'review', 'page', 'labels_missing', 'anchor_missing', 'untrusted',
    'source_copy', 'guide', 'candidate', 'partition',
])
def test_review_drift_or_implicit_labels_rejected_before_matching(reviewed, change, monkeypatch):
    candidate, pool, review, labels_path, partition, output = reviewed
    if change in {'labels_missing', 'anchor_missing', 'untrusted'}:
        labels = json.loads(labels_path.read_text(encoding='utf-8'))
        if change == 'labels_missing':
            labels['labels'].pop('4')
        elif change == 'anchor_missing':
            labels['labels']['1'].pop('abilities')
        else:
            labels['trusted_reply_reference'] = ''
        labels_path.write_text(json.dumps(labels), encoding='utf-8')
    else:
        path = {
            'review': review / 'review.json', 'page': review / 'index.html',
            'source_copy': review / 'source_01.jpg', 'guide': review / 'guide_01.jpg',
            'candidate': candidate / 'round_timer.mask.png', 'partition': partition,
        }[change]
        path.write_bytes(path.read_bytes() + b'changed')

    def forbidden(*args):
        pytest.fail('invalid review must fail before matching')

    monkeypatch.setattr(subject, 'edge_anchors', forbidden)
    with pytest.raises(ValueError):
        subject.compare(*reviewed)
    assert not output.exists()


@pytest.mark.parametrize('change', ['holdout', 'source', 'overlap'])
def test_bound_but_ineligible_cohort_cannot_be_scored(reviewed, change, monkeypatch):
    candidate, pool, review, labels_path, partition, output = reviewed
    pool_path, review_path = pool / 'candidate_report.json', review / 'review.json'
    cohort = json.loads(pool_path.read_text(encoding='utf-8'))
    receipt = json.loads(review_path.read_text(encoding='utf-8'))
    if change == 'holdout':
        cohort['validation_frames'][0]['source_frame_pts'] = 10
        receipt['frames'][0]['source_frame_pts'] = 10
    elif change == 'source':
        cohort['source_sha256'] = 'b' * 64
    else:
        original = candidate / 'validation_frames/synthetic.jpg'
        (review / 'source_01.jpg').write_bytes(original.read_bytes())
        digest = sha256_file(original)
        cohort['validation_frames'][0]['sha256'] = digest
        receipt['frames'][0]['source_sha256'] = digest
    # Rebind this synthetic fixture so rejection tests eligibility, not merely
    # a stale hash. No real review/approval receipt is changed by this test.
    pool_path.write_text(json.dumps(cohort), encoding='utf-8')
    receipt['source_inventory_sha256'] = sha256_file(pool_path)
    review_path.write_text(json.dumps(receipt), encoding='utf-8')
    labels = json.loads(labels_path.read_text(encoding='utf-8'))
    labels['review_sha256'] = sha256_file(review_path)
    labels_path.write_text(json.dumps(labels), encoding='utf-8')

    def forbidden(*args):
        pytest.fail('ineligible source must not reach matcher')

    monkeypatch.setattr(subject, 'edge_anchors', forbidden)
    with pytest.raises(ValueError):
        subject.compare(*reviewed)
    assert not output.exists()
