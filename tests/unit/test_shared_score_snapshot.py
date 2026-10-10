from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace

import pytest

from tests.e2e.trace_adapter import to_e2e_trace
from tests.integration.test_hud_video_processor import make_observation
from valorant_ai_coach.events import EventSourceContract
from valorant_ai_coach.hud.models import shared_score_evidence
from valorant_ai_coach.resources import resource_path
from valorant_ai_coach.rounds import RoundPackageBuilder
from valorant_ai_coach.schema_validation import SchemaValidator
from valorant_ai_coach.video import VideoMetadata


def score_observation(time=1):
    obs = make_observation(time)
    obs['values'].update(score_ally=0, score_enemy=1)
    obs['quality']['roi_confidence'].update(score_ally_value=.95, score_enemy_value=.96)
    return obs


@pytest.mark.parametrize('confidence', [None, .89, True, float('nan'), float('inf'), 1.01])
def test_geometry_or_invalid_score_confidence_cannot_authorize_global_score(confidence):
    obs = score_observation()
    obs['quality']['roi_confidence'].update(score_ally_value=confidence, ally_score=.99)
    before = deepcopy(obs)
    assert shared_score_evidence(obs) == {'score_ally': None, 'score_enemy': 1}
    assert obs == before


@pytest.mark.parametrize('value', [True, -1, 1.0, None])
def test_unknown_or_invalid_numeric_score_is_not_repaired(value):
    obs = score_observation()
    obs['values']['score_ally'] = value
    assert shared_score_evidence(obs)['score_ally'] is None


def test_occluded_scores_remain_unknown():
    obs = score_observation()
    obs['quality']['occluded_rois'] = ['ally_score']
    assert shared_score_evidence(obs) == {'score_ally': None, 'score_enemy': None}


def test_global_scores_survive_native_package_trace_without_owned_facts_or_dedup_loss():
    observations = [score_observation(t) for t in (1, 1.01, 1.02)]
    for obs in observations[1:]:
        obs['primary_state'] = 'unknown'
        obs['values']['player_specific_hud_valid'] = False
        obs['view_context']['is_player_world_view_trustworthy'] = False
        for key in ('hp', 'armor', 'ammo_current', 'ammo_reserve', 'weapon_text'):
            obs['values'][key] = None
    observations[2]['values']['score_enemy'] = 2
    original = deepcopy(observations)
    validator = SchemaValidator()
    builder = RoundPackageBuilder(
        contract=EventSourceContract.load(resource_path('config/event_source_contract_v1.json')),
        validator=validator,
    )
    packages = builder.build(
        match_id='shared-score-test',
        video_metadata=VideoMetadata(Path('synthetic.mp4'), 2, 1920, 1080, 60,
                                     'h264', None, False, 1),
        hud_observations=observations, hud_events=(),
    )
    for package in packages:
        validator.validate_round_package(package)
    snapshots = [s for p in packages for s in p['state_snapshots']]
    assert [s['score_enemy'] for s in snapshots] == [1, 1, 2]
    assert [s['source_confidence']['score_enemy'] for s in snapshots] == [.96] * 3
    result = SimpleNamespace(round_packages=packages, observations=observations)
    trace = to_e2e_trace(result)
    assert [(s['score_player'], s['score_enemy']) for s in trace['snapshots']] == [
        (0, 1), (0, 1), (0, 2),
    ]
    assert trace['snapshots'][1]['view_owner'] == 'unknown'
    assert trace['snapshots'][1]['player_hp'] is None
    assert 'player_alive' not in trace['snapshots'][1]
    assert 'ammo_mag' not in trace['snapshots'][1]
    assert observations == original
    snapshots[1]['score_ally'] = 99
    with pytest.raises(ValueError, match='shared score source mismatch'):
        to_e2e_trace(result)
    snapshots[1]['score_ally'] = 0
    snapshots[1]['source_confidence']['score_ally'] = .99
    with pytest.raises(ValueError, match='shared score confidence mismatch'):
        to_e2e_trace(result)
