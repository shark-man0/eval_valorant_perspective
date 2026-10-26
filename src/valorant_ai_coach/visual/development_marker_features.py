"""Local, opt-in appearance features. No downloads, actor or geometry inference.

Learned scores are development hypotheses, never calibrated probabilities. Model
bytes, preprocessing and classifier parameters enter independent fingerprints.
The default detector does not import or invoke this experimental module.
"""

from __future__ import annotations

import hashlib
import importlib
import io
import json
import math
from copy import deepcopy
from pathlib import Path
from typing import Any

import cv2
import numpy as np
from numpy.typing import NDArray

from .development_marker_attribution import freeze_native_sample

Array = NDArray[Any]
CLASSES = ("PLAYER", "DEATH_MARKER", "UI", "BACKGROUND")


def _digest(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, allow_nan=False,
                                     separators=(",", ":")).encode()).hexdigest()


def _patches(patches: list[Array]) -> None:
    if not isinstance(patches, list) or not 1 <= len(patches) <= 256:
        raise ValueError("One to 256 local patches required")
    if any(not isinstance(p, np.ndarray) or p.dtype != np.uint8 or p.ndim != 3
           or p.shape[2] != 3 or min(p.shape[:2]) < 5
           or max(p.shape[:2]) > 129 for p in patches):
        raise ValueError("Bounded native uint8 BGR patches required")


def _torch_runtime() -> Any:
    torch = importlib.import_module("torch")
    try:
        version = tuple(int(p) for p in str(torch.__version__).split(".")[:2])
    except (AttributeError, ValueError) as exc:
        raise ValueError("Known patched Torch runtime required") from exc
    # GHSA-63cw-57p8-fm3p: weights_only checkpoints were unsafe through 2.9.1.
    if len(version) != 2 or version < (2, 10):
        raise ValueError("Torch >=2.10 required for patched weights-only loading")
    return torch


def _private_model_output(path: Path) -> None:
    target = path.resolve()
    if any((parent/".git").exists() for parent in target.parents):
        raise ValueError("Learned model outputs must remain outside Git checkouts")


def bound_patches(
    frame: Array, sample: dict[str, Any], centers: list[list[float]], *, radius: int = 12,
) -> tuple[list[Array], str]:
    """Copy complete local windows from one exactly native-bound frame.

    Clipped windows are rejected rather than padded into invented observations.
    Candidate centers are unchanged; feature extraction cannot repair localization.
    """
    if (not isinstance(frame, np.ndarray) or frame.dtype != np.uint8 or frame.ndim != 3
            or frame.shape[2] != 3 or type(radius) is not int or not 2 <= radius <= 64):
        raise ValueError("Native frame and bounded integer patch radius required")
    bound = freeze_native_sample(sample, frame_size_px=(frame.shape[1], frame.shape[0]))
    pixels = hashlib.sha256(frame.tobytes()).hexdigest()
    if sample != bound or pixels != bound["native_pixel_sha256"]:
        raise ValueError("Native frame identity mismatch")
    if not isinstance(centers, list) or not 1 <= len(centers) <= 256:
        raise ValueError("Bounded explicit candidate centers required")
    patches = []
    for center in centers:
        if (not isinstance(center, list) or len(center) != 2
                or any(type(v) not in (int, float) or not math.isfinite(v) for v in center)):
            raise ValueError("Finite two-dimensional centers required")
        x, y = (round(v) for v in center)
        if not (radius <= x < frame.shape[1]-radius
                and radius <= y < frame.shape[0]-radius):
            raise ValueError("Candidate patch clips native frame")
        patches.append(frame[y-radius:y+radius+1, x-radius:x+radius+1].copy())
    if hashlib.sha256(frame.tobytes()).hexdigest() != pixels:
        raise ValueError("Frame changed during patch acquisition")
    return patches, _digest({"sample": bound, "centers": centers, "radius": radius,
                             "patch_sha256": [hashlib.sha256(p.tobytes()).hexdigest()
                                              for p in patches]})


def handcrafted_features(patches: list[Array]) -> Array:
    """Fixed color/gradient baseline; labels and temporal identity are unused."""
    _patches(patches)
    rows = []
    for patch in patches:
        small = cv2.resize(patch, (8, 8), interpolation=cv2.INTER_AREA).astype(np.float32)/255
        gray = cv2.cvtColor(patch, cv2.COLOR_BGR2GRAY).astype(np.float32)/255
        gx, gy = np.gradient(gray)
        hist: Array = np.histogram(np.arctan2(gy, gx), bins=8, range=(-np.pi, np.pi),
                            weights=np.hypot(gx, gy))[0]
        hist = hist/(np.linalg.norm(hist)+1e-8)
        rows.append(np.concatenate([small.ravel(), hist]))
    return np.asarray(rows, dtype=np.float32)


