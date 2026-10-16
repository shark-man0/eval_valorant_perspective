"""Metadata export cannot imply unseen data or publish private annotations."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.diagnostics.export_pts_exposure_inventory import SOURCES, export, frame_records

SOURCE = SOURCES["supplemental_001927"]


def record(**updates):
    return {
        "pts_ticks": 460800,
        "pixel_sha256": "a" * 64,
        "encoded_sha256": "b" * 64,
        "source_epoch": "c" * 32,
        **updates,
    }


def test_frame_export_filters_images_annotations_and_local_paths():
    raw = record(
        path="/private/person/frame.png",
        manual_label="PRIVATE_GT",
        human_answer="PRIVATE_REVIEW",
        value="PRIVATE_PREDICTION",
    )
    got = list(frame_records(raw, SOURCE))
    encoded = json.dumps(got)
    assert "/private/" not in encoded and "PRIVATE_" not in encoded
    assert got[0]["pts_ticks"] == 460800
    assert got[0]["source_identity_inherited"] is True


@pytest.mark.parametrize(
    "change",
    [
        {"pts_ticks": True},
        {"pts_ticks": 1.5},
        {"pts_ticks": -1},
        {"pixel_sha256": "not-a-hash"},
        {"source_epoch": "/private/person"},
        {"source_video_sha256": "d" * 64},
        {"time_base": "1/60"},
    ],
)
def test_invalid_or_mismatched_identity_rejected(change):
    with pytest.raises(ValueError):
        list(frame_records(record(**change), SOURCE))


def test_nested_geometry_preserves_actual_frame_identity():
    nested = {"rows": [{"requested_sec": 30, "source_frame": record()}]}
    assert len(list(frame_records(nested, SOURCE))) == 1
    assert list(frame_records({"requested_sec": 30}, SOURCE)) == []


def test_snapshot_never_certifies_unviewed_or_holdout_and_is_immutable(tmp_path: Path):
    root = tmp_path / "work/independent-source-001927"
    root.mkdir(parents=True)
    (root / "source-manifest.json").write_text(json.dumps([record()]), encoding="utf-8")
    (root / "split-plan.json").write_text(
        json.dumps(
            {
                "partitions": {"development_geometry_only": [0, 180]},
                "evaluation_discovery_started": False,
                "private_note": "SECRET",
            }
        ),
        encoding="utf-8",
    )
    output = tmp_path / "exported"
    summary = export(tmp_path, output)
    assert summary["source_records"] == summary["unique_source_pts"] == 1
    assert summary["unlisted_frames_certified_unviewed"] is False
    assert summary["independent_holdout_certified"] is False
    snapshots = (output / "historical_split_plans.json").read_text(encoding="utf-8")
    assert "SECRET" not in snapshots and "evaluation_discovery_started" not in snapshots
    assert "historical_plan_not_current_exposure_certification" in snapshots
    frames = [
        json.loads(x) for x in (output / "frames.jsonl").read_text(encoding="utf-8").splitlines()
    ]
    assert frames[0]["new_blind_holdout_status"] == "not_certified"
    assert frames[0]["visual_review_status"] == "not_inferred_from_manifest"
    with pytest.raises(ValueError, match="must not exist"):
        export(tmp_path, output)
