import copy

import pytest

from scripts.diagnostics.check_scene_training_support import projected_exclusion, training_support


def rows():
    return [{'source_pixel_sha256': f'{i:064x}', 'source_pts_ticks': 1000+i*256,
             'proposal': {'diagnostic_initialization_proposed': True},
             'observed': {'descriptive_scene_link': i > 0,
                          'reason': 'descriptive_observed_scene_link' if i else
                          'image_supported_observed_seed', 'runtime_proof_authorized': False}}
            for i in range(4)]


def test_three_distinct_nonself_matches_and_links_only_pass_development_screen():
    result = training_support(rows(), {'0'*64})
    assert result['appearance_training_minimum_met']
    assert result['reference_self_matches'] == 1
    assert result['distinct_nonself_initialization_matches'] == 3
    assert not result['qualification_created']
    assert not result['runtime_authorized']
    assert not result['current_world_semantics_qualified']


def test_self_only_match_and_terminated_chain_are_rejected():
    inputs = rows()
    for row in inputs[1:]:
        row['proposal']['diagnostic_initialization_proposed'] = False
        row['observed'].update(descriptive_scene_link=False, reason='episode_terminated')
    result = training_support(inputs, {'0'*64})
    assert not result['appearance_training_minimum_met']
    assert result['first_episode_stop']['reason'] == 'episode_terminated'


def test_reference_matches_without_temporal_links_are_insufficient():
    inputs = rows()
    for row in inputs:
        row['observed']['descriptive_scene_link'] = False
    assert not training_support(inputs, set())['appearance_training_minimum_met']


def test_duplicate_source_frames_cannot_inflate_support():
    inputs = rows()
    inputs.append(copy.deepcopy(inputs[0]))
    with pytest.raises(ValueError, match='distinct native'):
        training_support(inputs, set())


def test_projection_into_protected_phase_is_visible_without_authorization():
    assert projected_exclusion((160,55,220,117), [[1,0,0],[0,1,0]])[
        'projected_pixels_touching_exclusion_or_image_boundary'] == 0
    assert projected_exclusion((160,55,220,117), [[1,0,10],[0,1,0]])[
        'projected_pixels_touching_exclusion_or_image_boundary'] > 0


def test_nonfinite_projection_is_rejected():
    with pytest.raises(ValueError, match='finite affine'):
        projected_exclusion((160,55,220,117), [[1,0,float('nan')],[0,1,0]])


def test_source_gap_cannot_be_counted_as_continuous_training():
    inputs = rows()
    inputs[2]['source_pts_ticks'] += 1
    with pytest.raises(ValueError, match='native training cadence'):
        training_support(inputs, set())


def test_rejoining_after_episode_failure_is_rejected():
    inputs = rows()
    inputs[1]['observed'].update(descriptive_scene_link=False, reason='episode_terminated')
    with pytest.raises(ValueError, match='cannot rejoin'):
        training_support(inputs, set())
