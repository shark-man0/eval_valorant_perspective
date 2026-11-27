"""Independent, read-only regression audit of development Map observation portfolios."""

from __future__ import annotations

import argparse
import math
from collections import Counter
from pathlib import Path

from valorant_ai_coach.temporal.evidence import digest, native_time
from valorant_ai_coach.temporal.map_recorder_path import measured_native_edges
from valorant_ai_coach.temporal.replay import file_sha, read_json, write_private


def bound(record, parent):
    path = Path(record["path"])
    if not path.is_absolute():
        path = parent / path
    if file_sha(path) != record["sha256"]:
        raise ValueError("An audit input changed after the cohort was frozen")
    data = read_json(path)
    if data.get("formal_outputs") != 0:
        raise ValueError("Only development observations may enter this audit")
    return data


def points(report):
    rows = {}
    for segment in report["segments"]:
        for point in segment:
            key = point["sample"]["sample_sha256"]
            if key in rows:
                raise ValueError("Duplicate native observation in the Map report")
            rows[key] = point
    return rows


def screen_center(report, key):
    proposal = report.get("multi_marker_replay", {}).get("added_evidence", {}).get(key, {}).get(
        "proposal")
    return proposal[1:3] if proposal is not None else None


def trajectory_flags(report):
    """Extract suspicious measured edges without assigning semantic identity."""
    native = points(report)
    evidence = report.get("multi_marker_replay", {}).get("added_evidence", {})
    flags = []
    edges = measured_native_edges(report) | {
        (a["sample"]["sample_sha256"], b["sample"]["sample_sha256"])
        for segment in report["segments"] for a, b in zip(segment, segment[1:], strict=False)
    }
    for a, b in sorted(edges):
        first, second = native[a], native[b]
        dt = float(native_time(second["sample"]) - native_time(first["sample"]))
        reasons = []
        same_geometry = all(first.get(k) == second.get(k)
                            for k in ("map_id", "reference_sha256"))
        if not same_geometry:
            reasons.append("map_or_reference_change")
        if dt <= 0 or dt > .25:
            reasons.append("noncontiguous_observed_edge")
        if dt > 0 and same_geometry:
            displacement = math.dist(first["map_reference_px"], second["map_reference_px"])
            if displacement > 6 + 60 * dt:
                reasons.append("large_reference_displacement")
        old_track, new_track = (evidence.get(k, {}).get("track") for k in (a, b))
        if old_track is not None and new_track is not None and old_track != new_track:
            reasons.append("track_id_changed")
        if reasons:
            flags.append({"samples": [a, b], "reasons": reasons})
    return flags


def measurement_agreement(report):
    """Agreement between two measurements is kept outside semantic accuracy."""
    centers, residuals = [], []
    selected = points(report)
    for key, evidence in report.get("multi_marker_replay", {}).get("added_evidence", {}).items():
        point = selected.get(key)
        if point is None:
            raise ValueError("Tracker evidence references an absent observation")
        center = screen_center(report, key)
        outline = evidence.get("current_enclosing_outline")
        if center is not None and outline is not None:
            centers.append(math.dist(center, outline["center_frame_px"]))
        residual = point.get("fit_residual_p95_reference_px")
        if type(residual) in (int, float) and math.isfinite(residual):
            residuals.append(residual)
    return {"native_center_agreement_px": centers,
            "reported_registration_residual_reference_px": residuals,
            "independent_owner_accuracy": None, "absolute_map_error": None}


def review_metrics(reviews, reports):
    """Human and AI results retain distinct, explicit reviewed denominators."""
    totals = {}
    seen = set()
    for review in reviews:
        origin = review["reviewer"]
        if origin not in {"HUMAN", "AI_VISUAL"}:
            raise ValueError("An explicit HUMAN or AI_VISUAL reviewer is required")
        index, key = review["index"], review["sample_ref"]
        identity = origin, index, key
        if identity in seen:
            raise ValueError("Duplicate review in a provenance stratum")
        seen.add(identity)
        report, checksum = reports[index]
        if review["report_sha256"] != checksum:
            raise ValueError("The review describes another recognition generation")
        point = points(report).get(key)
        if point is None:
            raise ValueError("Review is outside the frozen candidate observations")
        role = review["role"]
        if role not in {"SELF", "NON_SELF", "UNKNOWN"}:
            raise ValueError("Unknown reviewer role label")
        row = totals.setdefault(origin, {"reviewed": 0, "self": 0, "non_self": 0, "unknown": 0,
                                          "center_errors_px": [], "map_errors_reference_px": []})
        row["reviewed"] += 1
        row[role.lower()] += 1
        for field in ("center_frame_px", "map_reference_px"):
            if review.get(field) is None or role != "SELF":
                continue
            expected = review[field]
            if (len(expected) != 2
                    or any(type(v) not in (int, float) or not math.isfinite(v) for v in expected)):
                raise ValueError("Reviewed coordinates must be finite")
            if field == "center_frame_px":
                predicted = screen_center(report, key)
                if predicted is not None:
                    row["center_errors_px"].append(math.dist(predicted, expected))
            else:
                if (review.get("map_id") != point["map_id"]
                        or review.get("reference_sha256") != point["reference_sha256"]):
                    raise ValueError("Absolute Map error requires the identical reference geometry")
                row["map_errors_reference_px"].append(math.dist(point[field], expected))
    for row in totals.values():
        known = row["self"] + row["non_self"]
        row["wrong_selection_fraction_on_known_reviews"] = (
            row["non_self"] / known if known else None
        )
    return totals


