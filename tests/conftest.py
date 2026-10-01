import pytest


@pytest.fixture
def live_identity_signals():
    """Independent measured UI structures; never inferred from geometry fixtures."""
    return {
        "hp_hud_structure": True,
        "hp_hud_structure_confidence": 0.97,
        "ability_bar_structure": True,
        "ability_bar_structure_confidence": 0.97,
        "weapon_ammo_structure": True,
        "weapon_ammo_structure_confidence": 0.97,
        "spectator_panel_absent": True,
    }
