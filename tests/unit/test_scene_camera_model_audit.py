from __future__ import annotations

import numpy as np
import pytest

from scripts.diagnostics.scene_camera_model_audit import audit_world_models


def points():
    source = np.float32(
        [
            [x + dx, y + dy]
            for x, y in [(60, 80), (270, 160), (470, 230)]
            for dx in [0, 10, 20]
            for dy in [0, 10, 20]
        ]
    )
    return source, [i // 9 for i in range(len(source))]


def cloud(source, target, regions):
    return {"seed_points": source.tolist(), "current_points": target.tolist(), "regions": regions}


def test_shadow_affine_explains_shear_on_same_population_without_runtime_proof():
    source, regions = points()
    matrix = np.array([[1.15, 0.12, 5], [-0.03, 0.86, 2]])
    target = np.column_stack([source, np.ones(len(source))]) @ matrix.T
    result = audit_world_models(cloud(source, target, regions))
    assert not result["similarity"]["descriptive_geometric_quorum"]
    assert result["affine"]["descriptive_geometric_quorum"]
    assert result["affine"]["final_residual_inliers"] == len(source)
    assert result["runtime_proof_authorized"] is False


def test_shadow_projective_fit_reports_geometry_without_qualifying_photometry():
    source, regions = points()
    transform = np.array([[1, 0.04, 5], [-0.02, 1, 3], [0.001, 0.0005, 1]])
    homogeneous = np.column_stack([source, np.ones(len(source))]) @ transform.T
    target = homogeneous[:, :2] / homogeneous[:, 2, None]
    result = audit_world_models(cloud(source, target, regions))
    assert result["homography"]["descriptive_geometric_quorum"]
    assert result["homography"]["final_residual_inliers"] == len(source)
    assert result["homography"]["runtime_proof_authorized"] is False


def test_disagreeing_third_region_and_collinearity_cannot_supply_quorum():
    source, regions = points()
    target = source.copy()
    target[-9:] = np.random.default_rng(7).uniform(0, 600, (9, 2))
    result = audit_world_models(cloud(source, target, regions))
    assert not any(
        result[k]["descriptive_geometric_quorum"] for k in ["similarity", "affine", "homography"]
    )
    source[:, 1] = 45
    target = source + 2
    result = audit_world_models(cloud(source, target, regions))
    assert not any(
        result[k]["descriptive_geometric_quorum"] for k in ["similarity", "affine", "homography"]
    )


def test_shadow_inputs_reject_nonfinite_and_region_mismatch():
    source, regions = points()
    bad = source.copy()
    bad[0, 0] = np.nan
    with pytest.raises(ValueError, match="finite paired"):
        audit_world_models(cloud(bad, source, regions))
    with pytest.raises(ValueError, match="finite paired"):
        audit_world_models(cloud(source, source, regions[:-1]))
    with pytest.raises(ValueError, match="scale"):
        audit_world_models(cloud(source, source, regions), scale=2)


def test_original_fit_binding_detects_changed_model():
    source, regions = points()
    data = cloud(source, source + 1, regions)
    data["original_partial_affine"] = [[1, 0, 100], [0, 1, 0]]
    with pytest.raises(ValueError, match="not exactly reproduced"):
        audit_world_models(data)
