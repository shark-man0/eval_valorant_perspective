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


def test_existing_spectated_name_reaches_state_without_becoming_recorder_identity(monkeypatch):
    import hashlib

    import numpy as np

    from valorant_ai_coach.visual.development_marker_attribution import freeze_native_sample
    from valorant_ai_coach.visual.development_owner_observations import DevelopmentOwnerUI

    image = np.zeros((80, 80, 3), dtype=np.uint8)
    sample = freeze_native_sample(
        {
            "source_id": "synthetic",
            "source_sha256": "a" * 64,
            "native_epoch": "epoch",
            "acquisition_id": "epoch",
            "native_pts_tick": 0,
            "native_time_base": "1/60",
            "acquired_frame_sha256": "b" * 64,
            "native_pixel_sha256": hashlib.sha256(image.tobytes()).hexdigest(),
        },
        frame_size_px=(80, 80),
    )
    reader = DevelopmentOwnerUI({})
    monkeypatch.setattr(
        reader.screen,
        "inspect",
        lambda *a, **k: {
            "observed_cues": [],
            "spectator_slot": {"checked": True, "panel_present": True},
        },
    )
    monkeypatch.setattr(reader.spectator, "inspect", lambda *a, **k: {"status": "not_detected"})
    monkeypatch.setattr(
        reader.agent,
        "inspect",
        lambda *a, **k: {
            "positive_agent_association": False,
            "block_position_candidate": True,
            "actor_alias_evidence": {
                "status": "observed",
                "observed_alias": "synthetic-recorder",
                "slot_kind": "spectated_player_name",
                "ocr_confidence": 0.95,
                "alias_association": "alias_matches_recorder",
                "current_name_pixels_sha256": "c" * 64,
                "activation_reference_sha256": "d" * 64,
            },
        },
    )
    observed = reader.inspect(image, sample)
    assert observed["own_hud_support"] is False
    subject = observed["spectated_subject_observation"]
    assert subject["observed_alias"] == "synthetic-recorder"
    assert subject["sample_sha256"] == sample["sample_sha256"]
    assert subject["ownership"] == "UNKNOWN"
    state = DevelopmentOwnerTimeline().observe(sample, observed)
    assert state["view"] == "spectator" and state["life"] != "alive"
    assert state["camera_subject"] == subject
    assert state["formal_outputs"] == 0


def test_foreign_spectated_subject_cannot_be_attached_to_current_owner_sample():
    model = DevelopmentOwnerTimeline()
    sample, _ = observation(0)
    with pytest.raises(ValueError, match="subject"):
        model.observe(
            sample,
            ui(
                sample,
                spectator_ui=True,
                spectated_subject_observation={
                    "sample_sha256": "f" * 64,
                    "observed_alias": "synthetic",
                },
            ),
        )


@pytest.mark.parametrize("bad", ["low_confidence", "nonfinite", "no_spectator", "actor_slot"])
def test_name_only_or_unreliable_name_never_becomes_a_spectated_subject(bad):
    from valorant_ai_coach.visual.development_owner_observations import _spectated_subject

    sample, _ = observation(0)
    alias = {
        "status": "observed",
        "slot_kind": "spectated_player_name",
        "observed_alias": "synthetic-player",
        "ocr_confidence": 0.95,
        "current_name_pixels_sha256": "c" * 64,
        "activation_reference_sha256": "d" * 64,
    }
    if bad == "low_confidence":
        alias["ocr_confidence"] = 0.899
    elif bad == "nonfinite":
        alias["ocr_confidence"] = float("nan")
    elif bad == "actor_slot":
        alias["slot_kind"] = "current_actor_identifier"
    assert _spectated_subject(alias, sample, spectator_present=bad != "no_spectator") is None


