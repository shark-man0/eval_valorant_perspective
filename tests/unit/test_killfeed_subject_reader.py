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


def test_alternate_weapon_reference_is_source_bound_and_not_extra_corroboration():
    old, ocr, image = fixture()
    alternate = np.random.default_rng(84).integers(20, 220, (16, 24), dtype=np.uint8)
    profile = replace(old.profile, additional_weapon_references=(alternate,))
    reader = KillfeedSubjectReader(profile, ocr, runtime_fingerprint=HASH)
    assert profile.fingerprint() != old.profile.fingerprint()
    image[22:38, 100:124] = np.repeat(alternate[:, :, None], 3, axis=2)
    assert old.read(image, source(old, image))[0].role == 'unknown'
    rows = reader.read(image, source(reader, image))
    assert len(rows) == 1 and rows[0].role == 'victim'
    assert rows[0].weapon_support == pytest.approx(1)
    assert rows[0].formal_events == ()


def test_duplicate_weapon_templates_do_not_create_multiple_separator_witnesses():
    old, ocr, image = fixture()
    profile = replace(old.profile, additional_weapon_references=(old.profile.weapon_reference,))
    reader = KillfeedSubjectReader(profile, ocr, runtime_fingerprint=HASH)
    rows = reader.read(image, source(reader, image))
    assert len(rows) == 1 and rows[0].role == 'victim'
    assert rows[0].weapon_support == pytest.approx(1)


def glyph_fixture(*, killer=False):
    old, ocr, image = fixture(killer=killer)
    image[18:46, 95:169] = (40, 60, 200)
    image[25:30, 100:164] = 255
    image[30:40, 118:126] = 255
    profile = replace(old.profile, separator_method='white_glyph_geometry')
    return KillfeedSubjectReader(profile, ocr, runtime_fingerprint=HASH), image


@pytest.mark.parametrize('killer', [False, True])
def test_structural_glyph_role_has_measured_geometry_and_no_invented_ncc(killer):
    reader, image = glyph_fixture(killer=killer)
    rows = reader.read(image, source(reader, image))
    assert len(rows) == 1 and rows[0].role == ('killer' if killer else 'victim')
    geometry = rows[0].weapon_geometry
    assert geometry is not None
    assert geometry.roi == (100, 25, 164, 40)
    assert geometry.white_pixels == 64*5+8*10
    assert geometry.maximum_scanline_pixels == 64
    assert geometry.plate_family == 'red' and geometry.plate_fraction == 1
    assert rows[0].weapon_support is None
    assert rows[0].qualified is False and rows[0].formal_events == ()


@pytest.mark.parametrize('control', ['letters', 'line', 'block', 'colored', 'ambiguous',
                                   'portrait_context'])
def test_glyph_negative_controls_abstain(control):
    reader, image = glyph_fixture()
    if control not in {'ambiguous', 'portrait_context'}:
        image[22:44, 95:169] = (40, 60, 200)
    if control == 'letters':
        cv2.putText(image, 'IIIIIIII', (100, 36), cv2.FONT_HERSHEY_SIMPLEX, .4,
                    (255, 255, 255), 1)
    elif control == 'line':
        image[25:27, 100:164] = 255
    elif control == 'block':
        image[25:42, 100:164] = 255
    elif control == 'colored':
        image[25:30, 100:164] = (0, 0, 255)
        image[30:40, 118:126] = (0, 0, 255)
    elif control == 'ambiguous':
        image[18:46, 0:74] = (40, 60, 200)
        image[25:30, 4:68] = 255
        image[30:40, 22:30] = 255
    else:
        image[18:25, 95:169] = (180, 30, 20)
        image[42:46, 95:169] = (180, 30, 20)
    rows = reader.read(image, source(reader, image))
    assert len(rows) == 1 and rows[0].role == 'unknown'
    assert rows[0].weapon_geometry is None and rows[0].weapon_support is None


def test_glyph_method_and_name_calibration_are_explicit_fingerprinted_inputs():
    old, _, _ = fixture()
    changed = replace(old.profile, separator_method='white_glyph_geometry', name_gap_inset=3)
    assert changed.fingerprint() != old.profile.fingerprint()
    with pytest.raises(ValueError, match='separator'):
        replace(old.profile, separator_method='unreviewed')
    for inset in [True, -1, 20, 1.5]:
        with pytest.raises(ValueError, match='inset'):
            replace(old.profile, name_gap_inset=inset)


def test_strong_feature_keeps_dim_warm_background_out_of_outline_shape():
    old, ocr, image = fixture()
    profile = replace(old.profile, marker_feature_kind='hsv_strong_yellow_outline_v1')
    assert profile.fingerprint() != old.profile.fingerprint()
    warm = cv2.cvtColor(np.array([[[28, 140, 180]]], dtype=np.uint8), cv2.COLOR_HSV2BGR)[0, 0]
    crop = image[20:40, 180:210]
    crop[old.profile.marker_reference == 0] = warm
    reader = KillfeedSubjectReader(profile, ocr, runtime_fingerprint=HASH)
    rows = reader.read(image, source(reader, image))
    assert len(rows) == 1 and rows[0].role == 'victim'
    assert min(rows[0].marker_support) >= .90
    assert rows[0].yellow_fraction == 1
    assert rows[0].formal_events == ()
    with pytest.raises(ValueError, match='highlight feature'):
        replace(old.profile, marker_feature_kind='unreviewed')


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
