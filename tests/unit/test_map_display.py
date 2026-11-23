import json

import cv2
import numpy as np
import pytest

from valorant_ai_coach.temporal.map_display import load_map_display, prepare_map_display
from valorant_ai_coach.temporal.replay import file_sha


def test_display_uses_only_observed_public_atlas_and_detects_changed_bytes(tmp_path):
    source = tmp_path / "atlas.png"
    assert cv2.imwrite(str(source), np.full((12, 24, 3), 144, dtype=np.uint8))
    sha = file_sha(source)
    catalog = tmp_path / "catalog.json"
    catalog.write_text(json.dumps({
        "maps": [{"id": "map", "name": "Named Map", "reference": source.name}],
    }), encoding="utf-8")
    polygon = [[1, 1], [3, 1], [3, 4]]
    zones = tmp_path / "zones.json"
    zones.write_text(json.dumps({
        "maps": [{"map_id": "map", "reference_sha256": sha, "polygons": {"A": polygon}}],
    }), encoding="utf-8")
    point = {"map_id": "map", "reference_sha256": sha, "map_reference_px": [2, 2]}
    result = tmp_path / "map_result.json"
    result.write_text(json.dumps({
        "formal_outputs": 0, "qualified": False, "zone_catalog_sha256": file_sha(zones),
        "segments": [[point]],
    }), encoding="utf-8")
    manifest = prepare_map_display(result, catalog, zones)
    rows = [{"recorder_map_observations": [point]}]
    records, atlases = load_map_display(manifest, result, rows)
    assert records[0]["size"] == [24, 12]
    assert records[0]["zones"] == {"A": polygon}
    assert atlases == {sha: source.read_bytes()}
    with pytest.raises(ValueError, match="Unobserved"):
        load_map_display(manifest, result, [])
    (tmp_path / "map_atlases" / f"{sha}.png").write_bytes(b"wrong")
    with pytest.raises(ValueError, match="hash mismatch"):
        load_map_display(manifest, result, rows)
