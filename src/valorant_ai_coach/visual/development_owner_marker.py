"""UI-bound initialization, then local same-appearance tracking; offline only.

The remembered marker ID survives a short occlusion. Missing/blocked/ambiguous
current pixels never produce a position. No Production ownership is established.
"""

from __future__ import annotations

import hashlib
import math
from copy import deepcopy
from fractions import Fraction
from typing import Any

import cv2
import numpy as np

from .development_identity_metrics import marker_binding_matches
from .development_marker_attribution import _sha, freeze_native_sample
from .development_marker_features import _digest
from .self_marker import Image, MarkerPosition, SelfMarkerTracker


class DevelopmentOwnerMarkerTracker(SelfMarkerTracker):
    """Injectable into existing DevelopmentMapTimeline, without changing defaults."""

    def __init__(self) -> None:
        super().__init__()
        self._current: dict[str, Any] | None = None
        self._identity: int | None = None
        self._point: tuple[float, float] | None = None
        self._patch: Image | None = None
        self._last_observed: float | None = None
        self._last_sample: dict[str, Any] | None = None
        self._context_key: str | None = None
        self.execution = {
            "global_initializations": 0,
            "local_searches": 0,
            "successful_initializations": 0,
        }
        self.last_evidence: dict[str, Any] = {}

    @property
    def identity_memory(self) -> int | None:
        return self._identity

    def reset(self) -> None:
        super().reset()
        self._identity = None
        self._point = self._patch = self._last_observed = None
        self._last_sample = None
        self._context_key = None

    def set_observation(
        self,
        owner: dict[str, Any],
        *,
        marker_binding: dict[str, Any] | None,
        expected_crop_pixel_sha256: str,
        context_fingerprint: str,
    ) -> None:
        sample = owner.get("sample", {})
        size = sample.get("frame_size_px")
        if (
            not isinstance(size, list)
            or len(size) != 2
            or freeze_native_sample(sample, frame_size_px=tuple(size)) != sample
            or owner.get("sample_sha256") != sample["sample_sha256"]
            or owner.get("qualified") is not False
            or owner.get("formal_outputs") != 0
            or owner.get("ownership") != "UNKNOWN"
            or owner.get("qualification") != "development_only"
            or owner.get("life") not in {"unknown", "alive", "dead", "downed"}
            or owner.get("view") not in {"unknown", "self", "spectator", "remote"}
            or type(owner.get("native_continuity_used")) is not bool
            or not _sha(expected_crop_pixel_sha256)
            or not _sha(context_fingerprint)
        ):
            self.reset()
            self._current = None
            raise ValueError("Bound current owner hypothesis and actual crop required")
        self._current = {
            "owner": deepcopy(owner),
            "binding": deepcopy(marker_binding),
            "crop_sha256": expected_crop_pixel_sha256,
            "context": context_fingerprint,
        }

    def observe(
        self,
        crop: Image,
        time_sec: float,
        spec: dict[str, Any],
        *,
        ownership_eligible: bool,
    ) -> MarkerPosition:
        try:
            return self._observe(crop, time_sec, spec, ownership_eligible)
        except Exception:
            self.reset()
            self._current = None
            raise

    def _observe(
        self,
        crop: Image,
        time_sec: float,
        spec: dict[str, Any],
        eligible: bool,
    ) -> MarkerPosition:
        if (
            self._current is None
            or type(eligible) is not bool
            or not isinstance(crop, np.ndarray)
            or crop.dtype != np.uint8
            or crop.ndim != 3
            or crop.shape[2] != 3
            or crop.shape[0] * crop.shape[1] > 1_000_000
            or not isinstance(time_sec, (int, float))
            or isinstance(time_sec, bool)
            or not math.isfinite(time_sec)
        ):
            raise ValueError("Bounded current native crop and time required")
        current = self._current
        owner = current["owner"]
        sample = owner["sample"]
        expected = float(Fraction(sample["native_pts_tick"]) * Fraction(sample["native_time_base"]))
        if (
            not math.isclose(time_sec, expected, rel_tol=0, abs_tol=1e-8)
            or hashlib.sha256(crop.tobytes()).hexdigest() != current["crop_sha256"]
        ):
            raise ValueError("Current crop/native time does not match owner observation")
        if not self._load(spec):
            self.reset()
            return self._missing("invalid_reference_profile")
        h, w = self._references[0].shape[:2]
        if crop.shape[0] < h or crop.shape[1] < w:
            self.reset()
            return self._missing("invalid_roi")
        key = _digest(
            {
                "source": sample["source_sha256"],
                "id": sample["source_id"],
                "epoch": sample["native_epoch"],
                "base": sample["native_time_base"],
                "shape": list(crop.shape),
                "context": current["context"],
                "profile": owner["raw_ui"]["source_profile_fingerprint"],
                "reference": self.reference_fingerprint,
            }
        )
        if self._context_key != key or not owner["native_continuity_used"]:
            self.reset()
        elif self._last_sample is not None:
            dt = (
                Fraction(sample["native_pts_tick"]) - self._last_sample["native_pts_tick"]
            ) * Fraction(sample["native_time_base"])
            if not 0 < dt <= Fraction(3, 10):
                self.reset()
        self._context_key = key
        self._last_sample = deepcopy(sample)
        if owner["life"] in {"dead", "downed"} or owner["view"] in {"spectator", "remote"}:
            self.reset()
            return self._missing("owner_not_live_self")
        if owner["life"] != "alive" or owner["view"] != "self":
            # Missing pixels alone leave ALIVE/SELF in the temporal model.
            # UNKNOWN here means lost/conflicting owner context, not occlusion.
            self.reset()
            return self._missing("owner_state_unknown")
        binding = current["binding"]
        agent = owner["raw_ui"].get("agent_measurements", {}).get("recorder_agent_id")
        if not isinstance(binding, dict) or not marker_binding_matches(
            binding,
            source_id=sample["source_id"],
            source_sha256=sample["source_sha256"],
            recorder_agent_id=agent,
            reference_fingerprint=self.reference_fingerprint,
        ):
            self.reset()
            return self._missing("initial_UI_marker_binding_unavailable")
        if self._last_observed is not None and time_sec - self._last_observed > 0.6:
            self._identity = self._point = self._patch = self._last_observed = None
        if not eligible:
            return self._missing("current_map_context_blocked")
        if self._identity is None:
            direct = owner["raw_ui"].get("own_hud_support") is True
            reviewed = owner.get("state_origin") == "human_exact_frame"
            anchor = owner.get("last_direct_alive_sample")
            carried_anchor = False
            if isinstance(anchor, dict) and owner["native_continuity_used"]:
                try:
                    carried_anchor = (
                        freeze_native_sample(anchor, frame_size_px=tuple(sample["frame_size_px"]))
                        == anchor
                        and all(
                            anchor[k] == sample[k]
                            for k in (
                                "source_id",
                                "source_sha256",
                                "native_epoch",
                                "acquisition_id",
                                "native_time_base",
                                "frame_size_px",
                            )
                        )
                        and anchor["native_pts_tick"] < sample["native_pts_tick"]
                        and owner.get("state_origin") == "temporal_inference"
                        and owner.get("anchor_origin") in {"image_reader", "human_exact_frame"}
                    )
                except (ValueError, KeyError, TypeError):
                    carried_anchor = False
            if not direct and not reviewed and not carried_anchor:
                return self._missing("initial_UI_binding_required_not_global_reidentification")
            self.execution["global_initializations"] += 1
            result = super().observe(crop, time_sec, spec, ownership_eligible=True)
            if result.x_roi_norm is None:
                return self._missing(result.reason)
            assert result.y_roi_norm is not None
            x = round(result.x_roi_norm * crop.shape[1])
            y = round(result.y_roi_norm * crop.shape[0])
            self._identity = result.track_id
            self._point = (float(x), float(y))
            self._last_observed = time_sec
            self._patch = crop[y - h // 2 : y + h // 2 + 1, x - w // 2 : x + w // 2 + 1].copy()
            # The reused initializer can reset on its first ROI shape. Restore
            # only the current verified context, never any pre-reset identity.
            self._context_key = key
            self._last_sample = deepcopy(sample)
            self.execution["successful_initializations"] += 1
            self.last_evidence = {
                "mode": "UI_initialization",
                "anchor_origin": owner.get("anchor_origin"),
                "remembered_marker_id": self._identity,
                "current_position_observed": True,
            }
            return result
        assert (
            self._point is not None and self._patch is not None and self._last_observed is not None
        )
        self.execution["local_searches"] += 1
        x0, y0 = self._point
        left = max(0, round(x0) - 24 - w // 2)
        top = max(0, round(y0) - 24 - h // 2)
        right = min(crop.shape[1], round(x0) + 24 + w // 2 + 1)
        bottom = min(crop.shape[0], round(y0) + 24 + h // 2 + 1)
        region = crop[top:bottom, left:right]
        if region.shape[0] < h or region.shape[1] < w:
            return self._missing("local_region_unavailable")
        # Use the same authored portrait foreground as the initializer. Whole
        # patch NCC would accidentally compare changing map pixels as identity.
        temporal = self._scores(region, self._patch)
        positive = np.maximum.reduce([self._scores(region, r) for r in self._references])
        negative = np.maximum.reduce([self._scores(region, r) for r in self._negatives])
        temporal = np.clip(np.nan_to_num(temporal, nan=-1, posinf=-1, neginf=-1), -1, 1)
        positive = np.clip(np.nan_to_num(positive, nan=-1, posinf=-1, neginf=-1), -1, 1)
        negative = np.clip(np.nan_to_num(negative, nan=1, posinf=1, neginf=1), -1, 1)
        scores = np.where((positive >= 0.80) & (positive - negative >= 0.12), temporal, -1)
        _, best, _, (x, y) = cv2.minMaxLoc(scores)
        if best < 0.90:
            return self._missing("same_marker_current_appearance_missing")
        suppressed = scores.copy()
        suppressed[max(0, y - h // 2) : y + h // 2 + 1, max(0, x - w // 2) : x + w // 2 + 1] = -1
        if best - float(suppressed.max()) < 0.12:
            return self._missing("local_appearance_ambiguous")
        point = (float(left + x + w // 2), float(top + y + h // 2))
        dt = time_sec - self._last_observed
        displacement = math.dist(
            (point[0] / crop.shape[1], point[1] / crop.shape[0]),
            (x0 / crop.shape[1], y0 / crop.shape[0]),
        )
        if dt <= 0 or displacement / dt > 0.4:
            return self._missing("position_jump")
        self._point = point
        self._last_observed = time_sec
        xx, yy = map(round, point)
        self._patch = crop[yy - h // 2 : yy + h // 2 + 1, xx - w // 2 : xx + w // 2 + 1].copy()
        self.last_evidence = {
            "mode": "local_same_marker",
            "remembered_marker_id": self._identity,
            "current_position_observed": True,
            "gap_interpolated": False,
        }
        return MarkerPosition(
            "tracked",
            "local_same_marker",
            1,
            point[0] / crop.shape[1],
            point[1] / crop.shape[0],
            float(best),
            self._identity,
        )

    def _missing(self, reason: str) -> MarkerPosition:
        self.last_evidence = {
            "mode": "no_current_position",
            "reason": reason,
            "remembered_marker_id": self._identity,
            "current_position_observed": False,
            "gap_interpolated": False,
        }
        return MarkerPosition("unknown", reason)
