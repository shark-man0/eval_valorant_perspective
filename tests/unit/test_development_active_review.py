from dataclasses import replace

import numpy as np
import pytest

from tests.unit.test_development_pseudo_labels import frame, sha
from valorant_ai_coach.visual.development_active_review import (
    ReviewCandidate,
    ReviewPolicy,
    select_review,
)
from valorant_ai_coach.visual.development_learning_dataset import Label, Split


def item(i=0, *, split=Split.DEVELOPMENT_TRAIN, **kwargs):
    return ReviewCandidate(
        frame(i, split),
        sha(f"patch{i}"),
        (1.0, float(i % 3)),
        sha("features"),
        sha("detector"),
        i % 6,
        sha("clusters"),
        0.01,
        0.5,
        (Label.PLAYER, Label.UNKNOWN),
        **kwargs,
    )


def test_audit_is_uniform_before_hard_priority_and_repeats_exactly():
    rows = [item(i) for i in range(20)]
    p = ReviewPolicy()
    a = select_review(rows, policy=p)
    b = select_review(list(reversed(rows)), policy=p)
    assert a == b
    ids = sorted(c.fingerprint for c in rows)
    expected = [ids[int(i)] for i in np.random.default_rng(p.seed).choice(20, 2, replace=False)]
    assert a["audit_ids"] == expected
    assert a["audit_sampling"]["per_item_inclusion_probability"] == 0.1
    assert not set(a["hard_ids"]) & set(a["audit_ids"])
    assert a["new_human_reviews_performed"] == 0 and a["human_review_time_sec"] is None
    assert a["ownership"] == "UNKNOWN" and a["formal_outputs"] == 0


@pytest.mark.parametrize("split", [Split.DEVELOPMENT_VALIDATION, Split.DEVELOPMENT_FROZEN_TEST])
def test_frozen_and_validation_never_enter_active_or_simulation_pool(split):
    with pytest.raises(ValueError, match="validation/frozen"):
        select_review([item(0, split=split)], policy=ReviewPolicy())


def test_previously_reviewed_and_out_of_scope_do_not_create_new_review_requests():
    rows = [item(0, annotation_status="HUMAN_CONFIRMED"), item(1, annotation_status="OUT_OF_SCOPE")]
    a = select_review(rows, policy=ReviewPolicy())
    assert a["selected_count"] == 0
    b = select_review(rows, policy=ReviewPolicy(), simulate_existing_reveal=True)
    assert b["selected_count"] == 1 and b["mode"] == "RETROSPECTIVE_LABEL_REVEAL"
    assert b["selected"][0]["candidate"]["annotation_status"] == "HUMAN_CONFIRMED"
    assert b["new_human_reviews_performed"] == 0


def test_ssl_can_be_audited_but_cannot_be_hard_semantic_training_request():
    rows = [item(i, split=Split.SSL_TRAIN) for i in range(10)]
    a = select_review(rows, policy=ReviewPolicy())
    assert len(a["audit_ids"]) == 2 and not a["hard_ids"]
    assert all(r["candidate"]["frame"]["split"] == Split.SSL_TRAIN for r in a["selected"])


def test_exact_duplicates_reduce_queue_without_copied_labels_or_coordinates():
    rows = [item(0), replace(item(1), patch_sha256=item(0).patch_sha256)]
    a = select_review(rows, policy=ReviewPolicy())
    assert a["raw_inputs"] == 2 and a["exact_unique_review_items"] == 1
    assert len(a["redundancy_suppressed"]) == 1
    assert a["semantic_labels_propagated"] == 0
    assert a["original_candidates_or_coordinates_removed"] == 0


def test_near_time_appearance_is_only_review_redundancy_and_respects_acquisition():
    one = item(0)
    f = replace(
        one.frame, native_pts_tick=1, frame_sha256=sha("newframe"), pixel_sha256=sha("newpixels")
    )
    two = replace(one, frame=f, patch_sha256=sha("newpatch"))
    a = select_review([one, two], policy=ReviewPolicy(hard_slots=8, audit_slots=0))
    assert a["hard_representatives_after_near_dedup"] == 1
    changed = replace(two, frame=replace(f, acquisition_id="new-acq", native_epoch="new-epoch"))
    b = select_review([one, changed], policy=ReviewPolicy(hard_slots=8, audit_slots=0))
    assert b["hard_representatives_after_near_dedup"] == 2


def test_physical_cluster_and_native_frame_caps_apply_to_hard_channel():
    rows = [item(i) for i in range(20)]
    rows = [
        replace(r, frame=replace(r.frame, leakage_group_id="conservative-one-group")) for r in rows
    ]
    a = select_review(rows, policy=ReviewPolicy(hard_slots=8, audit_slots=0))
    assert len(a["hard_ids"]) == 2
    rows = [replace(item(i), cluster_id=0) for i in range(20)]
    b = select_review(rows, policy=ReviewPolicy(hard_slots=8, audit_slots=0))
    assert len(b["hard_ids"]) == 2


def test_same_native_frame_is_not_repeated_for_hard_review_even_with_different_rois():
    base = item(0)
    other = replace(
        base,
        frame=replace(base.frame, roi_xywh=(100.0, 100.0, 25.0, 25.0)),
        patch_sha256=sha("anotherpatch"),
        feature=(0.0, 1.0),
    )
    a = select_review([base, other], policy=ReviewPolicy(hard_slots=8, audit_slots=0))
    assert a["hard_representatives_after_near_dedup"] == 2 and len(a["hard_ids"]) == 1


def test_importance_and_disagreement_can_prioritize_a_deathlike_unknown():
    low = replace(
        item(0), margin=0.5, known_distance=0.1, teacher_labels=(Label.PLAYER, Label.PLAYER)
    )
    high = replace(item(1), flags=("deathlike", "known_regression", "raw_geometry"))
    a = select_review([low, high], policy=ReviewPolicy(hard_slots=1, audit_slots=0))
    assert a["hard_ids"] == [high.fingerprint]
    assert a["selected"][0]["score_is_probability"] is False


@pytest.mark.parametrize(
    "mutation", [{"feature_fingerprint": sha("different")}, {"feature": (1.0, 0.0, 1.0)}]
)
def test_mixed_feature_profiles_or_dimensions_are_rejected(mutation):
    with pytest.raises(ValueError, match="fixed feature view"):
        select_review([item(0), replace(item(1), **mutation)], policy=ReviewPolicy())


@pytest.mark.parametrize(
    "policy",
    [
        ReviewPolicy(hard_slots=9, audit_slots=2),
        ReviewPolicy(hard_slots=True),
        ReviewPolicy(near_similarity=float("nan")),
    ],
)
def test_review_budget_and_invalid_policy_are_rejected(policy):
    with pytest.raises(ValueError, match="at most ten"):
        select_review([item(0)], policy=policy)
