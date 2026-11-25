"""Recover development Map positions through consecutive measured portrait candidates."""

from __future__ import annotations

import argparse
import hashlib
import math
from collections import Counter
from pathlib import Path

import cv2
import numpy as np

from valorant_ai_coach.temporal.evidence import digest, native_time
from valorant_ai_coach.temporal.map_direct_recorder import _portrait_feature, _rim_evidence
from valorant_ai_coach.temporal.map_path_quality import measure_path_quality
from valorant_ai_coach.temporal.map_recorder_knowledge import KnowledgeRecorderMap
from valorant_ai_coach.temporal.map_recorder_path import (
    build_recorder_paths,
    join_recorder_seconds,
    measure_operable_coverage,
    measured_native_edges,
    project_recorder_witness,
)
from valorant_ai_coach.temporal.map_reference_support import (
    atlas_distances_for,
    clearly_outside_atlas,
)
from valorant_ai_coach.temporal.public_map_pixels import PublicMapPixels
from valorant_ai_coach.temporal.replay import file_sha, read_json, write_private
from valorant_ai_coach.temporal.visual_state import selected_agent

if __package__:
    from .bracket_portraits import _camera, _fit, _reachable, _read_frame, _selection, load_inputs
    from .portrait_cohort import episodes, portrait_seconds
    from .temporal_portrait_model import pair_features, probability, read_model
else:
    from bracket_portraits import _camera, _fit, _reachable, _read_frame, _selection, load_inputs
    from portrait_cohort import episodes, portrait_seconds
    from temporal_portrait_model import pair_features, probability, read_model

METHOD = "development_map_temporal_portrait_track_v1"


def seed_points(incumbent, operable, *, limit=24):
    """Select a deterministic, time-spread gallery of direct incumbent points."""
    points = sorted(
        (
            p
            for seg in incumbent["segments"]
            for p in seg
            if p["kind"] == "selected"
            and p["sample"]["sample_sha256"] in operable
            and not p.get("alignment_recovery")
            and not p.get("portrait_anchor_sample_refs")
            and type(p.get("fit_residual_p95_reference_px")) in {float, int}
            and 0 <= p["fit_residual_p95_reference_px"] <= 6
        ),
        key=lambda p: native_time(p["sample"]),
    )
    indices = np.linspace(0, len(points) - 1, min(limit, len(points)), dtype=int)
    return [points[i] for i in indices]


def _read_fit(image, sample, projector, map_id, cache, counts):
    if cache is not None:
        key = digest(["exact_atlas_fit_v1", projector.fingerprint, sample["sample_sha256"]])
        path = cache / f"{key}.json"
        if path.is_file():
            record = read_json(path)
            raw = record["raw"]
            left, top, right, bottom = raw["roi_pixel_bounds"]
            roi = image[top:bottom, left:right]
            if (
                record["key"] != key
                or record["raw_sha256"] != digest(raw)
                or hashlib.sha256(roi.tobytes()).hexdigest() != raw["roi_pixel_sha256"]
            ):
                raise ValueError("Cached Map fit failed its exact pixel and content binding")
            candidate = raw["map_name_candidates"]
            if (
                len(candidate) == 1
                and candidate[0]["map_id"] == map_id
                and 0 <= candidate[0]["fit_residual_p95_reference_px"] <= 8
            ):
                counts["exact_fit_cache_hit"] += 1
                return raw
            counts["registration_unavailable"] += 1
            return None
    return _fit(image, projector, map_id, counts)


def _hero_evidence(image, point, knowledge, target, fit):
    left, top, right, bottom = fit["roi_pixel_bounds"]
    matrix = fit["map_name_candidates"][0]["reference_to_roi_homography_candidate"]
    x, y = np.asarray(matrix)[:2] @ [*point["map_reference_px"], 1.0]
    center = x, y = round(x) + left, round(y) + top
    radius = max(2, round(5 * image.shape[1] / 1920))
    if not (left + radius <= x < right - radius and top + radius <= y < bottom - radius):
        return None
    strengths = knowledge._portrait_scores(image, center)
    if (
        strengths is None
        or strengths[target] < 0.76
        or (strengths[target] - np.delete(strengths, target).max() < 0.045)
    ):
        return None
    feature = _portrait_feature(image, center)
    if feature is None:
        return None
    template = image[y - radius : y + radius + 1, x - radius : x + radius + 1]
    return cv2.cvtColor(cv2.resize(template, (11, 11)), cv2.COLOR_BGR2GRAY), feature


