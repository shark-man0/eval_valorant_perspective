"""Shared localization must preserve direct semantic evidence and contrast."""
import cv2
import numpy as np
import pytest

from scripts.diagnostics.probe_result_translation import locate
from tests.unit.test_semantic_text import _assets
from valorant_ai_coach.hud.semantic_text import SemanticTextReference


def reference():
    image, mask, regions, training = _assets()
    return SemanticTextReference(image, mask, regions, training, .90)


def test_one_shared_shift_recovers_all_groups_without_changing_threshold():
    ref = reference()
    h, w = ref.reference.shape
    image = np.zeros((h + 30, w + 40), np.uint8)
    image[13:13 + h, 19:19 + w] = ref.reference
    result = locate(ref, image)
    assert result['shared_xy'] == [19, 13]
    assert result['accepted'] and result['score'] == pytest.approx(1)
    assert result['threshold'] == .90
    assert result['runtime_transition_authorized'] is False


def test_independent_group_matches_cannot_be_mixed_into_a_shared_match():
    ref = reference()
    h, w = ref.reference.shape
    image = np.zeros((h * 4, w + 15), np.uint8)
    for index, mask in enumerate(ref.masks):
        patch = np.zeros_like(ref.reference)
        patch[mask > 0] = ref.reference[mask > 0]
        image[index * h:(index + 1) * h, :w] = patch
    result = locate(ref, image)
    assert all(s > .99 for s in result['per_group_independent_maxima_diagnostic_only'])
    assert not result['accepted']


def test_flat_and_corrupted_text_remain_unknown():
    ref = reference()
    h, w = ref.reference.shape
    assert not locate(ref, np.full((h + 20, w + 20), 240, np.uint8))['accepted']
    corrupted = ref.reference.copy()
    corrupted[ref.masks[1] > 0] = 255 - corrupted[ref.masks[1] > 0]
    assert not locate(ref, cv2.copyMakeBorder(corrupted, 10, 10, 10, 10,
                                            cv2.BORDER_CONSTANT))['accepted']


def test_incomplete_source_roi_is_rejected():
    ref = reference()
    with pytest.raises(ValueError, match='complete reference'):
        locate(ref, ref.reference[:2, :3])
