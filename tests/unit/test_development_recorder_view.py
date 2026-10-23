import copy

import cv2
import numpy as np
import pytest

from valorant_ai_coach.visual.development_recorder_view import DevelopmentRecorderView


@pytest.fixture
def agent_case(tmp_path):
    rng = np.random.default_rng(18)
    frame = np.zeros((240, 600, 3), np.uint8)
    slots = [[.5, .6, .6, .8], [.65, .6, .75, .8], [.8, .6, .9, .8]]
    agents = []
    for name in ['recorder-agent', 'another-agent']:
        paths = []
        for i in range(3):
            glyph = rng.integers(0, 256, (15, 21, 3), np.uint8)
            path = tmp_path/f'{name}_{i}.png'
            cv2.imwrite(str(path), glyph)
            paths.append([str(path)])
            if name == 'recorder-agent':
                frame[150:165, 305+90*i:326+90*i] = glyph
        agents.append({'agent_id': name, 'templates': paths})
    binding = {'source_id': 'source', 'source_sha256': 'a'*64,
               'physical_match_id': 'one-match', 'acquisition_ids': ['limited-window'],
               'review_kind': 'human_source_roster', 'anchor_frame_sha256': 'b'*64,
               'review_sha256': 'c'*64, 'recorder_agent_id': 'recorder-agent'}
    return frame, {'mode': 'agent_binding_v1', 'frame_size_px': [600, 240],
                   'binding': binding, 'slots': slots, 'agents': agents}


def inspect(frame, spec, engine=None, **kwargs):
    return (engine or DevelopmentRecorderView()).inspect(
        frame, spec, minimap_roi=[0, 0, .4, .4], source_id='source',
        source_sha256=kwargs.get('source_sha256', 'a'*64),
        acquisition_id=kwargs.get('acquisition_id', 'limited-window'))


def test_source_binding_and_current_agent_support_never_assign_self(agent_case):
    frame, spec = agent_case
    result = inspect(frame, spec)
    assert result['association'] == 'recorder_agent_supported'
    assert result['positive_agent_association'] is True
    assert result['ownership'] == 'UNKNOWN' and result['recorder_identity_qualified'] is False
    assert result['block_position_candidate'] is False
    assert result['evidence_family'] == 'current_ability_glyphs'


def test_different_agent_and_reference_change_break_candidate(agent_case):
    frame, spec = agent_case
    engine = DevelopmentRecorderView()
    before = inspect(frame, spec, engine)
    spec['binding']['recorder_agent_id'] = 'another-agent'
    different = inspect(frame, spec, engine)
    assert different['association'] == 'different_agent_supported'
    assert different['block_position_candidate'] is True
    assert different['reference_fingerprint'] != before['reference_fingerprint']
    path = spec['agents'][0]['templates'][0][0]
    cv2.imwrite(path, np.zeros((15, 21, 3), np.uint8))
    assert inspect(frame, spec, engine)['status'] == 'unavailable'


@pytest.mark.parametrize('field,value', [('source_sha256', None), ('source_sha256', 'd'*64),
                                         ('acquisition_id', 'another-window')])
def test_binding_cannot_transfer_to_another_source_or_acquisition(agent_case, field, value):
    frame, spec = agent_case
    result = inspect(frame, spec, **{field: value})
    assert result['status'] == 'unavailable' and result['block_position_candidate'] is True


def test_same_signature_for_two_agents_is_unknown_even_with_recorder_binding(agent_case):
    frame, spec = agent_case
    spec['agents'][1]['templates'] = copy.deepcopy(spec['agents'][0]['templates'])
    result = inspect(frame, spec)
    assert result['association'] == 'UNKNOWN'
    assert result['visible_agent_candidate'] is None
    assert result['ownership'] == 'UNKNOWN'


@pytest.mark.parametrize('mutation', ['overlap', 'empty', 'wrong_size', 'binding_missing'])
def test_malformed_authoring_fails_closed(agent_case, mutation):
    frame, spec = agent_case
    if mutation == 'overlap':
        spec['slots'][1] = spec['slots'][0]
    elif mutation == 'empty':
        spec['agents'][1]['templates'][0] = []
    elif mutation == 'wrong_size':
        spec['frame_size_px'] = [1200, 480]
    else:
        spec['binding']['review_sha256'] = None
    result = inspect(frame, spec)
    assert result['status'] == 'unavailable' and result['block_position_candidate'] is True
