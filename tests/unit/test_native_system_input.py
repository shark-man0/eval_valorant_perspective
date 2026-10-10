import hashlib
from dataclasses import replace
from fractions import Fraction
from types import SimpleNamespace

import cv2
import numpy as np
import pytest

from valorant_ai_coach.hud.analyzers import RealHudAnalyzer
from valorant_ai_coach.hud.models import HudObservationV2, empty_hud_values
from valorant_ai_coach.hud.native_system_input import collect_native_system_observations
from valorant_ai_coach.hud.readers import ReaderResult, load_frame
from valorant_ai_coach.hud.semantic_text import CONFIDENCE_KEY
from valorant_ai_coach.resources import resource_path
from valorant_ai_coach.video.native import NativeSourceFrame


@pytest.fixture
def frames(tmp_path):
    result = []
    for index in range(2):
        image = np.full((64, 64, 3), 60 + index, np.uint8)
        path = tmp_path / f'{index}.png'
        assert cv2.imwrite(str(path), image)
        result.append(NativeSourceFrame(
            path, 63017 + index * 256, Fraction(1, 15360), 'unit-decoder', 'a'*64,
            hashlib.sha256(path.read_bytes()).hexdigest(),
            hashlib.sha256(image.tobytes()).hexdigest(), 64, 64,
        ))
    return result


def observed(frames, state='live_first_person'):
    values = empty_hud_values()
    values.update(
        round_time_remaining_sec=145, round_time_remaining_display='2:25',
        round_time_remaining_display_provenance={
            'reader': 'round_timer', 'sources': ['synthetic-ocr'],
            'confidence': .95, 'cross_checked': False,
        }, score_ally=0, score_enemy=1, buy_phase_visible=True,
    )
    if state == 'live_first_person':
        values.update(player_specific_hud_valid=True, hp=100, armor=50,
                      weapon_text='knife', ammo_current=10)
    return [HudObservationV2(
        frame.time_sec, index, primary_state=state, state_flags=('buy_phase_banner',),
        values=values, quality={
            'hud_confidence': .95, 'visual_confidence': 0, 'occluded_rois': [],
            'notes': [], 'state_confidence': .95,
            'roi_confidence': {'round_timer_value': .95, 'score_ally_value': .96,
                               'ally_score_value': .96, CONFIDENCE_KEY: .97, 'hp_value': .99},
        }, remote_view_type='astra_astral' if state == 'remote_control_view' else 'none',
        is_player_world_view_trustworthy=state == 'live_first_person',
    ).to_dict() for index, frame in enumerate(frames)]


def collect(frames, observe=observed, fingerprint=lambda: 'fixed'):
    return collect_native_system_observations(
        frames, native_step_ticks=256, observe=observe, fingerprint=fingerprint,
    )


@pytest.mark.parametrize('state', ['live_first_person', 'unknown', 'spectator_first_person',
                                 'buy_menu_open', 'remote_control_view'])
def test_native_global_projection_preserves_display_context_and_excludes_owned_facts(frames, state):
    original = observed(frames, state)
    rows = collect(frames, lambda source: original)
    for row, frame in zip(rows, frames, strict=True):
        observation = row['system_observation']
        assert observation['time_sec'] == frame.time_sec
        assert row['source_pts_ticks'] == frame.pts_ticks
        assert row['source_pixel_sha256'] == frame.pixel_sha256
        assert observation['primary_state'] == state
        assert observation['values']['round_time_remaining_display'] == '2:25'
        provenance = observation['values']['round_time_remaining_display_provenance']
        assert provenance['sources'] == ['synthetic-ocr']
        assert observation['values']['player_specific_hud_valid'] is False
        assert observation['values']['hp'] is None
        assert observation['values']['weapon_text'] is None
        assert observation['values']['ammo_current'] is None
        assert observation['values']['kill_feed_rows'] == []
        assert observation['view_context']['is_player_world_view_trustworthy'] is False
        assert observation['quality']['roi_confidence'][CONFIDENCE_KEY] == .97
        assert observation['quality']['roi_confidence']['ally_score_value'] == .96
        assert 'hp_value' not in observation['quality']['roi_confidence']
        assert row['system_evidence'] == {}
    rows[0]['system_observation']['values']['round_time_remaining_display_provenance']['sources'].clear()
    assert original[0]['values']['round_time_remaining_display_provenance']['sources']


@pytest.mark.parametrize('change', ['epoch', 'pts', 'video', 'timebase'])
def test_mixed_or_gapped_native_input_fails_before_analysis(frames, change):
    changes = {'epoch': {'source_epoch': 'other'}, 'pts': {'pts_ticks': 63785},
               'video': {'source_video_sha256': 'b'*64}, 'timebase': {'time_base': Fraction(1, 60)}}
    frames[1] = replace(frames[1], **changes[change])
    with pytest.raises(ValueError, match='contiguous'):
        collect(frames, lambda _: pytest.fail('must reject before analyzer'))


