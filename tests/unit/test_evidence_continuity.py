from fractions import Fraction

import pytest

from tests.unit.test_shared_game_timeline import obs
from valorant_ai_coach.temporal.game import DevelopmentGameTimeline


def run(rows, enabled=True, **kwargs):
    engine = DevelopmentGameTimeline(evidence_continuity=enabled, **kwargs)
    for row in rows:
        engine.add(row)
    return engine.rebuild()


def at(second, signals=(), score=None, timer=None):
    context = {}
    if score is not None:
        context["score"] = list(score)
    if timer is not None:
        context["timer_seconds"] = timer
    return obs(second * 10, signals, context=context)


def values(result, domain):
    return [f[domain]["value"] for f in result["frames"]]


def test_same_score_bracket_keeps_the_measured_phase_and_retains_the_rule_estimate():
    rows = [at(0, ["active"], (3, 4))] + [at(s, score=(3, 4)) for s in range(1, 8)]
    rows += [at(8, ["active"], (3, 4))]
    before = run(rows, False)
    assert values(before, "round")[4] == "UNKNOWN"
    after = run(rows)
    assert values(after, "round") == ["ACTIVE"] * 9
    revised = after["frames"][4]["round"]
    assert revised["reason"] == "same_score_phase_bracket"
    assert revised["rule_estimate"]["value"] == "UNKNOWN"
    assert revised["origin"] == "evidence_continuity_projection"
    assert after["evidence_continuity_projection_history"]
    assert after["configuration"]["evidence_continuity"] == "development_evidence_continuity_v1"
    assert after["qualified_facts"] == after["qualified_events"] == []


def test_score_update_lag_keeps_the_last_seconds_before_it_undecided():
    rows = [at(0, ["active"], (3, 4))] + [at(s, score=(3, 4)) for s in range(1, 10)]
    rows += [at(s, score=(4, 4)) for s in (10, 11, 12)] + [at(13, ["result"], (4, 4))]
    result = run(rows)
    rounds = values(result, "round")
    # The decision may be displayed up to DECISION_DISPLAY_LEAD before the score.
    assert rounds[:6] == ["ACTIVE"] * 6
    assert rounds[6:10] == ["UNKNOWN"] * 4
    assert rounds[10:13] == ["ENDED"] * 3
    ends = [t for t in result["transitions"] if t["kind"] == "round_end"]
    # The existing score-update edge keeps its rule lower sample and is widened.
    assert len(ends) == 1
    assert ends[0]["rule_lower_sample"]["native_pts_tick"] == 90
    assert ends[0]["lower_sample"]["native_pts_tick"] == 50
    assert ends[0]["lower_sample_basis"] == "score_display_lead"
    assert values(run(rows, False), "round")[6] == "UNKNOWN"
    # Without an existing edge, the added candidate uses the same bounds.
    rows[-1] = at(13, ["buy"], (4, 4))
    added = [t for t in run(rows)["transitions"] if t.get("basis") == (
        "measured_active_phase_and_one_point_score_increment")]
    assert len(added) == 1
    assert added[0]["lower_sample"]["native_pts_tick"] == 50
    assert added[0]["upper_sample"]["native_pts_tick"] == 100
    assert added[0]["qualified"] is False
    # A measured ACTIVE cue closer to the update moves the lower bound up to it.
    rows[8] = at(8, ["active"], (3, 4))
    closer = [t for t in run(rows)["transitions"] if t.get("basis")]
    assert closer[0]["lower_sample"]["native_pts_tick"] == 80


def test_unread_or_misread_scores_never_bridge_a_bracket():
    # Seconds 1-2 are the engine's existing two-second carry; the rest is the bracket.
    misread = [at(0, ["active"], (3, 4))] + [at(s, score=(3, 4)) for s in range(1, 8)]
    misread[5] = at(5, score=(3, 5))
    misread.append(at(8, ["active"], (3, 4)))
    result = run(misread)
    # Nothing at or after the inconsistent reading is revised, no end is invented.
    assert values(result, "round")[3:6] == ["UNKNOWN"] * 3
    assert not [t for t in result["transitions"] if t.get("basis")]
    unread = [at(0, ["active"])] + [at(s) for s in range(1, 8)] + [at(8, ["active"])]
    assert values(run(unread), "round")[3:6] == ["UNKNOWN"] * 3


