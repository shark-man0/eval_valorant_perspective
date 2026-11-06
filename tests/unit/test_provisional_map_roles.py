from copy import deepcopy
from fractions import Fraction

import pytest
from test_shared_game_timeline import obs, replay

from valorant_ai_coach.rules.development_timeline import evaluation_package
from valorant_ai_coach.temporal.adapters import map_packet
from valorant_ai_coach.temporal.application import build_application_timeline
from valorant_ai_coach.temporal.evidence import digest
from valorant_ai_coach.temporal.game import observation
from valorant_ai_coach.temporal.map_projection import project_current_map


def weak_self(tick=0, **kwargs):
    base = obs(tick, ["owner_hud"], **kwargs)
    return observation(
        sample=base["sample"], producer="c" * 64, signals=base["signals"],
        context={"unqualified_view_model": True}, continuity=base["continuity"],
        raw={"camera_hypothesis": "SELF", "current_HUD_component_supported": True,
             "owner_hypothesis_exclusions": [], "owned_verb_phrase": None,
             "view_hp": {"display": "100", "confidence": .95}},
    )


def packet(tick=0, **kwargs):
    sample = obs(tick, **kwargs)["sample"]
    candidates = [{"candidate_id": "left", "center_frame_px": [10, 10]},
                  {"candidate_id": "right", "center_frame_px": [30, 30]}]
    return seal({
        "schema": "map_consumer_provisional_v1", "sample": sample,
        "pool": {"sample": sample, "pool_sha256": "d" * 64, "candidates": candidates},
        "ui": {"sample_sha256": sample["sample_sha256"], "pool_sha256": "d" * 64,
               "feature_fingerprint": "e" * 64, "rows": [
                   {"candidate_index": 0, "score": .1}, {"candidate_index": 1, "score": 1.2}],
               "selected_index": 1, "status": "highlighted_marker_candidate",
               "qualification": "development_only", "ownership": "UNKNOWN", "formal_outputs": 0},
        "reference_context_fingerprint": "f" * 64, "initial_candidate_index": 0,
        "qualification": "development_only", "ownership": "UNKNOWN", "formal_outputs": 0,
    })


def seal(value):
    value["observation_sha256"] = digest(
        {k: v for k, v in value.items() if k != "observation_sha256"}
    )
    return value


def hypotheses(timeline):
    return timeline["frames"][-1]["map"].get("provisional_recorder_position_hypotheses", [])


def test_weak_current_self_and_highlight_restore_only_a_separate_role_hypothesis():
    rows = [weak_self(), map_packet(packet())]
    before = replay(rows)
    after = replay(rows, provisional_map_roles=True)
    proposal = hypotheses(after)[0]
    # Ranking uses current UI; the old reference-dependent initial choice is opposite.
    assert proposal["candidate"] == packet()["pool"]["candidates"][1]
    assert proposal["candidate_role"] == "RECORDER_SELF"
    assert "VIEWED_PLAYER" in proposal["role_hypotheses"]
    assert proposal["ownership"] == "UNKNOWN"
    assert proposal["qualified"] is proposal["position_authority"] is False
    assert after["frames"][0]["map"]["current_self_position_candidates"] == []
    for old, new in zip(before["frames"], after["frames"], strict=True):
        comparable = deepcopy(new)
        comparable["map"].pop("provisional_recorder_position_hypotheses")
        assert comparable == old
    for key in ["observations", "transitions", "boundary_candidates", "seconds"]:
        assert before[key] == after[key]
    assert after["qualified_facts"] == after["qualified_events"] == []


@pytest.mark.parametrize("signal", [
    "spectator", "remote", "death", "downed", "revival", "ability_return",
    "recorder_elimination_display", "hud_not_detected", "result", "intermission",
])
def test_contrary_current_evidence_blocks_highlight_attribution(signal):
    result = replay([weak_self(), map_packet(packet()), obs(0, [signal])],
                    provisional_map_roles=True)
    assert not hypotheses(result)
    assert result["frames"][0]["map"]["candidates"]


