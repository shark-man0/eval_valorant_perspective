"""Same-observation forward/offline controls; labels are read after prediction.

Reports only exact reviewed points. Unreviewed frames, absent event GT and
unconfigured Map readers remain unscored rather than negative examples.
"""

from __future__ import annotations

import argparse
import gc
from collections import Counter
from pathlib import Path
from typing import Any

from .evidence import is_sha, native_time
from .game import DOMAINS, DevelopmentGameTimeline
from .match import frame_observations
from .replay import SourcePolicy, file_sha, read_json, write_private

MODES = {
    "legacy_offline": {},
    "forward": {"forward_only": True},
    "offline_transition_brackets": {"mark_round_transition_gaps": True},
}


def compare_modes(
    *, policy_path: Path, input_path: Path, output: Path, reviews: list[Path]
) -> dict[str, Any]:
    if output.exists() or any((p / ".git").exists() for p in output.resolve().parents):
        raise ValueError("New private comparison directory required")
    policy = SourcePolicy(read_json(policy_path))
    data = read_json(input_path)
    rows = data.get("observations")
    if rows is None:
        producer = data["reader_fingerprint"]
        rows = [
            row
            for r in data["records"]
            for row in frame_observations(r["measurement"], r["sample"], producer)
        ]
    for row in rows:
        policy.admit(row["sample"])
    output.mkdir(parents=True, mode=0o700)
    predictions: dict[str, dict[str, Any]] = {}
    summaries: dict[str, Any] = {}
    for mode, config in MODES.items():
        engine = DevelopmentGameTimeline(
            fuse_exact_native_evidence=True,
            forward_only=config.get("forward_only", False),
            mark_round_transition_gaps=config.get("mark_round_transition_gaps", False),
        )
        for row in rows:
            engine.add(row)
        result = engine.rebuild()
        predictions[mode] = {
            f["sample"]["sample_sha256"]: {
                "sample": f["sample"],
                **{d: f[d] for d in ("round", "life", "camera")},
            }
            for f in result["frames"]
        }
        by_source: dict[str, Any] = {}
        for source in sorted({r["source_id"] for r in result["seconds"]}):
            seconds = [r for r in result["seconds"] if r["source_id"] == source]
            frames = [r for r in result["frames"] if r["sample"]["source_id"] == source]
            bins: dict[int, list[dict[str, Any]]] = {}
            for f in frames:
                bins.setdefault(int(native_time(f["sample"]) // 1), []).append(f)
            by_source[source] = {
                "native_points": len(frames),
                "second_rows": len(seconds),
                "video_observed_second_bins": sum(s["observation_present"] for s in seconds),
                "video_unobserved_second_bins": sum(not s["observation_present"] for s in seconds),
                "UNKNOWN_second_bins": {
                    d: sum(s[d]["value"] == "UNKNOWN" for s in seconds)
                    for d in ("round", "life", "camera")
                },
                "inferred_only_known_second_bins": {
                    d: sum(
                        s[d]["value"] != "UNKNOWN"
                        and not any(
                            f[d]["origin"] == "observation_projection"
                            for f in bins.get(s["second"], [])
                        )
                        for s in seconds
                    )
                    for d in ("round", "life", "camera")
                },
                "state_counts": {
                    d: dict(Counter(f[d]["value"] for f in frames))
                    for d in ("round", "life", "camera")
                },
                "correct_round_start": None,
                "false_round_start": None,
                "missed_round_start": None,
                "correct_round_end": None,
                "false_round_end": None,
                "missed_round_end": None,
                "internal_boundary_error": None,
                "Map_role_accuracy": None,
                "population_accuracy": None,
            }
        summaries[mode] = {"matches": by_source, "formal_outputs": result["formal_outputs"]}
        write_private(output / f"{mode}_predictions_PRIVATE.json", predictions[mode])
        del engine, result
        gc.collect()
    # No review content can affect any prediction above.
    review_records = [r for p in reviews for r in read_json(p)["records"]]
    unique: dict[tuple[str, str], dict[str, Any]] = {}
    for label in review_records:
        key = label.get("sample_sha256", label.get("sample", {}).get("sample_sha256"))
        domain, value = label["domain"], label["value"]
        if domain not in DOMAINS or value not in DOMAINS[domain]:
            raise ValueError("Known reviewed state domain and value required")
        if (
            label.get("origin") != "human_exact_frame"
            or not is_sha(label.get("review_sha256"))
            or not is_sha(key)
        ):
            raise ValueError("Independent human exact-frame response required")
        identity = (key, domain)
        if identity in unique and unique[identity]["value"] != value:
            raise ValueError("Conflicting reviews cannot be silently selected")
        unique[identity] = label
    review_records = list(unique.values())
    evaluation: dict[str, Any] = {}
    baseline = predictions["legacy_offline"]
    for mode, predicted in predictions.items():
        by_source_counts: dict[str, Counter[str]] = {}
        excluded = 0
        for label in review_records:
            key = label.get("sample_sha256", label.get("sample", {}).get("sample_sha256"))
            domain, value = label["domain"], label["value"]
            if domain not in {"round", "life", "camera"}:
                raise ValueError("Explicit reviewed state domain required")
            if label.get("origin") != "human_exact_frame" or not label.get("review_sha256"):
                raise ValueError("Independent human exact-frame response required")
            row = predicted.get(key)
            if row is None or value == "UNKNOWN":
                excluded += 1
                continue
            policy.admit(row["sample"])
            counts = by_source_counts.setdefault(row["sample"]["source_id"], Counter())
            actual = row[domain]["value"]
            kind = (
                "correct"
                if actual == value
                else "abstained"
                if actual == "UNKNOWN"
                else "incorrect"
            )
            counts[f"{domain}_{kind}"] += 1
            counts[f"{domain}_reviewed"] += 1
            counts["previous_correct_lost"] += int(
                baseline[key][domain]["value"] == value and actual != value
            )
            counts["wrong_SELF_attribution_at_reviewed_point"] += int(
                domain == "camera" and value != "SELF" and actual == "SELF"
            )
        evaluation[mode] = {
            "matches": {s: dict(v) for s, v in by_source_counts.items()},
            "excluded_unknown_or_unavailable": excluded,
            "population_accuracy": None,
        }
    report = {
        "version": "development_shared_mode_comparison_v1",
        "input_sha256": file_sha(input_path),
        "policy_sha256": file_sha(policy_path),
        "engine_sha256": file_sha(Path(__file__).with_name("game.py")),
        "predictions_sealed_before_review_read": True,
        "review_sha256s": {str(p): file_sha(p) for p in reviews},
        "modes": summaries,
        "exact_point_evaluation": evaluation,
        "unreviewed_not_negative": True,
        "formal_outputs": 0,
        "strict_qualification": "NOT_EVALUATED",
        "recognizer_adopted": False,
    }
    write_private(output / "comparison_PRIVATE.json", report)
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--policy", type=Path, required=True)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--review", type=Path, action="append", default=[])
    args = parser.parse_args()
    compare_modes(
        policy_path=args.policy, input_path=args.input, output=args.output, reviews=args.review
    )


if __name__ == "__main__":
    main()
