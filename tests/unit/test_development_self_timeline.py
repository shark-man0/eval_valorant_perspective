"""No synthetic cue is a qualified self-life or map marker event."""

from fractions import Fraction

import pytest

from valorant_ai_coach.visual.development_self_timeline import (
    DevelopmentSelfTimeline,
    SelfFrameCues,
)

SHA = "a" * 64


def frame(tick: int, **overrides: object) -> SelfFrameCues:
    defaults: dict[str, object] = {
        "source_sha256": SHA, "source_epoch": "e1", "pts_ticks": tick,
        "time_base": Fraction(1, 60), "continuous_from_previous": tick > 0,
    }
    defaults.update(overrides)
    return SelfFrameCues(**defaults)  # type: ignore[arg-type]


def test_life_survives_missing_ui_until_death_and_spectator() -> None:
    timeline = DevelopmentSelfTimeline()
    assert timeline.observe(frame(0, own_view_ui=True)).life == "alive"
    invisible = timeline.observe(frame(1))
    assert (invisible.life, invisible.view) == ("alive", "self")
    dead = timeline.observe(frame(2, self_death_transition=True))
    assert (dead.life, dead.view) == ("dead", "unknown")
    spectated = timeline.observe(frame(3, spectator_ui=True))
    assert (spectated.life, spectated.view) == ("dead", "spectator")
    assert timeline.observe(frame(4)).life == "dead"
    returned = timeline.observe(frame(5, new_round_reentry=True, own_view_ui=True))
    assert (returned.life, returned.view) == ("alive", "self")
    assert all(not output.qualified for output in (dead, spectated, returned))


def test_spectator_without_observed_death_is_explicit_hypothesis() -> None:
    timeline = DevelopmentSelfTimeline()
    timeline.observe(frame(0, own_view_ui=True))
    result = timeline.observe(frame(1, spectator_ui=True))
    assert (result.life, result.view, result.reason) == (
        "dead", "spectator", "spectator_death_hypothesis"
    )


def test_revival_from_dead_or_downed_and_second_death() -> None:
    timeline = DevelopmentSelfTimeline()
    timeline.observe(frame(0, own_view_ui=True))
    timeline.observe(frame(1, self_death_transition=True))
    revived = timeline.observe(frame(2, revival_transition=True, own_view_ui=True))
    assert (revived.life, revived.view) == ("alive", "self")
    timeline.observe(frame(3, self_death_transition=True))
    assert timeline.observe(frame(4)).life == "dead"
    timeline.observe(frame(5, new_round_reentry=True, own_view_ui=True))
    assert timeline.observe(frame(6, downed_transition=True)).life == "downed"
    assert timeline.observe(frame(7, revival_transition=True, own_view_ui=True)).life == "alive"


def test_downed_without_revival_not_alive_and_ability_return_not_death() -> None:
    timeline = DevelopmentSelfTimeline()
    timeline.observe(frame(0, own_view_ui=True))
    assert timeline.observe(frame(1, ultimate_return=True, own_view_ui=True)).life == "alive"
    assert timeline.observe(frame(2, remote_view_ui=True)).view == "remote"
    assert timeline.observe(frame(3, downed_transition=True)).life == "downed"
    assert timeline.observe(frame(4)).life == "downed"
    assert timeline.observe(frame(5, own_view_ui=True)).life == "unknown"


def test_no_self_map_from_spectator_or_unverified_marker() -> None:
    timeline = DevelopmentSelfTimeline()
    first = timeline.observe(frame(0, own_view_ui=True, marker_id="m1",
                                   marker_is_self_ui=True))
    assert first.self_marker_id == "m1"
    assert timeline.observe(frame(1, marker_id="m1")).self_marker_id is None
    assert timeline.observe(frame(2, spectator_ui=True, marker_id="m1",
                                  marker_is_self_ui=True)).self_marker_id is None
    assert timeline.observe(frame(3, revival_transition=True, own_view_ui=True,
                                  marker_id="m1", marker_is_self_ui=True)).self_marker_id == "m1"


def test_missing_continuity_and_epoch_change_drop_old_life() -> None:
    timeline = DevelopmentSelfTimeline()
    timeline.observe(frame(0, own_view_ui=True))
    assert timeline.observe(frame(1, continuous_from_previous=False)).life == "unknown"
    timeline.observe(frame(2, self_death_transition=True))
    assert timeline.observe(frame(3, source_epoch="e2")).life == "unknown"


def test_dropped_or_contradictory_cues_cannot_invent_resurrection() -> None:
    timeline = DevelopmentSelfTimeline()
    assert timeline.observe(frame(0, revival_transition=True)).life == "unknown"
    assert timeline.observe(frame(1, self_death_transition=True,
                                  revival_transition=True)).reason == "conflicting_evidence"
    assert timeline.observe(frame(2, spectator_ui=True, own_view_ui=True)).life == "unknown"
    timeline.observe(frame(3, self_death_transition=True))
    assert timeline.observe(frame(4, new_round_reentry=True)).life == "unknown"


def test_reject_invalid_source_cue() -> None:
    with pytest.raises(ValueError):
        frame(0, source_sha256="fake")
    with pytest.raises(ValueError):
        frame(0, marker_is_self_ui=True)
    with pytest.raises(ValueError):
        frame(0, time_base=Fraction(0))
    with pytest.raises(ValueError):
        frame(-1)


def test_death_onset_may_still_show_previous_self_hud() -> None:
    timeline = DevelopmentSelfTimeline()
    timeline.observe(frame(0, own_view_ui=True))
    result = timeline.observe(frame(1, self_death_transition=True, own_view_ui=True))
    assert (result.life, result.view) == ("dead", "unknown")
    assert timeline.observe(frame(2, spectator_ui=True)).life == "dead"
