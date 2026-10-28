from fractions import Fraction

import pytest

from valorant_ai_coach.visual.development_owner_state import (
    DevelopmentOwnerTimeline,
    MarkerObservation,
    OwnerObservation,
)
from valorant_ai_coach.visual.development_self_timeline import SelfFrameCues


def observation(tick, **kwargs):
    cue_changes = kwargs.pop("cue", {})
    if kwargs.get("life_evidence", "none") != "none":
        kwargs.setdefault("life_evidence_sha256", "d" * 64)
        kwargs.setdefault("life_subject", "recorder")
    return OwnerObservation(
        cue=SelfFrameCues(
            "a" * 64,
            "source-epoch",
            tick,
            Fraction(1, 60),
            continuous_from_previous=tick != 0,
            **cue_changes,
        ),
        context_fingerprint="b" * 64,
        **kwargs,
    )


def bound(tick=0):
    return observation(
        tick,
        cue={"own_view_ui": True},
        life_evidence="owner_alive",
        binding_marker_id="m1",
        binding_origin="automatic_ui",
        binding_evidence_sha256="c" * 64,
        markers=(MarkerObservation("m1", (20.0, 30.0), (0.2, 0.3), "test"),),
    )


def test_spectator_only_does_not_become_direct_recorder_death():
    row = DevelopmentOwnerTimeline().observe(observation(0, cue={"spectator_ui": True}))
    assert row["camera"] == "spectator" and row["life"] == "unknown"
    assert row["life_hypothesis"] == "dead"
    assert row["legacy_PR107_hypothesis"]["life"] == "dead"
    assert not row["self_to_spectator_observed"]
    assert row["formal_outputs"] == 0 and row["ownership"] == "UNKNOWN"


def test_self_to_spectator_transition_and_direct_death_are_separate():
    timeline = DevelopmentOwnerTimeline()
    timeline.observe(bound())
    row = timeline.observe(observation(12, cue={"spectator_ui": True}))
    assert row["self_to_spectator_observed"]
    assert row["life"] == "unknown" and row["life_evidence_kind"] == "none"
    assert row["current_observation"] is None


def test_direct_owner_death_is_retained_independently_of_camera():
    timeline = DevelopmentOwnerTimeline()
    timeline.observe(bound())
    row = timeline.observe(observation(12, life_evidence="owner_death"))
    assert row["life"] == "dead" and row["camera"] == "unknown"
    row = timeline.observe(observation(24, cue={"spectator_ui": True}))
    assert row["life"] == "dead" and row["camera"] == "spectator"


def test_other_death_information_does_not_change_owner_life_or_identity():
    timeline = DevelopmentOwnerTimeline()
    timeline.observe(bound())
    row = timeline.observe(observation(12, cue={"own_view_ui": True}, other_death_observed=True))
    assert row["life"] == "alive" and row["recorder_marker_id"] == "m1"


def test_marker_disappearance_keeps_identity_without_current_position_or_zone():
    timeline = DevelopmentOwnerTimeline()
    timeline.observe(bound())
    row = timeline.observe(observation(12, cue={"own_view_ui": True}))
    assert row["recorder_marker_id"] == "m1" and row["binding_state"] == "suspended"
    assert row["current_observation"] is None and not row["current_position_observed"]
    assert not row["position_interpolated"]


def test_ambiguous_reappearance_cannot_choose_a_current_location():
    timeline = DevelopmentOwnerTimeline()
    timeline.observe(bound())
    timeline.observe(observation(12, cue={"own_view_ui": True}))
    row = timeline.observe(
        observation(
            24,
            cue={"own_view_ui": True},
            markers=(MarkerObservation("m1", (22.0, 30.0)),),
            ambiguous_reappearance=True,
        )
    )
    assert row["binding_state"] == "ambiguous_reappearance"
    assert row["current_observation"] is None and row["recorder_marker_id"] == "m1"


