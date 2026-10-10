from scripts.diagnostics.inventory_native_exposure import collect_ticks, merge_ticks


def test_saved_native_ticks_include_nested_source_rows_but_not_gt_seconds():
    value = {
        "rows": [
            {"source_pts_ticks": 100},
            {"expected_timestamp": 4.1},
            {"source_pts_ticks": True},
            {"source_pts_ticks": "356"},
            {"result": {"source_pts_ticks": 356}},
        ]
    }
    assert collect_ticks(value) == {100, 356}


def test_exposure_ranges_do_not_bridge_unobserved_native_slots():
    assert merge_ticks([868, 356, 100, 100, 2000]) == [[100, 356], [868, 868], [2000, 2000]]
    assert merge_ticks([]) == []
