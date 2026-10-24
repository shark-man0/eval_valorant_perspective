import copy

import cv2
import numpy as np
import pytest

from valorant_ai_coach.visual.development_appearance_pool import ContrastiveAppearancePool


def example(tmp_path):
    rng = np.random.default_rng(921)
    patches = [rng.integers(0, 256, (17, 17, 3), np.uint8) for _ in range(4)]
    paths = []
    for i, patch in enumerate(patches):
        path = tmp_path/f'{i}.png'
        cv2.imwrite(str(path), patch)
        paths.append(str(path))
    libraries = [{'source_id': f'author{i}', 'role': 'appearance_contrast_only',
                  'matcher': {'mode': 'appearance_v1', 'positive_templates': [paths[i*2]],
                              'negative_templates': [paths[i*2+1]]}} for i in range(2)]
    crop = np.zeros((110, 140, 3), np.uint8)
    crop[30:47, 40:57] = patches[0]
    return crop, patches, {'mode': 'appearance_pool_v1', 'libraries': libraries}


def test_automatic_library_selection_is_candidate_appearance_only(tmp_path):
    crop, patches, spec = example(tmp_path)
    pool = ContrastiveAppearancePool()
    first = pool.observe(crop, 1., spec, ownership_eligible=True)
    assert first.x_roi_norm == pytest.approx(48/140)
    assert first.identity == 'UNKNOWN' and first.qualification == 'development_only'
    assert pool.last_evidence['semantic_recorder_link'] is False
    crop[30:47, 40:57] = patches[2]
    second = pool.observe(crop, 1.2, spec, ownership_eligible=True)
    assert second.x_roi_norm is not None and second.track_id != first.track_id


def test_ambiguous_library_blocks_another_single_candidate(tmp_path):
    crop, patches, spec = example(tmp_path)
    crop[60:77, 90:107] = patches[0]
    crop[10:27, 90:107] = patches[2]
    result = ContrastiveAppearancePool().observe(crop, 1., spec, ownership_eligible=True)
    assert result.reason == 'appearance_pool_ambiguous' and result.x_roi_norm is None


def test_reference_replacement_deletion_and_source_exclusion(tmp_path):
    crop, patches, spec = example(tmp_path)
    pool = ContrastiveAppearancePool()
    first = pool.observe(crop, 1., spec, ownership_eligible=True)
    fingerprint = pool.reference_fingerprint
    patches[0][0, 0] ^= 1
    cv2.imwrite(spec['libraries'][0]['matcher']['positive_templates'][0], patches[0])
    second = pool.observe(crop, 1.2, spec, ownership_eligible=True)
    assert pool.reference_fingerprint != fingerprint and second.track_id != first.track_id
    (tmp_path/'0.png').unlink()
    assert pool.observe(crop, 1.4, spec, ownership_eligible=True).reason == (
        'invalid_appearance_pool')
    assert pool.reference_fingerprint is None
    excluded = ContrastiveAppearancePool(excluded_source_id='author0')
    assert excluded.observe(crop, 1., spec, ownership_eligible=True).x_roi_norm is None


@pytest.mark.parametrize('change', ['negative', 'role', 'nan', 'count', 'time'])
def test_invalid_input_and_unusable_controls_fail_closed(tmp_path, change):
    crop, _, spec = example(tmp_path)
    spec = copy.deepcopy(spec)
    time = 1.
    if change == 'negative':
        spec['libraries'][0]['matcher']['negative_templates'] = []
    elif change == 'role':
        spec['libraries'][0]['role'] = 'SELF'
    elif change == 'nan':
        spec['unrecognized_option'] = float('nan')
    elif change == 'count':
        spec['libraries'] *= 3
    else:
        time = float('nan')
    pool = ContrastiveAppearancePool()
    assert pool.observe(crop, time, spec, ownership_eligible=True).x_roi_norm is None
    assert pool.observe(crop, 1., spec, ownership_eligible=False).reason == 'ownership_blocked'
