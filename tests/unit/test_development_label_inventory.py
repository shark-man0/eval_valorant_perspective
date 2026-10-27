from dataclasses import replace

import pytest

from tests.unit.test_development_pseudo_labels import frame, sha
from valorant_ai_coach.visual.development_label_inventory import (
    HumanLabelInventory,
    HumanReviewReference,
)
from valorant_ai_coach.visual.development_learning_dataset import (
    FrameLabel,
    Label,
    LabelOrigin,
    Split,
)


def reference(label=Label.PLAYER):
    f = frame()
    return HumanReviewReference(
        f,
        FrameLabel(f.frame_sha256, label, LabelOrigin.HUMAN_CONFIRMED, f.roi_xywh),
        sha("review"),
        "UNKNOWN",
    )


def test_reuse_keeps_human_origin_and_counts_dedup_without_reconfirmation():
    r = reference()
    index = HumanLabelInventory([r, r])
    result = index.lookup(r.frame)
    assert index.summary["unique_human_labels"] == 1
    assert index.summary["duplicate_references_removed"] == 1
    assert index.summary["human_reconfirmed_by_code"] == 0
    assert result["annotation"] == r.annotation
    assert result["status"] == "HUMAN_CONFIRMED" and result["ownership"] == "UNKNOWN"


@pytest.mark.parametrize(
    "field,value",
    [
        ("native_pts_tick", 100),
        ("native_epoch", "other"),
        ("source_sha256", sha("other")),
        ("acquisition_id", "other"),
        ("pixel_sha256", sha("other")),
    ],
)
def test_matching_pixel_or_roi_never_extends_review_to_another_native_observation(field, value):
    r = reference()
    index = HumanLabelInventory([r])
    result = index.lookup(replace(r.frame, **{field: value}))
    assert result["status"] == "UNREVIEWED" and result["annotation"] is None


def test_unknown_human_answer_is_not_an_unreviewed_or_out_of_scope_case():
    r = reference(Label.UNKNOWN)
    index = HumanLabelInventory([r])
    assert index.lookup(r.frame)["status"] == "HUMAN_CONFIRMED"
    assert index.lookup(r.frame)["annotation"].label is Label.UNKNOWN
    assert index.lookup(r.frame, out_of_scope=True)["status"] == "OUT_OF_SCOPE"
    assert index.lookup(r.frame, out_of_scope=True)["annotation"] is None


def test_frozen_role_cannot_be_reclassified_as_training_to_reuse_a_label():
    r = reference()
    r = replace(r, frame=replace(r.frame, split=Split.DEVELOPMENT_FROZEN_TEST))
    index = HumanLabelInventory([r])
    assert index.lookup(r.frame)["status"] == "HUMAN_CONFIRMED"
    with pytest.raises(ValueError, match="crosses splits"):
        index.lookup(replace(r.frame, split=Split.DEVELOPMENT_TRAIN))


def test_pseudo_or_conflicting_labels_cannot_enter_human_inventory():
    r = reference()
    with pytest.raises(ValueError, match="human review"):
        HumanLabelInventory(
            [replace(r, annotation=replace(r.annotation, origin=LabelOrigin.PSEUDO))]
        )
    with pytest.raises(ValueError, match="Conflicting human"):
        HumanLabelInventory([r, reference(Label.UI)])


def test_experiment_bookkeeping_changes_do_not_require_duplicate_annotation():
    r = reference()
    index = HumanLabelInventory([r])
    f = replace(
        r.frame,
        exposure_fingerprint=sha("new-exposure"),
        extraction_fingerprint=sha("same-native-roi-new-extractor"),
    )
    assert index.lookup(f)["annotation"] == r.annotation
