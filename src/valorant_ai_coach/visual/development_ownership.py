"""Independent screen-context evidence candidates; no recorder ownership claim.

Read-only reuse of HUD measurements. Shared first-person HUDs and absent spectator
patterns cannot distinguish a recorder from a spectated player. Correlated cues
are kept in families rather than counted as independent identity votes.
"""

from __future__ import annotations

import hashlib
import json
import math
from typing import Any

import numpy as np
from numpy.typing import NDArray

from valorant_ai_coach.hud.spectator_icon import detect_icon, menu_overlay_candidate
from valorant_ai_coach.video.geometry import normalized_roi_bounds

from .development_view import DevelopmentViewVeto

_CLAIMS = {
    "spectator_controls": "spectator_ui", "death_report": "report_overlay",
    "menu_overlay": "menu_ui", "first_person_hud": "shared_first_person_hud",
}


def _disjoint(a: tuple[int, int, int, int], b: tuple[int, int, int, int]) -> bool:
    return a[2] <= b[0] or b[2] <= a[0] or a[3] <= b[1] or b[3] <= a[1]


class DevelopmentOwnershipEvidence:
    """Current-frame context only, with no hysteresis or carry-forward evidence.

    Profile slots must have been reviewed outside the minimap at the exact frame
    geometry. That declaration is an unqualified authoring attestation, not a
    Production calibration. A configured unavailable probe fails closed.
    """

    def __init__(self) -> None:
        self._matchers = [DevelopmentViewVeto() for _ in range(8)]

    def inspect(
        self, frame: NDArray[Any], spec: Any, *, minimap_roi: Any,
        source_id: str, acquisition_id: str, time_sec: float, frame_index: int,
    ) -> dict[str, Any]:
        envelope: dict[str, Any] = {
            "qualification": "development_only", "ownership": "UNKNOWN",
            "status": "disabled", "block_position_candidate": False,
            "view_candidate": "UNKNOWN", "actor_candidate": "UNKNOWN",
            "source_id": source_id, "acquisition_id": acquisition_id,
            "time_sec": time_sec, "frame_index": frame_index,
            "observed_cues": [], "reasons": ["recorder_identity_link_unavailable"],
            "reference_fingerprint": None,
        }
        if spec is None:
            return envelope
        envelope.update(status="unavailable", block_position_candidate=True)
        if (not isinstance(source_id, str) or not source_id
                or not isinstance(acquisition_id, str) or not acquisition_id
                or not isinstance(time_sec, (int, float)) or isinstance(time_sec, bool)
                or not math.isfinite(time_sec) or time_sec < 0
                or not isinstance(frame_index, int) or isinstance(frame_index, bool)):
            return envelope
        if (not isinstance(frame, np.ndarray) or frame.dtype != np.uint8 or frame.ndim != 3
                or frame.shape[2] != 3 or min(frame.shape[:2]) <= 0):
            return envelope
        size = [frame.shape[1], frame.shape[0]]
        if (not isinstance(spec, dict) or spec.get("mode") != "screen_context_v1"
                or spec.get("frame_size_px") != size
                or spec.get("slot_review") != "source_reviewed_not_qualified"):
            return envelope
        minimap = normalized_roi_bounds(minimap_roi, *size)
        probes = spec.get("probes")
        if (minimap is None or not isinstance(probes, list) or not 1 <= len(probes) <= 8
                or any(not isinstance(p, dict) or not isinstance(p.get("claim"), str)
                       or p["claim"] not in _CLAIMS for p in probes)):
            return envelope
        cues = []
        for matcher, probe in zip(self._matchers, probes, strict=False):
            bounds = normalized_roi_bounds(probe.get("roi"), *size)
            if bounds is None or not _disjoint(bounds, minimap):
                return {**envelope, "reasons": ["probe_geometry_overlaps_minimap_or_invalid"]}
            result = matcher.inspect(frame, {
                "mode": "spectator_switch_v1", "roi": probe["roi"],
                "reference_frame_size_px": size, "template_path": probe.get("template_path"),
            })
            cues.append({
                "claim": probe["claim"], "family": _CLAIMS[probe["claim"]],
                "status": "unavailable" if result["status"] == "unavailable" else
                          "present" if result["veto"] else "not_detected",
                "similarity": result["similarity"], "reference_sha256": result["reference_sha256"],
                "independent_of_minimap_pixels": True,
                "qualification": "development_only", "ownership": "UNKNOWN",
            })
        # Reuse the existing dedicated-slot detector, without modifying HUD code.
        icon = {"checked": False, "panel_present": None, "reason": "not_configured"}
        if "spectator_icon_roi" in spec:
            bounds = normalized_roi_bounds(spec["spectator_icon_roi"], *size)
            if bounds is None or not _disjoint(bounds, minimap):
                return {**envelope, "reasons": ["invalid_spectator_slot_geometry"]}
            left, top, right, bottom = bounds
            obscured = False
            if "menu_close_roi" in spec:
                menu = normalized_roi_bounds(spec["menu_close_roi"], *size)
                if menu is None or not _disjoint(menu, minimap):
                    return {**envelope, "reasons": ["invalid_menu_slot_geometry"]}
                ml, mt, mr, mb = menu
                obscured = menu_overlay_candidate(frame[mt:mb, ml:mr])
            icon = detect_icon(frame[top:bottom, left:right], obscured=obscured)
        present = {c["claim"] for c in cues if c["status"] == "present"}
        reasons = ["recorder_identity_link_unavailable"]
        unavailable = any(c["status"] == "unavailable" for c in cues)
        if unavailable:
            reasons.append("configured_screen_probe_unavailable")
        spectator = "spectator_controls" in present or icon["panel_present"] is True
        overlay = bool(present & {"death_report", "menu_overlay"})
        if spectator:
            reasons.append("spectator_context_candidate")
        if "death_report" in present:
            reasons.append("death_report_is_not_current_actor_or_death_identity")
        if "first_person_hud" in present:
            reasons.append("first_person_hud_shared_by_self_and_spectator")
        families = sorted({c["family"] for c in cues if c["status"] == "present"})
        if icon["panel_present"] is True:
            families = sorted(set(families) | {"spectator_ui"})
        fingerprint = hashlib.sha256(json.dumps(
            {"spec": spec, "references": [c["reference_sha256"] for c in cues]},
            sort_keys=True).encode("utf-8")).hexdigest()
        return {
            **envelope, "status": "unavailable" if unavailable else "observed",
            "frame_pixel_sha256": hashlib.sha256(frame.tobytes()).hexdigest(),
            "block_position_candidate": unavailable or spectator or overlay,
            "view_candidate": "spectator_context" if spectator else "overlay_context"
                              if overlay else "first_person_hud_context"
                              if "first_person_hud" in present else "UNKNOWN",
            "actor_candidate": "non_recorder_view_candidate" if spectator else "UNKNOWN",
            "observed_cues": cues, "spectator_slot": icon, "reasons": reasons,
            "evidence_families": families, "reference_fingerprint": fingerprint,
            "positive_recorder_ownership_evidence": False,
        }
