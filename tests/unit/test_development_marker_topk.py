import copy
import hashlib

import cv2
import numpy as np
import pytest

from valorant_ai_coach.visual.development_marker_attribution import freeze_native_sample
from valorant_ai_coach.visual.development_marker_features import (
    AppearanceCentroids,
    _digest,
    bound_patches,
)
from valorant_ai_coach.visual.development_marker_topk import broad_shape_candidates, rank_candidates


def fixture():
    image = np.zeros((128, 160, 3), np.uint8)
    cv2.circle(image, (55, 55), 7, (100, 255, 0), 2)
    cv2.circle(image, (66, 55), 7, (100, 255, 0), 2)
    sample = freeze_native_sample(
        {
            "source_id": "synthetic",
            "source_sha256": "a" * 64,
            "acquisition_id": "epoch",
            "native_epoch": "epoch",
            "native_pts_tick": 123,
            "native_time_base": "1/60",
            "acquired_frame_sha256": "b" * 64,
            "native_pixel_sha256": hashlib.sha256(image.tobytes()).hexdigest(),
        },
        frame_size_px=(160, 128),
    )
    parent = [
        {
            "center_frame_px": [55.0, 55.0],
            "ownership": "UNKNOWN",
            "geometry_only_map_position_norm": [0.2, 0.3],
            "map_position_norm": None,
            "zone_resolution": None,
        }
    ]
    return image, sample, parent


def pool_for(image, sample, parent):
    return broad_shape_candidates(
        image, sample, roi_xywh=[10, 10, 120, 100], parent=parent, profile_fingerprint="c" * 64
    )


def bound_features(image, sample, pool):
    centers = [p["center_frame_px"] for p in pool["candidates"]]
    bindings = [
        bound_patches(image, sample, centers[i : i + 128])[1] for i in range(0, len(centers), 128)
    ]
    features = np.tile([1.0, 0.0], (len(centers), 1))
    features[0] = [0.0, 1.0]
    return features, _digest(bindings)


def model(labels=None):
    return AppearanceCentroids(
        np.eye(2),
        labels or ["PLAYER", "BACKGROUND"],
        "d" * 64,
        maximum_distance=0.01,
        minimum_margin=0.9,
    )


def test_native_candidates_preserve_parent_and_touching_alternatives():
    image, sample, parent = fixture()
    before = copy.deepcopy(parent)
    pool = pool_for(image, sample, parent)
    assert pool["candidates"][: len(parent)] == before == parent
    assert len(pool["candidates"]) > 2
    assert pool["near_window_pairs"] and pool["physical_association"] == "UNKNOWN"
    assert pool["formal_outputs"] == 0 and pool["ownership"] == "UNKNOWN"
    assert pool["map_build"] == "UNKNOWN"
    assert pool_for(image, sample, parent) == pool
    pool["candidates"][0]["center_frame_px"][0] = 99
    assert parent == before


@pytest.mark.parametrize(
    "field,value",
    [
        ("source_sha256", "e" * 64),
        ("native_pts_tick", 124),
        ("native_epoch", "other"),
        ("sample_sha256", "f" * 64),
    ],
)
def test_changed_source_or_time_is_rejected(field, value):
    image, sample, parent = fixture()
    sample[field] = value
    with pytest.raises(ValueError):
        pool_for(image, sample, parent)


def test_changed_pixels_are_rejected():
    image, sample, parent = fixture()
    image[0, 0] = 255
    with pytest.raises(ValueError):
        pool_for(image, sample, parent)


@pytest.mark.parametrize(
    "roi", [[0, 0, 1025, 100], [0, 0, 60, 60], [90, 0, 100, 100], [True, 0, 100, 100], [0, 0, 100]]
)
def test_roi_bounds(roi):
    image, sample, parent = fixture()
    with pytest.raises(ValueError):
        broad_shape_candidates(
            image, sample, roi_xywh=roi, parent=parent, profile_fingerprint="c" * 64
        )


