import json

from scripts.e2e.share_report import export_report


def _inputs(tmp_path, **changes):
    metadata = {
        "video_id": "match_1",
        "source_sha256": "a" * 64,
        "analyzer_commit": "abcdef1234567",
        "git_is_dirty": False,
        "executed_at": "2026-09-30T10:00:00Z",
        "validation_pack": "pack_v3",
        "validation_pack_sha256": "b" * 64,
        **changes,
    }
    assertions = {
        "required_point_events": [
            {
                "id": "point_1",
                "round_id": "r1",
                "type": "kill",
                "actor": "player",
                "acceptance_window": [4, 6],
            }
        ],
        "negative_assertions": [{"id": "negative_1", "window": [8, 9]}],
    }
    trace = {
        "events": [{"type": "kill", "time_sec": 5, "actor": "player"}],
        "state_intervals": [],
        "ownership_intervals": [],
        "snapshots": [],
        "visual_observations": [],
        "temporal_features": [],
    }
    evaluation = {
        "pass": True,
        "schema_valid": True,
        "trace_counts": {"events": 1},
        "failure_count": 0,
        "negative_assertion_count": 1,
        "failures": [],
    }
    return dict(
        raw={"path": "/private/alice/video.mp4"},
        trace=trace,
        evaluation=evaluation,
        assertions=assertions,
        metadata=metadata,
        output_dir=tmp_path,
    )


def test_pass_and_failure_details_are_bounded_and_reconciled(tmp_path):
    args = _inputs(tmp_path)
    path = export_report(**args)
    data = json.loads(path.read_text())
    assert data["result"]["status"] == "pass"
    assert data["counts"]["events"] == 1
    assert data["result"]["failure_count"] == 0
    args["evaluation"].update(pass_=False)
    args["evaluation"]["pass"] = False
    args["evaluation"].update(failure_count=1, failures=["missing_point:point_1"])
    path = export_report(**args)
    data = json.loads(path.read_text())
    assert data["result"]["status"] == "fail"
    assert data["failures"][0]["assertion_id"] == "point_1"
    assert data["failures"][0]["category"] == "missing_point"
    assert data["failures"][0]["interval"] == [4, 6]
    assert data["sections"]["HUD"]["failure_count"] == 1


def test_nested_secrets_paths_and_hostile_text_never_leak(tmp_path):
    args = _inputs(
        tmp_path,
        video_id="C:\\Users\\Alice\\video.mp4",
        analyzer_commit="Bearer-secret",
        error_code="API_KEY=secret",
    )
    args["raw"] = {
        "nested": {
            "path": "/Users/alice/private",
            "token": "secret-token",
            "player": "Alice",
            "diagnostic": "API_KEY=abc",
        }
    }
    args["trace"]["events"][0]["actor"] = "Alice Smith"
    args["evaluation"]["failures"] = ["missing_point:/Users/alice/token=secret"]
    args["evaluation"]["pass"] = False
    out = tmp_path / "share"
    args["output_dir"] = out
    export_report(**args)
    serialized = "".join(p.read_text() for p in out.iterdir() if p.is_file())
    for secret in ("Alice", "secret-token", "API_KEY", "/Users", "C:\\\\Users", "video.mp4"):
        assert secret not in serialized
    data = json.loads((out / "summary.json").read_text())
    assert data["metadata"]["video_id"] is None
    assert data["result"]["error_code"] is None
    assert data["result"]["status"] == "fail"


def test_error_unknown_counts_dirty_history_and_no_output_copy(tmp_path):
    args = _inputs(
        tmp_path,
        analyzer_commit=None,
        source_sha256=None,
        git_is_dirty=True,
        git_dirty_fingerprint="c" * 64,
        settings_fingerprint="d" * 64,
        error_code="PREFLIGHT_FAILED",
    )
    args.update(
        raw={},
        trace={},
        evaluation={"pass": False, "schema_valid": False, "failures": [], "failure_count": None},
        assertions={},
    )
    export_report(**args)
    data = json.loads((tmp_path / "summary.json").read_text())
    assert data["result"]["status"] == "fail"
    assert data["counts"]["events"] is None
    assert data["metadata"]["git_is_dirty"] is True
    assert data["failures"][0]["category"] == "runtime_error"
    assert set(p.name for p in tmp_path.iterdir()) == {"summary.json", "README.md", "history.json"}
    export_report(**args)
    history = json.loads((tmp_path / "history.json").read_text())
    assert len(history) == 1


