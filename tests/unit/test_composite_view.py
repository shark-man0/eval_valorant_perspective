import json
from copy import deepcopy

import cv2
import numpy as np
import pytest

from tests.unit.test_shared_game_timeline import obs
from valorant_ai_coach.temporal.composite_view import VERSION, AgentCatalogMatcher, measure_view
from valorant_ai_coach.temporal.game import DevelopmentGameTimeline, observation


def visual(base, raw):
    return observation(
        sample=base["sample"],
        producer="c" * 64,
        signals=[],
        raw=raw,
        context={"stream_kind": "hud_composite_view"},
    )


def features():
    return [{"slot": i, "descriptor": ([0, 100] * 72), "status": "CANDIDATE"} for i in range(4)]


def cue():
    return {
        "schema": VERSION,
        "ability_signature": features(),
        "viewed_agent_candidates": [],
        "portrait_candidate": {},
        "report_or_log_visibility": {"combat_report": "VISIBLE"},
    }


def run(rows):
    engine = DevelopmentGameTimeline()
    for row in rows:
        engine.add(row)
    return engine.rebuild()


def test_no_first_frame_or_same_agent_ownership_assumption():
    first, second = obs(0), obs(1)
    result = run([first, visual(first, cue()), second, visual(second, cue())])
    assert all(f["viewed_identity"]["recording_player_anchor"] is None for f in result["frames"])
    assert all(f["camera"]["value"] == "UNKNOWN" for f in result["frames"])


def test_same_signature_spectator_does_not_become_self_or_alive():
    anchor, spec = obs(0, ["owner_hud"]), obs(1, ["spectator"])
    result = run([anchor, visual(anchor, cue()), spec, visual(spec, cue())])
    frame = result["frames"][-1]
    assert frame["viewed_identity"]["agent_signature_relation"] == "COMPATIBLE"
    assert frame["camera"]["value"] == "SPECTATOR"
    assert frame["life"]["value"] == "UNKNOWN"
    assert frame["map"]["current_self_position_candidates"] == []
    assert result["formal_outputs"] == 0


def test_anchor_not_carried_across_epoch_or_confirmed_break():
    anchor, other = obs(0, ["owner_hud"]), obs(1, epoch="other")
    result = run([anchor, visual(anchor, cue()), other, visual(other, cue())])
    assert result["frames"][-1]["viewed_identity"]["recording_player_anchor"] is None
    other = obs(1, continuity={"content_break_confirmed": True})
    result = run([anchor, visual(anchor, cue()), other, visual(other, cue())])
    assert result["frames"][-1]["viewed_identity"]["recording_player_anchor"] is None


def test_current_report_persistence_is_not_a_new_death():
    first, second = obs(0, ["owner_hud", "report"]), obs(1, ["owner_hud", "report"])
    result = run([first, visual(first, cue()), second, visual(second, cue())])
    assert result["frames"][-1]["life"]["value"] == "ALIVE"
    assert not any(t["kind"] == "death" for t in result["transitions"])


def test_counter_and_keybind_pixels_do_not_change_ability_glyphs():
    image = np.random.default_rng(4).integers(0, 256, (1080, 1920, 3), dtype=np.uint8)
    changed = deepcopy(image)
    changed[1030:, 730:1180] = 0
    assert (
        measure_view(image, {})["ability_signature"]
        == measure_view(changed, {})["ability_signature"]
    )


def test_dark_hud_is_missing_not_matching_agent():
    result = measure_view(np.zeros((1080, 1920, 3), np.uint8), {})
    assert all(s["descriptor"] is None for s in result["ability_signature"])
    assert result["viewed_agent_candidates"] == []


def test_explicit_public_reference_assets_are_bound_and_not_recorder_identity(tmp_path):
    reference = np.zeros((32, 32, 4), np.uint8)
    cv2.circle(reference, (16, 16), 12, (255, 255, 255, 255), 2)
    cv2.imwrite(str(tmp_path / "glyph.png"), reference)
    cv2.imwrite(str(tmp_path / "portrait.png"), reference[:, :, :3])
    agent = {
        "name": "SyntheticAgent",
        "portrait_small": "portrait.png",
        "abilities": {
            slot: {"image": "glyph.png"} for slot in ("Grenade", "Ability1", "Ability2", "Ultimate")
        },
    }
    path = tmp_path / "catalog.json"
    path.write_text(
        json.dumps(
            {
                "characters": [agent],
                "catalog_version": "synthetic",
                "source_url": "https://example.invalid/synthetic",
            }
        ),
        encoding="utf-8",
    )
    matcher = AgentCatalogMatcher(path)
    pixels = np.zeros((1080, 1920, 3), np.uint8)
    raw = measure_view(pixels, {})
    matcher.measure(pixels, raw)
    assert raw["viewed_agent_selection"] == "UNKNOWN"
    assert raw["viewed_agent_candidates"][0]["ownership"] == "UNKNOWN"
    assert len(matcher.bindings["asset_sha256s"]) == 2
    agent["portrait_small"] = "../foreign.png"
    path.write_text(json.dumps({"characters": [agent]}), encoding="utf-8")
    with pytest.raises(ValueError, match="outside explicit catalog"):
        AgentCatalogMatcher(path)
