"""Source-cut transport tests; synthetic pixels never qualify real recognition."""
from pathlib import Path

import cv2
import numpy as np
import pytest

from tests.unit.test_visual_core_v2 import obs
from valorant_ai_coach.events import EventSourceContract
from valorant_ai_coach.resources import resource_path
from valorant_ai_coach.video import FrameSample, VideoMetadata
from valorant_ai_coach.visual.runtime import RealVisualAnalyzer


def analyzer():
    return RealVisualAnalyzer(EventSourceContract.load(
        resource_path('config/event_source_contract_v1.json'),
    ))


@pytest.mark.parametrize('missing_at_cut', [False, True])
def test_measurement_cut_resets_pixels_map_and_rejects_stale_hud(
    tmp_path, monkeypatch, missing_at_cut,
):
    from valorant_ai_coach.visual import runtime

    calls, extractors, timelines = [], [], []

    class Extractor:
        def __init__(self):
            extractors.append(self)

        def measure(self, image, previous, state, prior, **kwargs):
            calls.append((self, previous, prior, state))
            return obs(state['time_sec'])

    class Timeline:
        def __init__(self, profile):
            timelines.append(self)

        def calibrate(self, image):
            return None

        def resolve(self, *args):
            pass

    monkeypatch.setattr(runtime, 'PixelMeasurementExtractor', Extractor)
    monkeypatch.setattr(runtime, 'MapTimeline', Timeline)
    frames = []
    for t in (0.0, .1, .2):
        p = tmp_path / f'{t}.png'
        if not (missing_at_cut and t == .1):
            assert cv2.imwrite(str(p), np.full((16, 16, 3), 60, np.uint8))
        frames.append(FrameSample(t, p))
    hud = [{'time_sec': 0.0, 'primary_state': 'live_first_person',
            'values': {'player_specific_hud_valid': True}, 'quality': {}, 'state_flags': []}]
    _, evidence, _ = analyzer()._measure(frames, hud, continuity_breaks=(.05,))
    assert calls[0][0] is not calls[1][0]
    assert calls[1][1] is None and calls[1][2] is None
    assert calls[1][3]['primary_state'] == 'unknown'
    assert len(timelines) >= 2
    assert evidence[2 if missing_at_cut else 1]['source_discontinuity'] is True
    if not missing_at_cut:
        assert 'source_discontinuity' not in evidence[2]


@pytest.mark.parametrize('cuts', [(True,), (float('nan'),), (2,), (.2, .1), (.1, .1)])
@pytest.mark.parametrize('method', ['analyze', 'trigger_windows'])
def test_visual_break_input_contract_rejects_invalid_cuts(cuts, method):
    metadata = VideoMetadata(Path('video.mp4'), 2, 1920, 1080, 60, 'h264', None, False, 0)
    with pytest.raises(ValueError, match='continuity breaks'):
        getattr(analyzer(), method)([], [], video_metadata=metadata, continuity_breaks=cuts)


def test_trigger_enemy_latch_resets_on_source_break(monkeypatch):
    from tests.unit.test_visual_core_v2 import enemy

    runtime = analyzer()
    metadata = VideoMetadata(Path('video.mp4'), 2, 1920, 1080, 60, 'h264', None, False, 0)

    def measure(frames, hud, *, continuity_breaks):
        assert continuity_breaks == (.05,)
        return [obs(0, entities={'visible_enemies': [enemy()]}),
                obs(.1, index=1, entities={'visible_enemies': [enemy()]})], {
                    0: {}, 1: {'source_discontinuity': True}}, []

    monkeypatch.setattr(runtime, '_measure', measure)
    assert runtime.trigger_windows([], [], video_metadata=metadata, continuity_breaks=(.05,)) == (
        (0, 'engagement'), (.1, 'engagement'),
    )
