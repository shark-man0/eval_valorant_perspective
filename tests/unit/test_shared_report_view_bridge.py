"""Current evidence and two bounded anchors never qualify identity or events."""

from copy import deepcopy

import pytest
from test_shared_game_timeline import obs, replay

from valorant_ai_coach.temporal.game import DevelopmentGameTimeline, observation


def span(*, change=None, offset=0, source="a", end=8):
    rows = []
    for second in range(end + 1):
        altered = change or {}
        kwargs = altered.get("transport", {}) if second >= 4 else {}
        actual_source = kwargs.get("source", source)
        kwargs = {k: v for k, v in kwargs.items() if k != "source"}
        score = altered.get("score", [0, 0]) if second >= 4 else [0, 0]
        signals = ["buy", "report"] if second in {0, end} else ["report"]
        if second == 4:
            signals += altered.get("signals", [])
        base = obs((second + offset) * 10, signals, source=actual_source,
                   context={"stream_kind": "hud", "score": score}, **kwargs)
        raw = {"camera_hypothesis": "SELF", "current_HUD_component_supported": True,
               "owner_hypothesis_exclusions": ["combat_report_visible"],
               "owned_verb_phrase": None, "view_hp": {"display": "100", "confidence": .95}}
        if second == 4:
            raw.update(altered.get("raw", {}))
        view = observation(
            sample=base["sample"], producer=altered.get("producer", "c" * 64)
            if second >= 4 else "c" * 64,
            signals=["owner_hud"] if second in {0, end} else [], raw=raw,
            context={"stream_kind": "view", "unqualified_view_model": True},
            continuity=kwargs.get("continuity"),
        )
        rows += [base, view]
    return rows


def test_current_pixels_and_two_anchors_revise_only_weak_view_estimates():
    rows = span()
    saved = deepcopy(rows)
    before = replay(rows)
    after = replay(rows, report_view_bridge=True)
    assert before["frames"][4]["life"]["value"] == "UNKNOWN"
    frame = after["frames"][4]
    assert frame["life"]["value"] == "ALIVE" and frame["camera"]["value"] == "SELF"
    assert frame["life"]["forward_estimate"] == before["frames"][4]["life"]
    assert "DEAD" in frame["life"]["hypotheses"]
    assert {"SPECTATOR", "REMOTE", "UNKNOWN"} <= set(frame["camera"]["hypotheses"])
    assert frame["life"]["uncertainty"] == "unqualified_report_view_continuation"
    assert after["transitions"] == before["transitions"]
    assert after["boundary_candidates"] == before["boundary_candidates"]
    assert [f["map"] for f in before["frames"]] == [f["map"] for f in after["frames"]]
    assert [f["round_token"] for f in before["frames"]] == [
        f["round_token"] for f in after["frames"]]
    assert all(not h["Map_authority"] and not h["qualified"]
               for h in after["report_view_projection_history"])
    assert after["qualified_facts"] == after["qualified_events"] == []
    assert rows == saved


@pytest.mark.parametrize("signal", [
    "spectator", "remote", "death", "downed", "revival",
    "recorder_elimination_display", "result", "intermission",
])
def test_explicit_contrary_current_evidence_rejects_the_span(signal):
    result = replay(span(change={"signals": [signal]}), report_view_bridge=True)
    assert result["report_view_projection_history"] == []


@pytest.mark.parametrize("change", [
    {"transport": {"epoch": "new"}},
    {"transport": {"source": "d"}},
    {"transport": {"continuity": {"decode_ok": False}}},
    {"transport": {"continuity": {"content_break_confirmed": True}}},
    {"producer": "d" * 64},
    {"score": [1, 0]},
    {"signals": ["active"]},  # measured progress then a different BUY token
    {"raw": {"camera_hypothesis": "UNKNOWN"}},
    {"raw": {"current_HUD_component_supported": False}},
    {"raw": {"owner_hypothesis_exclusions": ["combat_report_visible", "remote_control_candidate"]}},
    {"raw": {"owned_verb_phrase": {"accepted": True}}},
    {"raw": {"view_hp": {"display": "0", "confidence": .99}}},
])
def test_reset_conflict_and_unsupported_current_view_do_not_fill_unknowns(change):
    result = replay(span(change=change), report_view_bridge=True)
    assert result["report_view_projection_history"] == []


@pytest.mark.parametrize("hp", [None, {"display": "100", "confidence": .89},
                              {"display": "100", "confidence": True}])
def test_missing_hp_is_not_negative_but_that_frame_stays_unknown(hp):
    result = replay(span(change={"raw": {"view_hp": hp}}), report_view_bridge=True)
    assert result["frames"][4]["life"]["value"] == "UNKNOWN"
    assert result["frames"][5]["life"]["value"] == "ALIVE"


def test_no_future_anchor_and_long_gaps_do_not_create_self():
    for rows in [span()[:-2], span(end=12)]:
        result = replay(rows, report_view_bridge=True)
        assert result["report_view_projection_history"] == []


def test_source_and_absolute_pts_do_not_choose_the_predicted_state():
    a = replay(span(), report_view_bridge=True)
    b = replay(span(offset=100, source="d"), report_view_bridge=True)
    assert [(f["life"]["value"], f["camera"]["value"]) for f in a["frames"]] == [
        (f["life"]["value"], f["camera"]["value"]) for f in b["frames"]]


def test_future_projection_requires_explicit_offline_configuration():
    with pytest.raises(ValueError, match="offline"):
        DevelopmentGameTimeline(report_view_bridge=True, forward_only=True)
    with pytest.raises(ValueError, match="explicit"):
        DevelopmentGameTimeline(report_view_bridge=1)


def test_retracting_future_view_revises_candidate_back_to_unknown():
    rows = span()
    engine = DevelopmentGameTimeline(report_view_bridge=True)
    for row in rows:
        engine.add(row)
    result = engine.rebuild()
    sample = result["frames"][4]["sample"]["sample_sha256"]
    assert result["frames"][4]["life"]["value"] == "ALIVE"
    engine.retract(rows[-1]["observation_id"])
    result = engine.rebuild()
    assert result["frames"][4]["life"]["value"] == "UNKNOWN"
    assert sample in result["revision_history"][-1]["revised_sample_ids"]


@pytest.mark.parametrize("signal", ["revival", "recorder_elimination_display"])
def test_life_edge_at_future_anchor_cannot_rewrite_the_preceding_gap(signal):
    rows = span()
    base = rows[-2]
    rows[-2] = observation(
        sample=base["sample"], producer=base["producer_fingerprint"],
        signals=[*base["signals"], signal], context=base["context"], raw=base["raw"],
    )
    result = replay(rows, report_view_bridge=True)
    assert result["frames"][-1]["life"]["value"] == "ALIVE"
    assert result["frames"][4]["life"]["value"] == "UNKNOWN"
    assert result["report_view_projection_history"] == []
