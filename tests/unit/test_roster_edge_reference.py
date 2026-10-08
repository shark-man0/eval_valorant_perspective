import sys
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.diagnostics.roster_edge_reference import (  # noqa: E402
    build_reference,
    locate_edges,
    masked_locations,
)


def test_masked_ncc_matches_direct_centered_formula():
    rng = np.random.default_rng(43)
    ref = rng.integers(0, 255, (16, 20), dtype=np.uint8)
    mask = np.zeros_like(ref)
    mask[2:14, 3:18] = 255
    search = rng.integers(0, 255, (25, 40), dtype=np.uint8)
    search[5:21, 11:31] = ref
    scores = masked_locations(ref, mask, search)
    chosen = mask > 0
    for x, y in ((0, 0), (11, 5), (20, 9)):
        a = ref[chosen].astype(float)
        b = search[y:y + 16, x:x + 20][chosen].astype(float)
        expected = np.corrcoef(a, b)[0, 1]
        assert scores[y, x] == pytest.approx(expected, abs=2e-6)
    result = locate_edges(ref, mask, search)
    assert result["offset_xy"] == [11, 5]
    assert result["similarity"] > .99
    assert "alive" not in result


def test_flat_search_never_becomes_verified_absence():
    ref = np.random.default_rng(9).integers(0, 255, (20, 20), dtype=np.uint8)
    result = locate_edges(ref, np.full_like(ref, 255), np.full((40, 40), 60, np.uint8))
    assert result["similarity"] is None
    assert result["reason"] == "search_contrast_insufficient"


def test_edge_mask_is_training_only_deterministic_and_nonmutating():
    source = np.random.default_rng(4).integers(0, 255, (40, 36), dtype=np.uint8)
    crops = [source.copy() for _ in range(3)]
    ref, mask, diagnostic = build_reference(crops)
    again = build_reference(crops)
    np.testing.assert_array_equal(mask, again[1])
    np.testing.assert_array_equal(ref, source)
    assert diagnostic["available"] is True
    assert diagnostic["mask_population"] >= 128
    assert min(diagnostic["training_similarity"]) >= .90
    assert set(np.unique(mask)).issubset({0, 255})
    for crop in crops:
        np.testing.assert_array_equal(crop, source)


def test_insufficient_source_and_edge_support_fail_closed():
    flat = np.full((40, 36), 60, np.uint8)
    with pytest.raises(ValueError, match="three"):
        build_reference([flat, flat])
    with pytest.raises(ValueError, match="support"):
        build_reference([flat, flat, flat])
    with pytest.raises(ValueError, match="support"):
        masked_locations(flat, np.zeros_like(flat), flat)
