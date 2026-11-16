from __future__ import annotations

import hashlib

import numpy as np
import pytest

from valorant_ai_coach.temporal.evidence import digest, freeze_native_sample
from valorant_ai_coach.temporal.map_recorder_path import (
    ReferenceZones,
    build_recorder_paths,
    join_recorder_seconds,
    project_recorder_witness,
)


def test_native_path_uses_exact_transform_and_leaves_missing_seconds_unknown():
    reference_sha = "c" * 64
    asset = {"lotus": reference_sha}
    zones = ReferenceZones(
        "lotus", reference_sha, {"site": [(0, 0), (45, 0), (45, 45), (0, 45)]},
    )
    points = []
    for i in range(4):
        image = np.full((60, 90, 3), i, dtype=np.uint8)
        sample = freeze_native_sample({
            "source_id": "s", "source_sha256": "a"*64, "acquisition_id": "e",
            "native_epoch": "e", "native_pts_tick": i + 3, "native_time_base": "1/10",
            "acquired_frame_sha256": "b"*64, "frame_size_px": [90, 60],
            "native_pixel_sha256": hashlib.sha256(image.tobytes()).hexdigest(),
        })
        pool = [{"center_frame_px": [20+i, 20]}]
        proposal = {
            "contract": "development_map_recorder_selection_v1",
            "selection_status": "RESEARCH_SELECTED" if i == 2 else "ABSTAIN",
            "sample_sha256": sample["sample_sha256"], "ordered_candidate_pool_digest": digest(pool),
            "support_count": i+1, "support_candidate_index": 0,
            "support_center_frame_px": [20+i, 20],
            "research_candidate_index": 0 if i == 2 else None,
            "qualified": False, "position_authority": False,
        }
        alignment = {
            "map_name_candidates": [{"map_id": "lotus", "qualified": False,
                "evidence": "public_reference_feature_alignment", "position_authority": False,
                "reference_to_roi_homography_candidate": [[1, 0, 1], [0, 1, 1], [0, 0, 1]]}],
            "marker_transform_qualified": False, "roi_pixel_bounds": [10, 10, 50, 50],
            "roi_pixel_sha256": hashlib.sha256(image[10:50,10:50].tobytes()).hexdigest(),
        }
        projected = project_recorder_witness(image, sample, pool, proposal, alignment,
                                              reference_sha256s=asset)
        assert projected is not None
        assert projected["map_reference_px"] == [9+i, 9]
        assert project_recorder_witness(image, sample, pool, proposal,
            {**alignment, "roi_pixel_sha256": "d"*64}, reference_sha256s=asset) is None
        points.append(projected)
    result = build_recorder_paths(points, zones=[zones])
    segment, = result["segments"]
    assert [r["zone_candidate"] for r in segment] == ["site"]*3
    assert result["interpolated_samples"] == 0 and not result["qualified"]
    broken_path = build_recorder_paths([points[0], None, *points[2:]])
    assert broken_path["segments"][0][0]["kind"] == "selected"
    refs = [r["sample"]["sample_sha256"] for r in segment]
    timeline = {"seconds": [{"timestamp": 0, "sample_refs": refs},
                            {"timestamp": 1, "sample_refs": []}]}
    joined = join_recorder_seconds(result, timeline)
    assert joined[0]["recorder_map_observations"] == segment
    assert joined[1]["coverage"] == "UNKNOWN"
    with pytest.raises(ValueError, match="absent from"):
        join_recorder_seconds(result, {"seconds": timeline["seconds"][1:]})


def test_path_edges_do_not_join_different_knowledge_witness_anchors():
    rows = []
    for i, anchor in enumerate(("x", "x", "y")):
        sample = freeze_native_sample({
            "source_id": "s", "source_sha256": "a"*64,
            "acquisition_id": "e", "native_epoch": "e",
            "native_pts_tick": i + 3, "native_time_base": "1/10",
            "acquired_frame_sha256": "b"*64, "frame_size_px": [90, 60],
            "native_pixel_sha256": "c"*64,
        })
        rows.append({
            "sample": sample, "support_count": i + 1, "kind": "selected",
            "map_id": "lotus", "reference_sha256": "d"*64,
            "selection_method": "knowledge_agent_uuid", "track_anchor": anchor,
        })
    assert [len(seg) for seg in build_recorder_paths(rows)["segments"]] == [2, 1]
