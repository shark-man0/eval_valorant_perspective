import hashlib
import json
from types import SimpleNamespace

import cv2
import numpy as np
import pytest

from valorant_ai_coach.temporal import public_map_pixels as module


@pytest.mark.parametrize(("shift", "recovered"), [(2, True), (6, False)])
def test_contrast_fits_preserve_original_roi_binding_and_require_agreement(shift, recovered):
    projector = object.__new__(module.PublicMapPixels)
    matrices = iter([
        [[1, 0, 0], [0, 1, 0], [0, 0, 1]],
        [[1, 0, shift], [0, 1, 0], [0, 0, 1]],
    ])
    def inspect(_):
        return {"raw": {"map_name_candidates": [{
            "map_id": "map", "fit_residual_p95_reference_px": 1.0,
            "reference_to_roi_homography_candidate": next(matrices),
        }]}}

    projector.inspect_exact = inspect
    image = np.full((80, 80, 3), 100, np.uint8)
    raw = {"map_name_candidates": [], "reference_ranking": [],
           "roi_pixel_bounds": [10, 10, 70, 70], "roi_pixel_sha256": "0" * 64}
    assert projector.recover_contrast(image, raw, "wrong", (4, 4)) == raw
    result = projector.recover_contrast(image, raw, "map", (40, 40))
    assert bool(result["map_name_candidates"]) == recovered
    assert image.min() == image.max() == 100
    if recovered:
        assert result["roi_pixel_sha256"] == raw["roi_pixel_sha256"]
        assert result["alignment_recovery"] == module.CONTRAST_ALIGNMENT
        assert result["map_name_candidates"][0]["fit_residual_p95_reference_px"] == shift


def test_public_reference_alignment_is_advisory_and_blank_view_is_unknown(tmp_path, monkeypatch):
    random = np.random.default_rng(42)
    mask = np.zeros((320, 320), np.uint8)
    for x, y, size in random.integers(8, 280, (60, 3)):
        cv2.rectangle(
            mask,
            (int(x), int(y)),
            (min(310, int(x + size // 6 + 3)), min(310, int(y + size // 8 + 3))),
            180,
            2,
        )
    reference = np.dstack([mask, mask, mask, mask])
    cv2.imwrite(str(tmp_path / "reference.png"), reference)
    index = tmp_path / "index.json"
    index.write_text(
        json.dumps(
            {
                "maps": [{"name": "SyntheticMap", "id": "m", "reference": "reference.png"}],
                "catalog_version": "synthetic",
            }
        ),
        encoding="utf-8",
    )
    layout = tmp_path / "layout.json"
    layout.write_text("{}", encoding="utf-8")
    monkeypatch.setattr(
        module.HudLayout,
        "load",
        lambda _: SimpleNamespace(
            normalized_roi=lambda _: SimpleNamespace(pixel_bounds=lambda w, h: (0, 0, 320, 320))
        ),
    )
    reader = module.PublicMapPixels(index, layout)
    pixels = np.zeros((720, 1280, 3), np.uint8)
    pixels[:320, :320] = reference[:, :, :3]
    result = reader.inspect(pixels)
    assert result["raw"]["map_name_candidates"][0]["map_name"] == "SyntheticMap"
    assert result["raw"]["marker_transform_qualified"] is False
    assert result["map_candidates"] == []
    assert result["signals"] == []
    assert reader.inspect(np.zeros_like(pixels))["raw"]["map_name_candidates"] == []
    cv2.setRNGSeed(11)
    exact = reader.inspect_exact(pixels)
    cv2.setRNGSeed(501)
    assert reader.inspect_exact(pixels) == exact


    extra = tmp_path / "reference.png"
    sha = hashlib.sha256(extra.read_bytes()).hexdigest()
    index.write_text(json.dumps({"maps": [], "catalog_version": "synthetic"}), encoding="utf-8")
    added = module.PublicMapPixels(
        index, layout, verified_references=[("VerifiedOnly", "m", extra, sha)],
    )
    hit, = added.inspect(pixels)["raw"]["map_name_candidates"]
    assert hit["map_name"] == "VerifiedOnly"
    assert hit["reference_image_size_px"] == [320, 320]
    assert hit["fit_residual_p95_reference_px"] < 1e-3
    with pytest.raises(ValueError, match="Verified Map reference bytes changed"):
        module.PublicMapPixels(
            index, layout, verified_references=[("VerifiedOnly", "m", extra, "e"*64)],
        )


def test_exact_search_recovery_requires_agreeing_geometry(monkeypatch):
    reader = object.__new__(module.PublicMapPixels)
    reader.matcher = object()
    reader.exact_matcher = object()
    baseline = {
        "map_id": "test", "inliers": 17,
        "reference_to_roi_homography_candidate": [[1, 0, 1], [0, 1, 1], [0, 0, 1]],
    }
    candidate = {**baseline, "inliers": 23}

    def inspect(image, matcher):
        exact = matcher is reader.exact_matcher
        return {"raw": {"reference_ranking": [candidate if exact else baseline],
                        "map_name_candidates": [candidate] if exact else [],
                        "roi_pixel_bounds": [0, 0, 200, 200]}}

    monkeypatch.setattr(reader, "_inspect", inspect)
    pixels = np.zeros((240, 240, 3), np.uint8)
    assert not reader.inspect(pixels)["raw"]["map_name_candidates"]
    assert reader.inspect(pixels, recover_alignment=True)["raw"]["map_name_candidates"]
    candidate["reference_to_roi_homography_candidate"] = [[1, 0, 25], [0, 1, 1], [0, 0, 1]]
    assert not reader.inspect(pixels, recover_alignment=True)["raw"]["map_name_candidates"]
