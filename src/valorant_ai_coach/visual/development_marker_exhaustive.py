"""Opt-in exhaustive integer NCC and lossless observation alternatives.

This is a separate development algorithm, not a bit-identical optimization of
OpenCV's masked NCC. No approximate rejection screen is used. Unsupported inputs
or arithmetic environments fall back to the original full masked NCC search.
Neither a reference match nor a duplicate association establishes player identity.
"""

from __future__ import annotations

import hashlib
import math
from collections.abc import Callable
from typing import Any

import cv2
import numpy as np

from .development_marker_detection import BoundedMarkerDetector, Image, _iou, _key
from .development_marker_quality import DevelopmentQualityMarkerProposals, QualityMarkerDetector
from .self_marker import MarkerReferenceInspector, SelfMarkerTracker


class _UnsupportedArithmetic(ValueError):
    pass


def _runtime_contract() -> bool:
    """Check the IEEE/GEMM prerequisite; this does not certify OpenCV parity."""
    if np.finfo(np.float32).nmant != 23 or np.finfo(np.float64).nmant != 52:
        return False
    rng = np.random.default_rng(961)
    for width in (9, 17, 65):
        a = rng.integers(0, 256, (33, width*3), np.uint8)
        b = rng.integers(0, 256, (width*3, 12), np.uint8)
        a[0], a[1], b[:, 0], b[:, 1] = 255, 0, 255, 0
        if not np.array_equal(a.astype(np.float32) @ b.astype(np.float32),
                              a.astype(np.int64) @ b.astype(np.int64)):
            return False
    return True


def _validate(image: Image, templates: list[Image], mask: Image) -> None:
    h, w = mask.shape
    if (image.dtype != np.uint8 or image.ndim != 3 or image.shape[2] != 3
            or max(image.shape[:2]) > 1024 or min(image.shape[:2]) < max(h, w)
            or not 9 <= h <= 65 or h != w or h % 2 != 1
            or mask.dtype != np.uint8 or not np.isin(mask, [0, 1]).all()
            or not mask.any() or not 1 <= len(templates) <= 12
            or any(t.shape != (h, w, 3) or t.dtype != np.uint8 for t in templates)):
        raise _UnsupportedArithmetic("Unsupported bounded integer NCC input")
    for row in mask:
        columns = np.flatnonzero(row)
        if len(columns) and not row[columns[0]:columns[-1]+1].all():
            raise _UnsupportedArithmetic("Mask rows must be contiguous binary runs")


def _moments(image: Image, mask: Image) -> tuple[Image, Image, int]:
    h, w = mask.shape
    oh, ow = image.shape[0]-h+1, image.shape[1]-w+1
    integral = cv2.integral(image, sdepth=cv2.CV_32S)
    energy_image = np.einsum('ijk,ijk->ij', image, image, dtype=np.int32)
    integral2 = cv2.integral(energy_image.astype(np.float64))
    del energy_image
    total = np.zeros((oh, ow, 3), np.int32)
    squared = np.zeros((oh, ow), np.int32)
    for y, row in enumerate(mask):
        columns = np.flatnonzero(row)
        if not len(columns):
            continue
        a, b = int(columns[0]), int(columns[-1])+1
        total += (integral[y+1:y+1+oh, b:b+ow]-integral[y:y+oh, b:b+ow]
                  - integral[y+1:y+1+oh, a:a+ow]+integral[y:y+oh, a:a+ow])
        squared += (integral2[y+1:y+1+oh, b:b+ow]-integral2[y:y+oh, b:b+ow]
                    - integral2[y+1:y+1+oh, a:a+ow]
                    + integral2[y:y+oh, a:a+ow]).astype(np.int32)
    n = int(mask.sum())
    energy = n*squared.astype(np.float64)-np.einsum(
        'ijk,ijk->ij', total, total, dtype=np.float64)
    if float(energy.min()) < 0:
        raise _UnsupportedArithmetic("Invalid integer moments")
    return total, energy, n


