"""Compare Map methods at identical source PTS and keep pixel mismatches explicit."""

import argparse
import hashlib
import json
import math
import tarfile
from collections import Counter
from fractions import Fraction
from pathlib import Path

from valorant_ai_coach.temporal.map_canonical_pass import own_live_samples
from valorant_ai_coach.temporal.replay import file_sha, read_json, write_private


def clock(sample):
    return sample["source_sha256"], Fraction(sample["native_pts_tick"]) * Fraction(
        sample["native_time_base"])


def selected(report):
    return {clock(p["sample"]): p for seg in report["segments"] for p in seg
            if p["kind"] == "selected"}


def compare(legacy, canonical, native):
    old, new = selected(legacy), selected(canonical)
    common = {clock(row["sample"]): row["sample"] for row in native.values()}
    # Denominator includes abstentions by either method and uses native observations.
    old_samples = {clock(p["sample"]): p["sample"] for seg in legacy["segments"] for p in seg}
    counts, cases = Counter(), []
    for key in sorted(common.keys() & old_samples.keys()):
        sample = common[key]
        same_pixels = sample["native_pixel_sha256"] == old_samples[key]["native_pixel_sha256"]
        a, b = old.get(key), new.get(key)
        delta = None
        if a is None and b is None:
            label = "neither_selected"
        elif a is None:
            label = "canonical_only"
        elif b is None:
            label = "legacy_only"
        elif (a["map_id"], a["reference_sha256"]) != (b["map_id"], b["reference_sha256"]):
            label = "geometry_disagreement"
        else:
            delta = math.dist(a["map_reference_px"], b["map_reference_px"])
            label = "coordinate_agreement_8px" if delta <= 8 else "coordinate_disagreement"
        counts[label] += 1
        counts[("same_pixels:" if same_pixels else "unverified_pixels:") + label] += 1
        counts["identical_full_pixels" if same_pixels else "pixel_identity_unverified"] += 1
        cases.append({"sample_ref": sample["sample_sha256"],
                      "legacy_sample_ref": old_samples[key]["sample_sha256"],
                      "source_sha256": sample["source_sha256"],
                      "native_pts_tick": sample["native_pts_tick"],
                      "native_time_base": sample["native_time_base"],
                      "comparison": label, "identical_full_pixels": same_pixels,
                      "distance_reference_px": delta,
                      "legacy_position": a["map_reference_px"] if a else None,
                      "canonical_position": b["map_reference_px"] if b else None})
    return dict(counts), cases


def run(portfolio, canonical_dir, timelines, handoff):
    data, sources = read_json(portfolio), read_json(handoff)
    rows, cases, totals = [], [], Counter()
    for entry in data["recordings"]:
        artifact = entry["candidate"]
        path = Path(artifact["path"])
        if file_sha(path) != artifact["sha256"]:
            raise ValueError("The corrected Map portfolio changed")
        legacy = read_json(path)
        source = sources["recordings"][entry["index"] - 1]
        rid = source["recording_id"]
        target = canonical_dir / f"{rid}__map_canonical_PRIVATE.json"
        canonical = read_json(target)
        if any(r.get("formal_outputs") != 0 for r in (legacy, canonical)):
            raise ValueError("Development-only reports required")
        with tarfile.open(timelines / rid / "timeline.tgz") as archive:
            member = archive.extractfile("timeline/timeline_PRIVATE.json")
            if member is None:
                raise ValueError("Canonical timeline missing")
            raw = member.read()
            if hashlib.sha256(raw).hexdigest() != canonical["timeline_sha256"]:
                raise ValueError("Canonical report uses another timeline")
            timeline = json.loads(raw)
        # Use the old full native manifest, including failed selections.
        artifact = source["artifacts"]["native_frame_manifest"]
        manifest_path = Path(artifact["path"])
        if file_sha(manifest_path) != artifact["sha256"]:
            raise ValueError("The original native manifest changed")
        old_manifest = read_json(manifest_path)
        pseudo = {**legacy, "segments": [
            [{"sample": item["sample"], "kind": "unselected"}]
            for item in old_manifest["frames"]
        ]}
        # Include every old observed native instant in the common cohort.
        old_clock = {clock(x["sample"]) for x in old_manifest["frames"]}
        eligible = own_live_samples(timeline)
        native = {k: v for k, v in timeline["native_frames"].items()
                  if k in eligible and clock(v["sample"]) in old_clock}
        # Add unselected samples to the lookup without changing selected points.
        legacy_for_denominator = {**legacy, "segments": legacy["segments"] + pseudo["segments"]}
        count, found = compare(legacy_for_denominator, canonical, native)
        totals.update(count)
        rows.append({"index": entry["index"], "counts": count,
                     "canonical_report_sha256": file_sha(target),
                     "legacy_report_sha256": file_sha(path)})
        cases.extend({**case, "index": entry["index"]} for case in found)
    return {"schema": "development_map_same_sample_comparison_v1", "formal_outputs": 0,
            "recordings": rows, "counts": dict(totals), "cases": cases,
            "agreement_threshold_reference_px": 8,
            "limit": "Same source and PTS. Pixel mismatches are outside same-pixel accuracy."}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    for name in ("portfolio", "canonical", "timelines", "handoff", "output"):
        p.add_argument(f"--{name}", type=Path, required=True)
    a = p.parse_args()
    if a.output.exists() or any((v / ".git").exists() for v in a.output.resolve().parents):
        p.error("A new private output is required")
    write_private(a.output, run(a.portfolio, a.canonical, a.timelines, a.handoff))


if __name__ == "__main__":
    main()
