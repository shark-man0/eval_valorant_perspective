"""Replay anonymous marker tracks with late recorder attribution on development video."""

from __future__ import annotations

import argparse
import hashlib
import math
from bisect import bisect_right
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
from valorant_ai_coach.temporal.map_recording_alignment import NativeMapFlowAlignment
from valorant_ai_coach.temporal.map_recording_anchors import RecordingMapAnchors
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
    from .acquire_marker_context import SCHEMA as CONTEXT_SCHEMA
    from .long_marker_ownership import extension, read_match_profile
    from .marker_tracks import Track, associate, observe, representatives
else:
    from acquire_marker_context import SCHEMA as CONTEXT_SCHEMA
    from long_marker_ownership import extension, read_match_profile
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


class ContextPixels:
    def __init__(self, path, bundle, source_sha, layout):
        self.path = path
        self.frames = {}
        if path is None:
            return
        receipt = read_json(path)
        if (
            receipt.get("schema") != CONTEXT_SCHEMA
            or receipt.get("formal_outputs") != 0
            or receipt.get("layout_sha256") != file_sha(layout)
            or receipt.get("timeline_sha256") != file_sha(bundle)
            or receipt.get("source_sha256") != source_sha
        ):
            raise ValueError("Native ROI receipt does not match this replay")
        self.bounds, self.frames = receipt["bounds"], receipt["frames"]

    def read(self, sample, path, overrides, layout):
        row = self.frames.get(sample["sample_sha256"])
        if row is None:
            return _read(sample, path, overrides)
        width, height = sample["frame_size_px"]
        expected = layout.normalized_roi("minimap_normal").pixel_bounds(width, height)
        crop_path = (self.path.parent / row["file"]).resolve()
        if crop_path.parent != self.path.resolve().parent:
            raise ValueError("Context crop must be stored with its acquisition receipt")
        data = crop_path.read_bytes()
        if (
            tuple(self.bounds) != tuple(expected)
            or row["native_pixel_sha256"] != sample["native_pixel_sha256"]
            or hashlib.sha256(data).hexdigest() != row["crop_sha256"]
        ):
            raise ValueError("Context ROI differs from the exact acquired pixels")
        crop = cv2.imdecode(np.frombuffer(data, np.uint8), cv2.IMREAD_COLOR)
        left, top, right, bottom = expected
        if crop is None or crop.shape != (bottom - top, right - left, 3):
            raise ValueError("Context ROI dimensions differ from its acquisition")
        # The padding is never used as evidence and is not passed into the
        # projection contract, which separately verifies a complete native frame.
        view = np.zeros((height, width, 3), np.uint8)
        view[top:bottom, left:right] = crop
        return view


def raw_fit(image, sample, projector, cache):
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
    return raw


def acceptable_fit(raw, map_id):
    fits = raw["map_name_candidates"]
    return (
        len(fits) == 1
        and fits[0]["map_id"] == map_id
        and 0 <= fits[0]["fit_residual_p95_reference_px"] <= 8
    )


def current_fit(image, sample, projector, map_id, cache, *, contrast_center=None):
    raw = raw_fit(image, sample, projector, cache)
    if contrast_center is not None and not raw["map_name_candidates"]:
        raw = projector.recover_contrast(image, raw, map_id, contrast_center)
    return raw if acceptable_fit(raw, map_id) else None


def recover_fit(image, sample, center, projector, map_id, cache, episode, history):
    raw = raw_fit(image, sample, projector, cache)
    if acceptable_fit(raw, map_id):
        return raw
    failed = {**raw, "map_name_candidates": []}
    contrast = projector.recover_contrast(image, failed, map_id, center)
    if acceptable_fit(contrast, map_id):
        return contrast
    bank = RecordingMapAnchors()
    now = native_time(sample)
    for previous, pixels in history:
        fit = current_fit(pixels, previous, projector, map_id, cache)
        if fit is None:
            continue
        elapsed = now - native_time(previous)
        if elapsed <= Fraction(1, 4):
            flow = NativeMapFlowAlignment()
            flow.remember(pixels, previous, episode, fit)
            candidate = flow.recover(image, sample, episode, failed, center, map_id, carry=True)
            if acceptable_fit(candidate, map_id):
                return candidate
        elif elapsed >= 10:
            bank.observe(pixels, previous, fit, map_id, center, recover=False)
    candidate = bank.observe(image, sample, failed, map_id, center)
    return candidate if acceptable_fit(candidate, map_id) else None


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


