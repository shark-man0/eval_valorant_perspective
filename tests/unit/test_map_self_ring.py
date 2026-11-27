from pathlib import Path

import cv2
import numpy as np
import pytest

from valorant_ai_coach.temporal.map_self_ring import read_self_ring, ring_support_at

FRAMES = (Path(__file__).resolve().parents[2] / "ValorantData" / "valorant_e2e_validation_pack_v3"
          / "assets" / "reference_frames")
GOLD = (175, 235, 245)  # BGR pale gold, HSV ~ (28, 70, 245)
TEAL = (200, 220, 90)


def _marker(image: np.ndarray, center: tuple[int, int], color: tuple[int, int, int],
            seed: int) -> None:
    rng = np.random.default_rng(seed)
    cv2.circle(image, center, 8, color, 3)
    x, y = center
    patch = rng.integers(40, 200, (9, 9, 3), dtype=np.uint8)
    disk = np.zeros((9, 9), np.uint8)
    cv2.circle(disk, (4, 4), 4, 1, -1)
    region = image[y - 4:y + 5, x - 4:x + 5]
    region[disk > 0] = patch[disk > 0]


def _minimap() -> np.ndarray:
    roi = np.full((427, 455, 3), (60, 30, 70), np.uint8)
    cv2.rectangle(roi, (60, 60), (400, 380), (150, 150, 150), -1)
    return roi


def test_unique_gold_ring_is_found_among_other_markers() -> None:
    roi = _minimap()
    _marker(roi, (200, 180), GOLD, 1)
    _marker(roi, (260, 220), TEAL, 2)
    # A saturated yellow ability icon is not the pale highlight.
    cv2.fillPoly(roi, [np.array([[100, 300], [120, 300], [110, 283]])], (0, 230, 255))
    result = read_self_ring(roi)
    assert result["status"] == "UNIQUE"
    assert result["center_roi_px"] == pytest.approx([200, 180], abs=1)
    assert result["qualified"] is False and result["position_authority"] is False


def test_two_gold_rings_abstain_and_no_ring_is_absent() -> None:
    roi = _minimap()
    _marker(roi, (150, 150), GOLD, 3)
    _marker(roi, (300, 250), GOLD, 4)
    assert read_self_ring(roi)["status"] == "AMBIGUOUS"
    assert read_self_ring(_minimap())["status"] == "ABSENT"


def test_filled_warm_area_is_not_a_ring() -> None:
    roi = _minimap()
    cv2.circle(roi, (200, 200), 12, GOLD, -1)
    assert read_self_ring(roi)["status"] == "ABSENT"


def test_support_check_reads_canonical_pixels_near_a_point() -> None:
    roi = _minimap()
    _marker(roi, (200, 180), GOLD, 5)
    assert ring_support_at(roi, (201.4, 179.2))["supported"] is True
    assert ring_support_at(roi, (260.0, 260.0))["supported"] is False


@pytest.mark.parametrize(("name", "status"), [
    ("r1_smoke_core_059.500s.jpg", "UNIQUE"),
    ("r2_hp80_143.000s.jpg", "UNIQUE"),
    ("r2_death_ui_148.000s.jpg", "ABSENT"),
    ("r2_buy_menu_110.000s.jpg", "ABSENT"),
    ("r1_death_first_visible_074.400s.jpg", "ABSENT"),
])
def test_reference_frames(name: str, status: str) -> None:
    image = cv2.imread(str(FRAMES / name))
    assert image is not None
    assert read_self_ring(image[48:475, 20:475])["status"] == status
