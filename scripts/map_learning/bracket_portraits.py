"""Recheck weak development Map portraits between independently measured markers."""

from __future__ import annotations

import argparse
import math
from collections import Counter
from dataclasses import dataclass
from fractions import Fraction
from pathlib import Path

import cv2
import numpy as np

from valorant_ai_coach.recordings.catalog import RecordingCatalog
from valorant_ai_coach.temporal.evidence import (
    digest,
    freeze_native_sample,
    native_time,
    source_scope,
)
from valorant_ai_coach.temporal.map_direct_recorder import (
    _portrait_feature,
    _rim_evidence,
    measured_direct_view,
)
from valorant_ai_coach.temporal.map_path_quality import measure_path_quality
from valorant_ai_coach.temporal.map_recorder_export import _load_native_image, _pixels_match
from valorant_ai_coach.temporal.map_recorder_knowledge import KnowledgeRecorderMap
from valorant_ai_coach.temporal.map_recorder_path import (
    ReferenceZones,
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
from valorant_ai_coach.temporal.map_timeline_report import load_map_timeline
from valorant_ai_coach.temporal.public_map_pixels import PublicMapPixels
from valorant_ai_coach.temporal.replay import file_sha, read_json, write_private
from valorant_ai_coach.temporal.visual_state import selected_agent

if __package__:
    from .portrait_similarity import read_metric, region_similarity
else:
    from portrait_similarity import read_metric, region_similarity

METHOD = "bracketed_portrait_v1"
MAX_SPAN = Fraction(4)
MAX_STEP = Fraction(1, 4)
BLOCKING_SIGNALS = frozenset(
    {
        "round_start",
        "round_end",
        "spectator",
        "remote",
        "downed",
        "death",
        "revival",
        "result",
        "intermission",
        "report",
    }
)


@dataclass(frozen=True)
class Bracket:
    left: str
    right: str
    targets: tuple[str, ...]
    view: str


def _camera(frame, observations):
    if any(BLOCKING_SIGNALS.intersection(row.get("signals", ())) for row in observations):
        return None
    if (frame.get("viewed_identity") or {}).get("agent_signature_relation") == "DIFFERENT":
        return None
    return measured_direct_view(frame, observations)


def _continuous(before, after):
    return (
        0 < native_time(after["sample"]) - native_time(before["sample"]) <= MAX_STEP
        and source_scope(before["sample"]) == source_scope(after["sample"])
        and before["sample"]["native_pixel_sha256"] != after["sample"]["native_pixel_sha256"]
        and after["continuity"].get("carry_allowed") is True
        and after["continuity"].get("confirmed_cut") is not True
        and all(
            before.get(field) == after.get(field)
            for field in (
                "round_token",
                "round_number",
                "self_view_round_token",
                "tracking_epoch",
            )
        )
        and before["round"].get("value") == after["round"].get("value")
    )


def find_brackets(timeline, incumbent, operable, unresolved):
    """Use the nearest directly registered incumbent markers and exact current view."""
    native = timeline["native_frames"]
    observations = timeline["observations"]
    points = {p["sample"]["sample_sha256"]: p for s in incumbent["segments"] for p in s}
    targets = {
        key
        for row, attached in zip(timeline["seconds"], incumbent["second_rows"], strict=True)
        if not attached["recorder_map_observations"] and set(row["sample_refs"]) <= operable
        for key in row["sample_refs"]
        if key in unresolved
    }
    refs = sorted(native, key=lambda k: native_time(native[k]["sample"]))
    anchor = previous = view = None
    pending = []
    result = []
    for key in refs:
        frame = native[key]
        if key not in operable:
            anchor = previous = view = None
            pending.clear()
            continue
        camera = _camera(frame, [observations[i] for i in frame["observation_ids"]])
        if (
            camera != view
            or camera is None
            or (previous is not None and not _continuous(native[previous], frame))
        ):
            anchor = None
            pending.clear()
        view, previous = camera, key
        if camera is None:
            continue
        point = points.get(key)
        if point is not None:
            if (
                point["kind"] != "selected"
                or point.get("alignment_recovery")
                or point.get("portrait_anchor_sample_refs")
            ):
                continue
            if (
                anchor is not None
                and len(pending) >= 2
                and (
                    native_time(frame["sample"]) - native_time(native[anchor]["sample"]) <= MAX_SPAN
                    and (points[anchor]["map_id"], points[anchor]["reference_sha256"])
                    == (point["map_id"], point["reference_sha256"])
                )
            ):
                result.append(Bracket(anchor, key, tuple(pending), camera))
            anchor = key
            pending.clear()
        elif anchor is not None:
            if native_time(frame["sample"]) - native_time(native[anchor]["sample"]) > MAX_SPAN:
                anchor = None
                pending.clear()
            elif key in targets:
                pending.append(key)
    return result


def load_inputs(args):
    rec_catalog = RecordingCatalog(args.recording_catalog)
    rec_catalog.guard([args.recording_id], "development_analysis")
    recording = rec_catalog.state.recordings[args.recording_id]
    if recording.split != "DEVELOPMENT":
        raise ValueError("An admitted DEVELOPMENT recording is required")
    timeline = read_json(args.bundle)
    if timeline["source"]["source_sha256"] != recording.source_sha256:
        raise ValueError("The timeline does not belong to the admitted recording")
    timeline_sha = file_sha(args.bundle)
    manifest_sha = file_sha(args.manifest)
    reference = read_json(args.reference)
    adaptive = read_json(args.adaptive)
    incumbent = read_json(args.incumbent)
    load_map_timeline(args.incumbent, args.bundle, timeline)
    for report in (reference, adaptive):
        if (
            report["formal_outputs"] != 0
            or report["qualified"] is not False
            or report["timeline_sha256"] != timeline_sha
            or report["frame_manifest_sha256"] != manifest_sha
        ):
            raise ValueError("Reference and adaptive replays must use the exact native inputs")
    if incumbent["reference_report_sha256"] != file_sha(args.reference):
        raise ValueError("The incumbent must be bound to the supplied reference replay")
    operable = set(reference["comparison_evidence"]["operable_sample_refs"])
    if not operable <= timeline["native_frames"].keys():
        raise ValueError("Operability evidence outside the timeline")
    unresolved = set(adaptive["comparison_evidence"]["unresolved_portrait_sample_refs"])
    if not unresolved <= operable:
        raise ValueError("Missing exact current view evidence for unresolved portraits")
    paths = {}
    for row in read_json(args.manifest)["frames"]:
        sample = freeze_native_sample(row["sample"])
        key = sample["sample_sha256"]
        if key in paths or sample != timeline["native_frames"].get(key, {}).get("sample"):
            raise ValueError("Native frame manifest differs from the timeline")
        paths[key] = Path(row["path"])
    if not operable <= paths.keys():
        raise ValueError("Native frame manifest is incomplete")
    return timeline, reference, adaptive, incumbent, operable, unresolved, paths, recording


def _read_frame(frame, path, override, counts):
    sample = frame["sample"]
    try:
        image = _load_native_image(sample, path)
    except FileNotFoundError:
        replacement = override / f"{sample['sample_sha256']}.png" if override else None
        try:
            data = replacement.read_bytes() if replacement is not None else None
        except FileNotFoundError:
            data = None
        if data is None:
            counts["missing_pixels"] += 1
            return None
        image = cv2.imdecode(np.frombuffer(data, np.uint8), cv2.IMREAD_COLOR)
    if image is None or not _pixels_match(image, sample):
        raise ValueError("Native decoded pixels differ from the bound sample")
    return image


def _fit(image, projector, map_id, counts):
    alignment = projector.inspect_exact(image)["raw"]
    fits = alignment["map_name_candidates"]
    if (
        len(fits) != 1
        or fits[0]["map_id"] != map_id
        or (fits[0]["fit_residual_p95_reference_px"] > 8)
    ):
        counts["registration_unavailable"] += 1
        return None
    return alignment


def _anchor_feature(image, point, projector, knowledge, target, counts):
    alignment = _fit(image, projector, point["map_id"], counts)
    if alignment is None:
        return None
    left, top, right, bottom = alignment["roi_pixel_bounds"]
    fit = alignment["map_name_candidates"][0]
    x, y = np.asarray(fit["reference_to_roi_homography_candidate"])[:2] @ [
        *point["map_reference_px"],
        1,
    ]
    center = (int(round(x)) + left, int(round(y)) + top)
    if not (left <= center[0] < right and top <= center[1] < bottom):
        return None
    scores = knowledge._portrait_scores(image, center)
    if (
        scores is None
        or scores[target] < 0.73
        or scores[target]
        - np.delete(
            scores,
            target,
        ).max()
        < 0.03
    ):
        counts["anchor_reference_unresolved"] += 1
        return None
    return _portrait_feature(image, center)


def _center_evidence(image, center, knowledge, target, features, metric, neighbor_support):
    feature = _portrait_feature(image, center)
    if feature is None:
        return None
    similarities = [
        float(feature @ anchor if metric is None else region_similarity(feature, anchor) @ metric)
        for anchor in features
    ]
    if min(similarities) < (0.67 if neighbor_support else 0.76):
        return None
    official = knowledge._portrait_scores(image, center)
    if official is None:
        return None
    external = float(official[target])
    margin = external - float(np.delete(official, target).max())
    strong = min(similarities) >= 0.76 and external >= 0.68 and margin >= 0.02
    if not strong and (not neighbor_support or external < 0.65 or margin < 0.025):
        return None
    return external, margin, similarities, strong


def _matches(
    image,
    roi,
    detector,
    knowledge,
    identity,
    features,
    score_portrait,
    metric,
    neighbor_support,
    counts,
):
    left, top, right, bottom = roi
    scale = image.shape[1] / 1920
    target = knowledge._uuids.index(identity)
    pixels = image[top:bottom, left:right]
    hsv = cv2.cvtColor(pixels, cv2.COLOR_BGR2HSV)
    peaks = detector.peaks(pixels, identity, scale=scale)
    result = []
    phase = max(1, round(scale))
    rim_extent = math.ceil(11 * scale)
    half = max(2, round(8 * scale))
    for peak in peaks:
        if peak.warm_sectors < 5 or peak.opposite_pairs < 1 or peak.chromatic_rivals > 5:
            continue
        x, y = peak.center[0] + left, peak.center[1] + top
        crop = image[y - half : y + half + 1, x - half : x + half + 1]
        if crop.shape[:2] != (2 * half + 1, 2 * half + 1):
            continue
        score = score_portrait(crop, target)
        if score >= 0.8:
            continue
        counts["weak_cnn_warm_peak"] += 1
        alternatives = []
        for dx, dy in (
            (0, 0),
            (-phase, 0),
            (phase, 0),
            (0, -phase),
            (0, phase),
            (-phase, -phase),
            (phase, phase),
            (phase, -phase),
            (-phase, phase),
        ):
            px, py = peak.center[0] + dx, peak.center[1] + dy
            if not (
                rim_extent <= px < right - left - rim_extent
                and rim_extent <= py < bottom - top - rim_extent
            ):
                continue
            warm, pairs, rivals = _rim_evidence(hsv, px, py, scale)
            if warm < 5 or pairs < 1 or rivals > 5:
                continue
            center = (x + dx, y + dy)
            evidence = _center_evidence(
                image,
                center,
                knowledge,
                target,
                features,
                metric,
                neighbor_support,
            )
            if evidence is None:
                continue
            external, margin, similarities, strong = evidence
            alternatives.append(
                (
                    center,
                    {
                        "marker_response": peak.response,
                        "warm_sectors": warm,
                        "opposite_pairs": pairs,
                        "rival_sectors": rivals,
                        "cnn_target_score_at_original_peak": score,
                        "external_target_score": external,
                        "external_agent_margin": margin,
                        "anchor_similarities": similarities,
                        "strong_current_portrait": strong,
                        "center_shift_frame_px": [dx, dy],
                    },
                )
            )
        if alternatives:
            counts["shape_and_current_portrait"] += 1
            result.append(max(alternatives, key=_rank_measurement))
    return result


def _selection(key, center, identity, count, anchor, pool):
    return {
        "contract": "development_map_recorder_selection_v1",
        "sample_sha256": key,
        "ordered_candidate_pool_digest": digest(pool),
        "support_candidate_index": 0,
        "support_center_frame_px": list(center),
        "support_count": count,
        "selection_status": "RESEARCH_SELECTED",
        "research_candidate_index": 0,
        "qualified": False,
        "position_authority": False,
        "selection_method": "knowledge_agent_uuid",
        "recorder_agent_uuid_candidate": identity,
        "track_anchor": anchor,
    }


def _reachable(before, after):
    dt = native_time(after["sample"]) - native_time(before["sample"])
    return 0 < dt <= MAX_SPAN and (
        math.dist(before["map_reference_px"], after["map_reference_px"]) <= 6 + 60 * float(dt)
    )


def _strong_isolated(left, point, right, details):
    """Allow a strongly corroborated current point without creating a native edge."""
    first, center, last = (p["map_reference_px"] for p in (left, point, right))
    excess = math.dist(first, center) + math.dist(center, last) - math.dist(first, last)
    return (
        native_time(right["sample"]) - native_time(left["sample"]) <= 2
        and excess <= 8
        and details["warm_sectors"] >= 10
        and details["opposite_pairs"] >= 3
        and details["rival_sectors"] <= 2
        and details["external_target_score"] >= 0.73
        and details["external_agent_margin"] >= 0.055
        and min(details["anchor_similarities"]) >= 0.83
    )


def _rank_measurement(measurement):
    details = measurement[1]
    return details["strong_current_portrait"], min(details["anchor_similarities"])


def _corroborated_groups(group):
    """Allow a weaker current portrait only immediately beside a strong one."""
    strong = {i for i, (_, details, _) in enumerate(group) if details["strong_current_portrait"]}
    current = []
    for i, measurement in enumerate(group):
        if strong.intersection((i - 1, i, i + 1)):
            current.append(measurement)
        else:
            if len(current) >= 2:
                yield current
            current = []
    if len(current) >= 2:
        yield current


def _prefer_unique(candidates, counts):
    if not candidates:
        return None
    found = sorted(candidates, key=_rank_measurement, reverse=True)
    if any(math.dist(found[0][0], item[0]) > 6 for item in found[1:]):
        counts["ambiguous_current_markers"] += 1
        return None
    return found[0]


def replay(args, inputs, brackets):
    from runtime import DenseMarkerCNN, image_tensor, load_models
    from torch import inference_mode, set_num_threads

    timeline, reference, adaptive, incumbent, operable, unresolved, paths, recording = inputs
    cv2.setNumThreads(1)
    set_num_threads(1)
    knowledge = KnowledgeRecorderMap.load(args.asset_cache, args.map_catalog)
    projector = PublicMapPixels(
        args.map_catalog,
        args.layout,
        verified_references=knowledge.map_references,
    )
    binding = reference["recording_agent_uuid_binding"]
    if (
        binding is None
        or not reference["recording_map_uuid"]
        or binding != adaptive["recording_agent_uuid_binding"]
        or binding.get("qualified") is not False
        or binding["source_sha256"] != timeline["source"]["source_sha256"]
    ):
        raise ValueError("A shared, exact development recorder binding is required")
    identity = binding["uuid"]
    map_id = reference["recording_map_uuid"]
    assets = projector.bindings["asset_sha256s"]
    if reference["map_catalog_fingerprint"] != projector.fingerprint:
        raise ValueError("The replay atlas and layout fingerprint differs")
    receipt = file_sha(args.models_directory / "training_summary_PRIVATE.json")
    if receipt != adaptive["experimental_model_receipts"]["portrait"] or (
        receipt != adaptive["experimental_model_receipts"]["marker"]
    ):
        raise ValueError("Replay requires the same marker and portrait model receipts")
    weights = load_models(args.models_directory, knowledge, receipt_sha256=receipt)
    detector = DenseMarkerCNN(weights["marker"], args.threshold)

    @inference_mode()
    def score_portrait(crop, target):
        values = weights["portrait"](image_tensor(cv2.resize(crop, (17, 17))))[0].softmax(dim=0)
        return float(values[target])

    metric, metric_sha = (
        read_metric(args.metric, recording.physical_match_id) if args.metric else (None, None)
    )
    if file_sha(args.zones) != reference["zone_catalog_sha256"]:
        raise ValueError("The Zone catalog differs from the reference replay")
    zones = [
        ReferenceZones(z["map_id"], z["reference_sha256"], z["polygons"])
        for z in read_json(args.zones)["maps"]
    ]
    void = atlas_distances_for(args.map_catalog, map_id, assets[map_id], knowledge.map_references)
    callouts = KnowledgeRecorderMap.callouts(args.asset_cache, args.map_catalog)
    native = timeline["native_frames"]
    points = {p["sample"]["sample_sha256"]: p for s in incumbent["segments"] for p in s}
    counts = Counter()
    evidence = {}
    isolated_controls = {}
    recovered = []

    for span in brackets:
        left_point, right_point = points[span.left], points[span.right]
        if (left_point["map_id"], left_point["reference_sha256"]) != (map_id, assets[map_id]):
            continue
        features = []
        for key in (span.left, span.right):
            image = _read_frame(native[key], paths[key], args.pixel_overrides, counts)
            feature = (
                None
                if image is None
                else _anchor_feature(
                    image,
                    points[key],
                    projector,
                    knowledge,
                    knowledge._uuids.index(
                        identity,
                    ),
                    counts,
                )
            )
            if feature is not None:
                features.append(feature)
        if len(features) != 2:
            continue
        anchor = digest([METHOD, span.left, span.right, identity])
        observations = []
        records = {}
        group = []
        for key in span.targets:
            frame = native[key]
            view = frame.get("viewed_identity") or {}
            name = selected_agent(view.get("viewed_agent_candidates", []))
            current = knowledge._catalog.agent(name) if name else None
            image = (
                None
                if current is not None and current.uuid != identity
                else _read_frame(
                    frame,
                    paths[key],
                    args.pixel_overrides,
                    counts,
                )
            )
            measurement = None
            if image is not None:
                bounds = projector.layout.normalized_roi("minimap_normal").pixel_bounds(
                    image.shape[1],
                    image.shape[0],
                )
                matches = _matches(
                    image,
                    bounds,
                    detector,
                    knowledge,
                    identity,
                    features,
                    score_portrait,
                    metric,
                    args.neighbor_support,
                    counts,
                )
                if matches:
                    alignment = _fit(image, projector, map_id, counts)
                    if alignment is not None:
                        viable = []
                        for center, details in matches:
                            pool = [{"center_frame_px": list(center), "proposal_kind": METHOD}]
                            sample = frame["sample"]
                            selection = _selection(key, center, identity, 1, anchor, pool)
                            point = project_recorder_witness(
                                image,
                                sample,
                                pool,
                                selection,
                                alignment,
                                reference_sha256s=assets,
                            )
                            if (
                                point is not None
                                and _reachable(left_point, point)
                                and _reachable(point, right_point)
                                and not clearly_outside_atlas(void, point["map_reference_px"])
                            ):
                                viable.append((center, details, point))
                        measurement = _prefer_unique(viable, counts)
            if group and (
                measurement is None
                or not _continuous(
                    native[group[-1][0]],
                    frame,
                )
                or not _reachable(group[-1][2], measurement[2])
            ):
                observations.append(group)
                group = []
            if measurement is not None:
                center, details, point = measurement
                group.append((key, details, point))
                records[key] = {"center_frame_px": list(center), **details}
        if group:
            observations.append(group)
        stable = [part for group in observations for part in _corroborated_groups(group)]
        selected_refs = {key for group in stable for key, _, _ in group}
        for group in observations:
            for key, details, point in group:
                if key in selected_refs or not details["strong_current_portrait"]:
                    continue
                if args.strong_isolated and _strong_isolated(
                    left_point, point, right_point, details
                ):
                    counts["independently_supported_isolated_point"] += 1
                    stable.append([(key, details, point)])
                else:
                    counts["isolated_current_measurement"] += 1
                    isolated_controls[key] = {
                        "position": point,
                        "bracket_sample_refs": [span.left, span.right],
                        **records[key],
                    }
        for group in stable:
            for i, (_, _, point) in enumerate(group, 2 if len(group) > 1 else 1):
                point["support_count"] = i
            segment = build_recorder_paths(
                (point for _, _, point in group),
                zones=zones,
                callouts=callouts,
            )["segments"][0]
            recovered.append(segment)
            for point in segment:
                key = point["sample"]["sample_sha256"]
                evidence[key] = {
                    "method": METHOD,
                    "support_policy": "consecutive_current"
                    if len(group) > 1
                    else "strong_isolated",
                    "position_sha256": digest(point),
                    "current_view": span.view,
                    "cnn_receipt_sha256": receipt,
                    "portrait_metric_receipt_sha256": metric_sha,
                    "portrait_reference_sha256": digest(knowledge.provenance),
                    "bracket_sample_refs": [span.left, span.right],
                    "bracket_position_sha256s": [digest(left_point), digest(right_point)],
                    **records[key],
                }
    merged = {
        **incumbent,
        "segments": sorted(
            [*incumbent["segments"], *recovered],
            key=lambda s: native_time(s[0]["sample"]),
        ),
    }
    rows = join_recorder_seconds(merged, timeline)
    new_edges = measured_native_edges({"segments": recovered})
    expected_edges = measured_native_edges(incumbent) | new_edges
    if measured_native_edges(merged) != expected_edges:
        raise ValueError("Replay must preserve incumbent edges and add only observed new edges")
    return {
        **merged,
        "second_rows": rows,
        "operable_coverage": measure_operable_coverage(merged, timeline["seconds"], rows, operable),
        "path_quality": measure_path_quality(merged, timeline["seconds"], rows, operable),
        "bracket_portrait_replay": {
            "input_sha256s": {
                name: file_sha(getattr(args, name))
                for name in ("bundle", "reference", "adaptive", "incumbent", "manifest")
            },
            "adaptive_unresolved_samples": len(unresolved),
            "target_samples": sum(len(b.targets) for b in brackets),
            "marker_threshold": args.threshold,
            "neighbor_support": args.neighbor_support,
            "strong_isolated": args.strong_isolated,
            "eligible_brackets": len(brackets),
            "counts": dict(counts),
            "evidence": evidence,
            "isolated_controls": isolated_controls,
        },
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("plan", "replay"))
    for name in (
        "recording-catalog",
        "bundle",
        "manifest",
        "reference",
        "adaptive",
        "incumbent",
        "output",
    ):
        parser.add_argument(f"--{name}", type=Path, required=True)
    parser.add_argument("--recording-id", required=True)
    for name in (
        "pixel-overrides",
        "asset-cache",
        "map-catalog",
        "layout",
        "models-directory",
        "zones",
        "metric",
    ):
        parser.add_argument(f"--{name}", type=Path)
    parser.add_argument("--threshold", type=float, default=0.5)
    parser.add_argument("--neighbor-support", action="store_true")
    parser.add_argument("--strong-isolated", action="store_true")
    args = parser.parse_args()
    output = args.output.resolve()
    if output.exists() or any((p / ".git").exists() for p in output.parents):
        raise ValueError("Choose a new private output path outside Git worktrees")
    if args.action == "replay" and (
        not (0 < args.threshold <= 1)
        or not all(
            (
                args.asset_cache,
                args.map_catalog,
                args.layout,
                args.models_directory,
                args.zones,
            )
        )
    ):
        parser.error("Replay requires reference assets, layout, zones, and matching CNN models")
    inputs = load_inputs(args)
    timeline, _, _, incumbent, operable, unresolved, paths, _ = inputs
    brackets = find_brackets(timeline, incumbent, operable, unresolved)
    if args.action == "plan":
        keys = {key for b in brackets for key in (b.left, *b.targets, b.right)}
        result = {
            "source_sha256": timeline["source"]["source_sha256"],
            "formal_outputs": 0,
            "brackets": [
                {"left": b.left, "right": b.right, "targets": b.targets} for b in brackets
            ],
            "samples": [
                {
                    "sample": timeline["native_frames"][key]["sample"],
                    "path": str(paths[key]),
                }
                for key in sorted(
                    keys, key=lambda k: native_time(timeline["native_frames"][k]["sample"])
                )
            ],
        }
    else:
        result = replay(args, inputs, brackets)
    write_private(output, result)


if __name__ == "__main__":
    main()
