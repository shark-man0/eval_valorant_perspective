"""Opt-in quarantine of version-unverified development map projections.

An outline fit measures image alignment, not client/map-version compatibility.
Reference retrieval dates, registration dates and recording filenames never
establish a build. Caller-supplied evidence hashes are traceability anchors,
not automatic verification of their content or Production qualification.
"""

from __future__ import annotations

import copy
import hashlib
import re
from typing import Any


def _sha(value: Any) -> bool:
    return isinstance(value, str) and re.fullmatch(r"[0-9a-f]{64}", value) is not None


def _build(value: Any) -> bool:
    return (isinstance(value, str) and 0 < len(value.strip()) <= 200
            and not re.search(r"unknown|unverified|unspecified|not supplied", value, re.I))


def gate_map_version(
    record: dict[str, Any], reference: dict[str, Any], reference_bytes: bytes, *,
    source_build_evidence: dict[str, Any] | None,
) -> dict[str, Any]:
    """Keep raw geometric output for inspection; withhold usable projection.

    Evidence is exact source/acquisition and exact asset. Different evidenced
    builds are conservatively incompatible; no patch-range inference. Even the
    same declared build does not qualify geometry or recorder ownership. Raw
    historical studies may retain their old outputs; downstream callers opting
    into this gate must use the returned top-level candidates and not the
    explicitly unverified diagnostic copy.
    """
    if (record.get("qualification") != "development_only"
            or record.get("ownership", {}).get("identity") != "UNKNOWN"
            or record.get("formal_self_position_fact") is not None):
        raise ValueError("UNKNOWN development record required")
    status, reason = "UNKNOWN", "map_or_source_build_unverified"
    if (not isinstance(reference_bytes, bytes) or not 0 < len(reference_bytes) <= 64*1024*1024
            or not _sha(reference.get("reference_sha256"))):
        reason = "reference_bytes_unavailable"
    elif hashlib.sha256(reference_bytes).hexdigest() != reference["reference_sha256"]:
        status, reason = "MISMATCH", "reference_content_mismatch"
    elif reference.get("map_id") != record.get("map_id"):
        status, reason = "MISMATCH", "reference_map_mismatch"
    elif source_build_evidence is not None:
        source = source_build_evidence
        if (not isinstance(source, dict) or not _sha(source.get("source_sha256"))
                or source["source_sha256"] != record.get("source_sha256")
                or not isinstance(source.get("acquisition_id"), str)
                or not source["acquisition_id"]
                or source["acquisition_id"] != record.get("acquisition_id")):
            reason = "source_build_evidence_binding_mismatch"
        elif (_build(source.get("client_build")) and _build(reference.get("client_build"))
              and _sha(source.get("evidence_sha256"))
              and _sha(reference.get("build_evidence_sha256"))):
            status, reason = (("SAME_EVIDENCED_BUILD", "same_declared_build_only")
                              if source["client_build"] == reference["client_build"]
                              else ("MISMATCH", "different_evidenced_builds"))
    result = copy.deepcopy(record)
    result["map_version_evidence"] = {
        "qualification": "development_only", "ownership": "UNKNOWN",
        "status": status, "reason": reason,
        "reference_sha256": reference.get("reference_sha256"),
        "reference_build": reference.get("client_build"),
        "reference_build_evidence_sha256": reference.get("build_evidence_sha256"),
        "source_evidence": copy.deepcopy(source_build_evidence),
        "qualified_geometry": False, "qualified_recorder_link": False,
    }
    if status == "SAME_EVIDENCED_BUILD":
        return result
    # Preserve a diagnostic copy with its own boundary; no automatic correction,
    # coordinate substitution, interpolation or semantic Zone propagation.
    fields = ("map_position_norm", "map_segment", "map_speed_norm_per_sec", "calibration",
              "zone_resolution", "development_region_candidate", "development_events")
    result["unverified_geometry_candidate"] = {
        **{key: copy.deepcopy(record.get(key)) for key in fields},
        "qualification": "development_only", "ownership": "UNKNOWN",
        "usable_as_version_compatible_position": False,
    }
    result.update(map_position_norm=None, map_segment=None, map_speed_norm_per_sec=None,
                  development_region_candidate=None, development_events=[],
                  calibration={"status": "calibration_required", "confidence": 0,
                               "diagnostics": [reason]},
                  zone_resolution={"zone_id": None, "candidate_zone_ids": [],
                                   "qualification": "development_only", "ownership": "UNKNOWN",
                                   "reason": reason})
    return result
