from dataclasses import replace

import pytest

from valorant_ai_coach.visual.development_learning_dataset import (
    FORMAL_OUTPUTS,
    OWNERSHIP,
    QUALIFICATION,
    FrameLabel,
    FrameRecord,
    Label,
    LabelOrigin,
    SourceAcceptance,
    Split,
    Use,
    validate_dataset,
    validate_use,
)


def digest(char: str) -> str:
    return char * 64


def accepted() -> SourceAcceptance:
    return SourceAcceptance(True, digest("a"), digest("b"), digest("a"), digest("b"))


def frame(*, split: Split = Split.DEVELOPMENT_TRAIN, index: int = 1,
          group: str = "physical-match-1") -> FrameRecord:
    return FrameRecord(
        source_sha256=digest("c"), acquisition_id="acq-1", native_epoch="epoch-1",
        native_pts_tick=index, native_time_base="1/15360",
        frame_sha256=digest("d" if index == 1 else "e"),
        pixel_sha256=digest("f" if index == 1 else "0"), frame_size_px=(1920, 1080),
        roi_xywh=(100.0, 40.0, 500.0, 300.0), extraction_fingerprint=digest("1"),
        exposure_fingerprint=digest("2"), leakage_group_id=group, split=split,
        source_acceptance=accepted(),
    )


def label_for(row: FrameRecord, label: Label, origin: LabelOrigin) -> FrameLabel:
    return FrameLabel(row.frame_sha256, label, origin, roi_xywh=row.roi_xywh)


def test_human_semantic_label_is_bound_and_train_only():
    row = frame()
    label = label_for(row, Label.PLAYER, LabelOrigin.HUMAN_CONFIRMED)
    validate_dataset([row], [label])
    validate_use(row, Use.SUPERVISED_TRAIN, label)
    with pytest.raises(ValueError, match="development train"):
        validate_use(replace(row, split=Split.DEVELOPMENT_VALIDATION), Use.SUPERVISED_TRAIN, label)


@pytest.mark.parametrize("use", [Use.SSL, Use.PSEUDO_LABEL, Use.SELECT])
def test_frozen_test_blocks_learning_and_selection(use):
    row = frame(split=Split.DEVELOPMENT_FROZEN_TEST)
    with pytest.raises(ValueError, match="frozen test"):
        validate_use(row, use)
    validate_use(row, Use.HUMAN_REVIEW)


def test_frozen_evaluation_requires_human_labels():
    row = frame(split=Split.DEVELOPMENT_FROZEN_TEST)
    human = label_for(row, Label.DEATH_MARKER, LabelOrigin.HUMAN_CONFIRMED)
    pseudo = replace(human, origin=LabelOrigin.PSEUDO)
    validate_use(row, Use.EVALUATE, human)
    with pytest.raises(ValueError, match="human labels"):
        validate_use(row, Use.EVALUATE)
    with pytest.raises(ValueError, match="human labels"):
        validate_use(row, Use.EVALUATE, pseudo)
    with pytest.raises(ValueError, match="frozen test"):
        validate_dataset([row], [replace(pseudo, label=Label.UNKNOWN)])


def test_conservative_physical_group_cannot_cross_splits():
    with pytest.raises(ValueError, match="crosses splits"):
        validate_dataset([frame(), frame(split=Split.DEVELOPMENT_VALIDATION, index=2)])


def test_same_source_hash_cannot_cross_splits_even_with_different_group_ids():
    with pytest.raises(ValueError, match="crosses splits"):
        validate_dataset([
            frame(), frame(split=Split.DEVELOPMENT_VALIDATION, index=2, group="other")
        ])


def test_duplicate_frame_or_pixel_identity_cannot_cross_splits():
    base = frame()
    different_frame_same_pixels = replace(
        frame(split=Split.DEVELOPMENT_VALIDATION, index=2), pixel_sha256=base.pixel_sha256)
    with pytest.raises(ValueError, match="crosses splits"):
        validate_dataset([base, different_frame_same_pixels])
    duplicate_frame = replace(frame(split=Split.DEVELOPMENT_VALIDATION, index=2),
                              frame_sha256=base.frame_sha256, leakage_group_id="other")
    with pytest.raises(ValueError, match="crosses splits"):
        validate_dataset([base, duplicate_frame])


def test_unlabeled_and_pseudo_are_not_human_semantic_targets():
    row = frame()
    unlabeled = label_for(row, Label.UNKNOWN, LabelOrigin.UNLABELED)
    pseudo = label_for(row, Label.PLAYER, LabelOrigin.PSEUDO)
    validate_dataset([row], [pseudo])
    with pytest.raises(ValueError, match="human-confirmed"):
        validate_use(row, Use.SUPERVISED_TRAIN, pseudo)
    with pytest.raises(ValueError, match="UNKNOWN"):
        validate_dataset([row], [replace(unlabeled, label=Label.UI)])
    with pytest.raises(ValueError, match="one explicit label"):
        validate_dataset([row], [unlabeled, pseudo])


