import hashlib
from pathlib import Path

import cv2
import numpy as np
import pytest

from valorant_ai_coach.visual.development_marker_attribution import freeze_native_sample
from valorant_ai_coach.visual.development_owner_marker import DevelopmentOwnerMarkerTracker
from valorant_ai_coach.visual.self_marker import SelfMarkerTracker


def setup(tmp_path: Path):
    rng = np.random.default_rng(5)
    positive = rng.integers(0, 256, (15, 15, 3), np.uint8)
    negative = rng.integers(0, 256, (15, 15, 3), np.uint8)
    for name, im in [("positive", positive), ("negative", negative)]:
        cv2.imwrite(str(tmp_path / (name + ".png")), im)
    spec = {
        "mode": "appearance_v1",
        "positive_templates": [str(tmp_path / "positive.png")],
        "negative_templates": [str(tmp_path / "negative.png")],
    }
    base = SelfMarkerTracker()
    assert base._load(spec)
    binding = {
        "source_id": "synthetic",
        "source_sha256": "a" * 64,
        "recorder_agent_id": "synthetic_agent",
        "review_sha256": "b" * 64,
        "reference_fingerprint": base.reference_fingerprint,
    }
    return positive, spec, binding


def current(tick, positive, *, visible=True, shift=0, life="alive", view="self", own=False):
    image = np.zeros((80, 80, 3), np.uint8)
    if visible:
        image[25:40, 25 + shift : 40 + shift] = positive
    pixel = hashlib.sha256(image.tobytes()).hexdigest()
    sample = freeze_native_sample(
        {
            "source_id": "synthetic",
            "source_sha256": "a" * 64,
            "acquisition_id": "epoch",
            "native_epoch": "epoch",
            "native_pts_tick": tick,
            "native_time_base": "1/60",
            "acquired_frame_sha256": "c" * 64,
            "native_pixel_sha256": pixel,
        },
        frame_size_px=(80, 80),
    )
    state = {
        "sample": sample,
        "sample_sha256": sample["sample_sha256"],
        "qualified": False,
        "life": life,
        "view": view,
        "native_continuity_used": tick > 0,
        "ownership": "UNKNOWN",
        "qualification": "development_only",
        "formal_outputs": 0,
        "state_origin": "image_reader",
        "anchor_origin": "image_reader",
        "raw_ui": {
            "own_hud_support": own,
            "source_profile_fingerprint": "d" * 64,
            "agent_measurements": {"recorder_agent_id": "synthetic_agent"},
        },
    }
    return image, state


def observe(tracker, image, state, spec, binding, *, eligible=True):
    tracker.set_observation(
        state,
        marker_binding=binding,
        expected_crop_pixel_sha256=hashlib.sha256(image.tobytes()).hexdigest(),
        context_fingerprint="e" * 64,
    )
    return tracker.observe(
        image, state["sample"]["native_pts_tick"] / 60, spec, ownership_eligible=eligible
    )


def test_bootstrap_ui_then_local_track_not_reidentify_each_frame(tmp_path):
    positive, spec, binding = setup(tmp_path)
    model = DevelopmentOwnerMarkerTracker()
    f, s = current(0, positive, own=True)
    first = observe(model, f, s, spec, binding)
    assert first.x_roi_norm is not None
    f, s = current(1, positive)
    second = observe(model, f, s, spec, binding)
    assert second.track_id == first.track_id and second.x_roi_norm is not None
    assert model.execution["global_initializations"] == 1
    assert model.execution["local_searches"] == 1
    assert second.identity == "UNKNOWN" and second.qualification == "development_only"


def test_occluded_identity_survives_but_current_position_stays_unknown(tmp_path):
    positive, spec, binding = setup(tmp_path)
    model = DevelopmentOwnerMarkerTracker()
    f, s = current(0, positive, own=True)
    first = observe(model, f, s, spec, binding)
    f, s = current(1, positive, visible=False)
    missing = observe(model, f, s, spec, binding)
    assert missing.x_roi_norm is None and model.identity_memory == first.track_id
    f, s = current(2, positive, shift=1)
    back = observe(model, f, s, spec, binding)
    assert back.track_id == first.track_id and back.x_roi_norm is not None
    assert model.execution["global_initializations"] == 1


@pytest.mark.parametrize(
    "life,view", [("dead", "spectator"), ("downed", "unknown"), ("alive", "spectator")]
)
def test_dead_and_spectated_locations_never_export_as_owner(tmp_path, life, view):
    positive, spec, binding = setup(tmp_path)
    model = DevelopmentOwnerMarkerTracker()
    f, s = current(0, positive, own=True)
    observe(model, f, s, spec, binding)
    f, s = current(1, positive, life=life, view=view)
    r = observe(model, f, s, spec, binding)
    assert r.x_roi_norm is None and model.identity_memory is None


