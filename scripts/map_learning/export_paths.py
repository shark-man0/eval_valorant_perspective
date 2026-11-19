"""Export development-only Map paths with the selected CNN stage."""

from __future__ import annotations

import argparse
import math
from pathlib import Path

from runtime import DenseMarkerCNN, LearnedRecorderTracker, load_models

from valorant_ai_coach.temporal.map_direct_recorder import DirectRecorderTracker
from valorant_ai_coach.temporal.map_recorder_export import export_recorder_paths


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    for field in (
        "bundle-path",
        "frame-manifest",
        "policy-path",
        "catalog",
        "layout",
        "knowledge-asset-cache",
        "models-directory",
        "output",
    ):
        parser.add_argument(f"--{field}", required=True, type=Path)
    parser.add_argument("--zones-path", type=Path)
    parser.add_argument("--threshold", type=float, required=True)
    parser.add_argument("--learned-stage", choices=("marker", "both"), required=True)
    arguments = vars(parser.parse_args())
    threshold = arguments.pop("threshold")
    stage = arguments.pop("learned_stage")
    directory = arguments.pop("models_directory")
    if not math.isfinite(threshold) or not 0 < threshold <= 1:
        raise ValueError("Validation-calibrated probability threshold required")

    def create_tracker(binding, knowledge):
        models = load_models(directory, knowledge)
        detector = DenseMarkerCNN(models["marker"], threshold)
        if stage == "marker":
            return DirectRecorderTracker(detector, binding, knowledge)
        return LearnedRecorderTracker(
            detector, binding, knowledge, portrait_model=models["portrait"]
        )

    export_recorder_paths(
        **arguments,
        direct_detector="guided",
        direct_tracker_factory=create_tracker,
        recover_map_alignment=True,
        recover_native_flow=True,
    )


if __name__ == "__main__":
    main()
