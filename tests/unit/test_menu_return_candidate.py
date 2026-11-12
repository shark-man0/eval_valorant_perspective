"""Menu pixels require current weak SELF and a witnessed next-Round return."""

from copy import deepcopy

import pytest
from test_conditional_state_tails import return_rows, row

from valorant_ai_coach.temporal.game import DevelopmentGameTimeline, observation


def menu_row(**changes):
    measurement = {
        "schema": "development_buy_menu_grid_geometry_v1",
        "supported": True,
        "status": "CANDIDATE",
        "score": 0.96,
        "geometry_scope": "current_pixel_menu_overlay_only",
        "owner_authority": False,
        "camera_authority": False,
        "phase_authority": False,
        "qualified": False,
    }
    measurement.update(changes)
    return observation(
        sample=row(6)["sample"],
        producer="e" * 64,
        signals=[],
        context={"stream_kind": "hud_menu_geometry"},
        raw={
            "schema": "development_buy_menu_grid_geometry_v1",
            "menu_grid_measurement": measurement,
        },
    )


def replay(rows, **flags):
    engine = DevelopmentGameTimeline(return_display_tail=True, **flags)
    for item in rows:
        engine.add(item)
    return engine.rebuild()


def frame(result, tick=6):
    return next(f for f in result["frames"] if f["sample"]["native_pts_tick"] == tick)


def test_menu_can_support_a_candidate_when_hp_is_hidden_but_not_a_fact():
    rows = return_rows() + [menu_row()]
    before = replay(rows)
    after = replay(rows, current_menu_return_candidate=True)
    assert frame(before)["life"]["value"] == "UNKNOWN"
    assert (frame(after)["life"]["value"], frame(after)["camera"]["value"]) == ("ALIVE", "SELF")
    assert "DEAD" in frame(after)["life"]["hypotheses"]
    assert "SPECTATOR" in frame(after)["camera"]["hypotheses"]
    assert after["transitions"] == before["transitions"]
    assert after["observations"] == before["observations"]
    assert after["qualified_facts"] == after["qualified_events"] == []
    assert frame(after)["map"]["current_self_position_candidates"] == []
    assert frame(after, 7)["life"]["value"] == "UNKNOWN"  # no carried menu witness


@pytest.mark.parametrize(
    "change",
    [
        {"supported": False},
        {"status": "UNKNOWN"},
        {"qualified": True},
        {"owner_authority": True},
        {"camera_authority": True},
        {"phase_authority": True},
        {"geometry_scope": "different"},
        {"score": float("nan")},
        {"score": True},
    ],
)
def test_invalid_menu_claim_never_selects_positive_state(change):
    # JSON observations reject non-finite data themselves; exercise that boundary too.
    if change.get("score") != change.get("score"):
        with pytest.raises(ValueError):
            menu_row(**change)
        return
    result = replay(return_rows() + [menu_row(**change)], current_menu_return_candidate=True)
    assert frame(result)["life"]["value"] != "ALIVE"


@pytest.mark.parametrize("signal", ["death", "spectator", "remote", "downed", "revival"])
def test_direct_contradictions_outweigh_overlay_and_future(signal):
    rows = return_rows() + [row(6, [signal]), menu_row()]
    result = replay(rows, current_menu_return_candidate=True)
    assert frame(result)["life"]["value"] != "ALIVE"


def test_menu_without_weak_self_or_same_epoch_return_is_not_enough():
    rows = [r for r in return_rows() if not r["context"].get("unqualified_view_model")]
    assert (
        frame(replay(rows + [menu_row()], current_menu_return_candidate=True))["life"]["value"]
        != "ALIVE"
    )
    rows = return_rows(return_epoch="other") + [menu_row()]
    assert frame(replay(rows, current_menu_return_candidate=True))["life"]["value"] != "ALIVE"


def test_foreign_current_pixels_cannot_supply_menu_support():
    evidence = menu_row()
    for key, value in [
        ("native_pts_tick", 7),
        ("native_pixel_sha256", "a" * 64),
        ("source_sha256", "f" * 64),
    ]:
        current = deepcopy(evidence["sample"])
        current[key] = value
        assert not DevelopmentGameTimeline._current_menu_support(evidence, current)


def test_explicit_offline_opt_in_required():
    with pytest.raises(ValueError, match="offline"):
        DevelopmentGameTimeline(current_menu_return_candidate=True)
    with pytest.raises(ValueError, match="offline"):
        DevelopmentGameTimeline(
            return_display_tail=True, forward_only=True, current_menu_return_candidate=True
        )
