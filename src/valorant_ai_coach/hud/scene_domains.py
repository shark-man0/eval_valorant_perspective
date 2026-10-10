"""Shared fixed-camera appearance measurements, without runtime authorization.

This image-only engine excludes clock/phase pixels and retains all offsets and
unknown competitors. Its limited appearance scope cannot authorize background
semantics, content-time continuity or a lifecycle boundary. No diagnostic scripts,
Validation Pack, PTS or OS-specific logic are imported by production code.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from typing import Any, cast

import cv2
import numpy as np
from numpy.typing import NDArray

ImageU8 = NDArray[np.uint8]
Boxes = Sequence[Sequence[int]]


def canonical_scene_image(image: Any) -> ImageU8:
    """Normalize the actual native BGR image; no sampling or ROI relabeling."""
    if image is None or image.shape != (1080, 1920, 3) or image.dtype != np.uint8:
        raise ValueError("1920x1080 uint8 BGR source image required")
    return cast(
        ImageU8,
        cv2.cvtColor(
            cv2.resize(image, (640, 360), interpolation=cv2.INTER_AREA), cv2.COLOR_BGR2GRAY
        ),
    )


def _validate(image: ImageU8, boxes: Boxes) -> None:
    if image.dtype != np.uint8 or image.shape != (360, 640):
        raise ValueError("canonical grayscale uint8 image required")
    if not boxes:
        raise ValueError("explicit non-UI crops required")
    for x1, y1, x2, y2 in boxes:
        if not (0 <= x1 < x2 <= 640 and 0 <= y1 < y2 <= 360):
            raise ValueError("crop outside image")
        # Exclude the entire top clock/score band and padded phase/result area.
        if y1 < 28 or (x1 < 416 and x2 > 224 and y1 < 120 and y2 > 28):
            raise ValueError("search crop intersects protected timer/phase pixels")
        if min(x2 - x1, y2 - y1) < 32:
            raise ValueError("crop too small")


def _ncc(a: NDArray[Any], b: NDArray[Any]) -> float | None:
    if min(float(a.std()), float(b.std())) < 1:
        return None
    result = float(cv2.matchTemplate(a, b, cv2.TM_CCOEFF_NORMED)[0, 0])
    return result if np.isfinite(result) else None


def _spread(points: Sequence[Any], scale: float = 1) -> bool:
    cells = {(int(y / (120 * scale)), int(x / (640 * scale / 3))) for x, y in points}
    return len(cells) >= 3 and len({r for r, c in cells}) >= 2 and len({c for r, c in cells}) >= 2


def domain_displacement_audit(
    previous: ImageU8,
    current: ImageU8,
    boxes: Boxes,
    model: Any,
    *,
    offset_sink: list[dict[str, Any]] | None = None,
    allowed_current_boxes: Boxes | None = None,
) -> list[dict[str, Any]]:
    """Audit a frozen +/-8-pixel lattice, never optimize the camera transform.

    This finite lattice cannot exclude all alternative camera models. A passing
    result is appearance evidence only, not a foreground-free world mask.
    """
    _validate(previous, boxes)
    _validate(current, boxes)
    model = np.asarray(model, float)
    if (
        model.shape != (2, 3)
        or not np.isfinite(model).all()
        or abs(np.linalg.det(model[:, :2])) < 1e-8
    ):
        raise ValueError("finite nondegenerate frozen camera model required")
    allowed = np.ones(current.shape, np.float32)
    allowed[:28] = 0
    allowed[28:120, 224:416] = 0
    if allowed_current_boxes is not None:
        _validate(current, allowed_current_boxes)
        allowed[:] = 0
        for x1, y1, x2, y2 in allowed_current_boxes:
            allowed[y1:y2, x1:x2] = 1
    rows = []
    for region, (x1, y1, x2, y2) in enumerate(boxes):
        yy, xx = np.mgrid[y1:y2, x1:x2]
        mx = (model[0, 0] * xx + model[0, 1] * yy + model[0, 2]).astype(np.float32)
        my = (model[1, 0] * xx + model[1, 1] * yy + model[1, 2]).astype(np.float32)
        source = previous[y1:y2, x1:x2]
        predicted_score = None
        competitors = []
        invalid = 0
        for dy in range(-8, 9):
            for dx in range(-8, 9):
                # No padding/protected samples, mismatch trimming or dynamic mask.
                valid = cv2.remap(allowed, mx + dx, my + dy, cv2.INTER_LINEAR)
                if not (valid == 1.0).all():
                    invalid += 1
                    if offset_sink is not None:
                        offset_sink.append(
                            {"region": region, "offset_xy": [dx, dy], "valid": False, "ncc": None}
                        )
                    continue
                image = cv2.remap(current, mx + dx, my + dy, cv2.INTER_LINEAR)
                score = _ncc(source, image)
                if offset_sink is not None:
                    offset_sink.append(
                        {"region": region, "offset_xy": [dx, dy], "valid": True, "ncc": score}
                    )
                if dx == dy == 0:
                    predicted_score = score
                if score is not None and score >= 0.90 and max(abs(dx), abs(dy)) > 2:
                    competitors.append({"offset_xy": [dx, dy], "ncc": score})
        rows.append(
            {
                "region": region,
                "predicted_ncc": predicted_score,
                "competing_offsets": competitors,
                "invalid_offsets": invalid,
                "locally_unambiguous_appearance": (
                    predicted_score is not None and predicted_score >= 0.90 and not competitors
                ),
                "search_scope": "17x17 integer translations of fixed affine projection",
                "world_mask_authorized": False,
                "runtime_proof_authorized": False,
            }
        )
    return rows


def joint_domain_audit(
    boxes: Boxes,
    model: Any,
    measurements: Sequence[dict[str, Any]],
) -> dict[str, Any]:
    model = np.asarray(model, float)
    _validate(np.zeros((360, 640), np.uint8), boxes)
    if (
        model.shape != (2, 3)
        or not np.isfinite(model).all()
        or abs(np.linalg.det(model[:, :2])) < 1e-8
    ):
        raise ValueError("finite source-camera model required")
    expected = {(dx, dy) for dy in range(-8, 9) for dx in range(-8, 9)}
    grids: list[dict[tuple[int, ...], dict[str, Any]]] = [dict() for _ in boxes]
    for item in measurements:
        region = item["region"]
        offset = tuple(item["offset_xy"])
        if (
            type(region) is not int
            or not 0 <= region < len(boxes)
            or offset not in expected
            or any(type(v) is not int for v in offset)
            or offset in grids[region]
            or type(item["valid"]) is not bool
        ):
            raise ValueError("unique complete integer displacement measurements required")
        score = item["ncc"]
        if score is not None and (
            type(score) not in (int, float) or not math.isfinite(score) or not -1 <= score <= 1
        ):
            raise ValueError("finite NCC or explicit unknown required")
        grids[region][offset] = item
    if not grids or any(set(grid) != expected for grid in grids):
        raise ValueError("complete frozen 17x17 lattice required for every source domain")

    def supported(item: dict[str, Any]) -> bool:
        return bool(item["valid"] and item["ncc"] is not None and item["ncc"] >= 0.90)

    witnesses = [i for i, grid in enumerate(grids) if supported(grid[(0, 0)])]
    centers = [
        np.array([(boxes[i][0] + boxes[i][2]) / 2, (boxes[i][1] + boxes[i][3]) / 2])
        for i in witnesses
    ]
    projected = [(model @ [*point, 1]).tolist() for point in centers]
    distributed = (
        len(witnesses) >= 3
        and _spread(centers)
        and _spread(projected)
        and all(0 <= x < 640 and 0 <= y < 360 for x, y in projected)
    )
    competing: list[list[int]] = []
    unresolved: list[list[int]] = []
    for offset in sorted(expected):
        if max(abs(v) for v in offset) <= 2:
            continue
        alternatives = [grids[i][offset] for i in witnesses]
        # A known photometric contradiction is different from an invalid tap,
        # unavailable texture or omitted offset; unknown never acts as a veto.
        contradicted = any(
            p["valid"] and p["ncc"] is not None and p["ncc"] < 0.90 for p in alternatives
        )
        if not contradicted:
            (
                competing
                if alternatives and all(supported(p) for p in alternatives)
                else unresolved
            ).append(list(offset))
    return {
        "fixed_projection_witness_regions": witnesses,
        "distributed_source_and_current_support": distributed,
        "joint_competing_offsets": competing,
        "unresolved_offsets": unresolved,
        "locally_unique_joint_appearance": distributed and not competing and not unresolved,
        "scope": "fixed affine plus complete local integer-translation lattice only",
        "world_mask_authorized": False,
        "runtime_proof_authorized": False,
    }
