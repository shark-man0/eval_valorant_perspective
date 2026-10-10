"""Shared original-identity scene tracking; appearance never authorizes a fact.

Tracking consumes explicitly supplied source domains, not inferred world masks.
Original identities, reciprocal flow, source/adjacent camera consensus and complete
photometric support are retained without reseeding. Neither scene continuity nor
player facts are certified here. Native PTS ownership belongs to the episode layer.
"""

from __future__ import annotations

import hashlib
from typing import Any, cast

import cv2
import numpy as np
from numpy.typing import NDArray

from .scene_domains import Boxes, ImageU8, _ncc, _spread, _validate


def symmetric_affine_membership(
    source: Any,
    target: Any,
    model: Any,
    *,
    scale: int = 1,
) -> NDArray[np.uint8]:
    """Fixed final-model error in both pixel spaces; no image qualification."""
    source, target = np.asarray(source, dtype=float), np.asarray(target, dtype=float)
    if model is None or not np.isfinite(model).all():
        return np.zeros(len(source), np.uint8)
    homogeneous = np.vstack([model, [0.0, 0.0, 1.0]])
    if np.linalg.matrix_rank(homogeneous) != 3:
        return np.zeros(len(source), np.uint8)
    forward = np.column_stack([source, np.ones(len(source))]) @ homogeneous.T
    backward = np.column_stack([target, np.ones(len(target))]) @ np.linalg.inv(homogeneous).T
    return cast(
        NDArray[np.uint8],
        (
            (np.linalg.norm(forward[:, :2] - target, axis=1) <= 2 * scale)
            & (np.linalg.norm(backward[:, :2] - source, axis=1) <= 2 * scale)
        ).astype(np.uint8),
    )


def _validate_resolution(image: ImageU8, boxes: Boxes, scale: int) -> None:
    if type(scale) is not int or scale not in {1, 3}:
        raise ValueError("only canonical or native 1920x1080 resolution is supported")
    if scale == 1:
        _validate(image, boxes)
        return
    if image.dtype != np.uint8 or image.shape != (360 * scale, 640 * scale):
        raise ValueError("native grayscale uint8 image required")
    if not boxes:
        raise ValueError("explicit non-UI crops required")
    for x1, y1, x2, y2 in boxes:
        if not (0 <= x1 < x2 <= 640 * scale and 0 <= y1 < y2 <= 360 * scale):
            raise ValueError("crop outside image")
        if y1 < 28 * scale or (
            x1 < 416 * scale and x2 > 224 * scale and y1 < 120 * scale and y2 > 28 * scale
        ):
            raise ValueError("search crop intersects protected timer/phase pixels")
        if min(x2 - x1, y2 - y1) < 32 * scale:
            raise ValueError("crop too small")


