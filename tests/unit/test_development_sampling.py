import pytest

from valorant_ai_coach.visual.development_sampling import map_sampling_targets


def test_whole_source_grid_has_no_prediction_input_and_fixed_temporal_thirds():
    plan = map_sampling_targets(3610)
    assert plan['coarse'] == list(range(30, 3600, 30))
    assert plan['dense_starts'] == [30, 1200, 2400]
    assert map_sampling_targets(35) == {'coarse': [], 'dense_starts': []}


def test_long_recording_increases_stride_instead_of_truncating_the_late_game():
    plan = map_sampling_targets(14400)
    assert len(plan['coarse']) <= 180
    assert plan['coarse'][0] == 30
    assert plan['coarse'][-1] > 14000
    assert all(a < b for a, b in zip(plan['coarse'], plan['coarse'][1:], strict=False))
    assert len(plan['dense_starts']) == 3


@pytest.mark.parametrize('duration', [False, 0, -1, float('nan'), float('inf')])
def test_invalid_duration_does_not_open_or_schedule_any_source(duration):
    with pytest.raises(ValueError):
        map_sampling_targets(duration)
