import cv2
import numpy as np
import pytest

from valorant_ai_coach.visual.development_annulus_pool import AnnulusValidatedAppearancePool
from valorant_ai_coach.visual.development_appearance_pool import ContrastiveAppearancePool
from valorant_ai_coach.visual.development_map import DevelopmentMapTimeline


def example(tmp_path, ring):
    rng = np.random.default_rng(21)
    patch = rng.integers(0, 256, (17, 17, 3), np.uint8)
    yy, xx = np.indices((17, 17))
    radius = np.hypot(xx-8, yy-8)
    annulus = (radius >= 17*.35) & (radius <= 17*.53)
    patch[annulus] = (20, 220, 230) if ring else (210, 210, 210)
    positive, negative = tmp_path/'p.png', tmp_path/'n.png'
    cv2.imwrite(str(positive), patch)
    cv2.imwrite(str(negative), rng.integers(0, 256, patch.shape, np.uint8))
    crop = np.zeros((90, 110, 3), np.uint8)
    crop[30:47, 40:57] = patch
    spec = {'mode': 'appearance_pool_annulus_v1', 'libraries': [{
        'source_id': 'author', 'role': 'appearance_contrast_only',
        'matcher': {'mode': 'portrait_v2', 'positive_templates': [str(positive)],
                    'negative_templates': [str(negative)]}}]}
    return crop, spec


def test_matching_core_without_annulus_cannot_be_a_selected_primary_candidate(tmp_path):
    crop, spec = example(tmp_path, False)
    old = ContrastiveAppearancePool().observe(
        crop, 1., {**spec, 'mode': 'appearance_pool_v1'}, ownership_eligible=True)
    assert old.x_roi_norm is not None
    tracker = AnnulusValidatedAppearancePool()
    result = tracker.observe(crop, 1., spec, ownership_eligible=True)
    assert result.x_roi_norm is None and result.reason == 'primary_annulus_not_supported'
    assert tracker.last_evidence['rejected_appearance']['x_roi_norm'] == old.x_roi_norm
    assert tracker.last_evidence['semantic_recorder_link'] is False


def test_ring_support_is_appearance_only_and_not_ownership(tmp_path):
    crop, spec = example(tmp_path, True)
    tracker = AnnulusValidatedAppearancePool()
    result = tracker.observe(crop, 1., spec, ownership_eligible=True)
    assert result.x_roi_norm is not None and result.identity == 'UNKNOWN'
    assert result.qualification == 'development_only'
    baseline = ContrastiveAppearancePool()
    baseline.observe(crop, 1., {**spec, 'mode': 'appearance_pool_v1'}, ownership_eligible=True)
    assert tracker.reference_fingerprint != baseline.reference_fingerprint
    assert tracker.observe(crop, 1.2, spec, ownership_eligible=False).x_roi_norm is None


def test_bad_mode_cannot_reuse_previous_accepted_observation(tmp_path):
    crop, spec = example(tmp_path, True)
    tracker = AnnulusValidatedAppearancePool()
    assert tracker.observe(crop, 1., spec, ownership_eligible=True).x_roi_norm is not None
    assert tracker.observe(crop, 1.2, {}, ownership_eligible=True).x_roi_norm is None
    assert tracker.reference_fingerprint is None


def test_timeline_factory_requires_explicit_unassigned_scope(tmp_path):
    _, spec = example(tmp_path, True)
    profile = {'reference_identity_confirmed': False, 'minimap_self_marker': spec,
               'map_zone': {'manual_map_id': 'bind'}}
    with pytest.raises(ValueError, match='unassigned coordinate scope'):
        DevelopmentMapTimeline(profile)
    timeline = DevelopmentMapTimeline(profile, coordinate_scope='unassigned_visual_candidate')
    assert isinstance(timeline.marker, AnnulusValidatedAppearancePool)