def episode_ordinals(scope, targets, whole_episode):
    if whole_episode:
        return range(len(scope))
    required = set()
    for ordinal, key in enumerate(scope):
        if key in targets:
            required.update(range(max(0, ordinal - 2), min(len(scope), ordinal + 3)))
    return sorted(required)


def alignment_history(index, scope, clock, frames, paths, args, context, layout):
    now = clock[index]
    for age in (60, 45, 30, 15):
        candidate = bisect_right(clock, now - age, hi=index) - 1
        if candidate >= 0:
            key = scope[candidate]
            sample = frames[key]["sample"]
            pixels = context.read(sample, paths[key], args.pixel_overrides, layout)
            if pixels is not None:
                yield sample, pixels
    if index > 0 and now - clock[index - 1] <= Fraction(1, 4):
        key = scope[index - 1]
        sample = frames[key]["sample"]
        pixels = context.read(sample, paths[key], args.pixel_overrides, layout)
        if pixels is not None:
            yield sample, pixels


def observations_for_episode(
    scope,
    targets,
    timeline,
    paths,
    projector,
    args,
    counts,
    pools,
    context,
):
    frames = timeline["native_frames"]
    layers, warm_counts, conflicts = [], {}, set()
    scale = None
    for ordinal in episode_ordinals(scope, targets, args.whole_episode):
        key = scope[ordinal]
        sample = frames[key]["sample"]
        image = context.read(sample, paths[key], args.pixel_overrides, projector.layout)
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
        else:
            counts["context_frames_read"] += 1
        warm_counts[key] = sum(
            m.palette == "WARM" and m.sectors >= 14 for m in representatives(pool, scale)
        )
        layers.append(pool)
    tracks = associate(layers, scale, conflicts) if scale is not None else []
    return tracks, scale, warm_counts, conflicts


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
    context,
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
        image = context.read(frame["sample"], paths[key], args.pixel_overrides, projector.layout)
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
                attach_owner(
                    Track(current, track.link_margins),
                    evidence,
                    warm_counts,
                    owned,
                    args.long_ownership,
                )
                current = []
            else:
                current.append(marker)
        attach_owner(
            Track(current, track.link_margins), evidence, warm_counts, owned, args.long_ownership
        )
    return relevant, owned, evidence


