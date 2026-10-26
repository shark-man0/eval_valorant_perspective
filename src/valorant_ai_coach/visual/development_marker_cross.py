"""Opt-in chromatic cross-shape observations; never death or player identity.

A private, explicitly supplied appearance profile selects chromatic pixels. Four
opposing diagonal arms and empty axial controls supply independent shape support.
The profile and every observation remain unqualified development evidence.
"""

from __future__ import annotations

import hashlib
import math
from dataclasses import asdict, dataclass
from typing import Any

import cv2
import numpy as np

from .development_marker_detection import Image, _iou, _key
from .development_marker_exhaustive import (
    DevelopmentExhaustiveMarkerProposals,
    ExhaustiveMarkerDetector,
)


@dataclass(frozen=True)
class CrossAppearanceProfile:
    hue_center: int
    hue_tolerance: int
    saturation_min: int
    value_min: int

    def __post_init__(self) -> None:
        if (any(type(v) is not int for v in asdict(self).values())
                or not 0 <= self.hue_center < 180 or not 1 <= self.hue_tolerance <= 30
                or not 1 <= self.saturation_min <= 255 or not 1 <= self.value_min <= 255):
            raise ValueError('Invalid bounded cross appearance parameters')

    @classmethod
    def parse(cls, value: dict[str, Any]) -> CrossAppearanceProfile:
        keys = {'mode', 'hue_center', 'hue_tolerance', 'saturation_min', 'value_min'}
        if (not isinstance(value, dict) or set(value) != keys
                or value['mode'] != 'unassigned_cross_shape_v1'
                or any(type(value[k]) is not int for k in keys-{'mode'})
                or not 0 <= value['hue_center'] < 180
                or not 1 <= value['hue_tolerance'] <= 30
                or not 1 <= value['saturation_min'] <= 255
                or not 1 <= value['value_min'] <= 255):
            raise ValueError('Explicit bounded development cross appearance profile required')
        return cls(*(value[k] for k in (
            'hue_center', 'hue_tolerance', 'saturation_min', 'value_min')))

    @property
    def fingerprint(self) -> str:
        return _key({'mode': 'unassigned_cross_shape_v1', **asdict(self)})


def _shape_options(labels: Image, index: int, box: list[int]) -> list[dict[str, Any]]:
    x, y, width, height = box
    # Sampling extends at most 9px from the component box center. Ten pixels
    # around its box preserve full-image border replication, using <=45x45
    # float pixels instead of another full-ROI image for every component.
    x0, y0 = max(0, x-10), max(0, y-10)
    tile = (labels[y0:min(labels.shape[0], y+height+10),
                   x0:min(labels.shape[1], x+width+10)] == index).astype(np.float32)
    bx, by = x+(width-1)/2, y+(height-1)/2
    steps = np.linspace(2, min(min(width, height)/2-1, 7), 5)
    options = []
    for ox in (-1., -.5, 0., .5, 1.):
        for oy in (-1., -.5, 0., .5, 1.):
            cx, cy = bx+ox, by+oy
            arms: list[float] = []
            axes: list[float] = []
            for directions, target in (
                (((-1, -1), (-1, 1), (1, -1), (1, 1)), arms),
                (((-1, 0), (1, 0), (0, -1), (0, 1)), axes),
            ):
                for dx, dy in directions:
                    target.append(float(np.mean([
                        cv2.getRectSubPix(tile, (3, 3),
                                          (cx-x0+dx*k, cy-y0+dy*k)).mean() for k in steps])))
            options.append({
                'center_roi_px': [cx, cy], 'arms': arms, 'axes': axes,
                'minimum_arm_support': min(arms),
                'diagonal_axis_contrast': float(np.mean(arms)-np.mean(axes)),
                'bbox_center_distance': math.hypot(ox, oy),
            })
    return options


