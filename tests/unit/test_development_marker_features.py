import copy
import hashlib
from contextlib import nullcontext
from types import SimpleNamespace

import numpy as np
import pytest

import valorant_ai_coach.visual.development_marker_features as features
from valorant_ai_coach.visual.development_marker_attribution import freeze_native_sample


def native_frame() -> tuple[np.ndarray, dict[str, object]]:
    frame = np.arange(64 * 64 * 3, dtype=np.uint8).reshape(64, 64, 3)
    sample = freeze_native_sample({
        "source_id": "synthetic-recording",
        "source_sha256": "1" * 64,
        "acquisition_id": "epoch-1",
        "native_epoch": "epoch-1",
        "native_pts_tick": 123,
        "native_time_base": "1/60",
        "acquired_frame_sha256": "2" * 64,
        "native_pixel_sha256": hashlib.sha256(frame.tobytes()).hexdigest(),
    }, frame_size_px=(64, 64))
    return frame, sample


def test_native_bound_patches_are_exact_copies_and_deterministic():
    frame, sample = native_frame()
    before = frame.copy()
    patches, fingerprint = features.bound_patches(frame, sample, [[32, 31], [40.0, 42.0]], radius=3)
    again, second_fingerprint = features.bound_patches(
        frame, sample, [[32, 31], [40.0, 42.0]], radius=3)

    assert len(patches) == 2
    assert all(patch.shape == (7, 7, 3) and patch.dtype == np.uint8 for patch in patches)
    assert np.array_equal(patches[0], before[28:35, 29:36])
    assert fingerprint == second_fingerprint
    assert all(np.array_equal(left, right) for left, right in zip(patches, again, strict=True))
    assert np.array_equal(frame, before)
    patches[0][:] = 0
    assert np.array_equal(frame, before)


@pytest.mark.parametrize("center", [[2, 30], [62, 30], [30, 2], [30, 62]])
def test_clipped_native_patch_is_rejected(center):
    frame, sample = native_frame()
    with pytest.raises(ValueError, match="clips"):
        features.bound_patches(frame, sample, [center], radius=3)


@pytest.mark.parametrize("centers", [[], [[float("nan"), 10]], [[1, 2, 3]], [(10, 10)]])
def test_invalid_candidate_centers_are_rejected(centers):
    frame, sample = native_frame()
    with pytest.raises(ValueError):
        features.bound_patches(frame, sample, centers)


def test_bad_radius_and_frame_are_rejected():
    frame, sample = native_frame()
    with pytest.raises(ValueError, match="radius"):
        features.bound_patches(frame, sample, [[32, 32]], radius=True)
    with pytest.raises(ValueError, match="Native frame"):
        features.bound_patches(frame.astype(np.float32), sample, [[32, 32]])


@pytest.mark.parametrize("field,value", [
    ("native_pts_tick", 124), ("source_sha256", "3" * 64),
    ("acquired_frame_sha256", "4" * 64), ("native_epoch", "epoch-2"),
])
def test_sample_identity_mutation_is_rejected(field, value):
    frame, sample = native_frame()
    changed = dict(sample)
    changed[field] = value
    with pytest.raises(ValueError, match="identity"):
        features.bound_patches(frame, changed, [[32, 32]])


def test_frame_pixel_mutation_is_rejected():
    frame, sample = native_frame()
    frame[0, 0, 0] ^= 1
    with pytest.raises(ValueError, match="identity"):
        features.bound_patches(frame, sample, [[32, 32]])


def test_handcrafted_features_have_fixed_finite_size_and_do_not_mutate_inputs():
    frame, sample = native_frame()
    patches, _ = features.bound_patches(frame, sample, [[32, 32], [44, 44]], radius=4)
    before = [patch.copy() for patch in patches]
    first = features.handcrafted_features(patches)
    second = features.handcrafted_features(patches)

    assert first.shape == (2, 200)
    assert first.dtype == np.float32
    assert np.isfinite(first).all()
    assert np.array_equal(first, second)
    assert all(np.array_equal(patch, saved) for patch, saved in zip(patches, before, strict=True))


