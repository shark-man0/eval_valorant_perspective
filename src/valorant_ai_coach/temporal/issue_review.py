"""Bound issue/history sidecars and before/after context for the existing viewer."""

from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import Any

from .comparison import DOMAINS, load_manifest, load_result
from .issue_analysis import VERSION as ANALYSIS_VERSION
from .replay import file_sha, read_json

HISTORY_VERSION = "development_timeline_improvement_history_v1"
HISTORY_FIELDS = {
    "id",
    "problem",
    "cause_hypothesis",
    "change",
    "inputs",
    "gained_controls",
    "lost_controls",
    "unverified_changes",
    "decision",
    "next",
}


def load_review_sidecars(manifest: Path, entries: dict[str, dict[str, Any]]) -> dict[str, Any]:
    """Optional additions; existing desktop manifest calls continue unchanged."""
    data = read_json(manifest)
    result: dict[str, Any] = {"analysis": None, "history": []}
    for name in ("issue_analysis", "improvement_history"):
        binding = data.get(name)
        if binding is None:
            continue
        path = Path(binding["path"])
        if not path.is_absolute():
            path = manifest.parent / path
        if file_sha(path) != binding["sha256"]:
            raise ValueError("Review sidecar digest mismatch")
        sidecar = read_json(path)
        if sidecar.get("formal_outputs") != 0:
            raise ValueError("Unqualified review sidecar required")
        if name == "issue_analysis":
            if sidecar.get("version") != ANALYSIS_VERSION:
                raise ValueError("Known issue analysis version required")
            baseline = Path(sidecar["baseline_manifest"])
            if file_sha(baseline) != sidecar["manifest_sha256"]:
                raise ValueError("Analysis baseline manifest changed")
            for original in load_manifest(baseline):
                current = entries[original["id"]]
                # New primary selections are allowed; the historical cohort stays explicit.
                for key in ("bundle_sha256", "policy_sha256", "conditions", "compare_to"):
                    if current.get(key) != original.get(key):
                        raise ValueError("Analysis baseline cohort conditions changed")
            # A baseline analysis remains valid when additional result versions are added.
            for identifier, original in sidecar["result_bindings"].items():
                entry = entries[identifier]
                if any(entry[k] != original[k] for k in ("bundle_sha256", "policy_sha256")):
                    raise ValueError("Issue analysis baseline changed")
            for row in sidecar["records"]:
                if (
                    row["bundle_sha256"] != entries[row["result_id"]]["bundle_sha256"]
                    or row.get("is_error") is not None
                    or row.get("formal_outputs") != 0
                ):
                    raise ValueError("Bound unlabelled issue required")
            if len(sidecar["records"]) != sidecar["intervals"]:
                raise ValueError("Issue denominator mismatch")
            result["analysis"] = sidecar
        else:
            if sidecar.get("version") != HISTORY_VERSION:
                raise ValueError("Known improvement history version required")
            if any(not set(r) >= HISTORY_FIELDS for r in sidecar["records"]):
                raise ValueError("Complete improvement history fields required")
            result["history"] = sidecar["records"]
    return result


def issue_page(
    review: dict[str, Any],
    *,
    cause: str = "",
    result_id: str = "",
    page: int = 0,
    page_size: int = 100,
) -> dict[str, Any]:
    if page < 0 or not 1 <= page_size <= 100:
        raise ValueError("Bounded issue pagination required")
    analysis = review["analysis"]
    if analysis is None:
        return {"total": 0, "records": [], "representatives": []}
    rows = [
        r
        for r in analysis["records"]
        if (not result_id or r["result_id"] == result_id)
        and (not cause or any(c["code"] == cause for c in r["causes"]))
    ]
    rows.sort(key=lambda r: (-r["priority"]["score"], r["issue_id"]))
    compact = []
    for row in rows[page * page_size : (page + 1) * page_size]:
        copy = {k: v for k, v in row.items() if k not in {"sample_refs", "evidence_refs"}}
        copy["sample_count"] = len(row["sample_refs"])
        copy["evidence_count"] = len(row["evidence_refs"])
        copy["representative"] = row["issue_id"] in analysis["representatives"]
        compact.append(copy)
    return {
        "total": len(rows),
        "records": compact,
        "baseline_manifest_sha256": analysis["manifest_sha256"],
        "baseline_result_ids": sorted(analysis["result_bindings"]),
        "scope": "frozen_baseline_cohort_not_current_primary_errors",
        "cause_counts": analysis["cause_counts_multiple_labels"],
        "representatives": analysis["representatives"],
        "formal_outputs": 0,
    }


def presentation_catalog(catalog: dict[str, Any]) -> dict[str, Any]:
    """Keep original downloadable evidence intact; omit unused large UI arrays."""
    result = deepcopy(catalog)
    for row in result["results"]:
        for issue in row.get("review_intervals", []):
            for key in ("evidence_refs", "sample_refs"):
                issue[key + "_count"] = len(issue.pop(key))
    return result


def context_window(
    entries: dict[str, dict[str, Any]], result_id: str, second: int
) -> dict[str, Any]:
    """Recheck receipts and native bindings; never align unlike Source clocks."""
    entry = entries[result_id]
    bundle = load_result(entry)
    if not 0 <= second < len(bundle["seconds"]):
        raise ValueError("Second outside recording")
    paired = entry.get("compare_to")
    current_child = next(
        (
            e["id"]
            for e in entries.values()
            if e.get("compare_to") == result_id and e.get("primary")
        ),
        None,
    )
    # Historical issues target a baseline that may itself have an older parent.
    # Prefer its current primary revision; selecting the revision still shows its parent.
    if current_child is not None and not entry.get("primary"):
        paired = current_child
    elif not paired:
        paired = next((e["id"] for e in entries.values() if e.get("compare_to") == result_id), None)
    versions = []
    for current in [entry, entries[paired]] if paired else [entry]:
        value = bundle if current is entry else load_result(current)
        if value["source"] != bundle["source"] or value["recording"] != bundle["recording"]:
            raise ValueError("Context comparison requires the same Source recording clock")
        rows = value["seconds"][max(0, second - 2) : second + 3]
        versions.append(
            {
                "id": current["id"],
                "bundle_sha256": current["bundle_sha256"],
                "conditions": current["conditions"],
                "configuration": value["engine_configuration"],
                "seconds": rows,
                "native_frames": {
                    s: value["native_frames"][s] for row in rows for s in row["sample_refs"]
                },
                "observations": {
                    s: value["observations"][s] for row in rows for s in row["evidence_refs"]
                },
                "domains": DOMAINS,
            }
        )
    return {"selected_second": second, "versions": versions, "formal_outputs": 0}
