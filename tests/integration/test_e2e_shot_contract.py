"""Apply supplied shot samples to the production candidate engine, not its oracle."""

import json
import os
from pathlib import Path

import pytest

from valorant_ai_coach.visual.core import VisualEventEngine
from valorant_ai_coach.visual.models import VisualObservation


def test_supplied_shot_granularity_in_production_engine():
    project = Path(__file__).resolve().parents[2]
    pack = Path(os.environ.get("VALORANT_E2E_PACK",
                               project.parent / "valorant_e2e_validation_pack_v3"))
    fixture = pack / "fixtures/shot_granularity_contract_v1.json"
    if not fixture.is_file():
        pytest.skip("External validation pack not installed")
    for case in json.loads(fixture.read_text())["cases"]:
        samples, proofs = [], {}
        previous = None
        for i, item in enumerate(case["input_samples"]):
            ammo = item.get("ammo")
            delta = None if previous is None else ammo - previous
            samples.append(VisualObservation.from_mapping({
                "time_sec": item["t"], "frame_index": i,
                "hud_primary_state": "live_first_person",
                "analysis_eligibility": {"player_mechanics": True,
                                         "world_semantics": True,
                                         "reason_codes": ["live_first_person"]},
                "weapon_action": {"ammo_current": ammo, "ammo_delta": delta,
                                  "weapon_text": item.get("weapon"),
                                  "muzzle_flash_score": float(item.get("muzzle", False)),
                                  "confidence": .9},
            }))
            proofs[i] = {"reload_detected": item.get("reload", False)}
            previous = ammo
        candidates = VisualEventEngine().process(samples, proofs)
        shots = [candidate for candidate in candidates if candidate.type == "shot"]
        assert len(shots) == case["expected_shot_events"], case["id"]
        # Missing weapon identity in the supplied firing fixtures must not be
        # invented merely to promote the right number of candidates to events.
        if all("weapon" not in item for item in case["input_samples"]):
            assert all(shot.confidence <= .64 for shot in shots)
