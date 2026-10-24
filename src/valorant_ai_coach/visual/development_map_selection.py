"""Unique registered-outline candidates without guessing an unsupported Map."""

from __future__ import annotations

import json
import re
from typing import Any

import numpy as np
from numpy.typing import NDArray

from valorant_ai_coach.maps.outline_calibration import OutlineMinimapCalibrator

from .development_map import development_registry


class DevelopmentOutlineMapSelector:
    """Every decision measures the current frame against all configured Maps.

    Only immutable reference preprocessing is cached. This returns a geometric
    candidate, not independently reviewed Map identity, camera identity or GT.
    """

    def __init__(self, map_ids: tuple[str, ...] = (
        "bind", "haven", "lotus", "corrode", "summit",
    )) -> None:
        if not 1 <= len(map_ids) <= 8 or len(set(map_ids)) != len(map_ids):
            raise ValueError("Bounded unique registered development Maps required")
        self.definitions = {}
        self.calibrators = {}
        for map_id in map_ids:
            registry = development_registry(map_id)
            definition = registry.load(map_id)
            provenance = json.loads((registry.root/"provenance.json").read_text(encoding="utf-8"))
            self.definitions[map_id] = definition
            self.calibrators[map_id] = OutlineMinimapCalibrator(
                expected_reference_sha256=provenance["reference_sha256"])

    def inspect(
        self, frame: NDArray[Any], minimap_roi: list[float], *, source_id: str,
        source_sha256: str, acquisition_id: str, profile: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        if (not isinstance(source_id, str) or not source_id
                or not isinstance(acquisition_id, str) or not acquisition_id
                or not isinstance(source_sha256, str)
                or re.fullmatch(r"[0-9a-f]{64}", source_sha256) is None):
            raise ValueError("Explicit source SHA and acquisition identity required")
        if (not isinstance(frame, np.ndarray) or frame.dtype != np.uint8
                or frame.ndim != 3 or frame.shape[2] != 3):
            raise ValueError("A current uint8 BGR source frame is required")
        results = {}
        for map_id, definition in self.definitions.items():
            result = self.calibrators[map_id].analyze(
                frame, minimap_roi, definition, profile=profile)
            results[map_id] = {"status": result.status, "confidence": result.confidence,
                               "geometry_version": result.geometry_version,
                               "diagnostics": list(result.diagnostics)}
        accepted = [key for key, value in results.items() if value["status"] == "ok"]
        return {
            "qualification": "development_only", "ownership": "UNKNOWN",
            "source_id": source_id, "source_sha256": source_sha256,
            "acquisition_id": acquisition_id,
            "map_id_candidate": accepted[0] if len(accepted) == 1 else None,
            "reason": "unique_registered_outline" if len(accepted) == 1 else
                      "multiple_registered_outlines_match" if accepted else
                      "no_registered_outline_match",
            "outline_results": results, "map_identity_qualified": False,
            "formal_self_position_fact": None,
        }
