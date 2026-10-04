"""Offline reproduction of a global-detail veto on an observable local slot."""

import json
import sys
from pathlib import Path

import cv2
import numpy as np

from scripts.diagnose_spectator_obscuration import main
from valorant_ai_coach.hud.layout import HudLayout


def test_global_low_detail_does_not_measure_the_separate_icon_roi(tmp_path, monkeypatch):
    layout_path = tmp_path / "hud_layout.json"
    layout_path.write_bytes(Path("config/hud_layout_1080p_v3.json").read_bytes())
    layout_path.with_suffix(".templates.json").write_text(
        json.dumps(
            {
                "schema_version": "1.0",
                "spectator_icon_detector": {
                    "version": 1,
                    "roi": "spectator_icon",
                    "method": "fixed_slot_structure_v1",
                },
            }
        ),
        encoding="utf-8",
    )
    layout = HudLayout.load(layout_path)
    frame = np.full((1080, 1920, 3), 70, np.uint8)
    x1, y1, x2, y2 = layout.normalized_roi("spectator_icon").pixel_bounds(1920, 1080)
    cv2.rectangle(frame, (x1 + 8, y1 + 12), (x2 - 9, y2 - 13), (160, 160, 160), 1)
    manifest = []
    for index in range(3):
        path = tmp_path / f"native_{index}.png"
        assert cv2.imwrite(str(path), frame)
        manifest.append({"frame_path": str(path), "time_sec": index / 10})
    private = tmp_path / "private.json"
    private.write_text(json.dumps(manifest), encoding="utf-8")
    output = tmp_path / "aggregate.json"
    monkeypatch.setattr(sys, "argv", ["diagnostic", str(private), str(layout_path), str(output)])
    main()
    text = output.read_text(encoding="utf-8")
    result = json.loads(text)
    assert result["before"] == {"icon_absent": 2, "icon_roi_obscured": 1}
    assert result["after"] == {"icon_absent": 3}
    assert "gate_estimates" not in result
    assert result["diagnostic_only"] is True
    assert "frame_path" not in text and str(tmp_path) not in text
    assert "time_sec" not in text
