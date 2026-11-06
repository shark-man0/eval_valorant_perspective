from types import SimpleNamespace

import numpy as np
import pytest
from test_hud_templates import _asset, _profile
from test_shared_game_timeline import obs, replay

from valorant_ai_coach.hud.readers import ReaderResult
from valorant_ai_coach.temporal.application import _hud
from valorant_ai_coach.temporal.game import observation
from valorant_ai_coach.temporal.hud_values import configured_hud_values


def layout():
    return SimpleNamespace(
        regions={"player_hp_armor": None, "weapon_inventory": None},
        normalized_roi=lambda _: SimpleNamespace(pixel_bounds=lambda w, h: (0, 0, w, h)),
    )


class Numbers:
    fields = {"hp": (0, 0, 1, 1), "armor": (0, 0, 1, 1)}

    def __init__(self, value=None, confidence=.95, error=False):
        self.value = {"hp": 100, "armor": 25} if value is None else value
        self.confidence, self.error, self.calls = confidence, error, 0

    def read(self, image, roi):
        self.calls += 1
        if self.error:
            raise OSError("reader unavailable")
        return ReaderResult(self.value, self.confidence, ("existing_digits",))


def test_existing_numeric_and_real_weapon_template_readers_reach_canonical_HUD(tmp_path):
    image = _asset(tmp_path, "weapon.png")
    weapon = _profile(tmp_path, readers={"weapon_inventory": {
        "kind": "weapon_templates", "values": {"Vandal": "weapon.png"}}}).build_readers()
    measurements = configured_hud_values(
        image, layout=layout(), readers={"player_hp_armor": Numbers(), **weapon},
        ui={}, calibrated=True,
    )
    base = obs(0)
    row = observation(sample=base["sample"], producer="c" * 64, signals=[],
                      raw={"hud_value_measurements": measurements})
    hud = _hud([row])
    assert hud["hp"]["candidates"][0]["value"] == 100
    assert hud["armor"]["candidates"][0]["value"] == 25
    assert hud["weapon"]["candidates"][0]["value"] == "Vandal"
    assert hud["credits"]["status"] == "UNKNOWN"
    assert hud["credits"]["unavailable_reasons"][0]["reason"] == "unconfigured_reader_or_roi"
    frame = replay([row, obs(0, ["spectator"])])["frames"][0]
    assert frame["camera"]["value"] == "SPECTATOR"
    assert frame["life"]["value"] != "ALIVE"
    assert frame["map"]["current_self_position_candidates"] == []


@pytest.mark.parametrize("cause", ["geometry", "unread", "low_confidence", "invalid", "error"])
def test_unavailable_values_keep_reasons_and_never_become_zero(cause):
    reader = Numbers(value={} if cause == "unread" else {"hp": True, "armor": -1}
                     if cause == "invalid" else None,
                     confidence=.2 if cause == "low_confidence" else .95,
                     error=cause == "error")
    measured = configured_hud_values(
        np.zeros((24, 28, 3), np.uint8), layout=layout(), readers={"player_hp_armor": reader},
        ui={}, calibrated=cause != "geometry",
    )
    assert all(m["value"] is None for m in measured)
    assert all(m["status"] == "UNKNOWN" for m in measured)
    if cause == "geometry":
        assert reader.calls == 0
    assert all(m["reason"] for m in measured)


def test_zero_is_a_measured_value_and_a_peer_field_may_be_unconfigured():
    reader = Numbers(value={"hp": 0})
    reader.fields = {"hp": (0, 0, 1, 1)}
    measured = configured_hud_values(np.zeros((24, 28, 3), np.uint8), layout=layout(),
                                    readers={"player_hp_armor": reader}, ui={}, calibrated=True)
    by_name = {m["name"]: m for m in measured}
    assert by_name["hp"]["value"] == 0 and by_name["hp"]["status"] == "CANDIDATE"
    assert by_name["armor"]["value"] is None
    assert by_name["armor"]["reason"] == "unconfigured_reader_or_roi"


def test_legacy_grouped_HUD_reader_outputs_are_not_lost_under_region_names():
    base = obs(0)
    row = observation(sample=base["sample"], producer="c" * 64, signals=[], raw={"values": {
        "player_hp_armor": {"value": {"hp": 75, "armor": 50}, "confidence": .96},
        "weapon_inventory": {"value": {"weapon_text": "Phantom"}, "confidence": .98},
        "ammo_current_weapon": {"value": {"ammo_current": 12, "ammo_reserve": 30},
                                "confidence": .95},
    }})
    hud = _hud([row])
    assert [hud[k]["candidates"][0]["value"] for k in ["hp", "armor", "weapon"]] == [
        75, 50, "Phantom"]
    assert hud["ammo_current"]["candidates"][0]["value"] == 12
    assert "weapon_inventory" not in hud and "player_hp_armor" not in hud
