from copy import deepcopy
from types import SimpleNamespace

import numpy as np
import pytest

from tests.e2e.trace_adapter import to_e2e_trace
from tests.unit.test_combat_report_readings import FieldReader, _reading
from tests.unit.test_report_field_localization import CapturingDigits
from tests.unit.test_report_header import header as header
from tests.unit.test_report_header import make_profile
from valorant_ai_coach.hud.models import HudObservationV2, empty_hud_values
from valorant_ai_coach.hud.readers import ReaderResult
from valorant_ai_coach.hud.report_header import ReportFieldLocator
from valorant_ai_coach.hud.templates import NumericFieldsReader, UnavailableConfiguredReader
from valorant_ai_coach.schema_validation import SchemaValidator

LABEL = 'レイズ'
BOUNDS = (125/150, 50/90, 145/150, 65/90)


def portrait_reader(model, result, *, located=True, bounds=BOUNDS):
    raw = FieldReader([result])
    reader = NumericFieldsReader(
        {'damage_received': BOUNDS}, CapturingDigits(),
        locator=ReportFieldLocator(model, (model.reference_x, 17/90)) if located else None,
        portrait_fields={'report_portrait_label': (bounds, raw)},
    )
    return reader, raw


def test_current_portrait_is_not_text_or_owned_fact_and_never_retained(header, monkeypatch):
    model, image = header
    reader, raw = portrait_reader(model, ReaderResult(LABEL, .99, (f'template:{LABEL}',)))
    monkeypatch.setattr(ReportFieldLocator, 'offset', lambda self, roi: (0, 0, .91))
    fields = reader.read_candidates(image)
    assert fields['damage_received']['value'] == 194
    assert fields['report_portrait_label'] == {
        'label': LABEL, 'confidence': .91,
        'sources': [f'template:{LABEL}', 'report_header_pose'],
        'cross_checked': False, 'roi_bounds_norm': list(BOUNDS),
    }
    monkeypatch.undo()
    assert reader.read_candidates(np.full(model.input_shape, 30, np.uint8)) == {}
    assert raw.calls == 1
    # The existing numeric API cannot expose portrait semantics.
    assert reader.read(image, image).value == {'damage_received': 194}
    assert raw.calls == 1


@pytest.mark.parametrize('result', [
    ReaderResult(LABEL, .89, (f'template:{LABEL}',)),
    ReaderResult(LABEL, float('nan'), (f'template:{LABEL}',)),
    ReaderResult(LABEL, True, (f'template:{LABEL}',)),
    ReaderResult(LABEL, .99, ('ocr',)),
    ReaderResult(LABEL, .99, (f'template:{LABEL}', ' ')),
    ReaderResult('', .99, ('template:',)),
    ReaderResult('x'*65, .99, ('template:'+'x'*65,)),
    ReaderResult(None, .99, ()),
])
def test_weak_ambiguous_or_unproven_portraits_abstain_independently(header, result):
    model, image = header
    reader, _ = portrait_reader(model, result)
    fields = reader.read_candidates(image)
    assert set(fields) == {'damage_received'}


@pytest.mark.parametrize('located,bounds', [(False, BOUNDS), (True, (.8, .9, .95, 1.))])
def test_no_locator_or_outside_crop_cannot_read_portrait(header, located, bounds):
    model, image = header
    if located:
        image[:] = 30
        image[35:59, 20:120] = model.reference
    reader, raw = portrait_reader(model, ReaderResult(LABEL, .99, (f'template:{LABEL}',)),
                                  located=located, bounds=bounds)
    assert 'report_portrait_label' not in reader.read_candidates(image)
    assert raw.calls == 0


def candidate_observation():
    report = _reading()
    report['fields']['report_portrait_label'] = {
        'label': LABEL, 'confidence': .95,
        'sources': [f'template:{LABEL}', 'report_header_pose'],
        'cross_checked': False, 'roi_bounds_norm': [.1, .2, .3, .4],
    }
    values = empty_hud_values()
    values.update(combat_report_visible=True, combat_report_readings=report)
    return HudObservationV2(1., 0, values=values).to_dict()


