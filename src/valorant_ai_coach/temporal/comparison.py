"""Private multi-match review catalogue over existing application outputs.

This is a downstream consumer, never another state machine or accuracy metric.
Inputs remain bound to their registered Sources and original output receipts.
"""

from __future__ import annotations

import argparse
import csv
import math
import re
from collections import Counter
from fractions import Fraction
from pathlib import Path
from typing import Any

from .application import HUD_FIELDS, VERSION
from .evidence import digest
from .replay import SourcePolicy, file_sha, read_json, write_private

MANIFEST_VERSION = "development_timeline_comparison_manifest_v1"
CATALOG_VERSION = "development_timeline_comparison_v1"
DOMAINS = ("round_state", "life_state", "camera_state")


def unknown_reason(row: dict[str, Any], domain: str) -> str:
    """Distinguish no sample, conflicting estimates and unresolved recognition."""
    state = row[domain]
    if state["value"] != "UNKNOWN":
        return "known_candidate"
    if not row["observation_present"]:
        return "not_observed"
    values = {h for h in state["hypotheses"] if h != "UNKNOWN"}
    return "conflicting_candidates" if len(values) > 1 else "observed_unresolved"


def review_intervals(bundle: dict[str, Any], *, minimum_unknown: int = 10) -> list[dict[str, Any]]:
    """Extract review suggestions without labelling unreviewed intervals as errors."""
    if minimum_unknown < 1:
        raise ValueError("Positive UNKNOWN run threshold required")
    rows = bundle["seconds"]
    flags: dict[tuple[str, str], list[int]] = {}

    def mark(kind: str, domain: str, second: int) -> None:
        flags.setdefault((kind, domain), []).append(second)

    for row in rows:
        second = row["timestamp"]
        for domain in DOMAINS:
            if row[domain]["value"] == "UNKNOWN":
                mark("unknown_" + unknown_reason(row, domain), domain, second)
            if len({v for v in row[domain]["hypotheses"] if v != "UNKNOWN"}) > 1:
                mark("competing_state_hypotheses", domain, second)
        life, camera = row["life_state"]["value"], row["camera_state"]["value"]
        if (life == "ALIVE" and camera == "SPECTATOR") or (life == "DEAD" and camera == "SELF"):
            mark("life_camera_tension", "life_camera", second)
        if any(f["candidates"] for f in row["hud_observations"].values()) and any(
            row[d]["value"] == "UNKNOWN" for d in DOMAINS
        ):
            mark("hud_available_state_unresolved", "HUD", second)
        maps = row["map_observations"]
        if maps["position_candidates"] and not maps["current_self_position_candidates"]:
            mark("map_candidates_unassigned", "Map", second)
        # A sustained BUY estimate is a review trigger, not proof of a false BUY.
        if row["round_state"]["value"] == "BUY":
            mark("buy_run_review", "round_state", second)
        for domain in DOMAINS:
            if any("continu" in str(x) for x in row[domain].get("uncertainty", [])):
                mark("continuity_uncertain", domain, second)
    pending_lifecycle: dict[str, Any] | None = None
    for event in sorted(bundle["events"].values(), key=lambda e: e["upper_timestamp"]):
        transition = event.get("native_transition", {})
        if transition.get("kind") in {
            "death",
            "return",
            "spectator",
            "death_candidate",
            "return_candidate",
        } and (not transition.get("evidence_ids") or transition.get("before") == "UNKNOWN"):
            mark(
                "lifecycle_context_incomplete",
                "life_camera",
                min(len(rows) - 1, max(0, math.floor(event["upper_timestamp"]))),
            )
        if event["kind"] in {"death", "death_hypothesis"}:
            pending_lifecycle = event
        if event["kind"] in {"return", "return_hypothesis"}:
            if pending_lifecycle is None:
                mark(
                    "lifecycle_context_incomplete",
                    "life_camera",
                    min(len(rows) - 1, max(0, math.floor(event["upper_timestamp"]))),
                )
            pending_lifecycle = None
    if pending_lifecycle:
        start = max(0, math.floor(pending_lifecycle["upper_timestamp"]))
        for second in range(start, len(rows)):
            mark("lifecycle_return_not_linked", "life_camera", second)
    result = []
    for (kind, domain), seconds in sorted(flags.items()):
        groups: list[list[int]] = []
        for second in sorted(set(seconds)):
            if groups and groups[-1][-1] + 1 == second:
                groups[-1].append(second)
            else:
                groups.append([second])
        for group in groups:
            threshold = (
                minimum_unknown
                if kind.startswith("unknown_")
                else 60
                if kind == "buy_run_review"
                else 1
            )
            if len(group) < threshold:
                continue
            first, last = group[0], group[-1]
            refs = sorted({ref for i in group for ref in rows[i]["evidence_refs"]})
            result.append(
                {
                    "kind": kind,
                    "domain": domain,
                    "start": first,
                    "end": last + 1,
                    "seconds": len(group),
                    "status": "UNLABELLED_REVIEW_CANDIDATE",
                    "is_error": None,
                    "evidence_refs": refs,
                    "sample_refs": sorted({ref for i in group for ref in rows[i]["sample_refs"]}),
                    "review_scope": "automatic_suggestion_not_GT_or_event_truth",
                }
            )
    return sorted(result, key=lambda x: (x["start"], x["kind"], x["domain"]))


