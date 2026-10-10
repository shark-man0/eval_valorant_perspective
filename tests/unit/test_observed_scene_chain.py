import hashlib
import json

import cv2
import numpy as np
import pytest
from test_scene_domain_bootstrap import source as source

from scripts.diagnostics.observed_scene_chain import ObservedSceneChain
from valorant_ai_coach.hud.scene_episode import ObservedSceneEpisode
from valorant_ai_coach.hud.scene_references import WorldDomainBootstrap


@pytest.mark.parametrize("spacing", [0, -1, True, 0.5])
def test_shared_owner_checks_spacing_before_loading_reference_assets(spacing):
    def forbidden_factory():
        raise AssertionError("invalid native cadence must not load assets")

    with pytest.raises(ValueError, match="spacing"):
        ObservedSceneEpisode(forbidden_factory, native_step_ticks=spacing)


def test_shared_owner_constructs_initializer_once_and_owns_actual_source_history(source):
    native, path = native_source(source)
    loaded = []

    def factory():
        loaded.append(path)
        return WorldDomainBootstrap(path)

    episode = ObservedSceneEpisode(factory, native_step_ticks=256)
    seed = episode.observe(native, 90000, source_epoch="shared-native-source")
    assert seed["reason"] == "image_supported_observed_seed"
    assert "previous_source_pts_ticks" not in seed
    later = episode.observe(np.roll(native, 3, axis=1), 90256, source_epoch="shared-native-source")
    assert later["descriptive_scene_link"] is True
    assert later["previous_source_pts_ticks"] == 90000
    assert later["previous_source_pixel_sha256"] == hashlib.sha256(native.tobytes()).hexdigest()
    assert later["runtime_proof_authorized"] is False
    episode.observe(native, 91000, source_epoch="shared-native-source")
    assert episode.observe(native, 91256, source_epoch="shared-native-source")["reason"] == (
        "episode_terminated"
    )
    assert loaded == [path]


def native_source(source):
    _, path, _ = source
    return cv2.imread(str(path.parent / "world.png")), path


def test_observed_seed_emits_no_reference_to_native_temporal_link(source):
    native, path = native_source(source)
    chain = ObservedSceneChain(path, native_step_ticks=256)
    result = chain.observe(native, 70000, source_epoch="source-A")
    assert result["reason"] == "image_supported_observed_seed"
    assert not result["descriptive_scene_link"]
    assert not result["reference_is_observed_previous_frame"]
    assert "previous_source_pts_ticks" not in result
    assert result["source_pixel_sha256"] == hashlib.sha256(native.tobytes()).hexdigest()


def test_continuous_native_motion_binds_actual_previous_pixels_and_pts(source):
    native, path = native_source(source)
    chain = ObservedSceneChain(path, native_step_ticks=256)
    chain.observe(native, 70000, source_epoch="source-A")
    next_image = np.roll(native, 3, axis=1)
    result = chain.observe(next_image, 70256, source_epoch="source-A")
    assert result["descriptive_scene_link"]
    assert result["previous_source_pts_ticks"] == 70000
    assert result["previous_source_pixel_sha256"] == hashlib.sha256(native.tobytes()).hexdigest()
    assert result["source_pixel_sha256"] == hashlib.sha256(next_image.tobytes()).hexdigest()
    assert not result["runtime_proof_authorized"]
    assert not result["world_mask_authorized"]
    assert result["profile_sha256"] == hashlib.sha256(path.read_bytes()).hexdigest()
    assert result["reference_id"] == "synthetic-world"
    assert len(result["witnesses"]) >= 3
    assert result["minimum_witness_ncc"] == min(
        witness["fixed_projection_ncc"] for witness in result["witnesses"]
    )
    assert result["minimum_witness_ncc"] >= 0.90
    declared_boxes = json.loads(path.read_text())["references"][0]["world_boxes_640x360"]
    for witness in result["witnesses"]:
        assert witness["previous_box_640x360"] == declared_boxes[witness["region"]]
    transform = np.asarray(result["previous_to_current_affine_640x360"])
    assert transform.shape == (2, 3)
    np.testing.assert_allclose(transform[:, 2], [1, 0], atol=0.05)
    json.dumps(result, allow_nan=False)