@pytest.mark.parametrize('mismatch', ['coverage', 'timestamp', 'index'])
def test_observation_must_match_each_actual_native_input(frames, mismatch):
    def wrong(source):
        rows = observed(source)
        if mismatch == 'coverage':
            return rows[:1]
        rows[0]['time_sec' if mismatch == 'timestamp' else 'frame_index'] += 1
        return rows
    with pytest.raises(ValueError, match='mismatch'):
        collect(frames, wrong)


def test_terminal_asset_mutation_withholds_all_observations(frames):
    def changed(source):
        rows = observed(source)
        source[-1].path.write_bytes(source[-1].path.read_bytes() + b'changed')
        return rows
    with pytest.raises(RuntimeError, match='asset changed'):
        collect(frames, changed)


def test_terminal_configuration_change_withholds_all_observations(frames):
    versions = iter(['initial', 'changed'])
    with pytest.raises(ValueError, match='inputs changed'):
        collect(frames, fingerprint=lambda: next(versions))


def test_shared_frame_loader_verifies_native_pixels_on_every_read(frames):
    assert np.array_equal(load_frame(frames[0]), frames[0].read_image())
    frames[0].path.write_bytes(frames[0].path.read_bytes() + b'changed')
    with pytest.raises(RuntimeError, match='asset changed'):
        load_frame(frames[0])


def test_real_analyzer_native_entrance_does_not_invoke_event_builder(frames, monkeypatch):
    analyzer = RealHudAnalyzer(resource_path('config/hud_layout_1080p_v3.json'))
    monkeypatch.setattr('valorant_ai_coach.hud.analyzers.HudDirectEventBuilder.build',
                        lambda *a, **k: pytest.fail('native measurements cannot emit events'))
    rows = analyzer.observe_native_system_frames(frames, native_step_ticks=256)
    assert len(rows) == 2
    assert all(row['system_evidence'] == {} for row in rows)
    assert all(row['system_observation']['primary_state'] == 'unknown' for row in rows)
    assert all(
        row['system_observation']['values']['round_time_remaining_sec'] is None for row in rows
    )


def test_native_entrance_rejects_profile_changed_since_analyzer_load(frames, tmp_path):
    layout = tmp_path / 'layout.json'
    layout.write_bytes(resource_path('config/hud_layout_1080p_v3.json').read_bytes())
    analyzer = RealHudAnalyzer(layout)
    layout.write_bytes(layout.read_bytes() + b'\n')
    with pytest.raises(RuntimeError, match='profile changed'):
        analyzer.observe_native_system_frames(frames, native_step_ticks=256)


def test_native_prefix_retains_acquired_geometry(frames, tmp_path, monkeypatch):
    # Synthetic detector outputs test transport/policy, not real qualification.
    import json

    layout = tmp_path / 'layout.json'
    raw = json.loads(resource_path('config/hud_layout_1080p_v3.json').read_text())
    raw['reference_resolution'] = {'width': 64, 'height': 64}
    layout.write_text(json.dumps(raw))
    texts = iter(['0:00', '2:25'])
    timer = SimpleNamespace(read=lambda *args: ReaderResult(
        next(texts), .95, sources=('synthetic-ocr',),
    ))
    analyzer = RealHudAnalyzer(layout, readers={'round_timer': timer})
    analyzer.ocr_fallback_rois = frozenset()
    first_anchors = {name: analyzer.layout.normalized_roi(name)
                     for name in ('round_timer', 'top_match_bar', 'player_hp_armor', 'abilities')}
    detections = iter([first_anchors, {'top_match_bar': first_anchors['top_match_bar']}])
    profile = SimpleNamespace(
        raw={}, fingerprint=lambda _: analyzer._native_loaded_base_fingerprint,
        detect_anchors=lambda *args: (next(detections), {}, ()),
        detect_signals=lambda *args, **kwargs: {},
    )
    monkeypatch.setattr(analyzer, 'template_profile', profile)
    rows = analyzer.observe_native_system_frames(frames, native_step_ticks=256)
    assert [row['system_observation']['values'].get('round_time_remaining_display')
            for row in rows] == ['0:00', '2:25']
    counts = analyzer.last_calibration_diagnostics['counts']
    assert counts['fresh_geometry_success'] == 1
    assert counts['effective_geometry_success'] == 2
    assert counts['retained_geometry_frames'] == 1
    assert all(row['system_evidence'] == {} for row in rows)