def test_decode_break_ends_a_continuity_segment():
    rows = [at(0, ["active"], (3, 4))] + [at(s, score=(3, 4)) for s in range(1, 10)]
    rows[5] = obs(50, context={"score": [3, 4]}, continuity={"decode_ok": False})
    rows.append(at(10, ["active"], (3, 4)))
    assert values(run(rows), "round")[3:5] == ["UNKNOWN", "UNKNOWN"]


def test_spectator_panel_during_a_round_is_not_alive_and_purchase_phase_is_alive():
    rows = [at(0, ["active", "owner_hud"], (1, 1)), at(1, ["active", "spectator"], (1, 1)),
            at(2, ["active"], (1, 1)), at(3, ["active", "spectator"], (1, 1))]
    result = run(rows)
    assert values(result, "life") == ["ALIVE", "DEAD", "DEAD", "DEAD"]
    assert result["frames"][1]["life"]["reason"] == "spectator_view_within_round"
    assert result["frames"][2]["life"]["reason"] == "dead_bracket_same_round"
    assert result["frames"][2]["camera"]["value"] == "SPECTATOR"
    assert values(run(rows, False), "life")[1:] == ["UNKNOWN"] * 3
    purchase = run([at(0, ["buy"], (1, 1)), at(1, ["buy", "spectator"], (1, 1))])
    assert values(purchase, "life") == ["ALIVE", "UNKNOWN"]


def test_dead_bracket_does_not_cross_a_round_or_a_current_owner_hud():
    crossing = [at(0, ["active", "spectator"], (1, 1)), at(1, score=(1, 1)),
                at(2, score=(1, 2)), at(3, ["active", "spectator"], (1, 2))]
    assert values(run(crossing), "life")[1:3] == ["UNKNOWN", "UNKNOWN"]
    owner = [at(0, ["active", "spectator"], (1, 1)), at(1, ["owner_hud"], (1, 1)),
             at(2, ["active", "spectator"], (1, 1))]
    assert values(run(owner), "life")[1] != "DEAD"


def test_higher_score_after_death_releases_a_current_owner_hud():
    rows = [at(0, ["buy", "owner_hud"], (0, 0)), at(1, ["active", "owner_hud"], (0, 0)),
            at(2, ["death", "spectator"], (0, 0)), at(3, ["result"], (0, 1))]
    rows += [at(s, score=(0, 1)) for s in range(4, 10)] + [at(10, ["active", "owner_hud"], (0, 1))]
    before = run(rows, False)
    assert before["frames"][-1]["life"]["reason"] == "return_edge_unobserved"
    after = run(rows)
    assert after["frames"][-1]["life"]["value"] == "ALIVE"
    assert after["frames"][-1]["life"]["reason"] == (
        "new_round_since_death_and_current_owner_hud")
    same_round = rows[:3] + [at(s, score=(0, 0)) for s in range(3, 10)]
    same_round.append(at(10, ["active", "owner_hud"], (0, 0)))
    assert run(same_round)["frames"][-1]["life"]["value"] == "UNKNOWN"


def test_start_bracket_from_result_to_active_is_narrowed_by_two_countdown_readings():
    rows = [at(0, ["result"], (1, 1))] + [at(s, score=(1, 1)) for s in range(1, 30)]
    rows += [at(30, ["active"], (1, 1), timer=99), at(31, ["active"], (1, 1), timer=98)]
    starts = [t for t in run(rows)["transitions"] if t["kind"] == "round_start"]
    assert len(starts) == 1
    start = starts[0]
    assert start["basis"].endswith("+active_countdown_projection")
    assert start["lower_sample"]["native_pts_tick"] == 280
    assert start["upper_sample"]["native_pts_tick"] == 300
    assert start["single_boundary_interval"]["lower_sample"]["native_pts_tick"] == 0
    single = rows[:-1]
    unsupported = [t for t in run(single)["transitions"] if t["kind"] == "round_start"]
    assert unsupported[0]["lower_sample"]["native_pts_tick"] == 0
    assert "countdown_projection" not in unsupported[0]


def test_existing_boundary_inside_the_interval_is_not_duplicated():
    rows = [at(0, ["buy"], (2, 2)), at(1, ["active"], (2, 2)), at(2, score=(2, 2)),
            at(3, ["active"], (2, 2))]
    starts = [t for t in run(rows)["transitions"] if t["kind"] == "round_start"]
    assert len(starts) == 1 and "basis" not in starts[0]


