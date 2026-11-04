"""An old visible report cannot become a new learned death hypothesis."""

import pytest
from test_shared_game_timeline import obs, replay


def claim(tick, signals, signature=None):
    context = {"unqualified_view_model": True}
    if signature is not None:
        context["elimination_display_signature"] = signature
    return obs(tick, signals, context=context)


def two_rounds(second_signature):
    return [
        claim(0, ["buy", "owner_hud"]),
        claim(10, ["active", "owner_hud"]),
        claim(20, ["spectator", "recorder_elimination_display"], "a" * 64),
        claim(30, ["result", "spectator"]),
        claim(40, ["buy", "owner_hud"]),
        claim(50, ["active", "owner_hud"]),
        claim(60, ["spectator", "recorder_elimination_display"], second_signature),
    ]


def test_same_display_after_return_cannot_create_a_second_elimination():
    result = replay(two_rounds("a" * 64))
    deaths = [r for r in result["transitions"] if r["kind"] == "death_hypothesis"]
    assert len(deaths) == 1
    assert result["frames"][-1]["life"]["value"] == "UNKNOWN"
    assert result["frames"][-1]["previously_seen_elimination_display_signatures"] == ["a" * 64]
    assert result["qualified_events"] == result["qualified_facts"] == []


def test_different_display_still_needs_the_existing_owned_spectator_context():
    result = replay(two_rounds("b" * 64))
    deaths = [r for r in result["transitions"] if r["kind"] == "death_hypothesis"]
    assert len(deaths) == 2
    assert deaths[1]["display_signatures"] == ["b" * 64]
    assert deaths[1]["display_identity_semantics"] == "not_physical_event_identity"


def test_report_already_seen_while_self_is_not_fresh_when_camera_switches():
    result = replay(
        [
            claim(0, ["buy", "owner_hud", "recorder_elimination_display"], "a" * 64),
            claim(10, ["active", "owner_hud"]),
            claim(20, ["spectator", "recorder_elimination_display"], "a" * 64),
        ]
    )
    assert not any(r["kind"] == "death_hypothesis" for r in result["transitions"])


def test_an_unread_gap_does_not_make_old_display_identity_new():
    rows = two_rounds("a" * 64)[:4] + [
        claim(100, ["buy", "owner_hud"]),
        claim(110, ["active", "owner_hud"]),
        claim(120, ["spectator", "recorder_elimination_display"], "a" * 64),
    ]
    result = replay(rows)
    assert sum(r["kind"] == "death_hypothesis" for r in result["transitions"]) == 1


def test_weak_elimination_text_without_display_identity_is_not_fresh_evidence():
    result = replay(
        [
            claim(0, ["buy", "owner_hud"]),
            claim(10, ["spectator", "recorder_elimination_display"]),
        ]
    )
    assert result["frames"][-1]["life"]["value"] == "UNKNOWN"
    assert not any(r["kind"] == "death_hypothesis" for r in result["transitions"])


@pytest.mark.parametrize("value", [None, "unhashed", 1])
def test_malformed_display_signature_is_rejected(value):
    with pytest.raises(ValueError, match="SHA256"):
        obs(0, context={"elimination_display_signature": value})
