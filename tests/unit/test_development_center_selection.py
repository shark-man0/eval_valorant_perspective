import hashlib
from copy import deepcopy

import numpy as np
import pytest

from valorant_ai_coach.visual.development_center_selection import (
    retain_parent_with_center_alternative,
    select_center_candidates,
)
from valorant_ai_coach.visual.development_marker_attribution import freeze_native_sample
from valorant_ai_coach.visual.development_marker_center import (
    CENTER_FEATURE_FINGERPRINT,
    CenterReadout,
    center_features,
)
from valorant_ai_coach.visual.development_marker_features import _digest, bound_patches


def native():
    im = np.random.default_rng(12).integers(0, 256, (64, 64, 3), dtype=np.uint8)
    sample = freeze_native_sample(
        {
            "source_id": "synthetic",
            "source_sha256": "a" * 64,
            "native_epoch": "epoch",
            "acquisition_id": "epoch",
            "native_pts_tick": 1,
            "native_time_base": "1/60",
            "acquired_frame_sha256": "b" * 64,
            "native_pixel_sha256": hashlib.sha256(im.tobytes()).hexdigest(),
        },
        frame_size_px=(64, 64),
    )
    points = [[22.0, 22.0], [22.0, 22.0], [45.0, 45.0]]
    pool = {
        "sample": sample,
        "ownership": "UNKNOWN",
        "formal_outputs": 0,
        "parent_count": 1,
        "candidates": [{"center_frame_px": p} for p in points],
    }
    pool["pool_sha256"] = _digest(pool)
    patches, binding = bound_patches(im, sample, points)
    return im, sample, pool, center_features(patches), _digest([binding])


def test_duplicate_windows_are_grouped_without_altering_centers_or_parent_prefix():
    im, sample, pool, features, binding = native()
    before = deepcopy(pool)
    result = select_center_candidates(
        im, sample, pool, features=features, feature_binding_sha256=binding
    )
    assert len(result["group_representative_indices"]) == 2
    assert any(set(g["indices"]) == {0, 1} for g in result["groups"])
    assert pool == before and result["coordinates_modified"] is False
    retained = retain_parent_with_center_alternative(pool, result, minimum_center_support=0)
    assert retained["selection_indices"] == [0, 2]
    assert retained["ownership"] == "UNKNOWN" and retained["formal_outputs"] == 0


def test_known_negative_semantic_candidate_cannot_be_the_added_alternative():
    im, sample, pool, features, binding = native()
    weights = np.zeros((42, 4))
    weights[-1, 2] = 2
    model = CenterReadout(
        np.zeros(41),
        np.full(41, 10.0),
        weights,
        feature_fingerprint=CENTER_FEATURE_FINGERPRINT,
        mode="human_semantics",
        training_fingerprint="c" * 64,
    )
    result = select_center_candidates(
        im,
        sample,
        pool,
        features=features,
        feature_binding_sha256=binding,
        semantic_model=model,
        semantic_features=features,
        semantic_feature_fingerprint=CENTER_FEATURE_FINGERPRINT,
    )
    assert result["semantic_class_candidates"] == ["UI"] * 3
    assert result["selection_indices"] == []
    # The conservative experiment preserves default parents, even if the
    # experimental semantic readout disagrees. This is not default adoption.
    retained = retain_parent_with_center_alternative(pool, result, minimum_center_support=0)
    assert retained["selection_indices"] == [0]


def test_changed_pixels_pool_binding_or_qualified_owner_is_rejected():
    im, sample, pool, features, binding = native()
    changed = im.copy()
    changed[0, 0, 0] ^= 1
    with pytest.raises(ValueError):
        select_center_candidates(
            changed, sample, pool, features=features, feature_binding_sha256=binding
        )
    for field, value in [("ownership", "SELF"), ("formal_outputs", 1), ("parent_count", 2)]:
        with pytest.raises(ValueError, match="current unqualified"):
            select_center_candidates(
                im,
                sample,
                {**pool, field: value},
                features=features,
                feature_binding_sha256=binding,
            )
    with pytest.raises(ValueError, match="feature-window"):
        select_center_candidates(
            im, sample, pool, features=features, feature_binding_sha256="d" * 64
        )


def test_weak_center_model_is_not_interchangeable_with_semantic_model():
    im, sample, pool, features, binding = native()
    model = CenterReadout(
        np.zeros(41),
        np.ones(41),
        np.zeros((42, 4)),
        feature_fingerprint=CENTER_FEATURE_FINGERPRINT,
        mode="human_semantics",
        training_fingerprint="c" * 64,
    )
    with pytest.raises(ValueError, match="Separate weak center"):
        select_center_candidates(
            im, sample, pool, features=features, feature_binding_sha256=binding, center_model=model
        )
