"""Replay anonymous marker tracks with late recorder attribution on development video."""

from __future__ import annotations

import argparse
import hashlib
import math
from collections import Counter, defaultdict
from copy import copy
from fractions import Fraction
from pathlib import Path

import cv2
import numpy as np

from valorant_ai_coach.recordings.catalog import RecordingCatalog
from valorant_ai_coach.temporal.evidence import digest, freeze_native_sample, native_time
from valorant_ai_coach.temporal.map_path_quality import measure_path_quality
from valorant_ai_coach.temporal.map_recorder_export import _load_native_image, _pixels_match
from valorant_ai_coach.temporal.map_recorder_knowledge import KnowledgeRecorderMap
from valorant_ai_coach.temporal.map_recorder_path import (
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
from valorant_ai_coach.temporal.map_view_episodes import map_view_episodes
from valorant_ai_coach.temporal.public_map_pixels import PublicMapPixels
from valorant_ai_coach.temporal.replay import file_sha, read_json, write_private
from valorant_ai_coach.temporal.visual_state import selected_agent

if __package__:
    from .marker_tracks import Track, associate, observe, representatives
else:
    from marker_tracks import Track, associate, observe, representatives

METHOD = "development_map_multi_marker_track_v1"


def load_inputs(args):
    catalog = RecordingCatalog(args.recording_catalog)
    catalog.guard([args.recording_id], "development_analysis")
    rec = catalog.state.recordings[args.recording_id]
    split = rec.learning.get("split")
    if rec.split != "DEVELOPMENT" or split not in {"TRAIN", "DEV_COMPARISON", "VALIDATION"}:
        raise ValueError("A catalog-admitted development recording is required")
    if split != args.split:
        raise ValueError("The actual recording split differs from the planned split")
    timeline = read_json(args.bundle)
    source = timeline["source"]
    if (source["source_sha256"], source["physical_match_id"]) != (
        rec.source_sha256,
        rec.physical_match_id,
    ):
        raise ValueError("The timeline does not belong to the admitted physical recording")
    reference, adaptive = (read_json(path) for path in (args.reference, args.adaptive))
    bundle_hash, manifest_hash = file_sha(args.bundle), file_sha(args.manifest)
    for report in (reference, adaptive):
        if (
            report["formal_outputs"] != 0
            or report["qualified"] is not False
            or report["timeline_sha256"] != bundle_hash
            or report["frame_manifest_sha256"] != manifest_hash
        ):
            raise ValueError("The replays must share the exact original native input")
    incumbent = read_json(args.incumbent)
    load_map_timeline(args.incumbent, args.bundle, timeline)
    if incumbent["reference_report_sha256"] != file_sha(args.reference):
        raise ValueError("Incumbent must use the original reference replay")
    prior = incumbent
    if args.exclude_covered is not None:
        load_map_timeline(args.exclude_covered, args.bundle, timeline)
        prior = read_json(args.exclude_covered)
        if prior["reference_report_sha256"] != incumbent["reference_report_sha256"]:
            raise ValueError("The previous comparison must share the original reference")
    paths = {}
    for entry in read_json(args.manifest)["frames"]:
        sample = freeze_native_sample(entry["sample"])
        key = sample["sample_sha256"]
        if key in paths or sample != timeline["native_frames"].get(key, {}).get("sample"):
            raise ValueError("Native manifest differs from the timeline")
        paths[key] = Path(entry["path"])
    return rec, timeline, reference, adaptive, incumbent, prior, paths


def _read(sample, path, overrides):
    try:
        return _load_native_image(sample, path)
    except FileNotFoundError:
        override = overrides / f"{sample['sample_sha256']}.png" if overrides else None
        if override is None or not override.is_file():
            return None
        image = cv2.imdecode(np.frombuffer(override.read_bytes(), np.uint8), cv2.IMREAD_COLOR)
        if image is None or not _pixels_match(image, sample):
            raise ValueError("Override must match the original observed pixels") from None
        return image


def current_fit(image, sample, projector, map_id, cache):
    raw = None
    if cache is not None:
        key = digest(["exact_atlas_fit_v1", projector.fingerprint, sample["sample_sha256"]])
        path = cache / f"{key}.json"
        if path.is_file():
            row = read_json(path)
            raw = row["raw"]
            left, top, right, bottom = raw["roi_pixel_bounds"]
            pixels = hashlib.sha256(image[top:bottom, left:right].tobytes()).hexdigest()
            if (
                row["key"] != key
                or row["raw_sha256"] != digest(raw)
                or (pixels != raw["roi_pixel_sha256"])
            ):
                raise ValueError("Exact Map fit cache differs from the native input")
    if raw is None:
        raw = projector.inspect_exact(image)["raw"]
    fits = raw["map_name_candidates"]
    if (
        len(fits) == 1
        and fits[0]["map_id"] == map_id
        and 0 <= fits[0]["fit_residual_p95_reference_px"] <= 8
    ):
        return raw
    return None


def freeze_targets(timeline, reference, adaptive, incumbent, prior):
    operable = set(reference["comparison_evidence"]["operable_sample_refs"])
    rejected = set(reference["comparison_evidence"]["unresolved_portrait_sample_refs"])
    rejected.intersection_update(adaptive["comparison_evidence"]["unresolved_portrait_sample_refs"])
    target = {}
    for source, baseline, previous in zip(
        timeline["seconds"],
        incumbent["second_rows"],
        prior["second_rows"],
        strict=True,
    ):
        if (
            source["timestamp"] != baseline["timestamp"]
            or source["timestamp"] != previous["timestamp"]
        ):
            raise ValueError("Different timeline seconds")
        keys = source["sample_refs"]
        if (
            keys
            and not baseline["recorder_map_observations"]
            and not previous["recorder_map_observations"]
            and set(keys) <= operable & rejected
        ):
            target[source["timestamp"]] = tuple(keys)
    return operable, target


def classify_track(track, evidence, frame_warm_counts):
    """Attribute a whole track from independently observed current evidence."""
    observations = track.measurements
    warm = [m for m in observations if m.palette == "WARM"]
    if len(warm) < 3 or len(warm) < 0.8 * len(observations):
        return []
    witnesses = []
    for m in warm:
        direct, score, margin, conflict = evidence[m.sample_ref, m.center]
        if conflict:
            continue
        if direct or (m.sectors >= 14 and score >= 0.75 and margin >= 0.08):
            witnesses.append(m)
    if len(witnesses) >= 2 and witnesses[-1].at > witnesses[0].at:
        return witnesses
    # A weak portrait at one time can support a repeatedly measured distinctive
    # outline. It cannot identify a track competing with another warm outline.
    outline = [
        m
        for m in warm
        if m.sectors >= 18 and m.opposite >= 7 and frame_warm_counts[m.sample_ref] == 1
    ]
    if len(outline) >= 4 and outline[-1].at - outline[0].at >= Fraction(3, 5) and witnesses:
        return witnesses + [m for m in outline if m not in witnesses]
    return []


def marker_ref(marker):
    return [marker.sample_ref, *marker.center, marker.palette]


def direct_anchor(incumbent, fit, pool, scale):
    if incumbent is None or fit is None:
        return None
    left, top, _, _ = fit["roi_pixel_bounds"]
    matrix = fit["map_name_candidates"][0]["reference_to_roi_homography_candidate"]
    x, y = np.asarray(matrix)[:2] @ [*incumbent["map_reference_px"], 1.0]
    ranks = sorted(
        (math.dist((x + left, y + top), marker.center), marker.center)
        for marker in pool
        if marker.palette == "WARM"
    )
    if (
        ranks
        and ranks[0][0] <= 3 * scale
        and (len(ranks) == 1 or ranks[1][0] - ranks[0][0] >= 2 * scale)
    ):
        return ranks[0][1]
    return None


def observations_for_episode(scope, targets, timeline, paths, projector, args, counts, pools):
    frames = timeline["native_frames"]
    required = set()
    for ordinal, key in enumerate(scope):
        if key in targets:
            required.update(range(max(0, ordinal - 2), min(len(scope), ordinal + 3)))
    layers, warm_counts = [], {}
    scale = None
    for ordinal in sorted(required):
        key = scope[ordinal]
        sample = frames[key]["sample"]
        image = _read(sample, paths[key], args.pixel_overrides)
        if image is None:
            if key in targets:
                counts["pixels_missing"] += 1
            continue
        scale = image.shape[1] / 1920
        bounds = projector.layout.normalized_roi("minimap_normal").pixel_bounds(
            image.shape[1],
            image.shape[0],
        )
        pool = observe(image, bounds, key, ordinal, native_time(sample))
        pools[key] = [
            {
                "center_frame_px": list(m.center),
                "palette": m.palette,
                "radius_px": m.radius,
                "ring_sectors": m.sectors,
                "opposing_sectors": m.opposite,
            }
            for m in pool
        ]
        if key in targets:
            counts["pixels_read"] += 1
            counts["proposals"] += len(pool)
        warm_counts[key] = sum(
            m.palette == "WARM" and m.sectors >= 14 for m in representatives(pool, scale)
        )
        layers.append(pool)
    tracks = associate(layers, scale) if scale is not None else []
    return tracks, scale, warm_counts


def attributed_tracks(
    tracks,
    targets,
    frames,
    paths,
    incumbents,
    knowledge,
    projector,
    target,
    map_id,
    args,
    scale,
    warm_counts,
):
    relevant = [
        t
        for t in tracks
        if len(t.measurements) >= 3 and any(m.sample_ref in targets for m in t.measurements)
    ]
    warm_points = defaultdict(list)
    for track in relevant:
        for marker in track.measurements:
            if marker.palette == "WARM":
                warm_points[marker.sample_ref].append(marker)
    evidence = {}
    for key, points in warm_points.items():
        frame = frames[key]
        image = _read(frame["sample"], paths[key], args.pixel_overrides)
        if image is None:
            raise ValueError("Observed native pixels disappeared during the replay")
        existing = incumbents.get(key)
        fit = (
            current_fit(image, frame["sample"], projector, map_id, args.alignment_cache)
            if existing
            else None
        )
        direct = direct_anchor(existing, fit, points, scale)
        viewed = selected_agent(
            (frame.get("viewed_identity") or {}).get("viewed_agent_candidates", [])
        )
        viewed = knowledge._catalog.agent(viewed) if viewed else None
        hud_conflict = viewed is not None and viewed.uuid != knowledge._uuids[target]
        for m in points:
            values = knowledge._portrait_scores(image, m.center)
            score = float(values[target]) if values is not None else 0.0
            rival = float(np.delete(values, target).max()) if values is not None else 0.0
            evidence[key, m.center] = (
                m.center == direct,
                score,
                score - rival,
                hud_conflict or (rival >= 0.78 and rival - score >= 0.12),
            )
    owned = []
    for track in relevant:
        current = []
        for marker in track.measurements:
            if marker.palette == "WARM" and evidence[marker.sample_ref, marker.center][3]:
                attach_owner(current, evidence, warm_counts, owned)
                current = []
            else:
                current.append(marker)
        attach_owner(current, evidence, warm_counts, owned)
    return relevant, owned, evidence


def attach_owner(measurements, evidence, warm_counts, owned):
    track = Track(measurements)
    witnesses = classify_track(track, evidence, warm_counts)
    if witnesses:
        owned.append((track, witnesses))


def _selection(marker, pool, identity, track_id, sequence):
    index = next(
        i
        for i, entry in enumerate(pool)
        if entry["center_frame_px"] == list(marker.center) and entry["palette"] == marker.palette
    )
    return {
        "contract": "development_map_recorder_selection_v1",
        "sample_sha256": marker.sample_ref,
        "ordered_candidate_pool_digest": digest(pool),
        "support_candidate_index": index,
        "research_candidate_index": index,
        "support_center_frame_px": list(marker.center),
        "support_count": sequence,
        "selection_status": "RESEARCH_SELECTED",
        "qualified": False,
        "position_authority": False,
        "selection_method": "knowledge_agent_uuid",
        "recorder_agent_uuid_candidate": identity,
        "track_anchor": track_id,
    }


def replay(args):
    rec, timeline, reference, adaptive, incumbent, prior, paths = load_inputs(args)
    operable, seconds = freeze_targets(timeline, reference, adaptive, incumbent, prior)
    targets = {key for refs in seconds.values() for key in refs}
    if not operable <= paths.keys():
        raise ValueError("Operable frames are missing from the native manifest")
    frames = timeline["native_frames"]
    knowledge = KnowledgeRecorderMap.load(args.asset_cache, args.map_catalog)
    projector = PublicMapPixels(
        args.map_catalog, args.layout, verified_references=knowledge.map_references
    )
    binding = reference["recording_agent_uuid_binding"]
    if (
        not binding
        or binding != adaptive["recording_agent_uuid_binding"]
        or binding["source_sha256"] != rec.source_sha256
        or binding["qualified"] is not False
        or len(set(binding["evidence_samples"])) < 3
        or not set(binding["evidence_samples"]) <= frames.keys()
        or projector.fingerprint != reference["map_catalog_fingerprint"]
        or any(r["game_knowledge"] != knowledge.provenance for r in (reference, adaptive))
    ):
        raise ValueError("Exact existing HUD Agent binding and public assets required")
    identity = binding["uuid"]
    target = knowledge._uuids.index(identity)
    map_id = reference["recording_map_uuid"]
    assets = projector.bindings["asset_sha256s"]
    atlas = atlas_distances_for(args.map_catalog, map_id, assets[map_id], knowledge.map_references)
    # The reference replay already binds the physical recording to a Map. Fit
    # that reference independently to current pixels when no original fit exists.
    # Keep the original fingerprint so cached all-Map checks remain verifiable.
    projector = copy(projector)
    projector.references = [row for row in projector.references if row[1] == map_id]
    if len(projector.references) != 1:
        raise ValueError("Exactly one copy of the recording Map reference is required")
    counts = Counter()
    pools, traces, track_evidence, anonymous_tracks = {}, {}, {}, {}
    tracking, ownership = set(), set()
    segments = []
    incumbents = {
        point["sample"]["sample_sha256"]: point
        for segment in incumbent["segments"]
        for point in segment
        if point["kind"] == "selected"
        and not point.get("alignment_recovery")
        and point.get("fit_residual_p95_reference_px", 99) is not None
        and point["fit_residual_p95_reference_px"] <= 6
        and point["map_id"] == map_id
    }
    for episode in map_view_episodes(timeline):
        scope = episode.current_samples
        if not targets.intersection(scope):
            continue
        counts["episodes_examined"] += 1
        counts["episode_target_frames"] += len(targets.intersection(scope))
        tracks, scale, warm_counts = observations_for_episode(
            scope,
            targets,
            timeline,
            paths,
            projector,
            args,
            counts,
            pools,
        )
        anonymous_tracks[episode.episode_ref] = [
            [marker_ref(marker) for marker in track.measurements]
            for track in tracks
            if len(track.measurements) >= 2
        ]
        relevant, owned, evidence = attributed_tracks(
            tracks,
            targets,
            frames,
            paths,
            incumbents,
            knowledge,
            projector,
            target,
            map_id,
            args,
            scale,
            warm_counts,
        )
        for track in relevant:
            tracking.update(m.sample_ref for m in track.measurements if m.sample_ref in targets)
        required = Counter(m.sample_ref for track, _ in owned for m in track.measurements)
        for track, witnesses in owned:
            points = []
            track_id = digest([METHOD, episode.episode_ref, marker_ref(track.measurements[0])])
            track_evidence[track_id] = {
                "episode": episode.episode_ref,
                "measurements": [marker_ref(m) for m in track.measurements],
                "owner_witnesses": [marker_ref(m) for m in witnesses],
            }
            first = min(w.ordinal for w in witnesses)
            last = max(w.ordinal for w in witnesses)
            for i, marker in enumerate(track.measurements):
                key = marker.sample_ref
                if (
                    key not in targets
                    or required[key] != 1
                    or marker.palette != "WARM"
                    or evidence[key, marker.center][3]
                    or not first - 4 <= marker.ordinal <= last + 4
                ):
                    continue
                ownership.add(key)
                sample = frames[key]["sample"]
                image = _read(sample, paths[key], args.pixel_overrides)
                if image is None:
                    raise ValueError("Observed native pixels disappeared before projection")
                fit = current_fit(image, sample, projector, map_id, args.alignment_cache)
                if fit is None:
                    continue
                pool = pools[key]
                selection = _selection(marker, pool, identity, track_id, i + 1)
                point = project_recorder_witness(
                    image, sample, pool, selection, fit, reference_sha256s=assets
                )
                if point is None or clearly_outside_atlas(atlas, point["map_reference_px"]):
                    continue
                if points:
                    old = points[-1]
                    elapsed = native_time(sample) - native_time(old["sample"])
                    distance = math.dist(point["map_reference_px"], old["map_reference_px"])
                    if (
                        distance > 6 + 60 * float(elapsed)
                        or elapsed > Fraction(1, 4)
                        or old["support_count"] != i
                    ):
                        segments.append(points)
                        points = []
                points.append(point)
                traces[key] = {
                    "track": track_id,
                    "proposal": marker_ref(marker),
                    "observed_point_sha256": digest(point),
                }
            if points:
                segments.append(points)
    result = {
        **incumbent,
        "segments": sorted(
            [*incumbent["segments"], *segments], key=lambda s: native_time(s[0]["sample"])
        ),
    }
    result["second_rows"] = join_recorder_seconds(result, timeline)
    result["operable_coverage"] = measure_operable_coverage(
        result,
        timeline["seconds"],
        result["second_rows"],
        operable,
    )
    result["path_quality"] = measure_path_quality(
        result, timeline["seconds"], result["second_rows"], operable
    )
    if not measured_native_edges(incumbent) <= measured_native_edges(result):
        raise ValueError("The candidate removed existing measured edges")
    has_candidates = {key for key in targets if pools.get(key)}
    counts["target_frames"] = len(targets)
    counts["target_seconds"] = len(seconds)
    for name, keys in (
        ("candidate", has_candidates),
        ("track", tracking),
        ("owner", ownership),
        ("projection", traces.keys()),
    ):
        counts[f"{name}_frames"] = len(keys)
        counts[f"{name}_seconds"] = sum(
            any(key in keys for key in refs) for refs in seconds.values()
        )
    result["multi_marker_replay"] = {
        "method": METHOD,
        "split": args.split,
        "implementation_sha256s": {
            name: file_sha(Path(__file__).with_name(name))
            for name in ("marker_tracks.py", "replay_marker_tracks.py")
        },
        "input_sha256s": {
            name: file_sha(getattr(args, name))
            for name in (
                "bundle",
                "manifest",
                "reference",
                "adaptive",
                "incumbent",
                "exclude_covered",
            )
            if getattr(args, name) is not None
        },
        "counts": dict(counts),
        "track_evidence": track_evidence,
        "added_evidence": traces,
        "formal_outputs": 0,
    }
    write_private(
        args.proposals,
        {
            "schema": "development_map_anonymous_candidate_pool_v1",
            "timeline_sha256": file_sha(args.bundle),
            "frames": pools,
            "anonymous_tracks": anonymous_tracks,
            "formal_outputs": 0,
        },
    )
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in (
        "recording-catalog",
        "bundle",
        "manifest",
        "reference",
        "adaptive",
        "incumbent",
        "asset-cache",
        "map-catalog",
        "layout",
        "proposals",
        "output",
    ):
        parser.add_argument(f"--{name}", required=True, type=Path)
    for name in ("pixel-overrides", "alignment-cache", "exclude-covered"):
        parser.add_argument(f"--{name}", type=Path)
    parser.add_argument("--recording-id", required=True)
    parser.add_argument("--split", required=True, choices=("TRAIN", "DEV_COMPARISON", "VALIDATION"))
    args = parser.parse_args()
    for destination in (args.output, args.proposals):
        if destination.exists() or any(
            (p / ".git").exists() for p in destination.resolve().parents
        ):
            parser.error("A new private destination outside Git is required")
    cv2.setNumThreads(1)
    result = replay(args)
    write_private(args.output, result)
    print(result["multi_marker_replay"]["counts"], flush=True)


if __name__ == "__main__":
    main()
