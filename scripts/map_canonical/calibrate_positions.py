"""Turn a blind visual review of sampled Map positions into per-support confidence values.

Inputs: the stratified sample (``id``, ``tier``, ``recording``, ``sample``, ``sec``) shown
to the reviewer without its tier, and the reviewer's labels
(``{"correct": [ids], "wrong": [ids], "unclear": [ids]}``). Every sampled id must have
exactly one label. Confidence is the Wilson 95% lower bound of precision with unclear
counted as wrong, so a small or noisy review gives a low value rather than a high one.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from collections import Counter
from pathlib import Path

SCHEMA = "development_map_position_calibration_v1"
LABELS = ("correct", "wrong", "unclear")


def wilson_lower(successes: int, total: int, z: float = 1.96) -> float:
    if total <= 0:
        return 0.0
    p = successes / total
    centre = p + z * z / (2 * total)
    spread = z * math.sqrt(p * (1 - p) / total + z * z / (4 * total * total))
    return (centre - spread) / (1 + z * z / total)


def calibrate(sample: list[dict], labels: dict[str, list[int]]) -> dict:
    label_of: dict[int, str] = {}
    for name in LABELS:
        for item in labels.get(name, []):
            if item in label_of:
                raise ValueError(f"id {item} has two labels")
            label_of[int(item)] = name
    ids = {int(row["id"]) for row in sample}
    if set(label_of) != ids:
        raise ValueError("labels must cover exactly the sampled ids")
    counts: dict[str, Counter] = {}
    for row in sample:
        counts.setdefault(row["tier"], Counter())[label_of[int(row["id"])]] += 1
    tiers = {}
    for tier, c in sorted(counts.items()):
        reviewed = sum(c[name] for name in LABELS)
        tiers[tier] = {
            **{name: c[name] for name in LABELS}, "reviewed": reviewed,
            "precision_excluding_unclear": round(
                c["correct"] / max(1, c["correct"] + c["wrong"]), 4),
            "confidence": round(wilson_lower(c["correct"], reviewed), 4),
        }
    return {
        "schema": SCHEMA,
        "method": "blind visual review; Wilson 95% lower bound; unclear counted as wrong",
        "confidence": {tier: row["confidence"] for tier, row in tiers.items()},
        "tiers": tiers,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sample", type=Path, required=True)
    parser.add_argument("--labels", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    sample_bytes = args.sample.read_bytes()
    labels_bytes = args.labels.read_bytes()
    result = calibrate(json.loads(sample_bytes.decode("utf-8")),
                       json.loads(labels_bytes.decode("utf-8")))
    result["sample_sha256"] = hashlib.sha256(sample_bytes).hexdigest()
    result["labels_sha256"] = hashlib.sha256(labels_bytes).hexdigest()
    args.out.write_text(json.dumps(result, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
