"""Opt-in partial-arc candidate research; no player identity or production output.

The independent generator supplies additional unassigned hypotheses. It never
filters, merges, moves, or ranks the parent D candidates and is not a marker
classifier. Coordinates and source details are private caller evidence.
"""
from __future__ import annotations

import copy
import hashlib
import math
from typing import Any

import cv2
import numpy as np

from valorant_ai_coach.video.geometry import normalized_roi_bounds

from .development_marker_attribution import freeze_native_sample
from .development_marker_cross import CrossMarkerDetector
from .development_marker_detection import Image, _key

RADII = (6, 8, 10, 12, 14)
SECTORS = 12
MIN_SECTORS = 7
MIN_PROJECTION = 48.0
MIN_RADIAL_COHERENCE = .55
NMS_DISTANCE = 5.0
MAX_PEAKS = 4096
MAX_ADDITIONS = 64
METHOD = 'partial_radial_arc_v1'


def _shift(array: Image, dx: int, dy: int) -> Image:
    """Sample array[y+dy,x+dx] and never wrap image boundaries."""
    h, w = array.shape
    shifted = np.zeros_like(array)
    x0, x1 = max(0, -dx), min(w, w-dx)
    y0, y1 = max(0, -dy), min(h, h-dy)
    if x0 < x1 and y0 < y1:
        shifted[y0:y1, x0:x1] = array[y0+dy:y1+dy, x0+dx:x1+dx]
    return shifted


def partial_arc_observations(crop: Image) -> dict[str, Any]:
    """Search all valid ROI centers with fixed radial support and budgets.

    Each sampled sector is supported only when its Sobel gradient has a strong
    radial projection and sufficient radial coherence. The score is a count,
    not a calibrated confidence. Missing sectors permit partial arcs; the full
    support disk must be observed inside the ROI. Thresholds are deliberately
    fixed research settings, not fitted to any labelled example.
    """
    if (not isinstance(crop, np.ndarray) or crop.dtype != np.uint8 or crop.ndim != 3
            or crop.shape[2] != 3 or min(crop.shape[:2]) < 65
            or max(crop.shape[:2]) > 1024):
        raise ValueError('Bounded native uint8 BGR minimap ROI required')
    gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
    smooth = cv2.GaussianBlur(gray, (3, 3), .8)
    gx = cv2.Sobel(smooth, cv2.CV_32F, 1, 0, ksize=3)
    gy = cv2.Sobel(smooth, cv2.CV_32F, 0, 1, ksize=3)
    height, width = gray.shape
    best = np.zeros((height, width), np.uint8)
    best_radius = np.zeros((height, width), np.uint8)
    for radius in RADII:
        support = np.zeros((height, width), np.uint8)
        for angle in range(SECTORS):
            theta = 2*math.pi*angle/SECTORS
            ux, uy = math.cos(theta), math.sin(theta)
            dx, dy = round(radius*ux), round(radius*uy)
            sx, sy = _shift(gx, dx, dy), _shift(gy, dx, dy)
            projection = np.abs(sx*ux+sy*uy)
            energy = np.sqrt(sx*sx+sy*sy)
            support += ((projection >= MIN_PROJECTION)
                        & (projection >= MIN_RADIAL_COHERENCE*energy)).astype(np.uint8)
        margin = radius+1
        support[:margin] = 0
        support[-margin:] = 0
        support[:, :margin] = 0
        support[:, -margin:] = 0
        improved = support > best
        best[improved] = support[improved]
        best_radius[improved] = radius
    # 3x3 maxima generate seeds; explicit deterministic 5px NMS follows.
    maxima = cv2.dilate(best, np.ones((3, 3), np.uint8))
    ys, xs = np.nonzero((best >= MIN_SECTORS) & (best == maxima))
    scores = best[ys, xs]
    order = np.lexsort((xs, ys, -scores.astype(np.int16)))
    total_peaks = int(len(order))
    candidates: list[dict[str, Any]] = []
    selected: list[tuple[int, int]] = []
    overflow = 0
    for index in order[:MAX_PEAKS]:
        x, y = int(xs[index]), int(ys[index])
        if any((x-xx)**2+(y-yy)**2 <= NMS_DISTANCE**2 for xx, yy in selected):
            continue
        if len(selected) >= MAX_ADDITIONS:
            overflow += 1
            continue
        selected.append((x, y))
        radius = int(best_radius[y, x])
        candidates.append({
            'kind': 'partial_radial_arc', 'center_roi_px': [x, y],
            'size_roi_px': [2*radius+1, 2*radius+1], 'radius_px': radius,
            'supported_sectors': int(best[y, x]), 'sector_count': SECTORS,
            'raw_score': int(best[y, x])/SECTORS, 'score_calibrated': False,
            'candidate_kind': 'unassigned_partial_arc', 'physical_equivalence': 'UNKNOWN',
            'ownership': 'UNKNOWN', 'qualification': 'development_only',
        })
    return {'method': METHOD, 'candidates': candidates, 'candidate_peaks_total': total_peaks,
            'processed_peaks': min(total_peaks, MAX_PEAKS), 'output_overflow': overflow,
            'unprocessed_peaks': max(0, total_peaks-MAX_PEAKS),
            'search_truncated': total_peaks > MAX_PEAKS or bool(overflow),
            'semantic_class': 'UNKNOWN', 'ownership': 'UNKNOWN',
            'qualification': 'development_only'}


