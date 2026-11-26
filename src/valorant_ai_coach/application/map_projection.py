"""Development-only projection of a published Map package onto the canonical timeline.

The Map library (#186) binds each package to the timeline the Map side measured on.
That timeline is a separate acquisition of the same source video: its native frames
have other sample hashes, so ``load_map_timeline`` (exact binding) connects nothing to
the canonical shared timeline. This module connects by source time instead:

* the package receipt, the Map report and the canonical timeline must name the same
  source video (SHA-256), and the report must be the receipt's file (SHA-256);
* each Map observation's own native sample must be a valid frozen sample of that
  source, and its presentation time must fall in the second it is listed under;
* the canonical timeline decides whose view it is: a second is kept only where the
  canonical timeline observed the recorder's own live view (camera ``SELF`` and life
  ``ALIVE``, both ``OBSERVED``). Other seconds are counted and dropped.

Nothing here is formal. Map observations stay ``qualified: false`` and
``position_authority: false``; no Fact or Event is produced. Promotion waits for the
Map side to define qualification (confidence, evidence, ownership).
"""

from __future__ import annotations

import hashlib
import json
import math
from collections import Counter
from collections.abc import Mapping
from dataclasses import dataclass, field
from fractions import Fraction
from pathlib import Path
from typing import Any

from valorant_ai_coach.temporal.evidence import freeze_native_sample, is_sha

PROJECTION_SCHEMA = "development_map_projection_v1"
RECEIPT_SCHEMA = "development_map_library_entry_v1"
REPORT_SCHEMA = "development_recorder_map_path_v1"


class MapProjectionError(ValueError):
    """The package, report and timeline do not describe the same verified recording."""


@dataclass
class MapProjection:
    recording_id: str
    source_sha256: str
    report_kind: str
    report_sha256: str
    rows: dict[int, list[dict[str, Any]]] = field(default_factory=dict)
    counts: Counter[str] = field(default_factory=Counter)

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": PROJECTION_SCHEMA,
            "qualification": "development_only",
            "formal_outputs": 0,
            "position_authority": False,
            "recording_id": self.recording_id,
            "source_sha256": self.source_sha256,
            "report_kind": self.report_kind,
            "report_sha256": self.report_sha256,
            "counts": dict(sorted(self.counts.items())),
            "seconds": {str(sec): rows for sec, rows in sorted(self.rows.items())},
        }


def _sha(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _observed(state: Mapping[str, Any] | None, value: str) -> bool:
    return (
        state is not None and state.get("value") == value and state.get("status") == "OBSERVED"
    )


def _coordinates(value: Any) -> bool:
    return (
        isinstance(value, list)
        and len(value) == 2
        and all(
            type(item) in (int, float) and math.isfinite(item) and item >= 0 for item in value
        )
    )


def project_map_package(
    receipt: Mapping[str, Any],
    report_path: Path,
    timeline: Mapping[str, Any],
    *,
    report_kind: str = "recovered",
) -> MapProjection:
    """Project one Map package onto the canonical timeline by source time."""
    artifacts = receipt.get("artifacts", {})
    if (
        receipt.get("schema") != RECEIPT_SCHEMA
        or receipt.get("formal_outputs") != 0
        or report_kind not in ("recovered", "standard")
        or report_kind not in artifacts
        or "bundle" not in artifacts
    ):
        raise MapProjectionError("A development Map library receipt is required")
    report_sha = _sha(report_path)
    if report_sha != artifacts[report_kind].get("sha256"):
        raise MapProjectionError("The Map report is not the receipt's file")
    source = timeline.get("source", {}).get("source_sha256")
    if (
        not is_sha(source)
        or receipt.get("source_sha256") != source
        or timeline.get("qualification") != "development_only"
        or timeline.get("formal_outputs") != 0
    ):
        raise MapProjectionError("The Map package and the timeline name different sources")
    report = json.loads(report_path.read_text(encoding="utf-8"))
    if (
        report.get("schema") != REPORT_SCHEMA
        or report.get("qualified") is not False
        or report.get("formal_outputs") != 0
        or report.get("interpolated_samples") != 0
        or report.get("timeline_sha256") != artifacts["bundle"].get("sha256")
    ):
        raise MapProjectionError("An unqualified Map report bound to the receipt is required")

    projection = MapProjection(
        recording_id=str(receipt.get("recording_id", "")),
        source_sha256=source,
        report_kind=report_kind,
        report_sha256=report_sha,
    )
    counts = projection.counts
    seconds = timeline["seconds"]
    for row in report.get("second_rows", []):
        observations = row.get("recorder_map_observations") or []
        if not observations:
            continue
        second = row.get("timestamp")
        if type(second) is not int or not 0 <= second < len(seconds):
            raise MapProjectionError("Map second outside the timeline")
        kept: list[dict[str, Any]] = []
        for point in observations:
            sample = freeze_native_sample(point.get("sample", {}))
            at = Fraction(sample["native_pts_tick"]) * Fraction(sample["native_time_base"])
            if (
                sample["source_sha256"] != source
                or math.floor(at) != second
                or point.get("qualified") is not False
                or point.get("position_authority") is not False
                or not isinstance(point.get("map_id"), str)
                or not point["map_id"]
                or not _coordinates(point.get("map_reference_px"))
            ):
                raise MapProjectionError("Exact unqualified Map observation required")
            kept.append(
                {
                    "map_id": point["map_id"],
                    "map_reference_px": list(point["map_reference_px"]),
                    "kind": point.get("kind"),
                    "zone_candidate": point.get("zone_candidate"),
                    "callout_candidate": point.get("callout_candidate"),
                    "source_time_sec": float(at),
                    "native_pts_tick": sample["native_pts_tick"],
                    "native_time_base": sample["native_time_base"],
                    "map_sample_sha256": point["sample"].get("sample_sha256"),
                    "qualified": False,
                    "position_authority": False,
                }
            )
        counts["map_seconds"] += 1
        canonical = seconds[second]
        if not _observed(canonical.get("camera_state"), "SELF"):
            counts["dropped_canonical_view_not_self"] += 1
            continue
        if not _observed(canonical.get("life_state"), "ALIVE"):
            counts["dropped_canonical_not_alive"] += 1
            continue
        projection.rows[second] = kept
        counts["projected_seconds"] += 1
        counts["projected_observations"] += len(kept)
        if any(item["zone_candidate"] for item in kept):
            counts["zone_candidate_seconds"] += 1
        if any(item["callout_candidate"] for item in kept):
            counts["callout_candidate_seconds"] += 1
        if row.get("trajectory_coverage") == "native_edge_observed":
            counts["native_edge_seconds"] += 1
    return projection
