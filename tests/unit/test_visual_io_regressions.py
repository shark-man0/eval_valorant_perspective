import numpy as np

from valorant_ai_coach.video import FrameSample
from valorant_ai_coach.visual.pixels import PixelMeasurementExtractor
from valorant_ai_coach.visual.semantic import FACT_FIELDS, SemanticVisualAdapter


def _hud(time_sec: float) -> dict:
    return {
        "time_sec": time_sec,
        "values": {},
        "quality": {"hud_confidence": 0.0},
    }


def test_entity_outlines_are_limited_to_world_roi_and_mask_hud_overlaps():
    profile = {
        "rois": {
            "world": [0.1, 0.1, 0.9, 0.9],
            "minimap": [0.1, 0.1, 0.25, 0.25],
            "weapon": [0.1, 0.75, 0.9, 0.9],
        },
        "outline_colors_hsv": {
            "enemy": {
                "lower": [50, 200, 200],
                "upper": [70, 255, 255],
                "min_area_px": 8,
            }
        },
    }
    outside_only = np.zeros((120, 160, 3), np.uint8)
    outside_only[4:12, 4:12] = (0, 255, 0)
    outside_only[16:26, 20:30] = (0, 255, 0)  # Minimap overlap.
    outside_only[96:106, 20:30] = (0, 255, 0)  # Weapon HUD overlap.
    extractor = PixelMeasurementExtractor()

    first = extractor.measure(outside_only, None, _hud(0), profile=profile)
    assert first["entities"]["visible_enemies"] == []

    inside_counterpart = outside_only.copy()
    inside_counterpart[50:60, 70:80] = (0, 255, 0)
    second = extractor.measure(inside_counterpart, None, _hud(0.1), profile=profile)
    enemies = second["entities"]["visible_enemies"]
    assert len(enemies) == 1
    assert enemies[0]["bbox_norm"] == [70 / 160, 50 / 120, 80 / 160, 60 / 120]
    assert enemies[0]["head_point_norm"] is None
    assert enemies[0]["confidence"] <= 0.64


def test_semantic_missing_frame_abstains_then_valid_frame_returns_normal_result(tmp_path):
    missing = tmp_path / "missing.jpg"
    valid = tmp_path / "valid.jpg"
    valid.write_bytes(b"test-image-bytes")
    calls: list[list[dict]] = []
    expected = {
        **{field: None for field in FACT_FIELDS},
        "affected_side": "unknown",
        "confidence": 0.95,
    }

    def transport(content: list[dict], _schema: dict) -> dict:
        calls.append(content)
        return expected

    adapter = SemanticVisualAdapter(transport=transport)

    assert adapter.observe([FrameSample(1.0, missing)], match_id="m", round_id="r") is None
    assert calls == []
    assert "semantic_frame_unreadable" in adapter.diagnostics

    result = adapter.observe([FrameSample(1.1, valid)], match_id="m", round_id="r")
    assert result == expected
    assert len(calls) == 1
    assert any(item["type"] == "input_image" for item in calls[0])
