"""Joint world-patch translation hypotheses; diagnostic, never runtime proof.

Repeated patches are retained as alternatives. A distributed constellation must
explain >=90% of all features with NCC-qualified candidates, and any distinct
competing constellation causes abstention. No timer, phase, PTS or GT input.
"""

from __future__ import annotations

import cv2
import numpy as np

from scripts.diagnostics.scene_patch_search import _validate, reviewed_patches


def patch_peaks(patch, image, boxes):
    peaks = []
    for x1, y1, x2, y2 in boxes:
        values = cv2.matchTemplate(image[y1:y2, x1:x2], patch, cv2.TM_CCOEFF_NORMED)
        if not np.isfinite(values).all():
            continue
        for _ in range(32):
            _, score, _, (x, y) = cv2.minMaxLoc(values)
            if score < 0.90:
                break
            peaks.append((float(score), [x + x1 + 7, y + y1 + 7]))
            values[max(0, y - 2) : y + 3, max(0, x - 2) : x + 3] = -1
        if float(values.max()) >= 0.90:
            return None  # Candidate budget cannot hide alternative matches.
    return peaks


def _distributed(points):
    cells = {(int(y / 120), int(x / (640 / 3))) for x, y in points}
    return (
        len(cells) >= 3
        and len({r for r, c in cells}) >= 2
        and len({c for r, c in cells}) >= 2
        and all(0 <= r < 3 and 0 <= c < 3 for r, c in cells)
    )


def coherent_translation(groups):
    eligible = [g for g in groups if g["candidates"]]
    if len(eligible) < 3 or len({g["region"] for g in eligible}) < 3:
        return None, [], "insufficient_distributed_candidates"
    vectors = np.array(
        [np.array(pos) - g["reference_xy"] for g in eligible for score, pos in g["candidates"]],
        float,
    )
    # Exhaust every occupied bin; no winning hypothesis can conceal a second
    # globally coherent position. The translation-only model safely abstains
    # on rotation, deformation or larger parallax.
    hypotheses = np.unique(np.round(vectors / 2) * 2, axis=0)
    solutions = []
    for hypothesis in hypotheses:
        selected = []
        for group in eligible:
            positions = np.array([p for score, p in group["candidates"]], float)
            errors = np.linalg.norm(positions - group["reference_xy"] - hypothesis, axis=1)
            valid = np.flatnonzero(errors <= 2)
            if len(valid) != 1:
                continue
            index = int(valid[0])
            score, position = group["candidates"][index]
            selected.append({**group, "position": position, "score": score})
        if (
            len(selected) < 0.90 * len(eligible)
            or len({g["region"] for g in selected}) < 3
            or not _distributed([g["reference_xy"] for g in selected])
            or not _distributed([g["position"] for g in selected])
        ):
            continue
        solutions.append((hypothesis, selected))
    if not solutions:
        return None, [], "no_coherent_distributed_constellation"
    best, selected = max(solutions, key=lambda item: len(item[1]))
    if any(np.linalg.norm(hypothesis - best) > 2 for hypothesis, items in solutions):
        return None, [], "competing_distributed_constellations"
    return best.tolist(), selected, "descriptive_constellation"


def measure_constellation(reference, current, boxes, *, patches=None):
    _validate(reference, boxes)
    _validate(current, boxes)
    if patches is None:
        patches = reviewed_patches(reference, boxes)
    groups = []
    for region, position, patch in patches:
        peaks = patch_peaks(patch, current, boxes)
        if peaks is None:
            return {
                "accepted_reference_tracks": 0,
                "model_inliers": 0,
                "reason": "candidate_peak_budget_exceeded",
                "runtime_proof_authorized": False,
            }, []
        groups.append({"region": region, "reference_xy": position, "candidates": peaks})
    model, selected, reason = coherent_translation(groups)
    tracks = []
    if model is not None:
        for group in selected:
            x, y = group["position"]
            patch = current[y - 7 : y + 8, x - 7 : x + 8]
            reverse = patch_peaks(patch, reference, boxes)
            if reverse is None:
                continue
            valid = [
                (score, pos)
                for score, pos in reverse
                if np.linalg.norm(np.array(pos) - group["reference_xy"]) <= 1
            ]
            if len(valid) != 1:
                continue
            tracks.append(
                {
                    "region": group["region"],
                    "reference_xy": group["reference_xy"],
                    "current_xy": group["position"],
                    "patch_ncc": group["score"],
                    "fb_error_px": float(
                        np.linalg.norm(np.array(valid[0][1]) - group["reference_xy"])
                    ),
                    "model_inlier": True,
                }
            )
    eligible = sum(bool(g["candidates"]) for g in groups)
    if len(tracks) < 0.90 * eligible:
        tracks = []
        reason = "reciprocal_constellation_insufficient" if model is not None else reason
    return {
        "accepted_reference_tracks": len(tracks),
        "model_inliers": len(tracks),
        "reason": reason,
        "eligible_reference_features": eligible,
        "reference_patches": len(patches),
        "translation": model,
        "runtime_proof_authorized": False,
    }, tracks
