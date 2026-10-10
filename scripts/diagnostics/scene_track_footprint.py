"""Audit image support outside the tracker's central 15-pixel NCC patch.

No semantic world mask, occlusion label, continuity or runtime proof is emitted.
The caller supplies the unchanged world-correspondence transform and identities.
"""

from __future__ import annotations

import cv2
import numpy as np

from scripts.diagnostics.scene_world_chain import _ncc


def projected_patch_support(source, current, center, model, *, radius):
    """Compare the full source square; never discard mismatching pixels."""
    for image in (source, current):
        if image.shape != (360, 640) or image.dtype != np.uint8:
            raise ValueError("canonical uint8 grayscale required")
    if type(radius) is not int or radius not in {7, 10, 15}:
        raise ValueError("existing 15/21/31-pixel support footprints required")
    model = np.asarray(model, dtype=float)
    if (
        model.shape != (2, 3)
        or not np.isfinite(model).all()
        or abs(np.linalg.det(model[:, :2])) < 1e-8
    ):
        raise ValueError("finite nondegenerate source-camera transform required")
    center = np.asarray(center, dtype=float)
    if center.shape != (2,) or not np.isfinite(center).all():
        raise ValueError("finite source point required")
    x, y = np.round(center).astype(int)
    row = {
        "size": 2 * radius + 1,
        "source_center_xy": [int(x), int(y)],
        "current_center_xy": (model @ [x, y, 1]).tolist(),
        "ncc": None,
        "appearance_supported": False,
        "world_mask_authorized": False,
        "runtime_proof_authorized": False,
    }
    yy, xx = np.mgrid[y - radius : y + radius + 1, x - radius : x + radius + 1]
    mx = (model[0, 0] * xx + model[0, 1] * yy + model[0, 2]).astype(np.float32)
    my = (model[1, 0] * xx + model[1, 1] * yy + model[1, 2]).astype(np.float32)
    # Every source pixel and every bilinear destination tap must be in bounds
    # and outside the independently excluded clock/phase areas.
    allowed = np.ones(source.shape, np.float32)
    allowed[:28] = 0
    allowed[28:120, 224:416] = 0
    source_valid = x - radius >= 0 and x + radius < 640 and y - radius >= 0 and y + radius < 360
    if not source_valid or not allowed[yy, xx].all():
        row["reason"] = "source_footprint_invalid_or_protected"
        return row
    validity = cv2.remap(allowed, mx, my, cv2.INTER_LINEAR, borderMode=cv2.BORDER_CONSTANT)
    row["valid_fraction"] = float(np.mean(validity == 1.0))
    if not (validity == 1.0).all():
        row["reason"] = "projected_footprint_invalid_or_protected"
        return row
    aligned = cv2.remap(current, mx, my, cv2.INTER_LINEAR, borderMode=cv2.BORDER_CONSTANT)
    row["ncc"] = _ncc(source[yy, xx], aligned)
    row["appearance_supported"] = row["ncc"] is not None and row["ncc"] >= 0.90
    row["reason"] = (
        "matched_appearance_only" if row["appearance_supported"] else "appearance_unknown"
    )
    return row