def compare_versions(before: dict[str, Any], after: dict[str, Any]) -> dict[str, Any]:
    """Describe changes at aligned seconds and exact pixels, never infer correctness."""
    if before["source"] != after["source"] or before["recording"] != after["recording"]:
        raise ValueError("Same physical Source and recording clock required")
    if len(before["seconds"]) != len(after["seconds"]):
        raise ValueError("Same full-length grid required")
    intervals = []
    counts = {}
    for domain in DOMAINS:
        changed = [
            i
            for i, (a, b) in enumerate(zip(before["seconds"], after["seconds"], strict=True))
            if a[domain]["value"] != b[domain]["value"]
        ]
        counts[domain] = {
            "changed_seconds": len(changed),
            "previous_known_estimates_changed_not_lost_truth": sum(
                before["seconds"][i][domain]["value"] != "UNKNOWN" for i in changed
            ),
            "previous_correct_lost": None,
        }
        groups: list[list[int]] = []
        for i in changed:
            if groups and groups[-1][-1] + 1 == i:
                groups[-1].append(i)
            else:
                groups.append([i])
        for group in groups:
            intervals.append(
                {
                    "kind": "acquisition_or_configuration_changed",
                    "domain": domain,
                    "start": group[0],
                    "end": group[-1] + 1,
                    "seconds": len(group),
                    "status": "UNLABELLED_REVIEW_CANDIDATE",
                    "is_error": None,
                    "evidence_refs": sorted(
                        {ref for i in group for ref in after["seconds"][i]["evidence_refs"]}
                    ),
                    "sample_refs": sorted(
                        {ref for i in group for ref in after["seconds"][i]["sample_refs"]}
                    ),
                    "review_scope": "configuration_or_density_difference_not_accuracy",
                }
            )

    def key(frame: dict[str, Any]) -> tuple[Any, ...]:
        s = frame["sample"]
        return (
            s["source_sha256"],
            Fraction(s["native_pts_tick"]) * Fraction(s["native_time_base"]),
            s["native_pixel_sha256"],
            tuple(s["frame_size_px"]),
        )

    left = {key(f): f for f in before["native_frames"].values()}
    right = {key(f): f for f in after["native_frames"].values()}
    common = left.keys() & right.keys()
    native = {
        d: sum(left[k][d]["value"] != right[k][d]["value"] for k in common)
        for d in ("round", "life", "camera")
    }
    return {
        "seconds": counts,
        "exact_pixel_common_native_points": len(common),
        "exact_pixel_native_state_changes": native,
        "review_intervals": intervals,
        "population_accuracy": None,
        "previous_correct_lost": None,
    }


