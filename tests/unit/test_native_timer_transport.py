import hashlib
from copy import deepcopy
from dataclasses import replace
from types import SimpleNamespace

import pytest

from tests.e2e.trace_adapter import to_e2e_trace
from tests.integration.test_hud_video_processor import make_observation
from tests.unit.test_native_event_merge import qualified_processor, result
from valorant_ai_coach.hud.native_event_merge import merge_native_timer_displays
from valorant_ai_coach.video import FrameSample


def sample(timestamp):
    observation = make_observation(timestamp)
    observation['values']['round_time_remaining_sec'] = None
    return observation


def test_exact_pts_preserves_display_and_player_facts_without_mutating_inputs(tmp_path):
    _, native = result(tmp_path)
    sampled = [sample(.14), sample(.141)]
    sampled[0]['primary_state'] = 'unknown'
    sampled[0]['values']['player_specific_hud_valid'] = False
    sampled[0]['values']['hp'] = None
    before = deepcopy(sampled)
    original = deepcopy(native)
    merged = merge_native_timer_displays(sampled, native)
    assert merged[0]['values']['round_time_remaining_display'] == '2:08'
    assert merged[1]['values']['round_time_remaining_sec'] is None
    assert merged[0]['primary_state'] == 'unknown'
    assert merged[0]['values']['hp'] is None
    assert merged[0]['values']['player_specific_hud_valid'] is False
    assert sampled == before and native == original


@pytest.mark.parametrize('invalid', ['weak', 'occluded', 'conflict', 'existing'])
def test_unsafe_or_conflicting_timer_is_not_overwritten(tmp_path, invalid):
    _, native = result(tmp_path)
    obs = sample(.14)
    if invalid == 'weak':
        native.observations[7]['quality']['roi_confidence']['round_timer_value'] = .89
    elif invalid == 'occluded':
        obs['quality']['occluded_rois'] = ['round_timer']
    elif invalid == 'conflict':
        obs['values']['round_time_remaining_sec'] = 37
    else:
        obs['values']['round_time_remaining_display'] = '0:37'
    assert merge_native_timer_displays([obs], native) == [obs]


def test_unqualified_timer_transport_is_rejected(tmp_path):
    _, native = result(tmp_path)
    with pytest.raises(ValueError, match='qualified native timer'):
        merge_native_timer_displays([sample(.14)], replace(native, qualification=None))


def test_native_timer_reaches_package_and_trace_with_unchanged_sampling(tmp_path):
    processor, metadata, frames, native = qualified_processor(tmp_path)
    bound_frames = []
    for frame in frames:
        frame.path.write_bytes(b'synthetic-decoder-image')
        bound_frames.append(FrameSample(
            frame.time_sec, frame.path, round(frame.time_sec * 1000), '1/1000',
            native.source_rows[0]['source_video_sha256'],
            hashlib.sha256(frame.path.read_bytes()).hexdigest(),
        ))
    frames = bound_frames
    original = processor.analyzer.observe_frames

    def observe(*args, **kwargs):
        measured = original(*args, **kwargs)
        for observation in measured.observations:
            observation['values']['round_time_remaining_sec'] = None
        return measured

    processor.analyzer.observe_frames = observe
    processed = processor.process_frames(metadata, 'synthetic-timer', frames,
                                         native_lifecycle=native)
    assert processed.sampled_frame_count == len(frames)
    assert all(o['values']['hp'] == 100 for o in processed.observations)
    trace = to_e2e_trace(SimpleNamespace(round_packages=processed.round_packages,
                                        observations=processed.observations,
                                        visual_observations=()))
    assert any(s.get('game_timer_display') == '1:33' for s in trace['snapshots'])
    assert [o['time_sec'] for o in processed.observations] == [f.time_sec for f in frames]


def test_legacy_sampled_image_cannot_join_by_timestamp_alone(tmp_path):
    _, native = result(tmp_path)
    observation = sample(.14)
    assert merge_native_timer_displays(
        [observation], native, frames=[FrameSample(.14, tmp_path / 'legacy.jpg')],
    ) == [observation]


@pytest.mark.parametrize('invalid', [None, 'foreign', 'corrupt'])
def test_decoder_identity_joins_across_decimal_precision_and_guards_source(tmp_path, invalid):
    _, native = result(tmp_path)
    path = tmp_path / 'decoded.jpg'
    path.write_bytes(b'decoder-image')
    frame = FrameSample(.1400003, path, 140, '1/1000',
                        'b' * 64 if invalid == 'foreign'
                        else native.source_rows[0]['source_video_sha256'],
                        hashlib.sha256(path.read_bytes()).hexdigest())
    if invalid == 'corrupt':
        path.write_bytes(b'changed')
    observation = sample(frame.time_sec)
    if invalid:
        with pytest.raises(ValueError):
            merge_native_timer_displays([observation], native, frames=[frame])
    else:
        merged = merge_native_timer_displays([observation], native, frames=[frame])
        assert merged[0]['values']['round_time_remaining_display'] == '2:08'
        assert merged[0]['time_sec'] == .1400003