def test_candidate_roundtrip_does_not_create_killer_or_death_trace():
    source = candidate_observation()
    SchemaValidator().validate_hud_observation(source)
    assert HudObservationV2.from_dict(source).to_dict() == source
    assert source['values']['player_specific_hud_valid'] is False
    trace = to_e2e_trace(SimpleNamespace(
        round_packages=[{'round_window': {'start_sec': 0, 'end_sec': 2},
                         'state_snapshots': [{'time_sec': 1}]}],
        observations=[deepcopy(source)],
    ))
    assert trace['events'] == []
    assert 'killer_agent' not in trace['snapshots'][0]
    assert 'report_portrait_label' not in trace['snapshots'][0]


@pytest.mark.parametrize('mutation', ['cross_checked', 'no_pose', 'wrong_template',
                                     'display', 'owner', 'killer_agent', 'stale_pts'])
def test_persisted_portrait_cannot_be_promoted_or_lose_provenance(mutation):
    source = candidate_observation()
    report = source['values']['combat_report_readings']
    field = report['fields']['report_portrait_label']
    if mutation == 'cross_checked':
        field['cross_checked'] = True
    elif mutation == 'no_pose':
        field['sources'] = [f'template:{LABEL}']
    elif mutation == 'wrong_template':
        field['sources'] = ['template:フェイド', 'report_header_pose']
    elif mutation == 'display':
        field['display'] = field.pop('label')
    elif mutation == 'owner':
        field['owner'] = 'self'
    elif mutation == 'killer_agent':
        report['fields']['killer_agent'] = report['fields'].pop('report_portrait_label')
    else:
        report['source_pts_sec'] = .5
    with pytest.raises(ValueError):
        HudObservationV2.from_dict(source)
    with pytest.raises(ValueError):
        SchemaValidator().validate_hud_observation(source)


@pytest.mark.parametrize('mutation', [None, 'wrong_role', 'wrong_kind', 'no_locator',
                                     'low_threshold', 'bool_threshold', 'nan_threshold',
                                     'extra_key', 'wrong_field', 'missing_asset'])
def test_profile_explicit_portrait_contract(tmp_path, header, mutation):
    model, _ = header
    profile = make_profile(tmp_path, model)
    spec = {'bounds': list(BOUNDS), 'values': {LABEL: 'reference.png'}, 'threshold': .90}
    # make_profile provides a real image asset; no production portrait fixture needed.
    import cv2
    assert cv2.imwrite(str(tmp_path / 'reference.png'), model.reference)
    raw = {'kind': 'fields', 'fields': {}, 'templates': {},
           'localization': {'method': 'report_header_pose_v1',
                            'reference_origin_norm': [model.reference_x, 17/90]},
           'portrait_fields': {'report_portrait_label': spec}}
    role = 'combat_report'
    if mutation == 'wrong_role':
        role = 'round_timer'
    elif mutation == 'wrong_kind':
        raw['kind'] = 'digits'
    elif mutation == 'no_locator':
        raw.pop('localization')
    elif mutation in {'low_threshold', 'bool_threshold', 'nan_threshold'}:
        spec['threshold'] = {'low_threshold': .89, 'bool_threshold': True,
                             'nan_threshold': float('nan')}[mutation]
    elif mutation == 'extra_key':
        spec['owner'] = 'self'
    elif mutation == 'wrong_field':
        raw['portrait_fields'] = {'killer_agent': spec}
    elif mutation == 'missing_asset':
        spec['values'] = {LABEL: 'missing.png'}
    profile.raw['readers'] = {role: raw}
    reader = profile.build_readers()[role]
    if mutation is None:
        assert isinstance(reader, NumericFieldsReader)
        assert set(reader.portrait_fields) == {'report_portrait_label'}
    else:
        assert isinstance(reader, UnavailableConfiguredReader)
        assert profile.reader_diagnostics
