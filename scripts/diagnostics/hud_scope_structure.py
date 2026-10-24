"""Offline top-HUD structure evidence, never full geometry or lifecycle approval."""
from __future__ import annotations

import hashlib
import math
import re
from typing import Any, cast

import cv2
import numpy as np

from scripts.diagnostics.diagnose_hud_transfer import _specific_structure
from scripts.diagnostics.geometry_edge_similarity import measure
from scripts.diagnostics.result_title_region import title_region
from scripts.temporal_gt.contract import canonical_hash
from valorant_ai_coach.hud.layout import HudLayout
from valorant_ai_coach.hud.timer_glyphs import ImageU8

FRAME_KEYS = ('source_id', 'source_sha256', 'tick', 'time_base', 'epoch',
              'encoded_sha256', 'pixel_sha256')
BINDINGS = ('layout_sha256', 'reader_profile_sha256', 'reference_bank_sha256',
            'references_sha256')


def outline_mask(template: ImageU8, mask: ImageU8) -> ImageU8:
    """Select long reference strokes, excluding dynamic glyph interiors.

    Only the frozen reference is inspected. The observation, predicted values
    and desired calibration outcome cannot influence this mask.
    """
    if (template.dtype != np.uint8 or template.ndim != 2
            or mask.dtype != np.uint8 or mask.shape != template.shape):
        raise ValueError('same-sized uint8 gray reference/mask required')
    width = template.shape[1]
    edges = cv2.Canny(template, 60, 150)
    lines = cv2.HoughLinesP(edges, 1, np.pi / 180, max(8, math.ceil(.04 * width)),
                            minLineLength=max(12, math.ceil(.06 * width)),
                            maxLineGap=max(1, math.ceil(.005 * width)))
    selected = np.zeros_like(mask)
    if lines is not None:
        for x1, y1, x2, y2 in lines[:, 0]:
            cv2.line(selected, (int(x1), int(y1)), (int(x2), int(y2)), 255, 5)
    return np.asarray(cv2.bitwise_and(mask, selected), dtype=np.uint8)


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


