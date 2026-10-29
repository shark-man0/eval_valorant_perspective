from copy import deepcopy

import pytest
from test_shared_game_timeline import obs, replay

from valorant_ai_coach.temporal.game import observation


def map_row(*, tick=0, continuity=None):
    sample = obs(tick, epoch="b")["sample"]
    candidates = [{"marker_id": "candidate"}]
    return observation(
        sample=sample,
        producer="c" * 64,
        signals=[],
        context={"stream_kind": "map"},
        continuity=continuity,
        raw={
            "schema": "map_consumer_provisional_v1",
            "pool": {"candidates": candidates},
            "initial_candidate_index": 0,
        },
        map_candidates=candidates,
    )


def test_exact_current_pixels_share_measurements_without_epoch_state_carry():
    owner = obs(0, ["buy", "owner_hud"], epoch="a", context={"stream_kind": "hud"})
    marker = map_row()
    before = replay([owner, marker])
    after = replay([owner, marker], fuse_exact_native_evidence=True)
    assert before["frames"][-1]["life"]["value"] == "UNKNOWN"
    state = after["frames"][-1]
    assert state["sample"] == marker["sample"]
    assert state["continuity"]["carry_allowed"] is False
    assert state["continuity"]["semantic"] == "UNKNOWN"
    assert state["life"]["value"] == "ALIVE"
    assert state["map"]["current_self_position_candidates"] == marker["map_candidates"]
    assert state["current_pixel_evidence_links"][0]["independent_confirmation"] is False
    assert len(after["observations"]) == 2  # Aliases are not additional observations.
    assert owner["sample"]["acquired_frame_sha256"] != marker["sample"]["acquired_frame_sha256"]
    assert after["qualified_facts"] == after["qualified_events"] == []


@pytest.mark.parametrize(
    "field,value",
    [
        ("native_pts_tick", 1),
        ("native_pixel_sha256", "e" * 64),
        ("frame_size_px", [1080, 1920]),
        ("source_sha256", "e" * 64),
    ],
)
def test_near_time_or_different_pixels_geometry_source_never_alias(field, value):
    marker = map_row()
    sample = deepcopy(marker["sample"])
    del sample["sample_sha256"]
    sample[field] = value
    marker = observation(
        sample=sample,
        producer="c" * 64,
        signals=[],
        raw=marker["raw"],
        map_candidates=marker["map_candidates"],
    )
    result = replay(
        [obs(0, ["buy", "owner_hud"], epoch="a"), marker], fuse_exact_native_evidence=True
    )
    state = next(f for f in result["frames"] if f["sample"]["native_epoch"] == "b")
    assert state["life"]["value"] == "UNKNOWN"


@pytest.mark.parametrize("cue", [{"decode_ok": False}, {"content_break_confirmed": True}])
@pytest.mark.parametrize("broken_donor", [False, True])
def test_invalid_acquisition_cues_do_not_transfer_evidence(cue, broken_donor):
    owner = obs(0, ["owner_hud"], epoch="a", continuity=cue if broken_donor else None)
    marker = map_row(continuity=None if broken_donor else cue)
    result = replay([owner, marker], fuse_exact_native_evidence=True)
    assert result["frames"][-1]["life"]["value"] == "UNKNOWN"


def test_a_state_inferred_at_another_time_cannot_be_transferred_as_current_evidence():
    result = replay(
        [obs(0, ["owner_hud"], epoch="a"), obs(1, epoch="a"), map_row(tick=1)],
        fuse_exact_native_evidence=True,
    )
    state = next(f for f in result["frames"] if f["sample"]["native_epoch"] == "b")
    assert state["life"]["value"] == "UNKNOWN"


def test_same_pixel_conflicting_observers_abstain_instead_of_voting():
    result = replay(
        [obs(0, ["owner_hud"], epoch="a"), obs(0, ["spectator"], epoch="b")],
        fuse_exact_native_evidence=True,
    )
    assert all(f["camera"]["value"] == "UNKNOWN" for f in result["frames"])
    assert all("ALIVE" in f["life"]["hypotheses"] for f in result["frames"])


def test_intermittent_exact_observer_does_not_reset_original_stream():
    rows = [obs(t, ["buy"] if t == 0 else [], epoch="a") for t in range(4)]
    rows.append(obs(1, ["spectator"], epoch="b"))
    result = replay(rows, fuse_exact_native_evidence=True)
    original = [f for f in result["frames"] if f["sample"]["native_epoch"] == "a"]
    assert all(f["continuity"]["carry_allowed"] for f in original[1:])
    assert all(f["round"]["value"] == "BUY" for f in original)


def test_borrowed_origin_profile_change_still_resets():
    owners = [obs(t, ["buy"] if t == 0 else [], epoch="a") for t in (0, 1)]
    donors = [
        obs(0, epoch="b", context={"profile_fingerprint": "old"}),
        obs(1, epoch="b", context={"profile_fingerprint": "new"}),
    ]
    result = replay(owners + donors, fuse_exact_native_evidence=True)
    target = next(
        f for f in result["frames"]
        if f["sample"]["native_epoch"] == "a" and f["sample"]["native_pts_tick"] == 1
    )
    assert target["continuity"]["reason"] == "producer_or_profile_change"
    assert target["round"]["value"] == "UNKNOWN"
