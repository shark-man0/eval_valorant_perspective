"""Frozen measurement transport checks, not source-recognizer qualification."""
from copy import deepcopy
from dataclasses import asdict

import pytest

from tests.unit.test_self_death_image_recognizer import observe, setup
from valorant_ai_coach.experimental.subject_death import ReviewStatus, SubjectRelation, SubjectRole
from valorant_ai_coach.experimental.subject_witness_transport import transport_prediction


def readings():
    model, base, header = setup()
    rows = [asdict(observe(model, base, header, 0, report=False, marker=False)),
            asdict(observe(model, base, header, 1, marker=False))]
    rows.extend(asdict(observe(model, base, header, tick)) for tick in range(2, 6))
    assert rows[-1]['status'] == 'prediction'
    return rows


def test_original_onset_confidence_and_physical_binding_are_not_replaced_by_confirmation():
    rows = readings()
    # Explicit synthetic source-support values exercise transport, not recognition.
    rows[1]['report_support'] = .91
    rows[-1]['report_support'] = .99
    result = transport_prediction(rows, 5, report_roi=(0, 45, 80, 78))
    transition = next(w for w in result.evidence if w.role == SubjectRole.DEATH_TRANSITION)
    assert transition.source.pts_ticks == 1 and transition.confidence == .91
    assert asdict(transition.source) == rows[1]['source']
    assert transition.roi == tuple(rows[1]['report_match_roi'])
    assert result.source.pts_ticks == 5 and result.confidence <= .91
    assert result.boundary_time_sec == 1/60 and result.confirmation_time_sec == 5/60
    assert all(w.review_status == ReviewStatus.CANDIDATE
               and w.relation == SubjectRelation.UNKNOWN and w.subject_token is None
               for w in result.evidence)
    assert result.to_dict()['qualified'] is False and result.to_dict()['formal_events'] == []


def test_geometric_role_never_inherits_plate_fraction_as_numeric_confidence():
    rows = readings()
    victim = rows[-1]['subjects'][0]
    victim['weapon_support'] = None
    victim['weapon_geometry'] = {'roi': victim['weapon_roi'], 'plate_fraction': 1.0}
    result = transport_prediction(rows, 5, report_roi=(0, 45, 80, 78))
    role = next(w for w in result.evidence if w.role == SubjectRole.VICTIM)
    assert role.confidence is None
    assert 'victim_numeric_confidence_absent_structural_witness_only' in result.blockers
    assert role.source == result.source


@pytest.mark.parametrize('failure', ['missing_onset', 'changed_pixels', 'cross_context',
                                   'bad_onset', 'nonself_role', 'other_subject_source',
                                   'missing_confirmation'])
def test_missing_conflicting_or_nonvictim_evidence_cannot_be_repaired(failure):
    rows = deepcopy(readings())
    if failure == 'missing_onset':
        rows[1]['source']['pts_ticks'] = 99
    elif failure == 'changed_pixels':
        rows[1]['source']['pixel_sha256'] = 'c'*64
    elif failure == 'cross_context':
        rows[-1]['evidence_sources'][0]['segment_id'] = 'other'
    elif failure == 'bad_onset':
        rows[-1]['onset_time_sec'] = .123
    elif failure == 'nonself_role':
        rows[-1]['subjects'][0]['role'] = 'killer'
    elif failure == 'missing_confirmation':
        rows[-1]['evidence_sources'] = [s for s in rows[-1]['evidence_sources']
                                       if s['pts_ticks'] != 5]
    else:
        rows[-1]['subjects'][0]['source']['pixel_sha256'] = 'd'*64
    with pytest.raises(ValueError):
        transport_prediction(rows, 5, report_roi=(0, 45, 80, 78))


@pytest.mark.parametrize('bad', [None, True, '0.99', float('nan'), float('inf'), 1.1, .89])
def test_invalid_or_unaccepted_original_support_is_not_defaulted(bad):
    rows = readings()
    rows[1]['report_support'] = bad
    with pytest.raises(ValueError):
        transport_prediction(rows, 5, report_roi=(0, 45, 80, 78))


def test_only_an_actual_prediction_can_be_transported():
    rows = readings()
    with pytest.raises(ValueError, match='actually recorded'):
        transport_prediction(rows, 0, report_roi=(0, 45, 80, 78))


def test_legacy_artifact_without_match_roi_keeps_its_explicit_search_box():
    rows = readings()
    for row in rows:
        row.pop('report_match_roi')
    result = transport_prediction(rows, 5, report_roi=(0, 45, 80, 78))
    transition = next(w for w in result.evidence if w.role == SubjectRole.DEATH_TRANSITION)
    assert transition.roi == (0, 45, 80, 78)


@pytest.mark.parametrize('roi', [None, [0, 0, 10, 10], [0, 45, 90, 78]])
def test_missing_or_out_of_search_precise_caption_box_is_not_repaired(roi):
    rows = readings()
    rows[1]['report_match_roi'] = roi
    with pytest.raises(ValueError):
        transport_prediction(rows, 5, report_roi=(0, 45, 80, 78))