def joint_scope(template: ImageU8, mask: ImageU8, observed: ImageU8,
                regions: dict[str, list[int]]) -> dict[str, Any]:
    """One reference must support all six halves of three fixed components.

    Specificity is checked on their joint mask. Separate generic lines cannot
    authorize a component; the frozen three-part spatial constellation, edge
    orientations and every region must agree at the unchanged .90 floor.
    """
    result: dict[str, Any] = {'status': 'UNKNOWN', 'reference_specific': False,
                              'regions': {}}
    if template.shape != observed.shape[:2]:
        return result
    joint = np.zeros_like(mask)
    for x, y, xx, yy in regions.values():
        if not (0 <= x < xx <= template.shape[1] and 0 <= y < yy <= template.shape[0]):
            return result
        joint[y:yy, x:xx] = mask[y:yy, x:xx]
    if not _specific_structure(template, joint):
        return result
    gray = cv2.cvtColor(observed, cv2.COLOR_BGR2GRAY) if observed.ndim == 3 else observed
    measured: dict[str, dict[str, Any]] = {}
    for name, (x, y, xx, yy) in regions.items():
        tiles = []
        for a, b in ((x, (x+xx)//2), ((x+xx)//2, xx)):
            detail = measure(template[y:yy, a:b], gray[y:yy, a:b], mask[y:yy, a:b])
            tiles.append({**detail, 'bounds': [a,y,b,yy],
                          'supported': detail['score'] is not None and detail['score'] >= .90})
        measured[name] = {'bounds': [x,y,xx,yy], 'tiles': tiles}
    supported = all(t['supported'] for v in measured.values() for t in v['tiles'])
    return {'status': 'JOINT_STRUCTURE_SUPPORTED' if supported else 'UNKNOWN',
            'reference_specific': True, 'regions': measured,
            'reference_mask_sha256': hashlib.sha256(joint.tobytes()).hexdigest()}


def _joint_supported(value: dict[str, Any], box: list[int], same_size: bool) -> bool:
    if value.get('reference_specific') is False and value.get('regions') == {}:
        if value.get('status') != 'UNKNOWN':
            raise ValueError('unavailable joint reference must remain UNKNOWN')
        return False
    regions = value.get('regions')
    if (value.get('reference_specific') is not True or not isinstance(regions, dict)
            or set(regions) != {'ally_score','enemy_score','round_timer'}
            or re.fullmatch(r'[0-9a-f]{64}', value.get('reference_mask_sha256', '')) is None):
        raise ValueError('specific fixed joint reference required')
    supported = same_size
    for region in regions.values():
        bounds = region.get('bounds')
        if (not isinstance(bounds, list) or len(bounds) != 4
                or any(type(v) is not int for v in bounds)
                or not (0 <= bounds[0] < bounds[2] <= box[2]-box[0]
                        and 0 <= bounds[1] < bounds[3] <= box[3]-box[1])):
            raise ValueError('joint region outside fixed top HUD')
        a,b,c,d = bounds
        tiles = region.get('tiles', [])
        if [v.get('bounds') for v in tiles] != [[a,b,(a+c)//2,d],[(a+c)//2,b,c,d]]:
            raise ValueError('both disjoint halves required')
        for tile in tiles:
            ok = (type(tile.get('score')) in (int,float) and math.isfinite(tile['score'])
                  and .90 <= tile['score'] <= 1 and tile.get('reference_edge_count',0) >= 32)
            if tile.get('supported') is not bool(ok):
                raise ValueError('joint tile flag contradicts measured edges')
            supported = supported and ok
    left, timer, right = (regions[k]['bounds'] for k in (
        'ally_score','round_timer','enemy_score'))
    if not (left[0] < timer[0] < right[0] and left[2] <= timer[2] and timer[2] <= right[2]):
        raise ValueError('ordered separated Score/Timer constellation required')
    if value.get('status') != ('JOINT_STRUCTURE_SUPPORTED' if supported else 'UNKNOWN'):
        raise ValueError('joint status contradicts its component evidence')
    return supported


def reference_fingerprint(references: list[tuple[ImageU8, ImageU8]]) -> str:
    return canonical_hash([[hashlib.sha256(t.tobytes()).hexdigest(),
                            hashlib.sha256(m.tobytes()).hexdigest()] for t, m in references])


def _result_bounds(frame: dict[str, Any], image_size: list[int]) -> list[int] | None:
    region = frame['result'].get('region', {})
    outer, bounds = region.get('outer_pixel_bounds'), region.get('text_pixel_bounds')
    if (region.get('method') != 'relative_white210_title_line_v1'
            or region.get('status') != 'PROPOSAL'
            or not isinstance(outer, list) or not isinstance(bounds, list)
            or len(outer) != 4 or len(bounds) != 4
            or any(type(n) is not int for n in outer + bounds)):
        return None
    a, b, c, d = outer
    x, y, xx, yy = bounds
    if not (0 <= a <= x < xx <= c <= image_size[0]
            and 0 <= b <= y < yy <= d <= image_size[1]):
        return None
    return bounds


def component_geometry(frame: dict[str, Any], image: ImageU8, layout: HudLayout,
                       references: list[tuple[ImageU8, ImageU8]],
                       bindings: dict[str, str], *, joint_regions: bool = False) -> dict[str, Any]:
    """Bind actual pixels and frozen long-line references to Round ROI support.

    References contain precomputed outline masks. No player state/ownership or
    full calibration is authorized; only the offline Round consumers opt in.
    """
    if type(joint_regions) is not bool:
        raise ValueError('explicit joint-region option required')
    if (image.dtype != np.uint8 or image.ndim != 3 or image.shape[2] != 3
            or hashlib.sha256(image.tobytes()).hexdigest() != frame['pixel_sha256']):
        raise ValueError('component geometry requires bound native BGR pixels')
    if (set(bindings) != set(BINDINGS) or any(re.fullmatch(r'[0-9a-f]{64}', v) is None
                                            for v in bindings.values())
            or not references
            or reference_fingerprint(references) != bindings['references_sha256']):
        raise ValueError('frozen component reference/profile bindings required')
    size = [image.shape[1], image.shape[0]]
    same_size = tuple(size) == layout.reference_resolution
    top_bounds = layout.normalized_roi('top_match_bar').pixel_bounds(*size)
    x, y, xx, yy = top_bounds
    scopes = [top_scope(t, m, image[y:yy, x:xx]) for t, m in references] if same_size else []
    best = max(scopes, key=lambda z: min((v['score'] or 0 for v in z['tiles']), default=0)
               ) if scopes else {'status': 'UNKNOWN', 'tiles': []}
    supported = same_size and best['status'] == 'TOP_STRUCTURE_SUPPORTED'
    joint: dict[str, Any] = {'status': 'UNKNOWN', 'reference_specific': False, 'regions': {}}
    if joint_regions and same_size:
        regions = {}
        for role in ('ally_score','enemy_score','round_timer'):
            a,b,c,d = layout.normalized_roi(role).pixel_bounds(*size)
            regions[role] = [a-x,b-y,c-x,d-y]
        proposals = [joint_scope(t,m,image[y:yy,x:xx],regions) for t,m in references]
        joint = max(proposals, key=lambda z: min((v['score'] or 0
                    for r in z['regions'].values() for v in r['tiles']), default=0))
    joint_valid = joint['status'] == 'JOINT_STRUCTURE_SUPPORTED'
    bounds = _result_bounds(frame, size)
    result_verified = False
    if bounds and frame['result']['region']['outer_pixel_bounds'] == list(
            layout.normalized_roi('round_end_banner').pixel_bounds(*size)):
        a, b, c, d = bounds
        left, top, right, bottom = frame['result']['region']['outer_pixel_bounds']
        proposal = title_region(image[top:bottom, left:right])
        relative = proposal['bounds']
        result_verified = (proposal['status'] == 'PROPOSAL' and relative is not None
                           and bounds == [left + relative[0], top + relative[1],
                                          left + relative[2], top + relative[3]]
                           and hashlib.sha256(image[b:d, a:c].tobytes()).hexdigest() == (
                               frame['result']['region'].get('crop_pixel_sha256')))
    record = {'kind': 'offline_Round_component_geometry_v1',
              'method': ('frozen_long_outline_joint_regions_v1' if joint_regions
                         else 'frozen_long_outline_three_tiles_v1'),
              'frame': {k: frame[k] for k in FRAME_KEYS}, 'bindings': bindings.copy(),
              'image_size': size, 'reference_resolution': list(layout.reference_resolution or ()),
              'top_bounds': list(top_bounds), 'top_scope': best,
              'result_region_sha256': canonical_hash(frame['result'].get('region', {})),
              'reader_evidence_sha256': canonical_hash({k: frame[k] for k in (
                  'ally_score', 'enemy_score', 'timer', 'result')}),
              'result_region_verified': result_verified,
              'roles': {'score': supported or joint_valid, 'timer': supported or joint_valid,
                        'result': (supported or joint_valid) and result_verified},
              **({'joint_scope': joint} if joint_regions else {}),
              'global_geometry_authorized': False, 'ownership_authorized': False,
              'production_qualified': False, 'formal_events': []}
    return {**record, 'evidence_sha256': canonical_hash(record)}


def component_support(frame: dict[str, Any], role: str) -> bool:
    """Validate opt-in receipt; partial support never becomes full geometry."""
    value = frame.get('component_geometry')
    if value is None:
        return False
    if (role not in {'score', 'timer', 'result'} or not isinstance(value, dict)
            or value.get('kind') != 'offline_Round_component_geometry_v1'
            or value.get('method') not in {'frozen_long_outline_three_tiles_v1',
                                           'frozen_long_outline_joint_regions_v1'}
            or value.get('frame') != {k: frame[k] for k in FRAME_KEYS}
            or value.get('evidence_sha256') != canonical_hash(
                {k: v for k, v in value.items() if k != 'evidence_sha256'})
            or any(value.get(k) is not False for k in (
                'global_geometry_authorized', 'ownership_authorized', 'production_qualified'))
            or value.get('formal_events') != []
            or set(value.get('roles', {})) != {'score', 'timer', 'result'}
            or any(type(v) is not bool for v in value['roles'].values())
            or set(value.get('bindings', {})) != set(BINDINGS)
            or any(not isinstance(v, str) or re.fullmatch(r'[0-9a-f]{64}', v) is None
                   for v in value['bindings'].values())
            or value.get('result_region_sha256') != canonical_hash(
                frame['result'].get('region', {}))
            or value.get('reader_evidence_sha256') != canonical_hash({k: frame[k] for k in (
                'ally_score', 'enemy_score', 'timer', 'result')})):
        raise ValueError('invalid bound component geometry receipt')
    tiles = value.get('top_scope', {}).get('tiles', [])
    size = value.get('image_size')
    bounds = value.get('top_bounds')
    top_valid = (isinstance(size, list) and len(size) == 2
                 and all(type(n) is int and n > 0 for n in size)
                 and isinstance(bounds, list) and len(bounds) == 4
                 and all(type(n) is int for n in bounds)
                 and 0 <= bounds[0] < bounds[2] <= size[0]
                 and 0 <= bounds[1] < bounds[3] <= size[1])
    box = cast(list[int], bounds)
    expected = ([[((box[2] - box[0]) * i // 3), 0,
                  ((box[2] - box[0]) * (i+1) // 3), box[3] - box[1]]
                 for i in range(3)] if top_valid else [])
    supported = (isinstance(size, list) and len(size) == 2
                 and all(type(n) is int and n > 0 for n in size)
                 and size == value.get('reference_resolution')
                 and value['top_scope'].get('status') == 'TOP_STRUCTURE_SUPPORTED'
                 and top_valid and [t.get('bounds') for t in tiles] == expected
                 and len(tiles) == 3 and all(
                     type(t.get('score')) in (int, float) and math.isfinite(t['score'])
                     and .90 <= t['score'] <= 1 and t.get('reference_edge_count', 0) >= 32
                     for t in tiles))
    if value['method'] == 'frozen_long_outline_joint_regions_v1':
        joint = value.get('joint_scope')
        if not isinstance(joint, dict) or not top_valid:
            raise ValueError('bound joint regions required')
        joint_valid = _joint_supported(joint, box, size == value.get('reference_resolution'))
        supported = supported or joint_valid
    elif 'joint_scope' in value:
        raise ValueError('joint support requires explicit method')
    roles = {'score': supported, 'timer': supported,
             'result': supported and value.get('result_region_verified') is True
             and _result_bounds(frame, cast(list[int], size)) is not None}
    if value.get('roles') != roles:
        raise ValueError('component roles contradict structure evidence')
    return bool(roles[role])