@pytest.mark.parametrize(
    "change",
    [
        "owner",
        "formal_position",
        "zone",
        "invalid_center",
        "budget",
        "formal_fact",
        "formal_events",
        "formal_self_position_fact",
    ],
)
def test_qualified_or_invalid_parent_cannot_enter(change):
    image, sample, parent = fixture()
    if change == "owner":
        parent[0]["ownership"] = "SELF"
    elif change == "formal_position":
        parent[0]["map_position_norm"] = [0.1, 0.2]
    elif change == "zone":
        parent[0]["zone_resolution"] = {}
    elif change == "invalid_center":
        parent[0]["center_frame_px"] = [float("nan"), 10]
    elif change.startswith("formal_"):
        parent[0][change] = {"actor": "player"}
    else:
        parent *= 129
    with pytest.raises(ValueError):
        pool_for(image, sample, parent)


def test_ranking_is_view_not_filter_or_ownership():
    image, sample, parent = fixture()
    pool = pool_for(image, sample, parent)
    before = copy.deepcopy(pool)
    features, binding = bound_features(image, sample, pool)
    result = rank_candidates(
        image,
        sample,
        pool,
        features=features,
        feature_fingerprint="d" * 64,
        feature_binding_sha256=binding,
        classifier=model(),
        top_k=3,
    )
    assert result["ranked_indices"][-1] == 0
    assert sorted(result["ranked_indices"]) == list(range(len(features)))
    assert result["scores"][0] == -1 and len(result["top_k_indices"]) == 3
    assert result["formal_outputs"] == 0 and result["ownership"] == "UNKNOWN"
    assert pool == before


@pytest.mark.parametrize("change", ["pool", "binding", "fingerprint", "count", "nan", "zero", "k"])
def test_ranking_rejects_stale_or_malformed_evidence(change):
    image, sample, parent = fixture()
    pool = pool_for(image, sample, parent)
    features, binding = bound_features(image, sample, pool)
    fp, k = "d" * 64, 5
    if change == "pool":
        pool["candidates"][0]["center_frame_px"][0] += 1
    elif change == "binding":
        binding = "e" * 64
    elif change == "fingerprint":
        fp = "e" * 64
    elif change == "count":
        features = features[:-1]
    elif change == "nan":
        features[0, 0] = float("nan")
    elif change == "zero":
        features[0] = 0
    else:
        k = 0
    with pytest.raises(ValueError):
        rank_candidates(
            image,
            sample,
            pool,
            features=features,
            feature_fingerprint=fp,
            feature_binding_sha256=binding,
            classifier=model(),
            top_k=k,
        )


def test_unknown_semantics_remains_ranked_not_relabelled():
    image, sample, parent = fixture()
    pool = pool_for(image, sample, parent)
    features, binding = bound_features(image, sample, pool)
    features[:] = [0.5, 0.5]
    result = rank_candidates(
        image,
        sample,
        pool,
        features=features,
        feature_fingerprint="d" * 64,
        feature_binding_sha256=binding,
        classifier=model(),
    )
    assert result["UNKNOWN"] == len(features)
    assert len(result["ranked_indices"]) == len(features)
    assert all(p["appearance_class_candidate"] == "UNKNOWN" for p in result["appearance_reviews"])


def test_rank_above_classifier_batch_limit():
    image, sample, parent = fixture()
    pool = pool_for(image, sample, parent)
    pool["candidates"] = pool["candidates"] * 60
    pool["candidates"] = pool["candidates"][:300]
    pool["pool_sha256"] = _digest({k: v for k, v in pool.items() if k != "pool_sha256"})
    features, binding = bound_features(image, sample, pool)
    result = rank_candidates(
        image,
        sample,
        pool,
        features=features,
        feature_fingerprint="d" * 64,
        feature_binding_sha256=binding,
        classifier=model(),
    )
    assert len(result["ranked_indices"]) == len(features) > 256


def test_empty_search_is_explicit():
    image, sample, _ = fixture()
    image[:] = 0
    sample["native_pixel_sha256"] = hashlib.sha256(image.tobytes()).hexdigest()
    sample = freeze_native_sample(sample, frame_size_px=(160, 128))
    pool = pool_for(image, sample, [])
    assert pool["candidates"] == [] and pool["near_window_pairs"] == []
