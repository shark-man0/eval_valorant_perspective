from copy import deepcopy

import pytest
from test_shared_current_map_view import marker
from test_shared_game_timeline import obs, replay

from valorant_ai_coach.temporal.evidence import digest
from valorant_ai_coach.temporal.game import observation
from valorant_ai_coach.temporal.map_projection import project_current_map
from valorant_ai_coach.temporal.zone_observations import BATCH_VERSION, normalize_zone_batch


def batch(tick=0, *, source="a", epoch="e", unread=False):
    sample = obs(tick, source=source, epoch=epoch)["sample"]
    profile = {
        "frame_size_px": [1920, 1080],
        "roi_xywh_native": [160, 8, 190, 36],
        "scale": 4,
        "padding": 24,
        "minimum_word_confidence": 0.90,
        "modes": ["gray_inverted", "bright_strokes_inverted"],
        "model_sha256": "c" * 64,
        "binary_sha256": "d" * 64,
    }
    readings = []
    for mode in profile["modes"]:
        readings.append(
            {
                "mode": mode,
                "text": "Bテスト",
                "minimum_confidence": 0.96,
                "words": [{"text": "Bテスト", "confidence": 0.96, "bbox": [64, 64, 120, 64]}],
                "box_inside_roi": True,
                "candidate_passed": True,
                "valid_TSV_output": True,
                "tsv_sha256": "e" * 64,
            }
        )
    if unread:
        readings[1].update(
            text="B別地点",
            words=[
                {
                    "text": "B別地点",
                    "confidence": 0.96,
                    "bbox": [64, 64, 120, 64],
                }
            ],
        )
    record = {
        "sample": sample,
        "profile_sha256": digest(profile),
        "roi_xywh_native": profile["roi_xywh_native"],
        "measurements": readings,
        "status": "UNKNOWN" if unread else "OBSERVED_LABEL_CANDIDATE",
        "zone_label_candidate": None if unread else "Bテスト",
        "confidence": None if unread else 0.96,
        "qualification": "development_only",
        "ownership": "UNKNOWN",
        "position_subject": "unassigned_viewed_actor",
        "formal_outputs": 0,
    }
    return seal(
        {
            "version": BATCH_VERSION,
            "profile": profile,
            "producer": {
                "implementation_sha256": "f" * 64,
                "profile_sha256": digest(profile),
                "model_sha256": profile["model_sha256"],
                "binary_sha256": profile["binary_sha256"],
                "language": "jpn",
                "renderings": "correlated",
            },
            "records": [record],
            "qualification": "development_only",
            "ownership": "UNKNOWN",
            "labels_or_reviews_used": False,
            "formal_outputs": 0,
        }
    )


def seal(value):
    return {
        **value,
        "batch_sha256": digest({k: v for k, v in value.items() if k != "batch_sha256"}),
    }


def zone(tick=0, **kwargs):
    return normalize_zone_batch(batch(tick, **kwargs))[0]


def test_supplier_zone_resolution_is_retained_in_dedicated_common_view():
    zone = {
        "zone_id": "synthetic-zone",
        "qualification": "development_only",
        "ownership": "UNKNOWN",
    }
    result = replay([obs(0, maps=[{"zone_resolution": zone}])])
    frame = result["frames"][0]
    assert frame["map"]["candidates"][0]["zone_resolution"] == zone
    assert frame["map"]["zone_candidates"] == [zone]
    assert result["qualified_events"] == result["qualified_facts"] == []


@pytest.mark.parametrize(
    "signals", [[], ["spectator"], ["remote"], ["owner_hud", "spectator"], ["owner_hud", "death"]]
)
def test_viewed_location_never_becomes_recorder_zone_without_current_self(signals):
    result = replay([obs(0, signals), zone(), marker(0)])
    state = result["frames"][0]["map"]
    assert state["zone_candidates"][0]["label_text"] == "Bテスト"
    assert state["zone_candidates"][0]["zone_subject"] == "unassigned_viewed_actor"
    assert state["current_recorder_zone_candidates"] == []
    projected = project_current_map(result)
    assert projected["rows"][0]["current_recorder_zone_hypotheses"] == []
    assert projected["rows"][0]["ownership"] == "UNKNOWN"
    assert projected["formal_outputs"] == 0


