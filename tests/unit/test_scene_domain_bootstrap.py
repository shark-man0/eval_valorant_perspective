import hashlib
import json

import cv2
import numpy as np
import pytest

from scripts.diagnostics.scene_correspondence import sha256
from valorant_ai_coach.hud.scene_references import WorldDomainBootstrap

BOXES = ((40, 50, 100, 110), (40, 160, 100, 220), (460, 160, 540, 220))


@pytest.fixture
def source(tmp_path):
    image = np.random.default_rng(113).integers(0, 256, (360, 640), np.uint8)
    asset = tmp_path / "world.png"
    cv2.imwrite(str(asset), cv2.resize(image, (1920, 1080), interpolation=cv2.INTER_NEAREST))
    data = {
        "schema_version": 1,
        "scope": "diagnostic_reviewed_domains",
        "references": [
            {
                "id": "synthetic-world",
                "asset": "world.png",
                "asset_sha256": sha256(asset),
                "source_pixel_sha256": hashlib.sha256(cv2.imread(str(asset)).tobytes()).hexdigest(),
                "world_boxes_640x360": BOXES,
                "review_provenance": "Synthetic world domains",
            }
        ],
    }
    path = tmp_path / "profile.json"
    path.write_text(json.dumps(data))
    return image, path, data


def test_image_only_proposal_is_not_a_previous_native_frame_or_world_mask(source):
    image, path, _ = source
    result = WorldDomainBootstrap(path).recognize(image)
    assert result["diagnostic_initialization_proposed"]
    assert not result["reference_is_observed_previous_frame"]
    assert not result["whole_roi_world_attested"]
    assert not result["runtime_proof_authorized"]
    assert not result["qualification_created"]


def test_other_scene_cannot_inherit_reviewed_world_labels(source):
    image, path, _ = source
    other = np.random.default_rng(114).integers(0, 256, image.shape, np.uint8)
    assert not WorldDomainBootstrap(path).recognize(other)["diagnostic_initialization_proposed"]


def test_protected_ui_is_not_initialization_evidence(source):
    image, path, _ = source
    bootstrap = WorldDomainBootstrap(path)
    before = bootstrap.recognize(image)
    changed = image.copy()
    changed[:28] = 0
    changed[28:120, 224:416] = 255
    assert bootstrap.recognize(changed) == before


def test_competing_reference_proposals_are_withheld(source):
    image, path, data = source
    data["references"].append({**data["references"][0], "id": "other-reference"})
    path.write_text(json.dumps(data))
    result = WorldDomainBootstrap(path).recognize(image)
    assert result["reference_ambiguity"]
    assert not result["diagnostic_initialization_proposed"]


def test_landmark_scope_is_not_implicitly_promoted_to_domain_review(source):
    _, path, data = source
    data["scope"] = "diagnostic_landmarks_only"
    path.write_text(json.dumps(data))
    with pytest.raises(ValueError):
        WorldDomainBootstrap(path)


def test_displaced_current_candidates_need_projected_joint_support(source):
    image, path, _ = source
    current = np.roll(image, 40, axis=1)
    destinations = ((0, 28, 224, 360), (416, 28, 640, 360), (224, 120, 416, 360))
    result = WorldDomainBootstrap(path).recognize(current, current_search_boxes=destinations)
    assert result["diagnostic_initialization_proposed"]
    proposal = result["proposals"][0]
    assert proposal["joint"]["locally_unique_joint_appearance"]
    np.testing.assert_allclose(
        np.asarray(proposal["reference_to_current_affine"])[:, 2], [40, 0], atol=0.05
    )
    assert not result["whole_roi_world_attested"]
    assert not result["runtime_proof_authorized"]