def proposals(roi, templates, scale):
    """Locate current pixels with appearance support from multiple source times."""
    native_gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
    gray = (
        native_gray
        if scale == 1
        else cv2.resize(
            native_gray,
            None,
            fx=1 / scale,
            fy=1 / scale,
            interpolation=cv2.INTER_AREA,
        )
    )
    if min(gray.shape) < 11:
        return
    fields = np.stack([cv2.matchTemplate(gray, patch, cv2.TM_CCOEFF_NORMED) for patch in templates])
    np.nan_to_num(fields, copy=False, nan=-1, neginf=-1, posinf=-1)
    joint = np.partition(fields, -2, axis=0)[-2]
    peaks = np.argwhere(joint == cv2.dilate(joint, np.ones((7, 7), np.uint8)))
    hsv = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV)
    extent = math.ceil(11 * scale)
    for i, j in sorted(peaks, key=lambda p: (-joint[*p], *p))[:14]:
        center = x, y = round(scale * (int(j) + 5)), round(scale * (int(i) + 5))
        if not (extent <= x < roi.shape[1] - extent and extent <= y < roi.shape[0] - extent):
            continue
        warm, pairs, rivals = _rim_evidence(hsv, x, y, scale)
        if warm >= 10 and pairs >= 3 and rivals <= 2:
            yield center, (warm, pairs, rivals)


def candidate_pixels(image, bounds, gallery, knowledge, target, model):
    left, top, right, bottom = bounds
    refs, templates, features = zip(*gallery, strict=True)
    features = np.asarray(features)
    for (x, y), shape in proposals(image[top:bottom, left:right], templates, image.shape[1] / 1920):
        center = x + left, y + top
        scores = knowledge._portrait_scores(image, center)
        if scores is None:
            continue
        confidence = float(scores[target])
        margin = confidence - float(np.delete(scores, target).max())
        if confidence < 0.73 or margin < 0.055:
            continue
        feature = _portrait_feature(image, center)
        if feature is None:
            continue
        scores = probability(
            pair_features(features, np.broadcast_to(feature, features.shape)), model
        )
        rank = np.argsort(-scores, kind="stable")[:2]
        if scores[rank[1]] >= model["threshold"]:
            yield (
                center,
                {
                    "source_gallery_samples": [refs[i] for i in rank],
                    "appearance_scores": scores[rank].tolist(),
                    "public_agent_score": confidence,
                    "public_agent_margin": margin,
                    "rim_sectors_pairs_rivals": shape,
                },
            )


def _linked(first, second):
    return (
        first["map_id"] == second["map_id"]
        and first["reference_sha256"] == second["reference_sha256"]
        and 0 < native_time(second["sample"]) - native_time(first["sample"]) <= 0.25
        and _reachable(first, second)
    )


def tracked_runs(layers):
    """Require locally unambiguous paths with at least three distinct measurements."""

    def spans(items, linked):
        counts = []
        last_candidates, last_scores = (), ()
        for current in items:
            current_scores = [
                1
                + max(
                    (
                        length
                        for old, length in zip(last_candidates, last_scores, strict=True)
                        if linked(old, p)
                    ),
                    default=0,
                )
                for p in current
            ]
            counts.append(current_scores)
            last_candidates, last_scores = current, current_scores
        return counts

    forward = spans(layers, _linked)
    backward = spans(reversed(layers), lambda a, b: _linked(b, a))[::-1]
    run = []
    for points, a, b in zip(layers, forward, backward, strict=True):
        viable = [p for p, left, right in zip(points, a, b, strict=True) if left + right - 1 >= 3]
        chosen = viable[0] if len(viable) == 1 else None
        if run and (chosen is None or not _linked(run[-1], chosen)):
            if len(run) >= 3:
                yield run
            run = []
        if chosen is not None:
            run.append(chosen)
    if len(run) >= 3:
        yield run