@pytest.mark.parametrize("change", [
    "carried", "unknown_camera", "report", "hp_zero", "low_hp_confidence", "decode",
    "no_highlight", "tie", "duplicate_index", "wrong_index", "pool_binding", "sample_binding",
    "epoch_without_fusion", "different_pixels", "different_time", "different_source",
])
def test_missing_ambiguous_or_unbound_current_evidence_preserves_abstention(change):
    view, p = weak_self(), packet()
    fusion = True
    if change == "carried":
        p = packet(10)
    elif change == "unknown_camera":
        view["raw"]["camera_hypothesis"] = "UNKNOWN"
    elif change == "report":
        view["raw"]["owner_hypothesis_exclusions"] = ["combat_report_visible"]
    elif change == "hp_zero":
        view["raw"]["view_hp"]["display"] = "0"
    elif change == "low_hp_confidence":
        view["raw"]["view_hp"]["confidence"] = .3
    elif change == "decode":
        view["continuity"]["decode_ok"] = False
    elif change == "no_highlight":
        p["ui"]["selected_index"] = None
    elif change == "tie":
        p["ui"]["rows"][0]["score"] = 1.2
    elif change == "duplicate_index":
        p["ui"]["rows"].append(p["ui"]["rows"][0])
    elif change == "wrong_index":
        p["ui"]["selected_index"] = 0
    elif change == "pool_binding":
        p["ui"]["pool_sha256"] = "0" * 64
    elif change == "sample_binding":
        p["ui"]["sample_sha256"] = "0" * 64
    elif change == "epoch_without_fusion":
        p, fusion = packet(epoch="other"), False
    elif change == "different_pixels":
        p = packet(epoch="other")
        p["sample"]["native_pixel_sha256"] = "0" * 64
        from valorant_ai_coach.temporal.evidence import freeze_native_sample
        p["sample"].pop("sample_sha256")
        p["sample"] = freeze_native_sample(p["sample"])
        p["pool"]["sample"] = p["sample"]
        p["ui"]["sample_sha256"] = p["sample"]["sample_sha256"]
    elif change == "different_time":
        p = packet(1)
    elif change == "different_source":
        p = packet(source="b")
    # Rebuild observations after changing the test's supplier inputs.
    view = observation(sample=view["sample"], producer=view["producer_fingerprint"],
                       signals=view["signals"], raw=view["raw"], context=view["context"],
                       continuity=view["continuity"])
    result = replay([view, map_packet(seal(p))], provisional_map_roles=True,
                    fuse_exact_native_evidence=fusion)
    assert all(not f["map"]["provisional_recorder_position_hypotheses"] for f in result["frames"])


def test_exact_pixel_alias_keeps_original_samples_and_exports_to_application_and_evaluation():
    timeline = replay([weak_self(epoch="view"), map_packet(packet())],
                      fuse_exact_native_evidence=True, provisional_map_roles=True)
    projection = project_current_map(timeline)
    assert len(projection["rows"]) == 1
    assert len(projection["rows"][0]["provisional_recorder_position_hypotheses"]) == 1
    assert projection["rows"][0]["current_position_hypotheses"] == []
    bundle = build_application_timeline(
        timeline, source={"video_id": "a", "source_sha256": "a" * 64,
                          "physical_match_id": "synthetic"},
        duration=Fraction(2), origin=Fraction(0),
    )
    row = bundle["seconds"][0]
    assert len(row["map_observations"]["provisional_recorder_position_hypotheses"]) == 1
    assert not bundle["seconds"][1]["map_observations"]["provisional_recorder_position_hypotheses"]
    package = evaluation_package(bundle, 0, 2)
    assert package["development_timeline"][0]["map_observations"] == row["map_observations"]
    assert package["deterministic_facts"] == package["events"] == []
    corrupted = deepcopy(timeline)
    for frame in corrupted["frames"]:
        proposed = frame["map"]["provisional_recorder_position_hypotheses"][0]
        proposed["candidate"] = {"invented": True}
    with pytest.raises(ValueError, match="Map role evidence"):
        project_current_map(corrupted)


def test_retracting_current_view_removes_proposal_and_detached_outputs_are_safe():
    from valorant_ai_coach.temporal.game import DevelopmentGameTimeline
    with pytest.raises(ValueError):
        DevelopmentGameTimeline(provisional_map_roles="true")
    engine = DevelopmentGameTimeline(provisional_map_roles=True)
    view = weak_self()
    engine.add(view)
    engine.add(map_packet(packet()))
    result = engine.rebuild()
    hypotheses(result)[0]["candidate"].clear()
    assert hypotheses(engine.rebuild())[0]["candidate"]
    engine.retract(view["observation_id"])
    assert hypotheses(engine.rebuild()) == []
