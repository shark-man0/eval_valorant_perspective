"""Saved-row adapter safety; tiny synthetic archives, no private fixtures."""

import json

import pytest

from scripts.diagnostics.replay_clock_type_end_study import compose


def fixture_archive(root, *, pixel="a" * 64, matched=False):
    files = {
        "production-separated-score/rows.json": [
            {
                "pool": "WON",
                "tick": 256,
                "field": field,
                "pixel_sha256": pixel,
                "value": "2",
                "confidence": 0.95,
            }
            for field in ("ally_score", "enemy_score")
        ],
        "timer-rejection-development/rows.json": [
            {"window": "WON", "tick": 256, "pixel_sha256": "a" * 64, "value": None, "confidence": 0}
        ],
        "clock-type-chromatic-development/full-development-rows.json": [
            {
                "window": "WON",
                "tick": 256,
                "pixel_sha256": "a" * 64,
                "prediction": {"kind": "spike", "literal": None, "confidence": 0.95},
            }
        ],
        "development-timing/WON-result/raw-rows.json": [
            {
                "source_video_sha256": "b" * 64,
                "source_epoch": "original",
                "source_pts_ticks": 256,
                "source_time_base": "1/15360",
                "source_pixel_sha256": "a" * 64,
                "system_observation": {"values": {}, "quality": {"roi_confidence": {}}},
                "system_measurements": {
                    "native_ui": {
                        "phase_scan_valid": True,
                        "phase_present": False,
                        "phase_confidence": 0,
                        "round_result_matched": matched,
                        "round_result_confidence": 0.95 if matched else 0,
                    }
                },
            }
        ],
    }
    for name, data in files.items():
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data), encoding="utf-8")


@pytest.mark.parametrize("matched", [False, True])
def test_archive_preserves_epoch_unknown_context_and_nonmatch_is_not_absence(tmp_path, matched):
    fixture_archive(tmp_path, matched=matched)
    rows, baseline = compose(tmp_path, "WON")
    assert rows[0].epoch == "original"
    assert rows[0].view == rows[0].phase == "unknown"
    assert rows[0].caption == ("complete" if matched else "unknown")
    assert rows[0].clock_kind == "spike"
    assert baseline[0]["system_observation"]["values"]["round_time_remaining_sec"] is None


def test_archive_refuses_cross_pixel_component_join(tmp_path):
    fixture_archive(tmp_path, pixel="c" * 64)
    with pytest.raises(AssertionError):
        compose(tmp_path, "WON")
