import hashlib
import sys
from pathlib import Path

import cv2
import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.diagnostics.diagnose_result_structure import structural_candidate  # noqa: E402


def text_image(text="TEAM ACE"):
    image = np.full((90, 360), 25, np.uint8)
    cv2.putText(image, text, (5, 65), cv2.FONT_HERSHEY_SIMPLEX, 1.8, 255, 3,
                cv2.LINE_AA)
    return image


def source_hashes():
    return [hashlib.sha256(str(i).encode()).hexdigest() for i in range(3)]


def test_training_and_control_scores_do_not_create_boundaries():
    image = text_image()
    controls = [image.copy(), np.full_like(image, 25), text_image("TEAM AGE")]
    report = structural_candidate([image.copy() for _ in range(3)], source_hashes(), controls)
    assert report["status"] == "training_supported_not_qualified"
    assert report["training_support"] == 3
    assert report["threshold"] == .90
    assert report["evaluation_scores"][0] >= .90
    assert report["evaluation_scores"][1] < .90
    # A whole-group NCC match can overlook one changed glyph. This is an
    # explicit counterexample, not a verified semantic result observation.
    assert report["evaluation_scores"][2] >= .90
    assert report["semantic_identity_verified"] is False
    assert report["qualification_created"] is False
    assert report["profile_adopted"] is False
    assert report["events_emitted"] == 0


def test_missing_text_remains_rejected_not_absence():
    image = np.zeros((90, 360), np.uint8)
    report = structural_candidate([image.copy() for _ in range(3)], source_hashes())
    assert report["status"] == "training_rejected"
    assert report["mask_population"] == 0
    assert "evaluation_scores" not in report


def test_reused_training_hashes_cannot_establish_support():
    image = text_image()
    report = structural_candidate([image.copy() for _ in range(3)], ["a"*64]*3)
    assert report["status"] == "training_rejected"


@pytest.mark.parametrize("crops", [[], [text_image()], [text_image(), text_image(),
                                                       np.zeros((10, 10), np.uint8)]])
def test_invalid_training_rejected(crops):
    with pytest.raises(ValueError):
        structural_candidate(crops, source_hashes()[:len(crops)])
