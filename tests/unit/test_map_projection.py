"""Development-only Map projection onto the canonical timeline by source time."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import pytest

from valorant_ai_coach.application.map_projection import (
    MapProjectionError,
    project_map_package,
)
from valorant_ai_coach.temporal.evidence import freeze_native_sample

SOURCE = "a" * 64
MAP_TIMELINE = "b" * 64


def _state(value: str, status: str = "OBSERVED") -> dict[str, Any]:
    return {"value": value, "status": status}


CANONICAL = "f" * 64


def _timeline(n: int = 8) -> dict[str, Any]:
    seconds = [
        {"timestamp": s, "camera_state": _state("SELF"), "life_state": _state("ALIVE"),
         "sample_refs": [f"{s:064x}"]}
        for s in range(n)
    ]
    seconds[3]["camera_state"] = _state("SPECTATOR")
    seconds[4]["life_state"] = _state("ALIVE", "INFERRED")
    return {
        "qualification": "development_only",
        "formal_outputs": 0,
        "source": {"source_sha256": SOURCE},
        "seconds": seconds,
    }


def _point(sec: float, **extra: Any) -> dict[str, Any]:
    tick = int(round(sec * 15360))
    sample = freeze_native_sample(
        {
            "source_id": "rec",
            "source_sha256": SOURCE,
            "acquisition_id": "map-acquisition",
            "native_epoch": "map-acquisition",
            "native_pts_tick": tick,
            "native_time_base": "1/15360",
            "acquired_frame_sha256": "c" * 64,
            "native_pixel_sha256": "d" * 64,
            "frame_size_px": [1920, 1080],
        }
    )
    return {
        "sample": sample,
        "kind": "selected",
        "map_id": "map-1",
        "map_reference_px": [10.0, 20.0],
        "zone_candidate": None,
        "callout_candidate": None,
        "qualified": False,
        "position_authority": False,
        **extra,
    }


def _report(rows: dict[int, list[dict[str, Any]]], n: int = 8) -> dict[str, Any]:
    return {
        "schema": "development_recorder_map_path_v1",
        "qualified": False,
        "formal_outputs": 0,
        "interpolated_samples": 0,
        "timeline_sha256": MAP_TIMELINE,
        "second_rows": [
            {"timestamp": s, "recorder_map_observations": rows.get(s, []),
             "trajectory_coverage": "native_edge_observed" if rows.get(s) else "UNKNOWN"}
            for s in range(n)
        ],
    }


def _package(tmp_path: Path, report: dict[str, Any]) -> tuple[Path, Path]:
    path = tmp_path / "map_recovered_PRIVATE.json"
    path.write_text(json.dumps(report), encoding="utf-8")
    receipt = {
        "schema": "development_map_library_entry_v1",
        "recording_id": "rec",
        "source_sha256": SOURCE,
        "formal_outputs": 0,
        "artifacts": {
            "bundle": {"sha256": MAP_TIMELINE},
            "recovered": {"sha256": hashlib.sha256(path.read_bytes()).hexdigest()},
            "standard": {"sha256": "1" * 64},
        },
    }
    receipt_path = tmp_path / "receipt_PRIVATE.json"
    receipt_path.write_text(json.dumps(receipt), encoding="utf-8")
    return receipt_path, path


def project(receipt: Path, path: Path, timeline: dict[str, Any], **kwargs: Any):
    kwargs.setdefault("timeline_sha256", CANONICAL)
    return project_map_package(receipt, path, timeline, **kwargs)


def test_map_seconds_land_on_canonical_own_live_seconds_only(tmp_path: Path) -> None:
    rows = {
        1: [_point(1.2), _point(1.8, zone_candidate="A Site")],
        2: [_point(2.9)],  # the next canonical sample (3) is a spectator: unbracketed
        3: [_point(3.4)],  # canonical view is a spectator: dropped
        4: [_point(4.0)],  # canonical life only inferred: dropped
        5: [_point(5.6)],
        7: [_point(7.1)],  # no canonical sample after it: unbracketed
    }
    receipt, path = _package(tmp_path, _report(rows))
    projection = project(receipt, path, _timeline())
    assert sorted(projection.rows) == [1, 5]
    assert projection.counts["map_seconds"] == 6
    assert projection.counts["dropped_canonical_view_not_self"] == 1
    assert projection.counts["dropped_canonical_not_alive"] == 1
    assert projection.counts["dropped_view_boundary_unbracketed"] == 2
    assert projection.counts["zone_candidate_seconds"] == 1
    item = projection.rows[1][0]
    assert item["qualified"] is False and item["position_authority"] is False
    assert item["source_time_sec"] == pytest.approx(1.2, abs=1e-4)
    assert [b["sec"] for b in item["canonical_bracket"]] == [1, 2]
    assert item["canonical_bracket"][1]["sample_refs"] == [f"{2:064x}"]
    assert item["map_sample_sha256"] == rows[1][0]["sample"]["sample_sha256"]
    out = projection.to_dict()
    assert out["formal_outputs"] == 0 and out["qualification"] == "development_only"


def test_both_sides_hashes_are_kept(tmp_path: Path) -> None:
    receipt, path = _package(tmp_path, _report({1: [_point(1.5)]}))
    out = project(receipt, path, _timeline()).to_dict()
    assert out["timeline_sha256"] == CANONICAL
    assert out["map_timeline_sha256"] == MAP_TIMELINE
    assert out["receipt_sha256"] == hashlib.sha256(receipt.read_bytes()).hexdigest()
    assert out["report_sha256"] == hashlib.sha256(path.read_bytes()).hexdigest()
    assert out["map_artifact_sha256"] == {
        "bundle": MAP_TIMELINE, "recovered": out["report_sha256"], "standard": "1" * 64,
    }
    with pytest.raises(MapProjectionError, match="canonical timeline SHA-256"):
        project(receipt, path, _timeline(), timeline_sha256="unknown")


def test_a_report_that_is_not_the_receipts_file_is_refused(tmp_path: Path) -> None:
    receipt, path = _package(tmp_path, _report({1: [_point(1.5)]}))
    path.write_text(json.dumps(_report({1: [_point(1.6)]})), encoding="utf-8")
    with pytest.raises(MapProjectionError, match="receipt's file"):
        project(receipt, path, _timeline())


def test_another_source_video_is_refused(tmp_path: Path) -> None:
    receipt, path = _package(tmp_path, _report({1: [_point(1.5)]}))
    timeline = _timeline()
    timeline["source"]["source_sha256"] = "e" * 64
    with pytest.raises(MapProjectionError, match="different sources"):
        project(receipt, path, timeline)


@pytest.mark.parametrize(
    "point",
    [
        _point(2.5),  # listed under second 1: its own time says second 2
        _point(1.5, qualified=True),
        _point(1.5, position_authority=True),
        _point(1.5, map_reference_px=[-1.0, 2.0]),
    ],
)
def test_an_observation_that_does_not_match_its_second_or_contract_is_refused(
    tmp_path: Path, point: dict[str, Any]
) -> None:
    receipt, path = _package(tmp_path, _report({1: [point]}))
    with pytest.raises(MapProjectionError, match="Exact unqualified"):
        project(receipt, path, _timeline())
