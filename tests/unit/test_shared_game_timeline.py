from copy import deepcopy
from fractions import Fraction

import pytest

from valorant_ai_coach.temporal.evidence import digest, freeze_native_sample
from valorant_ai_coach.temporal.game import DevelopmentGameTimeline, map_context, observation


def obs(tick, signals=(), *, epoch="e", source="a", continuity=None, context=None, maps=None):
    sample = freeze_native_sample(
        {
            "source_id": source,
            "source_sha256": source * 64,
            "acquisition_id": epoch,
            "native_epoch": epoch,
            "native_pts_tick": tick,
            "native_time_base": "1/10",
            "acquired_frame_sha256": digest([source, epoch, tick]),
            "native_pixel_sha256": digest([source, tick]),
            "frame_size_px": [1920, 1080],
        }
    )
    return observation(
        sample=sample,
        producer="b" * 64,
        signals=list(signals),
        raw={},
        continuity=continuity,
        context=context,
        map_candidates=maps,
    )


def replay(rows, **kwargs):
    engine = DevelopmentGameTimeline(**kwargs)
    for row in rows:
        engine.add(row)
    return engine.rebuild()


def test_round_and_life_episode_preserves_subsecond_edges():
    result = replay(
        [
            obs(0, ["buy", "owner_hud"]),
            obs(1, ["active", "owner_hud"]),
            obs(2, ["death", "spectator"]),
            obs(3, ["spectator"]),
            obs(4, ["result"]),
            obs(5, ["buy"]),
            obs(6, ["buy", "owner_hud"]),
        ]
    )
    assert result["frames"][2]["life"]["value"] == "DEAD"
    assert result["frames"][3]["camera"]["value"] == "SPECTATOR"
    assert result["frames"][-1]["life"]["value"] == "ALIVE"
    assert {t["kind"] for t in result["transitions"]} >= {
        "round_start",
        "round_end",
        "death",
        "spectator",
        "return",
    }
    assert result["seconds"][0]["life"]["within_second_states"] == ["ALIVE", "DEAD"]
    assert result["qualified_facts"] == result["qualified_events"] == []
    assert all(t["internal_game_event_time"] is None for t in result["transitions"])


def test_spectator_is_competing_death_hypothesis_without_direct_death():
    result = replay([obs(0, ["owner_hud"]), obs(1, ["spectator"])])
    assert result["frames"][-1]["life"]["value"] == "UNKNOWN"
    assert result["frames"][-1]["life"]["hypotheses"] == ["DEAD", "UNKNOWN"]
    assert result["frames"][-1]["camera"]["value"] == "SPECTATOR"
    assert result["frames"][-1]["transition_hypotheses"][0]["kind"] == "recorder_death"
    assert result["frames"][-1]["transition_hypotheses"][0]["qualified"] is False


def test_short_dropout_retains_hypothesis_but_not_current_map_position():
    result = replay([obs(0, ["owner_hud", "active"], maps=[{"zone": "candidate"}]), obs(1)])
    state = result["frames"][-1]
    assert state["life"]["value"] == "ALIVE"
    assert state["life"]["uncertainty"] == "continuation_unverified"
    assert state["map"]["candidates"] == []
    assert state["continuity"]["semantic"] == "UNKNOWN"


@pytest.mark.parametrize(
    "change",
    [
        {"epoch": "new"},
        {"source": "c"},
        {"continuity": {"decode_ok": False}},
        {"continuity": {"content_break_confirmed": True}},
        {"continuity": {"discontinuity": True}},
    ],
)
def test_reset_does_not_carry_across_break(change):
    result = replay([obs(0, ["owner_hud"]), obs(1, **change)])
    assert result["frames"][-1]["life"]["value"] == "UNKNOWN"
    assert result["frames"][-1]["continuity"]["carry_allowed"] is False


def test_long_gap_unknown_seconds_and_no_interpolated_event():
    result = replay([obs(0, ["owner_hud"]), obs(100, ["spectator"])])
    assert len(result["seconds"]) == 11
    assert sum(not r["observation_present"] for r in result["seconds"]) == 9
    assert result["transitions"] == []