@pytest.mark.parametrize("patches", [
    [], [np.zeros((4, 5, 3), dtype=np.uint8)],
    [np.zeros((130, 5, 3), dtype=np.uint8)],
    [np.zeros((5, 5), dtype=np.uint8)],
    [np.zeros((5, 5, 4), dtype=np.uint8)],
    [np.zeros((5, 5, 3), dtype=np.float32)],
])
def test_handcrafted_feature_extractor_rejects_unbounded_or_non_native_patches(patches):
    with pytest.raises(ValueError):
        features.handcrafted_features(patches)


def make_classifier(*, centers=None, labels=None, maximum_distance=0.5, minimum_margin=0.1):
    if centers is None:
        centers = np.array([[1.0, 0.0], [0.0, 1.0]], dtype=np.float32)
    if labels is None:
        labels = ["PLAYER", "DEATH_MARKER"]
    return features.AppearanceCentroids(
        centers, labels, "a" * 64,
        maximum_distance=maximum_distance, minimum_margin=minimum_margin,
    )


def test_centroids_return_development_candidates_and_keep_safety_outputs_fixed():
    classifier = make_classifier()
    result = classifier.classify(
        np.array([[1.0, 0.0], [0.0, 1.0]], dtype=np.float32),
        feature_fingerprint="a" * 64,
    )

    assert [row["appearance_class_candidate"] for row in result] == ["PLAYER", "DEATH_MARKER"]
    assert [row["cosine_distance"] for row in result] == pytest.approx([0.0, 0.0])
    assert all(row["scores_are_probabilities"] is False for row in result)
    assert all(row["qualification"] == "development_only" for row in result)
    assert all(row["ownership"] == "UNKNOWN" for row in result)
    assert all(row["map_position"] is None and row["formal_fact"] is None for row in result)
    assert all(row["formal_events"] == [] for row in result)


def test_centroid_distance_and_margin_reject_to_unknown():
    far = make_classifier(maximum_distance=0.2)
    assert far.classify(np.array([[-1.0, 0.0]], dtype=np.float32),
                        feature_fingerprint="a" * 64)[0]["appearance_class_candidate"] == "UNKNOWN"

    tied = make_classifier(maximum_distance=2.0, minimum_margin=0.1)
    tie_result = tied.classify(np.array([[1.0, 1.0]], dtype=np.float32),
                               feature_fingerprint="a" * 64)[0]
    assert tie_result["margin"] == pytest.approx(0.0)
    assert tie_result["appearance_class_candidate"] == "UNKNOWN"

    zero = tied.classify(np.zeros((1, 2), dtype=np.float32),
                         feature_fingerprint="a" * 64)[0]
    assert zero["appearance_class_candidate"] == "UNKNOWN"


def test_centroid_feature_fingerprint_mismatch_is_rejected():
    classifier = make_classifier()
    with pytest.raises(ValueError, match="Matching finite"):
        classifier.classify(np.array([[1.0, 0.0]], dtype=np.float32),
                             feature_fingerprint="b" * 64)


@pytest.mark.parametrize("features_matrix", [
    np.array([[float("nan"), 0.0]], dtype=np.float32),
    np.array([[float("inf"), 0.0]], dtype=np.float32),
    np.ones((1, 3), dtype=np.float32),
])
def test_centroid_classifier_rejects_nonfinite_or_wrong_sized_features(features_matrix):
    with pytest.raises(ValueError, match="Matching finite"):
        make_classifier().classify(features_matrix, feature_fingerprint="a" * 64)


@pytest.mark.parametrize("kwargs", [
    {"centers": np.array([[0.0, 0.0]])},
    {"centers": np.array([[float("nan"), 1.0]])},
    {"labels": ["UNRECOGNIZED", "PLAYER"]},
    {"labels": ["PLAYER", "PLAYER"]},
    {"maximum_distance": 0.0},
    {"minimum_margin": 2.1},
])
def test_centroid_classifier_rejects_invalid_model_contract(kwargs):
    with pytest.raises(ValueError, match="Bounded appearance classifier"):
        make_classifier(**kwargs)