def test_current_zone_hypothesis_retains_original_sample_and_no_world_position():
    result = replay([obs(0, ["owner_hud"]), zone(), marker(0)])
    frame = result["frames"][0]
    assert frame["round"]["value"] == "UNKNOWN"
    candidate = frame["map"]["current_recorder_zone_candidates"][0]
    assert candidate["sample"] == frame["sample"]
    assert candidate["zone_subject"] == "current_recorder_hypothesis"
    assert candidate["map_position_norm"] is candidate["zone_resolution"] is None
    assert candidate["ownership"] == "UNKNOWN" and candidate["formal_outputs"] == 0
    projected = project_current_map(result)
    assert len(projected["seconds"][0]["current_recorder_zone_hypotheses"]) == 1
    assert projected["seconds"][0]["path"] is None


def test_carried_self_cannot_associate_a_new_location_and_missing_name_is_not_carried():
    carried = replay([obs(0, ["owner_hud"]), zone(10)])
    assert carried["frames"][-1]["camera"]["value"] == "SELF"
    assert carried["frames"][-1]["map"]["current_recorder_zone_candidates"] == []
    missing = replay([obs(0, ["owner_hud"]), zone(), obs(10, ["owner_hud"])])
    assert missing["frames"][-1]["map"]["zone_candidates"] == []
    assert missing["frames"][-1]["map"]["current_recorder_zone_candidates"] == []


def test_valid_unread_measurement_stays_observed_unknown_not_absent():
    original = batch(unread=True)
    saved = deepcopy(original)
    result = replay(normalize_zone_batch(original))
    assert original == saved
    state = result["frames"][0]["map"]
    assert state["observation_present"] is True
    assert state["zone_observation_ids"]
    assert state["zone_candidates"] == [] and state["status"] == "UNKNOWN"
    assert result["frames"][0]["camera"]["value"] == "UNKNOWN"


@pytest.mark.parametrize(
    "change",
    [
        {"valid_TSV_output": False},
        {"minimum_confidence": float("nan")},
        {"box_inside_roi": False},
        {"text": "B改変"},
    ],
)
def test_format_and_word_measurement_tampering_cannot_create_a_location(change):
    data = batch()
    data["records"][0]["measurements"][0].update(change)
    # NaN is rejected even before a valid seal can be generated.
    with pytest.raises(ValueError):
        normalize_zone_batch(seal(data))


def test_review_and_duplicate_samples_cannot_be_normalized_as_measurements():
    data = batch()
    data["labels_or_reviews_used"] = True
    with pytest.raises(ValueError, match="measurement batch"):
        normalize_zone_batch(seal(data))
    data = batch()
    data["records"].append(deepcopy(data["records"][0]))
    with pytest.raises(ValueError, match="One measured record"):
        normalize_zone_batch(seal(data))


def test_zone_observer_cannot_smuggle_an_owner_signal_into_common_state():
    row = zone()
    forged = observation(
        sample=row["sample"],
        producer=row["producer_fingerprint"],
        signals=["owner_hud"],
        raw=row["raw"],
        context=row["context"],
    )
    with pytest.raises(ValueError, match="cannot assert game state"):
        replay([forged])


def test_projection_rejects_changed_label_or_recorder_attribution():
    result = replay([obs(0, ["owner_hud"]), zone(), marker(0)])
    result["frames"][0]["map"]["zone_candidates"][0]["label_text"] = "B改変"
    with pytest.raises(ValueError, match="Original observed"):
        project_current_map(result)
    result = replay([obs(0, ["owner_hud"]), zone(), marker(0)])
    result["frames"][0]["map"]["current_recorder_zone_candidates"][0]["sample"] = obs(1)["sample"]
    with pytest.raises(ValueError, match="require shared current SELF"):
        project_current_map(result)


def test_exact_pixel_alias_does_not_transfer_recorder_zone_between_acquisitions():
    result = replay(
        [obs(0, ["owner_hud"]), zone(epoch="other"), marker(0)], fuse_exact_native_evidence=True
    )
    projected = project_current_map(result)
    assert len(projected["rows"][0]["zone_candidates"]) == 1
    assert projected["rows"][0]["current_recorder_zone_hypotheses"] == []


def test_replay_admits_all_zone_sources_before_output(tmp_path):
    from test_shared_timeline_replay import policy_fixture, write

    from valorant_ai_coach.temporal.replay import replay as replay_files
    from valorant_ai_coach.temporal.zone_observations import VERSION

    policy = write(tmp_path / "policy.json", policy_fixture(tmp_path))
    archive = write(
        tmp_path / "zones.json",
        {"version": VERSION, "observations": [zone(source="b")], "formal_outputs": 0},
    )
    with pytest.raises(ValueError, match="allowlist"):
        replay_files(policy_path=policy, hud_zones=archive)
