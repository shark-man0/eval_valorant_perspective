from scripts.diagnostics.validate_frozen_result_feature import timestamp_ticks


def test_decimal_exposure_coordinates_match_only_source_grid():
    tick = 1173289
    assert timestamp_ticks({'rows': [{'pts_sec': round(tick / 15360, 6)}]}) == {tick}
    assert timestamp_ticks({'pts_sec': tick / 15360 + .001}) == set()
    assert timestamp_ticks({'pts_sec': True}) == set()
    assert timestamp_ticks({'pts_sec': float('nan')}) == set()


def test_exposure_inventory_does_not_treat_windows_or_expected_values_as_decoded_frames():
    assert timestamp_ticks({'window_sec': [76.55, 76.75], 'expected_timer': 99}) == set()
