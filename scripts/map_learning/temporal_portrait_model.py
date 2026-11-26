"""Learn an Agent-agnostic, recording-disjoint portrait association score."""

from __future__ import annotations

import argparse
import hashlib
from collections import defaultdict
from fractions import Fraction
from pathlib import Path

import cv2
import numpy as np

from valorant_ai_coach.recordings.catalog import RecordingCatalog
from valorant_ai_coach.temporal.evidence import is_sha, native_time, source_scope
from valorant_ai_coach.temporal.replay import file_sha, read_json, write_private

if __package__:
    from .crop_lineage import load_crop_lineage
    from .portrait_similarity import _features, region_similarity
else:
    from crop_lineage import load_crop_lineage
    from portrait_similarity import _features, region_similarity

SCHEMA = "development_map_temporal_portrait_association_v1"
FEATURES = ("cosine", "upper_left", "upper_right", "center", "lower_left", "lower_right")


def pair_features(a, b):
    return np.concatenate(
        [
            np.sum(a * b, axis=-1, keepdims=True),
            region_similarity(a, b),
        ],
        axis=-1,
    )


def _logistic(value):
    return 1 / (1 + np.exp(-np.clip(value, -40, 40)))


def probability(features, model):
    return _logistic(np.asarray(features) @ np.asarray(model["weights"]) + model["bias"])


def _verified_hard_positives(lineage, positive, entry):
    if entry is None:
        return set()
    if entry["positive_weak_crops"] != len(positive):
        raise ValueError("The hard index must address the exact positive archive")
    indices = set()
    for item in entry["hard_crops"]:
        i = item["crop_index"]
        if type(i) is not int or not 0 <= i < len(positive) or i in indices:
            raise ValueError("Unique hard crop index required")
        trace = lineage["rows"]["positive"][i]
        if (
            item["role_label"] != trace["label"]
            or item["sample_sha256"] != trace["sample_sha256"]
            or hashlib.sha256(positive[i].tobytes()).hexdigest() != item["crop_sha256"]
            or not 0 <= item["old_target_score"] <= 1
            or item["reason"] not in {"target_under_threshold", "other_agent_ranked_first"}
        ):
            raise ValueError("Hard crop lineage differs from the bound TRAIN archive")
        indices.add(i)
    return indices


def load_corpus(catalog, receipt, hard, *, excluded=()):
    if receipt["schema"] != "map_cnn_training_receipt_v2":
        raise ValueError("Exact v2 development Map crop lineage is required")
    lookup = {row["recording_id"]: row for row in hard.get("records", ())}
    if len(lookup) != len(hard.get("records", ())) or (lookup and hard["formal_outputs"] != 0):
        raise ValueError("Expected a distinct development hard crop index")
    if lookup.keys() - {row["recording_id"] for row in receipt["recordings"]}:
        raise ValueError("Hard crops must belong to the training receipt")
    groups = []
    physical = set(excluded)
    for record in receipt["recordings"]:
        rid = record["recording_id"]
        catalog.guard([rid], "training")
        rec = catalog.state.recordings[rid]
        if (
            rec.split != "DEVELOPMENT"
            or rec.learning.get("split") != "TRAIN"
            or rec.physical_match_id in physical
            or rec.source_sha256 != record["source_sha256"]
        ):
            raise ValueError("Distinct catalogued DEVELOPMENT TRAIN matches required")
        physical.add(rec.physical_match_id)
        path = Path(record["patches"])
        if file_sha(path) != record["sha256"]:
            raise ValueError("Map TRAIN archive digest mismatch")
        with np.load(path, allow_pickle=False) as arrays:
            lineage = load_crop_lineage(
                Path(record["lineage"]),
                record["lineage_sha256"],
                rec.source_sha256,
                arrays,
            )
            hard_indices = _verified_hard_positives(lineage, arrays["positive"], lookup.get(rid))
            features = {
                kind: _features(arrays[kind]) for kind in ("positive", "negative", "background")
            }
        negatives = defaultdict(list)
        for kind in ("negative", "background"):
            for feature, detail in zip(features[kind], lineage["rows"][kind], strict=True):
                if feature is not None:
                    negatives[detail["sample_sha256"]].append(feature)
        entries = []
        for i, (feature, trace) in enumerate(
            zip(
                features["positive"],
                lineage["rows"]["positive"],
                strict=True,
            )
        ):
            if feature is not None:
                key = trace["sample_sha256"]
                entries.append(
                    (lineage["samples"][key], feature, i in hard_indices, negatives[key])
                )
        entries.sort(key=lambda item: native_time(item[0]))
        if len(entries) < 2:
            raise ValueError("Each training recording needs distinct observed portrait crops")
        groups.append(
            {
                "recording_id": rid,
                "physical_match": rec.physical_match_id,
                "agent": record["recorder_agent_uuid"],
                "items": entries,
                "hard_source_count": len(hard_indices),
            }
        )
    return groups