def test_centroid_model_copies_and_freezes_prototypes():
    centers = np.array([[2.0, 0.0], [0.0, 4.0]], dtype=np.float32)
    classifier = make_classifier(centers=centers)
    expected = classifier.classify(np.array([[1.0, 0.0]], dtype=np.float32),
                                   feature_fingerprint="a" * 64)
    centers[:] = 0
    assert classifier.classify(np.array([[1.0, 0.0]], dtype=np.float32),
                               feature_fingerprint="a" * 64) == expected
    with pytest.raises(ValueError):
        classifier.centers[0, 0] = 0


def test_mobile_net_rejects_invalid_view_before_optional_import(tmp_path, monkeypatch):
    imported = []
    monkeypatch.setattr(features.importlib, "import_module",
                        lambda name: imported.append(name))
    with pytest.raises(ValueError, match="supported feature view"):
        features.FrozenMobileNetFeatures(tmp_path / "missing.pth", "0" * 64, view="other")
    assert imported == []


def test_mobile_net_rejects_untrusted_local_bytes_before_optional_import(tmp_path, monkeypatch):
    path = tmp_path / "weights.pth"
    path.write_bytes(b"synthetic local weights")
    imported = []
    monkeypatch.setattr(features.importlib, "import_module",
                        lambda name: imported.append(name))
    with pytest.raises(ValueError, match="Feature model bytes changed"):
        features.FrozenMobileNetFeatures(path, "0" * 64)
    assert imported == []


def test_mobile_net_rejects_file_changed_after_binding_before_inference(tmp_path, monkeypatch):
    path = tmp_path / "weights.pth"
    content = b"synthetic local weights"
    path.write_bytes(content)

    class FakeFeatures:
        def __getitem__(self, key):
            return self

        def eval(self):
            return self

        def requires_grad_(self, value):
            return self

    class FakeModel:
        features = FakeFeatures()

        def load_state_dict(self, state, strict):
            return None

        def eval(self):
            return self

        def requires_grad_(self, value):
            return self

    fake_torch = SimpleNamespace(
        __version__="test",
        load=lambda stream, map_location, weights_only: {},
        inference_mode=nullcontext,
    )
    fake_models = SimpleNamespace(mobilenet_v3_small=lambda weights: FakeModel())
    imported = []

    def import_module(name):
        imported.append(name)
        return {"torch": fake_torch, "torchvision.models": fake_models,
                "torchvision": SimpleNamespace(__version__="test")}[name]

    monkeypatch.setattr(features.importlib, "import_module", import_module)
    model = features.FrozenMobileNetFeatures(path, hashlib.sha256(content).hexdigest())
    path.write_bytes(b"changed local weights")
    assert imported == ["torch", "torchvision.models", "torchvision"]
    with pytest.raises(ValueError, match="Feature model bytes changed"):
        model.extract([np.zeros((7, 7, 3), dtype=np.uint8)])


class SyntheticExtractor:
    def __init__(self):
        self.fingerprint = hashlib.sha256(b"synthetic-feature-profile").hexdigest()
        self.calls = 0

    def extract(self, patches):
        self.calls += 1
        return np.tile(np.array([[1.0, 0.0]], dtype=np.float32), (len(patches), 1))


def review_classifier(fingerprint):
    return features.AppearanceCentroids(
        np.array([[1.0, 0.0], [0.0, 1.0]], dtype=np.float32),
        ["PLAYER", "UI"], fingerprint,
        maximum_distance=0.5, minimum_margin=0.1,
    )


def development_proposals():
    return {
        "qualification": "development_only", "ownership": "UNKNOWN",
        "formal_self_position_fact": None, "selected_self_position": None,
        "development_events": [], "track_segments": [],
        "proposals": [{
            "ownership": "UNKNOWN", "center_frame_px": [32.0, 32.0],
            "center_roi_px": [12.0, 12.0], "map_position_norm": None,
            "zone_resolution": None, "geometry_only_map_position_norm": [0.3, 0.4],
        }],
    }