class ReviewedWorldChain:
    def __init__(
        self,
        seed: ImageU8,
        boxes: Boxes,
        *,
        support_mode: str = "world_features",
        scale: int = 1,
        dense_footprint: str = "interior",
        seed_membership: str = "ransac_mask",
        world_mask: Any = None,
    ) -> None:
        if support_mode not in {
            "world_features",
            "dense_world",
            "adjacent_dense_world",
            "projected_world",
        }:
            raise ValueError("unknown descriptive support mode")
        self.support_mode = support_mode
        if dense_footprint not in {"interior", "full_valid"} or (
            dense_footprint != "interior"
            and support_mode not in {"adjacent_dense_world", "projected_world"}
        ):
            raise ValueError("full-valid footprint requires explicit adjacent dense mode")
        self.dense_footprint = dense_footprint
        if seed_membership not in {"ransac_mask", "symmetric_final"} or (
            seed_membership != "ransac_mask"
            and support_mode not in {"adjacent_dense_world", "projected_world"}
        ):
            raise ValueError("final membership requires explicit adjacent dense mode")
        self.seed_membership = seed_membership
        _validate_resolution(seed, boxes, scale)
        self.previous_world: Any = None
        if support_mode == "projected_world":
            if (
                scale != 1
                or dense_footprint != "full_valid"
                or seed_membership != "symmetric_final"
            ):
                raise ValueError("explicit canonical projected-world configuration required")
            _check_mask(seed, world_mask)
            if not all(world_mask[y1:y2, x1:x2].all() for x1, y1, x2, y2 in boxes):
                raise ValueError("complete source footprints must be reviewed world")
            self.previous_world = world_mask.copy()
        elif world_mask is not None:
            raise ValueError("world mask requires projected-world mode")
        self.scale = scale
        self.seed = seed.copy()
        self.boxes = boxes
        self.previous = seed.copy()
        self.previous_sha = hashlib.sha256(seed.tobytes()).hexdigest()
        # OpenCV array overloads vary across builds. Typing-only casts below
        # preserve the exact calls and their existing shape normalization.
        self.tracks: list[dict[str, Any]] = []
        self.seed_region_diagnostics: list[dict[str, Any]] = []
        for region, (x1, y1, x2, y2) in enumerate(boxes):
            crop = seed[y1:y2, x1:x2]
            corners = cv2.goodFeaturesToTrack(crop, 100, 0.01, 5 * scale)
            stats: dict[str, Any] = {
                "region": region,
                "crop_std": float(crop.std()),
                "raw_corners": 0 if corners is None else len(corners),
                "border_rejected": 0,
                "texture_rejected": 0,
                "seed_features": 0,
            }
            self.seed_region_diagnostics.append(stats)
            if corners is None:
                continue
            for point in corners.reshape(-1, 2):
                x, y = np.round(point).astype(int)
                if not (
                    16 * scale <= x < crop.shape[1] - 16 * scale
                    and 16 * scale <= y < crop.shape[0] - 16 * scale
                ):
                    stats["border_rejected"] += 1
                    continue
                radius = 15 * scale
                patch = crop[y - radius : y + radius + 1, x - radius : x + radius + 1].copy()
                if float(patch.std()) < 1:
                    stats["texture_rejected"] += 1
                    continue
                stats["seed_features"] += 1
                position = point + np.array([x1, y1])
                self.tracks.append(
                    {
                        "region": region,
                        "seed_xy": position.tolist(),
                        "seed_patch_origin": [int(x + x1 - radius), int(y + y1 - radius)],
                        "seed_patch": patch,
                        "current_xy": position.tolist(),
                    }
                )
        self.seed_features = len(self.tracks)
        self.previous_dense_regions = (
            {
                r["region"]
                for r in dense_world_regions(
                    seed,
                    seed,
                    boxes,
                    np.array([[1.0, 0.0, 0.0], [0.0, 1.0, 0.0]]),
                    scale=scale,
                    footprint=dense_footprint,
                )
                if r["supported"]
            }
            if support_mode in {"dense_world", "adjacent_dense_world", "projected_world"}
            else set()
        )

    def advance(
        self,
        current: ImageU8,
        *,
        discontinuity: bool = False,
        region_sink: list[dict[str, Any]] | None = None,
        model_sink: list[dict[str, Any]] | None = None,
        dense_model_sink: list[dict[str, Any]] | None = None,
        current_world: Any = None,
    ) -> dict[str, Any]:
        _validate_resolution(current, self.boxes, self.scale)
        scale = self.scale
        if self.support_mode == "projected_world":
            try:
                _check_mask(current, current_world)
            except ValueError:
                self.tracks = []
                return self._unknown("current_world_mask_missing_or_invalid")
            if not all(current_world[y1:y2, x1:x2].all() for x1, y1, x2, y2 in self.boxes):
                self.tracks = []
                return self._unknown("tracking_footprint_occluded_or_unreviewed")
        elif current_world is not None:
            raise ValueError("current world mask requires projected-world mode")
        margin, radius = 8 * scale, 7 * scale
        window = 20 * scale + 1
        region_stats: list[dict[str, Any]] = [{} for _ in self.boxes]
        if region_sink is not None:
            region_sink.extend(region_stats)

        def count(region: int, stage: str, amount: int = 1) -> None:
            if region_sink is not None:
                stats = region_stats[region]
                stats[stage] = stats.get(stage, 0) + amount

        for item in self.tracks:
            count(item["region"], "input_tracks")
        if discontinuity:
            self.tracks = []
            return self._unknown("content_discontinuity")
        digest = hashlib.sha256(current.tobytes()).hexdigest()
        if digest == self.previous_sha:
            self.tracks = []
            return self._unknown("duplicate_image")
        if not self.tracks:
            return self._unknown("chain_terminated")
        candidates = []
        for x1, y1, x2, y2 in self.boxes:
            selected = [
                t
                for t in self.tracks
                if x1 + margin <= t["current_xy"][0] < x2 - margin
                and y1 + margin <= t["current_xy"][1] < y2 - margin
            ]
            if not selected:
                continue
            for item in selected:
                count(item["region"], "selected")
            left = self.previous[y1:y2, x1:x2]
            right = current[y1:y2, x1:x2]
            points = cast(Any, np.float32)(
                [np.array(t["current_xy"]) - [x1, y1] for t in selected]
            ).reshape(-1, 1, 2)
            forward, ok, _ = cast(Any, cv2.calcOpticalFlowPyrLK)(
                left, right, points, None, winSize=(window, window), maxLevel=3
            )
            if forward is None:
                for item in selected:
                    count(item["region"], "flow_unavailable")
                continue
            if region_sink is not None:
                shadow, shadow_ok, eigen = cast(Any, cv2.calcOpticalFlowPyrLK)(
                    left,
                    right,
                    points,
                    None,
                    winSize=(window, window),
                    maxLevel=3,
                    flags=cv2.OPTFLOW_LK_GET_MIN_EIGENVALS,
                )
                if not (
                    np.array_equal(forward, shadow, equal_nan=True)
                    and np.array_equal(ok, shadow_ok)
                ):
                    raise ValueError("min-eigenvalue diagnostic changed forward flow")
                for item, yes, value in zip(selected, ok.ravel(), eigen.ravel(), strict=True):
                    if not yes:
                        count(
                            item["region"],
                            "forward_failed_below_default_min_eigen"
                            if value < 1e-4
                            else "forward_failed_other",
                        )
            back, back_ok, _ = cast(Any, cv2.calcOpticalFlowPyrLK)(
                right, left, forward, None, winSize=(window, window), maxLevel=3
            )
            if back is None:
                for item in selected:
                    count(item["region"], "flow_unavailable")
                continue
            if region_sink is not None:
                shadow, shadow_ok, eigen = cast(Any, cv2.calcOpticalFlowPyrLK)(
                    right,
                    left,
                    forward,
                    None,
                    winSize=(window, window),
                    maxLevel=3,
                    flags=cv2.OPTFLOW_LK_GET_MIN_EIGENVALS,
                )
                if not (
                    np.array_equal(back, shadow, equal_nan=True)
                    and np.array_equal(back_ok, shadow_ok)
                ):
                    raise ValueError("min-eigenvalue diagnostic changed backward flow")
                for item, yes, value in zip(selected, back_ok.ravel(), eigen.ravel(), strict=True):
                    if not yes:
                        count(
                            item["region"],
                            "backward_failed_below_default_min_eigen"
                            if value < 1e-4
                            else "backward_failed_other",
                        )
            for old, q, p, yes, back_yes in zip(
                selected,
                forward.reshape(-1, 2),
                back.reshape(-1, 2),
                ok.ravel(),
                back_ok.ravel(),
                strict=True,
            ):
                if not yes or not back_yes or not np.isfinite([q, p]).all():
                    count(old["region"], "flow_status_or_nonfinite")
                    continue
                fb = float(np.linalg.norm(p - (np.array(old["current_xy"]) - [x1, y1])))
                x, y = np.round(q).astype(int)
                ox, oy = np.round(np.array(old["current_xy"]) - [x1, y1]).astype(int)
                if fb > scale or not (
                    margin <= x < right.shape[1] - margin and margin <= y < right.shape[0] - margin
                ):
                    count(old["region"], "reciprocal_error_or_outside_crop")
                    continue
                a = left[oy - radius : oy + radius + 1, ox - radius : ox + radius + 1]
                b = right[y - radius : y + radius + 1, x - radius : x + radius + 1]
                score = _ncc(a, b)
                if score is None or score < 0.90:
                    count(
                        old["region"],
                        "adjacent_texture_unknown" if score is None else "adjacent_ncc_below_floor",
                    )
                    continue
                count(old["region"], "adjacent_candidates")
                candidates.append(
                    {
                        **old,
                        "current_xy": (q + [x1, y1]).tolist(),
                        "previous_xy": old["current_xy"],
                        "fb_error_px": fb,
                        "adjacent_patch_ncc": score,
                    }
                )
        if len(candidates) < 3 or len({t["region"] for t in candidates}) < 3:
            self.tracks = []
            return self._unknown("insufficient_reviewed_world_tracks", len(candidates), candidates)
        cv2.setRNGSeed(0)
        model, inliers = cast(Any, cv2.estimateAffinePartial2D)(
            cast(Any, np.float32)([t["seed_xy"] for t in candidates]),
            cast(Any, np.float32)([t["current_xy"] for t in candidates]),
            method=cv2.RANSAC,
            ransacReprojThreshold=2 * scale,
        )
        if model_sink is not None:
            model_sink.append(
                {
                    "seed_points": cast(Any, np.float32)(
                        [t["seed_xy"] for t in candidates]
                    ).tolist(),
                    "current_points": cast(Any, np.float32)(
                        [t["current_xy"] for t in candidates]
                    ).tolist(),
                    "previous_points": cast(Any, np.float32)(
                        [t["previous_xy"] for t in candidates]
                    ).tolist(),
                    "regions": [t["region"] for t in candidates],
                    "adjacent_patch_ncc": [t["adjacent_patch_ncc"] for t in candidates],
                    "original_partial_affine": model.tolist() if model is not None else None,
                    "original_inliers": inliers.reshape(-1).tolist()
                    if inliers is not None
                    else None,
                }
            )
        if model is None or not np.isfinite(model).all() or inliers is None:
            self.tracks = []
            return self._unknown("seed_model_unavailable", len(candidates))
        if int(inliers.sum()) < 0.90 * len(candidates):
            self.tracks = []
            return self._unknown("seed_model_incoherent", len(candidates))
        if self.seed_membership == "symmetric_final":
            inliers = symmetric_affine_membership(
                cast(Any, np.float32)([t["seed_xy"] for t in candidates]),
                cast(Any, np.float32)([t["current_xy"] for t in candidates]),
                model,
                scale=scale,
            )
            if model_sink is not None:
                model_sink[-1]["selected_seed_inliers"] = inliers.tolist()
            if int(inliers.sum()) < 0.90 * len(candidates):
                self.tracks = []
                return self._unknown("final_seed_model_incoherent", len(candidates))
        retained = []
        for item, inlier in zip(candidates, inliers.reshape(-1), strict=True):
            if not inlier:
                count(item["region"], "affine_outlier")
                continue
            count(item["region"], "affine_inliers")
            x, y = np.round(item["current_xy"]).astype(int)
            local = model.copy()
            local[:, 2] += model[:, :2] @ np.array(item["seed_patch_origin"]) - [
                x - radius,
                y - radius,
            ]
            patch_size = (2 * radius + 1, 2 * radius + 1)
            patch = cv2.warpAffine(item["seed_patch"], local, patch_size, flags=cv2.INTER_LINEAR)
            valid = cv2.warpAffine(
                np.full(item["seed_patch"].shape, 255, np.uint8),
                local,
                patch_size,
                flags=cv2.INTER_LINEAR,
            )
            if not (valid == 255).all():
                count(item["region"], "seed_warp_invalid_footprint")
                continue
            score = _ncc(patch, current[y - radius : y + radius + 1, x - radius : x + radius + 1])
            if score is not None and score >= 0.90:
                count(item["region"], "retained")
                retained.append({**item, "original_seed_patch_ncc": score})
            else:
                count(
                    item["region"],
                    "seed_texture_unknown" if score is None else "seed_ncc_below_floor",
                )
        feature_spread = _spread([t["previous_xy"] for t in retained], scale) and _spread(
            [t["current_xy"] for t in retained], scale
        )
        dense_regions = []
        if self.support_mode in {"dense_world", "adjacent_dense_world", "projected_world"}:
            dense_source = self.seed
            dense_model = model
            if self.support_mode in {"adjacent_dense_world", "projected_world"}:
                if len(retained) < 3 or len({t["region"] for t in retained}) < 3:
                    self.tracks = []
                    return self._unknown(
                        "original_world_support_insufficient", len(retained), retained
                    )
                cv2.setRNGSeed(0)
                dense_model, adjacent_inliers = cast(Any, cv2.estimateAffinePartial2D)(
                    cast(Any, np.float32)([t["previous_xy"] for t in retained]),
                    cast(Any, np.float32)([t["current_xy"] for t in retained]),
                    method=cv2.RANSAC,
                    ransacReprojThreshold=2 * scale,
                )
                if (
                    dense_model is None
                    or not np.isfinite(dense_model).all()
                    or adjacent_inliers is None
                ):
                    self.tracks = []
                    return self._unknown(
                        "adjacent_world_model_unavailable", len(retained), retained
                    )
                adjacent_kept = [
                    t for t, yes in zip(retained, adjacent_inliers.ravel(), strict=True) if yes
                ]
                if (
                    len(adjacent_kept) < 0.90 * len(retained)
                    or len({t["region"] for t in adjacent_kept}) < 3
                ):
                    self.tracks = []
                    return self._unknown("adjacent_world_model_incoherent", len(retained), retained)
                retained = adjacent_kept
                dense_source = self.previous
            if dense_model_sink is not None:
                dense_model_sink.append(
                    {
                        "model": dense_model.tolist(),
                        "retained_regions": [t["region"] for t in retained],
                        "previous_xy": [t["previous_xy"] for t in retained],
                        "current_xy": [t["current_xy"] for t in retained],
                    }
                )
            if self.support_mode == "projected_world":
                dense_regions = projected_world_regions(
                    dense_source,
                    current,
                    self.boxes,
                    dense_model,
                    self.previous_world,
                    current_world,
                )
                for row in dense_regions:
                    row["center_xy"] = row.get("projected_center_xy", row["source_center_xy"])
            else:
                dense_regions = dense_world_regions(
                    dense_source,
                    current,
                    self.boxes,
                    dense_model,
                    scale=scale,
                    footprint=self.dense_footprint,
                )
            centers = [
                r["center_xy"]
                for r in dense_regions
                if r["supported"] and r["region"] in self.previous_dense_regions
            ]
            spatial_supported = len(centers) >= 3 and _spread(centers, scale)
            if self.support_mode == "projected_world":
                source_centers = [
                    r["source_center_xy"]
                    for r in dense_regions
                    if r["supported"] and r["region"] in self.previous_dense_regions
                ]
                spatial_supported = spatial_supported and _spread(source_centers, scale)
        else:
            spatial_supported = feature_spread
        if len(retained) < 3 or len({t["region"] for t in retained}) < 3 or not spatial_supported:
            self.tracks = []
            result = self._unknown("original_world_support_insufficient", len(retained), retained)
            if self.support_mode in {"dense_world", "adjacent_dense_world", "projected_world"}:
                result["dense_world_regions"] = dense_regions
                result["previous_dense_regions"] = sorted(self.previous_dense_regions)
            return result
        self.tracks = retained
        self.previous = current.copy()
        self.previous_sha = digest
        if self.support_mode == "projected_world":
            self.previous_world = current_world.copy()
        if self.support_mode in {"dense_world", "adjacent_dense_world", "projected_world"}:
            self.previous_dense_regions = {r["region"] for r in dense_regions if r["supported"]}
        return {
            "reason": "descriptive_reviewed_world_chain",
            "support_mode": self.support_mode,
            "feature_spread_supported": feature_spread,
            "dense_world_regions": dense_regions,
            "seed_features": self.seed_features,
            "retained_features": len(retained),
            "regions": sorted({t["region"] for t in retained}),
            "minimum_adjacent_ncc": min(t["adjacent_patch_ncc"] for t in retained),
            "minimum_seed_ncc": min(t["original_seed_patch_ncc"] for t in retained),
            "descriptive_supported": True,
            "runtime_proof_authorized": False,
        }

    def _unknown(
        self,
        reason: str,
        features: int = 0,
        tracks: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        tracks = tracks or []
        return {
            "reason": reason,
            "seed_features": self.seed_features,
            "retained_features": features,
            "retained_regions": sorted({t["region"] for t in tracks}),
            "previous_witness_cells": sorted(
                {
                    (
                        int(t["previous_xy"][1] / (120 * self.scale)),
                        int(t["previous_xy"][0] / (640 * self.scale / 3)),
                    )
                    for t in tracks
                }
            ),
            "current_witness_cells": sorted(
                {
                    (
                        int(t["current_xy"][1] / (120 * self.scale)),
                        int(t["current_xy"][0] / (640 * self.scale / 3)),
                    )
                    for t in tracks
                }
            ),
            "descriptive_supported": False,
            "runtime_proof_authorized": False,
        }


def dense_world_regions(
    seed: ImageU8,
    current: ImageU8,
    boxes: Boxes,
    model: Any,
    *,
    scale: int = 1,
    footprint: str = "interior",
) -> list[dict[str, Any]]:
    """Warp each reviewed source crop locally; never import excluded pixels."""
    if footprint not in {"interior", "full_valid"}:
        raise ValueError("unknown source footprint")
    result = []
    for region, (x1, y1, x2, y2) in enumerate(boxes):
        crop = seed[y1:y2, x1:x2]
        local = model.copy()
        local[:, 2] += model[:, :2] @ np.array([x1, y1]) - [x1, y1]
        size = (x2 - x1, y2 - y1)
        aligned = cv2.warpAffine(crop, local, size, flags=cv2.INTER_LINEAR)
        if footprint == "full_valid":
            # Check coverage directly in [0,1] to reject sampled padding.
            valid = (
                cv2.warpAffine(np.ones(crop.shape, np.float32), local, size, flags=cv2.INTER_LINEAR)
                == 1.0
            )
            population = crop.size
        else:
            valid = (
                cv2.warpAffine(
                    np.full(crop.shape, 255, np.uint8), local, size, flags=cv2.INTER_LINEAR
                )
                == 255
            )
            interior = np.zeros(crop.shape, bool)
            margin = 8 * scale
            interior[margin:-margin, margin:-margin] = True
            valid &= interior
            population = int(interior.sum())
        count = int(valid.sum())
        fraction = count / population
        score = None
        if count >= 32 * scale * scale and fraction >= 0.90:
            score = _ncc(aligned[valid].reshape(-1, 1), current[y1:y2, x1:x2][valid].reshape(-1, 1))
        result.append(
            {
                "region": region,
                "ncc": score,
                "valid_fraction": fraction,
                "center_xy": [(x1 + x2) / 2, (y1 + y2) / 2],
                "supported": score is not None and score >= 0.90,
            }
        )
    return result


def _check_mask(image: ImageU8, mask: Any) -> None:
    if not isinstance(mask, np.ndarray) or mask.dtype != np.bool_ or mask.shape != image.shape:
        raise ValueError("explicit same-shape boolean world mask required")
    if mask[:28].any() or mask[28:120, 224:416].any():
        raise ValueError("world mask imports protected timer/phase pixels")


def projected_world_regions(
    previous: ImageU8,
    current: ImageU8,
    boxes: Boxes,
    model: Any,
    previous_world: Any,
    current_world: Any,
) -> list[dict[str, Any]]:
    """Sample current pixels only where every interpolation tap is reviewed."""
    _validate_resolution(previous, boxes, 1)
    _validate_resolution(current, boxes, 1)
    _check_mask(previous, previous_world)
    _check_mask(current, current_world)
    model = np.asarray(model, dtype=float)
    if model.shape != (2, 3) or not np.isfinite(model).all():
        raise ValueError("finite independently measured partial-affine transform required")
    if abs(np.linalg.det(model[:, :2])) < 1e-8:
        raise ValueError("nondegenerate source-camera transform required")
    results = []
    world = current_world.astype(np.float32)
    for region, (x1, y1, x2, y2) in enumerate(boxes):
        row: dict[str, Any] = {
            "region": region,
            "valid_fraction": 0.0,
            "ncc": None,
            "supported": False,
            "runtime_proof_authorized": False,
            "source_center_xy": [(x1 + x2) / 2, (y1 + y2) / 2],
        }
        if not previous_world[y1:y2, x1:x2].all():
            row["reason"] = "source_footprint_not_fully_reviewed"
            results.append(row)
            continue
        yy, xx = np.mgrid[y1:y2, x1:x2]
        mx = (model[0, 0] * xx + model[0, 1] * yy + model[0, 2]).astype(np.float32)
        my = (model[1, 0] * xx + model[1, 1] * yy + model[1, 2]).astype(np.float32)
        validity = cv2.remap(world, mx, my, cv2.INTER_LINEAR, borderMode=cv2.BORDER_CONSTANT)
        valid = validity == 1.0
        aligned = cv2.remap(current, mx, my, cv2.INTER_LINEAR, borderMode=cv2.BORDER_CONSTANT)
        crop = previous[y1:y2, x1:x2]
        count = int(valid.sum())
        row["valid_fraction"] = count / crop.size
        row["projected_center_xy"] = (
            model @ np.array([(x1 + x2) / 2, (y1 + y2) / 2, 1.0])
        ).tolist()
        if count < 32 or row["valid_fraction"] < 0.90:
            row["reason"] = "projected_review_coverage_insufficient"
        else:
            score = _ncc(crop[valid].reshape(-1, 1), aligned[valid].reshape(-1, 1))
            row["ncc"] = score
            row["supported"] = score is not None and score >= 0.90
            row["reason"] = (
                "descriptive_projected_world" if row["supported"] else "appearance_unknown"
            )
        results.append(row)
    return results
