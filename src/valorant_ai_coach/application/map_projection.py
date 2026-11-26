"""Development-only projection of a published Map package onto the canonical timeline.

The Map library (#186) binds each package to the timeline the Map side measured on.
That timeline is a separate acquisition of the same source video: its native frames
have other sample hashes, so ``load_map_timeline`` (exact binding) connects nothing to
the canonical shared timeline. This module connects by source time instead:

* the package receipt, the Map report and the canonical timeline must name the same
  source video (SHA-256), and the report must be the receipt's file (SHA-256);
* each Map observation's own native sample must be a valid frozen sample of that
  source, and its presentation time must fall in the second it is listed under;
* the canonical timeline decides whose view it is. Its sample of second ``s`` is
  taken at ``s``, so an observation at ``s <= t < s + 1`` lies between the samples of
  seconds ``s`` and ``s + 1``. It is kept only when both samples observed the
  recorder's own live view (camera ``SELF`` and life ``ALIVE``, both ``OBSERVED``):
  a death, a switch to spectating or a return inside that interval would leave one
  of them unobserved or changed. Other observations are counted and dropped.

The projection keeps the hashes of both sides: the receipt and every artifact it
names (Map evidence), the Map report and the Map-side timeline, the canonical
timeline it was projected onto, and per observation the Map sample and the two
canonical samples that bracket it.

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
    receipt_sha256: str
    map_artifact_sha256: dict[str, str]
    map_timeline_sha256: str
    timeline_sha256: str
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
            "receipt_sha256": self.receipt_sha256,
            "map_artifact_sha256": dict(sorted(self.map_artifact_sha256.items())),
            "map_timeline_sha256": self.map_timeline_sha256,
            "timeline_sha256": self.timeline_sha256,
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
    receipt_path: Path,
    report_path: Path,
    timeline: Mapping[str, Any],
    *,
    timeline_sha256: str,
    report_kind: str = "recovered",
) -> MapProjection:
    """Project one Map package onto the canonical timeline by source time.

    ``timeline_sha256`` names the canonical timeline the bundle was read from.
    """
    if not is_sha(timeline_sha256):
        raise MapProjectionError("The canonical timeline SHA-256 is required")
    receipt_sha = _sha(receipt_path)
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
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
        receipt_sha256=receipt_sha,
        map_artifact_sha256={
            name: str(item.get("sha256"))
            for name, item in artifacts.items()
            if isinstance(item, Mapping) and is_sha(item.get("sha256"))
        },
        map_timeline_sha256=str(report["timeline_sha256"]),
        timeline_sha256=timeline_sha256,
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
            try:
                sample = freeze_native_sample(point.get("sample", {}))
            except (ValueError, KeyError, TypeError) as exc:
                raise MapProjectionError("Exact unqualified Map observation required") from exc
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
                    "map_sample_sha256": sample["sample_sha256"],
                    "map_acquired_frame_sha256": sample["acquired_frame_sha256"],
                    "map_native_pixel_sha256": sample["native_pixel_sha256"],
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
        # The canonical samples of s and s + 1 bracket every observation in s.
        following = seconds[second + 1] if second + 1 < len(seconds) else None
        if following is None or not (
            _observed(following.get("camera_state"), "SELF")
            and _observed(following.get("life_state"), "ALIVE")
        ):
            counts["dropped_view_boundary_unbracketed"] += 1
            continue
        bracket = [
            {"sec": item["timestamp"], "sample_refs": list(item.get("sample_refs", []))}
            for item in (canonical, following)
        ]
        for item in kept:
            item["canonical_bracket"] = bracket
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
