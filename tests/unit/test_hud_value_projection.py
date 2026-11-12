from copy import deepcopy
from fractions import Fraction

import pytest
from test_development_timeline_application import make_timeline

from valorant_ai_coach.temporal.application import build_application_timeline
from valorant_ai_coach.temporal.evidence import freeze_native_sample
from valorant_ai_coach.temporal.game import observation
from valorant_ai_coach.temporal.hud_values import VERSION


def value_row(sample, **changes):
    sample = {k: v for k, v in sample.items() if k != "sample_sha256"}
    sample.update(acquisition_id="values", native_epoch="values", **changes)
    return observation(
        sample=freeze_native_sample(sample), producer="d" * 64, signals=[],
        context={"stream_kind": "hud_values"},
        raw={"schema": VERSION, "ownership": "UNKNOWN", "formal_outputs": 0,
             "hud_value_measurements": [
                 {"name": "armor", "value": 25, "confidence": .95, "status": "CANDIDATE"}]},
    )


def build(timeline, extra=None):
    return build_application_timeline(
        timeline, source={"video_id": "synthetic", "source_sha256": "a" * 64,
                          "physical_match_id": "physical"},
        duration=Fraction(7, 2), origin=Fraction(51, 10), hud_value_observations=extra,
    )


def test_value_only_epoch_does_not_create_UNKNOWN_state_lanes_or_attribute_spectator_HUD():
    timeline = make_timeline()
    original = deepcopy(timeline)
    # This is an observed spectator frame. Armor is viewed HUD, not recorder state.
    sample = timeline["frames"][2]["sample"]
    row = value_row(sample)
    before, after = build(timeline), build(timeline, [row])
    assert timeline == original
    assert after["native_frames"] == before["native_frames"]
    assert after["events"] == before["events"]
    for old, new in zip(before["seconds"], after["seconds"], strict=True):
        for field in old.keys() - {"hud_observations", "evidence_refs"}:
            assert old[field] == new[field]
        assert "HUD_value_sample_refs" in new
    selected = after["seconds"][2]
    assert selected["life_state"]["value"] == "DEAD"
    assert selected["camera_state"]["value"] == "SPECTATOR"
    assert selected["hud_observations"]["armor"]["candidates"][0]["value"] == 25
    assert "recorder_ownership_unresolved" in (
        selected["hud_observations"]["armor"]["candidates"][0]["subject"]
    )
    assert after["HUD_value_observation_links"][0]["original_sample"] == row["sample"]
    assert after["HUD_value_observation_links"][0]["matched_native_sample_refs"] == [
        sample["sample_sha256"]]


@pytest.mark.parametrize("change", ["time", "pixels", "size", "decode"])
def test_nearby_or_failed_values_remain_unmatched_without_changing_any_state(change):
    timeline = make_timeline()
    s = timeline["frames"][0]["sample"]
    kwargs = {"time": {"native_pts_tick": s["native_pts_tick"] + 1},
              "pixels": {"native_pixel_sha256": "0" * 64},
              "size": {"frame_size_px": [64, 64]}, "decode": {}}[change]
    row = value_row(s, **kwargs)
    if change == "decode":
        row = observation(sample=row["sample"], producer=row["producer_fingerprint"], signals=[],
                          context=row["context"], raw=row["raw"], continuity={"decode_ok": False})
    bundle = build(timeline, [row])
    assert bundle["unmatched_HUD_value_observation_ids"] == [row["observation_id"]]
    assert not bundle["HUD_value_observation_links"]
    assert all(not r["hud_observations"]["armor"]["candidates"] for r in bundle["seconds"])
    assert row["observation_id"] in bundle["observations"]


def test_duplicate_foreign_or_state_bearing_rows_are_rejected():
    timeline = make_timeline()
    row = value_row(timeline["frames"][0]["sample"])
    with pytest.raises(ValueError, match="Duplicate"):
        build(timeline, [row, row])
    foreign = value_row(timeline["frames"][0]["sample"], source_id="other")
    with pytest.raises(ValueError, match="same-Source"):
        build(timeline, [foreign])
    state_claim = observation(sample=row["sample"], producer=row["producer_fingerprint"],
                              context=row["context"], signals=["owner_hud"], raw=row["raw"])
    with pytest.raises(ValueError, match="value-only"):
        build(timeline, [state_claim])
