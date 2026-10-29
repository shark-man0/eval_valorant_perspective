from copy import deepcopy

import pytest
from test_shared_game_timeline import obs, replay

from valorant_ai_coach.temporal.game import observation
from valorant_ai_coach.temporal.map_projection import project_current_map


def marker(tick):
    sample = obs(tick)["sample"]
    candidates = [{"marker_id": "unqualified", "center_frame_px": [100, 100]}]
    return observation(
        sample=sample,
        producer="c" * 64,
        signals=[],
        context={"stream_kind": "map"},
        map_candidates=candidates,
        raw={
            "schema": "map_consumer_provisional_v1",
            "pool": {"candidates": candidates},
            "initial_candidate_index": 0,
        },
    )


def test_current_self_candidate_does_not_require_inventing_round_or_continuity():
    result = replay([obs(0, ["owner_hud"]), marker(0)])
    frame = result["frames"][0]
    assert frame["round"]["value"] == "UNKNOWN"
    assert frame["continuity"]["semantic"] == "UNKNOWN"
    assert frame["map"]["current_self_position_candidates"] == marker(0)["map_candidates"]
    assert frame["map"]["current_recorder_view_evidence_ids"]
    assert frame["map"]["temporal_path_eligible"] is False
    assert result["qualified_events"] == []


def test_carried_self_state_is_not_a_current_owner_measurement():
    result = replay([obs(0, ["buy", "owner_hud"]), marker(1)])
    frame = result["frames"][-1]
    assert frame["life"]["value"] == "ALIVE"
    assert frame["camera"]["value"] == "SELF"
    assert frame["map"]["current_self_position_candidates"] == []
    assert frame["map"]["current_recorder_view_evidence_ids"] == []


def test_current_spectator_conflict_or_terminal_round_blocks_position():
    for signals in (
        ["owner_hud", "spectator"],
        ["owner_hud", "death"],
        ["owner_hud", "downed"],
        ["owner_hud", "remote"],
        ["owner_hud", "result"],
        ["owner_hud", "intermission"],
        ["owner_hud", "buy", "result"],
    ):
        result = replay([obs(0, signals), marker(0)])
        assert result["frames"][0]["map"]["current_self_position_candidates"] == []


def test_current_decode_failure_cannot_support_map_candidate():
    result = replay([obs(0, ["owner_hud"], continuity={"decode_ok": False}), marker(0)])
    assert result["frames"][0]["map"]["current_self_position_candidates"] == []


def test_confirmed_break_has_current_evidence_but_no_path():
    result = replay(
        [obs(0, ["owner_hud"], continuity={"content_break_confirmed": True}), marker(0)]
    )
    frame = result["frames"][0]
    assert frame["map"]["current_self_position_candidates"]
    assert frame["map"]["temporal_path_eligible"] is False


def test_projection_keeps_native_candidates_and_missing_seconds_without_a_path():
    timeline = replay([obs(0, ["owner_hud"]), marker(0), marker(20)])
    original = deepcopy(timeline)
    result = project_current_map(timeline)
    assert result["summary"]["current_candidate_samples"] == 1
    assert result["seconds"][0]["position_status"] == "CANDIDATES"
    assert result["seconds"][1]["position_status"] == "UNKNOWN"
    assert result["seconds"][1]["native_Map_views"] == []
    assert result["seconds"][2]["position_status"] == "UNKNOWN"
    assert all(r["path"] is None for r in result["seconds"])
    assert all(r["semantic_continuity"] == "UNKNOWN" for r in result["rows"])
    assert result["rows"][0]["sample"] == marker(0)["sample"]
    assert result["rows"][0]["common_states"]["round"]["value"] == "UNKNOWN"
    assert result["formal_outputs"] == 0
    result["rows"][0]["marker_candidate_pool"].clear()
    assert timeline == original


def test_near_time_or_different_pixels_are_not_current_evidence_for_projection():
    timeline = replay([obs(0, ["owner_hud"]), marker(1)])
    timeline["frames"][-1]["map"]["current_recorder_view_evidence_ids"] = [
        timeline["observations"][0]["observation_id"]
    ]
    with pytest.raises(ValueError, match="current owner"):
        project_current_map(timeline)


def test_projection_rejects_changed_original_observation_digest():
    timeline = replay([obs(0, ["owner_hud"]), marker(0)])
    timeline["observations"][0]["signals"] = ["death"]
    with pytest.raises(ValueError, match="digest"):
        project_current_map(timeline)


def test_exact_pixel_alias_does_not_duplicate_native_Map_observation():
    owner = obs(0, ["owner_hud"], epoch="another")
    timeline = replay([owner, marker(0)], fuse_exact_native_evidence=True)
    result = project_current_map(timeline)
    assert len(result["rows"]) == result["summary"]["current_candidate_samples"] == 1
    assert result["rows"][0]["sample"] == marker(0)["sample"]


def test_projection_rejects_candidates_outside_exact_native_pool():
    timeline = replay([obs(0, ["owner_hud"]), marker(0)])
    timeline["frames"][0]["map"]["current_self_position_candidates"] = [{"marker_id": "invented"}]
    with pytest.raises(ValueError, match="exact native Map pool"):
        project_current_map(timeline)


def test_projection_CLI_admits_every_original_source_before_projection(tmp_path, monkeypatch):
    from test_shared_timeline_replay import policy_fixture, write

    from valorant_ai_coach.temporal.map_projection import main

    timeline = replay([obs(0, ["owner_hud"]), marker(0)])
    # A foreign observation hidden outside frame rows must still be rejected.
    timeline["observations"].append(obs(1, source="c"))
    policy = write(tmp_path / "policy.json", policy_fixture(tmp_path))
    source = write(tmp_path / "timeline.json", timeline)
    output = tmp_path / "out.json"
    monkeypatch.setattr(
        "sys.argv",
        [
            "map_projection", "--policy", str(policy), "--timeline", str(source),
            "--output", str(output),
        ],
    )
    with pytest.raises(ValueError, match="allowlist"):
        main()
    assert not output.exists()
