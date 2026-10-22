"""Offline structural/NCC decomposition; never runtime calibration or semantic GT.

Uses existing edge masks, raw NCC matcher and geometry policy. Experimental
structure localization is deliberately isolated from production and ownership.
Callers must freeze DEVELOPMENT-only source/frame provenance before fitting.
"""
from __future__ import annotations

import hashlib
import json
import math
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import cv2
import numpy as np

from scripts.diagnostics.diagnose_geometry_edges import (
    edge_candidate,
    persistent_structure,
    raw_scores,
)
from scripts.diagnostics.geometry_edge_similarity import features, measure
from valorant_ai_coach.hud.analyzers import _detect_letterbox
from valorant_ai_coach.hud.calibrate_temporal import ANCHORS, _check_output_privacy
from valorant_ai_coach.hud.layout import HudLayout, NormalizedRoi
from valorant_ai_coach.hud.templates import HudTemplateProfile


@dataclass(frozen=True)
class Reference:
    template: np.ndarray
    mask: np.ndarray
    profile: HudTemplateProfile
    search: list[float] | str
    training_index: int


def _specific_structure(template: np.ndarray, mask: np.ndarray) -> bool:
    """Reject sparse/localized edges and generic one/two-direction contours.

    This is only a frozen diagnostic specificity gate, never semantic HUD proof.
    """
    edges, real, imaginary = features(template, mask)
    if int(edges.sum()) < 32:
        return False
    angle = np.mod(np.arctan2(imaginary, real) / 2, np.pi)
    bins = np.floor(np.mod(angle + np.pi / 8, np.pi) / (np.pi / 4)).astype(int)
    counts = np.bincount(bins[edges], minlength=4)
    height, width = edges.shape
    ys, xs = np.nonzero(edges)
    cells = set(zip(np.minimum(ys * 4 // height, 3),
                    np.minimum(xs * 4 // width, 3), strict=True))
    return int(np.count_nonzero(counts >= 8)) >= 3 and len(cells) >= 4


def freeze_bank(training: list[np.ndarray], layout: HudLayout, base: dict[str, Any],
                output: Path, *, selection: str = 'ncc',
                training_groups: list[str] | None = None,
                ) -> tuple[dict[str, list[Reference]], dict[str, Any]]:
    """Max three references, ranked by non-self training support; no test input."""
    _check_output_privacy(output)
    if selection not in {'ncc', 'structure'}:
        raise ValueError('unsupported offline reference selection')
    if selection == 'structure' and (training_groups is None or
            len(training_groups) != len(training) or len(set(training_groups)) < 2):
        raise ValueError('structure selection requires aligned multi-source training groups')
    if len(training) < 8 or layout.reference_resolution is None:
        raise ValueError('at least eight training images and a reference resolution required')
    width, height = layout.reference_resolution
    if any(im.dtype != np.uint8 or im.shape != (height, width, 3) for im in training):
        raise ValueError('unchanged uint8 reference-resolution training required')
    bank: dict[str, list[Reference]] = {}
    stats: dict[str, Any] = {}
    for name in ANCHORS:
        if name not in layout.regions:
            continue
        bank[name] = []
        roi = layout.normalized_roi(name)
        x0, y0, x1, y1 = roi.pixel_bounds(width, height)
        crops = [im[y0:y1, x0:x1] for im in training]
        spec = base.get('anchors', {}).get(name, {})
        threshold = spec.get('threshold', .90)
        if type(threshold) not in (int, float) or not math.isfinite(threshold) or not .90 <= (
                threshold) <= 1:
            raise ValueError('unchanged NCC threshold >=0.90 required')
        proposal = (edge_candidate(crops, template_strategy='training_medoid', threshold=threshold)
                    if selection == 'ncc' else None)
        structure = persistent_structure(crops) if selection == 'structure' else None
        if structure is not None and structure[1]['mask_population'] >= 64:
            proposal = (np.empty(0), *structure)
        if proposal is None:
            stats[name] = {'reason': 'reference_structure_insufficient', 'reference_count': 0}
            continue
        _, mask, details = proposal
        templates = [cv2.cvtColor(im, cv2.COLOR_BGR2GRAY) for im in crops]
        # The structural path never invokes raw_scores or the NCC medoid selector.
        eligible = ([True] * len(templates) if selection == 'ncc' else
                    [_specific_structure(template, mask) for template in templates])
        support = ([raw_scores(crops, template, mask) for template in templates]
                   if selection == 'ncc' else
                   [[float(measure(template, other, mask)['score'] or 0.)
                     for other in templates] for template in templates])
        support_threshold = threshold if selection == 'ncc' else .90
        selected: list[int] = []
        covered: set[int] = set()
        for _ in range(3):
            choices = []
            for i, scores in enumerate(support):
                hits = {j for j, score in enumerate(scores) if j != i
                        and score >= support_threshold and eligible[j]}
                group_ok = selection == 'ncc' or len({(training_groups or [])[j]
                                                     for j in hits}) >= 2
                if (eligible[i] and group_ok and i not in selected and len(hits) >= 3
                        and len(hits - covered) >= 3):
                    choices.append((len(hits - covered), len(hits),
                                    float(np.median(scores[:i] + scores[i + 1:])), -i, hits))
            if not choices:
                break
            choice = max(choices, key=lambda v: v[:4])
            i = -choice[3]
            selected.append(i)
            covered.update(choice[4])
        search = spec.get('search_region', [max(0, roi.x - .06), max(0, roi.y - .06),
                                           min(1, roi.right + .06), min(1, roi.bottom + .06)])
        for rank, index in enumerate(selected):
            template = templates[index].copy()
            reference_mask = mask.copy()
            paths = []
            for suffix, pixels in [('template', template), ('mask', reference_mask)]:
                path = output / f'{name}_{rank}.{suffix}.png'
                ok, encoded = cv2.imencode('.png', pixels)
                if not ok:
                    raise ValueError('cannot encode frozen diagnostic reference')
                with open(path, 'xb', opener=lambda p, f: os.open(p, f, 0o600)) as stream:
                    stream.write(encoded.tobytes())
                paths.append(path)
            profile = HudTemplateProfile(output / 'not_exported.templates.json', {
                'schema_version': '1.0', 'anchors': {name: {
                    'template': paths[0].name, 'mask': paths[1].name,
                    'threshold': threshold, 'search_region': search,
                }}, 'signals': {}, 'readers': {},
            })
            template.setflags(write=False)
            reference_mask.setflags(write=False)
            bank[name].append(Reference(template, reference_mask, profile, search, index))
        stats[name] = {**details, 'reference_count': len(selected),
                       'selected_training_indices': selected,
                       'reason': ('frozen_training_support' if selected else
                                  'training_support_missing' if selection == 'ncc' else
                                  'reference_structure_nonspecific' if not any(eligible) else
                                  'structural_training_support_missing'),
                       'threshold': threshold, 'selection_excludes_self': True,
                       'semantic_label': 'UNKNOWN'}
        if selection == 'structure':
            stats[name].update(selection='structure', ncc_used_for_selection=False,
                               eligible_candidates=sum(eligible),
                               structural_nonself_support=[
                                   sum(j != i and score >= .90 and eligible[j]
                                       for j, score in enumerate(scores))
                                   for i, scores in enumerate(support)],
                               structural_threshold=.90, supporter_source_groups_min=2)
    return bank, stats


def _structural(image: np.ndarray, layout: HudLayout, name: str, ref: Reference) -> dict[str, Any]:
    height, width = image.shape[:2]
    x0, y0, x1, y1 = HudTemplateProfile._search_region(ref.search, layout, width, height)
    search = cv2.cvtColor(image[y0:y1, x0:x1], cv2.COLOR_BGR2GRAY)
    th, tw = ref.template.shape
    if search.shape[0] < th or search.shape[1] < tw:
        return {'supported': False, 'reason': 'search_region_too_small', 'score': None}
    reference_edges = cv2.Canny(ref.template, 60, 150)
    reference_edges[ref.mask == 0] = 0
    if np.count_nonzero(reference_edges) < 32:
        return {'supported': False, 'reason': 'reference_structure_insufficient', 'score': None}
    edges = cv2.Canny(search, 60, 150)
    # Proposal only. A high binary correlation cannot authorize a calibration.
    proposal = cv2.matchTemplate(edges, reference_edges, cv2.TM_CCORR_NORMED)
    proposal = np.where(np.isfinite(proposal), proposal, -1.)
    _, proposal_score, _, location = cv2.minMaxLoc(proposal)
    left, top = location
    details = measure(ref.template, search[top:top + th, left:left + tw], ref.mask)
    score = details['score']
    supported = score is not None and score >= .90
    box = NormalizedRoi((x0 + left) / width, (y0 + top) / height, tw / width, th / height)
    return {**details, 'supported': supported,
            'reason': 'diagnostic_structure_support' if supported else 'structure_mismatch',
            'proposal_score': float(proposal_score), 'box': box,
            'anchor': name, 'training_index': ref.training_index}


def observe(image: np.ndarray, layout: HudLayout,
            bank: dict[str, list[Reference]], *,
            reference_stats: dict[str, Any] | None = None) -> dict[str, Any]:
    if image.dtype != np.uint8 or image.ndim != 3 or image.shape[2] != 3:
        raise ValueError('unchanged uint8 BGR frame required')
    height, width = image.shape[:2]
    methods: dict[str, dict[str, NormalizedRoi]] = {
        'ncc_single': {}, 'ncc_multi': {}, 'structure_multi': {},
    }
    rows: dict[str, Any] = {}
    resolution_ok = layout.reference_resolution == (width, height)
    for name, references in bank.items():
        if not resolution_ok or not references:
            reason = (reference_stats or {}).get(name, {}).get('reason')
            missing = {
                'reference_structure_insufficient': 'reference_structure_insufficient',
                'training_support_missing': 'reference_training_support_missing',
                'structural_training_support_missing': 'reference_structural_support_missing',
                'reference_structure_nonspecific': 'reference_structure_nonspecific',
            }.get(reason, 'reference_unavailable')
            rows[name] = {'classification': missing if resolution_ok else 'resolution_mismatch',
                          'reference_count': len(references)}
            continue
        ncc, structural = [], []
        for ref in references:
            anchors, scores, _ = ref.profile.detect_anchors(image, layout)
            ncc.append((scores.get(name, 0.), anchors.get(name)))
            structural.append(_structural(image, layout, name, ref))
        if ncc[0][1] is not None:
            methods['ncc_single'][name] = ncc[0][1]
        best_ncc = max(ncc, key=lambda v: v[0])
        if best_ncc[1] is not None:
            methods['ncc_multi'][name] = best_ncc[1]
        best_structure = max(structural, key=lambda v: v.get('score') or 0.)
        if best_structure['supported']:
            methods['structure_multi'][name] = best_structure['box']
        x0, y0, x1, y1 = layout.normalized_roi(name).pixel_bounds(width, height)
        edge_count = int(np.count_nonzero(cv2.Canny(
            cv2.cvtColor(image[y0:y1, x0:x1], cv2.COLOR_BGR2GRAY), 60, 150)))
        classification = (
            'structure_supported_ncc_rejected'
            if best_structure['supported'] and best_ncc[1] is None
            else 'ncc_supported' if best_ncc[1] is not None
            else 'observed_edges_insufficient' if edge_count < 32
            else 'structure_mismatch_ncc_rejected'
        )
        rows[name] = {'classification': classification, 'reference_count': len(references),
                      'best_ncc_score': best_ncc[0], 'ncc_single_supported': ncc[0][1] is not None,
                      'ncc_multi_supported': best_ncc[1] is not None,
                      'structure_supported': best_structure['supported'],
                      'structure_score': best_structure.get('score'),
                      'observed_edges_at_expected_roi': edge_count,
                      'semantic_label': 'UNKNOWN'}
    results: dict[str, Any] = {}
    for method, anchors in methods.items():
        calibration = layout.validate_calibration(
            width, height, detected_anchors=anchors, letterboxed=_detect_letterbox(image),
            crop_applied=False if resolution_ok else None,
        )
        results[method] = {'geometry_consistent': calibration.calibrated,
                           'accepted_anchors': sorted(anchors),
                           'reasons': list(calibration.reasons),
                           'positions': {n: [v.x, v.y, v.right, v.bottom]
                                         for n, v in anchors.items()}}
    return {**results, 'anchors': rows, 'semantic_label': 'UNKNOWN',
            'production_qualified': False, 'formal_events': []}


def bank_fingerprint(bank: dict[str, list[Reference]]) -> str:
    digest = hashlib.sha256()
    for name, refs in bank.items():
        digest.update(name.encode('ascii'))
        for ref in refs:
            digest.update(ref.template.tobytes())
            digest.update(ref.mask.tobytes())
            digest.update(json.dumps(ref.profile.raw, sort_keys=True).encode('utf-8'))
            for asset in ref.profile.asset_paths:
                digest.update(ref.profile.resolve_asset(str(asset)).read_bytes())
    return digest.hexdigest()
