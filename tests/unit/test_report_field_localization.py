from dataclasses import replace

import numpy as np
import pytest

from tests.unit.test_report_header import header as header
from tests.unit.test_report_header import make_profile
from valorant_ai_coach.hud.readers import ReaderResult
from valorant_ai_coach.hud.report_header import ReportFieldLocator, report_header_evidence
from valorant_ai_coach.hud.templates import NumericFieldsReader, UnavailableConfiguredReader


class CapturingDigits:
    def __init__(self, confidence=.95):
        self.crops = []
        self.confidence = confidence

    def read(self, image, roi):
        self.crops.append(roi.copy())
        return ReaderResult('0194', self.confidence, ('source_ocr',), False)


def test_opt_in_header_pose_preserves_existing_presence_result(header):
    model, image = header
    previous = report_header_evidence(image, model)
    current = report_header_evidence(image, model, include_pose=True)
    assert current.pop('pose') == [20, 17]
    assert current == previous


@pytest.mark.parametrize('second_row', [39, 58])
def test_two_distinct_header_poses_cannot_choose_a_number(header, second_row):
    model, image = header
    image[second_row:second_row+24, 20:120] = model.reference
    result = report_header_evidence(image, model, include_pose=True)
    assert result['present'] is True  # Still useful exclusion evidence.
    assert result['pose'] is None
    raw = CapturingDigits()
    reader = NumericFieldsReader(
        {'damage_received': (.8, .6, .95, .8)}, raw,
        locator=ReportFieldLocator(model, (model.reference_x, 17/90)),
    )
    assert reader.read_candidates(image) == {}
    assert not raw.crops


@pytest.mark.parametrize('shift', [0, 18])
def test_current_structure_translates_crop_and_preserves_display(header, shift):
    model, _ = header
    image = np.full(model.input_shape, 30, np.uint8)
    image[17+shift:41+shift, 20:120] = model.reference
    digits = np.arange(15*20, dtype=np.uint8).reshape(15, 20)
    image[50+shift:65+shift, 125:145] = digits
    raw = CapturingDigits()
    reader = NumericFieldsReader(
        {'damage_received': (125/150, 50/90, 145/150, 65/90)}, raw,
        locator=ReportFieldLocator(model, (model.reference_x, 17/90)),
    )
    result = reader.read_candidates(image)['damage_received']
    assert np.array_equal(raw.crops[0], digits)
    assert result['display'] == '0194' and result['value'] == 194
    assert result['roi_bounds_norm'] == [125/150, (50+shift)/90, 145/150, (65+shift)/90]
    assert result['sources'] == ['source_ocr', 'report_header_pose']
    assert result['confidence'] == pytest.approx(.95)
    assert result['cross_checked'] is False  # Header does not verify digits.


def test_missing_current_header_never_reuses_previous_pose(header):
    model, image = header
    raw = CapturingDigits()
    reader = NumericFieldsReader(
        {'damage_received': (.8, .6, .95, .8)}, raw,
        locator=ReportFieldLocator(model, (model.reference_x, 17/90)),
    )
    assert reader.read_candidates(image)
    assert reader.read_candidates(np.full(model.input_shape, 30, np.uint8)) == {}
    assert len(raw.crops) == 1


def test_translated_crop_outside_frame_is_not_clipped_or_read(header):
    model, _ = header
    image = np.full(model.input_shape, 30, np.uint8)
    image[35:59, 20:120] = model.reference
    raw = CapturingDigits()
    reader = NumericFieldsReader(
        {'damage_received': (.8, .9, .95, 1.)}, raw,
        locator=ReportFieldLocator(model, (model.reference_x, 17/90)),
    )
    assert reader.read_candidates(image) == {}
    assert not raw.crops


