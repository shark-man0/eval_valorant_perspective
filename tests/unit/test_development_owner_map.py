import hashlib
from dataclasses import replace

import pytest

from tests.unit.test_development_learning_runs import frame as accepted_frame
from tests.unit.test_development_map import bind_case as make_map_case
from tests.unit.test_development_marker_temporal import continuity
from tests.unit.test_development_owner_observations import ui
from valorant_ai_coach.visual.development_marker_attribution import freeze_native_sample
from valorant_ai_coach.visual.development_marker_features import _digest
from valorant_ai_coach.visual.development_owner_map import DevelopmentOwnerMapPipeline
from valorant_ai_coach.visual.development_owner_observations import DevelopmentOwnerUI
from valorant_ai_coach.visual.self_marker import SelfMarkerTracker


@pytest.fixture
def bind_case(tmp_path):
    return make_map_case.__wrapped__(tmp_path)


def inputs(image, tick):
    frame = replace(
        accepted_frame(),
        native_pts_tick=tick,
        pixel_sha256=hashlib.sha256(image.tobytes()).hexdigest(),
        frame_size_px=(image.shape[1], image.shape[0]),
        roi_xywh=(0, 0, image.shape[1], image.shape[0]),
    )
    sample = freeze_native_sample(
        {
            "source_id": "synthetic",
            "source_sha256": frame.source_sha256,
            "native_epoch": frame.native_epoch,
            "acquisition_id": frame.acquisition_id,
            "native_pts_tick": frame.native_pts_tick,
            "native_time_base": frame.native_time_base,
            "acquired_frame_sha256": frame.frame_sha256,
            "native_pixel_sha256": frame.pixel_sha256,
        },
        frame_size_px=frame.frame_size_px,
    )
    return frame, sample


def test_accepted_pixels_reach_existing_map_with_temporal_owner_and_no_formal_fact(
    bind_case, monkeypatch
):
    _, _, image, profile, _ = bind_case
    tracker = SelfMarkerTracker()
    assert tracker._load(profile["minimap_self_marker"])
    profile["development_marker_binding"] = {
        "source_id": "synthetic",
        "source_sha256": "a" * 64,
        "recorder_agent_id": "synthetic",
        "reference_fingerprint": tracker.reference_fingerprint,
        "review_sha256": "f" * 64,
    }
    model = DevelopmentOwnerMapPipeline(profile, tracking="local")
    # Isolate the synthetic roster adapter; no real actor-identity label here.
    monkeypatch.setattr(
        model.map.recorder_view,
        "inspect",
        lambda *args, **kwargs: {
            "status": "disabled",
            "block_position_candidate": False,
            "recorder_agent_id": "synthetic",
            "positive_agent_association": False,
        },
    )
    previous = None
    for tick in range(3):
        frame, sample = inputs(image, tick)
        cues = ui(
            sample,
            own_hud_support=tick == 0,
            fingerprint=model.reader.fingerprint,
            source_profile_fingerprint=_digest(profile),
            agent_measurements={"recorder_agent_id": "synthetic"},
        )
        result = model.observe(
            image,
            sample,
            frame,
            cached_ui=cues,
            continuity=continuity(previous, sample) if previous else None,
        )
        assert result["owner"]["life"] == "alive"
        assert result["map"]["appearance"]["x_roi_norm"] is not None
        assert result["map"]["formal_self_position_fact"] is None
        assert result["ownership"] == "UNKNOWN" and result["formal_outputs"] == 0
        previous = sample
    assert result["marker_execution"]["global_initializations"] == 1
    assert result["marker_execution"]["local_searches"] == 2


@pytest.mark.parametrize("broken", ["acceptance", "pixels", "cached_reader", "native"])
def test_adapter_rejects_foreign_or_unaccepted_inputs_and_clears_state(bind_case, broken):
    _, _, image, profile, _ = bind_case
    model = DevelopmentOwnerMapPipeline(profile, tracking="legacy")
    frame, sample = inputs(image, 0)
    cues = ui(
        sample,
        own_hud_support=True,
        fingerprint=model.reader.fingerprint,
        source_profile_fingerprint=_digest(profile),
    )
    if broken == "acceptance":
        frame = replace(frame, source_acceptance=replace(frame.source_acceptance, accepted=False))
    elif broken == "pixels":
        image = image.copy()
        image[0, 0] ^= 255
    elif broken == "cached_reader":
        cues["fingerprint"] = "0" * 64
    else:
        sample = dict(sample, native_pts_tick=1)
    with pytest.raises(ValueError):
        model.observe(image, sample, frame, cached_ui=cues)
    assert model.owner.previous is None


def test_real_reader_does_not_make_blank_spectator_slot_verified_absence(bind_case):
    _, _, image, profile, _ = bind_case
    _, sample = inputs(image, 0)
    observed = DevelopmentOwnerUI(profile).inspect(image, sample)
    assert observed["own_hud_support"] is False
    assert observed["spectator_absence_checked"] is False


def test_spectated_subject_reaches_map_envelope_without_self_coordinates(bind_case):
    from valorant_ai_coach.visual.development_owner_observations import _spectated_subject

    _, _, image, profile, _ = bind_case
    model = DevelopmentOwnerMapPipeline(profile, tracking="legacy")
    frame, sample = inputs(image, 0)
    subject = _spectated_subject(
        {
            "status": "observed",
            "slot_kind": "spectated_player_name",
            "observed_alias": "synthetic-camera-subject",
            "ocr_confidence": 0.96,
            "current_name_pixels_sha256": "c" * 64,
            "activation_reference_sha256": "d" * 64,
        },
        sample,
        spectator_present=True,
    )
    cues = ui(
        sample,
        spectator_ui=True,
        fingerprint=model.reader.fingerprint,
        source_profile_fingerprint=_digest(profile),
        spectated_subject_observation=subject,
    )
    result = model.observe(image, sample, frame, cached_ui=cues)
    assert result["map"]["camera_subject_observation"] == subject
    assert result["map"]["map_position_norm"] is None
    assert result["owner"]["view"] == "spectator"
    assert result["formal_outputs"] == 0 and result["ownership"] == "UNKNOWN"
