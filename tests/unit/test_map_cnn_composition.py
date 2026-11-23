from copy import deepcopy

import pytest

from scripts.map_learning.compose_paths import compose_paths
from valorant_ai_coach.temporal.evidence import freeze_native_sample
from valorant_ai_coach.temporal.map_recorder_path import VERSION


def test_cnn_complement_keeps_reference_and_requires_unresolved_exact_portrait():
    def point(i, *, texture="registered"):
        return {
            "sample": freeze_native_sample(
                {
                    "source_id": "test",
                    "source_sha256": "a" * 64,
                    "acquisition_id": "a",
                    "native_epoch": "a",
                    "native_pts_tick": i,
                    "native_time_base": "1/5",
                    "acquired_frame_sha256": "b" * 64,
                    "native_pixel_sha256": "c" * 64,
                    "frame_size_px": [160, 100],
                }
            ),
            "map_id": "map",
            "reference_sha256": texture,
            "map_reference_px": [i, i],
            "fit_residual_p95_reference_px": 2,
            "track_anchor": "witness",
            "support_count": i + 1,
            "kind": "selected",
            "qualified": False,
            "position_authority": False,
        }

    points = [point(0), point(1), point(2), point(3, texture="other")]
    ids = [p["sample"]["sample_sha256"] for p in points]
    reference = {
        "schema": VERSION,
        "qualified": False,
        "formal_outputs": 0,
        "interpolated_samples": 0,
        "timeline_sha256": "timeline",
        "frame_manifest_sha256": "manifest",
        "map_catalog_fingerprint": "catalog",
        "zone_catalog_sha256": None,
        "recording_map_uuid": "map",
        "recording_agent_uuid_binding": {
            "source_sha256": "a" * 64,
            "uuid": "agent",
            "qualified": False,
        },
        "segments": [[points[0]]],
        "comparison_evidence": {
            "operable_sample_refs": ids,
            "unresolved_portrait_sample_refs": [ids[1], ids[3]],
        },
    }
    learned = {**reference, "experimental_direct_tracker": True, "segments": [points]}
    timeline = {"source": {"source_sha256": "a" * 64},
                "seconds": [{"timestamp": 0, "sample_refs": ids}]}
    composed = compose_paths(reference, learned, timeline, "timeline")
    first, second = composed["segments"]
    assert first == [points[0]]
    (added,) = second
    assert added["sample"] == points[1]["sample"]
    assert added["track_anchor"] != points[0]["track_anchor"]
    assert composed["formal_outputs"] == composed["interpolated_samples"] == 0
    assert composed["new_cnn_native_positions"] == 1
    assert composed["operable_coverage"]["operable_seconds_with_native_edge"] == 0
    linked = compose_paths(reference, learned, timeline, "timeline", link_corroborated=True)
    assert linked["segments"] == composed["segments"]
    assert linked["operable_coverage"]["operable_seconds_with_native_edge"] == 1
    assert linked["corroborated_native_edges"][0]["overlap_sample_ref"] == ids[0]
    displaced = deepcopy(learned)
    displaced["segments"][0][0]["map_reference_px"] = [4, 4]
    rejected = compose_paths(reference, displaced, timeline, "timeline", link_corroborated=True)
    assert rejected["corroborated_native_edges"] == []
    differently_observed = deepcopy(learned)
    differently_observed["comparison_evidence"]["operable_sample_refs"] = ids[1:]
    with pytest.raises(ValueError, match="view evidence"):
        compose_paths(reference, differently_observed, timeline, "timeline")

    primary = {**reference, "experimental_direct_tracker": True,
               "experimental_model_receipts": {"marker": "a" * 64, "portrait": "b" * 64}}
    backup = {**displaced, "experimental_model_receipts": {
        "marker": "c" * 64, "portrait": "b" * 64,
    }}
    companion = compose_paths(primary, backup, timeline, "timeline", marker_companion=True)
    assert companion["segments"][0] == [points[0]]
    assert companion["new_cnn_native_positions"] == 1
    weak = deepcopy(backup)
    weak["segments"][0][1]["support_count"] = 1
    assert compose_paths(primary, weak, timeline, "timeline", marker_companion=True)[
        "new_cnn_native_positions"
    ] == 0
    with pytest.raises(ValueError, match="change only"):
        compose_paths(primary, learned, timeline, "timeline", marker_companion=True)

    unbound = {**reference, "recording_agent_uuid_binding": None, "segments": []}
    unbound_learned = {**unbound, "experimental_direct_tracker": True}
    unknown = compose_paths(unbound, unbound_learned, timeline, "timeline")
    assert unknown["second_rows"][0]["coverage"] == "UNKNOWN"
    with pytest.raises(ValueError, match="Agent binding"):
        compose_paths({**unbound, "segments": [[points[0]]]}, unbound_learned,
                      timeline, "timeline")
