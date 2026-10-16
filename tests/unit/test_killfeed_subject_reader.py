"""Synthetic geometry/abstention controls, never real source qualification."""
import hashlib
from dataclasses import replace

import cv2
import numpy as np
import pytest

from valorant_ai_coach.experimental.killfeed_subject import (
    KillfeedSubjectProfile,
    KillfeedSubjectReader,
)
from valorant_ai_coach.experimental.subject_death import SourceBinding
from valorant_ai_coach.hud.readers import ReaderResult

HASH = 'a'*64


class NameReader:
    value = 'observed-name'
    confidence = .96

    def read(self, image, roi):
        return ReaderResult(self.value, self.confidence)


def fixture(*, killer=False):
    rng = np.random.default_rng(7)
    marker = np.zeros((20, 30, 3), np.uint8)
    masks = [np.zeros((20, 30), np.uint8) for _ in range(3)]
    masks[0][:3, :] = 255
    masks[1][-3:, :] = 255
    masks[2][3:-3, :3] = masks[2][3:-3, -3:] = 255
    occupied = np.any(np.stack(masks) > 0, axis=0)
    gold = occupied & (rng.random((20, 30)) > .4)
    marker[gold] = (30, 210, 240)
    ref = gold.astype(np.uint8)*255
    weapon = rng.integers(20, 220, (16, 24), dtype=np.uint8)
    head = rng.integers(20, 220, (12, 12), dtype=np.uint8)
    profile = KillfeedSubjectProfile(HASH, HASH, (80, 240), (0, 0, 240, 80),
                                     ref, tuple(masks), gold.astype(np.uint8)*255,
                                     weapon, head, (3, 17))
    image = np.zeros((80, 240, 3), np.uint8)
    x = 20 if killer else 180
    image[20:40, x:x+30] = np.fliplr(marker) if killer else marker
    image[22:38, 100:124] = np.repeat(weapon[:, :, None], 3, axis=2)
    ocr = NameReader()
    reader = KillfeedSubjectReader(profile, ocr, runtime_fingerprint=HASH)
    return reader, ocr, image


def source(reader, image, **changes):
    return replace(SourceBinding(HASH, 1, 1, 60, 'source-segment',
        hashlib.sha256(image.tobytes()).hexdigest(), reader.code_fingerprint,
        reader.profile.fingerprint(), HASH), **changes)


@pytest.mark.parametrize('killer', [False, True])
def test_role_comes_from_independent_weapon_side_and_retains_source(killer):
    reader, _, image = fixture(killer=killer)
    readings = reader.read(image, source(reader, image))
    assert len(readings) == 1
    row = readings[0]
    assert row.role == ('killer' if killer else 'victim')
    assert row.source == source(reader, image)
    assert row.name_text == 'observed-name' and row.name_confidence == .96
    assert min(row.marker_support) >= .90 and row.yellow_fraction == 1
    assert row.weapon_support >= .90
    assert row.qualified is False and row.formal_events == ()
    assert row.name_roi[0] < row.name_roi[2]


def test_missing_separator_retains_marker_but_never_assigns_victim():
    reader, _, image = fixture()
    image[22:38, 100:124] = 0
    rows = reader.read(image, source(reader, image))
    assert len(rows) == 1 and rows[0].role == 'unknown'
    assert rows[0].reason == 'weapon_separator_unavailable'
    assert rows[0].name_text is None


def test_weapons_on_both_sides_are_ambiguous():
    reader, _, image = fixture()
    image[22:38, 214:238] = np.repeat(reader.profile.weapon_reference[:, :, None], 3, axis=2)
    assert reader.read(image, source(reader, image))[0].role == 'unknown'


def test_matching_gray_border_without_yellow_cannot_claim_source_player():
    reader, _, image = fixture()
    gray = cv2.cvtColor(image[20:40, 180:210], cv2.COLOR_BGR2GRAY)
    image[20:40, 180:210] = np.repeat(gray[:, :, None], 3, axis=2)
    assert reader.read(image, source(reader, image)) == ()


@pytest.mark.parametrize('confidence', [.89, True, None, '0.99', float('nan'), float('inf'), 1.1])
def test_bad_name_support_does_not_destroy_independently_observed_marker(confidence):
    reader, ocr, image = fixture()
    ocr.confidence = confidence
    row = reader.read(image, source(reader, image))[0]
    assert row.role == 'victim' and row.name_text is None and row.name_confidence is None
    assert row.qualified is False


def test_partial_name_at_crop_edge_abstains_even_with_high_ocr_confidence():
    reader, _, image = fixture()
    first = reader.read(image, source(reader, image))[0]
    x1, y1, _, y2 = first.name_roi
    image[y1:y2, x1] = 255
    row = reader.read(image, source(reader, image))[0]
    assert row.role == 'victim' and row.name_text is None


def test_normalization_keeps_original_reading():
    reader, ocr, image = fixture()
    ocr.value = ' Ａlice '
    row = reader.read(image, source(reader, image))[0]
    assert row.name_text == ' Ａlice ' and row.normalized_name == 'Alice'


@pytest.mark.parametrize('field', ['pixel_sha256', 'video_sha256',
                                   'profile_fingerprint', 'code_fingerprint'])
def test_wrong_source_or_code_cannot_be_read(field):
    reader, _, image = fixture()
    assert reader.read(image, source(reader, image, **{field: 'b'*64})) == ()


def test_marker_absent_does_not_claim_source_player_even_if_weapon_is_present():
    reader, _, image = fixture()
    image[20:40, 180:210] = 0
    assert reader.read(image, source(reader, image)) == ()


def test_portrait_interior_does_not_supply_the_marker_structure():
    reader, _, image = fixture()
    before = reader.read(image, source(reader, image))[0]
    image[23:37, 183:207] = (120, 10, 80)
    after = reader.read(image, source(reader, image))[0]
    assert after.marker_support == before.marker_support
    assert after.role == 'victim'


def test_non_yellow_world_luminance_cannot_change_highlight_shape_support():
    reader, _, image = fixture()
    before = reader.read(image, source(reader, image))[0]
    patch = image[20:40, 180:210]
    background = reader.profile.marker_reference == 0
    luminance = np.random.default_rng(31).integers(0, 200, background.sum(), dtype=np.uint8)
    patch[background] = np.repeat(luminance[:, None], 3, axis=1)
    after = reader.read(image, source(reader, image))[0]
    assert after.marker_support == before.marker_support
    assert after.role == before.role == 'victim'
