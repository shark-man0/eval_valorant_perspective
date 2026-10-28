"""Opt-in accepted-DEVELOPMENT UI -> owner timeline -> existing Map pipeline.

This adapter does not establish account ownership or issue formal events. Cached
UI is accepted only under the current reader/Profile/reference fingerprint.
"""

from __future__ import annotations

import hashlib
from copy import deepcopy
from fractions import Fraction
from typing import Any, Literal

import numpy as np

from valorant_ai_coach.video.geometry import normalized_roi_bounds

from .development_learning_dataset import FrameRecord
from .development_map import DevelopmentMapTimeline
from .development_marker_attribution import freeze_native_sample
from .development_marker_features import _digest
from .development_owner_marker import DevelopmentOwnerMarkerTracker
from .development_owner_observations import DevelopmentOwnerTimeline, DevelopmentOwnerUI


class DevelopmentOwnerMapPipeline:
    """One explicit research run; never connected to a Production consumer.

    The caller verifies the accepted private registry and encoded frame bytes,
    constructs the existing FrameRecord, and supplies Native Decoder receipts.
    Human initialization is an optional, separately reported diagnostic only.
    """

    def __init__(self, profile: dict[str, Any], *, tracking: Literal["local", "legacy"]) -> None:
        if tracking not in {"local", "legacy"}:
            raise ValueError("Explicit development tracking method required")
        self.profile = deepcopy(profile)
        self.reader = DevelopmentOwnerUI(self.profile)
        self.owner = DevelopmentOwnerTimeline()
        self.map = DevelopmentMapTimeline(
            self.profile,
            marker=DevelopmentOwnerMarkerTracker() if tracking == "local" else None,
        )
        self._scope: str | None = None

    def reset(self) -> None:
        self.owner.reset()
        self.map.reset()
        self._scope = None

    def observe(
        self,
        image: np.ndarray,
        sample: dict[str, Any],
        frame: FrameRecord,
        *,
        continuity: dict[str, Any] | None = None,
        cached_ui: dict[str, Any] | None = None,
        initial_review: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        try:
            return self._observe(image, sample, frame, continuity, cached_ui, initial_review)
        except Exception:
            self.reset()
            raise

    def _observe(
        self,
        image: np.ndarray,
        sample: dict[str, Any],
        frame: FrameRecord,
        continuity: dict[str, Any] | None,
        cached_ui: dict[str, Any] | None,
        initial_review: dict[str, Any] | None,
    ) -> dict[str, Any]:
        frame.validate()
        definition = self.map.timeline.definition
        assert definition is not None
        frozen = freeze_native_sample(sample, frame_size_px=frame.frame_size_px)
        if (
            frozen != sample
            or any(
                frozen[k] != v
                for k, v in {
                    "source_sha256": frame.source_sha256,
                    "native_epoch": frame.native_epoch,
                    "acquisition_id": frame.acquisition_id,
                    "native_pts_tick": frame.native_pts_tick,
                    "native_time_base": frame.native_time_base,
                    "acquired_frame_sha256": frame.frame_sha256,
                    "native_pixel_sha256": frame.pixel_sha256,
                }.items()
            )
            or not isinstance(image, np.ndarray)
            or image.dtype != np.uint8
            or image.shape != (frame.frame_size_px[1], frame.frame_size_px[0], 3)
            or hashlib.sha256(image.tobytes()).hexdigest() != frame.pixel_sha256
        ):
            raise ValueError("Accepted exact native frame and current pixels required")
        fingerprint = self.reader.fingerprint
        profile_fp = _digest(self.profile)
        scope = _digest(
            {
                "source": frame.source_sha256,
                "epoch": frame.native_epoch,
                "group": frame.leakage_group_id,
                "split": frame.split,
                "exposure": frame.exposure_fingerprint,
                "extraction": frame.extraction_fingerprint,
                "reader": fingerprint,
                "profile": profile_fp,
                "map": definition.data,
            }
        )
        if self._scope != scope:
            self.reset()
            self._scope = scope
        ui = self.reader.inspect(image, sample) if cached_ui is None else deepcopy(cached_ui)
        if (
            ui.get("fingerprint") != fingerprint
            or ui.get("source_profile_fingerprint") != profile_fp
        ):
            raise ValueError("Cached UI reader/Profile/reference changed")
        owner = self.owner.observe(sample, ui, continuity=continuity, initial_review=initial_review)
        bounds = normalized_roi_bounds(
            self.profile.get("rois", {}).get("minimap"), *frame.frame_size_px
        )
        if bounds is None:
            raise ValueError("Explicit minimap Geometry required")
        left, top, right, bottom = bounds
        if isinstance(self.map.marker, DevelopmentOwnerMarkerTracker):
            self.map.marker.set_observation(
                owner,
                marker_binding=self.profile.get("development_marker_binding"),
                expected_crop_pixel_sha256=hashlib.sha256(
                    image[top:bottom, left:right].tobytes()
                ).hexdigest(),
                context_fingerprint=_digest({"scope": scope, "ROI": bounds}),
            )
        live = owner["life"] == "alive" and owner["view"] == "self"
        time_sec = float(Fraction(frame.native_pts_tick) * Fraction(frame.native_time_base))
        mapped = self.map.observe(
            image,
            time_sec,
            frame.native_pts_tick,
            view={
                "primary_state": "live_first_person" if live else "unknown",
                "values": {"player_specific_hud_valid": live},
                "state_flags": ["buy_phase_banner"] if ui["purchase_phase_visible"] else [],
            },
            evidence_kind="unqualified_hud_observation",
            source_id=sample["source_id"],
            acquisition_id=frame.acquisition_id,
            source_sha256=frame.source_sha256,
        )
        return {
            "sample": deepcopy(sample),
            "owner": owner,
            "map": mapped,
            "reader_fingerprint": fingerprint,
            "profile_fingerprint": profile_fp,
            "run_scope_fingerprint": scope,
            "geometry_version": definition.geometry_version,
            "exposure_fingerprint": frame.exposure_fingerprint,
            "qualification": "development_only",
            "ownership": "UNKNOWN",
            "formal_outputs": 0,
            "marker_execution": deepcopy(getattr(self.map.marker, "execution", {})),
            "marker_evidence": deepcopy(getattr(self.map.marker, "last_evidence", {})),
        }
