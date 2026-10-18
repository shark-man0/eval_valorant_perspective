"""Synthetic row association; neither Self nor new-death qualification."""
import hashlib
from dataclasses import replace

import cv2
import numpy as np
import pytest

from tests.unit.test_report_header import header as header_fixture
from valorant_ai_coach.experimental.death_episode_fields import ReportCandidateFrame
from valorant_ai_coach.experimental.report_fatal_row import FatalReportRowReader
from valorant_ai_coach.experimental.subject_death import SourceBinding
from valorant_ai_coach.hud.report_header import ReportFieldLocator

header = header_fixture
PRODUCER = ('a'*64, 'b'*64, 'c'*64)


def setup(header, **changes):
    model, gray = header
    image = cv2.cvtColor(gray, cv2.COLOR_GRAY2BGR)
    reference = np.random.default_rng(919).integers(25, 230, (12, 25), dtype=np.uint8)
    image[68:80, 101:126] = reference[:, :, None]
    args = dict(reference=reference, search_box=(95, 65, 140, 85),
                locator=ReportFieldLocator(model, (20/150, 17/90)),
                damage_bounds=(95/150, 45/90, 135/150, 65/90),
                field_producer=PRODUCER, dependencies_fingerprint='d'*64)
    args.update(changes)
    return FatalReportRowReader(**args), image, reference


def fields(image, *, dy=0, value=125, confidence=.93):
    source = SourceBinding('e'*64, 100, 1, 60, 'source-segment',
                           hashlib.sha256(image.tobytes()).hexdigest(), *PRODUCER)
    return ReportCandidateFrame.from_fields(source, (0, 0, 150, 90), {
        'damage_received': {'display': str(value), 'value': value, 'confidence': confidence,
            'sources': ['tesseract_digits', 'report_header_pose'], 'cross_checked': False,
            'roi_bounds_norm': [95/150, (45+dy)/90, 135/150, (65+dy)/90]},
    })


def test_current_static_label_links_original_value_without_ownership_or_event(header):
    reader, image, _ = setup(header)
    original = fields(image)
    result = reader.read(image, original)
    assert result.reason == 'unqualified_fatal_damage_row'
    assert result.damage_roi == (95, 45, 135, 65)
    assert result.marker_roi == (101, 68, 126, 80)
    assert result.association_support <= .93
    assert result.fields_source == original.source
    assert result.source.pixel_sha256 == original.source.pixel_sha256
    assert result.source.profile_fingerprint != original.source.profile_fingerprint
    assert result.source.code_fingerprint != original.source.code_fingerprint
    assert not result.qualified


def test_header_translation_applies_to_label_and_value_together(header):
    reader, image, _ = setup(header)
    shifted = np.roll(image, 3, axis=0)
    result = reader.read(shifted, fields(shifted, dy=3))
    assert result.damage_roi == (95, 48, 135, 68)
    assert result.marker_roi == (101, 71, 126, 83)
    assert reader.read(shifted, fields(shifted)).reason == (
        'fatal_marker_does_not_identify_original_damage_slot')


@pytest.mark.parametrize('what', ['header', 'marker', 'other_row', 'source', 'producer'])
def test_independent_support_and_exact_original_source_required(header, what):
    reader, image, _ = setup(header)
    original = fields(image)
    if what == 'header':
        image[17:41, 20:120] = 30
        original = fields(image)
    elif what == 'marker':
        image[68:80, 101:126] = 30
        original = fields(image)
    elif what == 'other_row':
        original = fields(image, dy=-20)
    elif what == 'source':
        image[0, 0] = 255
    else:
        original = replace(original, source=replace(original.source, profile_fingerprint='f'*64))
    result = reader.read(image, original)
    assert result.association_support is None and result.damage_roi is None


def test_duplicate_labels_are_ambiguous(header):
    reader, image, ref = setup(header, search_box=(95, 60, 140, 88))
    image[60:88, 95:140] = 30
    image[60:72, 101:126] = ref[:, :, None]
    image[74:86, 101:126] = ref[:, :, None]
    assert reader.read(image, fields(image)).reason == 'fatal_row_label_missing_or_ambiguous'


def test_persistent_label_does_not_claim_a_new_death(header):
    reader, image, _ = setup(header)
    a = reader.read(image, fields(image))
    b = reader.read(image, fields(image))
    assert a == b and a.reason == 'unqualified_fatal_damage_row'
    assert not a.qualified and not hasattr(a, 'event')


def test_digit_values_are_not_marker_inputs_and_field_confidence_is_not_increased(header):
    reader, image, _ = setup(header)
    a = reader.read(image, fields(image, value=1, confidence=.90))
    b = reader.read(image, fields(image, value=999, confidence=.99))
    assert a.marker_support == b.marker_support
    assert a.association_support == .90 and b.association_support <= .99


def test_calibration_assets_cannot_mutate_after_reader_construction(header):
    reader, image, ref = setup(header)
    fp = reader.profile_fingerprint
    ref[:] = 0
    header[0].reference[:] = 0
    assert reader.read(image, fields(image)).reason == 'unqualified_fatal_damage_row'
    assert reader.profile_fingerprint == fp


@pytest.mark.parametrize('bad', [True, float('nan'), float('inf'), -.1])
def test_invalid_calibration_is_rejected(header, bad):
    with pytest.raises(ValueError):
        setup(header, damage_bounds=(bad, .1, .9, .9))
