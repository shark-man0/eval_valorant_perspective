"""Explicit offline purchase-text structure witness; never phase absence or GT."""
from __future__ import annotations

import hashlib
import re
from typing import Any

import cv2
import numpy as np
from numpy.typing import NDArray

from scripts.diagnostics.geometry_edge_similarity import features
from scripts.diagnostics.hud_scope_structure import FRAME_KEYS
from scripts.temporal_gt.contract import canonical_hash
from valorant_ai_coach.hud.semantic_text import SemanticTextReference

ImageU8 = NDArray[np.uint8]
METHOD = 'offline_purchase_all_groups_edge_v1'


class PhaseStructureReference:
    """Reuse source-supported semantic groups at their fixed pixel position.

    A symmetric one-pixel edge neighbourhood accommodates rasterization. Every
    group must retain both observed precision and reference coverage >= .90,
    positive glyph polarity, and at least 32 edges. Missing groups, extra local
    edges, inversion and crop/scale changes remain UNKNOWN. No search, generated
    glyphs, text extrapolation, phase-disappearance or production hook is used.
    """

    def __init__(self, semantic: SemanticTextReference) -> None:
        self.reference = semantic.reference.copy()
        self.masks = tuple(m.copy() for m in semantic.masks)
        self.threshold = semantic.threshold
        self.binding = canonical_hash({
            'reference': hashlib.sha256(self.reference.tobytes()).hexdigest(),
            'masks': [hashlib.sha256(m.tobytes()).hexdigest() for m in self.masks],
            'threshold': self.threshold, 'method': METHOD,
            'shape': list(self.reference.shape),
        })
        self.parts = []
        kernel = np.ones((3, 3), np.uint8)
        for mask in self.masks:
            edge = features(self.reference, mask)[0]
            foreground = (self.reference >= 210) & (mask > 0)
            background = (self.reference < 180) & (mask > 0)
            if min(int(edge.sum()), int(foreground.sum()), int(background.sum())) < 32:
                raise ValueError('source-supported glyph edges and negative space required')
            self.parts.append((edge, cv2.dilate(edge.astype(np.uint8), kernel) > 0,
                               foreground, background))

    def measure(self, image: ImageU8) -> dict[str, Any]:
        result: dict[str, Any] = {
            'method': METHOD, 'reference_sha256': self.binding,
            'threshold': self.threshold, 'presence': None, 'groups': [],
            'reference_size': [self.reference.shape[1], self.reference.shape[0]],
            'absence_checked': False, 'production_qualified': False, 'formal_events': [],
        }
        if (image.dtype != np.uint8 or image.ndim not in (2, 3)
                or image.ndim == 3 and image.shape[2] != 3):
            return {**result, 'reason': 'invalid_pixels'}
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY) if image.ndim == 3 else image
        if gray.shape != self.reference.shape:
            return {**result, 'reason': 'shape_mismatch'}
        kernel = np.ones((3, 3), np.uint8)
        for mask, (edge, dilated, foreground, background) in zip(
                self.masks, self.parts, strict=True):
            observed = features(gray, mask)[0]
            expanded = cv2.dilate(observed.astype(np.uint8), kernel) > 0
            coverage = float(expanded[edge].mean())
            precision = float(dilated[observed].mean()) if observed.any() else 0.0
            polarity = float(gray[foreground].mean()) > float(gray[background].mean())
            result['groups'].append({
                'reference_edges': int(edge.sum()), 'observed_edges': int(observed.sum()),
                'coverage': coverage, 'precision': precision, 'positive_polarity': polarity,
                'supported': bool(observed.sum() >= 32 and polarity
                                  and min(coverage, precision) >= self.threshold),
            })
        supported = all(g['supported'] for g in result['groups'])
        return {**result, 'presence': True if supported else None,
                'reason': 'all_glyph_groups_supported' if supported else 'glyph_group_missing'}