def _score_rows(
    image: Image, templates: list[Image], mask: Image,
    moments: tuple[Image, Image, int] | None = None,
) -> list[Image]:
    """Evaluate every valid window; at most twelve maps and 64 output rows/tile.

    Each row dot is a sum of at most 195 nonnegative integer products. Its
    maximum is 195*255**2 < 2**24, so IEEE binary32 additions/products are exact
    regardless of reduction order. Integer row accumulation is < 2**31. The
    bounded integral images and normalization numerators are exact integers
    below 2**53. Square root/division are floating point, unlike those sums.
    """
    _validate(image, templates, mask)
    total, energy, n = _moments(image, mask) if moments is None else moments
    h, w = mask.shape
    oh, ow = image.shape[0]-h+1, image.shape[1]-w+1
    count = len(templates)
    kernels = (np.stack(templates)*mask[None, :, :, None]).astype(np.float32)
    dots = np.zeros((oh, ow, count), np.int32)
    source = image.astype(np.float32)
    for y, row in enumerate(mask):
        if not row.any():
            continue
        kernel = np.ascontiguousarray(kernels[:, y].reshape(count, -1).T)
        for top in range(0, oh, 64):
            rows = min(64, oh-top)
            view = np.lib.stride_tricks.sliding_window_view(
                source[top+y:top+y+rows], w, axis=1)
            patches = np.ascontiguousarray(view.transpose(0, 1, 3, 2)).reshape(-1, w*3)
            partial = patches @ kernel
            dots[top:top+rows] += partial.reshape(rows, ow, count).astype(np.int32)
    # Reuse the integer buffer for scores, after reading each corresponding dot
    # plane. A list of views retains one buffer, not twelve additional copies.
    result = dots.view(np.float32)
    for i, ref in enumerate(templates):
        masked = ref*mask[:, :, None]
        sums = masked.sum(axis=(0, 1), dtype=np.float64)
        te = n*(masked.astype(np.float64)**2).sum()-(sums*sums).sum()
        value = dots[:, :, i].astype(np.float64)
        value *= n
        value -= np.einsum('ijk,k->ij', total, sums, dtype=np.float64)
        denominator = energy*te
        np.sqrt(denominator, out=denominator)
        valid = denominator > 0
        np.divide(value, denominator, out=value, where=valid)
        value[~valid] = -1
        np.clip(value, -1, 1, out=value)
        result[:, :, i] = value
    return [result[:, :, i] for i in range(count)]


class _FrameCorrelations:
    def __init__(self) -> None:
        self.valid = _runtime_contract()
        self.signature: tuple[Any, ...] | None = None
        self.plan: dict[Any, Any] = {}
        self.clear()
        self.fallbacks = 0

    def clear(self) -> None:
        self.image: Image | None = None
        self.maps: dict[Any, Image] = {}
        self.moments: dict[Any, tuple[Image, Image, int]] = {}

    @staticmethod
    def key(ref: Image, mask: Image) -> tuple[Any, ...]:
        return ref.shape, hashlib.sha256(ref.tobytes()).digest(), mask.tobytes()

    def configure(self, inspectors: list[MarkerReferenceInspector]) -> None:
        entries = []
        for inspector in inspectors:
            loader = inspector._loader
            for ref in loader._references+loader._negatives:
                mask = (np.ones(ref.shape[:2], np.uint8) if loader._mask is None
                        else (loader._mask > 0).astype(np.uint8))
                entries.append((self.key(ref, mask), ref, mask))
        signature = tuple(key for key, _, _ in entries)
        if signature == self.signature:
            return
        self.signature = signature
        groups: dict[Any, Any] = {}
        for key, ref, mask in entries:
            groups.setdefault((mask.shape, mask.tobytes()), {}).setdefault(key, (ref, mask))
        self.plan = {}
        for group in groups.values():
            pairs = list(group.items())
            for start in range(0, len(pairs), 12):
                chunk = pairs[start:start+12]
                for key, _ in chunk:
                    self.plan[key] = chunk
        self.clear()

    def get(
        self, image: Image, ref: Image, mask: Image | None,
        original: Callable[[Image, Image], Image],
    ) -> Image:
        mask = (np.ones(ref.shape[:2], np.uint8) if mask is None
                else (mask > 0).astype(np.uint8))
        key = self.key(ref, mask)
        if not self.valid or key not in self.plan:
            self.fallbacks += 1
            return original(image, ref)
        if self.image is not image:
            self.clear()
            self.image = image
        if key not in self.maps:
            chunk = self.plan[key]
            templates = [pair[0] for _, pair in chunk]
            try:
                _validate(image, templates, mask)
                mk = mask.shape, mask.tobytes()
                if mk not in self.moments:
                    self.moments[mk] = _moments(image, mask)
                maps = _score_rows(image, templates, mask, self.moments[mk])
            except (ValueError, FloatingPointError, cv2.error):
                self.fallbacks += 1
                return original(image, ref)
            # Keep one chunk of correlation maps; moments are scale-local.
            self.maps = {k: score for (k, _), score in zip(chunk, maps, strict=True)}
        return self.maps[key]


