"""Unconfirmed aggregate texture remains exclusion, never positive view identity."""

import numpy as np
import pytest

from scripts.diagnose_remote_texture_probe import texture_cases
from valorant_ai_coach.hud.classifier import HudStateClassifier
from valorant_ai_coach.hud.identity import live_identity
from valorant_ai_coach.hud.layout import HudLayout
from valorant_ai_coach.hud.readers import OpenCvHudFeatureReader, _astra_scores
from valorant_ai_coach.resources import resource_path


def heuristic_signals():
    return {
        "astral_geometry": True,
        "purple_palette": True,
        "astra_hand_interface": True,
        "remote_confidence": 1.0,
        "remote_texture_candidate": True,
        "state_confidence": 1.0,
    }


def test_synthetic_circle_texture_does_not_establish_remote_interface():
    scores = _astra_scores(texture_cases()["purple_circle_checker_texture"])
    assert all(value >= 0.90 for value in scores.values())
    frame = np.zeros((1080, 1920, 3), dtype=np.uint8)
    frame[350:750, 760:1160] = texture_cases()["purple_circle_checker_texture"]
    reader = OpenCvHudFeatureReader(
        HudLayout.load(resource_path("config/hud_layout_1080p_v3.json"))
    )
    measured = reader.observe(frame).signals
    assert measured["remote_texture_candidate"] is True
    result = HudStateClassifier().classify(measured)
    assert result.primary_state == "unknown"
    assert result.remote_view_type == "none"
    assert result.confidence <= 0.45
    assert not result.player_specific_hud_valid
    assert not result.is_player_world_view_trustworthy


def test_unconfirmed_texture_still_excludes_live_identity(live_identity_signals):
    signals = {**live_identity_signals, **heuristic_signals()}
    identity = live_identity(signals, geometry_valid=True)
    assert identity.reason == "competing_view_evidence"
    assert not identity.live
    signals["live_first_person"] = True
    result = HudStateClassifier().classify(signals)
    assert result.primary_state == "unknown"
    assert not result.player_specific_hud_valid


@pytest.mark.parametrize(
    "mode",
    [
        {"buy_menu_grid_present": True, "buy_menu_close_anchor_present": True},
        {"expanded_map_stable": True},
        {"spectated_player_panel": True, "self_hud_identity_trustworthy": False},
    ],
)
def test_unconfirmed_remote_candidate_preserves_mode_conflicts(mode):
    result = HudStateClassifier().classify({**heuristic_signals(), **mode})
    assert result.primary_state == "unknown"
    assert result.remote_view_type == "none"
    assert not result.player_specific_hud_valid


@pytest.mark.parametrize(
    "signal,subtype",
    [
        ("cypher_camera_template", "cypher_camera"),
        ("sova_drone_template", "sova_drone"),
        ("skye_trailblazer_template", "skye_trailblazer"),
        ("other_remote_view_template", "other"),
    ],
)
def test_existing_template_paths_remain_positive(signal, subtype):
    result = HudStateClassifier().classify({signal: True, "remote_confidence": 0.95})
    assert result.primary_state == "remote_control_view"
    assert result.remote_view_type == subtype
    assert not result.player_specific_hud_valid


def test_explicit_remote_candidate_contract_is_preserved():
    result = HudStateClassifier().classify(
        {"remote_control_candidate": True, "remote_view_type": "other", "remote_confidence": 0.95}
    )
    assert result.primary_state == "remote_control_view"
    assert result.remote_view_type == "other"


def test_current_frame_cannot_inherit_previous_remote_acceptance():
    classifier = HudStateClassifier()
    assert classifier.classify({"sova_drone_template": True}).primary_state == "remote_control_view"
    rejected = classifier.classify(heuristic_signals())
    assert rejected.primary_state == "unknown"
    assert rejected.remote_view_type == "none"
    assert classifier.classify({}).primary_state == "unknown"


def test_existing_confirmed_semantic_astral_contract_is_preserved():
    signals = heuristic_signals()
    signals.pop("remote_texture_candidate")
    assert HudStateClassifier().classify(signals).primary_state == "remote_control_view"