def bind_phase(frame: dict[str, Any], image: ImageU8, bounds: list[int],
               reference: PhaseStructureReference, profile_sha256: str) -> dict[str, Any]:
    """Bind a fixed private Profile crop to actual observed source pixels."""
    if (image.dtype != np.uint8 or image.ndim != 3 or image.shape[2] != 3
            or hashlib.sha256(image.tobytes()).hexdigest() != frame['pixel_sha256']
            or not isinstance(profile_sha256, str)
            or re.fullmatch(r'[0-9a-f]{64}', profile_sha256) is None
            or len(bounds) != 4 or any(type(v) is not int for v in bounds)):
        raise ValueError('bound BGR source frame and integer crop required')
    x, y, xx, yy = bounds
    if not (0 <= x < xx <= image.shape[1] and 0 <= y < yy <= image.shape[0]):
        raise ValueError('phase crop outside source')
    crop = image[y:yy, x:xx]
    record = {**reference.measure(crop), 'frame': {k: frame[k] for k in FRAME_KEYS},
              'profile_sha256': profile_sha256, 'pixel_bounds': bounds.copy(),
              'image_size': [image.shape[1], image.shape[0]],
              'crop_pixel_sha256': hashlib.sha256(crop.tobytes()).hexdigest()}
    return {**record, 'evidence_sha256': canonical_hash(record)}


def phase_supported(frame: dict[str, Any]) -> bool:
    """Accept only an explicit frame-bound receipt, without inferring absence."""
    value = frame.get('phase_structure')
    if value is None:
        return False
    if (not isinstance(value, dict) or value.get('method') != METHOD
            or value.get('frame') != {k: frame[k] for k in FRAME_KEYS}
            or value.get('evidence_sha256') != canonical_hash(
                {k: v for k, v in value.items() if k != 'evidence_sha256'})
            or value.get('absence_checked') is not False
            or value.get('production_qualified') is not False or value.get('formal_events') != []
            or type(value.get('threshold')) not in (int, float)
            or not .90 <= value['threshold'] <= 1
            or not isinstance(value.get('groups'), list)
            or any(not isinstance(g, dict) for g in value['groups'])):
        raise ValueError('invalid offline purchase structure receipt')
    size, bounds = value.get('image_size'), value.get('pixel_bounds')
    if (not isinstance(size, list) or len(size) != 2
            or any(type(v) is not int or v <= 0 for v in size)
            or not isinstance(bounds, list) or len(bounds) != 4
            or any(type(v) is not int for v in bounds)
            or not (0 <= bounds[0] < bounds[2] <= size[0]
                    and 0 <= bounds[1] < bounds[3] <= size[1])
            or any(not isinstance(value.get(k), str)
                   or re.fullmatch(r'[0-9a-f]{64}', value[k]) is None
                   for k in ('profile_sha256', 'reference_sha256', 'crop_pixel_sha256'))):
        raise ValueError('invalid purchase crop or Profile binding')
    reference_size = value.get('reference_size')
    if (not isinstance(reference_size, list) or len(reference_size) != 2
            or any(type(v) is not int or v <= 0 for v in reference_size)):
        raise ValueError('reference dimensions required')
    if not value['groups']:
        if (value.get('reason') == 'shape_mismatch' and value.get('presence') is None
                and reference_size != [bounds[2]-bounds[0], bounds[3]-bounds[1]]):
            return False
        raise ValueError('missing purchase groups without a crop mismatch')
    if (len(value['groups']) not in (3, 4)
            or reference_size != [bounds[2]-bounds[0], bounds[3]-bounds[1]]):
        raise ValueError('complete groups at original reference size required')
    supported = all(g.get('supported') is True and g.get('positive_polarity') is True
                    and type(g.get('reference_edges')) is int and g['reference_edges'] >= 32
                    and type(g.get('observed_edges')) is int and g['observed_edges'] >= 32
                    and all(type(g.get(k)) in (int, float)
                            and value['threshold'] <= g[k] <= 1 for k in ('coverage', 'precision'))
                    for g in value['groups'])
    if value.get('presence') is not (True if supported else None):
        raise ValueError('phase presence contradicts group evidence')
    return supported
