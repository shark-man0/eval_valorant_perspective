import cv2
import numpy as np
import pytest

from scripts.diagnostics import diagnose_geometry_edges as experiment
from scripts.diagnostics.geometry_edge_similarity import measure


def structure():
    gray = np.full((100, 160), 30, np.uint8)
    cv2.rectangle(gray, (20, 20), (140, 80), 170, 3)
    cv2.line(gray, (30, 30), (110, 70), 220, 3)
    return gray, np.full_like(gray, 255)


def test_identical_edges_and_unsigned_contrast_polarity():
    gray, mask = structure()
    assert measure(gray, gray, mask)["score"] == pytest.approx(1, abs=1e-6)
    assert measure(gray, 255 - gray, mask)["score"] > .95


def test_compression_and_brightness_preserve_structure_without_setting_a_runtime_threshold():
    gray, mask = structure()
    ok, encoded = cv2.imencode(".jpg", gray, [cv2.IMWRITE_JPEG_QUALITY, 75])
    assert ok
    compressed = cv2.imdecode(encoded, cv2.IMREAD_GRAYSCALE)
    bright = np.clip(gray.astype(int) + 20, 0, 255).astype(np.uint8)
    assert measure(gray, compressed, mask)["score"] > .85
    assert measure(gray, bright, mask)["score"] > .95


def test_jitter_is_bounded_and_large_shift_flat_noise_do_not_match_like_a_positive():
    gray, mask = structure()
    one = np.roll(gray, 1, axis=1)
    large = np.roll(gray, 12, axis=1)
    rng = np.random.default_rng(21)
    noise = rng.integers(0, 256, gray.shape, dtype=np.uint8)
    positive = measure(gray, one, mask)["score"]
    assert positive > measure(gray, large, mask)["score"]
    assert positive > measure(gray, noise, mask)["score"]
    assert measure(gray, np.full_like(gray, 70), mask)["score"] == 0


def test_missing_reference_is_unknown_not_a_perfect_empty_match():
    gray, mask = structure()
    empty = np.full_like(gray, 70)
    result = measure(empty, empty, mask)
    assert result["score"] is None and result["status"] == "reference_structure_insufficient"


def test_extra_edges_are_penalized_and_measurement_is_symmetric():
    gray, mask = structure()
    extra = gray.copy()
    for x in range(40, 100, 8):
        cv2.line(extra, (x, 35), (x, 65), 200, 1)
    result = measure(gray, extra, mask)
    assert result["score"] < 1
    assert result["observed_coverage"] < result["reference_coverage"]
    assert result["score"] == pytest.approx(measure(extra, gray, mask)["score"])


@pytest.mark.parametrize("fault", ["shape", "dtype", "mask"])
def test_no_silent_alignment_or_invalid_input(fault):
    gray, mask = structure()
    image = gray[:, :-1] if fault == "shape" else gray
    reference = gray.astype(np.float32) if fault == "dtype" else gray
    if fault == "mask":
        mask = mask[:, :-1]
    with pytest.raises(ValueError):
        measure(reference, image, mask)


def test_diagnostic_edge_score_never_changes_ncc_status_template_mask_or_selection():
    gray, _mask = structure()
    images = [cv2.cvtColor(np.clip(gray.astype(int) + i, 0, 255).astype(np.uint8),
                           cv2.COLOR_GRAY2BGR) for i in range(32)]
    before, assets = experiment.compare(images, .90)
    after, other = experiment.compare(images, .90, edge_similarity_diagnostic=True)
    edge = after.pop("edge_similarity_diagnostic")
    assert before == after
    assert all(np.array_equal(a, b) for a, b in zip(assets, other, strict=True))
    assert edge["acceptance_threshold"] is None and edge["production_qualified"] is False
    assert edge["used_for_reference_selection"] is False
    assert len(edge["training"]) == len(edge["development_validation"]) == 16
