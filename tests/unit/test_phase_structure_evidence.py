"""Fixed-position offline glyph evidence must reject missing and unrelated text."""

import hashlib
from copy import deepcopy

import cv2
import numpy as np
import pytest

from scripts.diagnostics.phase_structure_evidence import (
    PhaseStructureReference,
    bind_phase,
    phase_supported,
)
from scripts.diagnostics.round_lifecycle_evidence import lifecycle
from tests.hud_evidence_fixtures import chain, frame
from valorant_ai_coach.hud.semantic_text import SemanticTextReference


def reference():
    image = np.full((65, 390), 70, np.uint8)
    for text, x in [("BUY", 2), ("PHASE", 112), ("NOW", 280)]:
        cv2.putText(image, text, (x, 45), cv2.FONT_HERSHEY_SIMPLEX, 1, 245, 2)
    mask = np.full_like(image, 255)
    regions = np.zeros_like(image)
    for i, (a, b) in enumerate([(0, 104), (110, 270), (278, 390)], 1):
        regions[5:58, a:b] = i
    mask[regions == 0] = 0
    semantic = SemanticTextReference(
        image, mask, regions, [(f"{n:064x}", image.copy()) for n in range(1, 4)], 0.90
    )
    return semantic, PhaseStructureReference(semantic)


def test_fixed_glyphs_survive_background_change_without_lowering_ncc_threshold():
    semantic, model = reference()
    image = semantic.reference.copy()
    # Change background inside every spatial group; retain all observed glyphs.
    gradient = np.tile(np.linspace(10, 200, 65, dtype=np.uint8)[:, None], (1, 390))
    image[image < 210] = gradient[image < 210]
    assert semantic.score(image) < 0.90
    assert model.measure(image)["presence"] is True
    assert model.threshold == semantic.threshold == 0.90


def test_fixed_contrast_normalization_recovers_washed_out_intact_glyphs():
    semantic, baseline = reference()
    washed = (semantic.reference.astype(np.float32)*.10+220).astype(np.uint8)
    assert baseline.measure(washed)['presence'] is None
    contrast = PhaseStructureReference(semantic,contrast_normalized=True)
    measured = contrast.measure(washed)
    assert measured['presence'] is True
    assert all(g['coverage'] >= .90 and g['precision'] >= .90
               and g['positive_contrast'] >= 12 for g in measured['groups'])
    f = frame(1)
    image = cv2.cvtColor(washed,cv2.COLOR_GRAY2BGR)
    f['pixel_sha256'] = hashlib.sha256(image.tobytes()).hexdigest()
    f['phase_structure'] = bind_phase(f,image,[0,0,390,65],contrast,'b'*64)
    assert phase_supported(f) and not f['phase_structure']['absence_checked']
    changed = deepcopy(f)
    changed['phase_structure']['groups'][0]['positive_contrast'] = 5
    value = changed['phase_structure']
    from scripts.temporal_gt.contract import canonical_hash
    value['evidence_sha256'] = canonical_hash({k:v for k,v in value.items()
                                               if k!='evidence_sha256'})
    with pytest.raises(ValueError):
        phase_supported(changed)


@pytest.mark.parametrize('kind',['missing_group','inverted','noise','shift','low_contrast'])
def test_contrast_normalization_cannot_manufacture_glyphs_or_matching_structure(kind):
    semantic, _ = reference()
    model = PhaseStructureReference(semantic,contrast_normalized=True)
    image = semantic.reference.copy()
    if kind == 'missing_group':
        image[:,278:] = 70
    elif kind == 'inverted':
        image = 255-image
    elif kind == 'noise':
        image = np.random.default_rng(21).integers(0,256,image.shape,dtype=np.uint8)
    elif kind == 'shift':
        image = np.roll(image,8,axis=1)
    else:
        image = (image.astype(np.float32)*.04+230).astype(np.uint8)
    assert model.measure(image)['presence'] is None


@pytest.mark.parametrize("fault", ["blank", "partial", "invert", "shift", "shape", "noise"])
def test_unrelated_partial_or_incompatible_pixels_remain_unknown(fault):
    _, model = reference()
    image = model.reference.copy()
    if fault == "blank":
        image[:] = 245
    elif fault == "partial":
        image[:, 278:] = 70
    elif fault == "invert":
        image = 255 - image
    elif fault == "shift":
        image = np.roll(image, 8, axis=1)
    elif fault == "shape":
        image = image[:, :-1]
    else:
        image = np.random.default_rng(12).integers(0, 256, image.shape, dtype=np.uint8)
    result = model.measure(image)
    assert result["presence"] is None
    assert result["absence_checked"] is False and result["formal_events"] == []


def receipt(f):
    _, model = reference()
    image = cv2.cvtColor(model.reference, cv2.COLOR_GRAY2BGR)
    f["pixel_sha256"] = hashlib.sha256(image.tobytes()).hexdigest()
    return bind_phase(f, image, [0, 0, 390, 65], model, "b" * 64)


def test_receipt_cannot_cross_frame_or_acquisition_and_never_sets_absence():
    f = frame(1)
    f["phase_structure"] = receipt(f)
    assert phase_supported(f)
    before = deepcopy(f)
    for key, value in [("tick", 2), ("epoch", "other"), ("source_sha256", "c" * 64)]:
        changed = deepcopy(f)
        changed[key] = value
        with pytest.raises(ValueError):
            phase_supported(changed)
    assert f == before
    with pytest.raises(ValueError):
        changed = deepcopy(f)
        changed["phase_structure"]["presence"] = None
        phase_supported(changed)


def test_structural_purchase_keeps_score_timer_continuity_guards():
    rows = chain()
    for f in rows:
        if f["buy_phase"]:
            f["phase_structure"] = receipt(f)
            f["buy_phase"] = None
    assert lifecycle(rows)["chains"][0]["status"] == "DEVELOPMENT_LIFECYCLE_CANDIDATE"
    for f in rows[10:]:
        f["epoch"] = "new"
    # Receipts cannot be silently replayed across epochs.
    with pytest.raises(ValueError):
        lifecycle(rows)


def test_different_resolution_is_unknown_instead_of_a_valid_group_receipt():
    _, model = reference()
    f = frame(1)
    image = cv2.cvtColor(model.reference[:-2, :-2], cv2.COLOR_GRAY2BGR)
    f["pixel_sha256"] = hashlib.sha256(image.tobytes()).hexdigest()
    f["phase_structure"] = bind_phase(f, image, [0, 0, 388, 63], model, "b" * 64)
    assert f["phase_structure"]["reason"] == "shape_mismatch"
    assert phase_supported(f) is False


def test_sparse_discovery_without_native_pts_cannot_enter_lifecycle():
    f = frame(1)
    f.update(tick=None, time_base=None)
    with pytest.raises(ValueError):
        lifecycle([f])
