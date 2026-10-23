"""Boundary sensitivity of unqualified image-space region candidates."""

from __future__ import annotations

import math
from typing import Any

from shapely.geometry import Point, Polygon


def validate_assumed_error_radius(value: Any) -> float | None:
    if value is not None and (
        isinstance(value, bool)
        or not isinstance(value, (int, float))
        or not math.isfinite(value) or value < 0
    ):
        raise ValueError("Finite non-negative assumed position error required")
    return float(value) if value is not None else None


def candidate_boundary_evidence(
    point_norm: tuple[float, float], polygon_norm: list[list[float]], *,
    reference_size_px: tuple[float, float], assumed_error_radius_px: float | None,
) -> dict[str, Any]:
    """An assumed disk is not a calibrated error bound or a probability.

    Convert x/y independently to reference pixels before computing distances.
    Even an interior disk says nothing about exact callout semantics, ownership,
    world distance, walkability, or occupancy between observations.
    """
    assumed_error_radius_px = validate_assumed_error_radius(assumed_error_radius_px)
    if (len(point_norm) != 2 or len(reference_size_px) != 2
            or len(polygon_norm) < 3 or any(len(p) != 2 for p in polygon_norm)):
        raise ValueError("Two-dimensional point, size and polygon required")
    values = (*point_norm, *reference_size_px, *(v for p in polygon_norm for v in p))
    if (any(not isinstance(v, (int, float)) or isinstance(v, bool) or not math.isfinite(v)
            for v in values) or any(v <= 0 for v in reference_size_px)):
        raise ValueError("Finite image-space geometry required")
    w, h = reference_size_px
    polygon = Polygon([(p[0]*w, p[1]*h) for p in polygon_norm])
    if not polygon.is_valid or polygon.is_empty or polygon.area <= 0:
        raise ValueError("Valid non-empty region polygon required")
    point = Point(point_norm[0]*w, point_norm[1]*h)
    inside = bool(polygon.covers(point))
    clearance = float(point.distance(polygon.boundary))
    state = ("outside_region" if not inside else "unmeasured_error_radius"
             if assumed_error_radius_px is None else "interior_under_assumption"
             if clearance > assumed_error_radius_px else "boundary_intersects_assumed_error")
    return {
        "qualification": "development_only", "ownership": "UNKNOWN",
        "boundary_clearance_reference_px": clearance if inside else -clearance,
        "assumed_error_radius_reference_px": assumed_error_radius_px,
        "boundary_assessment": state,
    }