def summarize_bundle(bundle: dict[str, Any]) -> dict[str, Any]:
    if bundle.get("version") != VERSION or bundle.get("formal_outputs") != 0:
        raise ValueError("Unqualified application bundle required")
    rows = bundle["seconds"]
    if len(rows) != math.ceil(Fraction(bundle["recording"]["duration_seconds"])) or any(
        row["timestamp"] != i for i, row in enumerate(rows)
    ):
        raise ValueError("Complete ordered recording-second grid required")
    domains: dict[str, Any] = {}
    for domain in DOMAINS:
        counts = Counter(r[domain]["value"] for r in rows)
        domains[domain] = {
            "counts": dict(counts),
            "available_seconds": len(rows) - counts["UNKNOWN"],
            "unknown_seconds": counts["UNKNOWN"],
            "unknown_fraction": counts["UNKNOWN"] / len(rows),
            "unknown_reasons": dict(
                Counter(unknown_reason(r, domain) for r in rows if r[domain]["value"] == "UNKNOWN")
            ),
        }
    hud = {
        name: sum(bool(r["hud_observations"].get(name, {}).get("candidates")) for r in rows)
        for name in sorted(set(HUD_FIELDS) | {k for r in rows for k in r["hud_observations"]})
    }
    maps = [r["map_observations"] for r in rows]
    return {
        "source": bundle["source"],
        "rows": len(rows),
        "duration_seconds": bundle["recording"]["duration_seconds"],
        "native_origin_seconds": bundle["recording"]["native_origin_seconds"],
        "observed_seconds": sum(r["observation_present"] for r in rows),
        "unobserved_seconds": sum(not r["observation_present"] for r in rows),
        "inferred_only_seconds": sum(
            r["observation_present"]
            and all(r[d]["status"] != "OBSERVED" for d in DOMAINS)
            and any(r[d]["value"] != "UNKNOWN" for d in DOMAINS)
            for r in rows
        ),
        "domains": domains,
        "hud_candidate_seconds": hud,
        "hud_visibility_analyzed_seconds": sum(
            bool(r.get("hud_visibility_observations", {}).get("analysis_present")) for r in rows
        ),
        "map_candidate_seconds": sum(bool(m["position_candidates"]) for m in maps),
        "map_self_candidate_seconds": sum(
            bool(m["current_self_position_candidates"]) for m in maps
        ),
        "map_provisional_seconds": sum(
            bool(m.get("provisional_recorder_position_hypotheses")) for m in maps
        ),
        "zone_candidate_seconds": sum(bool(m["zone_candidates"]) for m in maps),
        "map_name_candidate_seconds": sum(bool(m["map_name_candidates"]) for m in maps),
        "event_counts": dict(Counter(e["kind"] for e in bundle["events"].values())),
        "event_candidate_seconds": sum(bool(r["event_candidates"]) for r in rows),
        "producer_fingerprints": sorted(
            {r["producer_fingerprint"] for r in bundle["observations"].values()}
        ),
        "native_epochs": sorted(
            {f["sample"]["native_epoch"] for f in bundle["native_frames"].values()}
        ),
        "native_samples": len(bundle["native_frames"]),
        "engine_configuration": bundle["engine_configuration"],
        "measurement_scope": "coverage_not_accuracy; exposed_DEVELOPMENT; reused_acquisition",
        "formal_outputs": 0,
    }


def load_manifest(path: Path) -> list[dict[str, Any]]:
    manifest = read_json(path)
    if manifest.get("version") != MANIFEST_VERSION or not manifest.get("results"):
        raise ValueError("Development comparison manifest required")
    results: list[dict[str, Any]] = manifest["results"]
    ids = [r["id"] for r in results]
    if len(set(ids)) != len(ids) or any(not re.fullmatch(r"[A-Za-z0-9_-]+", i) for i in ids):
        raise ValueError("Unique safe result identifiers required")
    for entry in results:
        for key in ("bundle", "policy"):
            target = Path(entry[key])
            if not target.is_absolute():
                target = path.parent / target
            entry[key] = str(target.resolve())
            if file_sha(target) != entry[key + "_sha256"]:
                raise ValueError("Comparison input digest mismatch")
        if type(entry.get("primary")) is not bool or not isinstance(entry.get("conditions"), dict):
            raise ValueError("Explicit primary flag and acquisition conditions required")
    return results


def load_result(entry: dict[str, Any]) -> dict[str, Any]:
    path = Path(entry["bundle"])
    if (
        file_sha(path) != entry["bundle_sha256"]
        or file_sha(Path(entry["policy"])) != entry["policy_sha256"]
    ):
        raise ValueError("Comparison input changed")
    receipt = read_json(path.parent / "completion_PRIVATE.json")
    if receipt["output_sha256s"][path.name] != entry["bundle_sha256"]:
        raise ValueError("Bundle receipt mismatch")
    bundle: dict[str, Any] = read_json(path)
    if bundle.get("version") != VERSION or bundle.get("formal_outputs") != 0:
        raise ValueError("Unqualified application bundle required")
    policy = SourcePolicy(read_json(Path(entry["policy"])))
    source = policy.allowed[bundle["source"]["source_sha256"]]
    if (
        source["physical_match_id"] != bundle["source"]["physical_match_id"]
        or source["video_id"] != bundle["source"]["source_id"]
    ):
        raise ValueError("Physical-match identity mismatch")
    for frame in bundle["native_frames"].values():
        policy.admit(frame["sample"])
        if frame["sample"]["source_sha256"] != source["source_sha256"]:
            raise ValueError("One Source per result required")
    for row in bundle["observations"].values():
        policy.admit(row["sample"])
        if row["sample"]["source_sha256"] != source["source_sha256"]:
            raise ValueError("Observation belongs to another Source")
    return bundle