def test_one_native_frame_can_have_distinct_semantic_patch_roi_labels():
    player_roi = frame()
    death_roi = replace(player_roi, roi_xywh=(700.0, 40.0, 80.0, 80.0))
    player = label_for(player_roi, Label.PLAYER, LabelOrigin.HUMAN_CONFIRMED)
    death = label_for(death_roi, Label.DEATH_MARKER, LabelOrigin.HUMAN_CONFIRMED)

    validate_dataset([player_roi, death_roi], [player, death])
    validate_use(death_roi, Use.SUPERVISED_TRAIN, death,
                 dataset_frames=[player_roi, death_roi])


def test_frame_label_rejects_duplicate_and_unregistered_roi():
    row = frame()
    player = label_for(row, Label.PLAYER, LabelOrigin.HUMAN_CONFIRMED)
    duplicate_roi = replace(player, label=Label.UI)
    unknown_roi = replace(player, roi_xywh=(700.0, 40.0, 80.0, 80.0))

    with pytest.raises(ValueError, match="one explicit label"):
        validate_dataset([row], [player, duplicate_roi])
    with pytest.raises(ValueError, match="included frame ROI"):
        validate_dataset([row], [unknown_roi])


def test_label_roi_must_match_the_frame_used_and_none_must_not_be_ambiguous():
    player_roi = frame()
    death_roi = replace(player_roi, roi_xywh=(700.0, 40.0, 80.0, 80.0))
    wrong_roi_label = label_for(death_roi, Label.DEATH_MARKER, LabelOrigin.HUMAN_CONFIRMED)
    with pytest.raises(ValueError, match="ROI/frame ROI"):
        validate_use(player_roi, Use.SUPERVISED_TRAIN, wrong_roi_label,
                     dataset_frames=[player_roi, death_roi])

    ambiguous = FrameLabel(player_roi.frame_sha256, Label.PLAYER,
                           LabelOrigin.HUMAN_CONFIRMED)
    with pytest.raises(ValueError, match="ambiguous"):
        validate_dataset([player_roi, death_roi], [ambiguous])
    with pytest.raises(ValueError, match="ambiguous"):
        validate_use(player_roi, Use.SUPERVISED_TRAIN, ambiguous,
                     dataset_frames=[player_roi, death_roi])


def test_roi_omission_needs_single_full_frame_or_explicit_dataset_context():
    row = frame()
    label = FrameLabel(row.frame_sha256, Label.PLAYER, LabelOrigin.HUMAN_CONFIRMED)
    with pytest.raises(ValueError, match="ROI or complete dataset context"):
        validate_use(row, Use.SUPERVISED_TRAIN, label)
    validate_use(row, Use.SUPERVISED_TRAIN, label, dataset_frames=[row])

    full_frame = replace(row, roi_xywh=(0.0, 0.0, 1920.0, 1080.0))
    full_frame_label = FrameLabel(full_frame.frame_sha256, Label.PLAYER,
                                  LabelOrigin.HUMAN_CONFIRMED)
    validate_use(full_frame, Use.SUPERVISED_TRAIN, full_frame_label)


def test_source_receipt_hash_mutation_is_rejected():
    row = frame()
    with pytest.raises(ValueError, match="trusted hash"):
        validate_use(replace(row, source_acceptance=replace(
            accepted(), allocation_sha256=digest("9"))), Use.SSL)
    with pytest.raises(ValueError, match="accepted"):
        validate_use(replace(row, source_acceptance=replace(accepted(), accepted=False)), Use.SSL)


@pytest.mark.parametrize("roi", [(-1.0, 0.0, 1.0, 1.0), (0.0, 0.0, 0.0, 1.0),
                                  (1900.0, 0.0, 30.0, 1.0), (0.0, float("inf"), 1.0, 1.0)])
def test_invalid_or_nonfinite_roi_rejected(roi):
    with pytest.raises(ValueError, match="ROI"):
        validate_use(replace(frame(), roi_xywh=roi), Use.SSL)


def test_native_pts_is_integer_and_timebase_canonical():
    with pytest.raises(ValueError, match="integer native PTS"):
        validate_use(replace(frame(), native_pts_tick=True), Use.SSL)
    with pytest.raises(ValueError, match="canonical"):
        validate_use(replace(frame(), native_time_base="2/30720"), Use.SSL)


def test_split_policy_is_explicit_for_train_and_selection():
    ssl = frame(split=Split.SSL_TRAIN)
    validation = frame(split=Split.DEVELOPMENT_VALIDATION, group="match-2")
    validate_use(ssl, Use.SSL)
    validate_use(validation, Use.SELECT)
    with pytest.raises(ValueError, match="SSL_TRAIN"):
        validate_use(validation, Use.SSL)
    with pytest.raises(ValueError, match="development validation"):
        validate_use(ssl, Use.SELECT)
    with pytest.raises(ValueError, match="unavailable"):
        validate_use(validation, Use.PSEUDO_LABEL)


def test_learning_contract_never_emits_owned_or_formal_facts():
    assert QUALIFICATION == "development_only"
    assert OWNERSHIP == "UNKNOWN"
    assert FORMAL_OUTPUTS == 0