def pair_examples(groups, *, contrasts=()):
    rng = np.random.default_rng(119)
    result = []
    for group in groups:
        items = group["items"]
        other = [
            item[1]
            for g in (*groups, *contrasts)
            if g["agent"] != group["agent"]
            for item in g["items"]
        ]
        if not other:
            raise ValueError("At least two Agents are required for contrast")
        references, positives, nearby, cross, hard = [], [], [], [], []
        for i, (sample, current, difficult, controls) in enumerate(items):
            adjacent = []
            for other_i in (i - 1, i + 1):
                if 0 <= other_i < len(items):
                    candidate = items[other_i][0]
                    elapsed = abs(native_time(candidate) - native_time(sample))
                    if (
                        0 < elapsed <= Fraction(4, 5)
                        and source_scope(candidate) == source_scope(sample)
                        and candidate["native_pixel_sha256"] != sample["native_pixel_sha256"]
                    ):
                        adjacent.append(items[other_i][1])
            if not adjacent or not controls:
                continue
            exemplar = adjacent[rng.integers(len(adjacent))]
            reference_controls = np.asarray(controls)
            negatives = pair_features(
                np.broadcast_to(exemplar, reference_controls.shape), reference_controls
            )
            references.append(exemplar)
            positives.append(current)
            nearby.append(reference_controls[negatives[:, 0].argmax()])
            cross.append(other[rng.integers(len(other))])
            hard.append(difficult)
        if not positives:
            raise ValueError("No sound adjacent crop pairs and within-frame controls")
        ref = np.asarray(references)
        result.append(
            {
                "positive": pair_features(ref, np.asarray(positives)),
                "within_frame": pair_features(ref, np.asarray(nearby)),
                "other_agent": pair_features(ref, np.asarray(cross)),
                "hard": np.asarray(hard, dtype=bool),
            }
        )
    return result


def fit(groups, *, use_hard):
    samples, labels, weights = [], [], []
    examples = pair_examples(groups)
    for data in examples:
        pos = data["positive"]
        weights_positive = 1 + (data["hard"] if use_hard else np.zeros(len(pos), dtype=bool))
        samples.extend((pos, data["within_frame"], data["other_agent"]))
        labels.extend((np.ones(len(pos)), np.zeros(len(pos)), np.zeros(len(pos))))
        weights.extend(
            (
                0.5 * weights_positive / weights_positive.sum(),
                np.full(len(pos), 0.25 / len(pos)),
                np.full(len(pos), 0.25 / len(pos)),
            )
        )
    x = np.column_stack((np.concatenate(samples), np.ones(sum(len(y) for y in labels))))
    y = np.concatenate(labels)
    w = np.concatenate(weights) / len(examples)
    regularizer = np.diag([0.002] * len(FEATURES) + [0.0])
    beta = np.zeros(x.shape[1])
    for _ in range(24):
        prediction = _logistic(x @ beta)
        loss_gradient = x.T @ (w * (prediction - y)) + regularizer @ beta
        curvature = w * prediction * (1 - prediction)
        beta -= np.linalg.solve((x.T * curvature) @ x + regularizer, loss_gradient)
    return {
        "schema": SCHEMA,
        "formal_outputs": 0,
        "feature_order": list(FEATURES),
        "weights": beta[:-1].tolist(),
        "bias": float(beta[-1]),
        "training_physical_matches": sorted(g["physical_match"] for g in groups),
        "training_recordings": len(groups),
        "hard_weighted": use_hard,
        "hard_source_crops": sum(g["hard_source_count"] for g in groups),
        "hard_pairs": sum(int(e["hard"].sum()) for e in examples),
        "temporal_pairs": sum(len(e["positive"]) for e in examples),
    }


def score_examples(examples, model, cutoff):
    result = {
        "pairs": 0,
        "hard_pairs": 0,
        "ranked_first": 0,
        "hard_ranked_first": 0,
        "positive_accepted": 0,
        "within_frame_accepted": 0,
        "other_agent_accepted": 0,
    }
    for data in examples:
        scores = [probability(data[k], model) for k in ("positive", "within_frame", "other_agent")]
        win = scores[0] > np.maximum(scores[1], scores[2])
        result["pairs"] += len(win)
        result["hard_pairs"] += int(data["hard"].sum())
        result["ranked_first"] += int(win.sum())
        result["hard_ranked_first"] += int((win & data["hard"]).sum())
        for name, score in zip(("positive", "within_frame", "other_agent"), scores, strict=True):
            result[f"{name}_accepted"] += int((score >= cutoff).sum())
    return result


