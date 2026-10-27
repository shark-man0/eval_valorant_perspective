"""Train-only native appearance retrieval, with unlabeled SSL controls.

Templates are local user material, never downloaded. Retrieval windows are not
semantic truth, player identity or Map coordinates. Fit/extraction admission is
validated separately from inference-frame native binding.
"""

from __future__ import annotations

import hashlib
from dataclasses import asdict
from typing import Any

import cv2
import numpy as np

from .development_learning_dataset import (
    FrameLabel,
    FrameRecord,
    Use,
    validate_dataset,
    validate_use,
)
from .development_marker_features import Array, _digest
from .development_marker_topk import _native, broad_shape_candidates


class NativeTemplateBank:
    """At most 24 native, hash-bound 25px train patches; no label propagation.

    Callers must obtain patches with bound_patches and retain their independent
    digests. A matching digest here cannot authenticate a caller's Source ledger.
    """

    def __init__(
        self,
        patches: list[Array],
        frames: list[FrameRecord],
        *,
        patch_sha256: list[str],
        labels: list[FrameLabel] | None = None,
    ) -> None:
        if (
            not 1 <= len(patches) <= 24
            or len(frames) != len(patches)
            or len(patch_sha256) != len(patches)
            or any(
                not isinstance(p, np.ndarray) or p.dtype != np.uint8 or p.shape != (25, 25, 3)
                for p in patches
            )
        ):
            raise ValueError("One to 24 paired native 25px train patches required")
        validate_dataset(frames, labels or ())
        if labels is not None and len(labels) != len(frames):
            raise ValueError("Paired human labels required")
        for i, (patch, frame) in enumerate(zip(patches, frames, strict=True)):
            if hashlib.sha256(patch.tobytes()).hexdigest() != patch_sha256[i] or tuple(
                frame.roi_xywh[2:]
            ) != (25.0, 25.0):
                raise ValueError("Native patch bytes or ROI changed")
            label = labels[i] if labels is not None else None
            validate_use(
                frame, Use.SUPERVISED_TRAIN if label else Use.SSL, label, dataset_frames=frames
            )
            if label and label.label.value not in {"PLAYER", "DEATH_MARKER"}:
                raise ValueError("Positive human templates or unlabeled train controls only")
        self._frames = tuple(frames)
        self._templates = [p[4:21, 4:21].copy() for p in patches]
        for template in self._templates:
            template.setflags(write=False)
        self._hashes = [hashlib.sha256(t.tobytes()).hexdigest() for t in self._templates]
        self.origin = "human_train_reference" if labels is not None else "unlabeled_train_retrieval"
        self.fingerprint = _digest(
            {
                "templates": self._hashes,
                "frames": [asdict(f) for f in frames],
                "origin": self.origin,
                "labels": [asdict(label) for label in labels or ()],
                "search": [0.8, 1.0, 1.2, 0.45, 2, 3],
            }
        )

    def search(self, crop: Array) -> dict[str, Any]:
        if (
            not isinstance(crop, np.ndarray)
            or crop.dtype != np.uint8
            or crop.ndim != 3
            or crop.shape[2] != 3
            or not min(crop.shape[:2]) >= 65
            or max(crop.shape[:2]) > 1024
        ):
            raise ValueError("Bounded native minimap crop required")
        if self._hashes != [hashlib.sha256(t.tobytes()).hexdigest() for t in self._templates]:
            raise ValueError("Reference bank changed")
        observations = []
        for index, template in enumerate(self._templates):
            for scale in (0.8, 1.0, 1.2):
                size = round(17 * scale) | 1
                ref = cv2.resize(template, (size, size), interpolation=cv2.INTER_AREA)
                # A constant reference has no normalized correlation evidence.
                if np.std(ref.astype(np.float32), axis=(0, 1)).max() < 1:
                    continue
                scores = cv2.matchTemplate(crop, ref, cv2.TM_CCOEFF_NORMED)
                scores[~np.isfinite(scores)] = -1
                for _ in range(2):
                    _, similarity, _, location = cv2.minMaxLoc(scores)
                    if similarity < 0.45:
                        break
                    x, y = location
                    observations.append(
                        {
                            "center_roi_px": [float(x + size // 2), float(y + size // 2)],
                            "raw_score": similarity,
                            "template_index": index,
                            "scale": scale,
                            "bank_fingerprint": self.fingerprint,
                            "reference_origin": self.origin,
                            "method": "train_template_retrieval",
                        }
                    )
                    scores[max(0, y - 3) : y + 4, max(0, x - 3) : x + 4] = -1
        if self._hashes != [hashlib.sha256(t.tobytes()).hexdigest() for t in self._templates]:
            raise ValueError("Reference bank changed during search")
        return {
            "observations": observations,
            "bank_fingerprint": self.fingerprint,
            "ownership": "UNKNOWN",
            "semantic_class": "UNKNOWN",
            "qualification": "development_only",
        }


def template_candidate_pool(
    frame: Array,
    sample: dict[str, Any],
    *,
    roi_xywh: list[int],
    parent: list[dict[str, Any]],
    profile_fingerprint: str,
    human_bank: NativeTemplateBank,
    ssl_bank: NativeTemplateBank | None = None,
) -> dict[str, Any]:
    """Compare retrieval instead of loose shape proposals, keeping parent prefix.

    The shape search supplies the same native/parent validation envelope, but its
    additional windows remain a separate trial. This method returns only parent
    and template windows; it never discards a parent observation. Search cost of
    the validation envelope is included in timing, not hidden as cached work.
    """
    pool = broad_shape_candidates(
        frame, sample, roi_xywh=roi_xywh, parent=parent, profile_fingerprint=profile_fingerprint
    )
    if human_bank.origin != "human_train_reference" or (
        ssl_bank is not None and ssl_bank.origin != "unlabeled_train_retrieval"
    ):
        raise ValueError("Human train bank and separately identified unlabeled controls required")
    validate_dataset([*human_bank._frames, *(ssl_bank._frames if ssl_bank else ())])
    left, top, width, height = roi_xywh
    crop = frame[top : top + height, left : left + width]
    searches = [human_bank.search(crop)]
    if ssl_bank is not None:
        searches.append(ssl_bank.search(crop))
    extra = [
        {
            **p,
            "center_frame_px": [p["center_roi_px"][0] + left, p["center_roi_px"][1] + top],
            "class_candidate": "UNKNOWN",
            "candidate_kind": "unassigned_retrieval_window",
            "ownership": "UNKNOWN",
            "qualification": "development_only",
            "geometry_only_map_position_norm": None,
            "geometry_reason": "not_evaluated",
            "map_position_norm": None,
            "zone_resolution": None,
            "unknown_reason": "retrieval_is_not_semantic_or_ownership_evidence",
        }
        for search in searches
        for p in search["observations"]
    ]
    # 24 templates per bank yield at most 288 windows. Explicit output overflow
    # is retained as a count; parents always have priority in the 320-window cap.
    capacity = 320 - len(parent)
    pool["candidates"] = pool["candidates"][: len(parent)] + extra[:capacity]
    pool["retrieval_output_overflow"] = max(0, len(extra) - capacity)
    pool["retrieval_searches"] = searches
    pool["shape_windows_in_separate_trial"] = True
    pool["near_window_pairs"] = []
    pool["physical_association"] = "UNKNOWN"
    pool["policy_fingerprint"] = _digest(
        {
            "method": "train_retrieval_v1",
            "human": human_bank.fingerprint,
            "ssl": ssl_bank.fingerprint if ssl_bank else None,
        }
    )
    pool.pop("pool_sha256")
    pool["pool_sha256"] = _digest(pool)
    _native(frame, sample)
    return pool
