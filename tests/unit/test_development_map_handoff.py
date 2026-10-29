"""Map consumer contracts with controlled external state, not game-state GT."""

from copy import deepcopy

import pytest

from tests.unit.test_development_owner_tracking import frame, link
from valorant_ai_coach.visual.development_map_handoff import (
    HANDOFF_VERSION,
    DevelopmentMapStateConsumer,
    aggregate_map_seconds,
    make_map_observation,
    map_candidate_path_record,
)
from valorant_ai_coach.visual.development_marker_features import _digest


def observation(tick, points=((32, 32),), **kwargs):
    args = frame(tick, points, **kwargs)
    packet = make_map_observation(
        sample=args["sample"],
        pool=args["pool"],
        ui=args["ui"],
        appearance={
            "sample_sha256": args["sample"]["sample_sha256"],
            "consistent_indices": [0] if len(points) == 1 else [],
            "reference_source_agent_supported": True,
            "qualification": "development_only",
            "ownership": "UNKNOWN",
            "formal_outputs": 0,
        },
        geometry={
            "sample": args["sample"],
            "map_id": "synthetic",
            "geometry_version": "v1",
            "calibration": {"status": "ok", "confidence": 0.9},
            "qualification": "development_only",
            "formal_self_position_fact": None,
        },
        reference_context_fingerprint="1" * 64,
    )
    return args, packet


def context(packet, **changes):
    c = {
        "schema": HANDOFF_VERSION,
        "sample_sha256": packet["sample"]["sample_sha256"],
        "origin": "controlled_ablation",
        "producer_fingerprint": "2" * 64,
        "revision": "v1",
        "tracking_epoch": "external-segment1",
        "round_state": "ACTIVE",
        "recorder_life": "ALIVE",
        "camera": "SELF",
        "recorder_correspondence": "supported",
        "source_continuity": "continuous",
        "round_token": "round1",
        "self_view_round_token": "round1",
        "evidence_sha256s": ["3" * 64],
        "qualification": "development_only",
        "ownership": "UNKNOWN",
        "formal_outputs": 0,
        **changes,
    }
    c["context_sha256"] = _digest(c)
    return c


def feed(tracker, args, packet, **changes):
    return tracker.observe(
        packet, args["features"], context=context(packet, **changes), continuity=args["continuity"]
    )


def test_common_state_missing_preserves_unassigned_measurements_only():
    a, packet = observation(60)
    original = deepcopy(packet)
    row = DevelopmentMapStateConsumer().observe(
        packet, a["features"], context=None, continuity=None
    )
    assert row["current_observation"] is None
    assert row["reason"] == "common_state_unavailable"
    assert packet == original and packet["pool"]["candidates"]
    assert row["ownership"] == "UNKNOWN" and row["formal_outputs"] == 0


def test_current_binding_then_endpoint_link_without_rechoosing_initial_marker():
    tracker = DevelopmentMapStateConsumer()
    a, p = observation(60)
    b, q = observation(72, ((34, 32),))
    first = feed(tracker, a, p)
    # Disable per-frame reference match; native appearance links still work.
    q["appearance"]["consistent_indices"] = []
    q["initial_candidate_index"] = None
    q["observation_sha256"] = _digest({k: v for k, v in q.items() if k != "observation_sha256"})
    result = feed(tracker, link(a, b), q)
    assert first["current_position_observed"]
    assert result["reason"] == "temporal_endpoint_link"
    assert result["connected_to_previous_observation"]
    assert result["identity_lineage_candidate"] == first["identity_lineage_candidate"]


def test_missing_identity_history_is_not_a_current_position_or_filled_path():
    tracker = DevelopmentMapStateConsumer()
    a, p = observation(60)
    b, q = observation(72, ())
    c, r = observation(84)
    first = feed(tracker, a, p)
    missing = feed(tracker, link(a, b), q)
    assert missing["current_observation"] is None and not missing["last_known_is_current"]
    assert missing["last_known_observation"] == first["current_observation"]
    assert missing["marker_identity_candidate"] == first["marker_identity_candidate"]
    back = feed(tracker, link(b, c), r)
    assert back["reason"] == "unique_reappearance"
    assert back["identity_lineage_candidate"] == first["identity_lineage_candidate"]
    assert back["observed_segment_id"] != first["observed_segment_id"]
    assert not back["connected_to_previous_observation"]


@pytest.mark.parametrize(
    "change",
    [
        {"camera": "SPECTATOR", "recorder_life": "UNKNOWN"},
        {"camera": "REMOTE"},
        {"recorder_life": "DEAD"},
        {"recorder_life": "DOWNED"},
        {"round_state": "ENDED"},
        {"round_state": "INTERMISSION"},
        {"recorder_correspondence": "UNKNOWN"},
        {"recorder_correspondence": "conflicting"},
        {"source_continuity": "discontinuous"},
        {"camera": "UNKNOWN"},
    ],
)
def test_external_veto_drops_mapping_and_cannot_infer_life(change):
    tracker = DevelopmentMapStateConsumer()
    a, p = observation(60)
    b, q = observation(72)
    feed(tracker, a, p)
    row = feed(tracker, link(a, b), q, **change)
    assert row["current_observation"] is None and row["marker_identity_candidate"] is None
    assert row["external_context"]["recorder_life"] == change.get("recorder_life", "ALIVE")