def test_history_distinguishes_dirty_and_settings_fingerprints(tmp_path):
    args = _inputs(
        tmp_path, git_is_dirty=True, git_dirty_fingerprint="c" * 64, settings_fingerprint="d" * 64
    )
    export_report(**args)
    args["metadata"]["settings_fingerprint"] = "e" * 64
    export_report(**args)
    assert len(json.loads((tmp_path / "history.json").read_text())) == 2


def test_expected_actual_layers_negative_discontinuity_and_fractional_time(tmp_path):
    args = _inputs(tmp_path, executed_at="2026-09-30T10:00:00.123456+09:00")
    args["raw"] = {
        "observations": [{"primary_state": "unknown"}, {"primary_state": "live_first_person"}],
        "visual_observations": [{"observation": "muzzle_flash"}, {"observation": None}],
        "visual_events": [{"type": "shot"}],
        "zone_resolutions": [{"zone_id": "a"}, {"zone_id": None}],
        "round_packages": [{}, {}],
    }
    args["trace"]["snapshots"] = [
        {"round_id": "r1", "time_sec": 4, "score_ally": 2, "score_enemy": 3}
    ]
    args["assertions"]["required_snapshots"] = [
        {
            "id": "snap1",
            "round_id": "r1",
            "time_sec": 4,
            "tolerance_sec": 0.1,
            "expected": {"score_ally": 1},
        }
    ]
    args["assertions"]["negative_assertions"] = [
        {"id": "neg1", "window": [1, 2]},
        {"id": "neg2", "window": [3, 4]},
    ]
    args["assertions"]["event_count_constraints"] = [
        {"id": "count1", "round_id": "r1", "type": "kill", "actor": "player", "min": 2, "max": 3}
    ]
    args["evaluation"].update(
        {
            "pass": False,
            "failure_count": 3,
            "failures": [
                "snapshot:snap1:score_ally",
                "negative_match:neg1",
                "discontinuity_span:neg2:feature_a",
            ],
        }
    )
    path = export_report(**args)
    data = json.loads(path.read_text())
    assert data["failures"][0]["expected"] == {"score_ally": 1}
    assert data["failures"][0]["actual"] == {"score_ally": 2, "score_enemy": 3, "time_sec": 4}
    assert data["failures"][0]["confidence"] is None
    assert data["hud"] == {
        "observations": 2,
        "unknown": 1,
        "states": 2,
        "detected_states": {"unknown": 1, "live_first_person": 1},
    }
    assert data["visual"] == {"observations": 2, "events": 1, "missing_expected": []}
    # Unknown free-text zone labels must not be copied into shared reports.
    assert data["map_zone"] == {"resolved": 1, "unknown": 1, "zones": []}
    assert data["round_package"]["rounds"] == 2
    assert data["negative"] == {"passed": 0, "failed": 2, "assertions": 2}
    assert data["discontinuity"]["violations"] == 1
    assert data["metadata"]["executed_at"] == "2026-09-30T10:00:00.123456+09:00"


def test_untrusted_strings_and_existing_history_are_rebuilt(tmp_path):
    args = _inputs(tmp_path, video_id="sk-proj-abcdefghijklmnop", git_is_dirty=False)
    args["metadata"]["evidence_files"] = ["report.json", "sk-proj-abcdefghijklmnop"]
    args["evaluation"]["failures"] = ["snapshot:snap1:secret-token"]
    args["assertions"]["required_snapshots"] = [
        {
            "id": "snap1",
            "round_id": "r1",
            "time_sec": 4,
            "tolerance_sec": 1,
            "expected": {"score_ally": "sk-proj-abcdefghijklmnop"},
        }
    ]
    args["output_dir"].mkdir(exist_ok=True)
    (args["output_dir"] / "history.json").write_text(
        json.dumps(
            [
                {
                    "history_key": "f" * 64,
                    "metadata": {"video_id": "sk-proj-abcdefghijklmnop", "secret": "LEAK_ME"},
                    "result": {"status": "pass", "private": "LEAK_ME"},
                    "failure_count": 0,
                    "extra": "LEAK_ME",
                }
            ]
        )
    )
    export_report(**args)
    serialized = "".join(p.read_text() for p in args["output_dir"].iterdir())
    assert "sk-proj-abcdefghijklmnop" not in serialized
    assert "LEAK_ME" not in serialized
    assert "secret-token" not in serialized
    data = json.loads((args["output_dir"] / "summary.json").read_text())
    assert data["evidence_files"] == ["report.json"]