def test_pixels_do_not_prove_edit_or_semantic_continuity():
    a, b = obs(0, ["owner_hud"]), obs(1)
    sample = deepcopy(b["sample"])
    del sample["sample_sha256"]
    sample["native_pixel_sha256"] = a["sample"]["native_pixel_sha256"]
    b = observation(sample=sample, producer="b" * 64, signals=[], raw={})
    state = replay([a, b])["frames"][-1]
    assert state["continuity"]["duplicate_pixels"] is True
    assert state["continuity"]["confirmed_cut"] is False
    assert state["continuity"]["semantic"] == "UNKNOWN"


def test_contradictory_ui_and_missing_return_do_not_assert_alive():
    result = replay([obs(0, ["owner_hud"]), obs(1, ["death"]), obs(2, ["owner_hud"])])
    assert result["frames"][-1]["life"]["reason"] == "return_edge_unobserved"
    conflict = replay([obs(0, ["owner_hud", "spectator"])])["frames"][0]
    assert conflict["camera"]["value"] == "UNKNOWN"


def test_report_only_is_not_death_and_report_missing_hud_withholds_stale_alive():
    result = replay(
        [obs(0, ["owner_hud"]), obs(1, ["report"]), obs(2, ["report", "hud_not_detected"])]
    )
    assert result["frames"][1]["life"]["value"] == "ALIVE"
    assert result["frames"][2]["life"]["value"] == "UNKNOWN"
    assert not any(t["kind"] == "death" for t in result["transitions"])


def test_future_result_revises_unconfirmed_score_boundary():
    engine = DevelopmentGameTimeline()
    for row in [
        obs(0, ["active"], context={"score": [1, 1]}),
        obs(1, ["active"], context={"score": [2, 1]}),
    ]:
        engine.add(row)
    first = engine.rebuild()
    assert first["frames"][-1]["round"]["value"] == "ACTIVE"
    assert first["boundary_candidates"][0]["status"] == "pending"
    engine.add(obs(2, ["result"], context={"score": [2, 1]}))
    second = engine.rebuild()
    assert second["frames"][1]["round"]["value"] == "ENDED"
    assert second["boundary_candidates"][0]["status"] == "context_supported"
    assert (
        first["boundary_candidates"][0]["candidate_id"]
        == second["boundary_candidates"][0]["candidate_id"]
    )
    assert second["revision_history"][-1]["revised_sample_ids"]
    assert second["frames"][1]["round"]["evidence_ids"][-1:]


def test_detached_outputs_cannot_mutate_ledger_and_map_context_is_unqualified():
    engine = DevelopmentGameTimeline()
    row = obs(0, ["owner_hud", "buy"])
    engine.add(row)
    row["signals"].append("death")
    first = engine.rebuild()
    first["frames"][0]["life"]["value"] = "DEAD"
    second = engine.rebuild()
    assert second["frames"][0]["life"]["value"] == "ALIVE"
    context = map_context(second["frames"][0], producer_fingerprint="d" * 64, revision="1")
    assert context["source_continuity"] == "UNKNOWN"
    assert context["formal_outputs"] == 0
    assert context["context_sha256"] == digest(
        {k: v for k, v in context.items() if k != "context_sha256"}
    )


def test_exact_timebase_and_observation_validation():
    bad = obs(1)
    bad["sample"]["native_pts_tick"] = True
    with pytest.raises(ValueError):
        replay([bad])
    with pytest.raises(ValueError):
        DevelopmentGameTimeline(max_carry_seconds=Fraction(0))
    a, b = obs(0), obs(0)
    del b["sample"]["sample_sha256"]
    b["sample"]["native_pixel_sha256"] = "e" * 64
    b = observation(sample=b["sample"], producer="c" * 64, signals=[], raw={})
    with pytest.raises(ValueError, match="Conflicting pixels"):
        replay([a, b])