def attach_owner(track, evidence, warm_counts, owned, allow_round):
    witnesses = classify_track(track, evidence, warm_counts)
    if witnesses or (allow_round and len(track.measurements) >= 3):
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
    context = ContextPixels(args.context_pixels, args.bundle, rec.source_sha256, args.layout)
    profile = read_match_profile(args.match_profile, rec.physical_match_id)
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
    reasons = {}
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
        counts["episode_context_expected"] += len(scope)
        clock = [native_time(frames[key]["sample"]) for key in scope]
        tracks, scale, warm_counts, conflicts = observations_for_episode(
            scope,
            targets,
            timeline,
            paths,
            projector,
            args,
            counts,
            pools,
            context,
        )
        anonymous_tracks[episode.episode_ref] = [
            [marker_ref(marker) for marker in track.measurements]
            for track in tracks
            if len(track.measurements) >= 2
        ]
        anchors = incumbents
        if args.long_ownership and args.whole_episode:
            anchors = {key: incumbents[key] for key in scope[::5] if key in incumbents}
        relevant, owned, evidence = attributed_tracks(
            tracks,
            targets,
            frames,
            paths,
            anchors,
            knowledge,
            projector,
            target,
            map_id,
            args,
            scale,
            warm_counts,
            context,
        )
        for track in relevant:
            tracking.update(m.sample_ref for m in track.measurements if m.sample_ref in targets)
        opening = native_time(frames[episode.boundary_sample_ref or scope[0]]["sample"])
        pending = []
        required = Counter()
        for track, witnesses in owned:
            extra = (
                extension(
                    track,
                    witnesses,
                    evidence,
                    warm_counts,
                    episode.opening_boundary,
                    opening,
                    conflicts,
                    profile,
                )
                if args.long_ownership
                else {}
            )
            local = (
                (min(w.ordinal for w in witnesses) - 4, max(w.ordinal for w in witnesses) + 4)
                if witnesses
                else None
            )
            if not local and not extra:
                continue
            pending.append((track, witnesses, local, extra))
            required.update(
                m.sample_ref
                for m in track.measurements
                if not args.long_ownership
                or (local and local[0] <= m.ordinal <= local[1])
                or m.sample_ref in extra
            )
        by_sample = defaultdict(list)
        for (sample_ref, _), value in evidence.items():
            by_sample[sample_ref].append(value)
        ambiguous = {ref for ref, center in conflicts if (ref, center) in evidence}
        counts["marker_association_conflicts"] += len(ambiguous & targets)
        for key in targets.intersection(scope):
            per_frame = by_sample[key]
            if required[key] > 1:
                counts["owner_claim_conflicts"] += 1
                reasons[key] = "competing_owner_tracks"
            elif required[key] == 1:
                reasons[key] = "eligible_track_without_current_selection"
            elif key in ambiguous:
                reasons[key] = "ambiguous_track_link"
            elif not per_frame:
                reasons[key] = "no_tracked_warm_marker"
            elif all(row[3] for row in per_frame):
                reasons[key] = "identity_contradiction"
            elif any(row[0] or (row[1] >= 0.75 and row[2] >= 0.08) for row in per_frame):
                reasons[key] = "isolated_owner_witness"
            else:
                reasons[key] = "insufficient_owner_anchor_or_continuity"
        for track, witnesses, local, extra in pending:
            points = []
            track_id = digest([METHOD, episode.episode_ref, marker_ref(track.measurements[0])])
            track_evidence[track_id] = {
                "episode": episode.episode_ref,
                "measurements": [marker_ref(m) for m in track.measurements],
                "owner_witnesses": [marker_ref(m) for m in witnesses],
            }
            for i, marker in enumerate(track.measurements):
                key = marker.sample_ref
                near = local is not None and local[0] <= marker.ordinal <= local[1]
                if (
                    key not in targets
                    or required[key] != 1
                    or marker.palette != "WARM"
                    or evidence[key, marker.center][3]
                    or not (near or key in extra)
                ):
                    continue
                ownership.add(key)
                reasons[key] = "direct_atlas_fit_unavailable"
                sample = frames[key]["sample"]
                image = _read(sample, paths[key], args.pixel_overrides)
                if image is None:
                    raise ValueError("Observed native pixels disappeared before projection")
                if args.contrast_registration:
                    history = alignment_history(
                        marker.ordinal,
                        scope,
                        clock,
                        frames,
                        paths,
                        args,
                        context,
                        projector.layout,
                    )
                    fit = recover_fit(
                        image,
                        sample,
                        marker.center,
                        projector,
                        map_id,
                        args.alignment_cache,
                        episode.episode_ref,
                        history,
                    )
                else:
                    fit = current_fit(image, sample, projector, map_id, args.alignment_cache)
                if fit is None:
                    continue
                pool = pools[key]
                selection = _selection(marker, pool, identity, track_id, i + 1)
                point = project_recorder_witness(
                    image, sample, pool, selection, fit, reference_sha256s=assets
                )
                if point is None:
                    reasons[key] = "projection_contract_abstention"
                    continue
                if clearly_outside_atlas(atlas, point["map_reference_px"]):
                    reasons[key] = "outside_atlas"
                    continue
                if fit.get("alignment_recovery"):
                    counts["recovered_current_registrations"] += 1
                if not near and key in extra:
                    counts["extended_positions"] += 1
                    counts["round_seed_positions"] += extra[key]["round_start_seed"]
                reasons[key] = "projected"
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
                    **({"extended_owner": extra[key]} if not near and key in extra else {}),
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
        "context": "all_observed_episode_frames" if args.whole_episode else "target_with_neighbors",
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
                "context_pixels",
            )
            if getattr(args, name) is not None
        },
        "counts": dict(counts),
        "target_reasons": reasons,
        "match_profile_sha256": file_sha(args.match_profile) if args.match_profile else None,
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
    parser.add_argument(
        "--whole-episode",
        action="store_true",
        help="Use all available native pixels in each matching self-view episode",
    )
    parser.add_argument("--context-pixels", type=Path)
    parser.add_argument("--match-profile", type=Path)
    parser.add_argument("--long-ownership", action="store_true")
    parser.add_argument("--contrast-registration", action="store_true")
    args = parser.parse_args()
    if args.match_profile and not args.long_ownership:
        parser.error("A temporal matcher requires long ownership attribution")

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