def test_explicit_unique_association_connects_observed_positions():
    timeline = DevelopmentOwnerTimeline()
    timeline.observe(bound())
    row = timeline.observe(
        observation(
            12,
            cue={"own_view_ui": True},
            markers=(MarkerObservation("m2", (22.0, 30.0), (0.22, 0.3)),),
            associations=(("m1", "m2"),),
        )
    )
    assert row["recorder_marker_id"] == "m2" and row["current_position_observed"]


def test_source_gap_or_epoch_change_discards_old_identity():
    timeline = DevelopmentOwnerTimeline()
    timeline.observe(bound())
    row = timeline.observe(observation(60, cue={"own_view_ui": True}))
    assert row["recorder_marker_id"] is None and row["life"] == "unknown"


def test_human_binding_remains_diagnostic_and_never_automatic():
    from dataclasses import replace

    row = DevelopmentOwnerTimeline().observe(replace(bound(), binding_origin="human_diagnostic"))
    assert row["binding_origin"] == "human_diagnostic" and row["ownership"] == "UNKNOWN"


def test_missing_ui_receipt_cannot_establish_an_initial_binding():
    from dataclasses import replace

    with pytest.raises(ValueError, match="evidence receipt"):
        DevelopmentOwnerTimeline().observe(replace(bound(), binding_evidence_sha256=None))


def test_legacy_death_guess_about_another_subject_does_not_erase_owner_binding():
    timeline = DevelopmentOwnerTimeline()
    timeline.observe(bound())
    row = timeline.observe(
        observation(
            12, cue={"own_view_ui": True, "self_death_transition": True}, other_death_observed=True
        )
    )
    assert row["life"] == "alive" and row["recorder_marker_id"] == "m1"


def test_reusing_an_id_after_missing_is_not_evidence_of_reacquisition():
    timeline = DevelopmentOwnerTimeline()
    timeline.observe(bound())
    timeline.observe(observation(12, cue={"own_view_ui": True}))
    row = timeline.observe(
        observation(24, cue={"own_view_ui": True}, markers=(MarkerObservation("m1", (22.0, 30.0)),))
    )
    assert row["current_observation"] is None
    assert row["recorder_marker_id"] == "m1"


def test_conflicting_view_evidence_does_not_prove_a_self_to_spectator_transition():
    timeline = DevelopmentOwnerTimeline()
    timeline.observe(bound())
    row = timeline.observe(observation(12, cue={"own_view_ui": True, "spectator_ui": True}))
    assert row["camera"] == "unknown" and not row["self_to_spectator_observed"]


def test_nonfinite_current_position_cannot_be_returned_as_an_observation():
    timeline = DevelopmentOwnerTimeline()
    timeline.observe(bound())
    with pytest.raises(ValueError, match="measurement"):
        timeline.observe(
            observation(
                12,
                cue={"own_view_ui": True},
                markers=(MarkerObservation("m1", (float("nan"), 3.0)),),
            )
        )
    assert timeline.observe(observation(24))["recorder_marker_id"] is None


def test_automatic_first_person_candidate_does_not_establish_recorder_life():
    row = DevelopmentOwnerTimeline().observe(
        observation(
            0,
            first_person_candidate=True,
            binding_marker_id="m1",
            binding_origin="automatic_ui",
            binding_evidence_sha256="c" * 64,
            markers=(MarkerObservation("m1", (20.0, 30.0)),),
        )
    )
    assert row["life"] == "unknown" and row["camera"] == "first_person_candidate"
    assert row["current_position_observed"] and row["ownership"] == "UNKNOWN"


@pytest.mark.parametrize("subject", ["none", "visible_subject", "other_player"])
def test_other_subject_life_evidence_cannot_assign_recorder_death(subject):
    with pytest.raises(ValueError, match="Recorder-subject"):
        DevelopmentOwnerTimeline().observe(
            observation(0, life_evidence="owner_death", life_subject=subject)
        )


def test_detached_current_measurement_retains_unknown_development_boundary():
    row = DevelopmentOwnerTimeline().observe(bound())
    detached = row["current_observation"]
    assert detached["ownership"] == "UNKNOWN"
    assert detached["qualification"] == "development_only"
    assert detached["position_subject"] == "recorder_association_candidate"
    assert detached["formal_outputs"] == 0
