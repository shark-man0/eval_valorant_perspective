import copy

import cv2
import numpy as np
import pytest

from valorant_ai_coach.visual.development_portrait_bank import PortablePortraitTracker


def example(tmp_path):
    rng = np.random.default_rng(470)
    patch = rng.integers(35, 210, (17, 17), np.uint8)
    patch = cv2.cvtColor(patch, cv2.COLOR_GRAY2BGR)
    yy, xx = np.indices((17, 17))
    radius = np.hypot(xx-8, yy-8)
    patch[(radius >= 6) & (radius <= 9)] = [120, 230, 230]
    alternative = rng.integers(25, 220, (17, 17, 3), np.uint8)
    refs = []
    for index, image in enumerate([patch, alternative]):
        path = tmp_path/f'portrait{index}.png'
        cv2.imwrite(str(path), image)
        refs.append({'path': str(path), 'source_id': 'author',
                     'role': 'portrait_appearance_only'})
    spec = {'mode': 'portable_portrait_v1', 'templates': refs}
    frame = np.zeros((110, 140, 3), np.uint8)
    frame[35:52, 45:62] = patch
    return frame, patch, spec


@pytest.mark.parametrize('mode', ['bgr_v1', 'gray_v1', 'gray_shared_v2'])
def test_portrait_ring_texture_candidate_never_supplies_recorder_ownership(tmp_path, mode):
    frame, _, spec = example(tmp_path)
    spec['feature_mode'] = mode
    tracker = PortablePortraitTracker()
    result = tracker.observe(frame, 1., spec, ownership_eligible=True)
    assert result.x_roi_norm == pytest.approx(53/140)
    assert result.y_roi_norm == pytest.approx(43/110)
    assert result.identity == 'UNKNOWN' and result.qualification == 'development_only'
    assert tracker.last_evidence['semantic_recorder_link'] is False
    assert tracker.observe(frame, 1.2, spec, ownership_eligible=False).reason == 'ownership_blocked'


def test_shared_image_statistics_agree_with_masked_ncc_on_textured_pixels(tmp_path):
    frame, patch, spec = example(tmp_path)
    tracker = PortablePortraitTracker()
    tracker.observe(frame, 1., spec, ownership_eligible=True)
    rng = np.random.default_rng(91)
    target = rng.integers(0, 256, (110, 140), np.uint8)
    target[35:52, 45:62] = cv2.cvtColor(patch, cv2.COLOR_BGR2GRAY)
    templates = [cv2.cvtColor(cv2.imread(r['path']), cv2.COLOR_BGR2GRAY)
                 for r in spec['templates']]
    expected = np.maximum.reduce([tracker._scores(target, t) for t in templates])
    measured = tracker._shared_gray_scores(target, templates)
    np.testing.assert_allclose(measured, expected, atol=2e-5)
    assert cv2.minMaxLoc(measured)[3] == cv2.minMaxLoc(expected)[3]
    for mode in ['gray_v1', 'gray_shared_v2']:
        spec['feature_mode'] = mode
        assert tracker.observe(
            np.zeros_like(frame), 2., spec, ownership_eligible=True).x_roi_norm is None


def test_similar_teammate_portrait_and_color_alone_cannot_supply_position(tmp_path):
    frame, patch, spec = example(tmp_path)
    yy, xx = np.indices((17, 17))
    radius = np.hypot(xx-8, yy-8)
    patch[(radius >= 6) & (radius <= 9)] = [190, 230, 70]
    frame[35:52, 45:62] = patch
    result = PortablePortraitTracker().observe(frame, 1., spec, ownership_eligible=True)
    assert result.x_roi_norm is None
    patch[:] = [120, 230, 230]
    frame[35:52, 45:62] = patch
    assert PortablePortraitTracker().observe(
        frame, 1., spec, ownership_eligible=True).x_roi_norm is None


def test_multiple_supported_portraits_are_not_selected_by_tracking(tmp_path):
    frame, patch, spec = example(tmp_path)
    tracker = PortablePortraitTracker()
    assert tracker.observe(frame, 1., spec, ownership_eligible=True).x_roi_norm is not None
    frame[70:87, 95:112] = patch
    result = tracker.observe(frame, 1.2, spec, ownership_eligible=True)
    assert result.reason == 'portable_portrait_ambiguous'
    assert result.candidate_count == 2 and result.x_roi_norm is None


@pytest.mark.parametrize('count', [13, 29, 38, 48])
def test_bounded_catalog_spans_loader_groups_without_losing_digest_or_geometry(tmp_path, count):
    frame, _, spec = example(tmp_path)
    spec['templates'] = [copy.deepcopy(spec['templates'][i % 2]) for i in range(count)]
    tracker = PortablePortraitTracker()
    assert tracker.observe(frame, 1., spec, ownership_eligible=True).x_roi_norm is not None
    assert tracker.last_evidence['reference_count'] == count
    spec['templates'][-1]['image_sha256'] = '0'*64
    assert tracker.observe(frame, 1.2, spec, ownership_eligible=True).reason == (
        'portable_reference_digest_mismatch')
    assert tracker.reference_fingerprint is None
    spec['templates'] += [spec['templates'][0]]*49
    assert tracker.observe(frame, 1.4, spec, ownership_eligible=True).reason == (
        'invalid_portable_reference_profile')


def test_reference_content_replacement_deletion_and_source_exclusion(tmp_path):
    frame, patch, spec = example(tmp_path)
    tracker = PortablePortraitTracker()
    first = tracker.observe(frame, 1., spec, ownership_eligible=True)
    fingerprint = tracker.reference_fingerprint
    patch[0, 0] ^= 1
    cv2.imwrite(spec['templates'][0]['path'], patch)
    second = tracker.observe(frame, 1.2, spec, ownership_eligible=True)
    assert tracker.reference_fingerprint != fingerprint
    assert second.track_id != first.track_id
    (tmp_path/'portrait0.png').unlink()
    assert tracker.observe(frame, 1.4, spec, ownership_eligible=True).x_roi_norm is None
    assert tracker.reference_fingerprint is None
    excluded = PortablePortraitTracker(excluded_source_id='author')
    assert excluded.observe(frame, 1., spec, ownership_eligible=True).reason == (
        'portable_reference_vocabulary_unavailable')


@pytest.mark.parametrize('change', ['identity_role', 'feature_type', 'nonfinite_extra', 'time'])
def test_invalid_profile_is_unknown_without_reusing_old_result(tmp_path, change):
    frame, _, spec = example(tmp_path)
    tracker = PortablePortraitTracker()
    tracker.observe(frame, 1., spec, ownership_eligible=True)
    spec = copy.deepcopy(spec)
    time = 1.2
    if change == 'identity_role':
        spec['templates'][0]['role'] = 'SELF'
    elif change == 'feature_type':
        spec['feature_mode'] = []
    elif change == 'nonfinite_extra':
        spec['extra'] = float('nan')
    else:
        time = float('nan')
    assert tracker.observe(frame, time, spec, ownership_eligible=True).x_roi_norm is None