def read_model(path, evaluation_match):
    model = read_json(path)
    used = model["training_physical_matches"] + model["calibration_physical_matches"]
    if (
        model["schema"] != SCHEMA
        or model["formal_outputs"] != 0
        or model["feature_order"] != list(FEATURES)
        or len(set(used)) != len(used)
        or evaluation_match in used
        or len(model["weights"]) != len(FEATURES)
        or not np.isfinite([*model["weights"], model["bias"], model["threshold"]]).all()
        or not 0 < model["threshold"] <= 1
        or not all(
            is_sha(model[key])
            for key in (
                "training_receipt_sha256",
                "hard_index_sha256",
                "calibration_receipt_sha256",
            )
        )
    ):
        raise ValueError("A finite association model from disjoint DEVELOPMENT TRAIN is required")
    return model


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for arg in (
        "recording-catalog",
        "training-receipt",
        "hard-index",
        "calibration-receipt",
        "control-receipt",
        "output-directory",
    ):
        parser.add_argument(f"--{arg}", type=Path, required=True)
    parser.add_argument("--leave-one-recording-out", action="store_true")
    args = parser.parse_args()
    dest = args.output_directory.resolve()
    if any((p / ".git").exists() for p in (dest, *dest.parents)):
        raise ValueError("Use a private output directory outside Git")
    dest.mkdir(parents=True, exist_ok=False, mode=0o700)
    cv2.setNumThreads(1)
    catalog = RecordingCatalog(args.recording_catalog)
    train = load_corpus(catalog, read_json(args.training_receipt), read_json(args.hard_index))
    calibration = load_corpus(
        catalog,
        read_json(args.calibration_receipt),
        {},
        excluded=[g["physical_match"] for g in train],
    )
    control = load_corpus(
        catalog,
        read_json(args.control_receipt),
        {},
        excluded=[g["physical_match"] for g in train + calibration],
    )
    cal_examples, controls = pair_examples(calibration, contrasts=train), pair_examples(control)
    provenance = {
        "calibration_physical_matches": sorted(g["physical_match"] for g in calibration),
        "training_receipt_sha256": file_sha(args.training_receipt),
        "hard_index_sha256": file_sha(args.hard_index),
        "calibration_receipt_sha256": file_sha(args.calibration_receipt),
    }

    def calibrated(model, groups):
        negatives = np.concatenate(
            [probability(c[key], model) for c in groups for key in ("within_frame", "other_agent")]
        )
        return {
            **model,
            **provenance,
            "threshold": float(np.nextafter(negatives.max(), 1.0)),
        }, len(negatives)

    curve = {}
    sizes = sorted({n for n in (2, 4, 8, len(train)) if 2 <= n <= len(train)})
    with_contrast = [n for n in sizes if len({g["agent"] for g in train[:n]}) >= 2]
    for size, with_hard in [(n, True) for n in with_contrast] + [(len(train), False)]:
        name = f"{size}_with_hard" if with_hard else f"{size}_without_hard"
        model, negatives = calibrated(fit(train[:size], use_hard=with_hard), cal_examples)
        cutoff = model["threshold"]
        stats = score_examples(controls, model, cutoff)
        curve[name] = {
            **stats,
            "training_pairs": model["temporal_pairs"],
            "hard_source_crops": model["hard_source_crops"],
            "hard_pairs_used": model["hard_pairs"] if with_hard else 0,
            "calibration_negatives": negatives,
        }
        write_private(dest / f"{name}.json", model)
    cosine, _ = calibrated(
        {
            "schema": SCHEMA,
            "formal_outputs": 0,
            "feature_order": list(FEATURES),
            "training_physical_matches": [],
            "weights": [1, 0, 0, 0, 0, 0],
            "bias": 0,
        },
        cal_examples,
    )
    curve["cosine"] = score_examples(controls, cosine, cosine["threshold"])
    write_private(dest / "cosine.json", cosine)
    if args.leave_one_recording_out:
        folds = {}
        for index, held in enumerate(train):
            subset = [g for g in train if g["physical_match"] != held["physical_match"]]
            model, _ = calibrated(
                fit(subset, use_hard=True),
                pair_examples(calibration, contrasts=subset),
            )
            name = f"fold_{index + 1}.json"
            write_private(dest / name, model)
            folds[held["physical_match"]] = name
        write_private(dest / "folds.json", folds)
    write_private(dest / "learning_curve.json", {"controls": curve, "formal_outputs": 0})
    print(curve, flush=True)


if __name__ == "__main__":
    main()
