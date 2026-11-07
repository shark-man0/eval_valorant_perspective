"""Evidence-based cause hypotheses and balanced review work, not error labels."""

from __future__ import annotations

import argparse
import math
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from .comparison import DOMAINS, load_manifest, load_result
from .evidence import digest
from .replay import file_sha, read_json, write_private

VERSION = "development_issue_analysis_v1"
CAUSES = {
    "A1": "観測・直接根拠の不足",
    "A2": "HUD認識の失敗・欠落候補",
    "A3": "Round継承・遷移",
    "A4": "Life・Camera推定",
    "A5": "死亡・観戦・復帰の接続",
    "A6": "本人識別・Map対応",
    "A7": "競合仮説",
    "A8": "秒内集約の表示曖昧性",
    "A9": "観測密度・取得条件差",
    "A10": "原因未特定",
}


def _features(bundle: dict[str, Any]) -> list[dict[str, Any]]:
    result = []
    for row in bundle["seconds"]:
        frames = [bundle["native_frames"][k] for k in row["sample_refs"]]
        observations = [bundle["observations"][i] for i in row["evidence_refs"]]
        reasons = {
            str(e["estimate"]["reason"]) for d in DOMAINS for e in row[d]["native_estimates"]
        }
        mixed = {
            d
            for d in DOMAINS
            if len({e["estimate"]["value"] for e in row[d]["native_estimates"]}) > 1
        }
        competing = {d for d in DOMAINS if len(set(row[d]["hypotheses"]) - {"UNKNOWN"}) > 1}
        signals = {s for o in observations for s in o["signals"]}
        result.append(
            {
                "observed": row["observation_present"],
                "native_points": len(frames),
                "broken": any(
                    f["continuity"].get("reason")
                    in {
                        "uncovered_gap",
                        "confirmed_break_or_decode_failure",
                        "source_or_epoch_change",
                    }
                    for f in frames
                ),
                "reasons": reasons,
                "mixed": mixed,
                "competing": competing,
                "missing_HUD_signal": bool(signals & {"hud_not_detected", "report"}),
                "hud_core_missing": not any(
                    row["hud_observations"].get(k, {}).get("candidates")
                    for k in ("hp", "timer", "score")
                ),
                "map_unassigned": bool(row["map_observations"]["position_candidates"])
                and not row["map_observations"]["current_self_position_candidates"],
            }
        )
    return result


