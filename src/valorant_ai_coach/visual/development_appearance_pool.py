"""Bounded contrastive appearance libraries; roles never transfer as ownership."""

from __future__ import annotations

import hashlib
import json
from typing import Any

from numpy.typing import NDArray

from .self_marker import MarkerPosition, SelfMarkerTracker


class ContrastiveAppearancePool(SelfMarkerTracker):
    """Reuse authored positive/control distinctions without selecting a recording.

    The underlying matchers retain their original thresholds. One unambiguous
    library candidate is required, with no ambiguity reported by another member.
    Appearance selection is not an Agent, recorder or current-camera identity.
    """

    def __init__(self, *, excluded_source_id: str | None = None) -> None:
        super().__init__()
        self.excluded_source_id = excluded_source_id
        self.members = [SelfMarkerTracker() for _ in range(4)]
        self._pool_fingerprint: str | None = None
        self._selected: tuple[int, int | None] | None = None
        self._serial = 0
        self.last_evidence: dict[str, Any] = {}

    @property
    def reference_fingerprint(self) -> str | None:
        return self._pool_fingerprint

    def reset(self) -> None:
        super().reset()
        for member in getattr(self, "members", []):
            member.reset()
        self._selected = None

    def observe(
        self, crop: NDArray[Any], time_sec: float, spec: dict[str, Any], *,
        ownership_eligible: bool,
    ) -> MarkerPosition:
        self.last_evidence = {"qualification": "development_only", "ownership": "UNKNOWN",
                              "semantic_recorder_link": False, "members": []}

        def unknown(reason: str, count: int = 0) -> MarkerPosition:
            self.reset()
            return MarkerPosition("unknown", reason, count)

        if not ownership_eligible:
            return unknown("ownership_blocked")
        if (not isinstance(spec, dict) or spec.get("mode") != "appearance_pool_v1"
                or not isinstance(spec.get("libraries"), list)
                or not 1 <= len(spec["libraries"]) <= 4):
            self._pool_fingerprint = None
            return unknown("invalid_appearance_pool")
        libraries = spec["libraries"]
        if any(not isinstance(s, dict) or s.get("role") != "appearance_contrast_only"
               or not isinstance(s.get("source_id"), str) or not s["source_id"]
               or not isinstance(s.get("matcher"), dict) for s in libraries):
            self._pool_fingerprint = None
            return unknown("invalid_appearance_pool")
        libraries = [s for s in libraries if s["source_id"] != self.excluded_source_id]
        if not libraries:
            self._pool_fingerprint = None
            return unknown("appearance_pool_vocabulary_unavailable")
        active = self.members[:len(libraries)]
        if not all(member._load(s["matcher"]) for member, s in zip(active, libraries, strict=True)):
            self._pool_fingerprint = None
            return unknown("invalid_appearance_pool")
        try:
            fingerprint = hashlib.sha256(json.dumps({
                "spec": spec, "excluded_source_id": self.excluded_source_id,
                "members": [m.reference_fingerprint for m in active],
            }, sort_keys=True, allow_nan=False).encode("utf-8")).hexdigest()
        except (ValueError, TypeError):
            self._pool_fingerprint = None
            return unknown("invalid_appearance_pool")
        if fingerprint != self._pool_fingerprint:
            self.reset()
        self._pool_fingerprint = fingerprint
        values = [member.observe(crop, time_sec, s["matcher"], ownership_eligible=True)
                  for member, s in zip(active, libraries, strict=True)]
        self.last_evidence.update(members=[v.to_dict() for v in values],
                                  reference_fingerprint=fingerprint)
        candidates = [(i, v) for i, v in enumerate(values) if v.x_roi_norm is not None]
        if any(v.reason == "appearance_ambiguous" for v in values) or len(candidates) > 1:
            return unknown("appearance_pool_ambiguous", max(
                len(candidates), *(v.candidate_count for v in values)))
        if not candidates:
            return unknown("appearance_pool_unavailable")
        index, value = candidates[0]
        selected = index, value.track_id
        if selected != self._selected:
            self._serial += 1
        self._selected = selected
        return MarkerPosition(value.status, "contrastive_pool_appearance_only", 1,
                              value.x_roi_norm, value.y_roi_norm, value.appearance_score,
                              self._serial)
