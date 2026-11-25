import numpy as np
import pytest

from scripts.map_learning.bracket_portraits import (
    _corroborated_groups,
    _strong_isolated,
    find_brackets,
)
from scripts.map_learning.portrait_similarity import SCHEMA, read_metric, region_similarity
from valorant_ai_coach.temporal.evidence import digest, freeze_native_sample
from valorant_ai_coach.temporal.replay import write_private


def _replay():
    frames = {}
    observations = {}
    for i in range(7):
        sample = freeze_native_sample(
            {
                "source_id": "fixture",
                "source_sha256": "a" * 64,
                "acquisition_id": "a",
                "native_epoch": "a",
                "native_time_base": "1/5",
                "native_pts_tick": i,
                "acquired_frame_sha256": "b" * 64,
                "native_pixel_sha256": f"{i:064x}",
                "frame_size_px": [1920, 1080],
            }
        )
        row = {
            "sample": sample,
            "signals": ["owner_hud"],
            "context": {"stream_kind": "camera_panel"},
            "producer_fingerprint": "c" * 64,
            "raw": {
                "qualified": False,
                "formal_outputs": 0,
                "camera_panel": {
                    "own_ability_bar_score": 0.9,
                    "label": {"checked": True, "state": "ABSENT"},
                },
            },
        }
        ref = digest(row)
        observations[ref] = {**row, "observation_id": ref}
        frames[sample["sample_sha256"]] = {
            "sample": sample,
            "observation_ids": [ref],
            "round": {"value": "ACTIVE"},
            "round_token": "r",
            "camera": {"value": "SELF", "evidence_ids": [ref]},
            "life": {"value": "ALIVE"},
            "continuity": {"carry_allowed": True},
        }
    refs = list(frames)
    left, *middle, right = refs

    def point(key):
        return {
            "sample": frames[key]["sample"],
            "kind": "selected",
            "map_id": "map",
            "reference_sha256": "d" * 64,
        }

    incumbent = {
        "segments": [[point(left)], [point(right)]],
        "second_rows": [
            {"recorder_map_observations": [point(left)]},
            {"recorder_map_observations": []},
            {"recorder_map_observations": [point(right)]},
        ],
    }
    timeline = {
        "native_frames": frames,
        "observations": observations,
        "seconds": [{"sample_refs": refs} for refs in ([left], middle, [right])],
    }
    return timeline, incumbent, refs


def test_bracket_requires_wholly_operable_vacancy_and_keeps_measurements():
    timeline, incumbent, refs = _replay()
    (bracket,) = find_brackets(timeline, incumbent, set(refs), set(refs[1:6]))
    assert (bracket.left, bracket.targets, bracket.right) == (refs[0], tuple(refs[1:6]), refs[6])
    assert not find_brackets(timeline, incumbent, set(refs) - {refs[4]}, set(refs))
    incumbent["second_rows"][1]["recorder_map_observations"] = [{"kind": "measured_witness"}]
    assert not find_brackets(timeline, incumbent, set(refs), set(refs))


@pytest.mark.parametrize(
    "change",
    [
        {"camera": {"value": "SPECTATOR"}},
        {"life": {"value": "DEAD"}},
        {"round_token": "new"},
        {"round": {"value": "BUY"}},
        {"continuity": {"carry_allowed": True, "confirmed_cut": True}},
        {"viewed_identity": {"agent_signature_relation": "DIFFERENT"}},
    ],
)
def test_current_self_view_or_lifecycle_boundary_breaks_bracket(change):
    timeline, incumbent, refs = _replay()
    timeline["native_frames"][refs[3]].update(change)
    assert not find_brackets(timeline, incumbent, set(refs), set(refs))


def test_local_metric_does_not_reuse_a_physical_evaluation_match(tmp_path):
    p = tmp_path / "metric.json"
    write_private(
        p,
        {
            "schema": SCHEMA,
            "formal_outputs": 0,
            "training_receipt_sha256": "a" * 64,
            "training_physical_matches": ["a", "b"],
            "weights": [0.2] * 5,
        },
    )
    w, _ = read_metric(p, "c")
    feature = np.arange(243, dtype=np.float32)
    assert region_similarity(feature, feature) @ w == pytest.approx(1)
    assert region_similarity(feature, -feature) @ w == pytest.approx(-1)
    assert region_similarity(feature, np.zeros_like(feature)) @ w == 0
    with pytest.raises(ValueError, match="disjoint"):
        read_metric(p, "a")


def test_weak_neighbor_is_used_only_next_to_a_strong_current_portrait():
    group = [
        (str(i), {"strong_current_portrait": is_strong}, {})
        for i, is_strong in enumerate([False, False, True, False, False, False, True, False])
    ]
    kept = [tuple(item[0] for item in part) for part in _corroborated_groups(group)]
    assert kept == [("1", "2", "3"), ("5", "6", "7")]
    assert list(_corroborated_groups(group[:2])) == []
    assert list(_corroborated_groups(group[2:3])) == []


def test_isolated_point_needs_current_geometry_and_two_matching_witnesses():
    timeline, _, refs = _replay()
    points = [
        {"sample": timeline["native_frames"][key]["sample"], "map_reference_px": [x, 0]}
        for key, x in zip(refs[::3], (0, 20, 40), strict=True)
    ]
    left, current, right = points
    measurements = {
        "warm_sectors": 14,
        "opposite_pairs": 6,
        "rival_sectors": 1,
        "external_target_score": 0.75,
        "external_agent_margin": 0.08,
        "anchor_similarities": [0.87, 0.85],
    }
    assert _strong_isolated(left, current, right, measurements)
    assert not _strong_isolated(
        left,
        current,
        right,
        {
            **measurements,
            "anchor_similarities": [0.9, 0.8],
        },
    )
    assert not _strong_isolated(
        left, {**current, "map_reference_px": [20, 40]}, right, measurements
    )