class FrozenMobileNetFeatures:
    """Explicit local Torchvision V3-small weights, CPU inference, no network.

    Torch/torchvision are optional research dependencies, loaded on construction.
    Global224 and local64 are different predeclared feature experiments. Resizing
    tiny patches adds no original pixel information and is not super-resolution.
    """

    def __init__(self, path: Path, expected_sha256: str, *, view: str = "local64") -> None:
        if view not in {"local64", "global224"}:
            raise ValueError("Explicit supported feature view required")
        self.path, self.expected_sha256, self.view = path, expected_sha256, view
        content = self._bytes()
        self.torch = _torch_runtime()
        models = importlib.import_module("torchvision.models")
        model = models.mobilenet_v3_small(weights=None)
        state = self.torch.load(io.BytesIO(content), map_location="cpu", weights_only=True)
        model.load_state_dict(state, strict=True)
        self.model = model.features[:4] if view == "local64" else model.features
        self.model.eval().requires_grad_(False)
        self._bytes()
        self.fingerprint = _digest({"method": "frozen_mobilenet_v3_small_v1",
                                    "weights_sha256": expected_sha256, "view": view,
                                    "torch": self.torch.__version__,
                                    "torchvision": importlib.import_module(
                                        "torchvision").__version__,
                                    "preprocess": "BGR_RGB_area_64_or224_imagenet_norm",
                                    "pool": "2x2_local_or1x1_global"})

    def _bytes(self) -> bytes:
        if (not isinstance(self.expected_sha256, str) or len(self.expected_sha256) != 64
                or not self.path.is_file() or self.path.stat().st_size > 16*1024**2):
            raise ValueError("Bounded explicit local model and SHA required")
        content = self.path.read_bytes()
        if hashlib.sha256(content).hexdigest() != self.expected_sha256:
            raise ValueError("Feature model bytes changed")
        return content

    def extract(self, patches: list[Array]) -> Array:
        _patches(patches)
        self._bytes()
        size = 64 if self.view == "local64" else 224
        rows = []
        with self.torch.inference_mode():
            for start in range(0, len(patches), 32):
                images = np.stack([cv2.resize(p[:, :, ::-1], (size, size),
                                             interpolation=cv2.INTER_AREA)
                                   for p in patches[start:start+32]])
                tensor = self.torch.from_numpy(images.copy()).permute(0, 3, 1, 2).float()/255
                mean = self.torch.tensor([.485, .456, .406])[None, :, None, None]
                std = self.torch.tensor([.229, .224, .225])[None, :, None, None]
                features = self.model((tensor-mean)/std)
                pooled = self.torch.nn.functional.adaptive_avg_pool2d(
                    features, 2 if self.view == "local64" else 1)
                rows.append(pooled.flatten(1).numpy().copy())
        self._bytes()
        result = np.concatenate(rows).astype(np.float32)
        if not np.isfinite(result).all():
            raise ValueError("Nonfinite appearance features")
        return result


class AppearanceCentroids:
    """Small human-label prototype classifier with explicit rejection.

    Fit receives labels only after the caller validates the dataset use contract.
    Distances and margins are not probabilities. No role, death state, native
    source validity, Map compatibility or location is certified by this model.
    """

    def __init__(self, centers: Array, labels: list[str], feature_fingerprint: str,
                 *, maximum_distance: float, minimum_margin: float) -> None:
        if (not isinstance(centers, np.ndarray) or centers.ndim != 2
                or not 1 <= centers.shape[0] <= 4 or not 1 <= centers.shape[1] <= 4096
                or len(labels) != centers.shape[0] or len(set(labels)) != len(labels)
                or any(x not in CLASSES for x in labels) or not np.isfinite(centers).all()
                or not isinstance(feature_fingerprint, str) or len(feature_fingerprint) != 64
                or any(type(v) not in (int, float) or not math.isfinite(v)
                       for v in (maximum_distance, minimum_margin))
                or not 0 < maximum_distance <= 2 or not 0 <= minimum_margin <= 2):
            raise ValueError("Bounded appearance classifier required")
        self.centers = centers.astype(np.float64, copy=True)
        norms = np.linalg.norm(self.centers, axis=1, keepdims=True)
        if (norms <= 1e-12).any():
            raise ValueError("Nonzero appearance prototypes required")
        # Serialized unit prototypes must be a fixed point on reload. Repeated
        # division by a norm one rounding unit away from 1 changes their digest.
        self.centers /= np.where(np.abs(norms-1) <= 1e-12, 1., norms)
        self.centers.setflags(write=False)
        self.labels = tuple(labels)
        self.feature_fingerprint = feature_fingerprint
        self.maximum_distance, self.minimum_margin = maximum_distance, minimum_margin
        self.fingerprint = _digest({"algorithm": "appearance_centroids_v1",
                                    "centers": self.centers.tolist(), "labels": labels,
                                    "features": feature_fingerprint,
                                    "maximum_distance": maximum_distance,
                                    "minimum_margin": minimum_margin})

    def classify(self, features: Array, *, feature_fingerprint: str) -> list[dict[str, Any]]:
        if (feature_fingerprint != self.feature_fingerprint
                or not isinstance(features, np.ndarray) or features.ndim != 2
                or features.shape[1] != self.centers.shape[1]
                or not 1 <= len(features) <= 256 or not np.isfinite(features).all()):
            raise ValueError("Matching finite feature matrix required")
        norms = np.linalg.norm(features, axis=1, keepdims=True)
        unit = features/np.maximum(norms, 1e-12)
        distance = np.clip(1-unit@self.centers.T, 0, 2)
        result = []
        for row, norm in zip(distance, norms[:, 0], strict=True):
            order = np.argsort(row, kind="stable")
            best = int(order[0])
            margin = float(row[order[1]]-row[best]) if len(order) > 1 else 0.
            accepted = (norm > 1e-12 and len(order) > 1
                        and row[best] <= self.maximum_distance and margin >= self.minimum_margin)
            result.append({"appearance_class_candidate": (
                               self.labels[best] if accepted else "UNKNOWN"),
                           "cosine_distance": float(row[best]), "margin": margin,
                           "scores_are_probabilities": False, "qualification": "development_only",
                           "ownership": "UNKNOWN", "map_position": None,
                           "formal_fact": None, "formal_events": [],
                           "classifier_fingerprint": self.fingerprint})
        return result


