"""Synthetic isolation/control tests, not real-image subject qualification."""
import hashlib
from dataclasses import replace

import numpy as np
import pytest

from valorant_ai_coach.experimental.scoreboard_subject import (
    ScoreboardProfile,
    ScoreboardSubjectProbe,
)
from valorant_ai_coach.experimental.subject_death import (
    ReviewStatus,
    SourceBinding,
    SubjectRelation,
    SubjectRole,
)
from valorant_ai_coach.hud.readers import ReaderResult

HASH = 'a' * 64


class NameReader:
    def __init__(self, value='observed-name', confidence=.96):
        self.value = value
        self.confidence = confidence
        self.calls = 0

    def read(self, image, roi):
        self.calls += 1
        return ReaderResult(self.value, self.confidence)


def fixture():
    reference = np.random.default_rng(0).integers(0, 256, (20, 40), dtype=np.uint8)
    masks = [np.zeros_like(reference) for _ in range(3)]
    masks[0][:3, :] = 255
    masks[1][-3:, :] = 255
    masks[2][4:16, :3] = 255
    profile = ScoreboardProfile(HASH, HASH, (70, 60), (5, 2, 68), reference,
                                tuple(masks), (8, 5, 35, 15))
    image = np.zeros((70, 60), dtype=np.uint8)
    image[10:30, 5:45] = reference
    reader = NameReader()
    probe = ScoreboardSubjectProbe(profile, reader, runtime_fingerprint=HASH)
    return probe, reader, image


def source(probe, image, **changes):
    return replace(SourceBinding(
        HASH, 1, 1, 60, 'segment-0', hashlib.sha256(image.tobytes()).hexdigest(),
        probe.code_fingerprint, probe.profile.fingerprint(), HASH,
    ), **changes)


def test_three_supports_and_name_stay_unqualified_and_unknown():
    probe, reader, image = fixture()
    result = probe.read(image, source(probe, image))
    assert result.row_top == 10 and reader.calls == 1
    assert min(result.support_scores) == pytest.approx(1)
    observation = result.observation
    assert observation is not None
    assert observation.source == source(probe, image)
    assert observation.role == SubjectRole.SOURCE_PLAYER_BINDING
    assert observation.relation == SubjectRelation.UNKNOWN
    assert observation.review_status == ReviewStatus.CANDIDATE
    assert observation.confidence <= reader.confidence
    assert observation.subject_token == hashlib.sha256(b'observed-name').hexdigest()


def test_name_pixels_do_not_contribute_to_structural_support():
    probe, _, image = fixture()
    before = probe.read(image, source(probe, image))
    image[15:25, 13:40] = 0
    after = probe.read(image, source(probe, image))
    assert after.support_scores == before.support_scores
    assert after.observation is not None


@pytest.mark.parametrize('mask_index', range(3))
def test_each_independent_support_is_required_before_ocr(mask_index):
    probe, reader, image = fixture()
    region = image[10:30, 5:45]
    region[probe.profile.masks[mask_index] > 0] = 0
    result = probe.read(image, source(probe, image))
    assert result.observation is None and reader.calls == 0


def test_two_marked_rows_are_ambiguous_not_arbitrarily_selected():
    probe, reader, image = fixture()
    image[40:60, 5:45] = probe.profile.reference
    result = probe.read(image, source(probe, image))
    assert result.reason == 'ambiguous_marked_rows' and reader.calls == 0


@pytest.mark.parametrize('confidence', [.89, float('nan'), float('inf'), -1, 1.1,
                                         True, '0.99', None])
def test_invalid_or_low_name_confidence_is_rejected(confidence):
    probe, reader, image = fixture()
    reader.confidence = confidence
    result = probe.read(image, source(probe, image))
    assert result.reason == 'name_not_accepted' and result.observation is None


@pytest.mark.parametrize('value', [None, '', '   ', False, 0])
def test_missing_name_remains_unknown(value):
    probe, reader, image = fixture()
    reader.value = value
    assert probe.read(image, source(probe, image)).observation is None


@pytest.mark.parametrize('field', ['video_sha256', 'pixel_sha256',
                                    'code_fingerprint', 'profile_fingerprint'])
def test_source_binding_mismatch_cannot_supply_observation(field):
    probe, reader, image = fixture()
    result = probe.read(image, source(probe, image, **{field: 'b'*64}))
    assert result.reason == 'source_or_profile_mismatch' and reader.calls == 0


def test_resolution_is_source_bound():
    probe, reader, image = fixture()
    assert probe.read(image[:-1], source(probe, image)).observation is None
    assert reader.calls == 0


def test_profile_rejects_overlap_and_name_support():
    probe, _, _ = fixture()
    profile = probe.profile
    with pytest.raises(ValueError, match='independent'):
        replace(profile, masks=(profile.masks[0], profile.masks[0], profile.masks[2]))
    with pytest.raises(ValueError, match='exclude name'):
        replace(profile, name_roi=(0, 0, 10, 10))
