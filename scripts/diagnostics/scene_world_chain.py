"""Track reviewed world identities along native source frames; diagnostic only.

Only the initial reviewed world patches may provide identities. No reseeding,
foreground/background inference, timer/phase input or runtime proof is allowed.
Every successful link retains both reciprocal local flow and original-seed
photometric support. Missing distributed support terminates the chain.
"""

from __future__ import annotations

import hashlib

import cv2
import numpy as np

from scripts.diagnostics.scene_patch_search import _validate


def _ncc(a, b):
    if min(float(a.std()), float(b.std())) < 1:
        return None
    result = float(cv2.matchTemplate(a, b, cv2.TM_CCOEFF_NORMED)[0, 0])
    return result if np.isfinite(result) else None


def _spread(points):
    cells = {(int(y / 120), int(x / (640 / 3))) for x, y in points}
    return len(cells) >= 3 and len({r for r, c in cells}) >= 2 and len({c for r, c in cells}) >= 2


class ReviewedWorldChain:
    def __init__(self, seed, boxes, *, support_mode="world_features"):
        if support_mode not in {"world_features", "dense_world"}:
            raise ValueError("unknown descriptive support mode")
        self.support_mode = support_mode
        self.seed = seed.copy()
        _validate(seed, boxes)
        self.boxes = boxes
        self.previous = seed.copy()
        self.previous_sha = hashlib.sha256(seed.tobytes()).hexdigest()
        self.tracks = []
        for region, (x1, y1, x2, y2) in enumerate(boxes):
            crop = seed[y1:y2, x1:x2]
            corners = cv2.goodFeaturesToTrack(crop, 100, 0.01, 5)
            if corners is None:
                continue
            for point in corners.reshape(-1, 2):
                x, y = np.round(point).astype(int)
                if not (16 <= x < crop.shape[1] - 16 and 16 <= y < crop.shape[0] - 16):
                    continue
                patch = crop[y - 15 : y + 16, x - 15 : x + 16].copy()
                if float(patch.std()) < 1:
                    continue
                position = point + np.array([x1, y1])
                self.tracks.append(
                    {
                        "region": region,
                        "seed_xy": position.tolist(),
                        "seed_patch_origin": [int(x + x1 - 15), int(y + y1 - 15)],
                        "seed_patch": patch,
                        "current_xy": position.tolist(),
                    }
                )
        self.seed_features = len(self.tracks)
        self.previous_dense_regions = (
            {
                r["region"]
                for r in dense_world_regions(
                    seed, seed, boxes, np.array([[1.0, 0.0, 0.0], [0.0, 1.0, 0.0]])
                )
                if r["supported"]
            }
            if support_mode == "dense_world"
            else set()
        )

    def advance(self, current, *, discontinuity=False):
        _validate(current, self.boxes)
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
                if x1 + 8 <= t["current_xy"][0] < x2 - 8 and y1 + 8 <= t["current_xy"][1] < y2 - 8
            ]
            if not selected:
                continue
            left = self.previous[y1:y2, x1:x2]
            right = current[y1:y2, x1:x2]
            points = np.float32([np.array(t["current_xy"]) - [x1, y1] for t in selected]).reshape(
                -1, 1, 2
            )
            forward, ok, _ = cv2.calcOpticalFlowPyrLK(
                left, right, points, None, winSize=(21, 21), maxLevel=3
            )
            if forward is None:
                continue
            back, back_ok, _ = cv2.calcOpticalFlowPyrLK(
                right, left, forward, None, winSize=(21, 21), maxLevel=3
            )
            if back is None:
                continue
            for old, q, p, yes, back_yes in zip(
                selected,
                forward.reshape(-1, 2),
                back.reshape(-1, 2),
                ok.ravel(),
                back_ok.ravel(),
                strict=True,
            ):
                if not yes or not back_yes or not np.isfinite([q, p]).all():
                    continue
                fb = float(np.linalg.norm(p - (np.array(old["current_xy"]) - [x1, y1])))
                x, y = np.round(q).astype(int)
                ox, oy = np.round(np.array(old["current_xy"]) - [x1, y1]).astype(int)
                if fb > 1 or not (8 <= x < right.shape[1] - 8 and 8 <= y < right.shape[0] - 8):
                    continue
                a = left[oy - 7 : oy + 8, ox - 7 : ox + 8]
                b = right[y - 7 : y + 8, x - 7 : x + 8]
                score = _ncc(a, b)
                if score is None or score < 0.90:
                    continue
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
        model, inliers = cv2.estimateAffinePartial2D(
            np.float32([t["seed_xy"] for t in candidates]),
            np.float32([t["current_xy"] for t in candidates]),
            method=cv2.RANSAC,
            ransacReprojThreshold=2,
        )
        if model is None or not np.isfinite(model).all() or inliers is None:
            self.tracks = []
            return self._unknown("seed_model_unavailable", len(candidates))
        if int(inliers.sum()) < 0.90 * len(candidates):
            self.tracks = []
            return self._unknown("seed_model_incoherent", len(candidates))
        retained = []
        for item, inlier in zip(candidates, inliers.reshape(-1), strict=True):
            if not inlier:
                continue
            x, y = np.round(item["current_xy"]).astype(int)
            local = model.copy()
            local[:, 2] += model[:, :2] @ np.array(item["seed_patch_origin"]) - [x - 7, y - 7]
            patch = cv2.warpAffine(item["seed_patch"], local, (15, 15), flags=cv2.INTER_LINEAR)
            valid = cv2.warpAffine(
                np.full((31, 31), 255, np.uint8), local, (15, 15), flags=cv2.INTER_LINEAR
            )
            if not (valid == 255).all():
                continue
            score = _ncc(patch, current[y - 7 : y + 8, x - 7 : x + 8])
            if score is not None and score >= 0.90:
                retained.append({**item, "original_seed_patch_ncc": score})
        feature_spread = _spread([t["previous_xy"] for t in retained]) and _spread(
            [t["current_xy"] for t in retained]
        )
        dense_regions = []
        if self.support_mode == "dense_world":
            dense_regions = dense_world_regions(self.seed, current, self.boxes, model)
            centers = [
                r["center_xy"]
                for r in dense_regions
                if r["supported"] and r["region"] in self.previous_dense_regions
            ]
            spatial_supported = len(centers) >= 3 and _spread(centers)
        else:
            spatial_supported = feature_spread
        if len(retained) < 3 or len({t["region"] for t in retained}) < 3 or not spatial_supported:
            self.tracks = []
            result = self._unknown("original_world_support_insufficient", len(retained), retained)
            if self.support_mode == "dense_world":
                result["dense_world_regions"] = dense_regions
                result["previous_dense_regions"] = sorted(self.previous_dense_regions)
            return result
        self.tracks = retained
        self.previous = current.copy()
        self.previous_sha = digest
        if self.support_mode == "dense_world":
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

    def _unknown(self, reason, features=0, tracks=None):
        tracks = tracks or []
        return {
            "reason": reason,
            "seed_features": self.seed_features,
            "retained_features": features,
            "retained_regions": sorted({t["region"] for t in tracks}),
            "previous_witness_cells": sorted(
                {
                    (int(t["previous_xy"][1] / 120), int(t["previous_xy"][0] / (640 / 3)))
                    for t in tracks
                }
            ),
            "current_witness_cells": sorted(
                {
                    (int(t["current_xy"][1] / 120), int(t["current_xy"][0] / (640 / 3)))
                    for t in tracks
                }
            ),
            "descriptive_supported": False,
            "runtime_proof_authorized": False,
        }


def dense_world_regions(seed, current, boxes, model):
    """Warp each reviewed source crop locally; never import excluded pixels."""
    result = []
    for region, (x1, y1, x2, y2) in enumerate(boxes):
        crop = seed[y1:y2, x1:x2]
        local = model.copy()
        local[:, 2] += model[:, :2] @ np.array([x1, y1]) - [x1, y1]
        size = (x2 - x1, y2 - y1)
        aligned = cv2.warpAffine(crop, local, size, flags=cv2.INTER_LINEAR)
        valid = (
            cv2.warpAffine(np.full(crop.shape, 255, np.uint8), local, size, flags=cv2.INTER_LINEAR)
            == 255
        )
        interior = np.zeros(crop.shape, bool)
        interior[8:-8, 8:-8] = True
        valid &= interior
        count = int(valid.sum())
        fraction = count / int(interior.sum())
        score = None
        if count >= 32 and fraction >= 0.90:
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
