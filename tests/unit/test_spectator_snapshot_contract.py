from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace

import pytest

from tests.e2e.trace_adapter import to_e2e_trace
from tests.integration.test_hud_video_processor import make_observation
from valorant_ai_coach.events import EventSourceContract
from valorant_ai_coach.hud.models import spectator_primary_state_evidence
from valorant_ai_coach.resources import resource_path
from valorant_ai_coach.rounds import RoundPackageBuilder
from valorant_ai_coach.schema_validation import SchemaValidator
from valorant_ai_coach.video import VideoMetadata


@pytest.mark.parametrize('state,valid,confidence,expected', [
    ('spectator_first_person', False, .9, True),
    ('live_first_person', True, .9, False),
    ('live_first_person', False, .9, None),
    ('unknown', False, .9, None),
    ('buy_menu', False, .9, None),
    ('spectator_first_person', False, .64, None),
    ('spectator_first_person', False, float('nan'), None),
])
def test_unknown_or_unsafe_source_is_not_false_exclusion(state, valid, confidence, expected):
    obs = make_observation(1)
    obs['primary_state'] = state
    obs['values']['player_specific_hud_valid'] = valid
    obs['quality']['hud_confidence'] = confidence
    original = deepcopy(obs)
    assert spectator_primary_state_evidence(obs) is expected
    assert obs == original


def test_source_state_reaches_native_package_and_trace_without_owned_fact_promotion():
    observations = [make_observation(t) for t in (1, 1.01, 1.02)]
    observations[1]['primary_state'] = 'spectator_first_person'
    observations[2]['primary_state'] = 'unknown'
    for obs in observations[1:]:
        obs['values']['player_specific_hud_valid'] = False
        obs['view_context']['is_player_world_view_trustworthy'] = False
        for key in ('hp', 'armor', 'ammo_current', 'ammo_reserve', 'weapon_text'):
            obs['values'][key] = None
    builder = RoundPackageBuilder(
        contract=EventSourceContract.load(resource_path('config/event_source_contract_v1.json')),
        validator=SchemaValidator(),
    )
    packages = builder.build(
        match_id='synthetic-spectator-snapshot',
        video_metadata=VideoMetadata(Path('synthetic.mp4'), 2, 1920, 1080, 60,
                                     'h264', None, False, 1),
        hud_observations=observations, hud_events=(),
    )
    snapshots = [s for p in packages for s in p['state_snapshots']]
    assert [s['spectator_primary_state'] for s in snapshots] == [False, True, None]
    trace = to_e2e_trace(SimpleNamespace(round_packages=packages,
                                        observations=observations, visual_observations=()))
    assert [s['spectator_primary_state'] for s in trace['snapshots']] == [False, True, None]
    assert trace['snapshots'][1]['player_hp'] is None
    assert trace['snapshots'][2]['view_owner'] == 'unknown'
    snapshots[0]['spectator_primary_state'] = True
    with pytest.raises(ValueError, match='spectator state source mismatch'):
        to_e2e_trace(SimpleNamespace(round_packages=packages, observations=observations))
