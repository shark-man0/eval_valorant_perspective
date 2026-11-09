"""Opt-in image-only public Map reference candidates, without marker ownership."""

from __future__ import annotations

import hashlib
import importlib
from copy import deepcopy
from pathlib import Path
from typing import Any, cast

import cv2
import numpy as np
from numpy.typing import NDArray

from valorant_ai_coach.hud.layout import HudLayout

from .evidence import digest
from .replay import file_sha, read_json


class PublicMapPixels:
    """Match static map edges against an explicitly versioned external catalog.

    This first geometric matcher tolerates rotation and partial maps. Its
    similarity transform remains a hypothesis, not a qualified marker transform or Zone.
    """

    def __init__(self, index_path: Path, layout_path: Path) -> None:
        index = read_json(index_path)
        root = index_path.parent.resolve()
        self.layout = HudLayout.load(layout_path)
        self.orb: Any = cast(Any, cv2).SIFT_create(nfeatures=1200, contrastThreshold=0.008)
        self.matcher = cv2.FlannBasedMatcher(dict(algorithm=1, trees=3), dict(checks=32))
        self.references = []
        assets = {}
        for record in index["maps"]:
            path = (root / record["reference"]).resolve()
            if root not in path.parents:
                raise ValueError("Map reference outside catalog")
            if not path.is_file():
                continue
            image = cv2.imread(str(path), cv2.IMREAD_UNCHANGED)
            if image is None or image.ndim != 3:
                raise ValueError("Readable public map reference required")
            gray = cv2.cvtColor(image[:, :, :3], cv2.COLOR_BGR2GRAY)
            if image.shape[2] == 4:
                gray[image[:, :, 3] == 0] = 0
            keypoints, descriptors = self.orb.detectAndCompute(gray, None)
            if descriptors is not None:
                self.references.append((record["name"], record["id"], keypoints, descriptors))
            assets[record["id"]] = file_sha(path)
        if not self.references:
            raise ValueError("Readable map reference features required")
        self.bindings = {
            "version": "development_public_map_features_v1",
            "index_sha256": file_sha(index_path),
            "asset_sha256s": assets,
            "catalog_version": index["catalog_version"],
            "layout_sha256": file_sha(layout_path),
            "code_sha256": file_sha(Path(__file__)),
            "opencv": cv2.__version__,
            "numpy": np.__version__,
            "SIFT_features": 1200,
            "ratio": 0.75,
            "RANSAC_pixels": 3,
            "minimum_inliers": 20,
            "minimum_ratio": 0.55,
            "minimum_inlier_margin": 10,
            "minimum_ROI_hull_fraction": 0.08,
        }
        self.fingerprint = digest(self.bindings)

    def inspect(self, image: NDArray[np.uint8]) -> dict[str, Any]:
        if image.dtype != np.uint8 or image.ndim != 3 or image.shape[2] != 3:
            raise ValueError("Native BGR pixels required")
        h, w = image.shape[:2]
        left, top, right, bottom = self.layout.normalized_roi("minimap_normal").pixel_bounds(w, h)
        crop = image[top:bottom, left:right]
        gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
        keypoints, descriptors = self.orb.detectAndCompute(gray, None)
        ranking = []
        if descriptors is not None and len(keypoints) >= 4:
            for name, identity, reference_points, reference_descriptors in self.references:
                pairs = self.matcher.knnMatch(reference_descriptors, descriptors, k=2)
                good = [p[0] for p in pairs if len(p) == 2 and p[0].distance < 0.75 * p[1].distance]
                unique: dict[int, Any] = {}
                for match in sorted(good, key=lambda m: m.distance):
                    unique.setdefault(match.trainIdx, match)
                good = list(unique.values())
                if len(good) < 4:
                    continue
                source = np.asarray(
                    [reference_points[m.queryIdx].pt for m in good], dtype=np.float32
                )
                target = np.asarray([keypoints[m.trainIdx].pt for m in good], dtype=np.float32)
                affine, mask = cv2.estimateAffinePartial2D(
                    source, target, method=cv2.RANSAC, ransacReprojThreshold=3
                )
                count = int(mask.sum()) if mask is not None else 0
                if affine is None or not np.isfinite(affine).all() or mask is None:
                    continue
                scale = float(np.linalg.norm(affine[:, 0]))
                selected = target[mask.ravel().astype(bool)]
                coverage = (
                    float(cv2.contourArea(cv2.convexHull(selected))) / gray.size
                    if len(selected) >= 3
                    else 0
                )
                if not 0.1 <= scale <= 3 or coverage < 0.08:
                    continue
                matrix = np.vstack([affine, [0, 0, 1]])
                ranking.append(
                    {
                        "map_id": identity,
                        "map_name": name,
                        "inliers": count,
                        "matches": len(good),
                        "inlier_ratio": count / len(good),
                        "reference_to_roi_homography_candidate": matrix.tolist(),
                        "ownership": "UNKNOWN",
                        "qualified": False,
                    }
                )
        ranking.sort(key=lambda c: (-c["inliers"], c["map_name"]))
        accepted = []
        if ranking:
            best = ranking[0]
            margin = best["inliers"] - (ranking[1]["inliers"] if len(ranking) > 1 else 0)
            if best["inliers"] >= 20 and best["inlier_ratio"] >= 0.55 and margin >= 10:
                accepted = [
                    {
                        **best,
                        "evidence": "public_reference_feature_alignment",
                        "confidence": None,
                        "position_authority": False,
                        "catalog_version": self.bindings["catalog_version"],
                    }
                ]
        return {
            "signals": [],
            "context": {"stream_kind": "public_map_reference"},
            "map_candidates": [],
            "raw": {
                "schema": "development_generic_map_pixels_v1",
                "method": self.bindings["version"],
                "map_name_candidates": accepted,
                "zone_candidates": [],
                "reference_ranking": ranking[:3],
                "roi_pixel_bounds": [left, top, right, bottom],
                "roi_pixel_sha256": hashlib.sha256(crop.tobytes()).hexdigest(),
                "marker_transform_qualified": False,
                "ownership": "UNKNOWN",
                "formal_outputs": 0,
            },
        }