def test_next_round_needs_reconfirmed_self_scope_and_new_current_marker_evidence():
    tracker = DevelopmentMapStateConsumer()
    a, p = observation(60)
    b, q = observation(72)
    c, r = observation(84, ((32, 32), (80, 32)))
    d, s = observation(96)
    first = feed(tracker, a, p)
    assert not feed(tracker, link(a, b), q, round_token="round2")["current_position_observed"]
    assert not feed(tracker, link(b, c), r, round_token="round2", self_view_round_token="round2")[
        "current_position_observed"
    ]
    result = feed(tracker, link(c, d), s, round_token="round2", self_view_round_token="round2")
    assert result["current_position_observed"] and not result["connected_to_previous_observation"]
    assert result["identity_lineage_candidate"] != first["identity_lineage_candidate"]


@pytest.mark.parametrize(
    "change", ["profile", "source", "geometry", "reference", "gap", "reverse", "receipt"]
)
def test_no_inheritance_across_native_or_geometry_breaks(change):
    tracker = DevelopmentMapStateConsumer()
    a, p = observation(60)
    kwargs = {change: "0" * 64} if change in {"source", "profile"} else {}
    b, q = observation(
        90 if change == "gap" else 60 if change == "reverse" else 72, ((32, 32), (80, 32)), **kwargs
    )
    if change in {"geometry", "reference"}:
        q["geometry_version" if change == "geometry" else "reference_context_fingerprint"] = (
            "0" * 64
        )
        q["observation_sha256"] = _digest({k: v for k, v in q.items() if k != "observation_sha256"})
    feed(tracker, a, p)
    link(a, b)
    if change == "receipt":
        b["continuity"]["verified"] = False
    row = feed(tracker, b, q)
    assert row["current_observation"] is None and row["marker_identity_candidate"] is None


def test_ambiguous_reappearance_never_picks_one_marker():
    tracker = DevelopmentMapStateConsumer()
    a, p = observation(60)
    b, q = observation(72, ())
    c, r = observation(84, ((32, 32), (32, 32)))
    feed(tracker, a, p)
    feed(tracker, link(a, b), q)
    assert not feed(tracker, link(b, c), r)["current_position_observed"]


def test_stale_external_snapshot_and_recomputed_forgery_are_rejected():
    tracker = DevelopmentMapStateConsumer()
    a, p = observation(60)
    b, q = observation(72)
    feed(tracker, a, p)
    with pytest.raises(ValueError, match="Exact-sample"):
        tracker.observe(q, b["features"], context=context(p), continuity=link(a, b)["continuity"])
    assert tracker.memory is None
    q["initial_candidate_index"] = 88
    q["observation_sha256"] = _digest({k: v for k, v in q.items() if k != "observation_sha256"})
    with pytest.raises(ValueError, match="Unchanged"):
        feed(tracker, b, q)


def test_second_bins_retain_native_pts_and_do_not_fill_missing_seconds():
    tracker = DevelopmentMapStateConsumer()
    records = []
    for tick in (59, 60, 72, 180):
        a, p = observation(tick)
        records.append(feed(tracker, a, p))
    bins = aggregate_map_seconds(records)
    assert [b["second_from_source_pts_zero"] for b in bins] == [0, 1, 3]
    assert [o["sample"]["native_pts_tick"] for b in bins for o in b["observations"]] == [
        59,
        60,
        72,
        180,
    ]
    assert all(b["continuous_occupancy"] == "UNKNOWN" for b in bins)
    with pytest.raises(ValueError, match="order"):
        aggregate_map_seconds([records[0], records[0]])


def test_external_tracking_epoch_resets_even_if_sampled_camera_labels_are_identical():
    tracker = DevelopmentMapStateConsumer()
    a, p = observation(60)
    b, q = observation(72, ((32, 32), (80, 32)))
    feed(tracker, a, p)
    row = feed(tracker, link(a, b), q, tracking_epoch="after-unseen-camera-transition")
    assert row["current_observation"] is None and row["marker_identity_candidate"] is None


def test_path_adapter_rejects_formal_zone_and_never_displays_stale_position():
    tracker = DevelopmentMapStateConsumer()
    a, p = observation(60)
    row = feed(tracker, a, p)
    path = map_candidate_path_record(p, row, frame_index=1)
    assert path["map_position_norm"] == [0.2, 0.3]
    assert path["native_sample"] == a["sample"] and path["formal_self_position_fact"] is None
    with pytest.raises(ValueError, match="Zone"):
        map_candidate_path_record(p, row, frame_index=1, zone_resolution={"ownership": "SELF"})
    b, q = observation(72, ())
    stale = feed(tracker, link(a, b), q)
    assert map_candidate_path_record(q, stale, frame_index=2)["map_position_norm"] is None


def test_expired_mapping_keeps_history_but_does_not_block_new_unconnected_initialization():
    tracker = DevelopmentMapStateConsumer()
    a, p = observation(60)
    first = feed(tracker, a, p)
    previous = a
    for tick in (72, 84, 96):
        missing, q = observation(tick, ())
        row = feed(tracker, link(previous, missing), q)
        assert row["current_observation"] is None
        assert row["last_known_observation"] == first["current_observation"]
        previous = missing
    b, q = observation(108, ((80, 32),))
    back = feed(tracker, link(previous, b), q)
    assert back["current_position_observed"]
    assert back["identity_lineage_candidate"] != first["identity_lineage_candidate"]
    assert not back["connected_to_previous_observation"]


def test_changed_measured_reference_cannot_inherit_even_with_stale_caller_context():
    tracker = DevelopmentMapStateConsumer()
    a, p = observation(60)
    b, q = observation(72, ((32, 32), (80, 32)))
    feed(tracker, a, p)
    q["appearance"]["reference_measurements"] = {"reference_fingerprint": "9" * 64}
    q["observation_sha256"] = _digest({k: v for k, v in q.items() if k != "observation_sha256"})
    row = feed(tracker, link(a, b), q)
    assert row["marker_identity_candidate"] is None and row["current_observation"] is None