class _IntegerTracker(SelfMarkerTracker):
    def __init__(self, shared: _FrameCorrelations) -> None:
        super().__init__()
        self.shared = shared

    def _scores(self, image: Image, template: Image) -> Image:
        return self.shared.get(image, template, self._mask, super()._scores)


class _IntegerInspector(MarkerReferenceInspector):
    def __init__(self, shared: _FrameCorrelations) -> None:
        super().__init__()
        self._loader = _IntegerTracker(shared)


def observation_alternatives(result: dict[str, Any]) -> dict[str, Any]:
    """Retain suppressed measurements without claiming physical equivalence.

    Canonical proposals remain a display/geometry selection. Their nearby raw
    observations are not silently counted as proven duplicates or new players.
    Identical references/scales/windows are measurement identity only. No
    transitive clustering, center averaging, death/portrait or ownership labels.
    """
    observations = list(result['ncc_observations'])
    for search in ('circle_search', 'alt_search'):
        for p in result[search]['observations']:
            if p['support']['passed']:
                observations.append({**p, 'kind': search, 'size_roi_px': [2*p['radius_px']+1]*2})
    links = []
    unlinked = []
    for i, p in enumerate(observations):
        targets = []
        for j, c in enumerate(result['candidates']):
            if (math.dist(p['center_roi_px'], c['center_roi_px']) <= 5
                    and _iou(p, c) >= .45):
                targets.append(j)
        if targets:
            links.append({'observation_index': i, 'canonical_indices': targets,
                          'relation': 'UNKNOWN', 'evidence': 'nearby_overlapping_windows'})
        else:
            unlinked.append(i)
    return {'observations': observations, 'links': links, 'unlinked_indices': unlinked,
            'physical_marker_count': None, 'physical_equivalence': 'UNKNOWN',
            'canonical_semantics': 'display_selection_not_physical_deduplication',
            'qualification': 'development_only', 'ownership': 'UNKNOWN'}


class ExhaustiveMarkerDetector(QualityMarkerDetector):
    """Separate exhaustive NCC method, preserving unresolved center hypotheses."""

    def __init__(self) -> None:
        super().__init__()
        self.correlations = _FrameCorrelations()
        self.inspectors = [_IntegerInspector(self.correlations) for _ in range(4)]

    def _references(self, libraries: list[dict[str, Any]]) -> list[str]:
        refs = super()._references(libraries)
        self.correlations.configure(self.inspectors[:len(libraries)])
        return refs

    def _model_key(self, libraries: list[dict[str, Any]], refs: list[str]) -> str:
        return _key({'base': super()._model_key(libraries, refs),
                     'ncc': 'exhaustive_integer_rows_v1', 'tile_rows': 64,
                     'reference_batch': 12, 'observation_links': [5, .45, 'UNKNOWN']})

    def detect(self, crop: Image, appearance_pool: dict[str, Any]) -> dict[str, Any]:
        self.correlations.clear()
        self.correlations.fallbacks = 0
        self.execution_evidence = {}
        try:
            # Deliberately bypass ScreenedMarkerDetector.detect and its heuristic.
            result = BoundedMarkerDetector.detect(self, crop, appearance_pool)
            result = self._refine(crop, appearance_pool, result)
            result['observation_alternatives'] = observation_alternatives(result)
            result['method'] = 'exhaustive_integer_ncc_with_unresolved_observations_v1'
            self.execution_evidence = {
                'backend': 'exhaustive_integer_rows_v1',
                'runtime_contract': self.correlations.valid,
                'full_opencv_fallback_calls': self.correlations.fallbacks,
                'approximate_screen_enabled': False,
                'opencv': cv2.__version__, 'numpy': np.__version__,
                'qualification': 'development_only', 'numerical_backend_qualified': False,
            }
            self.last_evidence = {k: v for k, v in result.items() if k != 'candidates'}
            return result
        except (ValueError, TypeError, cv2.error):
            self._fingerprint = None
            self.last_evidence = {'reason': 'exhaustive_observation_failed',
                                  'ownership': 'UNKNOWN', 'qualification': 'development_only'}
            self.execution_evidence = {}
            raise
        finally:
            self.correlations.clear()


class DevelopmentExhaustiveMarkerProposals(DevelopmentQualityMarkerProposals):
    """Opt-in; inherited native sample, geometry, floor and version gates apply."""

    def __init__(self, map_id: str) -> None:
        super().__init__(map_id)
        self.detector = ExhaustiveMarkerDetector()
