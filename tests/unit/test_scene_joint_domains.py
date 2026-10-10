import numpy as np
import pytest

from valorant_ai_coach.hud.scene_domains import domain_displacement_audit, joint_domain_audit

BOXES = ((40, 50, 100, 110), (40, 160, 100, 220), (460, 160, 540, 220))
MODEL = np.array([[1.0, 0.0, 0.0], [0.0, 1.0, 0.0]])


def measurements():
    return [
        {
            "region": region,
            "offset_xy": [dx, dy],
            "valid": True,
            "ncc": 0.99 if dx == dy == 0 else 0.2,
        }
        for region in range(3)
        for dy in range(-8, 9)
        for dx in range(-8, 9)
    ]


def change_offset(items, *, valid, score):
    for item in items:
        if item["offset_xy"] == [4, 0]:
            item.update(valid=valid, ncc=score)


def test_joint_match_requires_distributed_source_and_current_evidence():
    result = joint_domain_audit(BOXES, MODEL, measurements())
    assert result["locally_unique_joint_appearance"]
    assert not result["world_mask_authorized"]
    assert not result["runtime_proof_authorized"]
    same_row = ((40, 160, 100, 220), (240, 160, 300, 220), (460, 160, 540, 220))
    assert not joint_domain_audit(same_row, MODEL, measurements())[
        "locally_unique_joint_appearance"
    ]


def test_common_competing_motion_blocks_joint_uniqueness():
    items = measurements()
    change_offset(items, valid=True, score=0.95)
    result = joint_domain_audit(BOXES, MODEL, items)
    assert [4, 0] in result["joint_competing_offsets"]
    assert not result["locally_unique_joint_appearance"]


@pytest.mark.parametrize("valid", (False, True))
def test_unavailable_competitors_are_not_photometric_contradictions(valid):
    items = measurements()
    change_offset(items, valid=valid, score=None)
    result = joint_domain_audit(BOXES, MODEL, items)
    assert [4, 0] in result["unresolved_offsets"]
    assert not result["locally_unique_joint_appearance"]


def test_distinctive_domain_can_disambiguate_other_repeated_domains():
    items = measurements()
    for item in items:
        if item["region"] != 0:
            item["ncc"] = 0.95
    assert joint_domain_audit(BOXES, MODEL, items)["locally_unique_joint_appearance"]


@pytest.mark.parametrize("corruption", ("missing", "duplicate"))
def test_lattice_cannot_be_silently_truncated(corruption):
    items = measurements()
    if corruption == "missing":
        items.pop()
    else:
        items.append(items[0])
    with pytest.raises(ValueError):
        joint_domain_audit(BOXES, MODEL, items)


def test_offset_observability_does_not_change_domain_audit():
    image = np.random.default_rng(112).integers(0, 256, (360, 640), np.uint8)
    sink = []
    original = domain_displacement_audit(image, image, BOXES, MODEL)
    assert domain_displacement_audit(image, image, BOXES, MODEL, offset_sink=sink) == original
    assert len(sink) == 3 * 17 * 17
