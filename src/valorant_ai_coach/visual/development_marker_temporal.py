"""Observed-endpoint appearance associations, not paths or ownership facts.

Reuses the existing marker/timeline continuity policy (positive PTS, <=.3s and
matching acquisition/profile/ROI). A caller supplies a current native continuity
receipt; time proximity alone never creates it. PR107 hypotheses are separate
unqualified view inputs, not an image reader or recorder-to-marker link.
"""

from __future__ import annotations

import math
from copy import deepcopy
from fractions import Fraction
from typing import Any

import numpy as np

from .development_marker_attribution import freeze_native_sample
from .development_marker_features import Array, _digest


class DevelopmentMarkerAssociations:
    """Ambiguity-rejecting appearance AND position links between observed points."""

    def __init__(self) -> None:
        self._previous: dict[str, Any] | None = None

    def reset(self) -> None:
        self._previous = None

    def observe(
        self,
        sample: dict[str, Any],
        pool: dict[str, Any],
        appearance: Array,
        *,
        appearance_fingerprint: str,
        continuity: dict[str, Any] | None,
        hud: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        try:
            return self._observe(
                sample,
                pool,
                appearance,
                appearance_fingerprint=appearance_fingerprint,
                continuity=continuity,
                hud=hud,
            )
        except Exception:
            # Invalid identity/geometry/features can raise inside validation.
            # Propagate the error, but never let the next valid observation
            # reconnect to state from before the rejected observation.
            self.reset()
            raise

    def _observe(
        self,
        sample: dict[str, Any],
        pool: dict[str, Any],
        appearance: Array,
        *,
        appearance_fingerprint: str,
        continuity: dict[str, Any] | None,
        hud: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        size = sample.get("frame_size_px")
        if (
            not isinstance(size, list)
            or len(size) != 2
            or freeze_native_sample(sample, frame_size_px=tuple(size)) != sample
            or pool.get("sample") != sample
            or pool.get("ownership") != "UNKNOWN"
            or pool.get("formal_outputs") != 0
            or pool.get("pool_sha256")
            != _digest({k: v for k, v in pool.items() if k != "pool_sha256"})
        ):
            self.reset()
            raise ValueError("Bound current native candidate pool required")
        n = len(pool["candidates"])
        if (
            not 0 <= n <= 320
            or not isinstance(appearance, np.ndarray)
            or appearance.ndim != 2
            or len(appearance) != n
            or not 1 <= appearance.shape[1] <= 4096
            or not np.isfinite(appearance).all()
            or len(appearance_fingerprint) != 64
        ):
            self.reset()
            raise ValueError("Bounded paired appearance features required")
        unit = appearance / np.maximum(np.linalg.norm(appearance, axis=1, keepdims=True), 1e-12)
        prior = self._previous
        key = _digest(
            {
                "source": sample["source_sha256"],
                "epoch": sample["native_epoch"],
                "base": sample["native_time_base"],
                "roi": pool["roi_xywh"],
                "profile": pool["profile_fingerprint"],
                "shape": size,
                "map": pool["map_id_candidate"],
                "build": pool["map_build"],
                "feature": appearance_fingerprint,
            }
        )
        reason = "first_observation"
        allowed = False
        view = {
            "life": "unknown",
            "view": "unknown",
            "self_marker_id": None,
            "qualified": False,
            "origin": "no_positive_owner_UI",
        }
        if hud is not None:
            if (
                hud.get("sample_sha256") != sample["sample_sha256"]
                or hud.get("qualified") is not False
                or hud.get("origin")
                not in {"image_reader", "human_exact_frame", "no_positive_owner_UI"}
                or hud.get("life") not in {"unknown", "alive", "dead", "downed"}
                or hud.get("view") not in {"unknown", "self", "spectator", "remote"}
            ):
                self.reset()
                raise ValueError("Source-bound unqualified view hypothesis required")
            view = deepcopy(hud)
        if prior is not None:
            dt = (
                Fraction(sample["native_pts_tick"]) * Fraction(sample["native_time_base"])
                - prior["time"]
            )
            allowed = bool(
                continuity
                and continuity.get("verified") is True
                and continuity.get("source_sha256") == sample["source_sha256"]
                and continuity.get("native_epoch") == sample["native_epoch"]
                and continuity.get("previous_sample_sha256") == prior["sample"]["sample_sha256"]
                and continuity.get("current_sample_sha256") == sample["sample_sha256"]
                and continuity.get("time_base") == sample["native_time_base"]
                and isinstance(continuity.get("receipt_sha256"), str)
                and len(continuity["receipt_sha256"]) == 64
                and prior["key"] == key
                and 0 < dt <= Fraction(3, 10)
            )
            reason = "observed_continuity" if allowed else "source_or_continuity_reset"
            if view["view"] != prior["view"]["view"] and (
                view["view"] != "unknown" or prior["view"]["view"] != "unknown"
            ):
                allowed, reason = False, "view_change_reset"
            elif view["life"] != prior["view"]["life"]:
                allowed, reason = False, "life_change_reset"
        links: list[dict[str, Any]] = []
        ambiguous = 0
        if allowed and prior is not None and n and len(prior["points"]):
            points = np.asarray([p["center_frame_px"] for p in pool["candidates"]])
            previous = np.asarray(prior["points"])
            distance = np.linalg.norm(points[:, None, :] - previous[None, :, :], axis=2)
            similarity = unit @ prior["unit"].T
            cost = 1 - similarity + distance / 40
            valid = (distance <= 12) & (similarity >= 0.90)
            cost[~valid] = math.inf
            for i, row in enumerate(cost):
                order = np.argsort(row, kind="stable")
                j = int(order[0])
                if not math.isfinite(float(row[j])):
                    continue
                reverse = np.argsort(cost[:, j], kind="stable")
                second = float(row[order[1]]) if len(order) > 1 else math.inf
                reverse_second = float(cost[reverse[1], j]) if len(reverse) > 1 else math.inf
                if int(reverse[0]) != i or min(second - row[j], reverse_second - row[j]) < 0.10:
                    ambiguous += 1
                    continue
                links.append(
                    {
                        "previous_index": j,
                        "current_index": i,
                        "distance_px": float(distance[i, j]),
                        "appearance_cosine": float(similarity[i, j]),
                        "physical_identity": "UNKNOWN",
                        "kind": "observed_endpoint_association",
                    }
                )
        current = {
            "sample": deepcopy(sample),
            "key": key,
            "time": Fraction(sample["native_pts_tick"]) * Fraction(sample["native_time_base"]),
            "points": [p["center_frame_px"].copy() for p in pool["candidates"]],
            "unit": unit.copy(),
            "view": deepcopy(view),
        }
        self._previous = current if n else None
        return {
            "sample_sha256": sample["sample_sha256"],
            "links": links,
            "ambiguous_links_rejected": ambiguous,
            "reason": reason,
            "continuity_allowed": allowed,
            "view_hypothesis": view,
            "recorder_view_veto": view["view"] in {"spectator", "remote"}
            or view["life"] in {"dead", "downed"},
            "generic_markers_preserved": True,
            "self_marker_binding_qualified": False,
            "ownership": "UNKNOWN",
            "qualification": "development_only",
            "formal_outputs": 0,
        }
