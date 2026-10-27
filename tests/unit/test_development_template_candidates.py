import hashlib
from dataclasses import replace

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
from valorant_ai_coach.visual.development_marker_attribution import freeze_native_sample
from valorant_ai_coach.visual.development_template_candidates import (
    NativeTemplateBank,
    template_candidate_pool,
)


def inputs(split=Split.DEVELOPMENT_TRAIN):
    patch = np.random.default_rng(41).integers(0, 256, (25, 25, 3), np.uint8)
    frame = FrameRecord(
        "a" * 64,
        "a",
        "a",
        12,
        "1/60",
        "b" * 64,
        "c" * 64,
        (100, 100),
        (20.0, 20.0, 25.0, 25.0),
        "d" * 64,
        "e" * 64,
        "physical",
        split,
        SourceAcceptance(True, *["f" * 64] * 4),
    )
    label = FrameLabel(
        frame.frame_sha256, Label.PLAYER, LabelOrigin.HUMAN_CONFIRMED, frame.roi_xywh
    )
    return patch, frame, label


def bank_for(patch, frame, labels=None):
    return NativeTemplateBank(
        [patch], [frame], patch_sha256=[hashlib.sha256(patch.tobytes()).hexdigest()], labels=labels
    )


def test_exact_native_train_retrieval_and_scales():
    patch, frame, label = inputs()
    bank = bank_for(patch, frame, [label])
    crop = np.zeros((100, 100, 3), np.uint8)
    crop[35:52, 42:59] = patch[4:21, 4:21]
    result = bank.search(crop)
    assert any(
        p["center_roi_px"] == [50.0, 43.0] and p["raw_score"] > 0.99 for p in result["observations"]
    )
    assert len(result["observations"]) <= 6
    assert result["semantic_class"] == result["ownership"] == "UNKNOWN"
    assert bank.search(crop) == result


@pytest.mark.parametrize("split", [Split.DEVELOPMENT_VALIDATION, Split.DEVELOPMENT_FROZEN_TEST])
@pytest.mark.parametrize("human", [True, False])
def test_no_evaluation_material_in_reference_banks(split, human):
    patch, frame, label = inputs(split)
    with pytest.raises(ValueError):
        bank_for(patch, frame, [label] if human else None)


def test_ssl_retrieval_never_acquires_positive_semantics():
    patch, frame, label = inputs(Split.SSL_TRAIN)
    bank = bank_for(patch, frame)
    assert bank.origin == "unlabeled_train_retrieval"
    with pytest.raises(ValueError):
        bank_for(patch, frame, [label])


def test_pseudo_labels_cannot_become_human_templates():
    patch, frame, label = inputs()
    with pytest.raises(ValueError):
        bank_for(patch, frame, [replace(label, origin=LabelOrigin.PSEUDO)])


def test_background_cannot_be_positive_template():
    patch, frame, label = inputs()
    with pytest.raises(ValueError):
        bank_for(patch, frame, [replace(label, label=Label.BACKGROUND)])


def test_input_copy_and_changed_reference_fingerprint_guard():
    patch, frame, label = inputs()
    bank = bank_for(patch, frame, [label])
    patch[:] = 0
    assert bank._templates[0].any()
    bank._templates[0].setflags(write=True)
    bank._templates[0][:] = 0
    with pytest.raises(ValueError, match="changed"):
        bank.search(np.zeros((100, 100, 3), np.uint8))


def test_bad_patch_hash_and_budget():
    patch, frame, _ = inputs()
    with pytest.raises(ValueError):
        NativeTemplateBank([patch], [frame], patch_sha256=["0" * 64])
    with pytest.raises(ValueError):
        NativeTemplateBank([patch] * 25, [frame] * 25, patch_sha256=["0" * 64] * 25)


def test_spatially_constant_color_is_not_perfect_ncc_evidence():
    patch, frame, label = inputs()
    patch[:] = [255, 20, 10]
    bank = bank_for(patch, frame, [label])
    assert bank.search(np.zeros((100, 100, 3), np.uint8))["observations"] == []


