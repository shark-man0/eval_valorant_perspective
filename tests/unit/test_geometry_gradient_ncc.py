import json

import cv2
import numpy as np
import pytest
from test_geometry_candidate_challenge import fixture as candidate_fixture
from test_geometry_edge_experiment import changing_brightness

from scripts.diagnostics import diagnose_geometry_gradient_ncc as subject
from scripts.diagnostics.diagnose_geometry_gradient_ncc import gradient_match, gradients
from scripts.e2e.run_dataset_case import sha256_file


def fixture():
    reference = np.full((80, 100), 30, np.uint8)
    cv2.rectangle(reference, (15, 15), (85, 65), 240, 3)
    mask = np.zeros_like(reference)
    cv2.rectangle(mask, (15, 15), (85, 65), 255, 13)
    return reference, mask


def test_identical_structure_has_high_score_and_correct_location():
    reference, mask = fixture()
    search = np.pad(reference, ((4, 6), (7, 8)), constant_values=30)
    result = gradient_match(search, reference, mask)
    assert result['score'] >= .90
    assert result['location'] == (7, 4)


def test_contrast_change_preserves_directions_without_confidence_inflation():
    reference, mask = fixture()
    candidate = (reference.astype(np.float32) * .5 + 60).astype(np.uint8)
    result = gradient_match(candidate, reference, mask)
    assert result['score'] >= .90
    assert result['score'] <= 1


def test_excluded_content_cannot_enter_through_sobel_neighbourhood():
    reference, mask = fixture()
    candidate = reference.copy()
    candidate[mask == 0] = np.random.default_rng(42).integers(
        0, 256, np.count_nonzero(mask == 0), dtype=np.uint8)
    assert gradient_match(candidate, reference, mask)['score'] >= .99


def test_constant_reference_or_insufficient_eroded_mask_abstains():
    reference, mask = fixture()
    assert gradient_match(reference, np.full_like(reference, 100), mask) is None
    thin = np.zeros_like(mask)
    thin[20, 10:90] = 255
    assert gradient_match(reference, reference, thin) is None


def test_constant_noise_and_wrong_orientation_do_not_match():
    reference, mask = fixture()
    candidates = [np.full_like(reference, 100),
                  np.random.default_rng(42).integers(0, 256, reference.shape, dtype=np.uint8),
                  255 - reference]
    for candidate in candidates:
        assert gradient_match(candidate, reference, mask)['score'] < .90


def test_sobel_feature_is_signed_and_does_not_mutate_input():
    reference, _ = fixture()
    before = reference.copy()
    feature = gradients(reference)
    assert feature.shape == (*reference.shape, 2)
    assert feature.dtype == np.float32
    assert np.min(feature) < 0 < np.max(feature)
    assert np.array_equal(before, reference)


@pytest.mark.parametrize('bad', [np.zeros((10, 10, 3), np.uint8),
                                np.zeros((10, 10), np.float32)])
def test_invalid_feature_inputs_rejected(bad):
    with pytest.raises(ValueError):
        gradients(bad)



@pytest.fixture
def candidate(tmp_path):
    root = candidate_fixture(tmp_path / 'candidate')
    (root / 'validation_frames' / 'synthetic.jpg').unlink()
    profile = json.loads((root / 'hud_layout.templates.json').read_text(encoding='utf-8'))
    for spec in profile['anchors'].values():
        spec['search_region'] = [0, 0, 1, 1]
    (root / 'hud_layout.templates.json').write_text(json.dumps(profile), encoding='utf-8')
    report = {'source_sha256': 'a' * 64, 'candidate_assets_frozen_before_validation': True,
              'production_adopted': False, 'identity_assets_generated': False,
              'anchors': {name: {
                  f'{field}_sha256': sha256_file(root / spec[field])
                  for field in ('template', 'mask')}
                  for name, spec in profile['anchors'].items()}}
    for split, samples in (('training', [0, 1, 2]), ('validation', [3, 4, 4])):
        folder = root / f'{split}_frames'
        folder.mkdir(exist_ok=True)
        rows = []
        for i, index in enumerate(samples):
            path = folder / f'frame_{i:02d}.jpg'
            assert cv2.imwrite(str(path), changing_brightness()[index])
            rows.append({'source_frame_pts': i + (1 if split == 'training' else 10),
                         'sha256': sha256_file(path)})
        report[f'{split}_frames'] = rows
    (root / 'candidate_report.json').write_text(json.dumps(report), encoding='utf-8')
    partition = tmp_path / 'partition.json'
    partition.write_text(json.dumps({
        'kind': 'development_holdout_partition_not_gt', 'source_video_sha256': 'a' * 64,
        'development': {'start_sec_inclusive': 0, 'end_sec_exclusive': 20},
        'holdout': {'start_sec_inclusive': 20, 'end_sec_exclusive': 100},
    }), encoding='utf-8')
    return root, partition, tmp_path / 'measurement'


