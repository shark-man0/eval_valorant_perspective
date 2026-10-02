import cv2
import numpy as np
import pytest

from scripts.e2e.calibration_report import sanitize_calibration
from valorant_ai_coach.hud import weapon_identity
from valorant_ai_coach.hud.spectator import detect_panel, generate_panel_reference, panel_components


def local_weapon_frames(jitter=False):
    frames = []
    for i in range(16):
        image = np.full((180, 320), 50, np.uint8)
        cv2.rectangle(image, (108, 73), (120, 87), 220, 1)
        cv2.rectangle(image, (133, 93), (146, 106), 220, 1)
        cv2.line(image, (153, 72), (163, 86), 200, 1)
        if jitter:
            image = cv2.warpAffine(
                image, np.float32([[1, 0, i % 2], [0, 1, 0]]), (320, 180), borderValue=50
            )
            image = np.clip(
                image.astype(float) + np.random.default_rng(i).normal(0, 0.5, image.shape), 0, 255
            ).astype(np.uint8)
        frames.append(image)
    return frames


def test_component_proposals_find_2d_pattern_missed_by_old_grid(monkeypatch):
    frames = local_weapon_frames()
    stats = {}
    assert weapon_identity.weapon_reference(frames, stats) is not None
    selected = stats["selected_candidate"]
    assert selected["proposal_source"] == "component_group"
    assert selected["structural_gates"]["spatial_spread"]
    assert selected["occupied_rows"] >= 2 and selected["occupied_columns"] >= 2
    original = weapon_identity.candidate_windows
    monkeypatch.setattr(
        weapon_identity,
        "candidate_windows",
        lambda e, s: [p for p in original(e, s) if p["proposal_source"] == "legacy_grid"],
    )
    assert weapon_identity.weapon_reference(frames, {}) is None


def test_component_proposals_tolerate_small_motion_and_edge_noise():
    stats = {}
    assert weapon_identity.weapon_reference(local_weapon_frames(jitter=True), stats) is not None
    assert stats["training_accept_count"] >= 3 and stats["holdout_accept_count"] >= 3


@pytest.mark.parametrize("kind", ["line", "parallel", "stripe", "narrow", "random"])
def test_adaptive_weapon_proposals_keep_negative_protections(kind):
    image = np.full((180, 320), 50, np.uint8)
    if kind == "line":
        cv2.line(image, (0, 90), (319, 90), 220, 1)
    elif kind == "parallel":
        for y in range(40, 140, 12):
            cv2.line(image, (0, y), (319, y), 220, 1)
    elif kind == "stripe":
        image[85:95] = 220
    elif kind == "narrow":
        cv2.rectangle(image, (150, 40), (153, 120), 220, 1)
    else:
        image = np.random.default_rng(2).integers(0, 256, image.shape, dtype=np.uint8)
    assert weapon_identity.weapon_reference([image] * 16, {}) is None


def test_proposals_do_not_use_holdout_to_select_localization():
    frames = local_weapon_frames()
    first = {}
    assert weapon_identity.weapon_reference(frames, first) is not None
    second = {}
    assert (
        weapon_identity.weapon_reference(
            [f if i % 2 == 0 else np.zeros_like(f) for i, f in enumerate(frames)], second
        )
        is None
    )
    assert first["proposals"] == second["proposals"]
    assert first["selected_candidate"]["roi_bounds"] == second["selected_candidate"]["roi_bounds"]
    assert second["selected_candidate"]["rejection_stage"] == "holdout"


def changed_boundary(panel_images, y=40, fragmented=False):
    panel, _ = panel_images(160, 126)
    image = cv2.cvtColor(panel, cv2.COLOR_BGR2GRAY)
    image[:20] = 60
    if fragmented:
        cv2.line(image, (5, y), (72, y), 230, 2)
        cv2.line(image, (80, y), (155, y), 230, 2)
    else:
        cv2.line(image, (5, y), (155, y), 230, 2)
    return image


@pytest.mark.parametrize(
    "y,topology", [(8, "group_header"), (40, "text_separator"), (96, "group_footer")]
)
def test_coherent_panel_topologies_and_shared_drift(panel_images, y, topology):
    image = changed_boundary(panel_images, y)
    diag = {}
    assert panel_components(image, diag) is not None
    assert diag["panel_topology"] == topology
    crops = [
        cv2.warpAffine(
            image, np.float32([[1, 0, i % 2], [0, 1, i % 2]]), (160, 126), borderValue=60
        )
        for i in range(16)
    ]
    stats = {}
    labels = generate_panel_reference(crops, stats)
    assert labels is not None
    assert stats["training_accept_count"] >= 3 and stats["holdout_accept_count"] >= 3
    assert all(detect_panel(c, labels)["panel_present"] is True for c in crops)


def test_fragmented_boundary_must_jointly_cover_group(panel_images):
    image = changed_boundary(panel_images, fragmented=True)
    diag = {}
    assert panel_components(image, diag) is not None
    assert diag["boundary_fragment_count"] >= 2 and diag["boundary_coverage"] >= 0.90
    assert generate_panel_reference([image] * 16, {}) is not None
    image[36:44, 50:120] = 60
    assert panel_components(image) is None


@pytest.mark.parametrize(
    "kind",
    [
        "portrait_only",
        "unrelated_text",
        "world_boundary",
        "partial",
        "ordering",
        "distant_boundary",
    ],
)
def test_panel_geometry_rejects_unrelated_or_partial_structure(panel_images, kind):
    image = changed_boundary(panel_images)
    if kind == "portrait_only":
        image[:20] = 60
        image[36:44] = 60
        image[25:90, 50:] = 60
    elif kind == "unrelated_text":
        image[25:90, 50:] = 60
        cv2.putText(image, "AAA", (110, 65), cv2.FONT_HERSHEY_SIMPLEX, 0.5, 230, 1)
    elif kind == "world_boundary":
        image[25:90, :50] = 60
    elif kind == "partial":
        image[25:90, 50:] = 60
    elif kind == "ordering":
        image[25:90] = 60
        cv2.rectangle(image, (95, 30), (130, 85), 200, 2)
        cv2.putText(image, "AAA", (10, 65), cv2.FONT_HERSHEY_SIMPLEX, 0.5, 230, 1)
    else:
        image = changed_boundary(panel_images, y=120)
    assert panel_components(image) is None
    assert generate_panel_reference([image] * 16, {}) is None


def test_new_localization_diagnostics_are_sanitized():
    stats = {}
    weapon_identity.weapon_reference(local_weapon_frames(), stats)
    stats["selected_candidate"]["path"] = "PRIVATE"
    stats["proposals"][0]["path"] = "PRIVATE"
    raw = {
        "schema_version": 1,
        "automatic_identity_generation": {"references": {"weapon_ammo_structure": stats}},
    }
    shared = sanitize_calibration(raw)["automatic_identity_generation"]["references"][
        "weapon_ammo_structure"
    ]["weapon_ammo_generation"]
    assert shared["proposal_count"] <= 41
    assert len(shared["proposals"]) <= 6
    assert shared["omitted_proposal_count"] > 0
    assert shared["selected_candidate"]["proposal_source"] == "component_group"
    assert "PRIVATE" not in str(shared)
