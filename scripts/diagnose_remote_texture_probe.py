"""Offline sufficiency probe: synthetic texture is not gameplay remote UI."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import cv2
import numpy as np

from valorant_ai_coach.hud.classifier import HudStateClassifier
from valorant_ai_coach.hud.readers import _astra_scores


def texture_cases() -> dict[str, np.ndarray]:
    """Generate known synthetic color/shape texture without reference assets."""
    solid = np.full((400, 400, 3), (255, 15, 255), dtype=np.uint8)
    texture = solid.copy()
    for center in ((100, 100), (290, 120)):
        cv2.circle(texture, center, 43, (255, 255, 255), 4)
    for y in range(235, 400, 10):
        for x in range(0, 400, 10):
            if ((y - 235) // 10 + x // 10) % 2 == 0:
                texture[y : y + 10, x : x + 10] = 0
    return {"solid_purple_control": solid, "purple_circle_checker_texture": texture}


def probe() -> dict[str, object]:
    """Exercise the current proxy and classifier; no scene/state oracle is passed."""
    classifier = HudStateClassifier()
    rows = []
    for name, image in texture_cases().items():
        scores = _astra_scores(image)
        classified = classifier.classify(
            {
                "astral_geometry": scores["geometry"] >= 0.90,
                "purple_palette": scores["palette"] >= 0.90,
                "astra_hand_interface": scores["interface"] >= 0.90,
                "remote_confidence": min(scores.values()),
            }
        )
        rows.append(
            {
                "case": name,
                "shape_hwc": list(image.shape),
                "decoded_bgr_sha256": hashlib.sha256(image.tobytes()).hexdigest(),
                "scores": scores,
                "classified_state": classified.primary_state,
                "classified_subtype": classified.remote_view_type,
                "player_hud_valid": classified.player_specific_hud_valid,
            }
        )
    return {
        "diagnostic_only": True,
        "scope": "Synthetic texture sufficiency counterexample; no gameplay UI or labels.",
        "limitations": "Not a real-data false-positive rate or independent holdout.",
        "threshold_unchanged": 0.90,
        "opencv_version": cv2.__version__,
        "cases": rows,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = probe()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("x", encoding="utf-8") as stream:
        json.dump(result, stream, indent=2)
        stream.write("\n")
    print(json.dumps(result))


if __name__ == "__main__":
    main()
