"""Reproduce diagnostic pseudo-view LOPO ranking on private native timelines."""

from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from fractions import Fraction
from pathlib import Path
from typing import Any, cast

from .development_view_reranker import (
    PseudoExample,
    fit_pseudo_view_reranker,
    limited_current_ui_pseudo_label,
    margin_features,
    temporal_hp_correspondence,
)
from .evidence import native_time
from .replay import file_sha, read_json, write_private


def run(manifest: Path, output: Path) -> dict[str, Any]:
    if output.exists():
        raise ValueError("New private experiment output required")
    if any((p / ".git").exists() for p in output.resolve().parents):
        raise ValueError("Private model output outside Git required")
    entries = read_json(manifest)["records"]
    matches = {e["physical_match"] for e in entries}
    if len(matches) != len(entries) or len(matches) < 2:
        raise ValueError("Separate declared physical matches required")
    examples, diagnostics, bindings = [], [], {}
    for entry in entries:
        path = Path(entry["native_timeline"])
        if file_sha(path) != entry["native_sha256"]:
            raise ValueError("Frozen native timeline changed")
        bindings[str(path)] = entry["native_sha256"]
        timeline = read_json(path)
        tail_ids = {
            r["sample"]["sample_sha256"]
            for r in timeline.get("return_display_tail_projection_history", [])
        }
        groups: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
        for row in timeline["observations"]:
            if row["context"].get("unqualified_view_model") is True:
                sample = row["sample"]
                groups[(sample["source_sha256"], sample["native_epoch"])].append(row)
        for rows in groups.values():
            rows.sort(key=lambda r: (native_time(r["sample"]), r["observation_id"]))
            for index, row in enumerate(rows):

                def neighbor(
                    offset: int,
                    *,
                    index: int = index,
                    rows: list[dict[str, Any]] = rows,
                    row: dict[str, Any] = row,
                ) -> dict[str, Any] | None:
                    other_index = index + offset
                    if not 0 <= other_index < len(rows):
                        return None
                    other = rows[other_index]
                    gap = abs(native_time(other["sample"]) - native_time(row["sample"]))
                    if not 0 < gap <= Fraction(2) or any(
                        r.get("continuity", {}).get("decode_ok") is False
                        or r.get("continuity", {}).get("source_discontinuity") is True
                        for r in (row, other)
                    ):
                        return None
                    return cast(dict[str, Any], other["raw"])

                previous, following = neighbor(-1), neighbor(1)
                features = margin_features(row["raw"], previous=previous, following=following)
                pseudo = limited_current_ui_pseudo_label(row)
                if pseudo is not None:
                    examples.append(PseudoExample(entry["physical_match"], features, pseudo))
                diagnostics.append(
                    {
                        "physical_match": entry["physical_match"],
                        "sample": row["sample"],
                        "features": features,
                        "pseudo": pseudo,
                        "tail": row["sample"]["sample_sha256"] in tail_ids,
                        "hp": temporal_hp_correspondence(
                            row["raw"], previous=previous, following=following
                        ),
                    }
                )
    folds = []
    for heldout in sorted(matches):
        model = fit_pseudo_view_reranker(
            examples, train_matches=matches - {heldout}, heldout_matches={heldout}
        )
        held = [r for r in diagnostics if r["physical_match"] == heldout]
        counts: dict[int, Counter[str]] = {0: Counter(), 1: Counter()}
        for row in held:
            row["score"] = model.score(row["features"])["score"]
            label = row["pseudo"]
            if label is not None:
                counts[label]["total"] += 1
                counts[label]["agreement"] += (row["score"] >= 0.5) == bool(label)
        recalls = [c["agreement"] / c["total"] for c in counts.values() if c["total"]]
        folds.append(
            {
                "heldout_physical_match": heldout,
                "train_matches": model.train_matches,
                "train_positive": model.positive_count,
                "train_negative": model.negative_count,
                "heldout_pseudo": {str(k): dict(v) for k, v in counts.items()},
                "pseudo_balanced_agreement": sum(recalls) / len(recalls)
                if len(recalls) == 2
                else None,
                "private_weights": model.weights,
                "private_intercept": model.intercept,
            }
        )
    tails = [r for r in diagnostics if r["tail"]]
    result = {
        "method": "limited_current_ui_pseudo_label_balanced_l2_logistic_v1",
        "manifest_sha256": file_sha(manifest),
        "native_bindings": bindings,
        "code_sha256": file_sha(Path(__file__)),
        "folds": folds,
        "pseudo_total": dict(Counter(e.pseudo_label for e in examples)),
        "tail_candidates": len(tails),
        "tail_score_at_least_half": sum(r["score"] >= 0.5 for r in tails),
        "tail_repeated_hp": sum(r["hp"]["repeated_current_hp"] for r in tails),
        "state_applied": False,
        "human_accuracy": None,
        "pseudo_agreement_is_not_accuracy": True,
        "formal_outputs": 0,
    }
    write_private(output, result)
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = run(args.manifest, args.output)
    print(json.dumps({k: v for k, v in result.items() if k not in {"native_bindings", "folds"}}))


if __name__ == "__main__":
    main()
