"""Contract experiments for an offline candidate, not production Ability behavior."""

import cv2
import numpy as np
import pytest

from scripts.diagnose_ability_scaffold import candidate_score, learn_candidate


def fixture_candidate():
    regions = np.zeros((80, 240), np.uint8)
    regions[15:65, 10:110] = 1
    regions[15:65, 130:230] = 2
    image = np.full(regions.shape, 25, np.uint8)
    for x in [20, 140]:
        for y in [25, 40, 55]:
            cv2.line(image, (x, y), (x + 80, y), 220, 2)
    return image, regions, learn_candidate(np.stack([image] * 4), regions)


def test_excluded_pixels_cannot_define_or_destroy_identity():
    image, regions, candidate = fixture_candidate()
    assert candidate_score(image, candidate) >= 0.90
    changed = image.copy()
    changed[regions == 0] = np.random.default_rng(7).integers(
        0, 256, np.count_nonzero(regions == 0), dtype=np.uint8
    )
    assert candidate_score(changed, candidate) == candidate_score(image, candidate)
    changed[regions > 0] = 25
    assert candidate_score(changed, candidate) == 0


def test_every_independent_group_is_required():
    image, regions, candidate = fixture_candidate()
    for label in [1, 2]:
        missing = image.copy()
        missing[regions == label] = 25
        assert candidate_score(missing, candidate) == 0


def test_visible_wrong_shape_and_wrong_polarity_reject():
    image, regions, candidate = fixture_candidate()
    assert candidate_score(255 - image, candidate) < 0.90
    wrong = image.copy()
    wrong[regions == 1] = 25
    for x in [30, 60, 90]:
        cv2.line(wrong, (x, 20), (x, 60), 220, 2)
    assert candidate_score(wrong, candidate) < 0.90


def test_affine_brightness_change_retains_structure():
    image, _, candidate = fixture_candidate()
    changed = (image.astype(float) * 0.7 + 25).astype(np.uint8)
    assert candidate_score(changed, candidate) >= 0.90


def test_training_cannot_learn_absent_or_single_group_evidence():
    image, regions, _ = fixture_candidate()
    with pytest.raises(ValueError, match="population"):
        learn_candidate(np.full((4, *image.shape), 25, np.uint8), regions)
    regions[regions == 2] = 0
    with pytest.raises(ValueError, match="two to four"):
        learn_candidate(np.stack([image] * 4), regions)


def test_evaluation_geometry_must_match_training():
    image, _, candidate = fixture_candidate()
    with pytest.raises(ValueError, match="geometry"):
        candidate_score(image[:-1], candidate)
