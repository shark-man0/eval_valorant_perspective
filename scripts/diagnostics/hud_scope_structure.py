"""Offline top-HUD structure evidence, never full geometry or lifecycle approval."""
from __future__ import annotations

from typing import Any

import cv2
import numpy as np

from scripts.diagnostics.diagnose_hud_transfer import _specific_structure
from scripts.diagnostics.geometry_edge_similarity import measure
from valorant_ai_coach.hud.timer_glyphs import ImageU8


def top_scope(template: ImageU8, mask: ImageU8, observed: ImageU8) -> dict[str, Any]:
    """Compare three disjoint tiles at the expected position, without alignment.

    Missing bottom HUD can explain a global rejection while top structure is
    supported. This result cannot replace geometry_consistent, identify a
    player, attest a screen state or establish a Result/Score/Timer value.
    """
    if (template.dtype != np.uint8 or template.ndim != 2 or mask.dtype != np.uint8
            or mask.shape != template.shape or observed.dtype != np.uint8
            or observed.ndim not in (2, 3)
            or observed.ndim == 3 and observed.shape[2] != 3):
        raise ValueError('uint8 gray reference/mask and gray/BGR observation required')
    result: dict[str, Any] = {
        'method': 'three_disjoint_top_tiles_v1', 'status': 'UNKNOWN', 'tiles': [],
        'global_geometry_authorized': False, 'semantic_status': 'UNVERIFIED',
        'formal_events': [], 'production_qualified': False,
    }
    if observed.shape[:2] != template.shape:
        return {**result, 'reason': 'resolution_or_region_mismatch'}
    if min(template.shape) < 8 or not _specific_structure(template, mask):
        return {**result, 'reason': 'reference_structure_nonspecific'}
    gray = cv2.cvtColor(observed, cv2.COLOR_BGR2GRAY) if observed.ndim == 3 else observed
    width = template.shape[1]
    for i in range(3):
        left, right = width * i // 3, width * (i + 1) // 3
        detail = measure(template[:, left:right], gray[:, left:right], mask[:, left:right])
        result['tiles'].append({**detail, 'bounds': [left, 0, right, template.shape[0]],
                                'supported': detail['score'] is not None
                                and detail['score'] >= .90})
    supported = all(t['supported'] for t in result['tiles'])
    return {**result, 'status': 'TOP_STRUCTURE_SUPPORTED' if supported else 'UNKNOWN',
            'reason': 'all_three_tiles_supported' if supported else 'tile_structure_missing'}
