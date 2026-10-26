import hashlib
import io
import json
import zipfile
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
from valorant_ai_coach.visual.development_marker_learning import (
    cluster_features,
    fit_centroids,
    load_centroids,
    save_centroids,
)


def sha(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def acceptance() -> SourceAcceptance:
    manifest, allocation = sha("manifest"), sha("allocation")
    return SourceAcceptance(True, manifest, allocation, manifest, allocation)


def one_frame(*, split: Split = Split.DEVELOPMENT_TRAIN, index: int = 0) -> FrameRecord:
    return FrameRecord(
        source_sha256=sha(f"source-{index}"), acquisition_id=f"acq-{index}",
        native_epoch=f"epoch-{index}", native_pts_tick=index, native_time_base="1/60",
        frame_sha256=sha(f"frame-{index}"), pixel_sha256=sha(f"pixels-{index}"),
        frame_size_px=(640, 480), roi_xywh=(20.0, 20.0, 32.0, 32.0),
        extraction_fingerprint=sha("extractor"), exposure_fingerprint=sha("exposure"),
        leakage_group_id=f"physical-{index}", split=split, source_acceptance=acceptance(),
    )


def two_roi_training_data(*, split: Split = Split.DEVELOPMENT_TRAIN):
    common = one_frame(split=split)
    player = common
    death = replace(common, roi_xywh=(80.0, 20.0, 32.0, 32.0))
    labels = [
        FrameLabel(common.frame_sha256, Label.PLAYER, LabelOrigin.HUMAN_CONFIRMED,
                   roi_xywh=player.roi_xywh),
        FrameLabel(death.frame_sha256, Label.DEATH_MARKER, LabelOrigin.HUMAN_CONFIRMED,
                   roi_xywh=death.roi_xywh),
    ]
    features = np.array([[1.0, 0.0], [0.0, 1.0]], dtype=np.float32)
    return features, [player, death], labels


def fitted_model():
    features, frames, labels = two_roi_training_data()
    model, receipt = fit_centroids(
        features, frames, labels, feature_fingerprint=sha("feature-method"),
        maximum_distance=0.5, minimum_margin=0.1,
    )
    return features, model, receipt


def test_non_axis_aligned_prototypes_roundtrip_without_second_normalization(tmp_path):
    _, frames, labels = two_roi_training_data()
    features = np.random.default_rng(270027).normal(size=(2, 96)).astype(np.float32)
    model, _ = fit_centroids(features, frames, labels,
                            feature_fingerprint=sha("real-dimensional-features"),
                            maximum_distance=.35, minimum_margin=.02)
    path = tmp_path / "classifier.npz"
    expected = save_centroids(model, path)
    loaded = load_centroids(path, expected)
    np.testing.assert_array_equal(model.centers, loaded.centers)
    assert loaded.fingerprint == model.fingerprint


def test_fit_centroids_accepts_human_train_labels_for_multiple_rois_on_one_native_frame():
    features, frames, labels = two_roi_training_data()
    model, receipt = fit_centroids(
        features, frames, labels, feature_fingerprint=sha("feature-method"),
        maximum_distance=0.5, minimum_margin=0.1,
    )

    assert model.labels == ("DEATH_MARKER", "PLAYER")
    assert receipt["training_patches"] == 2
    assert receipt["labels"] == {"DEATH_MARKER": 1, "PLAYER": 1}
    assert receipt["ownership"] == "UNKNOWN"
    assert receipt["qualification"] == "development_only"
    assert receipt["formal_outputs"] == 0


@pytest.mark.parametrize("split", [
    Split.SSL_TRAIN,
    Split.DEVELOPMENT_VALIDATION,
    Split.DEVELOPMENT_FROZEN_TEST,
])
def test_fit_centroids_rejects_non_development_train_splits(split):
    features, frames, labels = two_roi_training_data(split=split)
    message = ("frozen test" if split is Split.DEVELOPMENT_FROZEN_TEST
               else "supervised training requires development train")
    with pytest.raises(ValueError, match=message):
        fit_centroids(features, frames, labels, feature_fingerprint=sha("feature-method"),
                      maximum_distance=0.5, minimum_margin=0.1)


def test_fit_centroids_rejects_pseudo_and_unknown_labels():
    features, frames, labels = two_roi_training_data()
    pseudo = [labels[0], FrameLabel(
        labels[1].frame_sha256, Label.DEATH_MARKER, LabelOrigin.PSEUDO,
        roi_xywh=labels[1].roi_xywh,
    )]
    with pytest.raises(ValueError, match="human-confirmed"):
        fit_centroids(features, frames, pseudo, feature_fingerprint=sha("feature-method"),
                      maximum_distance=0.5, minimum_margin=0.1)

    unknown = [labels[0], FrameLabel(
        labels[1].frame_sha256, Label.UNKNOWN, LabelOrigin.HUMAN_CONFIRMED,
        roi_xywh=labels[1].roi_xywh,
    )]
    with pytest.raises(ValueError, match="non-UNKNOWN"):
        fit_centroids(features, frames, unknown, feature_fingerprint=sha("feature-method"),
                      maximum_distance=0.5, minimum_margin=0.1)


def test_fit_centroids_rejects_unregistered_and_mistargeted_label_rois():
    features, frames, labels = two_roi_training_data()
    unregistered = [labels[0], FrameLabel(
        labels[1].frame_sha256, Label.DEATH_MARKER, LabelOrigin.HUMAN_CONFIRMED,
        roi_xywh=(300.0, 20.0, 32.0, 32.0),
    )]
    with pytest.raises(ValueError, match="included frame ROI"):
        fit_centroids(features, frames, unregistered, feature_fingerprint=sha("feature-method"),
                      maximum_distance=0.5, minimum_margin=0.1)

    # Every label ROI exists for the native frame, but it must still match its paired row.
    swapped = [labels[1], labels[0]]
    with pytest.raises(ValueError, match="ROI/frame ROI"):
        fit_centroids(features, frames, swapped, feature_fingerprint=sha("feature-method"),
                      maximum_distance=0.5, minimum_margin=0.1)


def test_centroid_snapshot_save_load_preserves_fingerprint_and_predictions(tmp_path):
    feature_rows, model, _ = fitted_model()
    path = tmp_path / "centroids.npz"
    file_sha = save_centroids(model, path)
    loaded = load_centroids(path, file_sha)

    expected = model.classify(feature_rows, feature_fingerprint=model.feature_fingerprint)
    actual = loaded.classify(feature_rows, feature_fingerprint=loaded.feature_fingerprint)
    assert loaded.fingerprint == model.fingerprint
    assert actual == expected


def test_centroid_snapshot_rejects_byte_mutation_and_overwrite(tmp_path):
    _, model, _ = fitted_model()
    path = tmp_path / "centroids.npz"
    original_sha = save_centroids(model, path)
    with pytest.raises(FileExistsError):
        save_centroids(model, path)

    content = bytearray(path.read_bytes())
    content[-1] ^= 1
    path.write_bytes(content)
    with pytest.raises(ValueError, match="Classifier bytes changed"):
        load_centroids(path, original_sha)


def snapshot_members(model):
    buffer = io.BytesIO()
    np.savez_compressed(
        buffer,
        centers=model.centers,
        metadata=np.frombuffer(json.dumps({
            "version": 1,
            "labels": list(model.labels),
            "feature_fingerprint": model.feature_fingerprint,
            "maximum_distance": model.maximum_distance,
            "minimum_margin": model.minimum_margin,
            "classifier_fingerprint": model.fingerprint,
        }, sort_keys=True).encode(), dtype=np.uint8),
    )
    return buffer.getvalue()


def test_centroid_snapshot_rejects_metadata_fingerprint_tampering(tmp_path):
    _, model, _ = fitted_model()
    buffer = io.BytesIO()
    with np.load(io.BytesIO(snapshot_members(model)), allow_pickle=False) as archive:
        metadata = json.loads(archive["metadata"].tobytes())
        centers = archive["centers"].copy()
    metadata["classifier_fingerprint"] = "f" * 64
    changed_metadata = np.frombuffer(json.dumps(metadata, sort_keys=True).encode(), dtype=np.uint8)
    np.savez_compressed(buffer, centers=centers, metadata=changed_metadata)
    path = tmp_path / "tampered.npz"
    path.write_bytes(buffer.getvalue())

    with pytest.raises(ValueError, match="Classifier fingerprint mismatch"):
        load_centroids(path, hashlib.sha256(path.read_bytes()).hexdigest())


def test_centroid_snapshot_rejects_oversized_zip_expansion_before_numpy_load(tmp_path):
    metadata = np.frombuffer(b"{}", dtype=np.uint8)
    metadata_buffer = io.BytesIO()
    np.save(metadata_buffer, metadata)
    path = tmp_path / "expanded.npz"
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("centers.npy", b"0" * (2 * 1024**2 + 1))
        archive.writestr("metadata.npy", metadata_buffer.getvalue())
    assert path.stat().st_size < 2 * 1024**2

    with pytest.raises(ValueError, match="Bounded tensor-only"):
        load_centroids(path, hashlib.sha256(path.read_bytes()).hexdigest())


def test_centroid_snapshot_rejects_object_array_without_pickle(tmp_path):
    _, model, _ = fitted_model()
    path = tmp_path / "object-array.npz"
    np.savez_compressed(
        path,
        centers=np.array([[{"unsafe": True}]], dtype=object),
        metadata=np.frombuffer(json.dumps({
            "version": 1,
            "labels": list(model.labels),
            "feature_fingerprint": model.feature_fingerprint,
            "maximum_distance": model.maximum_distance,
            "minimum_margin": model.minimum_margin,
            "classifier_fingerprint": model.fingerprint,
        }, sort_keys=True).encode(), dtype=np.uint8),
    )

    with pytest.raises(ValueError, match="Object arrays cannot be loaded"):
        load_centroids(path, hashlib.sha256(path.read_bytes()).hexdigest())


def test_cluster_features_is_deterministic_train_only_and_semantics_remain_unknown():
    features = np.array([
        [1.0, 0.0], [0.99, 0.1], [0.0, 1.0], [0.1, 0.99],
    ], dtype=np.float32)
    frames = [one_frame(index=index) for index in range(len(features))]
    first = cluster_features(features, frames, clusters=2, seed=7)
    second = cluster_features(features, frames, clusters=2, seed=7)

    assert first == second
    assert len(first["assignments"]) == len(features)
    assert first["cluster_semantics"] == ["UNKNOWN", "UNKNOWN"]
    assert first["ownership"] == "UNKNOWN"
    assert first["qualification"] == "development_only"
    assert first["formal_outputs"] == 0


@pytest.mark.parametrize("split", [Split.DEVELOPMENT_VALIDATION, Split.DEVELOPMENT_FROZEN_TEST])
def test_cluster_features_rejects_validation_and_frozen_inputs(split):
    features = np.array([[1.0, 0.0], [0.0, 1.0]], dtype=np.float32)
    frames = [one_frame(split=split, index=index) for index in range(2)]
    with pytest.raises(ValueError, match="Clustering fit cannot consume"):
        cluster_features(features, frames, clusters=2)


def test_cluster_features_rejects_physical_group_split_leakage():
    features = np.array([[1.0, 0.0], [0.0, 1.0]], dtype=np.float32)
    train = one_frame(index=0)
    validation = one_frame(split=Split.DEVELOPMENT_VALIDATION, index=1)
    validation = replace(validation, leakage_group_id=train.leakage_group_id)
    with pytest.raises(ValueError, match="crosses splits"):
        cluster_features(features, [train, validation], clusters=2)
