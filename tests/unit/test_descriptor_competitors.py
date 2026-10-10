import json

import numpy as np

from scripts.diagnostics.audit_descriptor_competitors import competitors


def test_repeated_patches_keep_competitors_instead_of_choosing_a_peak():
    source = np.zeros((360, 640), np.uint8)
    patch = np.random.default_rng(5).integers(0, 256, (15, 15), np.uint8)
    source[43:58, 43:58] = patch
    current = source.copy()
    current[43:58, 83:98] = patch
    result = competitors(
        source,
        current,
        (30, 30, 70, 70),
        [(30, 30, 110, 80)],
        [50, 50],
        [90, 50],
        [[1, 0, 0], [0, 1, 0]],
    )
    assert result["integer_peak_count"] == 2
    assert result["peaks_outside_endpoint_2px"] == 1
    assert result["peaks_outside_projection_2px"] == 1
    assert result["endpoint_ncc"] >= 0.90
    assert result["projection_ncc"] >= 0.90
    assert json.loads(json.dumps(result)) == result


def test_unavailable_oriented_source_and_fractional_current_taps_stay_unknown():
    source = np.random.default_rng(6).integers(0, 256, (360, 640), np.uint8)
    missing = competitors(
        source,
        source,
        (43, 43, 58, 58),
        [(30, 30, 110, 80)],
        [50, 50],
        [50, 50],
        [[0.8, 0, 0], [0, 0.8, 0]],
    )
    assert missing["reason"] == "oriented_source_footprint_unavailable"
    result = competitors(
        source,
        source,
        (30, 30, 70, 70),
        [(30, 30, 58, 80)],
        [50, 50],
        [50.5, 50],
        [[1, 0, 0], [0, 1, 0]],
    )
    assert result["endpoint_ncc"] is None


def test_constant_source_is_not_a_localization_witness():
    source = np.zeros((360, 640), np.uint8)
    result = competitors(
        source,
        source,
        (30, 30, 70, 70),
        [(30, 30, 110, 80)],
        [50, 50],
        [50, 50],
        [[1, 0, 0], [0, 1, 0]],
    )
    assert result["reason"] == "source_texture_unavailable"
