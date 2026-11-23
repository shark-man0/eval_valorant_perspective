"""Run a private Map analysis plan for explicitly registered DEVELOPMENT recordings."""

from __future__ import annotations

import argparse
import os
from pathlib import Path
from subprocess import CalledProcessError

from compare_runs import compare
from run_recording import _run

from valorant_ai_coach.recordings.admission import resolve_catalog
from valorant_ai_coach.temporal.replay import file_sha, read_json, write_private

_PATH_OPTIONS = {
    "hud-config", "spectator-label", "map-catalog", "layout", "asset-cache", "zones-path",
    "models-directory", "camera-hint", "companion-models-directory", "acquisition", "frame-cache",
}
_SHARED = _PATH_OPTIONS - {"acquisition", "frame-cache"} | {
    "threshold", "companion-threshold", "jobs", "portrait-mode", "hwaccel",
}
_FLAGS = {
    "compare-without-portraits", "no-shared-alignment-cache", "screen-atlas-void",
    "strict-recovery-tracking", "lossless-webp",
}
_REQUIRED = {
    "hud-config", "spectator-label", "map-catalog", "layout", "asset-cache", "zones-path",
    "models-directory", "threshold",
}
_RECORD = {
    "recording_id", "acquisition", "frame-cache", "baseline_run", "prepare_weak_crops",
}


def _path(value: str, root: Path) -> Path:
    if not isinstance(value, str) or not value:
        raise ValueError("A path in the Map batch plan is missing")
    return (root / value).resolve()


def run_batch(plan_path: Path, output: Path) -> bool:
    plan_path, output = plan_path.resolve(), output.resolve()
    content_sha = file_sha(plan_path)
    plan = read_json(plan_path)
    if plan.get("schema") != "development_map_batch_v1":
        raise ValueError("A development Map batch plan is required")
    root = plan_path.parent
    catalog_path = _path(plan["recording_catalog"], root)
    catalog = resolve_catalog(catalog_path)
    if catalog is None:
        raise ValueError("A registered recording catalog is required")
    common = plan["run_options"]
    flags = plan.get("run_flags", [])
    recordings = plan["recordings"]
    if (not _REQUIRED <= common.keys() <= _SHARED or set(flags) - _FLAGS
            or len(set(flags)) != len(flags) or not recordings):
        raise ValueError("Batch requires known run options and at least one recording")
    options = {
        name: _path(value, root) if name in _PATH_OPTIONS else value
        for name, value in common.items()
    }
    ids = [row["recording_id"] for row in recordings]
    if len(set(ids)) != len(ids):
        raise ValueError("Recordings must be unique in the batch")
    for row in recordings:
        rec = catalog.state.recordings.get(row["recording_id"])
        if row.keys() - _RECORD or rec is None or rec.split != "DEVELOPMENT":
            raise ValueError("Batch entries must name registered DEVELOPMENT recordings")
        if type(row.get("prepare_weak_crops", False)) is not bool:
            raise ValueError("prepare_weak_crops must be a boolean")
        catalog.guard([rec.recording_id], "development_analysis")
        if row.get("prepare_weak_crops", False):
            if rec.learning.get("split") != "TRAIN" or row.get("baseline_run"):
                raise ValueError("Weak crops require a registered TRAIN source outside regression")
            catalog.guard([rec.recording_id], "training")

    # Admission and plan validation finish before a run opens any source media.
    policy = output / "source_policy_PRIVATE.json"
    write_private(policy, {"catalog": str(catalog_path), "allowed_recording_ids": ids})
    completed = []
    for index, row in enumerate(recordings, start=1):
        rec = catalog.state.recordings[row["recording_id"]]
        run_dir = output / f"recording_{index:03d}"
        entry = {
            "recording_id": rec.recording_id, "physical_match_id": rec.physical_match_id,
            "source_sha256": rec.source_sha256,
        }
        stage = "analysis"
        try:
            recording_options = {
                name: _path(row[name], root) for name in ("acquisition", "frame-cache")
                if name in row
            }
            training = row.get("prepare_weak_crops", False)
            catalog.record_exposure(rec.recording_id, "development_use", "Map analysis batch")
            run_flags = tuple(f"--{name}" for name in flags)
            if training:
                run_flags += ("--training-candidates",)
            _run("run_recording.py", {
                **options, **recording_options, "source-sha256": rec.source_sha256,
                "policy-path": policy, "output": run_dir,
            }, run_flags)
            receipt = run_dir / "run_PRIVATE.json"
            entry["run_sha256"] = file_sha(receipt)
            if training:
                stage = "weak_crops"
                _run("prepare_crops.py", {
                    "recording-catalog": catalog_path, "source-policy": policy,
                    "replay-report": run_dir / "map_reference_PRIVATE.json",
                    "native-manifest": run_dir / "timeline/map_frames_PRIVATE.json",
                    "layout": options["layout"], "output-directory": run_dir / "weak_crops",
                })
                entry["training_record_sha256"] = file_sha(
                    run_dir / "weak_crops/training_record_PRIVATE.json"
                )
            if row.get("baseline_run"):
                stage = "regression"
                regression = run_dir / "regression_PRIVATE.json"
                write_private(regression, compare(_path(row["baseline_run"], root), receipt))
                entry["regression_sha256"] = file_sha(regression)
        except (CalledProcessError, OSError, ValueError) as exc:
            entry.update(status="failed", stage=stage, error_type=type(exc).__name__)
        else:
            entry["status"] = "complete"
        completed.append(entry)
    write_private(output / "batch_PRIVATE.json", {
        "schema": "development_map_batch_result_v1", "plan_sha256": content_sha,
        "recordings": completed, "formal_outputs": 0,
    })
    return all(row["status"] == "complete" for row in completed)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plan", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    os.umask(0o077)
    if not run_batch(args.plan, args.output):
        raise SystemExit("One or more Map batch stages failed; see the private receipt")


if __name__ == "__main__":
    main()
