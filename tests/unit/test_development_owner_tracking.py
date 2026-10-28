import hashlib

import cv2
import numpy as np
import pytest

from valorant_ai_coach.visual.development_camera_marker_ui import inspect_camera_marker_ui
from valorant_ai_coach.visual.development_marker_attribution import freeze_native_sample
from valorant_ai_coach.visual.development_marker_features import _digest
from valorant_ai_coach.visual.development_owner_tracking import (
    DevelopmentOwnerTracking,
    owner_tracking_features,
)


def frame(tick, points=((32, 32),), *, source="a" * 64, profile="c" * 64):
    image = np.zeros((96, 128, 3), np.uint8)
    for x, y in points:
        cv2.circle(image, (x, y), 10, (80, 210, 210), 2)
        image[y - 5 : y + 6, x - 5 : x + 6] = np.random.default_rng(42).integers(
            0, 255, (11, 11, 3), dtype=np.uint8
        )
    sample = freeze_native_sample(
        {
            "source_id": "synthetic",
            "source_sha256": source,
            "acquisition_id": "epoch",
            "native_epoch": "epoch",
            "native_pts_tick": tick,
            "native_time_base": "1/60",
            "acquired_frame_sha256": "b" * 64,
            "native_pixel_sha256": hashlib.sha256(image.tobytes()).hexdigest(),
        },
        frame_size_px=(128, 96),
    )
    pool = {
        "sample": sample,
        "ownership": "UNKNOWN",
        "formal_outputs": 0,
        "parent_count": len(points),
        "candidates": [
            {"center_frame_px": list(p), "geometry_only_map_position_norm": [0.2, 0.3]}
            for p in points
        ],
        "roi_xywh": [0, 0, 128, 96],
        "profile_fingerprint": profile,
        "map_id_candidate": "synthetic",
        "map_build": "unverified",
    }
    pool["pool_sha256"] = _digest(pool)
    ui = inspect_camera_marker_ui(image, sample, pool)
    proposal = {
        "sample_sha256": sample["sample_sha256"],
        "ownership": "UNKNOWN",
        "formal_outputs": 0,
        "recorder_account_identity_qualified": False,
        "marker_id": None,
        "candidate_index": None,
        "camera": "unknown",
        "binding_origin": "none",
        "evidence_sha256": "e" * 64,
    }
    return dict(
        sample=sample,
        pool=pool,
        ui=ui,
        proposal=proposal,
        features=owner_tracking_features(image, sample, pool),
        identity_context_fingerprint=profile,
        continuity=None,
    )


def seed(args):
    args["proposal"].update(
        marker_id=args["ui"]["rows"][0]["marker_observation_id"],
        candidate_index=0,
        camera="first_person_candidate",
        binding_origin="automatic_ui",
    )
    return args


def link(a, b):
    b["continuity"] = {
        "verified": True,
        "source_sha256": b["sample"]["source_sha256"],
        "native_epoch": "epoch",
        "time_base": "1/60",
        "previous_sample_sha256": a["sample"]["sample_sha256"],
        "current_sample_sha256": b["sample"]["sample_sha256"],
        "receipt_sha256": "f" * 64,
    }
    return b


def test_moving_native_marker_is_connected_without_per_frame_HUD_or_agent_ID():
    tracker = DevelopmentOwnerTracking()
    a, b = seed(frame(60)), frame(72, ((34, 32),))
    assert tracker.observe(**a)["current_position_observed"]
    row = tracker.observe(**link(a, b))
    assert row["current_observation"]["image_position_px"] == (34, 32)
    assert row["selection_origin"] == "temporal_endpoint_link"
    assert row["connected_to_previous_observation"]
    assert row["life"] == "unknown" and row["ownership"] == "UNKNOWN"


def test_missing_retains_ID_but_reappearance_starts_new_observed_segment():
    tracker = DevelopmentOwnerTracking()
    a, b, c = seed(frame(60)), frame(72, ()), frame(84)
    first = tracker.observe(**a)
    missing = tracker.observe(**link(a, b))
    assert missing["current_observation"] is None
    assert missing["recorder_marker_id"] == first["recorder_marker_id"]
    assert missing["identity_lineage_id"] == first["identity_lineage_id"]
    back = tracker.observe(**link(b, c))
    # Identity may resume after verified empty frames; no path crosses the gap.
    assert not back["connected_to_previous_observation"]
    assert back["current_observation"] is not None
    assert back["observed_segment_id"] != first["observed_segment_id"]
    assert back["selection_origin"] == "unique_reappearance"
    assert back["identity_lineage_id"] == first["identity_lineage_id"]


def test_ambiguous_close_reappearance_never_selects_one_location():
    tracker = DevelopmentOwnerTracking()
    a, b = seed(frame(60)), frame(72, ((32, 32), (32, 32)))
    tracker.observe(**a)
    assert tracker.observe(**link(a, b))["current_observation"] is None


@pytest.mark.parametrize("change", ["source", "profile", "gap", "receipt", "regression"])
def test_context_or_continuity_break_cannot_inherit(change):
    tracker = DevelopmentOwnerTracking()
    a = seed(frame(60))
    b = frame(72)
    if change == "source":
        b = frame(72, source="0" * 64)
    if change == "profile":
        b = frame(72, profile="0" * 64)
    if change == "gap":
        b = frame(90)
    if change == "regression":
        b = frame(60)
    tracker.observe(**a)
    link(a, b)
    if change == "receipt":
        b["continuity"]["verified"] = False
    row = tracker.observe(**b)
    assert row["current_observation"] is None and row["recorder_marker_id"] is None


def test_spectator_clears_owner_candidate_without_claiming_recorder_death():
    tracker = DevelopmentOwnerTracking()
    a, b, c = seed(frame(60)), frame(72), frame(84)
    tracker.observe(**a)
    link(a, b)
    b["proposal"]["camera"] = "spectator"
    row = tracker.observe(**b)
    assert row["camera"] == "spectator" and row["life"] == "unknown"
    assert row["current_observation"] is None
    assert tracker.observe(**link(b, c))["current_observation"] is None


def test_forged_human_candidate_id_is_rejected_and_resets_state():
    tracker = DevelopmentOwnerTracking()
    a, b = seed(frame(60)), seed(frame(72))
    tracker.observe(**a)
    b["proposal"]["marker_id"] = "human-reviewed-id"
    with pytest.raises(ValueError, match="Automatic"):
        tracker.observe(**link(a, b))
    assert tracker.previous is None


def test_agreeing_UI_refresh_preserves_the_observed_segment():
    tracker = DevelopmentOwnerTracking()
    a, b = seed(frame(60)), seed(frame(72, ((34, 32),)))
    first = tracker.observe(**a)
    row = tracker.observe(**link(a, b))
    assert row["selection_origin"] == "automatic_UI_refresh"
    assert row["connected_to_previous_observation"]
    assert row["observed_segment_id"] == first["observed_segment_id"]
    assert row["identity_lineage_id"] == first["identity_lineage_id"]


def test_new_UI_disagreeing_with_observed_identity_cannot_silently_switch():
    tracker = DevelopmentOwnerTracking()
    a, b = seed(frame(60)), seed(frame(72, ((32, 32), (80, 32))))
    first = tracker.observe(**a)
    b["proposal"].update(candidate_index=1, marker_id=b["ui"]["rows"][1]["marker_observation_id"])
    row = tracker.observe(**link(a, b))
    assert row["current_observation"] is None
    assert row["recorder_marker_id"] == first["recorder_marker_id"]
    assert row["selection_origin"] == "conflicting_initialization"