@pytest.mark.parametrize('image_kind', ['partial', 'flat', 'contradictory'])
def test_geometry_and_independent_header_groups_are_required(header, image_kind):
    model, image = header
    if image_kind == 'partial':
        image = image[:40]
    elif image_kind == 'flat':
        image[:] = 30
    else:
        patch = image[17:41, 20:120]
        patch[model.regions == 2] = 30
    raw = CapturingDigits()
    reader = NumericFieldsReader(
        {'damage_received': (.8, .6, .95, .8)}, raw,
        locator=ReportFieldLocator(model, (model.reference_x, 17/90)),
    )
    assert reader.read_candidates(image) == {}
    assert not raw.crops


def test_header_localization_does_not_weaken_numeric_acceptance(header):
    model, image = header
    raw = CapturingDigits(.89)
    reader = NumericFieldsReader(
        {'damage_received': (.8, .6, .95, .8)}, raw,
        locator=ReportFieldLocator(model, (model.reference_x, 17/90)),
    )
    assert reader.read_candidates(image) == {}


def test_field_confidence_bounded_without_numeric_corroboration(header, monkeypatch):
    model, image = header
    monkeypatch.setattr(ReportFieldLocator, 'offset', lambda self, roi: (0, 0, .91))
    reader = NumericFieldsReader(
        {'damage_received': (.8, .6, .95, .8)}, CapturingDigits(.99),
        locator=ReportFieldLocator(model, (model.reference_x, 17/90)),
    )
    result = reader.read_candidates(image)['damage_received']
    assert result['confidence'] == .91
    assert result['cross_checked'] is False


@pytest.mark.parametrize('origin', [(True, .2), (.5, .2), (20/150, float('nan')),
                                   (20/150, -.1), (20/150, .9)])
def test_invalid_reference_origin_rejected(header, origin):
    model, _ = header
    with pytest.raises(ValueError):
        ReportFieldLocator(model, origin).validate()


def test_header_threshold_stays_at_least_point_nine(header):
    model, _ = header
    with pytest.raises(ValueError):
        ReportFieldLocator(replace(model, threshold=.89), (20/150, 17/90)).validate()


def test_explicit_profile_localization_builds_common_reader(tmp_path, header):
    model, image = header
    profile = make_profile(tmp_path, model)
    profile.raw['readers'] = {'combat_report': {
        'kind': 'fields', 'fields': {'damage_received': [.8, .6, .95, .8]},
        'templates': {}, 'minimum_confidence': .90,
        'localization': {'method': 'report_header_pose_v1',
                         'reference_origin_norm': [model.reference_x, 17/90]},
    }}
    reader = profile.build_readers()['combat_report']
    assert isinstance(reader, NumericFieldsReader)
    assert reader.locator.offset(image) == pytest.approx((0, 0, 1.))


@pytest.mark.parametrize('mutation', ['wrong_role', 'wrong_method', 'no_header',
                                     'bad_origin', 'extra_key', 'wrong_kind', 'bad_fields'])
def test_invalid_explicit_localization_keeps_unavailable_reader(tmp_path, header, mutation):
    model, _ = header
    profile = make_profile(tmp_path, model)
    local = {'method': 'report_header_pose_v1', 'reference_origin_norm': [model.reference_x, 17/90]}
    role = 'combat_report'
    if mutation == 'wrong_role':
        role = 'round_timer'
    elif mutation == 'wrong_method':
        local['method'] = 'guess'
    elif mutation == 'no_header':
        profile._report_header = None
    elif mutation == 'bad_origin':
        local['reference_origin_norm'] = [True, .2]
    elif mutation == 'extra_key':
        local['gt_time'] = 4.1
    profile.raw['readers'] = {role: {'kind': 'fields', 'fields': {}, 'templates': {},
                                   'localization': local}}
    if mutation == 'wrong_kind':
        profile.raw['readers'][role]['kind'] = 'digits'
    elif mutation == 'bad_fields':
        profile.raw['readers'][role]['fields'] = []
    assert isinstance(profile.build_readers()[role], UnavailableConfiguredReader)
    assert profile.reader_diagnostics
