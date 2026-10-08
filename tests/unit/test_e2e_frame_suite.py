import json

import pytest

from scripts.e2e import frame_suite as frame_suite_module
from scripts.e2e.frame_suite import (
    EXPECTED_STATES,
    compare_metrics,
    evaluate_frames,
    load_suite,
    selected_frames,
)

SOURCE = "a" * 64


def frame(pts, categories=("live",), **extra):
    return {
        "pts_sec": pts,
        "categories": list(categories),
        "provenance": [{"path": "missing/frozen.json", "sha256": "b" * 64}],
        **extra,
    }


def document(frames=None, mode="targeted"):
    return {
        "schema_version": 1,
        "suite_id": "test",
        "mode": mode,
        "video_id": "match_001",
        "source_sha256": SOURCE,
        "calibration_prefix": [0.1, 0.2],
        "frames": frames if frames is not None else [frame(1.0)],
    }


def write(tmp_path, data):
    path = tmp_path / "suite.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    return path


def test_load_suite_binds_source_and_reports_missing_portable_provenance(tmp_path):
    path = write(tmp_path, document())
    suite = load_suite(path, "targeted", SOURCE)
    assert suite["suite_sha256"]
    assert suite["provenance_diagnostics"] == [{"path": "missing/frozen.json", "status": "missing"}]
    assert suite["frames"][0]["pts_sec"] == 1.0


@pytest.mark.parametrize(
    "frames",
    [
        [frame(2), frame(1)],
        [frame(1), frame(1)],
        [frame(float("nan"))],
        [frame(1, categories=("made_up",))],
        [frame(1, categories=("live", "live"))],
        [frame(1, categories=("live",), expected_numeric={"hp": 75})],
    ],
)
def test_load_suite_rejects_invalid_frame_definitions(tmp_path, frames):
    with pytest.raises(ValueError):
        load_suite(write(tmp_path, document(frames)), "targeted", SOURCE)


def test_load_suite_rejects_mode_and_source_mismatch(tmp_path):
    path = write(tmp_path, document())
    with pytest.raises(ValueError, match="mode mismatch"):
        load_suite(path, "sampled", SOURCE)
    with pytest.raises(ValueError, match="source_sha256"):
        load_suite(path, "targeted", "c" * 64)


def test_expected_state_is_checked_against_hud_state_enum(tmp_path):
    for state in EXPECTED_STATES:
        valid = document([frame(1, ("regression_protection",), expected_state=state)])
        assert (
            load_suite(write(tmp_path, valid), "targeted", SOURCE)["frames"][0]["expected_state"]
            == state
        )
    invalid = document([frame(1, expected_state="spectator_free_camera")])
    with pytest.raises(ValueError, match="unsupported expected_state"):
        load_suite(write(tmp_path, invalid), "targeted", SOURCE)


def test_local_provenance_hash_mismatch_fails_closed(tmp_path, monkeypatch):
    evidence = tmp_path / "evidence.json"
    evidence.write_text("frozen source", encoding="utf-8")
    manifest = document([frame(1, provenance=[{"path": "evidence.json", "sha256": "b" * 64}])])
    path = write(tmp_path, manifest)
    monkeypatch.setattr(frame_suite_module, "_REPO_ROOT", tmp_path)
    with pytest.raises(ValueError, match="provenance hash mismatch"):
        load_suite(path, "targeted", SOURCE)


def test_selected_frames_uses_any_requested_category():
    suite = {"frames": [frame(1, ("live", "hp_numeric")), frame(2, ("unknown",))]}
    assert selected_frames(suite, ["hp_numeric", "unknown"]) == [{"pts_sec": 1}, {"pts_sec": 2}]
    assert selected_frames(suite, ["unknown"]) == [{"pts_sec": 2}]
    assert set(selected_frames(suite, ["live"])[0]) == {"pts_sec"}