@pytest.mark.parametrize("condition", ("gap", "duplicate", "epoch", "cut", "invalid_image"))
@pytest.mark.parametrize("deferred", [False, True])
def test_stopped_episode_cannot_reacquire_a_reference(condition, deferred, source):
    native, path = native_source(source)
    chain = ObservedSceneChain(path, native_step_ticks=256, deferred_initialization=deferred)
    chain.observe(native, 70000, source_epoch="source-A")
    current = np.roll(native, 3, axis=1)
    tick, epoch, cut = 70256, "source-A", False
    if condition == "gap":
        tick += 256
    elif condition == "duplicate":
        current = native
    elif condition == "epoch":
        epoch = "source-B"
    elif condition == "cut":
        cut = True
    else:
        current = None
    assert not chain.observe(current, tick, source_epoch=epoch, discontinuity=cut)[
        "descriptive_scene_link"
    ]
    assert chain.observe(native, tick + 256, source_epoch=epoch)["reason"] == "episode_terminated"


def test_unmatched_initial_frame_cannot_supply_a_seed(source):
    native, path = native_source(source)
    chain = ObservedSceneChain(path, native_step_ticks=256)
    unknown = np.random.default_rng(115).integers(0, 256, native.shape, np.uint8)
    assert chain.observe(unknown, 70000, source_epoch="source-A")["reason"] == (
        "image_supported_initialization_unavailable"
    )
    assert chain.observe(native, 70256, source_epoch="source-A")["reason"] == "episode_terminated"


def test_deferred_seed_has_no_history_from_pending_frames(source):
    native, path = native_source(source)
    chain = ObservedSceneChain(path, native_step_ticks=256, deferred_initialization=True)
    unknown = np.random.default_rng(115).integers(0, 256, native.shape, np.uint8)
    assert chain.observe(unknown, 70000, source_epoch="source-A")["reason"] == (
        "image_supported_initialization_pending"
    )
    assert chain.previous is None and chain.chain is None
    seed = chain.observe(native, 70256, source_epoch="source-A")
    assert seed["reason"] == "image_supported_observed_seed"
    assert not seed["descriptive_scene_link"]
    assert "previous_source_pts_ticks" not in seed
    assert chain.pending_binding is None
    link = chain.observe(np.roll(native, 3, axis=1), 70512, source_epoch="source-A")
    assert link["previous_source_pts_ticks"] == 70256


@pytest.mark.parametrize("condition", ["gap", "epoch", "duplicate", "cut"])
def test_pending_initialization_cannot_cross_source_protocol_break(condition, source):
    native, path = native_source(source)
    chain = ObservedSceneChain(path, native_step_ticks=256, deferred_initialization=True)
    unknown = np.random.default_rng(115).integers(0, 256, native.shape, np.uint8)
    chain.observe(unknown, 70000, source_epoch="source-A")
    result = chain.observe(
        unknown if condition == "duplicate" else native,
        70512 if condition == "gap" else 70256,
        source_epoch="source-B" if condition == "epoch" else "source-A",
        discontinuity=condition == "cut",
    )
    assert not result["descriptive_scene_link"]
    assert chain.terminated and chain.pending_binding is None
    assert chain.observe(native, 70768, source_epoch="source-A")["reason"] == "episode_terminated"


@pytest.mark.parametrize("bad_option", [None, 1, "yes"])
def test_deferred_initialization_requires_explicit_boolean(bad_option, source):
    _, path = native_source(source)
    with pytest.raises(ValueError, match="boolean"):
        ObservedSceneChain(path, native_step_ticks=256, deferred_initialization=bad_option)


@pytest.mark.parametrize(
    "bad_frame",
    [[], {}, 42, "decode failed", np.zeros((1080, 1920), np.uint8)],
    ids=["list", "dict", "scalar", "text", "wrong-shape"],
)
def test_malformed_decoded_frame_clears_observed_state(bad_frame, source):
    native, path = native_source(source)
    chain = ObservedSceneChain(path, native_step_ticks=256)
    chain.observe(native, 70000, source_epoch="source-A")
    assert chain.previous is not None
    result = chain.observe(bad_frame, 70256, source_epoch="source-A")
    assert result["reason"] == "invalid_native_image"
    assert chain.previous is None
    assert chain.chain is None
    assert chain.observe(native, 70512, source_epoch="source-A")["reason"] == "episode_terminated"


@pytest.mark.parametrize("bad_cut", [None, 0, "", []])
def test_unknown_or_mistyped_discontinuity_cannot_mean_continuous(bad_cut, source):
    native, path = native_source(source)
    chain = ObservedSceneChain(path, native_step_ticks=256)
    chain.observe(native, 70000, source_epoch="source-A")
    result = chain.observe(
        np.roll(native, 3, axis=1), 70256, source_epoch="source-A", discontinuity=bad_cut
    )
    assert result["reason"] == "invalid_source_binding"
    assert chain.previous is None
    assert chain.chain is None
    assert chain.observe(native, 70512, source_epoch="source-A")["reason"] == "episode_terminated"
