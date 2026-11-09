import json
from types import SimpleNamespace

import cv2
import numpy as np

from valorant_ai_coach.temporal import public_map_pixels as module


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