def review_proposals(
    frame: Array, sample: dict[str, Any], proposals: dict[str, Any], *,
    extractor: Any, classifier: AppearanceCentroids,
) -> dict[str, Any]:
    """Attach appearance candidates to a safe result; never remove or locate.

    The existing producer remains responsible for source admission, context and
    current-frame geometry. Native pixels are independently rechecked here. A
    consumer receives unchanged coordinates and separate unqualified class scores.
    """
    if (not isinstance(frame, np.ndarray) or frame.dtype != np.uint8 or frame.ndim != 3
            or frame.shape[2] != 3 or not isinstance(proposals, dict)):
        raise ValueError("Native uint8 BGR frame and development result required")
    if (proposals.get("qualification") != "development_only"
            or proposals.get("ownership") != "UNKNOWN"
            or proposals.get("formal_self_position_fact") is not None
            or proposals.get("selected_self_position") is not None
            or proposals.get("development_events") != []
            or proposals.get("track_segments") != []):
        raise ValueError("Only unassigned development proposals may be reviewed")
    result = deepcopy(proposals)
    rows = result.get("proposals")
    if (not isinstance(rows, list) or len(rows) > 128
            or any(not isinstance(p, dict) or p.get("ownership") != "UNKNOWN"
                   or p.get("map_position_norm") is not None
                   or p.get("zone_resolution") is not None for p in rows)):
        raise ValueError("No formal positions or Zones may enter feature review")
    fingerprint = extractor.fingerprint
    if fingerprint != classifier.feature_fingerprint:
        raise ValueError("Classifier does not bind supplied feature extractor")
    # Even an empty proposal result must bind the supplied native observation.
    bound = freeze_native_sample(sample, frame_size_px=(frame.shape[1], frame.shape[0]))
    if (sample != bound or hashlib.sha256(frame.tobytes()).hexdigest()
            != bound["native_pixel_sha256"]):
        raise ValueError("Native review frame identity mismatch")
    if (result.get("sample") != bound
            or any(row.get("sample_sha256") != bound["sample_sha256"] for row in rows)):
        raise ValueError("Proposal producer and each candidate must bind this observation")
    binding = None
    if rows:
        patches, binding = bound_patches(frame, sample, [p["center_frame_px"] for p in rows])
        features = extractor.extract(patches)
        if extractor.fingerprint != fingerprint:
            raise ValueError("Feature configuration changed during observation")
        labels = classifier.classify(features, feature_fingerprint=fingerprint)
        for row, label in zip(rows, labels, strict=True):
            row["appearance_class_review"] = label
    if hashlib.sha256(frame.tobytes()).hexdigest() != bound["native_pixel_sha256"]:
        raise ValueError("Frame changed during appearance review")
    result["feature_review"] = {"method": "separate_appearance_review_v1",
                                "feature_fingerprint": fingerprint,
                                "classifier_fingerprint": classifier.fingerprint,
                                "patch_binding_sha256": binding,
                                "qualification": "development_only", "ownership": "UNKNOWN",
                                "coordinates_changed": False, "proposals_removed": 0,
                                "formal_outputs": 0}
    return result
