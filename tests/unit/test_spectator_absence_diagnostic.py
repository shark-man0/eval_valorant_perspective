"""Safety and privacy checks for offline Spectator absence experiments."""

import json
import sys

import cv2
import numpy as np
import pytest

from scripts.diagnose_spectator_absence import candidate_vetoes, main, normalized_features
from valorant_ai_coach.hud.spectator_icon import detect_icon


def ordinary():
    image = np.full((83, 75, 3), 70, np.uint8)
    cv2.rectangle(image, (8, 12), (66, 70), (160, 160, 160), 1)
    return image


def test_contrast_normalization_preserves_directional_sparse_world_absence():
    image = ordinary()
    result = detect_icon(image)
    assert result["panel_present"] is False
    assert not candidate_vetoes(image, result)["normalized_orientation"]
    assert normalized_features(image)["bins"] < 8


def test_veto_never_proves_positive_or_promotes_unknown():
    for result in (
        {"checked": False, "panel_present": None},
        {"checked": True, "panel_present": True},
    ):
        assert not any(candidate_vetoes(ordinary(), result).values())
        assert "metrics" not in result


def test_bad_crop_geometry_cannot_enter_normalized_comparison():
    with pytest.raises(ValueError, match="geometry"):
        normalized_features(np.full((83, 120), 80, np.uint8))


def test_diagnostic_output_has_only_aggregate_counts(tmp_path, monkeypatch):
    image_path = tmp_path / "private_world.png"
    assert cv2.imwrite(str(image_path), ordinary())
    manifest = tmp_path / "private_manifest.json"
    manifest.write_text(
        json.dumps(
            {"portrait_training": [], "portrait_holdout": [], "ordinary_absence": [str(image_path)]}
        )
    )
    output = tmp_path / "aggregate.json"
    monkeypatch.setattr(sys, "argv", ["diagnostic", str(manifest), str(output)])
    main()
    text = output.read_text()
    data = json.loads(text)
    assert data["diagnostic_only"]
    assert data["cohorts"]["ordinary_absence"]["counts"]["runtime_checked_absence"] == 1
    assert str(tmp_path) not in text
    assert "time_sec" not in text and "frame_index" not in text


def test_identical_pixels_across_training_holdout_reject(tmp_path, monkeypatch):
    image_path = tmp_path / "private.png"
    assert cv2.imwrite(str(image_path), ordinary())
    manifest = tmp_path / "private.json"
    manifest.write_text(
        json.dumps(
            {
                "portrait_training": [str(image_path)],
                "portrait_holdout": [str(image_path)],
                "ordinary_absence": [],
            }
        )
    )
    monkeypatch.setattr(sys, "argv", ["diagnostic", str(manifest), str(tmp_path / "output.json")])
    with pytest.raises(ValueError, match="identical decoded pixels"):
        main()


def test_oracle_fields_rejected_by_diagnostic_contract(tmp_path, monkeypatch):
    manifest = tmp_path / "private.json"
    manifest.write_text(
        json.dumps(
            {
                "portrait_training": [],
                "portrait_holdout": [],
                "ordinary_absence": [],
                "expected_state": "spectator",
            }
        )
    )
    monkeypatch.setattr(sys, "argv", ["diagnostic", str(manifest), str(tmp_path / "output.json")])
    with pytest.raises(ValueError, match="exact diagnostic cohort"):
        main()
