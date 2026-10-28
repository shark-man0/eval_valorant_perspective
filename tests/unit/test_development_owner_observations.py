from copy import deepcopy

import pytest

from tests.unit.test_development_marker_temporal import continuity, observation
from valorant_ai_coach.visual.development_owner_observations import DevelopmentOwnerTimeline


def ui(sample, **changes):
    return {
        "sample_sha256": sample["sample_sha256"],
        "fingerprint": "1" * 64,
        "source_profile_fingerprint": "2" * 64,
        "origin": "image_reader",
        "qualified": False,
        "formal_outputs": 0,
        "own_hud_support": False,
        "spectator_ui": False,
        "combat_report_visible": False,
        "purchase_phase_visible": False,
        "remote_ui": False,
        **changes,
    }


@pytest.mark.parametrize("role", ["NONSELF_VICTIM", "SELF_KILLER", "UNKNOWN"])
def test_other_death_self_kill_and_report_do_not_change_owner_life(role):
    model = DevelopmentOwnerTimeline()
    first, _ = observation(0)
    result = model.observe(first, ui(first, own_hud_support=True))
    assert result["life"] == "alive"
    previous = first
    for tick, visible in enumerate([True, True, False, True, True], 1):
        frame, _ = observation(tick)
        result = model.observe(
            frame,
            ui(frame, combat_report_visible=visible, killfeed_role=role),
            continuity=continuity(previous, frame),
        )
        assert (result["life"], result["view"]) == ("alive", "self")
        assert result["death_transition_candidate"] is None
        assert result["formal_outputs"] == 0
        previous = frame
    assert result["report_observation"] == "persistent_observation"


def test_first_spectator_observation_does_not_invent_observed_death_boundary():
    model = DevelopmentOwnerTimeline()
    f, _ = observation(0)
    result = model.observe(f, ui(f, spectator_ui=True, combat_report_visible=True))
    assert result["view"] == "spectator"
    assert result["death_transition_candidate"] is None
    assert result["life_evidence"] == "unanchored_spectator_hypothesis"


def test_spectator_edge_brackets_candidate_once_without_equating_internal_death():
    model = DevelopmentOwnerTimeline()
    first, _ = observation(0)
    model.observe(first, ui(first, own_hud_support=True))
    second, _ = observation(1)
    r = model.observe(second, ui(second, spectator_ui=True), continuity=continuity(first, second))
    event = r["death_transition_candidate"]
    assert event["last_self_alive_pts"] == 0 and event["first_dead_hypothesis_pts"] == 1
    assert event["kind"] == "self_to_spectator_inferred"
    assert event["internal_game_death_time"] is None
    third, _ = observation(2)
    r = model.observe(
        third,
        ui(third, spectator_ui=True, combat_report_visible=True),
        continuity=continuity(second, third),
    )
    assert r["active_death_candidate_id"] == event["candidate_id"]
    assert r["death_transition_candidate"] is None


@pytest.mark.parametrize("violation", ["gap", "duplicate", "epoch", "missing_receipt", "cut"])
def test_no_state_carry_across_unknown_native_input(violation):
    model = DevelopmentOwnerTimeline()
    first, _ = observation(0)
    model.observe(first, ui(first, own_hud_support=True))
    second, _ = observation(
        30 if violation == "gap" else 0 if violation == "duplicate" else 1,
        **({"native_epoch": "other", "acquisition_id": "other"} if violation == "epoch" else {}),
    )
    cues = ui(second, source_discontinuity=None if violation == "cut" else False)
    receipt = None if violation == "missing_receipt" else continuity(first, second)
    r = model.observe(second, cues, continuity=receipt)
    assert (r["life"], r["view"]) == ("unknown", "unknown")
    assert not r["native_continuity_used"]


def test_foreign_ui_failure_clears_previous_context():
    model = DevelopmentOwnerTimeline()
    first, _ = observation(0)
    model.observe(first, ui(first, own_hud_support=True))
    second, _ = observation(1)
    with pytest.raises(ValueError):
        model.observe(
            second, ui(second, sample_sha256="f" * 64), continuity=continuity(first, second)
        )
    third, _ = observation(2)
    r = model.observe(third, ui(third), continuity=continuity(second, third))
    assert r["life"] == "unknown"


def test_report_absence_and_reappearance_are_not_new_death_events():
    model = DevelopmentOwnerTimeline()
    previous = None
    states = []
    for tick, present in enumerate([False, True, True, False, True]):
        f, _ = observation(tick)
        r = model.observe(
            f,
            ui(f, own_hud_support=tick == 0, combat_report_visible=present),
            continuity=continuity(previous, f) if previous else None,
        )
        states.append(r["report_observation"])
        assert r["life"] == "alive" and r["death_transition_candidate"] is None
        previous = f
    assert states == [
        "not_detected",
        "first_observed_presence",
        "persistent_observation",
        "not_detected_after_presence",
        "presence_after_non_detection",
    ]


def test_human_seed_is_explicit_and_not_repeated_as_current_ui():
    model = DevelopmentOwnerTimeline()
    first, _ = observation(0)
    reviewed = {
        "sample_sha256": first["sample_sha256"],
        "review_sha256": "3" * 64,
        "frame_sha256": first["acquired_frame_sha256"],
        "role": "SELF_LIVE",
        "qualification": "development_only",
        "ownership": "UNKNOWN",
        "origin": "human_exact_frame",
        "status": "human_confirmed",
    }
    r = model.observe(first, ui(first), initial_review=reviewed)
    assert r["anchor_origin"] == "human_exact_frame" and r["life"] == "alive"
    assert r["raw_ui"]["own_hud_support"] is False
    second, _ = observation(1)
    r = model.observe(second, ui(second), continuity=continuity(first, second))
    assert r["life"] == "alive" and r["state_origin"] == "temporal_inference"
    with pytest.raises(ValueError):
        model.observe(second, ui(second), initial_review=deepcopy(reviewed))
