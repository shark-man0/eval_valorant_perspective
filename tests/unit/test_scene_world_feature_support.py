from copy import deepcopy

from scripts.diagnostics.scene_world_feature_support import common_world_feature_support


def points():
    return [
        {
            "region": region,
            "reference_xy": [x, y],
            "current_xy": [x + 1, y + 1],
            "patch_ncc": 0.97,
            "fb_error_px": 0.1,
            "model_inlier": True,
        }
        for region, x, y in ((0, 180, 80), (1, 230, 155), (4, 480, 160))
    ]


METRICS = {"accepted_reference_tracks": 3, "model_inliers": 3}


def test_world_patches_link_without_claiming_unmatched_region_pixels_or_runtime_proof():
    before, after = points(), points()
    result = common_world_feature_support(before, after, METRICS, METRICS)
    assert result["distributed_descriptive_support"]
    assert result["shared_world_feature_count"] == 3
    assert result["minimum_patch_ncc"] == 0.97
    assert not result["runtime_proof_authorized"]


def test_different_reference_feature_id_cannot_replace_missing_correspondence():
    after = points()
    after[0]["reference_xy"][0] += 1
    result = common_world_feature_support(points(), after, METRICS, METRICS)
    assert result["shared_world_feature_count"] == 2
    assert not result["distributed_descriptive_support"]


def test_positive_similarity_cannot_override_bad_tracking_or_geometry():
    for field, value in (("patch_ncc", 0.89), ("fb_error_px", 2), ("model_inlier", False)):
        after = points()
        after[0][field] = value
        assert not common_world_feature_support(points(), after, METRICS, METRICS)[
            "distributed_descriptive_support"
        ]
    bad = {"accepted_reference_tracks": 4, "model_inliers": 3}
    assert not common_world_feature_support(points(), points(), METRICS, bad)[
        "distributed_descriptive_support"
    ]


def test_both_frames_need_spatial_spread_even_if_current_view_has_it():
    before = deepcopy(points())
    for point in before:
        point["current_xy"][1] = 180
    assert not common_world_feature_support(before, points(), METRICS, METRICS)[
        "distributed_descriptive_support"
    ]


def test_insufficient_or_empty_world_reference_matches_remain_unknown():
    assert not common_world_feature_support([], [], METRICS, METRICS)[
        "distributed_descriptive_support"
    ]