class PublicMapSupplementObserver:
    """Explicit optional native supplier; original pools and signals stay intact."""

    def __init__(self, config_path: Path) -> None:
        cfg = read_json(config_path)
        if set(cfg) != {"parent_observer", "parent_config", "catalog_index", "layout"}:
            raise ValueError("Explicit parent and public Map reference config required")
        module, name = cfg["parent_observer"].split(":", 1)
        self.parent = getattr(importlib.import_module(module), name)(Path(cfg["parent_config"]))
        self.map = PublicMapPixels(Path(cfg["catalog_index"]), Path(cfg["layout"]))
        self.bindings = {
            "parent": self.parent.bindings,
            "parent_fingerprint": self.parent.fingerprint,
            "public_map": self.map.bindings,
            "config_sha256": file_sha(config_path),
            "baseline_producer_fingerprints": self.parent.bindings.get(
                "baseline_producer_fingerprints", [self.parent.fingerprint]
            ),
            "supplier_producer_fingerprints": [
                *self.parent.bindings.get(
                    "supplier_producer_fingerprints", [self.parent.fingerprint]
                ),
                self.map.fingerprint,
            ],
            "map_reader_status": "CONFIGURED_DEVELOPMENT_CANDIDATES",
        }
        self.fingerprint = digest(self.bindings)

    def inspect(self, image: NDArray[np.uint8]) -> dict[str, Any]:
        result: dict[str, Any] = deepcopy(self.parent.inspect(image))
        suppliers = result.get("supplier_observations")
        if suppliers is None:
            suppliers = [
                {k: deepcopy(result[k]) for k in ("signals", "raw", "context", "map_candidates")}
            ]
            suppliers[0]["producer_fingerprint"] = self.parent.fingerprint
        suppliers.append({**self.map.inspect(image), "producer_fingerprint": self.map.fingerprint})
        result["supplier_observations"] = suppliers
        return result