def build_catalog(manifest_path: Path) -> dict[str, Any]:
    """Process one bundle at a time; do not retain all large native bundles."""
    results = []
    primary_matches: set[str] = set()
    entries = load_manifest(manifest_path)
    entry_by_id = {e["id"]: e for e in entries}
    for entry in entries:
        bundle = load_result(entry)
        summary = summarize_bundle(bundle)
        physical = summary["source"]["physical_match_id"]
        if entry["primary"]:
            if physical in primary_matches:
                raise ValueError("One primary result per physical match required")
            primary_matches.add(physical)
        summary.update(
            {
                "id": entry["id"],
                "label": entry.get("label", entry["id"]),
                "primary": entry["primary"],
                "generation_status": "VERIFIED_SAVED_OUTPUT",
                "bundle_sha256": entry["bundle_sha256"],
                "conditions": entry["conditions"],
                "condition_identity": digest(entry["conditions"]),
                "recognizer_configuration_identity": digest(
                    {
                        "conditions": entry["conditions"],
                        "engine": bundle["engine_configuration"],
                        "observed_producers": summary["producer_fingerprints"],
                    }
                ),
                "seconds": [
                    {
                        "timestamp": r["timestamp"],
                        **{d: r[d]["value"] for d in DOMAINS},
                        "unknown_reasons": {d: unknown_reason(r, d) for d in DOMAINS},
                        "round_candidates": r["round_number"]["candidates"],
                        "observed": r["observation_present"],
                        "events": len(r["event_candidates"]),
                        "hud": any(v["candidates"] for v in r["hud_observations"].values()),
                        "map": bool(r["map_observations"]["position_candidates"]),
                        "zone": bool(r["map_observations"]["zone_candidates"]),
                    }
                    for r in bundle["seconds"]
                ],
                "review_intervals": review_intervals(bundle),
            }
        )
        if entry.get("compare_to"):
            before_entry = entry_by_id[entry["compare_to"]]
            difference = compare_versions(load_result(before_entry), bundle)
            summary["comparison_to"] = before_entry["id"]
            summary["before_after"] = {
                k: v for k, v in difference.items() if k != "review_intervals"
            }
            summary["review_intervals"].extend(difference["review_intervals"])
        results.append(summary)
        del bundle
    primary = [r for r in results if r["primary"]]
    return {
        "version": CATALOG_VERSION,
        "manifest_sha256": file_sha(manifest_path),
        "physical_matches": len(primary_matches),
        "result_versions": len(results),
        "primary_rows": sum(r["rows"] for r in primary),
        "primary_duration_seconds": str(
            sum((Fraction(r["duration_seconds"]) for r in primary), Fraction())
        ),
        "primary_unknown_totals": {
            d: sum(r["domains"][d]["unknown_seconds"] for r in primary) for d in DOMAINS
        },
        "primary_unknown_mean_fractions": {
            d: sum(r["domains"][d]["unknown_fraction"] for r in primary) / len(primary)
            if primary
            else None
            for d in DOMAINS
        },
        "results": results,
        "formal_outputs": 0,
        "comparability": (
            "Different conditions/epochs/supplements are separate review cohorts, "
            "not equal-condition accuracy. No labels supplied; "
            "review candidates are not errors."
        ),
    }


def export_catalog(manifest: Path, output: Path) -> dict[str, Any]:
    from valorant_ai_coach.rules.development_timeline import review_timeline

    if output.exists():
        raise ValueError("New private output directory required")
    catalog = build_catalog(manifest)
    output.mkdir(parents=True, mode=0o700)
    write_private(output / "comparison_PRIVATE.json", catalog)
    fields = [
        "id",
        "physical_match_id",
        "primary",
        "rows",
        "observed_seconds",
        "inferred_only_seconds",
        *[d + "_unknown" for d in DOMAINS],
        "map_candidate_seconds",
        "zone_candidate_seconds",
        "condition_identity",
    ]
    with (output / "comparison_PRIVATE.csv").open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        for r in catalog["results"]:
            writer.writerow(
                {
                    **{k: r[k] for k in fields if k in r},
                    "physical_match_id": r["source"]["physical_match_id"],
                    **{d + "_unknown": r["domains"][d]["unknown_seconds"] for d in DOMAINS},
                }
            )
    evaluations = {}
    for entry in load_manifest(manifest):
        result = review_timeline(load_result(entry))
        evaluations[entry["id"]] = result
    write_private(output / "evaluation_PRIVATE.json", evaluations)
    write_private(
        output / "completion_PRIVATE.json",
        {
            "manifest_sha256": file_sha(manifest),
            "physical_matches": catalog["physical_matches"],
            "primary_rows": catalog["primary_rows"],
            "formal_outputs": 0,
            "output_sha256s": {p.name: file_sha(p) for p in output.iterdir() if p.is_file()},
        },
    )
    return catalog


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    catalog = export_catalog(args.manifest, args.output)
    print(
        f"{catalog['physical_matches']} physical matches; "
        f"{catalog['primary_rows']} primary rows; coverage only"
    )


if __name__ == "__main__":
    main()
