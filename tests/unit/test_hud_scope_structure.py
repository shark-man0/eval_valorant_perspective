import cv2
import numpy as np
import pytest

from scripts.diagnostics.hud_scope_structure import outline_mask, top_scope


def reference():
    im = np.zeros((90, 600), np.uint8)
    for x in [0, 200, 400]:
        cv2.rectangle(im, (x + 20, 12), (x + 180, 76), 220, 2)
        cv2.line(im, (x + 30, 20), (x + 165, 65), 220, 3)
    return im, np.full_like(im, 255)


def test_scope_support_does_not_authorize_geometry_or_state():
    template, mask = reference()
    before = template.copy()
    r = top_scope(template, mask, cv2.cvtColor(template, cv2.COLOR_GRAY2BGR))
    assert r['status'] == 'TOP_STRUCTURE_SUPPORTED'
    assert len(r['tiles']) == 3 and all(t['supported'] for t in r['tiles'])
    assert not r['global_geometry_authorized'] and not r['production_qualified']
    assert r['semantic_status'] == 'UNVERIFIED' and r['formal_events'] == []
    assert np.array_equal(template, before)


@pytest.mark.parametrize('kind', ['blank', 'one_tile_missing', 'shift', 'scale', 'noise'])
def test_missing_or_misaligned_structures_cannot_pass(kind):
    template, mask = reference()
    bad = template.copy()
    if kind == 'blank':
        bad[:] = 0
    elif kind == 'one_tile_missing':
        bad[:, 200:400] = 0
    elif kind == 'shift':
        bad = np.roll(bad, 15, axis=1)
    elif kind == 'scale':
        bad = cv2.resize(bad, (300, 45))
    else:
        bad = np.random.default_rng(77).integers(0, 256, bad.shape, dtype=np.uint8)
    assert top_scope(template, mask, bad)['status'] == 'UNKNOWN'


def test_generic_line_or_missing_mask_is_not_reference_identity():
    template, mask = reference()
    mask[:] = 0
    assert top_scope(template, mask, template)['status'] == 'UNKNOWN'
    template[:] = 0
    cv2.line(template, (1, 30), (598, 30), 255, 2)
    assert top_scope(template, np.full_like(template, 255), template)['status'] == 'UNKNOWN'


def test_frozen_long_outline_remains_supported_when_short_glyphs_change():
    template, mask = reference()
    for x in [0, 200, 400]:
        cv2.putText(template, '8', (x + 95, 32), cv2.FONT_HERSHEY_SIMPLEX, .5, 255, 1)
    selected = outline_mask(template, mask)
    observed = template.copy()
    for x in [0, 200, 400]:
        observed[19:34, x + 90:x + 120] = 0
    assert top_scope(template, selected, observed)['status'] == 'TOP_STRUCTURE_SUPPORTED'
    assert not np.array_equal(selected, mask)
    assert np.array_equal(selected, outline_mask(template, mask))


def test_outline_mask_cannot_make_missing_reference_or_clutter_valid():
    template, mask = reference()
    selected = outline_mask(template, mask)
    assert top_scope(template, selected, np.zeros_like(template))['status'] == 'UNKNOWN'
    assert not outline_mask(np.zeros_like(template), mask).any()


def test_joint_constellation_needs_every_half_and_specific_whole_reference():
    from scripts.diagnostics.hud_scope_structure import joint_scope
    t, m = reference()
    m = outline_mask(t, m)
    regions = {'ally_score': [0,0,200,90], 'round_timer': [200,0,400,90],
               'enemy_score': [400,0,600,90]}
    assert joint_scope(t,m,t,regions)['status'] == 'JOINT_STRUCTURE_SUPPORTED'
    for left, right in [(0,100),(200,300),(500,600)]:
        missing = t.copy()
        missing[:, left:right] = 0
        assert joint_scope(t,m,missing,regions)['status'] == 'UNKNOWN'
    generic = np.zeros_like(t)
    cv2.line(generic,(0,30),(599,30),255,2)
    assert joint_scope(generic,np.full_like(m,255),generic,regions)['status'] == 'UNKNOWN'
