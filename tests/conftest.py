import cv2
import numpy as np
import pytest


@pytest.fixture
def panel_images():
    """Synthetic positive UI and changing scene; not real VALORANT samples."""

    def make(width, height, offset=0):
        panel = np.full((126, 160), 60, np.uint8)
        cv2.line(panel, (5, 8), (155, 8), 230, 2)
        cv2.rectangle(panel, (10, 30), (45, 85), 200, 2)
        cv2.putText(panel, "AAA", (55, 65), cv2.FONT_HERSHEY_SIMPLEX, 0.5, 230, 1)
        scene = np.tile(np.linspace(25 + offset, 100 + offset, 160, dtype=np.uint8), (126, 1))
        cv2.circle(scene, (140, 110), 8, 230, 2)
        return tuple(
            cv2.cvtColor(
                cv2.resize(p, (width, height), interpolation=cv2.INTER_NEAREST), cv2.COLOR_GRAY2BGR
            )
            for p in (panel, scene)
        )

    return make


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
        "spectator_detector_checked": True,
        "spectator_panel_present": False,
    }