def test_observed_active_countdown_is_not_lost_below_buy_clock_range():
    result = replay(
        [
            obs(0, ["active"], context={"score": [1, 1], "timer_seconds": 46}),
            obs(10, context={"score": [1, 1], "timer_seconds": 45}),
            obs(20, context={"score": [1, 1], "timer_seconds": 44}),
            obs(21, ["result"], context={"score": [2, 1]}),
        ]
    )
    assert result["frames"][2]["round"]["value"] == "ACTIVE"
    assert sum(t["kind"] == "round_end" for t in result["transitions"]) == 1


def test_positive_spectator_ui_survives_report_and_missing_shared_hud():
    state = replay([obs(0, ["spectator", "report", "hud_not_detected"])])["frames"][0]
    assert state["camera"]["value"] == "SPECTATOR"
    assert state["life"]["value"] == "UNKNOWN"


def test_downed_latch_never_becomes_dead_due_to_a_dropout():
    result = replay([obs(0, ["downed"]), obs(10), obs(20), obs(30)])
    assert all(f["life"]["value"] == "DOWNED" for f in result["frames"])


def test_unread_intermediate_score_preserves_actual_before_witness():
    result = replay(
        [
            obs(0, context={"score": [1, 1]}),
            obs(1),
            obs(2, context={"score": [2, 1]}),
            obs(3, ["result"]),
        ]
    )
    ends = [t for t in result["transitions"] if t["kind"] == "round_end"]
    assert len(ends) == 1
    assert ends[0]["lower_sample"]["native_pts_tick"] == 0
    assert ends[0]["upper_sample"]["native_pts_tick"] == 2
    assert result["frames"][2]["round"]["origin"] == "temporal_inference"


def test_common_source_clock_retains_parallel_epochs_and_unknown_gap():
    result = replay(
        [
            obs(0, ["owner_hud"], epoch="a"),
            obs(1, ["owner_hud"], epoch="b"),
            obs(30, ["spectator"], epoch="c"),
        ]
    )
    assert len(result["seconds"]) == 4
    assert len(result["seconds"][0]["acquisition_views"]) == 2
    assert result["seconds"][1]["observation_present"] is False
    assert result["seconds"][1]["life"]["value"] == "UNKNOWN"
    assert result["seconds"][3]["camera"]["value"] == "SPECTATOR"
    assert len(result["acquisition_seconds"]) == 3


def test_missing_hud_packet_does_not_reset_on_map_only_frame():
    result = replay(
        [
            obs(0, ["owner_hud"], context={"stream_kind": "hud"}),
            obs(1, context={"stream_kind": "map"}),
        ]
    )
    assert result["frames"][1]["life"]["value"] == "ALIVE"
    assert result["frames"][1]["continuity"]["carry_allowed"] is True


def test_changed_hud_configuration_after_missing_packet_resets_state():
    row = obs(2, context={"stream_kind": "hud", "profile_fingerprint": "d" * 64})
    result = replay(
        [
            obs(0, ["owner_hud"], context={"stream_kind": "hud", "profile_fingerprint": "c" * 64}),
            obs(1, context={"stream_kind": "map"}),
            row,
        ]
    )
    assert result["frames"][2]["life"]["value"] == "UNKNOWN"
    assert result["frames"][2]["continuity"]["reason"] == "producer_or_profile_change"


def test_future_result_does_not_corroborate_across_changed_profile():
    result = replay(
        [
            obs(0, ["active"], context={"score": [1, 1]}),
            obs(1, ["active"], context={"score": [2, 1]}),
            obs(2, ["result"], context={"profile_fingerprint": "e" * 64}),
        ]
    )
    assert result["boundary_candidates"][0]["status"] == "pending"


def test_overlapping_round_evidence_across_acquisitions_is_not_counted_independent():
    result = replay(
        [
            obs(0, ["buy"], epoch="a"),
            obs(1, ["active"], epoch="a"),
            obs(0, ["buy"], epoch="b"),
            obs(1, ["active"], epoch="b"),
        ]
    )
    assert sum(t["kind"] == "round_start" for t in result["transitions"]) == 2
    assert len(result["round_candidate_groups"]) == 1
    assert len(result["round_candidate_groups"][0]["members"]) == 2
    assert "not_verified" in result["round_candidate_groups"][0]["semantics"]


