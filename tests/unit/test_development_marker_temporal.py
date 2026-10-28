from copy import deepcopy

import numpy as np
import pytest

from valorant_ai_coach.visual.development_marker_attribution import freeze_native_sample
from valorant_ai_coach.visual.development_marker_features import _digest
from valorant_ai_coach.visual.development_marker_temporal import DevelopmentMarkerAssociations


def observation(tick, *, points=None, **changes):
    sample = freeze_native_sample(
        {
            "source_id": "synthetic",
            "source_sha256": "a" * 64,
            "acquisition_id": "epoch",
            "native_epoch": "epoch",
            "native_pts_tick": tick,
            "native_time_base": "1/60",
            "acquired_frame_sha256": "b" * 64,
            "native_pixel_sha256": "c" * 64,
            **changes,
        },
        frame_size_px=(64, 64),
    )
    points = [[20.0, 20.0], [40.0, 40.0]] if points is None else points
    pool = {
        "sample": sample,
        "ownership": "UNKNOWN",
        "formal_outputs": 0,
        "candidates": [{"center_frame_px": p} for p in points],
        "roi_xywh": [0, 0, 64, 64],
        "profile_fingerprint": "d" * 64,
        "map_id_candidate": "synthetic",
        "map_build": "unverified",
    }
    pool["pool_sha256"] = _digest(pool)
    return sample, pool


def continuity(previous, current):
    return {
        "verified": True,
        "source_sha256": current["source_sha256"],
        "native_epoch": current["native_epoch"],
        "time_base": current["native_time_base"],
        "previous_sample_sha256": previous["sample_sha256"],
        "current_sample_sha256": current["sample_sha256"],
        "receipt_sha256": "e" * 64,
    }


def observe(tracker, pair, previous=None, *, features=None, hud=None, receipt=None):
    sample, pool = pair
    if features is None:
        features = np.eye(2)[: len(pool["candidates"])]
    return tracker.observe(
        sample,
        pool,
        features,
        appearance_fingerprint="f" * 64,
        continuity=receipt
        if receipt is not None
        else continuity(previous, sample)
        if previous
        else None,
        hud=hud,
    )


def test_mutual_appearance_and_position_links_are_unqualified_endpoints():
    tracker = DevelopmentMarkerAssociations()
    a, b = observation(60), observation(72, points=[[21.0, 20.0], [41.0, 40.0]])
    assert observe(tracker, a)["links"] == []
    result = observe(tracker, b, a[0])
    assert len(result["links"]) == 2 and result["continuity_allowed"]
    assert all(x["physical_identity"] == "UNKNOWN" for x in result["links"])
    assert result["ownership"] == "UNKNOWN" and result["formal_outputs"] == 0


@pytest.mark.parametrize(
    "second",
    [
        observation(60),
        observation(59),
        observation(79),
        observation(72, source_sha256="0" * 64),
        observation(72, native_epoch="other", acquisition_id="other"),
        observation(72, native_time_base="1/120"),
    ],
)
def test_time_regression_gap_source_epoch_and_base_reset(second):
    tracker = DevelopmentMarkerAssociations()
    first = observation(60)
    observe(tracker, first)
    result = observe(tracker, second, first[0])
    assert not result["continuity_allowed"] and result["links"] == []


def test_close_timestamps_without_verified_receipt_do_not_link():
    tracker = DevelopmentMarkerAssociations()
    observe(tracker, observation(60))
    result = observe(tracker, observation(72))
    assert result["links"] == [] and not result["continuity_allowed"]


def test_position_alone_and_appearance_alone_cannot_link():
    tracker = DevelopmentMarkerAssociations()
    first = observation(60)
    observe(tracker, first)
    result = observe(tracker, observation(72), first[0], features=-np.eye(2))
    assert result["links"] == []
    result = observe(
        tracker,
        observation(84, points=[[50.0, 1.0], [1.0, 50.0]]),
        observation(72)[0],
        features=-np.eye(2),
    )
    assert result["links"] == []


def test_nearby_crossing_lookalikes_remain_ambiguous():
    tracker = DevelopmentMarkerAssociations()
    first = observation(60, points=[[20.0, 20.0], [21.0, 20.0]])
    observe(tracker, first, features=np.ones((2, 2)))
    result = observe(
        tracker,
        observation(72, points=[[20.5, 20.0], [20.5, 20.0]]),
        first[0],
        features=np.ones((2, 2)),
    )
    assert result["links"] == [] and result["ambiguous_links_rejected"] == 2


def test_disappearance_ends_track_and_reappearance_never_bridges_missing_observation():
    tracker = DevelopmentMarkerAssociations()
    first, missing, back = observation(60), observation(72, points=[]), observation(84)
    observe(tracker, first)
    observe(tracker, missing, first[0])
    result = observe(tracker, back, missing[0])
    assert result["reason"] == "first_observation" and result["links"] == []


def test_hud_view_change_resets_and_preserves_generic_markers():
    tracker = DevelopmentMarkerAssociations()
    first, second = observation(60), observation(72)
    observe(tracker, first)
    hud = {
        "sample_sha256": second[0]["sample_sha256"],
        "qualified": False,
        "origin": "image_reader",
        "view": "spectator",
        "life": "dead",
    }
    result = observe(tracker, second, first[0], hud=hud)
    assert result["reason"] == "view_change_reset" and result["links"] == []
    assert result["recorder_view_veto"] and result["generic_markers_preserved"]
    assert not result["self_marker_binding_qualified"]


def test_death_state_change_without_new_camera_ui_discards_prior_associations():
    tracker = DevelopmentMarkerAssociations()
    first, second = observation(60), observation(72)
    observe(tracker, first)
    hud = {
        "sample_sha256": second[0]["sample_sha256"],
        "qualified": False,
        "origin": "image_reader",
        "view": "unknown",
        "life": "dead",
    }
    result = observe(tracker, second, first[0], hud=hud)
    assert result["reason"] == "life_change_reset" and result["links"] == []


@pytest.mark.parametrize("qualified,origin", [(True, "image_reader"), (False, "inferred_owner")])
def test_foreign_or_qualified_hud_cannot_enter_research_association(qualified, origin):
    pair = observation(60)
    hud = {
        "sample_sha256": pair[0]["sample_sha256"],
        "qualified": qualified,
        "origin": origin,
        "view": "self",
        "life": "alive",
    }
    with pytest.raises(ValueError, match="unqualified view"):
        observe(DevelopmentMarkerAssociations(), pair, hud=hud)


def test_mutated_pool_is_rejected_and_discards_prior_state():
    tracker = DevelopmentMarkerAssociations()
    first, second = observation(60), observation(72)
    observe(tracker, first)
    changed = deepcopy(second[1])
    changed["candidates"][0]["center_frame_px"] = [30.0, 30.0]
    with pytest.raises(ValueError, match="Bound current"):
        observe(tracker, (second[0], changed), first[0])
    assert observe(tracker, second, first[0])["reason"] == "first_observation"
