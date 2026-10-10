from dataclasses import replace
from types import SimpleNamespace

import pytest

from tests.unit.test_native_source_input import make_video, window
from valorant_ai_coach.hud import native_scene_input


@pytest.fixture
def video(tmp_path):
    return make_video(tmp_path)


def test_native_entrance_delivers_actual_owned_pixels_ticks_without_facts(video, monkeypatch):
    captured = []
    verified = []

    class Episode:
        def __init__(self, factory, **options):
            assert options == {'native_step_ticks': 256, 'deferred_initialization': False}

        def observe(self, image, tick, **options):
            captured.append((image.copy(), tick, options['source_epoch']))
            return {'runtime_proof_authorized': False, 'qualification_created': False}

    monkeypatch.setattr(native_scene_input, 'ObservedSceneEpisode', Episode)
    binding = SimpleNamespace(verify=lambda: verified.append(True), profile_path='unused')
    with window(video) as frames:
        rows = native_scene_input.observe_native_scene_window(
            frames, binding, native_step_ticks=256,
        )
        assert [item[1] for item in captured] == [frame.pts_ticks for frame in frames]
        assert [row['source_pts_sec'] for row in rows] == [frame.time_sec for frame in frames]
        assert all(row['source_pixel_sha256'] == frame.pixel_sha256
                   for row, frame in zip(rows, frames, strict=True))
        assert all(set(row) == {
            'source_video_sha256', 'source_epoch', 'source_pts_ticks', 'source_time_base',
            'source_pts_sec', 'source_pixel_sha256', 'scene_measurement',
        } for row in rows)
    assert verified == [True, True]


@pytest.mark.parametrize('field,value', [
    ('source_epoch', 'other'), ('source_video_sha256', '0'*64),
    ('time_base', 1),
])
def test_native_entrance_rejects_mixed_source_bindings_before_episode(
    video, monkeypatch, field, value
):
    monkeypatch.setattr(native_scene_input, 'ObservedSceneEpisode',
                        lambda *a, **k: pytest.fail('unexpected episode'))
    binding = SimpleNamespace(verify=lambda: None)
    with window(video) as frames:
        altered = [frames[0], replace(frames[1], **{field: value})]
        with pytest.raises(ValueError, match='one decoder-owned'):
            native_scene_input.observe_native_scene_window(altered, binding, native_step_ticks=256)