def classify_intervals(
    bundle: dict[str, Any],
    intervals: list[dict[str, Any]],
    *,
    result_id: str,
    bundle_sha256: str,
    density_ranges: list[tuple[int, int]] | None = None,
) -> list[dict[str, Any]]:
    """Multiple traceable hypotheses per unchanged input review interval.

    A8 means information hidden by the one-second summary, not discarded native
    data. Normal PTS spacing never proves game continuity. Labels are not read.
    """
    features = _features(bundle)
    output = []
    for interval in intervals:
        start, end = interval["start"], interval["end"]
        if not 0 <= start < end <= len(features):
            raise ValueError("Review interval outside recording")
        current = features[start:end]
        kind, domain = interval["kind"], interval["domain"]
        reasons = sorted({s for f in current for s in f["reasons"]})
        causes: dict[str, str] = {}
        if any(not f["observed"] or f["broken"] for f in current):
            causes["A1"] = "Missing samples or explicit acquisition/continuity barrier"
        if any(f["missing_HUD_signal"] and f["hud_core_missing"] for f in current):
            causes["A2"] = (
                "Current HUD absence/report signal and no core value; hidden UI is an alternative"
            )
        if domain == "round_state" or kind == "buy_run_review":
            causes["A3"] = (
                "Unresolved/competing Round or uncertain carry; not a proven incorrect transition"
            )
        if domain in {"life_state", "camera_state", "life_camera"}:
            causes["A4"] = "Life/camera estimate or continuity needs current-view evidence"
        if kind.startswith("lifecycle_") or any(
            any(word in reason for word in ("death", "victim", "return", "spectator"))
            for reason in reasons
        ):
            causes["A5"] = "Elimination/spectator/return context is unresolved or unlinked"
        if kind == "map_candidates_unassigned" or any(f["map_unassigned"] for f in current):
            causes["A6"] = "Current marker pool exists without recorder correspondence"
        if any(f["competing"] for f in current) or kind == "life_camera_tension":
            causes["A7"] = "Concurrent state alternatives or life/camera tension remain"
        if any(f["mixed"] for f in current):
            causes["A8"] = (
                "Native estimates differ within a second; all native estimates remain available"
            )
        if kind == "acquisition_or_configuration_changed" or any(
            lo < end and hi > start for lo, hi in density_ranges or []
        ):
            causes["A9"] = (
                "Separate fixed-density cohort changes estimates in overlapping time; "
                "not direct causal proof"
            )
        if not causes:
            causes["A10"] = "Insufficient specific evidence to attribute a cause"
        domains = {domain}
        if set(causes) & {"A4", "A5", "A6"}:
            domains.update({"life", "camera", "HUD_attribution", "Map_attribution", "evaluation"})
        if "A3" in causes:
            domains.update({"round", "round_segmentation", "evaluation"})
        identity = digest(
            {
                "result": result_id,
                "bundle_sha256": bundle_sha256,
                "kind": kind,
                "domain": domain,
                "start": start,
                "end": end,
            }
        )

        def information(i: int) -> tuple[int, int]:
            before = bundle["seconds"][max(0, i - 1)]
            after = bundle["seconds"][i]
            edge = sum(before[d]["value"] != after[d]["value"] for d in DOMAINS)
            return (4 * edge + 3 * len(features[i]["mixed"]) + len(features[i]["competing"]), -i)

        anchor = max(range(start, end), key=information)
        output.append(
            {
                "issue_id": identity,
                "result_id": result_id,
                "source": bundle["source"],
                "bundle_sha256": bundle_sha256,
                "kind": kind,
                "domain": domain,
                "start": start,
                "end": end,
                "duration_seconds": end - start,
                "causes": [
                    {
                        "code": c,
                        "label": CAUSES[c],
                        "reason": reason,
                        "status": "CAUSE_HYPOTHESIS_NOT_ERROR_TRUTH",
                    }
                    for c, reason in sorted(causes.items())
                ],
                "native_estimate_reasons": reasons,
                "affected_domains": sorted(domains),
                "observed_seconds": sum(f["observed"] for f in current),
                "native_points": sum(f["native_points"] for f in current),
                "aggregation_ambiguous_seconds": sum(bool(f["mixed"]) for f in current),
                "competing_seconds": sum(bool(f["competing"]) for f in current),
                "evidence_refs": interval["evidence_refs"],
                "sample_refs": interval["sample_refs"],
                "is_error": None,
                "formal_outputs": 0,
                "cluster": digest([kind, domain, sorted(causes), reasons[:3]]),
                "inspection_window": {
                    "anchor": anchor,
                    "start": max(0, anchor - 3),
                    "end": min(len(features), anchor + 4),
                    "selection": "native_conflict_and_state_edge; no_GT",
                },
            }
        )
    return output


def prioritize(records: list[dict[str, Any]]) -> None:
    """Heuristic review priority, not confidence or an accuracy estimate."""
    prevalence: dict[str, set[str]] = defaultdict(set)
    for row in records:
        for cause in row["causes"]:
            prevalence[cause["code"]].add(row["source"]["physical_match_id"])
    for row in records:
        codes = {c["code"] for c in row["causes"]}
        support = max(len(prevalence[c]) for c in codes)
        components = {
            "cross_domain_impact": 5 * min(5, len(row["affected_domains"])),
            "physical_match_prevalence": 3 * support,
            "duration_log_capped": round(3 * math.log2(min(600, row["duration_seconds"]) + 1), 2),
            "state_context_tension": 12 if codes & {"A5", "A7"} else 0,
            "available_native_evidence": 5 if row["evidence_refs"] else 0,
            "generic_algorithm_opportunity": 8 if codes & {"A3", "A4", "A5", "A8", "A9"} else 2,
            "downstream_attribution_or_round_scope": 8
            if "evaluation" in row["affected_domains"]
            else 0,
        }
        row["priority"] = {
            "score": round(sum(components.values()), 2),
            "components": components,
            "physical_match_support": support,
            "scope": "review_utility_heuristic_not_correctness",
        }


