from pathlib import Path
from types import SimpleNamespace

import pytest

from tests.e2e.trace_adapter import to_e2e_trace
from valorant_ai_coach.events import EventSourceContract
from valorant_ai_coach.hud.models import HudObservationV2, empty_hud_quality, empty_hud_values
from valorant_ai_coach.hud.temporal import HudDirectEventBuilder
from valorant_ai_coach.resources import resource_path
from valorant_ai_coach.rounds import RoundPackageBuilder
from valorant_ai_coach.schema_validation import SchemaValidator
from valorant_ai_coach.video import VideoMetadata


def sample(index, time, *, phase=False, menu=False, timer=100, score=0, confidence=0.95):
    values = empty_hud_values()
    values.update(
        round_time_remaining_sec=timer,
        score_ally=score,
        score_enemy=0,
        player_specific_hud_valid=not menu,
        buy_phase_visible=phase,
    )
    quality = empty_hud_quality()
    quality.update(hud_confidence=confidence, state_confidence=confidence)
    return HudObservationV2(
        time,
        index,
        "buy_menu_open" if menu else "live_first_person",
        values=values,
        quality=quality,
        state_flags=("buy_phase_banner",) if phase else (),
    ).to_dict()


def boundaries(samples, evidence=None):
    return [
        e
        for e in HudDirectEventBuilder().build(samples, evidence_by_frame=evidence)
        if e["type"] in {"round_start", "round_end"}
    ]


@pytest.mark.parametrize("offset", [0, 500])
def test_start_preserves_candidate_pts_after_later_timer_corroboration(offset):
    samples = [
        sample(0, offset, phase=True, timer=0),
        sample(1, offset + 0.2),
        sample(2, offset + 0.4, timer=99),
    ]
    events = boundaries(samples)
    assert len(events) == 1
    assert (events[0]["type"], events[0]["actor"], events[0]["time_sec"]) == (
        "round_start",
        "system",
        offset + 0.2,
    )
    proof = events[0]["attributes"]["evidence_provenance"]
    assert proof["producer"] == "hud_analyzer"
    assert proof["confirmation_pts_sec"] == offset + 0.4


def test_one_frame_reset_and_jitter_cannot_confirm_start():
    assert not boundaries([sample(0, 0, phase=True, timer=0), sample(1, 0.2)])
    assert not boundaries(
        [sample(0, 0, phase=True, timer=0), sample(1, 0.2), sample(2, 0.4, phase=True, timer=0)]
    )


def test_active_menu_reset_cannot_duplicate_start():
    samples = [
        sample(0, 0, phase=True, timer=0),
        sample(1, 0.2),
        sample(2, 0.4),
        sample(3, 0.6, menu=True, timer=0),
        sample(4, 0.8),
        sample(5, 1.0),
    ]
    assert [e["type"] for e in boundaries(samples)] == ["round_start"]


def test_two_rounds_emit_one_end_without_inventing_second_end():
    samples = [
        sample(0, 0, phase=True, timer=0),
        sample(1, 0.2),
        sample(2, 0.4),
        sample(3, 0.6, score=1),
        sample(4, 0.8, score=1),
        sample(5, 1.0, phase=True, timer=0, score=1),
        sample(6, 1.2, score=1),
        sample(7, 1.4, timer=99, score=1),
    ]
    evidence = {3: {"round_end_template": True}, 4: {"round_end_template": True}}
    events = boundaries(samples, evidence)
    assert [(e["type"], e["time_sec"]) for e in events] == [
        ("round_start", 0.2),
        ("round_end", 0.6),
        ("round_start", 1.2),
    ]
    assert all(e["actor"] == "system" for e in events)
    end = events[1]["attributes"]["evidence_provenance"]
    assert len(end["pts_sec"]) >= 2
    assert end["signals"] == ["score_transition", "phase_banner"]


@pytest.mark.parametrize("marker", ["discontinuity", "content_jump"])
def test_source_cut_marker_discards_pending_start(marker):
    samples = [sample(0, 0, phase=True, timer=0), sample(1, 0.2), sample(2, 0.4)]
    assert not boundaries(samples, {2: {marker: True}})


def test_gap_discards_pending_start_and_prevents_banner_score_join():
    assert not boundaries([sample(0, 0, phase=True, timer=0), sample(1, 0.2), sample(2, 1.3)])
    assert not boundaries(
        [sample(0, 0), sample(1, 0.2), sample(2, 1.4, score=1)], {1: {"round_end_template": True}}
    )