def replay(args):
    timeline, reference, adaptive, incumbent, operable, _, paths, rec = load_inputs(args)
    target_seconds = portrait_seconds(timeline, incumbent, reference, adaptive)
    targets = {key for refs in target_seconds.values() for key in refs}
    model_sha = file_sha(args.model)
    model = read_model(args.model, rec.physical_match_id)
    if file_sha(args.model) != model_sha:
        raise ValueError("Association model changed during load")
    knowledge = KnowledgeRecorderMap.load(args.asset_cache, args.map_catalog)
    projector = PublicMapPixels(
        args.map_catalog,
        args.layout,
        verified_references=knowledge.map_references,
    )
    binding = reference["recording_agent_uuid_binding"]
    if (
        not binding
        or binding != adaptive["recording_agent_uuid_binding"]
        or binding["source_sha256"] != rec.source_sha256
        or binding["qualified"] is not False
        or projector.fingerprint != reference["map_catalog_fingerprint"]
        or any(r["game_knowledge"] != knowledge.provenance for r in (reference, adaptive))
    ):
        raise ValueError("Existing Agent, public appearance, and atlas bindings required")
    identity = binding["uuid"]
    target = knowledge._uuids.index(identity)
    map_id = reference["recording_map_uuid"]
    assets = projector.bindings["asset_sha256s"]
    atlas = atlas_distances_for(args.map_catalog, map_id, assets[map_id], knowledge.map_references)
    frames = timeline["native_frames"]
    counts = Counter()
    gallery = []
    for point in seed_points(incumbent, operable):
        if point["map_id"] != map_id or point["reference_sha256"] != assets[map_id]:
            continue
        key = point["sample"]["sample_sha256"]
        frame = frames[key]
        if _camera(frame, [timeline["observations"][i] for i in frame["observation_ids"]]) is None:
            continue
        image = _read_frame(frame, paths[key], args.pixel_overrides, counts)
        if image is None:
            continue
        fit = _read_fit(image, frame["sample"], projector, map_id, args.alignment_cache, counts)
        if fit is None:
            continue
        evidence = _hero_evidence(image, point, knowledge, target, fit)
        if evidence is None or any(np.array_equal(evidence[0], old[1]) for old in gallery):
            continue
        gallery.append((key, *evidence))
    counts["gallery_measurements"] = len(gallery)
    recovered, traces = [], {}
    for camera, scope in episodes(timeline, operable):
        if len(gallery) < 2 or not targets.intersection(scope):
            continue
        layers, details = [], {}
        track = digest([METHOD, scope[0], camera, identity])
        for key in scope:
            current = []
            layers.append(current)
            if key not in targets:
                continue
            frame = frames[key]
            name = selected_agent(
                (frame.get("viewed_identity") or {}).get("viewed_agent_candidates", [])
            )
            viewed = knowledge._catalog.agent(name) if name else None
            if viewed is not None and viewed.uuid != identity:
                counts["hud_agent_conflict"] += 1
                continue
            image = _read_frame(frame, paths[key], args.pixel_overrides, counts)
            if image is None:
                continue
            counts["examined_targets"] += 1
            bounds = projector.layout.normalized_roi("minimap_normal").pixel_bounds(
                image.shape[1],
                image.shape[0],
            )
            pixels = list(candidate_pixels(image, bounds, gallery, knowledge, target, model))
            if not pixels:
                continue
            fit = _read_fit(image, frame["sample"], projector, map_id, args.alignment_cache, counts)
            if fit is None:
                continue
            for center, evidence in pixels:
                pool = [{"center_frame_px": list(center), "proposal_kind": METHOD}]
                selected = _selection(key, center, identity, 1, track, pool)
                point = project_recorder_witness(
                    image,
                    frame["sample"],
                    pool,
                    selected,
                    fit,
                    reference_sha256s=assets,
                )
                if point is not None and not clearly_outside_atlas(
                    atlas, point["map_reference_px"]
                ):
                    current.append(point)
                    details[id(point)] = {**evidence, "center_frame_px": list(center)}
        for run in tracked_runs(layers):
            for count, point in enumerate(run, start=1):
                point["support_count"] = count
            segments = build_recorder_paths(iter(run))["segments"]
            recovered.extend(segments)
            for measured, original in zip(segments[0], run, strict=True):
                key = measured["sample"]["sample_sha256"]
                traces[key] = {
                    **details[id(original)],
                    "position_sha256": digest(measured),
                    "model_receipt_sha256": model_sha,
                    "method": METHOD,
                    "camera_witness_sha256": camera,
                    "timeline_observation_ids": frames[key]["observation_ids"],
                }
    merged = {
        **incumbent,
        "segments": sorted(
            [*incumbent["segments"], *recovered],
            key=lambda s: native_time(s[0]["sample"]),
        ),
    }
    rows = join_recorder_seconds(merged, timeline)
    before_edges = measured_native_edges(incumbent)
    if measured_native_edges(merged) != before_edges | measured_native_edges(
        {"segments": recovered}
    ):
        raise ValueError("Only measured consecutive links may be added")
    return {
        **merged,
        "second_rows": rows,
        "operable_coverage": measure_operable_coverage(merged, timeline["seconds"], rows, operable),
        "path_quality": measure_path_quality(merged, timeline["seconds"], rows, operable),
        "temporal_portrait_replay": {
            "method": METHOD,
            "model_sha256": model_sha,
            "counts": dict(counts),
            "target_seconds": len(target_seconds),
            "target_frames": len(targets),
            "added_evidence": traces,
            "input_sha256s": {
                name: file_sha(getattr(args, name))
                for name in ("bundle", "reference", "adaptive", "incumbent", "manifest")
            },
        },
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for arg in (
        "recording-catalog",
        "bundle",
        "manifest",
        "reference",
        "adaptive",
        "incumbent",
        "asset-cache",
        "map-catalog",
        "layout",
        "model",
        "output",
    ):
        parser.add_argument(f"--{arg}", type=Path, required=True)
    parser.add_argument("--recording-id", required=True)
    parser.add_argument("--pixel-overrides", type=Path)
    parser.add_argument("--alignment-cache", type=Path)
    args = parser.parse_args()
    if args.output.exists() or any((p / ".git").exists() for p in args.output.resolve().parents):
        raise ValueError("Choose a new private output outside Git")
    cv2.setNumThreads(1)
    write_private(args.output, replay(args))


if __name__ == "__main__":
    main()