def test_spectated_name_is_not_carried_as_current_identity_when_pixels_are_missing():
    from valorant_ai_coach.visual.development_owner_observations import _spectated_subject

    sample, _ = observation(0)
    subject = _spectated_subject(
        {
            "status": "observed",
            "slot_kind": "spectated_player_name",
            "observed_alias": "synthetic-player",
            "ocr_confidence": 0.95,
            "current_name_pixels_sha256": "c" * 64,
            "activation_reference_sha256": "d" * 64,
        },
        sample,
        spectator_present=True,
    )
    model = DevelopmentOwnerTimeline()
    first = model.observe(
        sample, ui(sample, spectator_ui=True, spectated_subject_observation=subject)
    )
    assert first["camera_subject"] is not None
    following, _ = observation(1)
    missing = model.observe(
        following, ui(following, spectator_ui=True), continuity=continuity(sample, following)
    )
    assert missing["camera_subject"] is None
    assert missing["view"] == "spectator" and missing["life"] != "alive"


def test_camera_subject_switch_does_not_reassign_recorder_life_or_marker():
    from valorant_ai_coach.visual.development_owner_observations import _spectated_subject

    model = DevelopmentOwnerTimeline()
    previous = None
    for tick, name in enumerate(["synthetic-first", "synthetic-second"]):
        sample, _ = observation(tick)
        subject = _spectated_subject(
            {
                "status": "observed",
                "slot_kind": "spectated_player_name",
                "observed_alias": name,
                "ocr_confidence": 0.95,
                "current_name_pixels_sha256": "c" * 64,
                "activation_reference_sha256": "d" * 64,
            },
            sample,
            spectator_present=True,
        )
        result = model.observe(
            sample,
            ui(sample, spectator_ui=True, spectated_subject_observation=subject),
            continuity=continuity(previous, sample) if previous else None,
        )
        assert result["camera_subject"]["observed_alias"] == name
        assert result["view"] == "spectator" and result["life"] != "alive"
        assert result["self_marker_id"] is None and result["formal_outputs"] == 0
        previous = sample


def screen_context(*, shared_hud):
    return {
        "status": "observed",
        "observed_cues": [
            {"claim": "first_person_hud", "status": shared_hud},
            {"claim": "death_report", "status": "present"},
        ],
    }


def test_new_report_with_missing_current_hud_cannot_carry_stale_alive_self():
    model = DevelopmentOwnerTimeline()
    first, _ = observation(0)
    model.observe(first, ui(first, own_hud_support=True))
    second, _ = observation(1)
    result = model.observe(
        second,
        ui(second, combat_report_visible=True,
           screen_measurements=screen_context(shared_hud="not_detected")),
        continuity=continuity(first, second),
    )
    assert (result["life"], result["view"]) == ("unknown", "unknown")
    assert result["reason"] == "unresolved_view_change"
    assert result["death_transition_candidate"] is None
    assert result["formal_outputs"] == 0
    third, _ = observation(2)
    held = model.observe(third, ui(third, combat_report_visible=True),
                         continuity=continuity(second, third))
    assert (held["life"], held["view"]) == ("unknown", "unknown")


@pytest.mark.parametrize("own,shared", [(True, "not_detected"), (False, "present")])
@pytest.mark.parametrize("role", ["NONSELF_VICTIM", "SELF_KILLER", "UNKNOWN"])
def test_report_controls_with_current_hud_do_not_change_life(own, shared, role):
    model = DevelopmentOwnerTimeline()
    previous, _ = observation(0)
    model.observe(previous, ui(previous, own_hud_support=True))
    for tick, report in enumerate([True, True, False, True], 1):
        current, _ = observation(tick)
        result = model.observe(
            current,
            ui(current, own_hud_support=own, combat_report_visible=report,
               killfeed_role=role, screen_measurements=screen_context(shared_hud=shared)),
            continuity=continuity(previous, current),
        )
        assert (result["life"], result["view"]) == ("alive", "self")
        assert result["death_transition_candidate"] is None
        previous = current


@pytest.mark.parametrize("shared", ["unavailable", None])
def test_unavailable_screen_measurement_is_not_a_report_view_change(shared):
    model = DevelopmentOwnerTimeline()
    first, _ = observation(0)
    model.observe(first, ui(first, own_hud_support=True))
    second, _ = observation(1)
    result = model.observe(
        second,
        ui(second, combat_report_visible=True,
           screen_measurements=screen_context(shared_hud=shared)),
        continuity=continuity(first, second),
    )
    assert result["life"] == "alive"
    assert result["death_transition_candidate"] is None