def test_low_confidence_confirmation_and_unknown_timer_fail_closed():
    for kwargs in ({"confidence": 0.64}, {"timer": None}):
        assert not boundaries(
            [sample(0, 0, phase=True, timer=0), sample(1, 0.2), sample(2, 0.4, **kwargs)]
        )


@pytest.mark.parametrize("index", [0, 1, 2])
@pytest.mark.parametrize("field", ["score_ally", "score_enemy"])
@pytest.mark.parametrize("value", [None, True, -1, 1.0])
def test_start_requires_current_complete_score_evidence(index, field, value):
    samples = [sample(0, 0, phase=True, timer=0), sample(1, .2), sample(2, .4, timer=99)]
    samples[index]["values"][field] = value
    assert not boundaries(samples)


@pytest.mark.parametrize("index", [1, 2])
def test_score_change_cannot_corrobate_start(index):
    samples = [sample(0, 0, phase=True, timer=0), sample(1, .2), sample(2, .4, timer=99)]
    samples[index]["values"]["score_enemy"] = 1
    assert not boundaries(samples)


def test_start_provenance_records_score_continuity_without_changing_identity():
    samples = [sample(0, 0, phase=True, timer=0), sample(1, .2), sample(2, .4, timer=99)]
    event = boundaries(samples)[0]
    assert "score_continuity" in event["attributes"]["evidence_provenance"]["signals"]
    assert all(row["primary_state"] == "live_first_person" for row in samples)


def test_texture_banner_and_score_change_do_not_prove_semantic_round_end():
    samples = [sample(0, 0), sample(1, 0.2, score=1), sample(2, 0.4, score=1)]
    assert not boundaries(samples, {1: {"shared_banner": True}})
    assert all("round_end_banner" not in s["state_flags"] for s in samples)


def test_trace_preserves_native_actor_time_and_source_provenance():
    samples = [sample(0, 0, phase=True, timer=0), sample(1, 0.2), sample(2, 0.4)]
    event = boundaries(samples)[0]
    trace = to_e2e_trace(
        SimpleNamespace(
            round_packages=({"events": [event], "round_window": {"start_sec": 0, "end_sec": 1}},),
            observations=(),
        )
    )
    row = trace["events"][0]
    assert row["round_id"] == "sample_round_1"
    assert row["actor"] == event["actor"] == "system"
    assert row["time_sec"] == event["time_sec"]
    assert row["attributes"] == event["attributes"]


def test_native_lifecycle_to_two_packages_to_trace_without_boundary_repair():
    samples = [
        sample(0, 0, phase=True, timer=0),
        sample(1, 0.2),
        sample(2, 0.4),
        sample(3, 0.6, score=1),
        sample(4, 0.8, phase=True, timer=0, score=1),
        sample(5, 1.0, score=1),
        sample(6, 1.2, score=1),
    ]
    events = boundaries(samples, {3: {"round_end_template": True}})
    builder = RoundPackageBuilder(
        contract=EventSourceContract.load(resource_path("config/event_source_contract_v1.json")),
        validator=SchemaValidator(),
    )
    packages = builder.build(
        match_id="unit-lifecycle",
        video_metadata=VideoMetadata(Path("unit.mp4"), 2, 1920, 1080, 60, "h264", None, False, 0),
        hud_observations=samples,
        hud_events=events,
    )
    assert len(packages) == 2
    trace = to_e2e_trace(SimpleNamespace(round_packages=packages, observations=samples))
    actual = [e for e in trace["events"] if e["type"] in {"round_start", "round_end"}]
    assert [(e["round_id"], e["type"], e["time_sec"], e["actor"]) for e in actual] == [
        ("sample_round_1", "round_start", 0.2, "system"),
        ("sample_round_1", "round_end", 0.6, "system"),
        ("sample_round_2", "round_start", 1.0, "system"),
    ]
    assert [e["attributes"] for e in actual] == [e["attributes"] for e in events]
    assert packages[0]["round_window"]["start_sec"] == 0
    assert packages[1]["round_window"]["start_sec"] == 0.8
    assert any(s["time_sec"] == 0.8 for s in packages[1]["state_snapshots"])


def test_trace_shared_context_endpoint_belongs_to_upcoming_round():
    packages = (
        {"round_window": {"start_sec": 0, "end_sec": 1}},
        {"round_window": {"start_sec": 1, "end_sec": 2}},
    )
    trace = to_e2e_trace(
        SimpleNamespace(
            round_packages=packages,
            observations=[sample(0, 1), sample(1, 1.2)],
        )
    )
    assert trace["state_intervals"]
    assert all(row["round_id"] == "sample_round_2" for row in trace["state_intervals"])
    assert all(row["round_id"] == "sample_round_2" for row in trace["ownership_intervals"])
