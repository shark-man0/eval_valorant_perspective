from __future__ import annotations

import cv2
import numpy as np
import pytest

from valorant_ai_coach.hud import spectator as spectator_module
from valorant_ai_coach.hud.spectator import (
    PanelReference,
    component_match_diagnostics,
    detect_panel,
    generate_panel_reference,
    panel_components,
)

HEIGHT, WIDTH = 180, 320
BACKGROUND = 60


def _paint_text_row(image: np.ndarray, y: int, seed: int) -> None:
    """Draw generic separated glyph-like strokes without OCR content."""
    rng = np.random.default_rng(seed)
    x = 92
    for index in range(6):
        width = int(rng.integers(5, 9))
        height = int(rng.integers(7, 11))
        top = y - height
        color = int(rng.integers(185, 236))
        cv2.line(image, (x, top), (x, y), color, 1)
        cv2.line(image, (x, top), (x + width, top), color, 1)
        cv2.line(image, (x + width, top), (x + width, y), color, 1)
        if index % 2 == 0:
            cv2.line(image, (x, top + height // 2), (x + width, top + height // 2), color, 1)
        x += width + 4


def frameless_panel() -> np.ndarray:
    """Separator, generic image-like marks, and two aligned rows; no enclosing frame."""
    image = np.full((HEIGHT, WIDTH), BACKGROUND, dtype=np.uint8)
    # Thin separator: 64px tall, 35.6% of the synthetic ROI height.
    cv2.line(image, (20, 32), (20, 95), 235, 2)

    # Irregular, separated geometric marks occupy the area just right of the line.
    # They are deliberately abstract, with no face, agent, or semantic identity.
    polygons = (
        ((25, 38), (32, 36), (37, 42), (34, 48), (27, 47)),
        ((42, 37), (49, 39), (50, 46), (45, 49), (40, 44)),
        ((59, 38), (66, 36), (70, 42), (68, 48), (61, 47)),
        ((27, 53), (34, 51), (38, 57), (35, 63), (28, 62)),
        ((44, 52), (50, 54), (51, 61), (46, 64), (41, 59)),
        ((61, 53), (68, 51), (72, 57), (69, 64), (63, 62)),
        ((26, 70), (33, 68), (38, 73), (35, 80), (28, 79)),
        ((44, 69), (50, 71), (52, 77), (47, 81), (41, 76)),
        ((61, 70), (68, 68), (72, 74), (69, 81), (63, 79)),
    )
    for index, points in enumerate(polygons):
        contour = np.asarray(points, dtype=np.int32)
        cv2.fillPoly(image, [contour], 120 + (index * 13) % 100)
        cv2.polylines(image, [contour], True, 225, 1)
        x, y = points[0]
        cv2.line(image, (x + 2, y + 3), (x + 5, y + 6), 245, 1)

    _paint_text_row(image, 56, 11)
    _paint_text_row(image, 82, 19)
    return image


def _base() -> np.ndarray:
    return np.tile(np.linspace(42, 84, WIDTH, dtype=np.uint8), (HEIGHT, 1))


def _chat_and_unrelated_line() -> np.ndarray:
    image = _base()
    # Chat-like rows are distant from a decorative rule and have no image slot.
    cv2.line(image, (12, 20), (306, 20), 225, 2)
    for y, length in ((118, 74), (133, 58), (148, 85)):
        cv2.line(image, (205, y), (205 + length, y), 205, 1)
        cv2.rectangle(image, (190, y - 5), (195, y), 170, 1)
    return image


def _diagonal_slats_with_chat() -> np.ndarray:
    image = _base()
    # A coherent slatted background can supply many edges but lacks localized
    # portrait-like components and consistent image/text separation.
    for x in range(-45, 105, 13):
        cv2.line(image, (x, 102), (x + 78, 26), 225, 2)
    cv2.line(image, (20, 32), (20, 95), 235, 2)
    for y in (56, 82):
        for x in (92, 104, 117, 129, 143):
            cv2.rectangle(image, (x, y - 8), (x + 5, y), 210, 1)
    return image


def _hud_decoration_only() -> np.ndarray:
    image = _base()
    # Health/ammo bars, ability slots, and a small timer-like display.
    cv2.rectangle(image, (12, 154), (94, 164), 225, 2)
    cv2.rectangle(image, (12, 168), (68, 175), 185, 1)
    for x in (112, 135, 158, 181):
        cv2.rectangle(image, (x, 154), (x + 14, 169), 215, 1)
    for x, y in ((248, 22), (263, 22), (278, 22), (248, 31), (263, 31), (278, 31)):
        cv2.rectangle(image, (x, y), (x + 8, y + 5), 225, 1)
    return image


def _missing_group(kind: str) -> np.ndarray:
    image = frameless_panel()
    if kind == "separator":
        image[28:101, 16:25] = BACKGROUND
    elif kind == "image":
        image[30:98, 22:79] = BACKGROUND
    elif kind == "text":
        image[40:88, 88:180] = BACKGROUND
    else:
        raise AssertionError(kind)
    return image


def _single_group(kind: str) -> np.ndarray:
    image = np.full((HEIGHT, WIDTH), BACKGROUND, dtype=np.uint8)
    if kind == "separator":
        cv2.line(image, (20, 32), (20, 95), 235, 2)
    elif kind == "image":
        for points in (
            ((28, 42), (36, 38), (41, 47), (33, 51)),
            ((49, 42), (57, 39), (62, 48), (54, 52)),
            ((35, 67), (44, 63), (49, 73), (40, 77)),
        ):
            cv2.fillPoly(image, [np.asarray(points, dtype=np.int32)], 210)
    elif kind == "text":
        _paint_text_row(image, 56, 11)
        _paint_text_row(image, 82, 19)
    else:
        raise AssertionError(kind)
    return image


def _partial_or_displaced(kind: str) -> np.ndarray:
    image = frameless_panel()
    if kind == "partial_separator":
        image[62:101, 16:25] = BACKGROUND
    elif kind == "partial_image":
        image[64:99, 22:79] = BACKGROUND
    elif kind == "displaced_text":
        image[40:88, 88:180] = BACKGROUND
        _paint_text_row(image, 118, 11)
        _paint_text_row(image, 145, 19)
    else:
        raise AssertionError(kind)
    return image


def _shift(image: np.ndarray, dx: int, dy: int) -> np.ndarray:
    matrix = np.float32([[1, 0, dx], [0, 1, dy]])
    return cv2.warpAffine(image, matrix, (WIDTH, HEIGHT), borderValue=BACKGROUND)


def test_frameless_positive_is_self_consistent_and_keeps_shared_offset_contract() -> None:
    image = frameless_panel()
    reference = panel_components(image)
    assert isinstance(reference, PanelReference)
    assert component_match_diagnostics(image, reference)["passed"]
    for dx, dy in ((1, 0), (-1, 1), (2, -2)):
        assert component_match_diagnostics(_shift(image, dx, dy), reference)["passed"]


def test_frameless_positive_survives_existing_training_and_holdout_gates() -> None:
    image = frameless_panel()
    stats = {}
    reference = generate_panel_reference([image.copy() for _ in range(8)], stats)

    assert isinstance(reference, PanelReference)
    assert stats["training_accept_count"] >= 3
    assert stats["holdout_accept_count"] == 4
    assert detect_panel(image, reference)["panel_present"] is True


@pytest.mark.parametrize(
    "image_factory",
    [
        _chat_and_unrelated_line,
        _diagonal_slats_with_chat,
        _hud_decoration_only,
        lambda: _base(),
        lambda: _single_group("separator"),
        lambda: _single_group("image"),
        lambda: _single_group("text"),
        lambda: _missing_group("separator"),
        lambda: _missing_group("image"),
        lambda: _missing_group("text"),
    ],
    ids=(
        "chat-plus-unrelated-line",
        "diagonal-world-slats-plus-chat",
        "hud-decoration",
        "no-groups",
        "separator-only",
        "image-only",
        "text-only",
        "missing-separator",
        "missing-image",
        "missing-text",
    ),
)
def test_frameless_training_rejects_independent_negative_shapes(image_factory) -> None:
    image = image_factory()
    assert panel_components(image) is None
    stats = {}
    assert generate_panel_reference([image.copy() for _ in range(8)], stats) is None


@pytest.mark.parametrize("seed", range(8))
def test_frameless_training_rejects_dense_random_noise(seed: int) -> None:
    image = np.random.default_rng(seed).integers(0, 256, (HEIGHT, WIDTH), dtype=np.uint8)
    assert panel_components(image) is None
    assert generate_panel_reference([image.copy() for _ in range(8)], {}) is None


@pytest.mark.parametrize("kind", ["partial_separator", "partial_image", "displaced_text"])
def test_frameless_partial_or_displaced_panel_remains_unknown(kind: str) -> None:
    positive = frameless_panel()
    reference = panel_components(positive)
    assert isinstance(reference, PanelReference)

    result = detect_panel(_partial_or_displaced(kind), reference)
    assert result["panel_present"] is None
    assert result["checked"] is False


@pytest.mark.parametrize("seed", range(8))
def test_frameless_runtime_noise_never_proves_panel_presence(seed: int) -> None:
    positive = frameless_panel()
    reference = panel_components(positive)
    assert isinstance(reference, PanelReference)
    noise = np.random.default_rng(seed).integers(0, 256, (HEIGHT, WIDTH), dtype=np.uint8)

    result = detect_panel(noise, reference)
    assert result["panel_present"] is not True


def _large_connected_image_slot() -> np.ndarray:
    image = frameless_panel()
    image[30:98, 22:79] = BACKGROUND
    # A single filled serrated contour yields one connected edge component,
    # despite spanning most of the inferred portrait slot.
    points: list[tuple[int, int]] = []
    for x in range(26, 75):
        points.append((x, 35 + (x % 2) * 2))
    for y in range(42, 90):
        points.append((72 + (y % 2) * 2, y))
    for x in range(75, 25, -1):
        points.append((x, 91 - (x % 2) * 2))
    for y in range(91, 41, -1):
        points.append((26 + (y % 2) * 2, y))
    cv2.fillPoly(image, [np.asarray(points, dtype=np.int32)], 225)
    return image


def _one_slot_line(direction: str) -> np.ndarray:
    image = frameless_panel()
    image[30:98, 22:79] = BACKGROUND
    if direction == "horizontal":
        cv2.line(image, (27, 62), (74, 62), 230, 2)
    else:
        cv2.line(image, (50, 37), (50, 91), 230, 2)
    return image


def _rectangular_world_grid_with_rows() -> np.ndarray:
    image = frameless_panel()
    image[30:98, 22:79] = BACKGROUND
    # A periodic axis-aligned world grid is not portrait/image evidence.
    for x in range(25, 79, 8):
        cv2.line(image, (x, 33), (x, 94), 220, 1)
    for y in range(36, 96, 8):
        cv2.line(image, (24, y), (77, y), 220, 1)
    return image


def _unrelated_distant_boundary() -> np.ndarray:
    image = frameless_panel()
    # Remove the side separator, then add a far horizontal decoration that
    # cannot establish a relationship between image slot and text rows.
    image[28:101, 16:25] = BACKGROUND
    cv2.line(image, (8, 157), (309, 157), 230, 2)
    return image


def _portrait_like_without_text() -> np.ndarray:
    image = frameless_panel()
    image[40:88, 88:180] = BACKGROUND
    return image


def test_frameless_rejects_single_large_connected_image_component() -> None:
    diagnostics = {}
    assert panel_components(_large_connected_image_slot(), diagnostics) is None
    proposals = diagnostics["frameless_candidates"]
    assert proposals
    assert all(item["portrait_localized_component_count"] == 1 for item in proposals)


@pytest.mark.parametrize("direction", ["horizontal", "vertical"])
def test_frameless_rejects_single_axis_aligned_slot_line(direction: str) -> None:
    assert panel_components(_one_slot_line(direction)) is None


def test_frameless_rejects_rectangular_grid_even_with_rule_and_aligned_rows() -> None:
    image = _rectangular_world_grid_with_rows()
    assert panel_components(image) is None
    assert generate_panel_reference([image.copy() for _ in range(8)], {}) is None


def test_frameless_rejects_unrelated_distant_boundary() -> None:
    assert panel_components(_unrelated_distant_boundary()) is None


def test_frameless_rejects_portrait_like_marks_without_text_rows() -> None:
    assert panel_components(_portrait_like_without_text()) is None


def test_generation_only_proposes_from_training_frames(monkeypatch) -> None:
    image = frameless_panel()
    observed: list[int] = []
    original = spectator_module.panel_components

    def spy(gray, diagnostics=None):
        observed.append(len(observed))
        return original(gray, diagnostics)

    monkeypatch.setattr(spectator_module, "panel_components", spy)
    stats = {}
    generate_panel_reference([image.copy() for _ in range(8)], stats)

    assert len(observed) == 4
    assert stats["proposal_sample_count"] == 4
    assert stats["holdout_proposal_skipped_count"] == 4
    assert [sample["reason"] for sample in stats["samples"][1::2]] == [
        "holdout_not_proposed"
    ] * 4
