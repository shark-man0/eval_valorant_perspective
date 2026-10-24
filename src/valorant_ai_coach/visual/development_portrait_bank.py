"""Experimental portable portrait appearances, never recorder ownership.

An authored teammate portrait can be a texture reference for another recording.
Its semantic role is not transferred. A spatial annulus and inner texture are
required in addition to appearance, and multiple supported icons remain UNKNOWN.
The ordinary SelfMarkerTracker and its acceptance criteria are unchanged.
"""

from __future__ import annotations

import hashlib
import json
import math
from typing import Any

import cv2
import numpy as np
from numpy.typing import NDArray

from .self_marker import MarkerPosition, SelfMarkerTracker


class PortablePortraitTracker(SelfMarkerTracker):
    """Opt-in fixed-geometry pool; no learned identity or historical selection."""

    def __init__(self, *, excluded_source_id: str | None = None) -> None:
        super().__init__()
        self.excluded_source_id = excluded_source_id
        self._portable_fingerprint: str | None = None
        self._reference_loaders = [SelfMarkerTracker() for _ in range(4)]
        self.last_evidence: dict[str, Any] = {}

    @property
    def reference_fingerprint(self) -> str | None:
        return self._portable_fingerprint

    def observe(
        self, crop: NDArray[Any], time_sec: float, spec: dict[str, Any], *,
        ownership_eligible: bool,
    ) -> MarkerPosition:
        self.last_evidence = {
            "qualification": "development_only", "ownership": "UNKNOWN",
            "candidate_kind": "primary_style_portrait_appearance",
            "semantic_recorder_link": False, "matches": [],
        }

        def unknown(reason: str, count: int = 0) -> MarkerPosition:
            self.reset()
            return MarkerPosition("unknown", reason, count)

        if not ownership_eligible:
            return unknown("ownership_blocked")
        if (not isinstance(time_sec, (int, float)) or isinstance(time_sec, bool)
                or not math.isfinite(time_sec) or time_sec < 0):
            return unknown("invalid_time")
        if (not isinstance(spec, dict) or spec.get("mode") != "portable_portrait_v1"
                or not isinstance(spec.get("feature_mode", "bgr_v1"), str)
                or spec.get("feature_mode", "bgr_v1") not in {
                    "bgr_v1", "gray_v1", "gray_shared_v2"}
                or not isinstance(spec.get("templates"), list)
                or not 2 <= len(spec["templates"]) <= 48):
            self._portable_fingerprint = None
            return unknown("invalid_portable_reference_profile")
        references = spec["templates"]
        if any(not isinstance(r, dict) or not isinstance(r.get("source_id"), str)
               or not r["source_id"] or r.get("role") != "portrait_appearance_only"
               or not isinstance(r.get("path"), str) or not r["path"] for r in references):
            self._portable_fingerprint = None
            return unknown("invalid_portable_reference_profile")
        references = [r for r in references if r["source_id"] != self.excluded_source_id]
        if len(references) < 2:
            self._portable_fingerprint = None
            return unknown("portable_reference_vocabulary_unavailable")
        # Reuse the bounded content-hash/PNG/texture/shape loader only. Both
        # storage slots become generic portraits; neither assigns self/nonself.
        previous_fingerprint = self._portable_fingerprint
        group_count = math.ceil(len(references)/12)
        images: list[NDArray[Any]] = []
        digests: list[Any] = []
        loader_fingerprints: list[str | None] = []
        for index in range(group_count):
            group = references[index*len(references)//group_count:
                               (index+1)*len(references)//group_count]
            paths = [r["path"] for r in group]
            split = min(4, len(paths)-1)
            loader = self._reference_loaders[index]
            if not loader._load({"mode": "portrait_v2", "positive_templates": paths[:split],
                                 "negative_templates": paths[split:]}):
                self._portable_fingerprint = None
                return unknown("invalid_portable_reference_profile")
            assert loader._key is not None
            digests.extend(loader._key[-len(group):])
            images.extend([*loader._references, *loader._negatives])
            loader_fingerprints.append(loader.reference_fingerprint)
        if any(image.shape != images[0].shape for image in images):
            self._portable_fingerprint = None
            return unknown("portable_reference_geometry_unsupported")
        self._mask = self._reference_loaders[0]._mask
        if any("image_sha256" in ref and ref["image_sha256"] != digest
               for ref, digest in zip(references, digests, strict=True)):
            self._portable_fingerprint = None
            return unknown("portable_reference_digest_mismatch")
        try:
            fingerprint = hashlib.sha256(json.dumps({
                "loaders": loader_fingerprints, "spec": spec,
                "excluded_source_id": self.excluded_source_id,
            }, sort_keys=True, allow_nan=False).encode("utf-8")).hexdigest()
        except (ValueError, TypeError):
            self._portable_fingerprint = None
            return unknown("invalid_portable_reference_profile")
        if fingerprint != previous_fingerprint:
            self.reset()
        self._portable_fingerprint = fingerprint
        if (not isinstance(crop, np.ndarray) or crop.dtype != np.uint8 or crop.ndim != 3
                or crop.shape[2] != 3 or max(crop.shape[:2]) > 1024):
            return unknown("invalid_roi")
        templates = images
        h, w = templates[0].shape[:2]
        if min(crop.shape[:2]) < max(h, w) or h != w:
            return unknown("portable_reference_geometry_unsupported")
        if crop.shape != self._shape:
            self.reset()
            self._shape = crop.shape
        target = crop
        if spec.get("feature_mode", "bgr_v1") in {"gray_v1", "gray_shared_v2"}:
            target = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
            templates = [cv2.cvtColor(t, cv2.COLOR_BGR2GRAY) for t in templates]
        if spec.get("feature_mode") == "gray_shared_v2":
            scores = self._shared_gray_scores(target, templates)
        else:
            scores = self._scores(target, templates[0])
            for template in templates[1:]:
                np.maximum(scores, self._scores(target, template), out=scores)
        scores = np.clip(np.nan_to_num(scores, nan=-1, posinf=-1, neginf=-1), -1, 1)
        remaining = scores.copy()
        yy, xx = np.indices((h, w))
        radius = np.hypot(xx-w//2, yy-h//2)
        annulus = (radius >= w*.35) & (radius <= w*.53)
        inner = radius < w*.29
        matches = []
        for _ in range(64):
            _, score, _, (x, y) = cv2.minMaxLoc(remaining)
            if score < .80:
                break
            remaining[max(0, y-h//2):y+h//2+1, max(0, x-w//2):x+w//2+1] = -1
            patch = crop[y:y+h, x:x+w]
            channels = patch.astype(np.float32)
            chroma = np.minimum(channels[:, :, 2], channels[:, :, 1])-channels[:, :, 0]
            coverage = float((chroma[annulus] > 15).mean())
            quadrants = [float((chroma[annulus & (xx >= w//2 if hx else xx < w//2)
                                      & (yy >= h//2 if hy else yy < h//2)] > 15).mean())
                         for hx, hy in [(False, False), (False, True),
                                        (True, False), (True, True)]]
            texture = float(cv2.cvtColor(patch, cv2.COLOR_BGR2GRAY)[inner].std())
            if coverage >= .25 and sum(q >= .15 for q in quadrants) >= 3 and texture >= 12:
                matches.append({"x_roi_norm": (x+w//2)/crop.shape[1],
                                "y_roi_norm": (y+h//2)/crop.shape[0],
                                "portrait_similarity": float(score),
                                "annulus_coverage": coverage,
                                "annulus_quadrants": quadrants, "inner_texture_std": texture})
        self.last_evidence.update(matches=matches, reference_fingerprint=fingerprint,
                                  reference_count=len(references),
                                  feature_mode=spec.get("feature_mode", "bgr_v1"),
                                  search_truncated=bool(float(remaining.max()) >= .80))
        if self.last_evidence["search_truncated"]:
            return unknown("portable_search_truncated", len(matches))
        if len(matches) != 1:
            return unknown("portable_portrait_ambiguous" if matches else
                           "portable_portrait_unavailable", len(matches))
        match = matches[0]
        point = match["x_roi_norm"], match["y_roi_norm"]
        previous = self._previous
        if previous is not None:
            dt = time_sec-previous[0]
            if not 0 < dt <= .3:
                self.reset()
                previous = None
            elif math.dist(point, previous[1])/dt > .4:
                return unknown("position_jump", 1)
        streak = previous[2]+1 if previous else 1
        if previous is None:
            self._next_id += 1
        self._previous = time_sec, point, streak
        return MarkerPosition("tracked" if streak >= 3 else "candidate",
                              "portable_portrait_appearance_only", 1, point[0], point[1],
                              match["portrait_similarity"], self._next_id-1)

    def _shared_gray_scores(
        self, target: NDArray[Any], templates: list[NDArray[Any]],
    ) -> NDArray[Any]:
        """Binary-mask NCC with shared current-image statistics, bounded memory.

        This is a separate opt-in feature implementation. It never reuses a
        frame response or previous transform; floating-point parity must be
        measured before switching an existing experiment to this mode.
        """
        assert self._mask is not None
        mask = (self._mask != 0).astype(np.float32)
        count = float(mask.sum())
        image = target.astype(np.float32)
        sums = cv2.matchTemplate(image, mask, cv2.TM_CCORR)
        squares = cv2.matchTemplate(image*image, mask, cv2.TM_CCORR)
        variance = np.maximum(squares-sums*sums/count, 0)
        result = np.full(sums.shape, -1, np.float32)
        for template in templates:
            values = template.astype(np.float32)
            centered = (values-float((values*mask).sum())/count)*mask
            energy = float((centered*centered).sum())
            denominator = np.sqrt(variance*energy)
            numerator = cv2.matchTemplate(image, centered, cv2.TM_CCORR)
            response = np.full(sums.shape, -1, np.float32)
            np.divide(numerator, denominator, out=response, where=denominator > 1e-6)
            np.maximum(result, response, out=result)
        return result
