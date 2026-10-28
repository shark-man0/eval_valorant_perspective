"""Source-bound automatic association candidates; never qualified owner paths.

Initialization consumes image-reader output, not a human marker ID. Thereafter
PR109 supplies mutual appearance/position links. Occlusion retains identity only;
a bounded unique reappearance can resume observations in a NEW display segment.
No intermediate position, camera identity, recorder death or zone is invented.
"""

from __future__ import annotations

import math
from fractions import Fraction
from typing import Any

import cv2
import numpy as np

from .development_camera_marker_ui import UI_FINGERPRINT
from .development_marker_features import Array, _digest, bound_patches
from .development_marker_temporal import DevelopmentMarkerAssociations
from .development_marker_topk import _native
from .development_owner_state import DevelopmentOwnerTimeline, MarkerObservation, OwnerObservation
from .development_self_timeline import SelfFrameCues

OWNER_TRACK_FEATURE_FINGERPRINT = _digest(
    {
        "feature": "native_circle7_mean_centered_BGR_gaussian5_sigma1.2",
        "opencv": cv2.__version__,
        "numpy": np.__version__,
        "gap": 0.3,
        "reappearance_gap": 0.6,
        "cosine": 0.90,
        "distance": 12,
        "margin": 0.10,
    }
)


def owner_tracking_features(frame: Array, sample: dict[str, Any], pool: dict[str, Any]) -> Array:
    """Translation-tolerant native appearance, without adding/changing centers."""
    _native(frame, sample)
    n = pool["parent_count"]
    if type(n) is not int or not 0 <= n <= 128 or n > len(pool["candidates"]):
        raise ValueError("Bounded parent candidates required")
    if not n:
        return np.empty((0, 447), dtype=np.float64)
    patches, _ = bound_patches(
        frame, sample, [p["center_frame_px"] for p in pool["candidates"][:n]], radius=17
    )
    yy, xx = np.mgrid[-17:18, -17:18]
    mask = xx * xx + yy * yy <= 49
    features = np.array(
        [cv2.GaussianBlur(p, (5, 5), 1.2)[mask].astype(float).ravel() for p in patches]
    )
    features -= features.mean(axis=1, keepdims=True)
    return features