def test_empty_map_measurement_is_distinct_from_no_map_observation():
    row = observation(
        sample=obs(0)["sample"],
        producer="c" * 64,
        signals=[],
        raw={"schema": "map_consumer_provisional_v1"},
    )
    state = replay([row])["frames"][0]["map"]
    assert state["observation_present"] is True
    assert state["status"] == "UNKNOWN"
    assert state["zone_candidates"] == state["marker_associations"] == []


def test_alive_self_context_does_not_assign_unbound_pool_markers_to_recorder():
    candidates = [{"index": 0}, {"index": 1}]
    unbound = obs(0, ["owner_hud", "buy"], maps=candidates)
    state = replay([unbound])["frames"][0]["map"]
    assert state["candidates"] == candidates
    assert state["current_self_position_candidates"] == []
    bound = observation(
        sample=unbound["sample"],
        producer="c" * 64,
        signals=["owner_hud", "buy"],
        raw={
            "schema": "map_consumer_provisional_v1",
            "initial_candidate_index": 1,
            "pool": {"candidates": candidates},
        },
        map_candidates=candidates,
    )
    assert replay([bound])["frames"][0]["map"]["current_self_position_candidates"] == [
        candidates[1]
    ]


def test_returned_native_sample_cannot_rewrite_the_evidence_ledger():
    engine = DevelopmentGameTimeline()
    row = obs(0, ["buy"])
    engine.add(row)
    first = engine.rebuild()
    first["frames"][0]["sample"]["source_sha256"] = "e" * 64
    first["frames"][0]["sample"]["frame_size_px"][0] = 1
    second = engine.rebuild()
    assert second["frames"][0]["sample"]["source_sha256"] == "a" * 64
    assert second["frames"][0]["sample"]["frame_size_px"] == [1920, 1080]


def test_owner_return_in_same_buy_phase_does_not_manufacture_next_round():
    result = replay(
        [obs(0, ["buy", "owner_hud"]), obs(1, ["buy", "death"]), obs(2, ["buy", "owner_hud"])]
    )
    assert result["frames"][-1]["life"]["value"] == "UNKNOWN"
    assert not any(t["kind"] == "return" for t in result["transitions"])


def test_first_positive_self_observation_in_next_buy_phase_can_support_return():
    result = replay(
        [
            obs(0, ["buy", "owner_hud"]),
            obs(1, ["active", "owner_hud"]),
            obs(2, ["death", "spectator"]),
            obs(3, ["result"]),
            obs(4, ["buy", "owner_hud"]),
        ]
    )
    assert result["frames"][-1]["life"]["value"] == "ALIVE"
    assert sum(t["kind"] == "return" for t in result["transitions"]) == 1


def test_unresolved_return_preserves_downed_hypothesis():
    state = replay([obs(0, ["downed"]), obs(1, ["owner_hud"])])["frames"][-1]
    assert state["life"]["value"] == "UNKNOWN"
    assert "DOWNED" in state["life"]["hypotheses"]


def test_conflicting_revival_observation_does_not_clear_death_latch():
    result = replay([obs(0, ["death"]), obs(1, ["owner_hud", "revival", "death"]), obs(2)])
    assert not any(t["kind"] == "return" for t in result["transitions"])
    assert result["frames"][-1]["life"]["value"] == "DEAD"


def test_later_result_does_not_erase_current_conflicting_round_observation():
    result = replay(
        [
            obs(0, ["active"], context={"score": [1, 1]}),
            obs(1, ["active", "buy"], context={"score": [2, 1]}),
            obs(2, ["result"], context={"score": [2, 1]}),
        ]
    )
    state = result["frames"][1]["round"]
    assert state["value"] == "UNKNOWN"
    assert set(state["hypotheses"]) == {"ACTIVE", "BUY", "ENDED"}
