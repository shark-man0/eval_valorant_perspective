from pathlib import Path

import pytest

from valorant_ai_coach.hud.unedited_input import UneditedInputContract

ROOT = Path(__file__).resolve().parents[2]
SOURCE = "55d909c2d6a5f38575d1cb6c249ddfa7e2a48b96535841317adcae704c6f63b6"


def test_registered_match002_assurance_is_source_specific_not_continuity_or_identity():
    contract = UneditedInputContract.load(
        ROOT / "datasets/input_contracts/match_002.unedited.json", source_video_sha256=SOURCE)
    assert contract.source_video_sha256 == SOURCE
    assert "intentional user editing only" in contract.assurance_provenance
    assert "Recording pauses" in contract.assurance_provenance
    assert "does not certify observable game continuity" in contract.assurance_provenance
    assert "player ownership" in contract.assurance_provenance
    assert not hasattr(contract, "continuity_valid")
    assert not hasattr(contract, "player_specific_hud_valid")


def test_match002_assurance_cannot_be_used_for_another_source():
    with pytest.raises(ValueError, match="matching unedited"):
        UneditedInputContract.load(ROOT / "datasets/input_contracts/match_002.unedited.json",
                                  source_video_sha256="1" * 64)
