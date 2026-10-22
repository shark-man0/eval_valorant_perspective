import copy

import pytest

from scripts.diagnostics.hud_semantic_review import (
    position_stability,
    response_defaults,
    summarize_review,
)


def packet():
    positions = {n: [.1, .1, .2, .2] for n in ('timer', 'hp', 'abilities')}
    return {'cases': [{'case_id': str(i), 'frame': {'source_sha256': 'a' * 64, 'tick': i},
                       'methods': {m: {'geometry_consistent': True, 'positions': positions}
                                   for m in ('X', 'Y')}} for i in range(2)]}


def test_default_unknown_and_detector_success_cannot_become_semantic_truth():
    p = packet()
    s = summarize_review(p, response_defaults(p))
    assert s['reviewed_cases'] == 0 and s['unreviewed_cases'] == 2
    assert s['population_accuracy'] is None
    assert s['formal_events'] == [] and not s['production_qualified']
    assert all(c['confirmed_correct'] == c['confirmed_wrong'] == 0
               and c['unknown'] == 2 and c['reviewed_output_agreement'] is None
               for c in s['methods'].values())


def test_only_explicit_reviewed_boxes_count_and_spectator_is_not_automatically_wrong():
    p = packet()
    r = response_defaults(p)
    r['reviewer'] = 'human'
    a = r['cases'][0]
    a.update(reviewed=True, state='SPECTATOR')
    a['methods']['Y'] = dict.fromkeys(a['methods']['Y'], 'CORRECT')
    s = summarize_review(p, r)
    assert s['methods']['Y']['confirmed_correct'] == 1
    assert s['methods']['Y']['unknown'] == 1
    assert s['methods']['X']['unknown'] == 2
    assert s['states']['SPECTATOR']['Y']['confirmed_wrong'] == 0
    assert s['population_accuracy'] is None


def test_rejected_candidate_is_not_a_false_calibration():
    p = packet()
    p['cases'][0]['methods']['Y']['geometry_consistent'] = False
    r = response_defaults(p)
    r['reviewer'] = 'human'
    r['cases'][0]['reviewed'] = True
    r['cases'][0]['methods']['Y']['hp'] = 'INCORRECT'
    s = summarize_review(p, r)
    assert s['methods']['Y']['confirmed_wrong'] == 0


def test_reviewed_risk_state_is_preserved_when_both_methods_reject():
    p = packet()
    for m in p['cases'][0]['methods'].values():
        m['geometry_consistent'] = False
        m['positions'] = {}
    r = response_defaults(p)
    r['reviewer'] = 'human'
    r['cases'][0].update(reviewed=True, state='MENU')
    s = summarize_review(p, r)
    assert s['states']['MENU']['Y']['geometry_rejected'] == 1
    assert s['states']['MENU']['Y']['human_reviewed_cases'] == 1
    assert s['states']['MENU']['Y']['confirmed_wrong'] == 0


@pytest.mark.parametrize('mutation', ['ai', 'missing_reviewer', 'unreviewed_label',
                                      'unreviewed_state', 'wrong_anchor', 'wrong_case',
                                      'duplicate_case', 'source_changed', 'wrong_label'])
def test_response_provenance_and_unknown_boundaries(mutation):
    p = packet()
    r = response_defaults(p)
    if mutation == 'ai':
        r['origin'] = 'AI_generated'
    elif mutation == 'missing_reviewer':
        r['cases'][0]['reviewed'] = True
    elif mutation == 'unreviewed_label':
        r['cases'][0]['methods']['Y']['hp'] = 'CORRECT'
    elif mutation == 'unreviewed_state':
        r['cases'][0]['state'] = 'MENU'
    elif mutation == 'wrong_anchor':
        r['cases'][0]['methods']['Y']['other'] = 'UNKNOWN'
    elif mutation == 'wrong_case':
        r['cases'][0]['case_id'] = 'other'
    elif mutation == 'duplicate_case':
        r['cases'][1] = copy.deepcopy(r['cases'][0])
    elif mutation == 'source_changed':
        p['cases'][0]['frame']['source_sha256'] = 'b' * 64
    elif mutation == 'wrong_label':
        r['cases'][0]['methods']['Y']['hp'] = 'AUTO_ACCEPT'
    with pytest.raises(ValueError):
        summarize_review(p, r)


def witnesses():
    return [{'source_sha256': 'a' * 64, 'epoch': 'one', 'tick': i, 'time_base': '1/60',
             'result': {'geometry_consistent': True, 'positions': {'timer': [.1, .1, .2, .2]}}}
            for i in range(3)]


def test_missing_position_is_not_stability_and_native_identity_is_required():
    rows = witnesses()
    rows[1]['result']['positions'] = {}
    rows[1]['result']['geometry_consistent'] = False
    s = position_stability(rows)
    assert s['anchors']['timer']['present'] == 2
    assert not s['anchors']['timer']['present_in_all_witnesses']
    assert s['geometry_toggles'] == 2
    assert s['continuity'] == 'UNVERIFIED' and s['semantic_correctness'] == 'UNKNOWN'
    rows[1]['epoch'] = 'other'
    with pytest.raises(ValueError):
        position_stability(rows)


@pytest.mark.parametrize('mutation', ['duplicate_pts', 'float_pts', 'negative_timebase',
                                      'nan_box', 'outside_box', 'empty_box'])
def test_invalid_native_time_or_positions_rejected(mutation):
    rows = witnesses()
    if mutation == 'duplicate_pts':
        rows[1]['tick'] = 0
    elif mutation == 'float_pts':
        rows[1]['tick'] = .5
    elif mutation == 'negative_timebase':
        rows[1]['time_base'] = '-1/60'
    else:
        rows[1]['result']['positions']['timer'] = {
            'nan_box': [float('nan'), .1, .2, .2],
            'outside_box': [-.1, .1, .2, .2], 'empty_box': [.2, .1, .1, .2],
        }[mutation]
    with pytest.raises(ValueError):
        position_stability(rows)
