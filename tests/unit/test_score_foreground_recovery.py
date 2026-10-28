from __future__ import annotations

from copy import deepcopy

import numpy as np
import pytest

from scripts.diagnostics.score_foreground_recovery import (
    ScoreReadHistory,
    grouped_score,
    recover_score,
    review_visibility,
)
from scripts.temporal_gt.contract import canonical_hash
from tests.unit.test_hud_feature_contract import frame
from tests.unit.test_timer_glyphs import _templates
from valorant_ai_coach.hud.score_glyphs import StrictScoreGlyphReader


@pytest.mark.parametrize("case", ["empty", "oversize", "nonbinary", "channels"])
def test_group_mask_is_bounded_and_binary(case):
    masks = {
        "empty": np.zeros((0, 2), np.uint8),
        "oversize": np.zeros((1025, 1025), np.uint8),
        "nonbinary": np.full((8, 8), 127, np.uint8),
        "channels": np.zeros((8, 8, 3), np.uint8),
    }
    with pytest.raises(ValueError):
        grouped_score(masks[case], None)


@pytest.mark.parametrize("level", [0, 128, 255])
def test_no_score_uniform_has_no_recovery(level):
    reader = StrictScoreGlyphReader(_templates())
    result = recover_score(np.full((45, 44, 3), level, np.uint8), reader)
    assert result["value"] is None and not result["missing_native_pixels_filled"]
    assert result["formal_events"] == []


def observe(history, f, direct=None, recovery=None, **kw):
    return history.observe(
        f,
        direct=direct,
        recovery=recovery,
        geometry=kw.pop("geometry", True),
        expected_step=1,
        native_continuity_verified=kw.pop("verified", True),
        **kw,
    )


def test_history_never_fills_hidden_frame_and_stale_read_cannot_recover():
    h = ScoreReadHistory()
    f = frame()
    observe(h, f, direct="12")
    f["tick"] += 1
    r = observe(h, f)
    assert r["current_value"] is None and r["previous_direct_observation"]["value"] == "12"
    assert r["display_presence"] == "UNVERIFIED"
    f["tick"] += 1
    r = observe(h, f, recovery="12")
    assert r["current_value"] is None


@pytest.mark.parametrize(
    "change",
    [
        "gap",
        "duplicate",
        "reverse",
        "epoch",
        "time_base",
        "source_id",
        "source_sha256",
        "cut",
        "unverified",
    ],
)
def test_native_discontinuity_resets_history(change):
    h = ScoreReadHistory()
    f = frame()
    observe(h, f, direct="12")
    f["tick"] += 1
    kw = {}
    if change in ["epoch", "source_id"]:
        f[change] += "_other"
    elif change == "source_sha256":
        f[change] = "f" * 64
    elif change == "time_base":
        f[change] = "1/30"
    elif change == "cut":
        kw["explicit_cut"] = True
    elif change == "unverified":
        kw["verified"] = False
    else:
        f["tick"] += {"gap": 1, "duplicate": -1, "reverse": -2}[change]
    r = observe(h, f, recovery="12", **kw)
    assert r["current_value"] is None and r["previous_direct_observation"] is None


def test_current_pixels_and_geometry_are_required_despite_temporal_agreement():
    h = ScoreReadHistory()
    f = frame()
    observe(h, f, direct="12")
    f["tick"] += 1
    assert observe(h, f, recovery="12")["current_value"] == "12"
    h = ScoreReadHistory()
    f = frame()
    observe(h, f, direct="12")
    f["tick"] += 1
    assert observe(h, f, recovery="12", geometry=False)["current_value"] is None
    h = ScoreReadHistory()
    f = frame()
    observe(h, f, direct="12")
    f["tick"] += 1
    assert observe(h, f, direct="13", recovery="2")["current_value"] == "13"


def test_short_suffix_and_lost_foreground_is_uncertain_until_full_read_or_cut():
    h = ScoreReadHistory()
    f = frame()
    observe(h, f, direct="13", foreground_pixels=100)
    f["tick"] += 1
    r = observe(h, f, direct="3", foreground_pixels=40)
    assert r["current_direct_read"] == "3" and r["current_value"] is None
    f["tick"] += 1
    assert observe(h, f, direct="3", foreground_pixels=40)["current_value"] is None
    f["tick"] += 1
    assert observe(h, f, direct="14", foreground_pixels=100)["current_value"] == "14"
    f["tick"] += 1
    assert observe(h, f, direct="4", foreground_pixels=40)["current_value"] is None
    f["tick"] += 1
    assert (
        observe(h, f, direct="4", explicit_cut=True, foreground_pixels=40)["current_value"] == "4"
    )


@pytest.mark.parametrize("marker", [True, None, "UNKNOWN"])
def test_same_pts_spacing_does_not_hide_explicit_or_unknown_cut(marker):
    h = ScoreReadHistory()
    f = frame()
    observe(h, f, direct="12")
    f["tick"] += 1
    f["discontinuity"] = marker
    r = observe(h, f, recovery="12")
    assert r["current_value"] is None and r["previous_direct_observation"] is None


def packet_answer():
    p = {
        "kind": "DEVELOPMENT_blind_transcription_score_NOT_GT",
        "cases": [{"id": "one", "candidate_id": "point1", "frame": frame()}],
    }
    a = {
        "origin": "human",
        "reviewer": "user",
        "packet_sha256": canonical_hash(p),
        "cases": [
            {
                "id": "one",
                "reviewed": True,
                "left_score": None,
                "right_score": 12,
                "left_visibility": "ABSENT",
                "right_visibility": "VISIBLE",
            }
        ],
    }
    return p, a


def test_visibility_extends_bound_literal_contract_without_generating_gt():
    p, a = packet_answer()
    r = review_visibility(p, a)
    assert r["observations"][0]["visibility"] == "ABSENT"
    assert r["observations"][1]["literal"] == 12
    assert not r["approved_gt"] and r["formal_events"] == []


@pytest.mark.parametrize(
    "violation", ["partial_number", "unreviewed", "wrong_hash", "unknown_state"]
)
def test_absence_or_partial_is_not_inferred_from_missing_answer(violation):
    p, a = packet_answer()
    a = deepcopy(a)
    if violation == "partial_number":
        a["cases"][0].update(right_visibility="PARTIAL")
    elif violation == "unreviewed":
        a["cases"][0].update(reviewed=False, right_score=None)
    elif violation == "wrong_hash":
        a["packet_sha256"] = "f" * 64
    else:
        a["cases"][0]["left_visibility"] = "prediction_absent"
    with pytest.raises(ValueError):
        review_visibility(p, a)
