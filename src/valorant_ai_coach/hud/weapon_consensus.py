"""Training-consensus Weapon slot shapes, isolated from values and other roles.

Each learned slot is critical. No k-of-n fallback, frame persistence, Otsu
segmentation, or underline presence can manufacture positive evidence.
"""

from __future__ import annotations

from typing import Any, cast

import cv2
import numpy as np

from .weapon_identity import similarity_distribution

MATCHER = "weapon_consensus_ridges_v1"


def allowed_region(
    shape: tuple[int, int], spec: dict[str, Any], neighbors: list[list[float]]
) -> np.ndarray:
    h, w = shape
    result = np.zeros(shape, np.uint8)
    boxes = [spec["intended_bounds"], *spec.get("dynamic_bounds", []), *neighbors]
    for i, box in enumerate(boxes):
        if len(box) != 4 or not all(np.isfinite(v) for v in box):
            raise ValueError("invalid Weapon allowed bounds")
        if not (0 <= box[0] < box[2] <= 1 and 0 <= box[1] < box[3] <= 1):
            raise ValueError("invalid Weapon allowed bounds")
        x1, y1, x2, y2 = [round(v * (w if j % 2 == 0 else h)) for j, v in enumerate(box)]
        result[y1:y2, x1:x2] = 255 if i == 0 else 0
    if np.count_nonzero(result) < 64:
        raise ValueError("insufficient isolated Weapon area")
    return result


def contrast_features(image: np.ndarray, allowed: np.ndarray) -> np.ndarray:
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY) if image.ndim == 3 else image
    if gray.shape != allowed.shape or not np.any(allowed):
        return np.zeros(allowed.shape, float)
    selected = allowed > 0
    isolated = np.full(gray.shape, np.median(gray[selected]), np.uint8)
    isolated[selected] = gray[selected]
    # Cross-stroke contrast of the persistent vertical ammo slots. A local
    # linear brightness slope cancels; no frame-wide or Otsu threshold is used.
    contrast = isolated.astype(float) - cv2.blur(isolated, (7, 1)).astype(float)
    contrast[~selected] = 0
    return cast(np.ndarray, contrast)


def _group_score(reference: np.ndarray, values: np.ndarray) -> float:
    reference = reference - reference.mean()
    values = values - values.mean()
    denominator = float(np.linalg.norm(reference) * np.linalg.norm(values))
    return float(np.clip(reference @ values / denominator, -1, 1)) if denominator else 0.0


def consensus_score(
    reference: np.ndarray,
    image: np.ndarray,
    mask: np.ndarray,
    regions: np.ndarray,
    allowed: np.ndarray,
    diagnostics: dict[str, Any] | None = None,
) -> float:
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY) if image.ndim == 3 else image
    reference = cv2.cvtColor(reference, cv2.COLOR_BGR2GRAY) if reference.ndim == 3 else reference
    if not (gray.shape == reference.shape == mask.shape == regions.shape == allowed.shape):
        return 0.0
    groups = int(regions.max())
    if not 2 <= groups <= 4:
        return 0.0
    selected = [(regions == g) & (mask > 0) for g in range(1, groups + 1)]
    if any(np.count_nonzero(s) < 32 or np.any(s & (allowed == 0)) for s in selected):
        return 0.0
    observed = contrast_features(gray, allowed)
    decoded = reference.astype(float) - 127
    padded = np.pad(observed, 1)
    candidates = []
    h, w = gray.shape
    for dy in (-1, 0, 1):
        for dx in (-1, 0, 1):
            shifted = padded[1 + dy : 1 + dy + h, 1 + dx : 1 + dx + w]
            scores = []
            rows = []
            for g, support in enumerate(selected, 1):
                values = shifted[support]
                std = float(values.std())
                grayscale_std = float(gray[support].std())
                observable = std >= 5 and grayscale_std >= 5
                score = max(0.0, _group_score(decoded[support], values)) if observable else 0.0
                scores.append(score)
                rows.append(
                    dict(
                        group_id=g,
                        expected_feature_count=int(support.sum()),
                        local_grayscale_std=grayscale_std,
                        contrast_std=std,
                        score=score,
                        observable=observable,
                        matching=observable and score >= 0.90,
                        contradictory=observable and score < 0.90,
                        unobservable=not observable,
                    )
                )
            candidates.append((min(scores), -abs(dx) - abs(dy), dx, dy, rows))
    best = max(candidates, key=lambda item: item[:2])
    if diagnostics is not None:
        diagnostics.update(
            score=best[0],
            dx=best[2],
            dy=best[3],
            groups=best[4],
            limiting_group=min(best[4], key=lambda r: r["score"])["group_id"],
            rule="all_learned_slots_current_frame",
            threshold=0.90,
        )
    return float(best[0])


