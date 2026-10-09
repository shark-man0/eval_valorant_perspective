"""Source-bound portrait correspondence, not liveness or boundary recognition.

Freeze training crops before inspecting probe results. Matching a portrait is
only a location observation; a nonmatch never proves its death or absence.
No expected states, counts, timestamps or evaluator inputs are consumed.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import cv2
import numpy as np

from scripts.diagnostics.roster_edge_reference import (
    BANK_METHOD,
    build_reference,
    locate_bank,
    locate_edges,
    validate_groups,
)
from scripts.diagnostics.roster_edge_reference import (
    METHOD as EDGE_METHOD,
)
from valorant_ai_coach.hud.calibrate_temporal import _check_output_privacy
from valorant_ai_coach.hud.layout import HudLayout

METHOD = "roster_portrait_gray_ncc_location_v1"


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_gray(path):
    image = cv2.imdecode(np.frombuffer(path.read_bytes(), np.uint8), cv2.IMREAD_GRAYSCALE)
    if image is None or image.size == 0:
        raise ValueError("unreadable portrait diagnostic source")
    return image


def locate(reference, search):
    """Return one descriptive maximum, never an accepted living-player count."""
    if (
        reference.ndim != 2 or search.ndim != 2 or reference.size == 0
        or reference.shape[0] > search.shape[0] or reference.shape[1] > search.shape[1]
        or float(reference.std()) < 5
    ):
        raise ValueError("nonflat in-bounds portrait reference required")
    if float(search.std()) < 5:
        return {"similarity": None, "offset_xy": None, "reason": "search_contrast_insufficient"}
    scores = cv2.matchTemplate(search, reference, cv2.TM_CCOEFF_NORMED)
    if not np.isfinite(scores).all():
        raise ValueError("nonfinite portrait similarity")
    _, score, _, point = cv2.minMaxLoc(scores)
    return {"similarity": float(score), "offset_xy": list(point), "reason": "measured"}


def replay(layout_path, manifest_path, training_root, probe_root, output):
    _check_output_privacy(output.resolve())
    if output.exists():
        raise FileExistsError("portrait diagnostic output must be new")
    original = {layout_path: digest(layout_path), manifest_path: digest(manifest_path)}
    matcher_path = Path(__file__).with_name("roster_edge_reference.py")
    original[matcher_path] = digest(matcher_path)
    manifest = json.loads(manifest_path.read_bytes())
    method = manifest["method"]
    if method not in {METHOD, EDGE_METHOD, BANK_METHOD}:
        raise ValueError("portrait method differs from frozen declaration")
    layout = HudLayout.load(layout_path)
    width, height = layout.reference_resolution or (0, 0)
    sources = manifest["training_frames"]
    if len(sources) < 3 or len({row["sha256"] for row in sources}) != len(sources):
        raise ValueError("three distinct frozen training frames required")
    groups = validate_groups(manifest.get("training_groups"), len(sources)) \
        if method == BANK_METHOD else None
    training = []
    for row in sources:
        path = (training_root / row["frame"]).resolve()
        if not path.is_relative_to(training_root.resolve()) or digest(path) != row["sha256"]:
            raise ValueError("portrait training source binding mismatch")
        image = load_gray(path)
        if image.shape != (height, width):
            raise ValueError("portrait training resolution mismatch")
        original[path] = row["sha256"]
        training.append(image)
    probes = sorted(probe_root.rglob("*.jpg"))
    if not probes or len(probes) > 128:
        raise ValueError("portrait diagnostic requires 1..128 bounded probe frames")
    references = {}
    banks = {}
    for name, crop in manifest["crops"].items():
        side = crop["side"]
        if side not in {"ally", "enemy"}:
            raise ValueError("unknown portrait team ROI")
        bounds = crop["xyxy"]
        if len(bounds) != 4 or any(type(value) is not int for value in bounds):
            raise ValueError("integer training crop bounds required")
        x1, y1, x2, y2 = bounds
        left, top, right, bottom = layout.normalized_roi(f"{side}_roster").pixel_bounds(
            width, height
        )
        if not left <= x1 < x2 <= right or not top <= y1 < y2 <= bottom:
            raise ValueError("portrait training crop outside configured ROI")
        crops = [image[y1:y2, x1:x2] for image in training]
        if method == BANK_METHOD:
            banks[name] = [build_reference([crops[i] for i in group]) for group in groups]
            reference, mask, _ = banks[name][0]
            support = {"variants": [{**diagnostic,
                        "mask_sha256": hashlib.sha256(variant_mask.tobytes()).hexdigest()}
                       for _, variant_mask, diagnostic in banks[name]]}
        elif method == EDGE_METHOD:
            reference, mask, support = build_reference(crops)
            support["mask_sha256"] = hashlib.sha256(mask.tobytes()).hexdigest()
        else:
            reference, mask = crops[0], None
            support = {"training_similarity": [locate(reference, c)["similarity"] for c in crops]}
        references[name] = (side, reference, mask, support)
    rows = []
    for path in probes:
        hash_value = digest(path)
        if hash_value in {row["sha256"] for row in sources}:
            raise ValueError("training/probe overlap")
        image = load_gray(path)
        if image.shape != (height, width):
            raise ValueError("portrait probe resolution mismatch")
        original[path] = hash_value
        locations = {}
        for name, (side, reference, mask, support) in references.items():
            left, top, right, bottom = layout.normalized_roi(f"{side}_roster").pixel_bounds(
                width, height
            )
            search = image[top:bottom, left:right]
            if method == BANK_METHOD:
                measured = locate_bank(banks[name], search)
            elif mask is None:
                measured = locate(reference, search)
            elif support["available"]:
                measured = locate_edges(reference, mask, search)
            else:
                measured = {"similarity": None, "offset_xy": None,
                            "reason": "training_reference_insufficient"}
            offset = measured["offset_xy"]
            locations[name] = {**measured, "frame_xy": None if offset is None else
                               [left + offset[0], top + offset[1]]}
            if manifest.get("control_roi"):
                region = layout.normalized_roi(manifest["control_roi"])
                cl, ct, cr, cb = region.pixel_bounds(width, height)
                control = image[ct:cb, cl:cr]
                locations[name]["control"] = (
                    locate_bank(banks[name], control) if method == BANK_METHOD else
                    locate(reference, control) if mask is None else
                    locate_edges(reference, mask, control) if support["available"] else
                    {"similarity": None, "offset_xy": None,
                     "reason": "training_reference_insufficient"}
                )
        rows.append({"frame_sha256": hash_value, "locations": locations})
    if any(digest(path) != hash_value for path, hash_value in original.items()):
        raise ValueError("portrait diagnostic inputs changed")
    report = {
        "method": method, "qualification_created": False, "continuity_attested": False,
        "liveness_counts": None, "layout_sha256": original[layout_path],
        "manifest_sha256": original[manifest_path], "implementation_sha256": digest(Path(__file__)),
        "matcher_implementation_sha256": original[matcher_path],
        "training_frame_hashes": [row["sha256"] for row in sources],
        "references": {name: {"side": side, "dimensions": list(reference.shape[::-1]),
                              **support}
                       for name, (side, reference, _, support) in references.items()},
        "rows": rows,
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("layout", "manifest", "training-root", "probe-root", "output"):
        parser.add_argument(f"--{name}", type=Path, required=True)
    args = parser.parse_args()
    report = replay(args.layout, args.manifest, args.training_root, args.probe_root, args.output)
    print(json.dumps({"probe_frames": len(report["rows"]), "qualification_created": False}))


if __name__ == "__main__":
    main()