@pytest.mark.parametrize("shape", [(64, 100, 3), (1025, 100, 3), (100, 100)])
def test_bounded_current_image(shape):
    patch, frame, label = inputs()
    with pytest.raises(ValueError):
        bank_for(patch, frame, [label]).search(np.zeros(shape, np.uint8))


def native_input():
    image = np.zeros((128, 160, 3), np.uint8)
    sample = freeze_native_sample(
        {
            "source_id": "synthetic",
            "source_sha256": "a" * 64,
            "acquisition_id": "a",
            "native_epoch": "a",
            "native_pts_tick": 12,
            "native_time_base": "1/60",
            "acquired_frame_sha256": "b" * 64,
            "native_pixel_sha256": hashlib.sha256(image.tobytes()).hexdigest(),
        },
        frame_size_px=(160, 128),
    )
    return image, sample


def test_template_pool_preserves_parent_and_explicit_overflow(monkeypatch):
    patch, frame, label = inputs()
    human = bank_for(patch, frame, [label])
    ssl = bank_for(
        patch,
        replace(
            frame,
            split=Split.SSL_TRAIN,
            leakage_group_id="other",
            source_sha256="0" * 64,
            frame_sha256="1" * 64,
            pixel_sha256="2" * 64,
        ),
    )

    def search(self, crop):
        return {
            "observations": [{"center_roi_px": [40.0, 40.0], "raw_score": 0.6}] * 144,
            "bank_fingerprint": self.fingerprint,
        }

    monkeypatch.setattr(NativeTemplateBank, "search", search)
    image, sample = native_input()
    parent = [
        {
            "center_frame_px": [50.0, 50.0],
            "ownership": "UNKNOWN",
            "geometry_only_map_position_norm": [0.1, 0.2],
        }
    ] * 128
    pool = template_candidate_pool(
        image,
        sample,
        roi_xywh=[0, 0, 120, 100],
        parent=parent,
        profile_fingerprint="c" * 64,
        human_bank=human,
        ssl_bank=ssl,
    )
    assert pool["candidates"][:128] == parent
    assert len(pool["candidates"]) == 320 and pool["retrieval_output_overflow"] == 96
    assert len(pool["retrieval_searches"][1]["observations"]) == 144
    assert pool["ownership"] == "UNKNOWN" and pool["formal_outputs"] == 0
    assert pool["physical_association"] == "UNKNOWN"


def test_bank_roles_cannot_be_swapped():
    patch, frame, _ = inputs()
    unlabeled = bank_for(patch, replace(frame, split=Split.SSL_TRAIN))
    image, sample = native_input()
    with pytest.raises(ValueError, match="Human train bank"):
        template_candidate_pool(
            image,
            sample,
            roi_xywh=[0, 0, 120, 100],
            parent=[],
            profile_fingerprint="c" * 64,
            human_bank=unlabeled,
        )


def test_physical_split_conflict_between_two_banks_is_rejected():
    patch, frame, label = inputs()
    human = bank_for(patch, frame, [label])
    ssl = bank_for(patch, replace(frame, split=Split.SSL_TRAIN))
    image, sample = native_input()
    with pytest.raises(ValueError, match="split"):
        template_candidate_pool(
            image,
            sample,
            roi_xywh=[0, 0, 120, 100],
            parent=[],
            profile_fingerprint="c" * 64,
            human_bank=human,
            ssl_bank=ssl,
        )


def test_reference_change_during_search_is_rejected(monkeypatch):
    import cv2

    patch, frame, label = inputs()
    bank = bank_for(patch, frame, [label])
    original = cv2.matchTemplate

    def changed(*args, **kwargs):
        bank._templates[0].setflags(write=True)
        bank._templates[0][0, 0] ^= 255
        return original(*args, **kwargs)

    monkeypatch.setattr(cv2, "matchTemplate", changed)
    with pytest.raises(ValueError, match="changed"):
        bank.search(np.zeros((100, 100, 3), np.uint8))
