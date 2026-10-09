import pytest

from scripts.diagnostics.motion_consensus import measure_region_consensus


def tracks(moving_region=None):
    result = []
    for region in range(6):
        for x, y in ((0, 0), (20, 10), (10, 20), (30, 30)):
            px, py = x + region * 40, y + region * 15
            dx = 12 if region == moving_region else 1
            result.append({"region": region, "previous": [px, py], "current": [px + dx, py + 2]})
    return result


def test_common_translation_has_low_out_of_region_residual():
    results = measure_region_consensus(tracks())
    assert all(r["median_residual_px"] < 0.001 for r in results)
    assert all(r["region"] not in r["model_training_regions"] for r in results)
    assert all(r["consistent_at_existing_2px"] == 4 for r in results)


def test_independent_foreground_motion_is_not_supported_by_its_own_fit():
    results = measure_region_consensus(tracks(moving_region=2))
    assert results[2]["median_residual_px"] == pytest.approx(11)
    assert results[2]["consistent_at_existing_2px"] == 0
    assert all(r["median_residual_px"] < 0.001 for r in results if r["region"] != 2)
    assert all(r["unqualified"] is True for r in results)
    assert all("confidence" not in r and "segment" not in r for r in results)


def test_no_tracks_or_single_region_cannot_supply_out_of_region_motion_model():
    for data in ([], [t for t in tracks() if t["region"] == 1]):
        results = measure_region_consensus(data)
        assert all(r["out_of_region_affine"] is None for r in results)
        assert all(r["median_residual_px"] is None for r in results)


@pytest.mark.parametrize("bad", [float("nan"), float("inf")])
def test_nonfinite_coordinates_fail_closed(bad):
    data = tracks()
    data[0]["previous"][0] = bad
    with pytest.raises(ValueError, match="finite source"):
        measure_region_consensus(data)
