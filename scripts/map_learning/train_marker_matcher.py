"""Learn marker-pair appearance from exact TRAIN tracklets and separated rivals."""

from __future__ import annotations

import argparse
import math
from fractions import Fraction
from pathlib import Path

import cv2
import numpy as np

from valorant_ai_coach.recordings.catalog import RecordingCatalog
from valorant_ai_coach.temporal.evidence import native_time
from valorant_ai_coach.temporal.replay import file_sha, read_json, write_private

if __package__:
    from .long_marker_ownership import FEATURES, MATCH_SCHEMA, pair_features
    from .marker_tracks import _appearance
    from .replay_marker_tracks import _read
else:
    from long_marker_ownership import FEATURES, MATCH_SCHEMA, pair_features
    from marker_tracks import _appearance
    from replay_marker_tracks import _read


def bound(receipt):
    path = Path(receipt["path"])
    if file_sha(path) != receipt["sha256"]:
        raise ValueError("Frozen TRAIN evidence changed")
    return read_json(path)


def track_examples(row, source, pixels):
    report = bound(row["candidate"])
    detector = bound(row["anonymous_observations"])
    paths = {
        entry["sample"]["sample_sha256"]: Path(entry["path"])
        for entry in bound(source["artifacts"]["native_frame_manifest"])["frames"]
    }
    frames = detector["frames"]
    traces = report["multi_marker_replay"]
    selected = {
        p["sample"]["sample_sha256"]: p["sample"]
        for segment in report["segments"]
        for p in segment
        if p["sample"]["sample_sha256"] in traces["added_evidence"]
    }
    appearance = {}

    def read_candidates(ref):
        sample = selected[ref]
        image = _read(sample, paths[ref], pixels)
        if image is None:
            raise ValueError("Bound TRAIN pair pixels are missing")
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        scale = gray.shape[1] / 1920
        return {
            tuple(c["center_frame_px"]): _appearance(gray, *c["center_frame_px"], scale)
            for c in frames[ref]
        }

    examples = []
    for track_id, track in traces["track_evidence"].items():
        for first, second in zip(track["measurements"], track["measurements"][1:], strict=False):
            a, b = first[0], second[0]
            if a not in selected or b not in selected:
                continue
            if any(traces["added_evidence"][ref]["track"] != track_id for ref in (a, b)):
                continue
            one, two = selected[a], selected[b]
            if one["native_pixel_sha256"] == two["native_pixel_sha256"] or not 0 < native_time(
                two
            ) - native_time(one) <= Fraction(1, 4):
                continue
            rivals = [
                c
                for c in frames[b]
                if c["ring_sectors"] >= 14
                and math.dist(c["center_frame_px"], second[1:3])
                >= 20 * two["frame_size_px"][0] / 1920
            ]
            if not rivals:
                continue
            for ref in (a, b):
                if ref not in appearance:
                    appearance[ref] = read_candidates(ref)
            start = appearance[a][tuple(first[1:3])]
            next_ = appearance[b][tuple(second[1:3])]
            same_palette = [c for c in rivals if c["palette"] == second[-1]]
            alternatives = [
                pair_features(start, appearance[b][tuple(c["center_frame_px"])])
                for c in same_palette or rivals
            ]
            examples.append((pair_features(start, next_), max(alternatives, key=lambda f: f[0])))
    return np.asarray(examples)


def fit(groups):
    # Paired discrimination removes the per-match nuisance intercept.
    differences = [p[:, 0] - p[:, 1] for p in groups]
    x = np.concatenate(differences)
    weights = np.concatenate([np.full(len(g), 1 / (len(groups) * len(g))) for g in differences])
    beta = np.zeros(x.shape[1])
    for _ in range(200):
        error = 1 / (1 + np.exp(np.clip(x @ beta, -30, 30)))
        beta += 0.15 * (x.T @ (weights * error) - 0.025 * beta)
    return beta


def controls(data, weights, cutoff):
    scores = data @ weights
    return {
        "pairs": len(data),
        "positives_ranked_above_rival": int((scores[:, 0] > scores[:, 1]).sum()),
        "positive_accepts": int((scores[:, 0] >= cutoff).sum()),
        "rival_accepts": int((scores[:, 1] >= cutoff).sum()),
    }


def run(portfolio_path, overrides, output):
    portfolio = read_json(portfolio_path)
    if (
        portfolio.get("schema") != "development_map_multi_marker_portfolio_v1"
        or portfolio.get("formal_outputs") != 0
    ):
        raise ValueError("Exact development track portfolio required")
    handoff = bound(portfolio["source"])
    catalog = RecordingCatalog(Path(handoff["catalog"]))
    sources = {row["index"]: row for row in handoff["recordings"]}
    training = {}
    for row in portfolio["recordings"]:
        if row["split"] != "TRAIN":
            continue
        source = sources[row["index"]]
        catalog.guard([source["recording_id"]], "training")
        rec = catalog.state.recordings[source["recording_id"]]
        if rec.split != "DEVELOPMENT" or rec.learning.get("split") != "TRAIN":
            raise ValueError("Only physically distinct development TRAIN inputs are allowed")
        if rec.source_sha256 != source["source_sha256"] or rec.physical_match_id in training:
            raise ValueError("Duplicate or different physical recording")
        pairs = track_examples(row, source, overrides / str(row["index"]) / "pixels")
        if len(pairs):
            training[rec.physical_match_id] = pairs
    if len(training) < 4:
        raise ValueError("At least four distinct TRAIN matches with pairs required")
    if any((p / ".git").exists() for p in (output, *output.parents)):
        raise ValueError("Profiles are private development evidence")
    output.mkdir(mode=0o700, parents=True, exist_ok=False)
    # Repeat on TRAIN only, using a different physical match for calibration.
    results = []
    for hold in (*training, None):
        eligible = [(k, v) for k, v in training.items() if k != hold]
        stop = eligible[-1:]
        fit_groups = eligible[:-1]
        weights = fit([v for _, v in fit_groups])
        cal = np.concatenate([v for _, v in stop])
        cutoff = float(np.nextafter(float((cal[:, 1] @ weights).max()), np.inf))
        equals = np.asarray([1, 0, 0, 0, 0, 0], dtype=float)
        base_cutoff = float(np.nextafter(float(cal[:, 1, 0].max()), np.inf))
        name = "unseen.json" if hold is None else f"held_{hold}.json"
        if Path(name).name != name:
            raise ValueError("Invalid physical-match identity")
        write_private(
            output / name,
            {
                "schema": MATCH_SCHEMA,
                "formal_outputs": 0,
                "feature_order": list(FEATURES),
                "weights": weights.tolist(),
                "cutoff": cutoff,
                "holdout_match": hold,
                "training_matches": [k for k, _ in fit_groups],
                "calibration_matches": [k for k, _ in stop],
                "source_receipts": [file_sha(portfolio_path)],
            },
        )
        if hold is not None:
            results.append(
                {
                    "held_profile": name,
                    "learned": controls(training[hold], weights, cutoff),
                    "cosine": controls(training[hold], equals, base_cutoff),
                }
            )
    review = {
        "held_controls": results,
        "physical_matches_with_pairs": len(training),
        "formal_outputs": 0,
    }
    write_private(output / "controls_PRIVATE.json", review)
    return review


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for option in ("portfolio", "pixel-override-root", "output"):
        parser.add_argument(f"--{option}", type=Path, required=True)
    args = parser.parse_args()
    cv2.setNumThreads(1)
    run(args.portfolio, args.pixel_override_root, args.output)


if __name__ == "__main__":
    main()
