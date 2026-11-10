from copy import deepcopy

from tests.unit.test_composite_view import cue, visual
from tests.unit.test_shared_game_timeline import obs
from valorant_ai_coach.temporal.game import DevelopmentGameTimeline, observation


def run(rows, enabled=True):
    engine = DevelopmentGameTimeline(practical_visual_state=enabled)
    for row in rows:
        engine.add(row)
    return engine.rebuild()


def self_hint(base):
    return observation(sample=base["sample"], producer="d" * 64, signals=[],
                       raw={"camera_hypothesis": "SELF", "current_HUD_component_supported": True,
                            "view_hp": {"display": "100", "confidence": .95}},
                       context={"stream_kind": "hud_learned_view_claim"})


def test_matching_agent_requires_current_HUD_not_first_frame_and_respects_spectator():
    anchor, hidden, spectator = obs(0, ["owner_hud"]), obs(40), obs(50, ["spectator"])
    rows = [anchor, visual(anchor, cue()), hidden, visual(hidden, cue()),
            self_hint(hidden), spectator, visual(spectator, cue()), self_hint(spectator)]
    before = run(rows, False)
    assert before["frames"][1]["camera"]["value"] == "UNKNOWN"
    after = run(rows)
    assert after["frames"][1]["camera"]["value"] == "SELF"
    assert after["frames"][1]["life"]["value"] == "ALIVE"
    assert after["frames"][-1]["camera"]["value"] == "SPECTATOR"
    assert after["frames"][1]["camera"]["rule_estimate"]["value"] == "UNKNOWN"
    assert after["qualified_facts"] == after["qualified_events"] == []
    assert run([hidden, visual(hidden, cue()), self_hint(hidden)])["frames"][0][
        "camera"]["value"] == "UNKNOWN"


def test_named_agent_difference_with_portrait_and_report_revises_current_camera():
    anchor, other = obs(0, ["owner_hud"]), obs(40, ["report"])
    first, second = cue(), cue()
    first["viewed_agent_candidates"] = [{"agent": "Jett", "score": .9}]
    second["viewed_agent_candidates"] = [{"agent": "Sova", "score": .9}]
    second["portrait_candidate"] = {"agent_candidates": [{"agent": "Sova", "score": .7}]}
    result = run([anchor, visual(anchor, first), other, visual(other, second)])
    assert result["frames"][-1]["camera"]["value"] == "SPECTATOR"
    assert result["frames"][-1]["life"]["value"] == "UNKNOWN"
    remote = obs(40, ["remote", "report"])
    guarded = run([anchor, visual(anchor, first), remote, visual(remote, second)])
    assert guarded["frames"][-1]["camera"]["value"] == "REMOTE"


def test_unread_confidence_is_abstention_instead_of_crash_or_self_promotion():
    anchor, hidden = obs(0, ["owner_hud"]), obs(40)
    hint = self_hint(hidden)
    hint["raw"]["view_hp"]["confidence"] = None
    hint = observation(sample=hidden["sample"], producer="d" * 64, signals=[], raw=hint["raw"])
    after = run([anchor, visual(anchor, cue()), hidden, visual(hidden, cue()), hint])
    assert after["frames"][-1]["camera"]["value"] == "UNKNOWN"


def test_round_visual_score_updates_shared_state_but_keeps_next_buy():
    a, b = obs(0, context={"score": [0, 0]}), obs(1, context={"score": [1, 0]})
    after = run([a, b])
    assert after["frames"][-1]["round"]["value"] == "ENDED"
    buy = obs(1, ["buy"], context={"score": [1, 0]})
    assert run([a, buy])["frames"][-1]["round"]["value"] == "BUY"


def test_match_result_not_source_end_and_display_persistence_is_one_candidate():
    rows = []
    for t in (0, 1, 2):
        base = obs(t)
        rows.append(observation(sample=base["sample"], producer="d" * 64,
                                signals=["buy"] if t == 1 else [],
                                raw={"screen_cues": {"match_result": {"visible": True}}}))
    after = run(rows)
    assert len([e for e in after["transitions"] if e["kind"] == "match_end"]) == 1
    without = deepcopy(rows[0])
    without = observation(sample=without["sample"], producer="d" * 64,
                          signals=["result"], raw={})
    assert not any(e["kind"] == "match_end" for e in run([without])["transitions"])


def test_barrier_loss_updates_round_but_blue_sky_persistence_and_epoch_do_not():
    def barrier(base, present):
        return observation(sample=base["sample"], producer="e" * 64, signals=[],
                           raw={"screen_cues": {"barrier": {
                               "present": present, "not_detected": not present,
                               "map_view_supported": True, "map_signature": [20] * 1024}}})
    buy, missing = obs(0, ["buy"]), obs(10)
    result = run([buy, barrier(buy, True), missing, barrier(missing, False)])
    assert result["frames"][-1]["round"]["value"] == "ACTIVE"
    assert result["frames"][-1]["round"]["reason"] == "observed_purchase_barrier_loss"
    assert any(e["kind"] == "round_start" for e in result["transitions"])
    unchanged = run([buy, barrier(buy, True), missing, barrier(missing, True)])
    assert unchanged["frames"][-1]["round"]["value"] != "ACTIVE"
    other = obs(10, epoch="other")
    assert run([buy, barrier(buy, True), other, barrier(other, False)])["frames"][-1][
        "round"]["value"] != "ACTIVE"


def test_map_ranking_uses_current_spectator_subject_without_recorder_ownership():
    from valorant_ai_coach.temporal.visual_state import _attach_map_view

    frame = {"sample": obs(0)["sample"], "camera": {"value": "SPECTATOR",
             "evidence_ids": ["view"]}, "life": {"value": "DEAD"},
             "map": {"current_self_position_candidates": [], "marker_ranking_hypotheses": {
                 "map_supplier_fingerprint": "pool", "evidence_ids": ["ranking"],
                 "camera_candidate": "UNKNOWN", "rankings": [
                     {"candidate_index": 0, "score": 1.2}]}}}
    _attach_map_view(frame, [{"producer_fingerprint": "pool", "observation_id": "map",
                             "map_candidates": [{"center_frame_px": [30, 40]}]}])
    hypothesis = frame["map"]["research_view_position_hypotheses"][0]
    assert "RECORDER_SELF" not in hypothesis["role_hypotheses"]
    assert hypothesis["camera_candidate"] == "SPECTATOR"
    assert hypothesis["ownership"] == "UNKNOWN" and not hypothesis["position_authority"]
    assert frame["map"]["current_self_position_candidates"] == []
