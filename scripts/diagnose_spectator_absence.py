"""Diagnostic-only counterfactuals for sparse-edge Spectator absence.

Consumes private, independently pixel-reviewed crops. Output has aggregates only.
No function in this module is called by production. Run against the documented
analyzer commit to reproduce that commit's legacy detector decisions.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path

import cv2
import numpy as np

from valorant_ai_coach.hud.spectator_icon import detect_icon


def normalized_features(crop: np.ndarray) -> dict[str, float | int]:
    if crop.dtype != np.uint8 or crop.ndim not in (2, 3):
        raise ValueError("uint8 gray or BGR crop required")
    if crop.ndim == 3 and crop.shape[2] != 3:
        raise ValueError("BGR crop required")
    height, width = crop.shape[:2]
    if min(height, width) < 24 or abs(width / height / (75 / 83) - 1) > 0.12:
        raise ValueError("configured icon-slot geometry required")
    gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY) if crop.ndim == 3 else crop
    gray = cv2.resize(gray, (75, 83), interpolation=cv2.INTER_AREA)
    mean, std = float(gray.mean()), float(gray.std())
    normalized = np.clip(
        mean + (gray.astype(float) - mean) * max(1, 35 / max(std, 1)), 0, 255
    ).astype(np.uint8)
    edges = cv2.Canny(normalized, 60, 150)
    occupied = edges > 0
    cells = sum(
        float(part.mean()) >= 0.08
        for row in np.array_split(occupied, 4, axis=0)
        for part in np.array_split(row, 4, axis=1)
    )
    gx, gy = cv2.Sobel(normalized, cv2.CV_32F, 1, 0), cv2.Sobel(normalized, cv2.CV_32F, 0, 1)
    angle = np.mod(np.degrees(np.arctan2(gy, gx)), 360)
    hist = np.histogram(angle[occupied], bins=np.linspace(0, 360, 9))[0]
    bins = int(sum(hist / max(1, int(hist.sum())) >= 0.05))
    _, _, groups, _ = cv2.connectedComponentsWithStats(edges)
    localized = sum(
        area >= 6 and 2 <= gw < 0.90 * 75 and 2 <= gh < 0.90 * 83
        for x, y, gw, gh, area in groups[1:]
    )
    return {
        "density": float(occupied.mean()),
        "cells": cells,
        "groups": int(localized),
        "bins": bins,
    }


def candidate_vetoes(crop: np.ndarray, result: dict) -> dict[str, bool]:
    policies = (
        "partial_raw_topology",
        "contrast_floor",
        "normalized_density",
        "normalized_full_topology",
        "normalized_orientation",
    )
    # A veto can only turn legacy checked absence into UNKNOWN. It never proves
    # presence or absence, and never alters an already UNKNOWN/present decision.
    if result.get("checked") is not True or result.get("panel_present") is not False:
        return dict.fromkeys(policies, False)
    raw = result["metrics"]
    partial = raw.get("localized_groups", 0) >= 10 and raw.get("orientation_bins", 0) == 8
    norm = normalized_features(crop)
    return {
        "partial_raw_topology": partial,
        "contrast_floor": partial or raw["contrast"] < 35,
        "normalized_density": partial or norm["density"] > 0.08,
        "normalized_full_topology": partial
        or (norm["cells"] >= 13 and norm["groups"] >= 10 and norm["bins"] == 8),
        "normalized_orientation": partial or (norm["density"] > 0.08 and norm["bins"] == 8),
    }


def _variants(crop: np.ndarray):
    for scale in (1, 0.75, 0.5, 0.25, 0.2, 0.15, 0.125):
        mean = crop.astype(float).mean(axis=(0, 1), keepdims=True)
        faded = np.clip(mean + scale * (crop.astype(float) - mean), 0, 255).astype(np.uint8)
        for sigma in (0, 0.5, 1):
            image = faded if sigma == 0 else cv2.GaussianBlur(faded, (0, 0), sigma)
            for quality in (100, 70, 40):
                if quality == 100:
                    yield image
                else:
                    ok, encoded = cv2.imencode(".jpg", image, [cv2.IMWRITE_JPEG_QUALITY, quality])
                    if not ok:
                        raise ValueError("JPEG encoding failed")
                    yield cv2.imdecode(encoded, cv2.IMREAD_COLOR)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("private_manifest", type=Path)
    parser.add_argument("aggregate_output", type=Path)
    args = parser.parse_args()
    raw = args.private_manifest.read_bytes()
    manifest = json.loads(raw)
    if not isinstance(manifest, dict) or set(manifest) != {
        "portrait_training",
        "portrait_holdout",
        "ordinary_absence",
    }:
        raise ValueError("exact diagnostic cohort fields required; no timestamps or expected state")
    cohorts = {}
    split_hashes = {}
    for name, paths in manifest.items():
        if not isinstance(paths, list) or any(not isinstance(p, str) for p in paths):
            raise ValueError("private crop paths required")
        images = []
        hashes = set()
        for path in paths:
            image = cv2.imread(path, cv2.IMREAD_COLOR)
            if image is None:
                raise ValueError("unreadable private crop")
            normalized_features(image)
            hashes.add(hashlib.sha256(image.tobytes()).hexdigest())
            images.append(image)
        cohorts[name], split_hashes[name] = images, hashes
    if split_hashes["portrait_training"] & split_hashes["portrait_holdout"]:
        raise ValueError("identical decoded pixels across training and holdout")
    summaries = {}
    for name, images in cohorts.items():
        counts = Counter()
        decisions = Counter()
        for crop in images:
            variants = _variants(crop) if name.startswith("portrait_") else (crop,)
            for variant in variants:
                result = detect_icon(variant)
                counts["cases"] += 1
                decisions[result["reason"]] += 1
                absent = result["checked"] is True and result["panel_present"] is False
                counts["runtime_checked_absence"] += absent
                for policy, veto in candidate_vetoes(variant, result).items():
                    counts[f"{policy}_absence_to_unknown"] += veto
                    counts[f"{policy}_remaining_checked_absence"] += absent and not veto
        summaries[name] = {
            "source_crops": len(images),
            "counts": dict(counts),
            "runtime_reasons": dict(decisions),
        }
    payload = {
        "diagnostic_only": True,
        "manifest_sha256": hashlib.sha256(raw).hexdigest(),
        "scope": "candidate vetoes only; no positive promotion; private visual annotations",
        "cohorts": summaries,
    }
    args.aggregate_output.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
