import pytest
from test_shared_game_timeline import obs, replay

from valorant_ai_coach.temporal.adapters import hud_packet, map_packet, owner_ui, round_readers
from valorant_ai_coach.temporal.evidence import digest
from valorant_ai_coach.temporal.replay import compare_reviewed, write_private


def frame(sample):
    return {
        **{
            k: sample[k]
            for k in (
                "source_sha256",
                "acquisition_id",
                "native_epoch",
                "native_pts_tick",
                "native_time_base",
                "frame_size_px",
            )
        },
        "frame_sha256": sample["acquired_frame_sha256"],
        "pixel_sha256": sample["native_pixel_sha256"],
    }


def round_input(timer="1:40", *, confidence=0.99, geometry=True):
    sample = obs(1)["sample"]
    row = {
        "source_id": sample["source_id"],
        "source_sha256": sample["source_sha256"],
        "epoch": sample["native_epoch"],
        "tick": sample["native_pts_tick"],
        "time_base": sample["native_time_base"],
        "encoded_sha256": sample["acquired_frame_sha256"],
        "pixel_sha256": sample["native_pixel_sha256"],
        "component_geometry": {"roles": {"score": geometry, "timer": geometry, "result": geometry}},
        "ally_score": {"value": "1", "confidence": confidence},
        "enemy_score": {"value": "2", "confidence": confidence},
        "timer": {"value": timer, "confidence": confidence},
        "result": {"value": None, "confidence": 0},
    }
    return {
        "frame_contract": frame(sample),
        "row": row,
        "reader_fingerprint": "c" * 64,
        "profile_fingerprint": "d" * 64,
    }


@pytest.mark.parametrize("timer", ["29.04", "1:99", "UNKNOWN", None])
def test_decimal_or_invalid_clock_never_becomes_round_start(timer):
    assert "active" not in round_readers(round_input(timer))["signals"]


def test_no_geometry_or_low_confidence_cannot_support_active():
    assert "active" in round_readers(round_input())["signals"]
    assert "active" not in round_readers(round_input(geometry=False))["signals"]
    assert "active" not in round_readers(round_input(confidence=0.89))["signals"]
    item = round_input()
    item["row"]["component_geometry"] = None
    assert round_readers(item)["signals"] == []


def test_round_native_mutation_rejected():
    item = round_input()
    item["row"]["tick"] += 1
    with pytest.raises(ValueError):
        round_readers(item)


def test_owner_not_detected_is_unknown_and_report_not_death():
    sample = obs(1)["sample"]
    item = {
        "frame_contract": frame(sample),
        "source_id": sample["source_id"],
        "ui": {
            "sample_sha256": sample["sample_sha256"],
            "qualified": False,
            "formal_outputs": 0,
            "fingerprint": "c" * 64,
            "source_profile_fingerprint": "d" * 64,
            "own_hud_support": False,
            "combat_report_visible": True,
        },
    }
    assert owner_ui(item)["signals"] == ["report"]
    item["ui"]["qualified"] = True
    with pytest.raises(ValueError):
        owner_ui(item)


def test_supplier_packet_does_not_accept_false_as_negative_or_alias_as_owner():
    sample = obs(1)["sample"]
    p = {
        "version": "development_hud_observations_v1",
        "qualification": "development_only",
        "qualified": False,
        "formal_events": [],
        "formal_outputs": 0,
        "ownership": "UNKNOWN",
        "sample": sample,
        "reader_fingerprint": "c" * 64,
        "profile_fingerprint": "d" * 64,
        "measurements": [
            {"name": "current_owner_hud_support", "status": "UNKNOWN", "value": False},
            {"name": "spectated_subject_display", "value": "recorder alias"},
        ],
        "continuity_observations": {},
    }
    assert hud_packet(p)["signals"] == []
    p["formal_outputs"] = 1
    with pytest.raises(ValueError):
        hud_packet(p)


def test_map_packet_preserves_candidates_without_inventing_life():
    sample = obs(1)["sample"]
    packet = {
        "schema": "map_consumer_provisional_v1",
        "qualification": "development_only",
        "ownership": "UNKNOWN",
        "formal_outputs": 0,
        "sample": sample,
        "pool": {"sample": sample, "candidates": [{"geometry_only_map_position_norm": [0.1, 0.2]}]},
        "ui": {"feature_fingerprint": "c" * 64},
        "reference_context_fingerprint": "d" * 64,
    }
    packet["observation_sha256"] = digest(packet)
    row = map_packet(packet)
    assert row["signals"] == []
    assert row["map_candidates"] == packet["pool"]["candidates"]
    packet["pool"]["sample"] = {}
    with pytest.raises(ValueError):
        map_packet(packet)


def test_unknown_review_never_enters_negative_denominator():
    result = replay([obs(0, ["owner_hud"])])
    base = {
        "origin": "human_exact_frame",
        "review_sha256": "e" * 64,
        "domain": "life",
        "sample_sha256": result["frames"][0]["sample"]["sample_sha256"],
    }
    metrics = compare_reviewed(result, [{**base, "value": "UNKNOWN"}, {**base, "value": "ALIVE"}])
    assert metrics["reviewed"] == metrics["correct"] == 1
    assert metrics["excluded_unknown_or_unexposed"] == 1


def test_private_outputs_are_exclusive_and_reject_checkout(tmp_path):
    p = tmp_path / "private.json"
    write_private(p, {"text": "日本語"})
    assert p.stat().st_mode & 0o777 == 0o600
    with pytest.raises(FileExistsError):
        write_private(p, {})
    checkout = tmp_path / "checkout"
    checkout.mkdir()
    (checkout / ".git").mkdir()
    with pytest.raises(ValueError):
        write_private(checkout / "result.json", {})