def test_offline_only_and_explicit_boolean():
    with pytest.raises(ValueError, match="offline"):
        DevelopmentGameTimeline(evidence_continuity=True, forward_only=True)
    with pytest.raises(ValueError):
        DevelopmentGameTimeline(evidence_continuity=1)  # type: ignore[arg-type]


def test_disabled_flag_keeps_the_previous_output_shape():
    rows = [at(0, ["active"], (3, 4)), at(1, score=(3, 4)), at(2, ["active"], (3, 4))]
    result = run(rows, False)
    assert "evidence_continuity" not in result["configuration"]
    assert "evidence_continuity_projection_history" not in result
    assert Fraction(result["frames"][1]["sample"]["native_pts_tick"], 10) == 1


def test_score_increase_alone_does_not_confirm_a_respawn():
    rows = [at(0, ["buy", "owner_hud"], (0, 0)), at(1, ["active", "owner_hud"], (0, 0)),
            at(2, ["death", "spectator"], (0, 0)), at(3, ["result"], (0, 1))]
    # Owner-like HUD while the Round is still decided (ENDED): no purchase phase
    # or Round start has been seen, so the recorder is not declared alive.
    rows += [at(s, score=(0, 1)) for s in range(4, 7)] + [at(7, ["result", "owner_hud"], (0, 1))]
    assert run(rows)["frames"][-1]["life"]["value"] != "ALIVE"


def test_countdown_later_in_the_round_narrows_both_bounds_and_fills_active():
    rows = [at(0, ["result"], (1, 1))] + [at(s, score=(1, 1)) for s in range(1, 30)]
    rows += [at(30, ["active"], (1, 1))] + [at(s, score=(1, 1)) for s in range(31, 40)]
    rows += [at(40, ["active"], (1, 1), timer=80), at(41, ["active"], (1, 1), timer=79)]
    result = run(rows)
    start = [t for t in result["transitions"] if t["kind"] == "round_start"][0]
    # 1:20 shown at second 40 puts the start at second 20.
    assert start["lower_sample"]["native_pts_tick"] == 190
    assert start["upper_sample"]["native_pts_tick"] == 210
    assert result["frames"][25]["round"]["value"] == "ACTIVE"
    assert result["frames"][25]["round"]["reason"] == "active_countdown_since_projected_start"


def bounds(event):
    return event["lower_sample"]["native_pts_tick"], event["upper_sample"]["native_pts_tick"]


def test_countdown_start_next_to_the_purchase_anchor_uses_that_anchor():
    rows = [at(0, ["buy"], (1, 1))] + [at(s, score=(1, 1)) for s in range(1, 15)]
    rows += [at(15, ["active"], (1, 1), timer=85), at(16, ["active"], (1, 1), timer=84)]
    start = [t for t in run(rows)["transitions"] if t["kind"] == "round_start"][0]
    assert bounds(start) == (0, 10)
    # A countdown placing the start before a measured purchase frame is rejected.
    rows = [at(10, ["buy"], (1, 1))] + [at(s, score=(1, 1)) for s in range(11, 20)]
    rows += [at(20, ["active"], (1, 1), timer=85), at(21, ["active"], (1, 1), timer=84)]
    start = [t for t in run(rows)["transitions"] if t["kind"] == "round_start"][0]
    assert "countdown_projection" not in start
    assert bounds(start) == (100, 200)


def test_revisions_keep_frames_map_and_edges_consistent():
    from valorant_ai_coach.temporal.evidence_continuity import consistency_violations

    rows = [at(0, ["active", "owner_hud"], (1, 1)), at(1, ["active", "spectator"], (1, 1))]
    rows += [at(s, score=(1, 1)) for s in range(2, 6)] + [at(6, ["active", "spectator"], (1, 1))]
    rows += [at(s, ["buy"], (1, 2)) for s in range(40, 43)]
    before = consistency_violations(run(rows, False))
    after = consistency_violations(run(rows))
    assert set(after.values()) == {0}
    # The default path already leaves stale carried edges; the pass archives them.
    assert all(after[k] <= before[k] for k in before)
    summary = run(rows)["evidence_continuity_summary"]
    assert summary["withdrawn_meaning"] == "abstention_not_a_verified_error_count"
    assert summary["revised_frames_by_rule"]
