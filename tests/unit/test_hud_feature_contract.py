from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import Any

import cv2
import numpy as np
import pytest

from scripts.diagnostics.hud_feature_contract import (
    adjacent_change,
    deterministic_kmeans,
    file_hash,
    guarded_score,
    validate_split,
    verify_patch,
    verify_weights,
)


def frame() -> dict[str, Any]:
    return {"source_id": "dev1", "source_sha256": "a"*64, "tick": 123,
            "time_base": "1/60", "epoch": "native1", "encoded_sha256": "b"*64,
            "pixel_sha256": "c"*64}


def row() -> dict[str, Any]:
    return {"frame": frame(), "physical_match_id": "match1", "role": "SSL_TRAIN",
            "profile_sha256": "d"*64, "patch_sha256": "e"*64}


@pytest.mark.parametrize("violation", ["physical", "source", "image", "protected", "unassigned"])
def test_fitting_rejects_split_leakage_or_unadmitted_source(violation: str) -> None:
    a, b = row(), deepcopy(row())
    b["frame"].update(source_id="dev2", source_sha256="f"*64, pixel_sha256="0"*64)
    b.update(physical_match_id="match2", role="DEVELOPMENT_FROZEN_TEST")
    allowed = {"dev1": "a"*64, "dev2": "f"*64}
    if violation == "physical":
        b["physical_match_id"] = a["physical_match_id"]
    elif violation == "source":
        b["frame"].update(source_id="dev1", source_sha256="a"*64)
    elif violation == "image":
        b["frame"]["pixel_sha256"] = a["frame"]["pixel_sha256"]
    elif violation == "protected":
        allowed.pop("dev2")
    else:
        b["role"] = "UNKNOWN"
    with pytest.raises(ValueError):
        validate_split([a, b], allowed_development=allowed)


def test_different_frames_same_training_match_are_permitted() -> None:
    a, b = row(), deepcopy(row())
    b["frame"]["tick"] += 1
    assert len(validate_split([a, b], allowed_development={"dev1": "a"*64})) == 64


@pytest.mark.parametrize("change", ["source_id", "source_sha256", "epoch", "gap", "duplicate",
                                    "reversed", "time_base"])
def test_temporal_features_never_bridge_native_discontinuities(change: str) -> None:
    a, b = frame(), frame()
    b["tick"] += 1
    if change in {"source_id", "epoch"}:
        b[change] = "different"
    elif change == "source_sha256":
        b[change] = "f"*64
    elif change == "time_base":
        b[change] = "1/30"
    else:
        b["tick"] += {"gap": 1, "duplicate": -1, "reversed": -2}[change]
    z = np.array([1., 0.], dtype=np.float32)
    result = adjacent_change(a, b, z, z, expected_step=1)
    assert result["state"] == "UNKNOWN"
    assert result["change"] is None


def test_feature_change_has_no_semantic_event() -> None:
    a, b = frame(), frame()
    b["tick"] += 1
    x, y = np.eye(2, dtype=np.float32)
    result = adjacent_change(a, b, x, y, expected_step=1)
    assert result["change"] == 1
    assert result["internal_End_tick"] is None
    # Identical retained Result appearance is not another appearance event.
    assert adjacent_change(a, b, x, x, expected_step=1)["change"] == 0


def test_learned_score_cannot_override_unknown_geometry_or_digit_drop() -> None:
    assert guarded_score("12", "2", source_valid=True, geometry_valid=True)["value"] is None
    assert guarded_score(None, "12", source_valid=True, geometry_valid=True)["value"] is None
    assert guarded_score("12", "12", source_valid=True, geometry_valid=False)["value"] is None
    result = guarded_score("12", "12", source_valid=True, geometry_valid=True)
    assert result["value"] == "12" and result["formal_events"] == []
    assert result["semantic_correctness_verified"] is False
    with pytest.raises(ValueError, match="source"):
        guarded_score("12", "12", source_valid=False, geometry_valid=True)


def test_frame_profile_and_weight_integrity(tmp_path: Path) -> None:
    import hashlib
    image = np.arange(4*5*3, dtype=np.uint8).reshape(4, 5, 3)
    path = tmp_path/"synthetic.png"
    assert cv2.imwrite(str(path), image)
    record = {**row(), "path": str(path), "roi": [0, 0, 5, 4], "source_width": 5,
              "source_height": 4, "patch_sha256": file_hash(path),
              "patch_pixel_sha256": hashlib.sha256(image.tobytes()).hexdigest()}
    assert np.array_equal(verify_patch(record, profile_sha256="d"*64), image)
    with pytest.raises(ValueError, match="profile"):
        verify_patch(record, profile_sha256="0"*64)
    record["patch_pixel_sha256"] = "0"*64
    with pytest.raises(ValueError, match="pixel_hash"):
        verify_patch(record, profile_sha256="d"*64)
    weights = tmp_path/"synthetic_weights.bin"
    weights.write_bytes(b"fixed synthetic weight bytes")
    digest = file_hash(weights)
    verify_weights(weights, digest, max_bytes=100)
    weights.write_bytes(b"modified bytes")
    with pytest.raises(ValueError, match="weights"):
        verify_weights(weights, digest, max_bytes=100)
    path.write_bytes(b"changed frame")
    with pytest.raises(ValueError, match="encoded_hash"):
        verify_patch(record, profile_sha256="d"*64)


def test_clustering_is_repeatable_and_does_not_name_clusters() -> None:
    features = np.array([[0., 0.], [.1, 0.], [5., 5.], [5.1, 5.]], dtype=np.float32)
    first, centres = deterministic_kmeans(features, 2)
    second, other = deterministic_kmeans(features, 2)
    assert np.array_equal(first, second) and np.array_equal(centres, other)
    assert first[0] == first[1] and first[2] == first[3] and first[0] != first[2]


@pytest.mark.parametrize("violation", ["frozen", "label", "missing_source"])
def test_training_admission_fails_before_optional_torch_load(
    tmp_path: Path, violation: str,
) -> None:
    from scripts.diagnostics.hud_feature_learning import fit_verified_dataset
    record = {**row(), "spatial_training_sample": True, "label_kind": "UNLABELLED",
              "label": None}
    ids = {"dev1"}
    if violation == "frozen":
        record["role"] = "DEVELOPMENT_FROZEN_TEST"
    elif violation == "label":
        record.update(label_kind="PSEUDO_LABEL", label="3")
    else:
        ids.add("missing")
    with pytest.raises(ValueError, match="training_role_or_label"):
        fit_verified_dataset([record], allowed_development={"dev1": "a"*64},
                             profile_sha256="d"*64, source_ids=ids, seed=1, steps=1,
                             batch_size=2, max_seconds=1, output=tmp_path/"never_written.pt")
    assert not (tmp_path/"never_written.pt").exists()
