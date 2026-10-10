import numpy as np

from valorant_ai_coach.hud.scene_domains import domain_displacement_audit

BOXES = ((50, 60, 90, 100),)
MODEL = np.array([[1.0, 0.0, 0.0], [0.0, 1.0, 0.0]])


def test_distinctive_exact_domain_has_no_local_competing_offset():
    image = np.random.default_rng(109).integers(0, 256, (360, 640), np.uint8)
    row = domain_displacement_audit(image, image, BOXES, MODEL)[0]
    assert row["locally_unambiguous_appearance"]
    assert not row["world_mask_authorized"]
    assert not row["runtime_proof_authorized"]


def test_smooth_domain_has_high_ncc_but_competing_positions():
    image = np.tile(np.arange(640, dtype=np.uint16) % 128, (360, 1)).astype(np.uint8)
    row = domain_displacement_audit(image, image, BOXES, MODEL)[0]
    assert row["predicted_ncc"] >= 0.90
    assert row["competing_offsets"]
    assert not row["locally_unambiguous_appearance"]


def test_unknown_texture_and_unrelated_domain_do_not_support():
    image = np.zeros((360, 640), np.uint8)
    assert not domain_displacement_audit(image, image, BOXES, MODEL)[0][
        "locally_unambiguous_appearance"
    ]
    rng = np.random.default_rng(110)
    a, b = [rng.integers(0, 256, image.shape, np.uint8) for _ in range(2)]
    assert not domain_displacement_audit(a, b, BOXES, MODEL)[0]["locally_unambiguous_appearance"]


def test_protected_ui_changes_are_not_displacement_evidence():
    image = np.random.default_rng(111).integers(0, 256, (360, 640), np.uint8)
    changed = image.copy()
    changed[:28] = 0
    changed[28:120, 224:416] = 255
    assert domain_displacement_audit(image, image, BOXES, MODEL) == domain_displacement_audit(
        image, changed, BOXES, MODEL
    )


def test_complete_projected_domain_cannot_use_taps_outside_declared_current_search():
    image = np.random.default_rng(113).integers(0, 256, (360, 640), np.uint8)
    row = domain_displacement_audit(
        image, image, BOXES, MODEL, allowed_current_boxes=((50, 60, 89, 100),)
    )[0]
    assert row["predicted_ncc"] is None
    assert row["invalid_offsets"] == 289
    fractional = MODEL.copy()
    fractional[0, 2] = 0.5
    row = domain_displacement_audit(image, image, BOXES, fractional, allowed_current_boxes=BOXES)[0]
    assert row["predicted_ncc"] is None