def _encode_consensus(
    features: list[np.ndarray], regions: np.ndarray, members: list[int]
) -> np.ndarray:
    normalized = []
    for index in members:
        current = np.zeros(regions.shape, float)
        for g in range(1, int(regions.max()) + 1):
            selected = regions == g
            values = features[index][selected]
            values = values - values.mean()
            magnitude = float(np.linalg.norm(values))
            current[selected] = values / magnitude if magnitude else 0
        normalized.append(current)
    consensus = np.mean(np.stack(normalized), axis=0)
    peak = float(np.max(np.abs(consensus)))
    encoded = np.clip(np.rint(127 + consensus * 127 / max(peak, 1e-9)), 0, 254).astype(np.uint8)
    encoded[regions == 0] = 0
    return encoded


def persistent_reference(
    crops: list[np.ndarray],
    spec: dict[str, Any],
    stats: dict[str, Any],
    neighbor_bounds: list[list[float]],
) -> tuple[np.ndarray, list[float], np.ndarray, np.ndarray, np.ndarray] | None:
    stats.update(
        matcher=MATCHER,
        proposal_source="training_persistent_slots",
        training_count=len(crops[::2]),
        holdout_count=len(crops[1::2]),
        candidate_count=0,
        support_rejected=0,
        structural_rejected=0,
        holdout_rejected=0,
    )
    if len(crops) < 16 or any(c.shape != crops[0].shape for c in crops):
        return None
    h, w = crops[0].shape[:2]
    try:
        full_allowed = allowed_region((h, w), spec, neighbor_bounds)
    except (KeyError, ValueError, TypeError):
        stats["reason"] = "role_geometry_invalid"
        return None
    valid = cv2.erode(full_allowed, np.ones((7, 7), np.uint8)) > 0
    if np.count_nonzero(valid) < 64:
        stats.update(reason="role_geometry_invalid", structural_rejected=1)
        return None
    training = crops[::2]
    features = [contrast_features(c, full_allowed) for c in training]
    normalized = [f / max(8.0, float(np.percentile(np.abs(f[valid]), 99))) for f in features]
    recurrence = np.sum(np.stack(normalized) > 0.5, axis=0)
    recurrence[~valid] = 0
    recurrent = (recurrence >= 3).astype(np.uint8)
    connected = cv2.morphologyEx(recurrent, cv2.MORPH_CLOSE, np.ones((3, 1), np.uint8))
    _, _, components, centers = cv2.connectedComponentsWithStats(connected)
    atoms = []
    for component, center in zip(components[1:], centers[1:], strict=True):
        x, y, cw, ch, area = map(int, component)
        # A slot has separated cap/stem evidence, not a solid arbitrary stripe.
        occupied = recurrent[y : y + ch, x : x + cw].any(axis=1)
        hole = any(
            not occupied[j] and occupied[:j].any() and occupied[j + 1 :].any()
            for j in range(1, ch - 1)
        )
        if area >= 8 and ch >= 8 and ch >= 2 * cw and hole:
            atoms.append((component, center))
    atoms.sort(key=lambda item: item[1][0])
    if not 2 <= len(atoms) <= 4:
        stats.update(reason="persistent_slots_insufficient", structural_rejected=1)
        return None
    tops = [int(s[1]) for s, _ in atoms]
    ends = [int(s[1] + s[3]) for s, _ in atoms]
    if max(tops) - min(tops) > 2 or max(ends) - min(ends) > 2:
        stats.update(reason="slot_layout_inconsistent", structural_rejected=1)
        return None
    regions = np.zeros((h, w), np.uint8)
    boxes = []
    for j, (component, center) in enumerate(atoms):
        x, y, cw, ch, _ = map(int, component)
        left, right = max(0, x - 3), min(w, x + cw + 3)
        if j:
            left = max(left, round((atoms[j - 1][1][0] + center[0]) / 2))
        if j < len(atoms) - 1:
            right = min(right, round((center[0] + atoms[j + 1][1][0]) / 2))
        top, bottom = max(0, y - 3), min(h, y + ch + 3)
        regions[top:bottom, left:right] = j + 1
        boxes.append([left / w, top / h, right / w, bottom / h])
    regions[~valid] = 0
    if any(np.count_nonzero(regions == g) < 32 for g in range(1, len(atoms) + 1)):
        stats.update(reason="slot_support_insufficient", structural_rejected=1)
        return None
    # All discovery and consensus passes use TRAINING only; no single seed
    # supplies a feature pattern. Each contributor is equally normalized.
    mask = (regions > 0).astype(np.uint8) * 255
    reference = _encode_consensus(features, regions, list(range(len(training))))
    members = [
        i
        for i, c in enumerate(training)
        if consensus_score(reference, c, mask, regions, full_allowed) >= 0.90
    ]
    if len(members) < 3:
        stats.update(reason="consensus_support_insufficient", support_rejected=1)
        return None
    reference = _encode_consensus(features, regions, members)
    scores = [consensus_score(reference, c, mask, regions, full_allowed) for c in training]
    support = sum(v >= 0.90 for v in scores)
    if support < 3 or sum(scores[i] >= 0.90 for i in members) < 0.80 * len(members):
        stats.update(reason="consensus_support_insufficient", support_rejected=1)
        return None
    stats["candidate_count"] = 1
    heldout = crops[1::2]
    hold_scores = [consensus_score(reference, c, mask, regions, full_allowed) for c in heldout]
    hold_support = sum(v >= 0.90 for v in hold_scores)
    train_diagnostics: list[dict[str, Any]] = []
    hold_diagnostics: list[dict[str, Any]] = []
    for population, target in ((training, train_diagnostics), (heldout, hold_diagnostics)):
        for crop in population:
            diagnostic: dict[str, Any] = {}
            consensus_score(reference, crop, mask, regions, full_allowed, diagnostic)
            target.append(diagnostic)
    details = []
    for g, (component, _) in enumerate(atoms, 1):
        _, _, cw, ch, _ = map(int, component)
        x, y = int(component[0]), int(component[1])
        details.append(
            dict(
                group_id=g,
                normalized_bounds=boxes[g - 1],
                mask_population=int(np.count_nonzero(regions == g)),
                training_recurrence_min=int(
                    recurrence[y : y + ch, x : x + cw][recurrent[y : y + ch, x : x + cw] > 0].min()
                ),
                training_support=sum(d["groups"][g - 1]["matching"] for d in train_diagnostics),
                holdout_support=sum(d["groups"][g - 1]["matching"] for d in hold_diagnostics),
                consensus_cluster_support=sum(
                    train_diagnostics[i]["groups"][g - 1]["matching"] for i in members
                ),
                holdout_observable=sum(d["groups"][g - 1]["observable"] for d in hold_diagnostics),
                critical=True,
            )
        )
    selected = dict(
        roi_bounds=[0.0, 0.0, 1.0, 1.0],
        intended_bounds=spec["intended_bounds"],
        dynamic_bounds=spec.get("dynamic_bounds", []),
        learned_subfeatures=details,
        consensus_contributor_count=len(members),
        training_cluster_size=len(members),
        training_accept_count=support,
        holdout_accept_count=hold_support,
        training_similarity=similarity_distribution(scores),
        holdout_similarity=similarity_distribution(hold_scores),
        mask_population=int(mask.sum() // 255),
        group_mask_population=[
            int(np.count_nonzero(regions == g)) for g in range(1, len(atoms) + 1)
        ],
        neighbor_overlap_ratio=0.0,
        distance_from_intended_region=0.0,
        proposal_source="training_persistent_slots",
        structural_gates=dict(
            recurrent=True, nondegenerate_slots=True, separated_layout=True, arrangement=True
        ),
        spatial_edge_spread=[
            float((np.nonzero(regions)[1].max() - np.nonzero(regions)[1].min() + 1) / w),
            float((np.nonzero(regions)[0].max() - np.nonzero(regions)[0].min() + 1) / h),
        ],
    )
    stats.update(
        selected_candidate=selected,
        training_accept_count=support,
        holdout_accept_count=hold_support,
    )
    if hold_support < 3 or hold_support < 0.80 * support * len(heldout) / len(training):
        stats.update(reason="holdout_rejected", holdout_rejected=1)
        return None
    ys, xs = np.nonzero(full_allowed)
    left, top, right, bottom = int(xs.min()), int(ys.min()), int(xs.max() + 1), int(ys.max() + 1)
    bounds = [left / w, top / h, right / w, bottom / h]
    selected["roi_bounds"] = bounds
    selected["dimensions"] = [right - left, bottom - top]
    stats["reason"] = "selected"
    return (
        reference[top:bottom, left:right],
        bounds,
        mask[top:bottom, left:right],
        regions[top:bottom, left:right],
        full_allowed[top:bottom, left:right],
    )
