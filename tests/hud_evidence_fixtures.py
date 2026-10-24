"""Shared synthetic data only; no observer or lifecycle module dependency."""
from pathlib import Path

import cv2
import numpy as np


def read(text, confidence=.95):
    return {"value": text, "confidence": confidence}

def frame(tick, *, score=(1, 4), word=None, timer="0:06", epoch="a", geometry=True):
    return {"source_id": "dev", "source_sha256": "a" * 64, "tick": tick,
            "time_base": "1/60", "epoch": epoch, "expected_step_ticks": 1,
            "encoded_sha256": f"{tick + 1:064x}", "pixel_sha256": f"{tick + 2:064x}",
            "geometry_consistent": geometry,
            "ally_score": read(None if score is None else str(score[0])),
            "enemy_score": read(None if score is None else str(score[1])),
            "result": read(word), "timer": read(timer), "buy_phase": False}

def transition():
    return [frame(0), frame(1), frame(2, score=(2, 4)),
            frame(3, score=(2, 4), word="THRIFTY"),
            frame(4, score=(2, 4)),  # reject/unknown stays unknown
            frame(5, score=(2, 4), word="THRIFTY")]

def score_profile(tmp_path: Path):
    import json
    spec = {"kind": "strict_score_glyphs", "glyph_threshold": .90,
            "glyph_margin": .04, "comparison_preprocessing": "gaussian3x3_v1",
            "foreground_preprocessing": "unsupported_old_experiment",
            "templates": {str(i): f"{i}.png" for i in range(10)}}
    for i in range(10):
        im = np.zeros((32, 24), np.uint8)
        cv2.putText(im, str(i), (1, 24), 0, .8, 255, 2)
        cv2.imwrite(str(tmp_path / f"{i}.png"), im)
    path = tmp_path / "profile.json"
    path.write_text(json.dumps({"schema_version": "1.0",
                               "readers": {n: spec for n in ["ally_score", "enemy_score"]}}),
                    encoding="utf-8")
    return path

def chain():
    rows = transition()
    rows += [frame(t, score=(2, 4), timer=None) for t in range(6, 42)]
    for tick, timer, buy in [(9, "0:00", False), (10, "0:30", True),
                             (11, "0:29", True), (38, "0:02", True),
                             (39, "0:01", True), (40, "1:40", False),
                             (41, "1:39", False)]:
        rows[tick]["timer"]["value"] = timer
        rows[tick]["buy_phase"] = buy
    for f in rows:
        f["time_base"] = "1/1"
    return rows