def test_evaluate_frames_checks_only_frozen_state_and_numeric_labels():
    suite = document(
        [
            frame(1, ("live",), expected_state="live_first_person"),
            frame(2, ("timer_score",), expected_numeric={"timer": "1:39", "score_player": 0}),
            frame(3, ("unknown",)),
            frame(4, ("unknown",), expected_state="unknown"),
        ]
    )
    obs = [
        {"time_sec": 1, "primary_state": "unknown", "values": {}},
        {
            "time_sec": 2,
            "primary_state": "unknown",
            "values": {"round_time_remaining_sec": 99, "score_ally": 0},
        },
        {"time_sec": 3, "primary_state": "live_first_person", "values": {"hp": 100}},
        {"time_sec": 4, "primary_state": "unknown", "values": {}},
    ]
    result = evaluate_frames(suite, obs)
    assert result["counts"] == {"passed": 1, "failed": 1, "not_evaluated": 2}
    assert result["failures"] == [
        {
            "pts_sec": 1,
            "categories": ["live"],
            "field": "primary_state",
            "expected": "live_first_person",
            "actual": "unknown",
            "reason": "value_mismatch",
        }
    ]
    assert result["coverage"]["limitations"] == [
        "point frames only; no full-pack assertions or continuous event/round claims"
    ]


def test_evaluate_frames_requires_exact_unique_pts_and_reports_unlabeled_ne():
    suite = document(
        [frame(1, ("unknown",)), frame(2, ("spectator",), expected_state="spectator_first_person")]
    )
    result = evaluate_frames(
        suite,
        [
            {"time_sec": 1.000002, "primary_state": "unknown", "values": {}},
            {"time_sec": 2, "primary_state": "spectator_first_person", "values": {}},
            {"time_sec": 2, "primary_state": "unknown", "values": {}},
        ],
    )
    assert result["counts"] == {"passed": 0, "failed": 1, "not_evaluated": 1}
    assert result["failures"] == [
        {
            "pts_sec": 2,
            "categories": ["spectator"],
            "field": "primary_state",
            "expected": "spectator_first_person",
            "actual": None,
            "reason": "observation_pts_ambiguous",
        }
    ]
    assert [r["reason"] for r in result["not_evaluated_frames"]] == ["observation_missing"]


def test_evaluate_frames_fails_missing_values_and_reports_only_mismatched_fields():
    suite = document(
        [
            frame(1, ("hp_numeric",), expected_numeric={"hp": 75}),
            frame(
                2,
                ("live", "hp_numeric"),
                expected_state="live_first_person",
                expected_numeric={"hp": 75},
            ),
        ]
    )
    result = evaluate_frames(
        suite,
        [
            {"time_sec": 1, "primary_state": "live_first_person", "values": {"hp": None}},
            {"time_sec": 2, "primary_state": "live_first_person", "values": {"hp": 100}},
        ],
    )
    assert result["counts"] == {"passed": 0, "failed": 2, "not_evaluated": 0}
    assert result["failures"] == [
        {
            "pts_sec": 1,
            "categories": ["hp_numeric"],
            "field": "hp",
            "expected": 75,
            "actual": None,
            "reason": "expected_value_unavailable",
        },
        {
            "pts_sec": 2,
            "categories": ["live", "hp_numeric"],
            "field": "hp",
            "expected": 75,
            "actual": 100,
            "reason": "value_mismatch",
        },
    ]


def test_compare_metrics_requires_identical_suite_mode_selection_and_source():
    current = {
        "mode": "targeted",
        "suite_sha256": "hash",
        "selected_categories": ["live"],
        "video_id": "match_001",
        "source_sha256": SOURCE,
        "counts": {"passed": 2, "failed": 1, "not_evaluated": 0},
        "coverage": {"state_counts": {"unknown": 1, "live": 2, "spectator": 0, "menu": 0}},
        "wall_sec": 10,
        "fps": 3,
    }
    previous = {**current, "counts": {"passed": 1, "failed": 2, "not_evaluated": 0}, "wall_sec": 8}
    metrics = compare_metrics(current, previous)
    assert metrics[0] == {
        "metric": "passed",
        "current": 2,
        "previous": 1,
        "delta": 1,
        "percent_change": 100,
    }
    assert next(x for x in metrics if x["metric"] == "fps")["current"] == 3
    with pytest.raises(ValueError, match="mode"):
        compare_metrics({**current, "mode": "sampled"}, previous)
    with pytest.raises(ValueError, match="selected_categories"):
        compare_metrics({**current, "selected_categories": []}, previous)
