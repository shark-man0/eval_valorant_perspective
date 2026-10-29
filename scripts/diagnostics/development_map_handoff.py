"""Replay PRIVATE Map observations with optional externally supplied snapshots.

No video discovery, HUD reading, game-state inference or Production output.
Input is JSON {rows: [{image_path, sample, pool, ui, appearance, geometry,
reference_context_fingerprint, context?, continuity?}]}. Images must be exact
native samples. Keep both input and output outside public Git.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import cv2

from valorant_ai_coach.visual.development_map_features import owner_tracking_features
from valorant_ai_coach.visual.development_map_handoff import (
    DevelopmentMapStateConsumer,
    aggregate_map_seconds,
    make_map_observation,
)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        parser.error("Choose a new PRIVATE output; existing evidence is never overwritten")
    plan = json.loads(args.input.read_text(encoding="utf-8"))
    records = []
    observations = []
    tracker = DevelopmentMapStateConsumer()
    for row in plan["rows"]:
        frame = cv2.imread(str(row["image_path"]))
        if frame is None:
            raise ValueError("Exact native image unavailable")
        observation = make_map_observation(
            **{
                k: row[k]
                for k in (
                    "sample",
                    "pool",
                    "ui",
                    "appearance",
                    "geometry",
                    "reference_context_fingerprint",
                )
            }
        )
        features = owner_tracking_features(frame, row["sample"], row["pool"])
        records.append(
            tracker.observe(
                observation, features, context=row.get("context"), continuity=row.get("continuity")
            )
        )
        observations.append(observation)
    result = {
        "map_observations": observations,
        "records": records,
        "seconds": aggregate_map_seconds(records),
        "qualification": "development_only",
        "ownership": "UNKNOWN",
        "formal_outputs": 0,
    }
    args.output.write_text(
        json.dumps(result, ensure_ascii=False, allow_nan=False) + "\n", encoding="utf-8"
    )


if __name__ == "__main__":
    main()