def test_feature_review_attaches_class_without_changing_native_geometry():
    frame, sample = native_frame()
    proposals = development_proposals()
    original = copy.deepcopy(proposals)
    extractor = SyntheticExtractor()
    result = features.review_proposals(
        frame, sample, proposals, extractor=extractor,
        classifier=review_classifier(extractor.fingerprint),
    )

    reviewed = result["proposals"][0]
    assert proposals == original
    for key in ("center_frame_px", "center_roi_px", "map_position_norm",
                "geometry_only_map_position_norm"):
        assert reviewed[key] == original["proposals"][0][key]
    assert reviewed["appearance_class_review"]["appearance_class_candidate"] == "PLAYER"
    assert reviewed["appearance_class_review"]["ownership"] == "UNKNOWN"
    assert reviewed["appearance_class_review"]["formal_fact"] is None
    assert result["feature_review"]["coordinates_changed"] is False
    assert result["feature_review"]["proposals_removed"] == 0
    assert result["feature_review"]["formal_outputs"] == 0
    assert result["development_events"] == [] and result["track_segments"] == []
    assert extractor.calls == 1


@pytest.mark.parametrize("mutation", [
    {"ownership": "SELF"},
    {"formal_self_position_fact": {"x": 1}},
    {"selected_self_position": {"x": 1}},
    {"development_events": [{"type": "DEATH"}]},
    {"track_segments": [{"id": "track"}]},
])
def test_feature_review_rejects_production_or_assigned_results(mutation):
    frame, sample = native_frame()
    proposals = development_proposals() | mutation
    extractor = SyntheticExtractor()
    with pytest.raises(ValueError, match="unassigned development proposals"):
        features.review_proposals(
            frame, sample, proposals, extractor=extractor,
            classifier=review_classifier(extractor.fingerprint),
        )
    assert extractor.calls == 0


@pytest.mark.parametrize("mutation", [
    {"map_position_norm": [0.1, 0.2]},
    {"zone_resolution": {"zone": "A"}},
])
def test_feature_review_rejects_formal_geometry_in_proposal_rows(mutation):
    frame, sample = native_frame()
    proposals = development_proposals()
    proposals["proposals"][0].update(mutation)
    extractor = SyntheticExtractor()
    with pytest.raises(ValueError, match="formal positions or Zones"):
        features.review_proposals(
            frame, sample, proposals, extractor=extractor,
            classifier=review_classifier(extractor.fingerprint),
        )
    assert extractor.calls == 0


def test_feature_review_requires_bound_feature_profile_and_native_pixels():
    frame, sample = native_frame()
    extractor = SyntheticExtractor()
    with pytest.raises(ValueError, match="does not bind"):
        features.review_proposals(
            frame, sample, development_proposals(), extractor=extractor,
            classifier=review_classifier("0" * 64),
        )
    assert extractor.calls == 0

    frame[0, 0, 0] ^= 1
    with pytest.raises(ValueError, match="Native review frame identity"):
        features.review_proposals(
            frame, sample, development_proposals(), extractor=extractor,
            classifier=review_classifier(extractor.fingerprint),
        )
    assert extractor.calls == 0


def test_feature_review_rejects_sample_from_another_native_pts():
    frame, sample = native_frame()
    changed_sample = dict(sample)
    changed_sample["native_pts_tick"] += 1
    extractor = SyntheticExtractor()

    with pytest.raises(ValueError, match="Native review frame identity"):
        features.review_proposals(
            frame, changed_sample, development_proposals(), extractor=extractor,
            classifier=review_classifier(extractor.fingerprint),
        )
    assert extractor.calls == 0


def test_feature_review_rejects_native_pixels_changed_during_extraction():
    frame, sample = native_frame()

    class MutatingExtractor(SyntheticExtractor):
        def extract(self, patches):
            features_result = super().extract(patches)
            frame[0, 0, 0] ^= 1
            return features_result

    extractor = MutatingExtractor()
    with pytest.raises(ValueError, match="Frame changed during appearance review"):
        features.review_proposals(
            frame, sample, development_proposals(), extractor=extractor,
            classifier=review_classifier(extractor.fingerprint),
        )


def test_feature_review_rejects_profile_fingerprint_changed_during_extraction():
    frame, sample = native_frame()

    class ChangingExtractor(SyntheticExtractor):
        def extract(self, patches):
            result = super().extract(patches)
            self.fingerprint = "f" * 64
            return result

    extractor = ChangingExtractor()
    with pytest.raises(ValueError, match="configuration changed"):
        features.review_proposals(
            frame, sample, development_proposals(), extractor=extractor,
            classifier=review_classifier(extractor.fingerprint),
        )
