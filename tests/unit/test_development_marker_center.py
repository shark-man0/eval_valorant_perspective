from dataclasses import replace

import cv2
import numpy as np
import pytest

from valorant_ai_coach.visual.development_learning_dataset import (
    FrameLabel,
    FrameRecord,
    Label,
    LabelOrigin,
    SourceAcceptance,
    Split,
)
from valorant_ai_coach.visual.development_marker_center import (
    CENTER_FEATURE_FINGERPRINT,
    center_features,
    center_rule,
    fit_center_readout,
)


def training():
    frames = [
        FrameRecord(
            source_sha256="a" * 64,
            acquisition_id="epoch",
            native_epoch="epoch",
            native_pts_tick=i,
            native_time_base="1/60",
            frame_sha256=str(i + 1) * 64,
            pixel_sha256=str(i + 5) * 64,
            frame_size_px=(64, 64),
            roi_xywh=(0.0, 0.0, 25.0, 25.0),
            extraction_fingerprint="b" * 64,
            exposure_fingerprint="c" * 64,
            leakage_group_id="match",
            split=Split.DEVELOPMENT_TRAIN,
            source_acceptance=SourceAcceptance(True, "d" * 64, "e" * 64, "d" * 64, "e" * 64),
        )
        for i in range(4)
    ]
    labels = [
        FrameLabel(f.frame_sha256, Label(name), LabelOrigin.HUMAN_CONFIRMED, f.roi_xywh)
        for f, name in zip(frames, ["PLAYER", "DEATH_MARKER", "UI", "BACKGROUND"], strict=True)
    ]
    return frames, labels


def test_center_support_distinguishes_a_displaced_circle_and_blank_is_finite():
    patches = [np.zeros((25, 25, 3), np.uint8) for _ in range(3)]
    cv2.circle(patches[0], (12, 12), 7, (255, 255, 255), 1)
    cv2.circle(patches[1], (16, 12), 7, (255, 255, 255), 1)
    f = center_features(patches)
    assert f.shape == (3, 41) and np.isfinite(f).all()
    assert center_rule(f)[0] > center_rule(f)[1]
    assert center_rule(f)[2] == 0


def test_native_patch_geometry_is_required():
    with pytest.raises(ValueError, match="25px"):
        center_features([np.zeros((27, 27, 3), np.uint8)])


def test_readout_retains_fingerprint_and_does_not_mutate_training_inputs():
    frames, labels = training()
    f = np.eye(4)
    model, receipt = fit_center_readout(
        f, frames, labels, feature_fingerprint=CENTER_FEATURE_FINGERPRINT
    )
    assert receipt["unique_human_references"] == 4
    assert receipt["ownership"] == "UNKNOWN" and receipt["formal_outputs"] == 0
    assert model.scores(f, feature_fingerprint=CENTER_FEATURE_FINGERPRINT).argmax(
        1
    ).tolist() == list(range(4))
    f[:] = 0
    assert model.mean.tolist() == [0.25] * 4
    with pytest.raises(ValueError, match="Matching finite"):
        model.scores(np.eye(4), feature_fingerprint="f" * 64)


@pytest.mark.parametrize(
    "split", [Split.DEVELOPMENT_VALIDATION, Split.DEVELOPMENT_FROZEN_TEST, Split.SSL_TRAIN]
)
def test_semantic_fit_cannot_use_non_train_data(split):
    frames, labels = training()
    with pytest.raises(ValueError):
        fit_center_readout(
            np.eye(4),
            [replace(f, split=split) for f in frames],
            labels,
            feature_fingerprint=CENTER_FEATURE_FINGERPRINT,
        )


@pytest.mark.parametrize(
    "origin,label", [(LabelOrigin.PSEUDO, Label.PLAYER), (LabelOrigin.UNLABELED, Label.UNKNOWN)]
)
def test_pseudo_and_unknown_are_not_human_negative_examples(origin, label):
    frames, labels = training()
    labels[0] = replace(labels[0], origin=origin, label=label)
    with pytest.raises(ValueError):
        fit_center_readout(
            np.eye(4), frames, labels, feature_fingerprint=CENTER_FEATURE_FINGERPRINT
        )


def test_weak_offsets_reference_one_human_label_and_never_become_background():
    frames, labels = training()
    _, receipt = fit_center_readout(
        np.array([[1.0], [0.0], [0.0]]),
        [frames[0]] * 3,
        [labels[0]] * 3,
        offsets_px=[(0, 0), (-4, 0), (4, 0)],
        feature_fingerprint=CENTER_FEATURE_FINGERPRINT,
    )
    assert receipt["examples"] == 3 and receipt["unique_human_references"] == 1
    assert receipt["shifted_is_background"] is False
    assert receipt["true_center_GT"] is False


def test_missing_class_support_cannot_emit_an_untrained_semantic_class():
    frames, labels = training()
    with pytest.raises(ValueError, match="every semantic class"):
        fit_center_readout(
            np.eye(3), frames[:3], labels[:3], feature_fingerprint=CENTER_FEATURE_FINGERPRINT
        )