class DevelopmentOwnerTracking:
    """Per-acquisition state. Camera/owner life and marker position stay separate."""

    def __init__(self) -> None:
        self.reset()

    def reset(self) -> None:
        self.links = DevelopmentMarkerAssociations()
        self.state = DevelopmentOwnerTimeline()
        self.previous: dict[str, Any] | None = None
        self.memory: dict[str, Any] | None = None
        self.context: str | None = None
        self.identity_lineage_id: str | None = None
        self.segment = 0
        self.previous_observed = False

    def observe(
        self,
        *,
        sample: dict[str, Any],
        pool: dict[str, Any],
        ui: dict[str, Any],
        proposal: dict[str, Any],
        features: Array,
        identity_context_fingerprint: str,
        continuity: dict[str, Any] | None,
    ) -> dict[str, Any]:
        try:
            return self._observe(
                sample=sample,
                pool=pool,
                ui=ui,
                proposal=proposal,
                features=features,
                identity_context_fingerprint=identity_context_fingerprint,
                continuity=continuity,
            )
        except Exception:
            self.reset()
            raise

    def _observe(
        self,
        *,
        sample: dict[str, Any],
        pool: dict[str, Any],
        ui: dict[str, Any],
        proposal: dict[str, Any],
        features: Array,
        identity_context_fingerprint: str,
        continuity: dict[str, Any] | None,
    ) -> dict[str, Any]:
        n = pool["parent_count"]
        if (
            type(n) is not int
            or not 0 <= n <= 128
            or n > len(pool["candidates"])
            or ui.get("sample_sha256") != sample["sample_sha256"]
            or ui.get("pool_sha256") != pool.get("pool_sha256")
            or ui.get("feature_fingerprint") != UI_FINGERPRINT
            or pool.get("pool_sha256")
            != _digest({k: v for k, v in pool.items() if k != "pool_sha256"})
            or len(ui.get("rows", [])) != n
            or proposal.get("sample_sha256") != sample["sample_sha256"]
            or proposal.get("ownership") != "UNKNOWN"
            or proposal.get("formal_outputs") != 0
            or proposal.get("recorder_account_identity_qualified") is not False
            or not isinstance(features, np.ndarray)
            or features.shape != (n, 447)
            or not np.isfinite(features).all()
            or len(identity_context_fingerprint) != 64
            or any(c not in "0123456789abcdef" for c in identity_context_fingerprint)
        ):
            raise ValueError("Same-frame unqualified UI/proposal/context required")
        ids = []
        for i, r in enumerate(ui["rows"]):
            identifier = _digest(
                {"sample": sample["sample_sha256"], "pool": pool["pool_sha256"], "index": i}
            )
            if r["candidate_index"] != i or r["marker_observation_id"] != identifier:
                raise ValueError("Image-derived current candidate IDs required")
            ids.append(identifier)
        fresh = proposal.get("candidate_index")
        if proposal.get("marker_id") is not None and (
            type(fresh) is not int
            or not 0 <= fresh < n
            or proposal["marker_id"] != ids[fresh]
            or proposal.get("binding_origin") != "automatic_ui"
            or proposal.get("camera") != "first_person_candidate"
        ):
            raise ValueError("Automatic current-image initialization required")
        scope = _digest(
            {
                "identity": identity_context_fingerprint,
                "source": sample["source_sha256"],
                "epoch": sample["native_epoch"],
                "base": sample["native_time_base"],
                "size": sample["frame_size_px"],
                "roi": pool["roi_xywh"],
                "profile": pool["profile_fingerprint"],
                "map": pool["map_id_candidate"],
                "build": pool["map_build"],
            }
        )
        prior = self.previous["sample"] if self.previous else None
        receipt_hash = continuity.get("receipt_sha256") if continuity else None
        continuous = bool(
            prior
            and continuity
            and self.context == scope
            and continuity.get("verified") is True
            and continuity.get("source_sha256") == sample["source_sha256"]
            and continuity.get("native_epoch") == sample["native_epoch"]
            and continuity.get("time_base") == sample["native_time_base"]
            and continuity.get("previous_sample_sha256") == prior["sample_sha256"]
            and continuity.get("current_sample_sha256") == sample["sample_sha256"]
            and isinstance(receipt_hash, str)
            and len(receipt_hash) == 64
            and all(c in "0123456789abcdef" for c in receipt_hash)
            and 0
            < (sample["native_pts_tick"] - prior["native_pts_tick"])
            * Fraction(sample["native_time_base"])
            <= Fraction(3, 10)
        )
        if self.context != scope:
            self.links.reset()
            self.memory = None
        self.context = scope
        parent = {**pool, "candidates": pool["candidates"][:n]}
        parent.pop("pool_sha256")
        parent["pool_sha256"] = _digest(parent)
        association = self.links.observe(
            sample,
            parent,
            features,
            appearance_fingerprint=OWNER_TRACK_FEATURE_FINGERPRINT,
            continuity=continuity,
        )
        if not continuous:
            self.memory = None
            self.identity_lineage_id = None
        unit = features / np.maximum(np.linalg.norm(features, axis=1, keepdims=True), 1e-12)
        eligible = {
            r["candidate_index"]
            for r in ui["rows"]
            if r["warm_rim_arc"] >= 0.15 and r["radial_alignment"] >= 0.55
        }
        previous_id = self.memory["id"] if self.memory else None
        pairs = (
            [
                (self.previous["ids"][v["previous_index"]], ids[v["current_index"]])
                for v in association["links"]
            ]
            if self.previous and continuous
            else []
        )
        matches = [b for a, b in pairs if a == previous_id and ids.index(b) in eligible]
        index = ids.index(matches[0]) if len(matches) == 1 else None
        origin = "temporal_endpoint_link" if index is not None else "missing"
        ambiguous = len(matches) > 1
        if index is None and self.memory and continuous:
            memory = self.memory
            dt = (sample["native_pts_tick"] - memory["pts"]) * Fraction(sample["native_time_base"])
            possible = (
                [
                    i
                    for i in eligible
                    if float(unit[i] @ memory["feature"]) >= 0.90
                    and math.dist(pool["candidates"][i]["center_frame_px"], memory["point"]) <= 12
                ]
                if 0 < dt <= Fraction(3, 5)
                else []
            )
            ambiguous = len(possible) > 1
            if len(possible) == 1:
                index = possible[0]
                pairs = [(memory["id"], ids[index])]
                origin = "unique_reappearance"
        if proposal.get("marker_id") is not None:
            if index is not None and fresh != index:
                index, origin, ambiguous = None, "conflicting_initialization", True
            elif index is not None:
                origin, ambiguous = "automatic_UI_refresh", False
            else:
                index, origin, ambiguous = fresh, "automatic_UI_initial", False
        initialize = origin in {"automatic_UI_initial", "automatic_UI_refresh"}
        spectating = proposal.get("camera") == "spectator"
        if spectating:
            index, origin, self.memory = None, "positive_spectator_veto", None
            self.identity_lineage_id = None
        markers = []
        for i, p in enumerate(parent["candidates"]):
            point = p.get("geometry_only_map_position_norm")
            mapped = (
                tuple(point)
                if point is not None
                and len(point) == 2
                and all(math.isfinite(v) and 0 <= v <= 1 for v in point)
                else None
            )
            markers.append(MarkerObservation(ids[i], tuple(p["center_frame_px"]), mapped))
        cue = SelfFrameCues(
            sample["source_sha256"],
            sample["native_epoch"],
            sample["native_pts_tick"],
            Fraction(sample["native_time_base"]),
            continuous_from_previous=continuous,
            spectator_ui=spectating,
        )
        state = self.state.observe(
            OwnerObservation(
                cue=cue,
                first_person_candidate=index is not None and not spectating,
                binding_marker_id=proposal.get("marker_id")
                if initialize and not spectating
                else None,
                binding_origin="automatic_ui" if initialize and not spectating else "none",
                binding_evidence_sha256=proposal.get("evidence_sha256"),
                markers=tuple(markers),
                context_fingerprint=scope,
                associations=((previous_id, ids[index]),)
                if previous_id and index is not None and origin != "automatic_UI_initial"
                else (),
                ambiguous_reappearance=ambiguous,
            )
        )
        observed = state["current_position_observed"]
        connected = bool(
            observed
            and self.previous_observed
            and continuous
            and origin in {"temporal_endpoint_link", "automatic_UI_refresh"}
        )
        if observed:
            assert index is not None
            if origin == "automatic_UI_initial":
                self.identity_lineage_id = _digest(
                    {
                        "scope": scope,
                        "initial_marker": ids[index],
                        "evidence": proposal["evidence_sha256"],
                    }
                )
            if not connected:
                self.segment += 1
            self.memory = {
                "id": ids[index],
                "pts": sample["native_pts_tick"],
                "point": parent["candidates"][index]["center_frame_px"],
                "feature": unit[index].copy(),
            }
        self.previous_observed = bool(observed)
        self.previous = {"ids": ids, "sample": sample.copy()}
        return {
            **state,
            "sample_sha256": sample["sample_sha256"],
            "identity_lineage_id": self.identity_lineage_id,
            "identity_lineage_qualified": False,
            "association": association,
            "selection_origin": origin,
            "selected_index": index if observed else None,
            "observed_segment_id": self.segment if observed else None,
            "connected_to_previous_observation": connected,
            "connection_kind": "observed_endpoints_not_actual_continuous_path"
            if connected
            else None,
            "feature_fingerprint": OWNER_TRACK_FEATURE_FINGERPRINT,
        }