def test_experiment_freezes_before_measurement_and_preserves_duplicates(candidate):
    root, partition, output = candidate
    subject.run(root, partition, output)
    plan = json.loads((output / 'frozen_experiment.json').read_text(encoding='utf-8'))
    report = json.loads((output / 'measurement.json').read_text(encoding='utf-8'))
    assert plan['source_frame_count'] == 6 and plan['unique_source_image_count'] == 5
    assert plan['algorithm']['ncc_threshold'] == .90
    assert len([r for r in report['rows'] if r['split'] == 'validation']) == 3
    assert report['production_registered'] is False
    assert report['qualification_created'] is False
    assert report['natural_negative_qualification_completed'] is False
    with pytest.raises(FileExistsError):
        subject.run(root, partition, output)


@pytest.mark.parametrize('change', ['holdout', 'overlap', 'asset'])
def test_invalid_source_or_reference_fails_before_experiment(candidate, change):
    root, partition, output = candidate
    report_path = root / 'candidate_report.json'
    report = json.loads(report_path.read_text(encoding='utf-8'))
    if change == 'holdout':
        report['validation_frames'][0]['source_frame_pts'] = 20
    elif change == 'overlap':
        path = root / 'validation_frames/frame_00.jpg'
        path.write_bytes((root / 'training_frames/frame_00.jpg').read_bytes())
        report['validation_frames'][0]['sha256'] = sha256_file(path)
    else:
        report['anchors'][next(iter(report['anchors']))]['mask_sha256'] = 'b' * 64
    report_path.write_text(json.dumps(report), encoding='utf-8')
    with pytest.raises(ValueError):
        subject.run(root, partition, output)
    assert not output.exists()


def diagnostic_row(digest='a', removed=None, **scores):
    return {
        'split': 'validation' if removed is None else 'transformed_control',
        'source_image_sha256': digest, 'removed_anchor': removed,
        'raw_fresh_geometry': False, 'gradient_fresh_geometry': False,
        'gradient_scores': {name: None if value is None else {'score': value}
                            for name, value in scores.items()},
    }


def test_anchor_summary_separates_missing_low_score_and_duplicate_cases():
    row = diagnostic_row(timer=.89, hp=.90, abilities=None)
    summary = subject.summarize_anchor_scores([row, row.copy()], ['timer', 'hp', 'abilities'])
    frames = summary['validation']['frames']
    assert frames['case_count'] == 2
    assert summary['validation']['unique_cases']['case_count'] == 1
    assert frames['anchors']['timer']['below_threshold'] == 2
    assert frames['anchors']['hp']['accepted'] == 2
    assert frames['anchors']['abilities']['unscorable'] == 2
    assert frames['anchors']['abilities']['score_median'] is None
    assert frames['failed_anchor_combinations'] == [
        {'anchors': ['abilities', 'timer'], 'count': 2}]
    # Neither source identifiers nor detailed arrays leak into the aggregate.
    assert 'source_image_sha256' not in json.dumps(summary)
    assert summary['training']['frames']['case_count'] == 0


def test_anchor_summary_distinguishes_controls_and_geometry_gate():
    rows = [diagnostic_row(removed=name, timer=.91, hp=.95, abilities=.99)
            for name in ('timer', 'hp')]
    summary = subject.summarize_anchor_scores(rows, ['timer', 'hp', 'abilities'])
    unique = summary['transformed_control']['unique_cases']
    assert unique['case_count'] == 2
    assert unique['all_scores_accepted_but_geometry_rejected'] == 2
    assert unique['anchors']['hp']['score_median'] == .95


@pytest.mark.parametrize('value', [float('nan'), float('inf'), -.1, 1.1, True])
def test_anchor_summary_rejects_invalid_scores(value):
    with pytest.raises(ValueError, match='finite bounded'):
        subject.summarize_anchor_scores([diagnostic_row(timer=value)], ['timer'])


def test_anchor_summary_rejects_inconsistent_duplicates_and_missing_anchors():
    row = diagnostic_row(timer=.8)
    with pytest.raises(ValueError, match='inconsistent duplicate'):
        subject.summarize_anchor_scores([row, diagnostic_row(timer=.95)], ['timer'])
    with pytest.raises(ValueError, match='complete fixed anchor'):
        subject.summarize_anchor_scores([row], ['timer', 'hp'])
