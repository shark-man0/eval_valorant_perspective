"""Advisory UI candidates cannot establish phase, life, ownership or events."""

from copy import deepcopy
from fractions import Fraction

import pytest

from tests.unit.test_development_timeline_application import make_timeline
from valorant_ai_coach.temporal.application import build_application_timeline
from valorant_ai_coach.temporal.evidence import freeze_native_sample
from valorant_ai_coach.temporal.game import observation
from valorant_ai_coach.temporal.hud_visibility import classify_words, visibility_summary


def words(*items, confidence=.95):
    return [{"text": s, "confidence": confidence} for s in items]


def menu():
    return classify_words(words("サイドアーム", "ライフル"), {
        "buy_menu_close_anchor_present": True,
        "buy_menu_close_anchor_present_confidence": .99})


def test_menu_and_tracker_require_independent_current_UI_support():
    assert [c["kind"] for c in menu()["candidates"]] == ["BUY_MENU"]
    assert not classify_words(words("サイドアーム", "ライフル"), {})["candidates"]
    assert not classify_words(words("VALORANT TRACKER"), {})["candidates"]
    tracker = classify_words(words("VALORANT TRACKER", "Live Match"), {})
    assert [c["kind"] for c in tracker["candidates"]] == ["TRACKER"]
    assert all(tracker[k] is False for k in ["phase_authority", "life_authority",
                                            "camera_authority", "Map_authority", "qualified"])


@pytest.mark.parametrize("confidence", [0, .84, True, float("nan"), float("inf"), 1.1])
def test_unaccepted_words_never_identify_a_tracker(confidence):
    result = classify_words(words("VALORANT TRACKER", "Live Match", confidence=confidence), {})
    assert result["status"] == "UNKNOWN" and not result["candidates"]
    assert result["unknown_possible"] and result["absence_proven"] is False


def fixture():
    timeline = make_timeline()
    source = {"video_id": "synthetic", "source_sha256": "a"*64, "physical_match_id": "p"}
    sample = {k: v for k, v in timeline["frames"][0]["sample"].items() if k != "sample_sha256"}
    sample.update(acquisition_id="visibility", native_epoch="visibility")
    row = observation(sample=freeze_native_sample(sample), producer="d"*64, signals=[],
        raw={"schema": "development_HUD_visibility_observation_v1",
             "hud_visibility": menu(), "formal_outputs": 0},
        context={"stream_kind": "hud_visibility"})
    return timeline, source, row


def build(timeline, source, rows=None):
    return build_application_timeline(timeline, source=source, duration=Fraction(7,2),
        origin=Fraction(51,10), hud_visibility_observations=rows)


def test_new_epoch_joins_exact_pixels_without_adding_state_or_ownership():
    timeline, source, row = fixture()
    original = deepcopy(timeline)
    before, after = build(timeline, source), build(timeline, source, [row])
    assert timeline == original
    assert before["native_frames"] == after["native_frames"]
    assert before["events"] == after["events"]
    for a, z in zip(before["seconds"], after["seconds"], strict=True):
        for field in ["round_state", "life_state", "camera_state", "round_number",
                      "hud_observations", "map_observations", "event_candidates", "sample_refs"]:
            assert a[field] == z[field]
    visibility = after["seconds"][0]["hud_visibility_observations"]
    assert visibility["candidates"][0]["kind"] == "BUY_MENU"
    assert visibility["recorder_ownership"] == "UNKNOWN"
    assert after["HUD_visibility_observation_links"][0]["state_authority"] is False
    assert not before["seconds"][0]["hud_visibility_observations"]["analysis_present"]


@pytest.mark.parametrize("field,value", [("native_pts_tick", 52),
    ("native_pixel_sha256", "f"*64), ("frame_size_px", [64,32]), ("native_time_base", "1/20")])
def test_nearby_or_changed_pixels_remain_unmatched(field, value):
    timeline, source, row = fixture()
    sample = {k: v for k,v in row["sample"].items() if k != "sample_sha256"}
    sample[field] = value
    changed = observation(sample=freeze_native_sample(sample), producer=row["producer_fingerprint"],
        signals=[], raw=row["raw"], context=row["context"])
    result = build(timeline, source, [changed])
    assert result["unmatched_HUD_visibility_observation_ids"] == [changed["observation_id"]]
    assert not any(v["hud_visibility_observations"]["analysis_present"] for v in result["seconds"])


def test_state_bearing_foreign_duplicate_and_authoritative_visibility_are_rejected():
    timeline, source, row = fixture()
    with pytest.raises(ValueError, match="Duplicate"):
        build(timeline, source, [row, row])
    for signals, raw, sample in [(["owner_hud"],row["raw"],row["sample"]),
        ([],{**row["raw"],"hud_visibility":{**menu(),"life_authority":True}},row["sample"]),
        ([],row["raw"],{**row["sample"],"source_id":"foreign"})]:
        sample = freeze_native_sample({k:v for k,v in sample.items() if k != "sample_sha256"})
        changed = observation(sample=sample, producer=row["producer_fingerprint"], signals=signals,
                              raw=raw, context=row["context"])
        with pytest.raises(ValueError):
            build(timeline, source, [changed])
    assert visibility_summary([])["reason"] == "NOT_ANALYSED"