def test_geometry_block_retains_identity_without_position(tmp_path):
    positive, spec, binding = setup(tmp_path)
    model = DevelopmentOwnerMarkerTracker()
    f, s = current(0, positive, own=True)
    first = observe(model, f, s, spec, binding)
    f, s = current(1, positive)
    r = observe(model, f, s, spec, binding, eligible=False)
    assert r.x_roi_norm is None and model.identity_memory == first.track_id


def test_contradictory_owner_unknown_requires_new_initial_binding(tmp_path):
    positive, spec, binding = setup(tmp_path)
    model = DevelopmentOwnerMarkerTracker()
    f, s = current(0, positive, own=True)
    observe(model, f, s, spec, binding)
    f, s = current(1, positive, life="unknown", view="unknown")
    r = observe(model, f, s, spec, binding)
    assert r.x_roi_norm is None and model.identity_memory is None
    f, s = current(2, positive)
    assert observe(model, f, s, spec, binding).x_roi_norm is None


def test_carried_alive_without_initial_ui_binding_cannot_choose_a_marker(tmp_path):
    positive, spec, binding = setup(tmp_path)
    model = DevelopmentOwnerMarkerTracker()
    f, s = current(0, positive)
    r = observe(model, f, s, spec, binding)
    assert r.x_roi_norm is None and model.execution["global_initializations"] == 0
    s["raw_ui"]["own_hud_support"] = True
    r = observe(model, f, s, spec, None)
    assert r.x_roi_norm is None


def test_missing_continuity_and_crop_mismatch_cannot_reuse_old_identity(tmp_path):
    positive, spec, binding = setup(tmp_path)
    model = DevelopmentOwnerMarkerTracker()
    f, s = current(0, positive, own=True)
    observe(model, f, s, spec, binding)
    f, s = current(1, positive)
    s["native_continuity_used"] = False
    assert observe(model, f, s, spec, binding).x_roi_norm is None
    f, s = current(2, positive, own=True)
    observe(model, f, s, spec, binding)
    f, s = current(3, positive)
    model.set_observation(
        s, marker_binding=binding, expected_crop_pixel_sha256="f" * 64, context_fingerprint="e" * 64
    )
    with pytest.raises(ValueError):
        model.observe(f, 3 / 60, spec, ownership_eligible=True)
    assert model.identity_memory is None


def test_deferred_initialization_uses_verified_carried_hud_anchor(tmp_path):
    positive, spec, binding = setup(tmp_path)
    model = DevelopmentOwnerMarkerTracker()
    f, s = current(0, positive, visible=False, own=True)
    anchor = s["sample"]
    assert observe(model, f, s, spec, binding).x_roi_norm is None
    f, s = current(1, positive)
    s["last_direct_alive_sample"] = anchor
    s["state_origin"] = "temporal_inference"
    assert observe(model, f, s, spec, binding).x_roi_norm is not None
    assert model.execution["successful_initializations"] == 1


def test_deferred_initialization_rejects_foreign_anchor(tmp_path):
    positive, spec, binding = setup(tmp_path)
    model = DevelopmentOwnerMarkerTracker()
    f, s = current(1, positive)
    _, old = current(0, positive)
    anchor = dict(old["sample"], source_sha256="f" * 64)
    s["last_direct_alive_sample"] = anchor
    s["state_origin"] = "temporal_inference"
    assert observe(model, f, s, spec, binding).x_roi_norm is None


def test_portrait_local_match_excludes_profile_background_as_initializer_does(tmp_path):
    positive, spec, _ = setup(tmp_path)
    spec["mode"] = "portrait_v2"
    base = SelfMarkerTracker()
    assert base._load(spec)
    binding = {
        "source_id": "synthetic",
        "source_sha256": "a" * 64,
        "recorder_agent_id": "synthetic_agent",
        "review_sha256": "b" * 64,
        "reference_fingerprint": base.reference_fingerprint,
    }
    model = DevelopmentOwnerMarkerTracker()
    f, s = current(0, positive, own=True)
    first = observe(model, f, s, spec, binding)
    assert first.x_roi_norm is not None
    changed = positive.copy()
    assert base._mask is not None
    changed[base._mask == 0] = 255 - changed[base._mask == 0]
    f, s = current(1, changed)
    second = observe(model, f, s, spec, binding)
    assert second.x_roi_norm is not None and second.track_id == first.track_id