def audit(before_path, after_path, reviews=()):
    old, new = (read_json(p) for p in (before_path, after_path))
    if any(doc.get("formal_outputs") != 0 for doc in (old, new)):
        raise ValueError("Development portfolios required")
    before = {r["index"]: r for r in old["recordings"]}
    after = {r["index"]: r for r in new["recordings"]}
    if len(before) != len(old["recordings"]) or len(after) != len(new["recordings"]):
        raise ValueError("The cohort contains duplicate recording indices")
    if before.keys() != after.keys():
        raise ValueError("Regression requires the identical recording cohort")
    cases, rows, bound_reports = [], [], {}
    reasons = Counter()
    for index in sorted(before):
        a, b = before[index], after[index]
        first = bound(a["candidate"], before_path.parent)
        second = bound(b["candidate"], after_path.parent)
        for key in ("timeline_sha256", "frame_manifest_sha256", "zone_catalog_sha256"):
            if first.get(key) != second.get(key):
                raise ValueError("The comparison changed its native inputs or Zone geometry")
        left, right = points(first), points(second)
        bound_reports[index] = second, b["candidate"]["sha256"]
        missing = sorted(left.keys() - right.keys())
        diagnostics = second.get("quality_replay", {}).get("diagnostics", {})
        for key in missing:
            diagnostic = diagnostics.get(key)
            reason = "unexplained_removal"
            if diagnostic is not None:
                reason = ("current_outline_unconfirmed" if diagnostic.get("outline") is None
                          else "current_outline_center_mismatch")
            reasons[reason] += 1
            cases.append({"index": index, "sample_ref": key, "kind": "abstained",
                          "reason": reason, "diagnostic": diagnostic})
        changed = [key for key in left.keys() & right.keys()
                   if digest(left[key]) != digest(right[key])]
        flags = trajectory_flags(second)
        suspects = {key for flag in flags for key in flag["samples"]}
        # Freeze controls from the complete cohort by hash, independently of review labels.
        controls = sorted(right.keys() - suspects,
                          key=lambda k: digest(["map_quality_controls_v1", index, k]))[:3]
        for key in controls:
            cases.append({"index": index, "sample_ref": key, "kind": "control",
                          "reason": "no_automatic_edge_flag"})
        for flag in flags:
            cases.append({"index": index, "kind": "trajectory_suspect", **flag})
        rows.append({
            "index": index, "split": b["split"],
            "before": first.get("operable_coverage"), "after": second.get("operable_coverage"),
            "removed_observations": len(missing),
            "added_observations": len(right.keys()-left.keys()),
            "changed_observations": len(changed), "trajectory_flags": len(flags),
            "lost_native_edges": len(measured_native_edges(first) - measured_native_edges(second)),
            "report_sha256": b["candidate"]["sha256"],
            "map_ids": sorted({p["map_id"] for p in right.values()}),
            "measurement_agreement": measurement_agreement(second),
        })
    return {
        "schema": "development_map_independent_quality_audit_v1", "formal_outputs": 0,
        "inputs": {"before_sha256": file_sha(before_path), "after_sha256": file_sha(after_path)},
        "recordings": rows, "abstention_reasons": dict(reasons), "cases": cases,
        "reviews": review_metrics(reviews, bound_reports),
        "independent_owner_accuracy": None, "independent_id_switch_rate": None,
        "absolute_map_error_without_review": None,
        "limits": "Automatic flags and controls are development evidence. Controls are unreviewed.",
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for key in ("before", "after", "output"):
        parser.add_argument(f"--{key}", required=True, type=Path)
    parser.add_argument("--reviews", type=Path)
    args = parser.parse_args()
    output = args.output.resolve()
    if any((p / ".git").exists() for p in (output.parent, *output.parents)) or output.exists():
        parser.error("Use a new private destination outside Git")
    reviews = read_json(args.reviews)["rows"] if args.reviews else []
    result = audit(args.before.resolve(), args.after.resolve(), reviews)
    write_private(output, result)
    print("Recordings:", len(result["recordings"]),
          "Abstentions:", sum(result["abstention_reasons"].values()),
          "Reasons:", result["abstention_reasons"])


if __name__ == "__main__":
    main()
