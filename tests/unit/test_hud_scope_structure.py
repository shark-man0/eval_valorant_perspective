import cv2
import numpy as np
import pytest

from scripts.diagnostics.hud_scope_structure import top_scope


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