def select_representatives(records: list[dict[str, Any]], *, budget: int = 24) -> list[str]:
    """Greedy diversity, overlap suppression and per-match quota prevent domination."""
    if budget < 1:
        raise ValueError("Positive representative budget required")
    selected: list[dict[str, Any]] = []
    matches: Counter[str] = Counter()
    clusters: Counter[str] = Counter()
    covered: set[str] = set()
    buckets: Counter[str] = Counter()

    def bucket(row: dict[str, Any]) -> str:
        return {"round_state": "Round", "HUD": "HUD", "Map": "Map"}.get(row["domain"], "LifeCamera")

    bucket_quota = math.ceil(budget / max(1, len({bucket(r) for r in records})))
    remaining = list(records)
    quota = max(
        1, math.ceil(budget / max(1, len({r["source"]["physical_match_id"] for r in records})))
    )
    while remaining and len(selected) < budget:
        eligible = []
        for row in remaining:
            match = row["source"]["physical_match_id"]
            if matches[match] >= quota or clusters[row["cluster"]] >= 3:
                continue
            if buckets[bucket(row)] >= bucket_quota:
                continue
            window = row.get("inspection_window", row)
            overlaps = any(
                x["source"]["physical_match_id"] == match
                and max(
                    0,
                    min(x.get("inspection_window", x)["end"], window["end"])
                    - max(x.get("inspection_window", x)["start"], window["start"]),
                )
                > 3
                for x in selected
            )
            if overlaps:
                continue
            codes = {c["code"] for c in row["causes"]}
            score = row["priority"]["score"] + 15 * len(codes - covered)
            score += 30 if not matches[match] else 0
            score += 20 if not buckets[bucket(row)] else 0
            eligible.append((score, row["issue_id"], row))
        if not eligible:
            break
        chosen = max(eligible, key=lambda x: (x[0], x[1]))[2]
        selected.append(chosen)
        remaining.remove(chosen)
        matches[chosen["source"]["physical_match_id"]] += 1
        clusters[chosen["cluster"]] += 1
        buckets[bucket(chosen)] += 1
        covered.update(c["code"] for c in chosen["causes"])
    return [r["issue_id"] for r in selected]


def analyze_catalog(manifest: Path, catalog_path: Path) -> dict[str, Any]:
    catalog = read_json(catalog_path)
    if catalog["manifest_sha256"] != file_sha(manifest) or catalog["formal_outputs"] != 0:
        raise ValueError("Catalog must bind this exact manifest")
    entries = {e["id"]: e for e in load_manifest(manifest)}
    density: dict[str, list[tuple[int, int]]] = defaultdict(list)
    for result in catalog["results"]:
        if result.get("before_after"):
            density[result["source"]["physical_match_id"]].extend(
                (i["start"], i["end"])
                for i in result["review_intervals"]
                if i["kind"] == "acquisition_or_configuration_changed"
                and result["conditions"].get("cohort")
                == "separate_paired_automatic_full_acquisition"
            )
    records, bindings = [], {}
    for result in catalog["results"]:
        if not result["primary"]:
            continue
        entry = entries[result["id"]]
        if result["bundle_sha256"] != entry["bundle_sha256"]:
            raise ValueError("Catalog result binding changed")
        records.extend(
            classify_intervals(
                load_result(entry),
                result["review_intervals"],
                result_id=entry["id"],
                bundle_sha256=entry["bundle_sha256"],
                density_ranges=density[result["source"]["physical_match_id"]],
            )
        )
        bindings[entry["id"]] = {k: entry[k] for k in ("bundle_sha256", "policy_sha256")}
    prioritize(records)
    counts = Counter(c["code"] for r in records for c in r["causes"])
    per_match: dict[str, Counter[str]] = defaultdict(Counter)
    for row in records:
        per_match[row["source"]["physical_match_id"]].update(c["code"] for c in row["causes"])
    return {
        "version": VERSION,
        "manifest_sha256": file_sha(manifest),
        "baseline_manifest": str(manifest.resolve()),
        "catalog_sha256": file_sha(catalog_path),
        "result_bindings": bindings,
        "intervals": len(records),
        "physical_matches": len(per_match),
        "records": records,
        "cause_counts_multiple_labels": {k: counts[k] for k in CAUSES},
        "cause_counts_by_match": {m: {k: c[k] for k in CAUSES} for m, c in per_match.items()},
        "representatives": select_representatives(records),
        "qualification": "development_only",
        "formal_outputs": 0,
        "limits": [
            "Causes are hypotheses, not human error labels",
            "A8 preserves native information",
            "A9 uses overlapping-time evidence from a separate density cohort",
            "Missing Map analysis is not a negative marker/ownership observation",
        ],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--catalog", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = analyze_catalog(args.manifest, args.catalog)
    write_private(args.output, result)
    print(
        f"{result['intervals']} unlabelled intervals; "
        f"{len(result['representatives'])} representatives"
    )


if __name__ == "__main__":
    main()
