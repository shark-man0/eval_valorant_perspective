"""Saved component replay only: no video, readers, GT, or qualification issuer.

Input directory is the retained private new-source-development tree. No raw
observations are exported. Historical UI plus current static readers is explicitly
mixed-version diagnosis, never a current native pipeline or independent holdout.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from copy import deepcopy
from fractions import Fraction
from pathlib import Path
from time import perf_counter

from scripts.diagnostics.clock_type_end_study import Sample, replay_samples
from valorant_ai_coach.hud.unedited_ui_end import UneditedUiEndTracker

WINDOWS = ("LOST", "WON", "numeric")


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def compose(root: Path, window: str) -> tuple[list[Sample], list[dict]]:
    def read(name: str):
        return json.loads((root / name).read_text(encoding="utf-8"))

    scores = {
        (x["pool"], x["tick"], x["field"]): x for x in read("production-separated-score/rows.json")
    }
    timers = {(x["window"], x["tick"]): x for x in read("timer-rejection-development/rows.json")}
    clocks = {
        (x["window"], x["tick"]): x
        for x in read("clock-type-chromatic-development/full-development-rows.json")
    }
    historical = read(f"development-timing/{window}-result/raw-rows.json")
    samples, baseline = [], []
    for original in historical:
        row = deepcopy(original)
        tick, pixel = row["source_pts_ticks"], row["source_pixel_sha256"]
        timer, clock = timers[window, tick], clocks[window, tick]
        ally, enemy = (scores[window, tick, field] for field in ("ally_score", "enemy_score"))
        assert all(x["pixel_sha256"] == pixel for x in (timer, clock, ally, enemy))
        scan = row["system_measurements"]["native_ui"]
        values = row["system_observation"]["values"]
        quality = row["system_observation"]["quality"]["roi_confidence"]
        values["round_time_remaining_display"] = timer["value"]
        values["round_time_remaining_sec"] = (
            None
            if timer["value"] is None
            else int(timer["value"].split(":")[0]) * 60 + int(timer["value"].split(":")[1])
        )
        quality["round_timer_value"] = timer["confidence"]
        for component, field in ((ally, "score_ally"), (enemy, "score_enemy")):
            values[field] = None if component["value"] is None else int(component["value"])
            quality[field + "_value"] = component["confidence"]
        row["system_evidence"] = {
            "assured_phase_scan_valid": scan["phase_scan_valid"],
            "assured_phase_present": scan["phase_present"],
            "assured_phase_confidence": scan["phase_confidence"],
            "assured_round_result_present": scan["round_result_matched"],
            "assured_round_result_confidence": scan["round_result_confidence"],
        }
        baseline.append(row)
        predicted = clock["prediction"]
        kind = predicted["kind"] or ("numeric" if timer["value"] is not None else "unknown")
        score = (values["score_ally"], values["score_enemy"])
        samples.append(
            Sample(
                row["source_video_sha256"],
                row["source_epoch"],
                tick,
                Fraction(row["source_time_base"]),
                pixel,
                kind,
                predicted["literal"] if predicted["kind"] else timer["value"],
                predicted["confidence"] if predicted["kind"] else timer["confidence"],
                None if None in score else score,
                min(ally["confidence"], enemy["confidence"]),
                # A template nonmatch is NOT positive caption absence.
                "complete" if scan["round_result_matched"] else "unknown",
                scan["round_result_confidence"],
                "buy" if scan["phase_present"] else "unknown",
                "unknown",
                bool(scan.get("content_jump") or scan.get("discontinuity")),
            )
        )
    return samples, baseline


def baseline_patterns(rows: list[dict]) -> list[dict]:
    tracker, previous, patterns = UneditedUiEndTracker(native_step_ticks=256), None, []
    for row in deepcopy(rows):
        scan = row["system_measurements"]["native_ui"]
        broken = bool(scan.get("content_jump") or scan.get("discontinuity"))
        if previous is not None:
            broken |= any(
                row[k] != previous[k]
                for k in ("source_epoch", "source_time_base", "source_video_sha256")
            )
            broken |= row["source_pts_ticks"] - previous["source_pts_ticks"] != 256
            broken |= row["source_pixel_sha256"] == previous["source_pixel_sha256"]
        if broken:
            tracker.reset()
        elif (
            decision := tracker.advance(row, phase_scan_valid=scan["phase_scan_valid"])
        ) is not None:
            patterns.append(
                {
                    "diagnostic_boundary_sec": decision.time_sec,
                    "diagnostic_confirmation_sec": decision.attributes["evidence_provenance"][
                        "confirmation_pts_sec"
                    ],
                    "confidence": decision.confidence,
                    "formal_release": False,
                }
            )
        previous = row
    return patterns


def run(root: Path) -> dict:
    paths = [
        root / "production-separated-score/rows.json",
        root / "timer-rejection-development/rows.json",
        root / "clock-type-chromatic-development/full-development-rows.json",
        root / "clock-type-chromatic-development/full-development-result.json",
        root / "clock-type-chromatic-development/prototype.py",
        *(root / f"development-timing/{w}-result/raw-rows.json" for w in WINDOWS),
        Path(__file__),
        Path(__file__).with_name("clock_type_end_study.py"),
    ]
    frozen = {
        str(p.relative_to(root))
        if p.is_relative_to(root)
        else "scripts/diagnostics/" + p.name: digest(p)
        for p in paths
    }
    started = perf_counter()
    results = []
    for window in WINDOWS:
        samples, baseline = compose(root, window)
        typed = replay_samples(samples, 256)  # Intentionally no fabricated ActiveContext.
        old = baseline_patterns(baseline)
        assert typed == replay_samples(samples, 256)
        assert old == baseline_patterns(baseline)
        results.append(
            {
                "window": window,
                "frames": len(samples),
                "first_tick": samples[0].tick,
                "last_tick": samples[-1].tick,
                "source_sha256": samples[0].source,
                "epoch": samples[0].epoch,
                "time_base": str(samples[0].base),
                "baseline_collector_patterns": old,
                "typed_contract": typed,
                "missing_prerequisites": [
                    "same_epoch_active_Start",
                    "positive_caption_absence",
                    "admissible_global_context",
                ],
            }
        )
    assert all(
        digest(p)
        == frozen[
            str(p.relative_to(root)) if p.is_relative_to(root) else "scripts/diagnostics/" + p.name
        ]
        for p in paths
    )
    return {
        "scope": (
            "mixed-version saved-component development diagnosis; "
            "no current native or independent lifecycle claim"
        ),
        "decision": "DEFER_UNQUALIFIED_EXPERIMENT_STOPPED",
        "historical_UI_code": "58117f2bfe84f072c37f0989846145d7fad7a3a29d807ba55d9be9a6136a4f68",
        "current_static_component_code": (
            "414f9d9d3f1841cfe50fdf9732bb78e1bfa35aa4382eb7c0d90d194ed81155fa"
        ),
        "clock_reader_metadata": json.loads(
            (root / "clock-type-chromatic-development/full-development-result.json").read_text(
                encoding="utf-8"
            )
        )
        | {"input_sha256": "see original retained metadata"},
        "input_sha256": frozen,
        "results": results,
        "deterministic_twice": True,
        "input_hashes_unchanged": True,
        "elapsed_sec": perf_counter() - started,
        "new_decoder_calls": 0,
        "new_reader_calls": 0,
        "new_PNG_bytes": 0,
        "formal_events": 0,
        "owned_facts": 0,
        "qualification_issued": False,
        "full_E2E_run": False,
        "source_epoch_splice": False,
        "independent_data_established": False,
        "production_hookup": False,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-root", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    result = run(args.input_root)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
