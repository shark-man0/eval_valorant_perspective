import json

import cv2
import numpy as np
import pytest

from valorant_ai_coach.temporal.generic_map_provider import GenericMapObserver


def observer(tmp_path):
    layout = tmp_path / "layout.json"
    layout.write_text(
        json.dumps(
            {
                "schema_version": "3.0",
                "reference_resolution": {"width": 1920, "height": 1080},
                "rois": {"minimap_normal": {"norm": [0.01, 0.04, 0.25, 0.44]}},
            }
        ),
        encoding="utf-8",
    )
    config = tmp_path / "config.json"
    config.write_text(json.dumps({"layout": str(layout)}), encoding="utf-8")
    return GenericMapObserver(config), config


def test_image_only_map_candidate_keeps_name_zone_and_owner_unresolved(tmp_path):
    reader, _ = observer(tmp_path)
    image = np.zeros((1080, 1920, 3), np.uint8)
    cv2.circle(image, (150, 150), 8, (0, 255, 255), 2)
    result = reader.inspect(image)
    assert result["signals"] == []
    assert result["context"]["stream_kind"] == "map_generic"
    assert result["raw"]["schema"] == "development_generic_map_pixels_v1"
    assert result["raw"]["map_reader_status"] == "OBSERVED"
    assert result["raw"]["roi_xywh_native"] == [19, 43, 461, 432]
    assert result["map_candidates"]
    assert result["raw"]["map_name_candidates"] == []
    assert result["raw"]["zone_candidates"] == []
    assert all(c["ownership"] == "UNKNOWN" for c in result["map_candidates"])
    assert all(c["map_position_norm"] is None for c in result["map_candidates"])
    assert result["raw"]["formal_outputs"] == 0


def test_normalized_roi_scales_without_source_or_time_input(tmp_path):
    reader, _ = observer(tmp_path)
    image = np.zeros((720, 1280, 3), np.uint8)
    cv2.circle(image, (100, 100), 6, (0, 255, 255), 2)
    result = reader.inspect(image)
    assert result["raw"]["roi_xywh_native"] == [13, 29, 307, 288]
    assert result["raw"]["map_reader_status"] == "OBSERVED"
    assert result["map_candidates"]


def test_identity_config_and_unmatched_aspect_fail_closed(tmp_path):
    reader, config = observer(tmp_path)
    config.write_text(
        json.dumps(
            {"layout": json.loads(config.read_text(encoding="utf-8"))["layout"], "source_id": "x"}
        ),
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="only an existing HUD layout"):
        GenericMapObserver(config)
    result = reader.inspect(np.zeros((720, 1024, 3), np.uint8))
    assert result["raw"]["map_reader_status"] == "GEOMETRY_UNSUPPORTED"
    assert result["map_candidates"] == []
