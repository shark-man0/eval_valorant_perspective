from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest
from trace_adapter import to_e2e_trace


def test_global_phase_confidence_does_not_authorize_player_ownership():
    result = SimpleNamespace(
        round_packages=[{"round_window": {"start_sec": 0, "end_sec": 1}}],
        observations=[
            {
                "time_sec": timestamp,
                "primary_state": "unknown",
                "state_flags": ["buy_phase_banner"],
                "quality": {
                    "hud_confidence": 0,
                    "roi_confidence": {"center_phase_banner_semantic_text": confidence},
                },
            }
            for timestamp, confidence in [(0, 0.96), (0.1, 0.94), (0.2, 0.95)]
        ],
    )
    trace = to_e2e_trace(result)
    phase = next(row for row in trace["state_intervals"] if row["state"] == "buy_phase_banner")
    assert phase["confidence"] == 0.94
    assert phase["interval"] == [0, 0.2]
    assert all(row["owner"] == "unknown" for row in trace["ownership_intervals"])
    assert not trace["events"]


@pytest.mark.parametrize("confidence", [None, float("nan"), float("inf"), -0.1, 1.1, True])
def test_trace_rejects_invalid_or_missing_confidence(confidence):
    result = SimpleNamespace(round_packages=[{
        "events": [{"type": "shot", "time_sec": 2, "confidence": confidence}],
    }])
    with pytest.raises(ValueError, match="confidence"):
        to_e2e_trace(result)


def test_duration_features_use_native_onset_timestamp():
    result = SimpleNamespace(round_packages=[{
        "events": [{"type": kind, "time_sec": 20, "confidence": .9,
                    "attributes": {"duration_sec": 3}}
                   for kind in ("status_effect", "info_peek", "hold_angle")],
    }])
    assert all(feature["interval"] == [20, 23]
               for feature in to_e2e_trace(result)["temporal_features"])


def test_trace_adapter_keeps_unknowns_confidence_and_package_order() -> None:
    package = {
        "round_no": 9,
        "round_window": {"start_sec": 1.0, "end_sec": 171.0},
        "events": [{"type": "shot", "actor": "player", "time_sec": 151.0,
                    "attributes": {"ammo_delta": -1}, "confidence": 0.73}],
        "state_snapshots": [{"time_sec": 151.0, "hp": 100, "weapon": "Vandal",
                             "ammo_current": 21, "ammo_reserve": 50,
                             "player_location": {"zone_id": "summit_mid"}}],
    }
    result = SimpleNamespace(
        round_packages=(package,),
        observations=(
            {"time_sec": 1.5, "primary_state": "unknown", "state_flags": [],
             "quality": {"hud_confidence": 0.21}},
            {"time_sec": 151.0, "primary_state": "spectator_first_person", "state_flags": [],
             "view_context": {"remote_view_type": "none"},
             "values": {"player_specific_hud_valid": False, "hp": 85,
                        "ammo_current": 21, "ammo_reserve": 50, "weapon_text": "Vandal",
                        "location_text": "Mid"},
             "quality": {"hud_confidence": 0.88, "visual_confidence": 0.67}},
        ),
        visual_observations=({"time_sec": 151.0,
            "analysis_eligibility": {"player_mechanics": False},
            "weapon_action": {"muzzle_flash_score": 0.6, "confidence": 0.67}},),
    )

    trace = to_e2e_trace(result)

    assert trace["events"][0]["round_id"] == "sample_round_1"
    assert trace["events"][0]["confidence"] == 0.73
    # The production package's teammate HUD has leaked into player fields here.
    # Keep those values visible so the supplied negative assertion can fail.
    assert trace["snapshots"][0]["player_hp"] == 100
    assert trace["snapshots"][0]["ammo_mag"] == 21
    assert trace["snapshots"][0]["weapon"] == "Vandal"
    assert trace["snapshots"][0]["zone_id"] == "summit_mid"
    assert trace["snapshots"][0]["spectated_hp"] == 85
    assert trace["snapshots"][0]["spectated_ammo_mag"] == 21
    assert trace["ownership_intervals"][0]["owner"] == "unknown"
    assert trace["ownership_intervals"][0]["confidence"] == 0.21
    assert trace["ownership_intervals"][1]["owner"] == "teammate_spectated"
    assert trace["visual_observations"][0]["actor"] == "unknown"
    assert trace["visual_observations"][0]["confidence"] == 0.67
    assert trace["temporal_features"] == []

    pack_root = Path(
        os.environ.get(
            "VALORANT_E2E_VALIDATION_PACK",
            str(Path(__file__).resolve().parents[3] / "valorant_e2e_validation_pack_v3"),
        )
    )
    evaluator_dir = pack_root / "tests"
    if not evaluator_dir.is_dir():
        pytest.skip("sibling E2E validation pack is not present")
    sys.path.insert(0, str(evaluator_dir))
    from reference_evaluator import evaluate

    assertions = json.loads(
        (evaluator_dir / "generated/e2e_assertions_v3.json").read_text(encoding="utf-8")
    )
    failures = evaluate(assertions, trace)
    assert "poison:NEG-SPECTATOR-POISON-151" in failures