class DevelopmentPartialArcDetector:
    """Run native-bound D and add an independently bounded set of arc proposals."""

    def __init__(self, cross_appearance_profile: dict[str, Any]) -> None:
        self.parent = CrossMarkerDetector(cross_appearance_profile)

    def observe(self, frame: Image, *, sample: dict[str, Any],
                minimap_roi: list[float], appearance_pool: dict[str, Any]) -> dict[str, Any]:
        if (not isinstance(frame, np.ndarray) or frame.dtype != np.uint8
                or frame.ndim != 3 or frame.shape[2] != 3):
            raise ValueError('Native uint8 BGR frame required')
        bound = freeze_native_sample(sample, frame_size_px=(frame.shape[1], frame.shape[0]))
        digest = hashlib.sha256(frame.tobytes()).hexdigest()
        if sample != bound or digest != bound['native_pixel_sha256']:
            raise ValueError('Exact native sample and decoded pixels required')
        bounds = normalized_roi_bounds(minimap_roi, frame.shape[1], frame.shape[0])
        if bounds is None:
            raise ValueError('Explicit minimap ROI required')
        left, top, right, bottom = bounds
        crop = frame[top:bottom, left:right]
        d = self.parent.detect(crop, appearance_pool)
        d_before = copy.deepcopy(d)
        arc = partial_arc_observations(crop)
        self.parent.verify(appearance_pool['libraries'], d['reference_fingerprint'])
        if (hashlib.sha256(frame.tobytes()).hexdigest() != digest
                or hashlib.sha256(crop.tobytes()).hexdigest() != d['roi_pixel_sha256']
                or d != d_before):
            raise ValueError('Frame or parent proposal changed during arc search')
        parent = copy.deepcopy(d['candidates'])
        proposals: list[dict[str, Any]] = [
            {'source': 'D', 'parent_index': i, 'candidate': copy.deepcopy(p),
             'center_frame_px': [left+p['center_roi_px'][0], top+p['center_roi_px'][1]],
             'sample_sha256': bound['sample_sha256'], 'ownership': 'UNKNOWN',
             'qualification': 'development_only'} for i, p in enumerate(parent)]
        for i, p in enumerate(arc['candidates']):
            links = [j for j, q in enumerate(parent)
                     if math.dist(p['center_roi_px'], q['center_roi_px']) <= NMS_DISTANCE]
            proposals.append({'source': 'partial_arc', 'arc_index': i,
                              'candidate': copy.deepcopy(p),
                              'center_frame_px': [left+p['center_roi_px'][0],
                                                  top+p['center_roi_px'][1]],
                              'sample_sha256': bound['sample_sha256'],
                              'nearby_d_indices': links, 'physical_equivalence': 'UNKNOWN',
                              'ownership': 'UNKNOWN', 'qualification': 'development_only'})
        return {'sample': bound, 'roi_frame_px': list(bounds), 'baseline_d': d_before,
                'proposals': proposals, 'arc_search': arc,
                'method_fingerprint': _key({'method': METHOD, 'radii': RADII,
                    'sectors': SECTORS, 'minimum_sectors': MIN_SECTORS,
                    'minimum_projection': MIN_PROJECTION, 'coherence': MIN_RADIAL_COHERENCE,
                    'nms_distance': NMS_DISTANCE, 'max_peaks': MAX_PEAKS,
                    'max_additions': MAX_ADDITIONS, 'parent': d['reference_fingerprint']}),
                'semantic_class': 'UNKNOWN', 'ownership': 'UNKNOWN',
                'qualification': 'development_only', 'selected_self_position': None,
                'formal_self_position_fact': None, 'development_events': [], 'track_segments': []}