def cross_observations(crop: Image, profile: CrossAppearanceProfile) -> dict[str, Any]:
    """Bounded current-image components, without semantic/physical merging."""
    if (not isinstance(crop, np.ndarray) or crop.dtype != np.uint8 or crop.ndim != 3
            or crop.shape[2] != 3 or min(crop.shape[:2]) < 65
            or max(crop.shape[:2]) > 1024):
        raise ValueError('Bounded uint8 BGR minimap ROI required')
    hsv = cv2.cvtColor(crop, cv2.COLOR_BGR2HSV)
    delta = np.abs(hsv[:, :, 0].astype(np.int16)-profile.hue_center)
    mask = ((np.minimum(delta, 180-delta) <= profile.hue_tolerance)
            & (hsv[:, :, 1] >= profile.saturation_min)
            & (hsv[:, :, 2] >= profile.value_min)).astype(np.uint8)
    del hsv, delta
    count, labels, stats, _ = cv2.connectedComponentsWithStats(mask, connectivity=8)
    del mask
    boxes = stats[1:]
    width, height, area = boxes[:, 2], boxes[:, 3], boxes[:, 4]
    bounded = (np.minimum(width, height) >= 7) & (np.maximum(width, height) <= 25)
    sized = (area >= 15) & (area <= 180)
    aspect = (width >= .6*height) & (width <= 1.7*height)
    eligible = np.flatnonzero(bounded & sized & aspect)+1
    rejected = {'component_bbox': int((~bounded).sum()),
                'component_area': int((bounded & ~sized).sum()),
                'component_aspect': int((bounded & sized & ~aspect).sum()),
                'shape_support': 0}
    accepted = []
    for index in eligible[:128]:
        x, y, width, height, area = map(int, stats[index])
        options = _shape_options(labels, int(index), [x, y, width, height])
        best = max(options, key=lambda p: (
            p['minimum_arm_support'], p['diagonal_axis_contrast'], -p['bbox_center_distance']))
        if best['minimum_arm_support'] < .25 or best['diagonal_axis_contrast'] < .15:
            rejected['shape_support'] += 1
            continue
        accepted.append({**best, 'component_index': int(index),
                         'component_bbox_px': [x, y, width, height], 'area': area,
                         'center_hypotheses': options, 'physical_marker_count': None,
                         'physical_equivalence': 'UNKNOWN', 'kind': 'chromatic_cross_shape',
                         'size_roi_px': [width, height],
                         'x_roi_norm': best['center_roi_px'][0]/crop.shape[1],
                         'y_roi_norm': best['center_roi_px'][1]/crop.shape[0],
                         'candidate_kind': 'unassigned_cross_appearance',
                         'qualification': 'development_only', 'ownership': 'UNKNOWN'})
    return {'components': count-1, 'eligible_components': len(eligible),
            'checked_components': min(len(eligible), 128),
            'unprocessed_eligible_components': max(0, len(eligible)-128),
            'truncated': len(eligible) > 128, 'rejected': rejected, 'observations': accepted,
            'profile_fingerprint': profile.fingerprint, 'qualification': 'development_only',
            'ownership': 'UNKNOWN', 'semantic_marker_class': 'UNKNOWN'}


def _append_observations(result: dict[str, Any], search: dict[str, Any]) -> None:
    """Nearby windows remain separate proposals with UNKNOWN associations."""
    candidates = result['candidates']
    links, overflow = [], 0
    for index, point in enumerate(search['observations']):
        nearby = [j for j, p in enumerate(candidates) if math.dist(
            p['center_roi_px'], point['center_roi_px']) <= 5 and _iou(p, point) >= .45]
        if nearby:
            links.append({'cross_observation_index': index, 'previous_proposal_indices': nearby,
                          'relation': 'UNKNOWN', 'evidence': 'nearby_overlapping_windows'})
        if len(candidates) >= 128:
            overflow += 1
        else:
            candidates.append(point)
    # Even output-budget overflow observations remain in the search evidence.
    result['cross_search'] = search
    result['cross_associations'] = links
    result['cross_output_overflow'] = overflow
    result['output_count'] = len(candidates)
    result['search_truncated'] |= search['truncated'] or bool(overflow)


class CrossMarkerDetector(ExhaustiveMarkerDetector):
    """Additional shape evidence with unchanged parent proposal centers.

    Cross appearance does not identify a dead player, owner, camera state or
    game event. A connected component also need not be one physical marker.
    """

    def __init__(self, appearance_profile: dict[str, Any]) -> None:
        self.cross_profile = CrossAppearanceProfile.parse(appearance_profile)
        super().__init__()

    def _model_key(self, libraries: list[dict[str, Any]], refs: list[str]) -> str:
        return _key({'base': super()._model_key(libraries, refs),
                     'cross_profile': self.cross_profile.fingerprint,
                     'shape': ['four_diagonal_arms_vs_axes_v1', 7, 25, 15, 180, .6, 1.7,
                               .25, .15, 128, 128, 5, .45]})

    def detect(self, crop: Image, appearance_pool: dict[str, Any]) -> dict[str, Any]:
        try:
            result = super().detect(crop, appearance_pool)
            search = cross_observations(crop, self.cross_profile)
            _append_observations(result, search)
            self.verify(appearance_pool['libraries'], result['reference_fingerprint'])
            if hashlib.sha256(crop.tobytes()).hexdigest() != result['roi_pixel_sha256']:
                raise ValueError('ROI changed during cross observation')
            result['method'] = 'exhaustive_ncc_with_unassigned_cross_observations_v1'
            self.execution_evidence = {**self.execution_evidence,
                                       'cross_profile_fingerprint': self.cross_profile.fingerprint}
            self.last_evidence = {k: v for k, v in result.items() if k != 'candidates'}
            return result
        except (ValueError, TypeError, cv2.error):
            self._fingerprint = None
            self.last_evidence = {'reason': 'cross_observation_failed',
                                  'qualification': 'development_only', 'ownership': 'UNKNOWN'}
            self.execution_evidence = {}
            raise


class DevelopmentCrossMarkerProposals(DevelopmentExhaustiveMarkerProposals):
    """Inherited native binding, current-frame geometry, floor and build gates."""

    def __init__(self, map_id: str, appearance_profile: dict[str, Any]) -> None:
        super().__init__(map_id)
        self.detector = CrossMarkerDetector(appearance_profile)
