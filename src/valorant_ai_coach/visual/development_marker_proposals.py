"""Unassigned multi-appearance positions, isolated from single-player tracking.

Reuse the existing positive AND control proposal generator. Reference roles do
not transfer across sources. Context blocks and ambiguous selection do not erase
visible proposals, but no proposal is selected as self, tracked or emitted as a
Fact. Geometry is freshly calibrated on the supplied, native-bound frame.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any

import cv2
import numpy as np
from numpy.typing import NDArray

from valorant_ai_coach.maps.outline_calibration import OutlineMinimapCalibrator
from valorant_ai_coach.video.geometry import normalized_roi_bounds

from .development_map import development_registry
from .development_marker_attribution import freeze_native_sample
from .self_marker import MarkerReferenceInspector


class DevelopmentMarkerProposals:
    """Explicit, bounded, non-Production map and reference bank.

    Results retain per-library duplicates and search truncation. A consumer must
    not count duplicate proposals as independent marker observations. There is
    deliberately no temporal association between any of these proposals.
    """

    def __init__(self, map_id: str) -> None:
        registry = development_registry(map_id)
        self.definition = registry.load(map_id)
        if registry.registry["maps"][map_id]["production"]:
            raise ValueError("Proposal geometry requires a non-Production map")
        provenance = json.loads((registry.root / "provenance.json").read_text(encoding="utf-8"))
        self.calibrator = OutlineMinimapCalibrator(
            expected_reference_sha256=provenance["reference_sha256"])
        floor_path = (registry.root / provenance.get(
            "visible_floor_asset", "assets/bind_visible_floor.png")).resolve()
        if not floor_path.is_relative_to(registry.root.resolve()):
            raise ValueError("Development floor escapes registered bundle")
        content = floor_path.read_bytes()
        if hashlib.sha256(content).hexdigest() != provenance["visible_floor_sha256"]:
            raise ValueError("Development floor digest mismatch")
        self.floor = cv2.imdecode(np.frombuffer(content, np.uint8), cv2.IMREAD_GRAYSCALE)
        if self.floor is None:
            raise ValueError("Development floor unavailable")
        self.inspectors = [MarkerReferenceInspector() for _ in range(4)]

    def observe(
        self, frame: NDArray[Any], *, sample: dict[str, Any],
        minimap_roi: list[float], appearance_pool: dict[str, Any],
        calibration_profile: dict[str, Any], context_eligible: bool,
    ) -> dict[str, Any]:
        """Measure appearance proposals without bypassing player eligibility.

        Even eligible context does not authenticate recorder ownership or map
        version. Coordinates remain under geometry-only diagnostics. The caller
        supplies a frozen encoded-frame hash; this API verifies decoded pixels.
        """
        if (not isinstance(frame, np.ndarray) or frame.dtype != np.uint8
                or frame.ndim != 3 or frame.shape[2] != 3):
            raise ValueError("Native uint8 BGR frame required")
        bound = freeze_native_sample(sample, frame_size_px=(frame.shape[1], frame.shape[0]))
        if sample != bound:
            raise ValueError("Exact frozen native sample required")
        if hashlib.sha256(frame.tobytes()).hexdigest() != bound["native_pixel_sha256"]:
            raise ValueError("Frame pixels do not match native sample")
        bounds = normalized_roi_bounds(minimap_roi, frame.shape[1], frame.shape[0])
        if bounds is None or not isinstance(context_eligible, bool):
            raise ValueError("Explicit ROI and context eligibility required")
        libraries = appearance_pool.get("libraries")
        if (appearance_pool.get("mode") != "appearance_pool_v1"
                or not isinstance(libraries, list) or not 1 <= len(libraries) <= 4
                or any(not isinstance(lib, dict)
                       or lib.get("role") != "appearance_contrast_only"
                       or not isinstance(lib.get("source_id"), str) or not lib["source_id"]
                       or not isinstance(lib.get("matcher"), dict) for lib in libraries)):
            raise ValueError("Explicit bounded appearance pool required")
        left, top, right, bottom = bounds
        crop = frame[top:bottom, left:right]
        if max(crop.shape[:2]) > 1024:
            raise ValueError("Proposal ROI exceeds development bound")
        active = self.inspectors[:len(libraries)]
        evidence = [inspector.inspect(crop, lib["matcher"])
                    for inspector, lib in zip(active, libraries, strict=True)]
        if any(e["reason"] != "appearance_comparison_only" for e in evidence):
            raise ValueError("Invalid appearance library")
        calibration = self.calibrator.analyze(
            frame, minimap_roi, self.definition, profile=calibration_profile)
        assert self.floor is not None
        bbox = self.definition.data["coordinate_system"]["reference_map_mask_bbox_within_roi_px"]
        candidates = []
        for library_index, member in enumerate(evidence):
            for proposal_index, proposal in enumerate(member["matches"]):
                x, y = proposal["x_roi_norm"], proposal["y_roi_norm"]
                point = calibration.transform(x, y)
                reason = "calibration_required" if point is None else "geometry_only"
                if point is not None:
                    fx = round(bbox[0] + point[0] * (bbox[2] - bbox[0]))
                    fy = round(bbox[1] + point[1] * (bbox[3] - bbox[1]))
                    if not (0 <= fy < self.floor.shape[0] and 0 <= fx < self.floor.shape[1]
                            and self.floor[fy, fx] > 0):
                        point, reason = None, "outside_visible_floor"
                candidates.append({
                    "proposal_id": [library_index, proposal_index],
                    "qualification": "development_only", "ownership": "UNKNOWN",
                    "position_subject": "unassigned_visual_candidate",
                    "sample_sha256": bound["sample_sha256"],
                    "reference_fingerprint": member["reference_fingerprint"],
                    "center_frame_px": [left + x * (right-left), top + y * (bottom-top)],
                    "appearance_evidence": proposal,
                    "geometry_only_map_position_norm": list(point) if point is not None else None,
                    "geometry_reason": reason,
                    "map_position_norm": None, "zone_resolution": None,
                    "version_compatibility": "UNKNOWN",
                })
        # Re-read only bounded reference content, not cached frame transforms.
        for inspector, lib, member in zip(active, libraries, evidence, strict=True):
            loader = inspector._loader
            if (not loader._load(lib["matcher"])
                    or loader.reference_fingerprint != member["reference_fingerprint"]):
                raise ValueError("Reference changed during proposal observation")
        if hashlib.sha256(frame.tobytes()).hexdigest() != bound["native_pixel_sha256"]:
            raise ValueError("Frame changed during proposal observation")
        return {
            "qualification": "development_only", "ownership": "UNKNOWN", "sample": bound,
            "map_id": self.definition.map_id, "geometry_version": self.definition.geometry_version,
            "context_eligible": context_eligible, "context_semantics_qualified": False,
            "calibration": {"status": calibration.status,
                            "diagnostics": list(calibration.diagnostics)},
            "search_truncated": any(member["truncated"] for member in evidence),
            "proposals": candidates, "selected_self_position": None,
            "formal_self_position_fact": None, "development_events": [],
            "track_segments": [], "interpolated_positions": [],
        }
