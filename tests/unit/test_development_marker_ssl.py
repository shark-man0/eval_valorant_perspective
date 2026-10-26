import hashlib
from dataclasses import replace

import numpy as np
import pytest

import valorant_ai_coach.visual.development_marker_ssl as ssl
from valorant_ai_coach.visual.development_learning_dataset import (
    FrameRecord,
    SourceAcceptance,
    Split,
)


def digest(char: str) -> str:
    return char * 64


def accepted() -> SourceAcceptance:
    return SourceAcceptance(True, digest("a"), digest("b"), digest("a"), digest("b"))


def training_inputs(count: int = 16, split: Split = Split.SSL_TRAIN):
    patches = [np.full((8, 8, 3), index, dtype=np.uint8) for index in range(count)]
    hashes = [hashlib.sha256(patch.tobytes()).hexdigest() for patch in patches]
    frames = [FrameRecord(
        source_sha256=digest("c"), acquisition_id="acq-1", native_epoch="epoch-1",
        native_pts_tick=index, native_time_base="1/60",
        frame_sha256=digest(f"{index:064x}"[-1]), pixel_sha256=digest(f"{index + 1:064x}"[-1]),
        frame_size_px=(640, 480), roi_xywh=(10.0, 10.0, 8.0, 8.0),
        extraction_fingerprint=digest("d"), exposure_fingerprint=digest("e"),
        leakage_group_id="physical-match-1", split=split, source_acceptance=accepted(),
    ) for index in range(count)]
    return patches, frames, hashes


def forbid_torch_import(monkeypatch):
    calls = []
    monkeypatch.setattr(ssl.importlib, "import_module", lambda name: calls.append(name))
    return calls


def test_masked_training_budget_accepts_inclusive_boundaries():
    ssl.MaskedTrainingBudget(seed=0, maximum_images=16, epochs=1, steps=1,
                             seconds=1, batch_size=1).validate()
    ssl.MaskedTrainingBudget(seed=2**31-1, maximum_images=4096, epochs=20,
                             steps=1000, seconds=1200, batch_size=128).validate()


@pytest.mark.parametrize("change", [
    {"seed": -1}, {"seed": 2**31}, {"seed": True},
    {"maximum_images": 15}, {"maximum_images": 4097},
    {"epochs": 0}, {"epochs": 21}, {"steps": 0}, {"steps": 1001},
    {"seconds": 0}, {"seconds": 1201}, {"batch_size": 0}, {"batch_size": 129},
])
def test_masked_training_budget_rejects_out_of_bounds_values(change):
    with pytest.raises(ValueError, match="training budget"):
        replace(ssl.MaskedTrainingBudget(), **change).validate()


@pytest.mark.parametrize("split", [
    Split.DEVELOPMENT_TRAIN,
    Split.DEVELOPMENT_VALIDATION,
    Split.DEVELOPMENT_FROZEN_TEST,
])
def test_training_rejects_non_ssl_splits_before_torch_import(split, tmp_path, monkeypatch):
    patches, frames, hashes = training_inputs(split=split)
    calls = forbid_torch_import(monkeypatch)

    message = "frozen test" if split is Split.DEVELOPMENT_FROZEN_TEST else "SSL_TRAIN"
    with pytest.raises(ValueError, match=message):
        ssl.train_masked_encoder(
            patches, frames, hashes, budget=ssl.MaskedTrainingBudget(),
            output=tmp_path / "model.pth",
        )
    assert calls == []


def test_training_has_no_semantic_label_input_and_never_imports_torch_for_dev_train(
        tmp_path, monkeypatch):
    patches, frames, hashes = training_inputs(split=Split.DEVELOPMENT_TRAIN)
    calls = forbid_torch_import(monkeypatch)

    with pytest.raises(ValueError, match="SSL_TRAIN"):
        ssl.train_masked_encoder(
            patches, frames, hashes, budget=ssl.MaskedTrainingBudget(),
            output=tmp_path / "model.pth",
        )
    assert calls == []


def test_training_rejects_patch_hash_mutation_before_torch_import(tmp_path, monkeypatch):
    patches, frames, hashes = training_inputs()
    hashes[0] = digest("f")
    calls = forbid_torch_import(monkeypatch)

    with pytest.raises(ValueError, match="patch changed"):
        ssl.train_masked_encoder(
            patches, frames, hashes, budget=ssl.MaskedTrainingBudget(),
            output=tmp_path / "model.pth",
        )
    assert calls == []


@pytest.mark.parametrize("fault", [
    "too_few_patches", "frame_count", "hash_count", "existing_output", "over_budget",
    "invalid_budget",
])
def test_training_rejects_shape_output_and_budget_mismatches_before_torch_import(
        fault, tmp_path, monkeypatch):
    patches, frames, hashes = training_inputs()
    output = tmp_path / "model.pth"
    budget = ssl.MaskedTrainingBudget()
    if fault == "too_few_patches":
        patches, frames, hashes = patches[:-1], frames[:-1], hashes[:-1]
    elif fault == "frame_count":
        frames = frames[:-1]
    elif fault == "hash_count":
        hashes = hashes[:-1]
    elif fault == "existing_output":
        output.write_bytes(b"already exists")
    elif fault == "over_budget":
        patches, frames, hashes = training_inputs(count=17)
        budget = replace(budget, maximum_images=16)
    else:
        budget = replace(budget, epochs=21)
    calls = forbid_torch_import(monkeypatch)

    with pytest.raises(ValueError):
        ssl.train_masked_encoder(patches, frames, hashes, budget=budget, output=output)
    assert calls == []


def test_training_rejects_invalid_patch_before_torch_import(tmp_path, monkeypatch):
    patches, frames, hashes = training_inputs()
    patches[0] = np.zeros((4, 8, 3), dtype=np.uint8)
    hashes[0] = hashlib.sha256(patches[0].tobytes()).hexdigest()
    calls = forbid_torch_import(monkeypatch)

    with pytest.raises(ValueError, match="native uint8 BGR patches"):
        ssl.train_masked_encoder(
            patches, frames, hashes, budget=ssl.MaskedTrainingBudget(),
            output=tmp_path / "model.pth",
        )
    assert calls == []


def test_encoder_rejects_missing_path_or_invalid_hash_before_torch_import(tmp_path, monkeypatch):
    calls = forbid_torch_import(monkeypatch)
    with pytest.raises(ValueError, match="snapshot and SHA"):
        ssl.MaskedEncoderFeatures(tmp_path / "missing.pth", digest("a"))
    path = tmp_path / "model.pth"
    path.write_bytes(b"small local file")
    with pytest.raises(ValueError, match="snapshot and SHA"):
        ssl.MaskedEncoderFeatures(path, "short")
    assert calls == []


def test_encoder_rejects_changed_model_hash_before_torch_import(tmp_path, monkeypatch):
    path = tmp_path / "model.pth"
    path.write_bytes(b"weights with an untrusted digest")
    calls = forbid_torch_import(monkeypatch)

    with pytest.raises(ValueError, match="encoder changed"):
        ssl.MaskedEncoderFeatures(path, digest("0"))
    assert calls == []


def test_encoder_rejects_oversized_model_before_torch_import(tmp_path, monkeypatch):
    path = tmp_path / "oversized.pth"
    path.write_bytes(b"x" * (1024**2 + 1))
    calls = forbid_torch_import(monkeypatch)

    with pytest.raises(ValueError, match="snapshot and SHA"):
        ssl.MaskedEncoderFeatures(path, hashlib.sha256(path.read_bytes()).hexdigest())
    assert calls == []
