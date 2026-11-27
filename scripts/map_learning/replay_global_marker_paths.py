"""Compare globally resolved observed marker paths with a frozen development baseline."""

from __future__ import annotations

import argparse
from collections import Counter, OrderedDict
from pathlib import Path

import cv2
import numpy as np

from valorant_ai_coach.recordings.catalog import RecordingCatalog
from valorant_ai_coach.temporal.evidence import digest, native_time
from valorant_ai_coach.temporal.map_path_quality import measure_path_quality
from valorant_ai_coach.temporal.map_recorder_knowledge import KnowledgeRecorderMap
from valorant_ai_coach.temporal.map_recorder_path import (
    join_recorder_seconds,
    measure_operable_coverage,
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

if __package__:
    from .global_marker_paths import solve
    from .marker_quality import enclosing_outline
    from .marker_tracks import Marker, _appearance, representatives
    from .partial_marker_support import partial_supported
    from .replay_marker_tracks import ContextPixels, _read, _selection, current_fit
else:
    from global_marker_paths import solve
    from marker_quality import enclosing_outline
    from marker_tracks import Marker, _appearance, representatives
    from partial_marker_support import partial_supported
    from replay_marker_tracks import ContextPixels, _read, _selection, current_fit


def verified(item):
    path = Path(item["path"])
    if file_sha(path) != item["sha256"]:
        raise ValueError("Frozen evaluation receipt changed")
    return read_json(path)


def replay(args):
    h = read_json(args.handoff)
    row = next(r for r in h["recordings"] if r["index"] == args.index)
    cat = RecordingCatalog(Path(h["catalog"]))
    cat.guard([row["recording_id"]], "development_analysis")
    rec = cat.state.recordings[row["recording_id"]]
    if rec.split != "DEVELOPMENT":
        raise ValueError("A development physical recording is required")
    baseline = verified(args.baseline)
    art = row["artifacts"]
    timeline = verified(art["native_and_second_timeline"])
    if timeline["source"]["source_sha256"] != rec.source_sha256:
        raise ValueError("Native timeline belongs to a different source")
    bundle = Path(art["native_and_second_timeline"]["path"])
    load_map_timeline(Path(args.baseline["path"]), bundle, timeline)
    source = read_json(args.observations)
    if source["timeline_sha256"] != file_sha(bundle) or source["formal_outputs"] != 0:
        raise ValueError("Candidate stream differs from timeline")
    proof = read_json(args.anchor_report)
    if proof["timeline_sha256"] != file_sha(bundle) or proof["formal_outputs"] != 0:
        raise ValueError("Anchor report differs from timeline")
    context = ContextPixels(args.context, bundle, rec.source_sha256, args.layout)
    knowledge = KnowledgeRecorderMap.load(args.asset_cache, args.map_catalog)
    projector = PublicMapPixels(
        args.map_catalog, args.layout, verified_references=knowledge.map_references
    )
    ref = verified(art["reference_replay"])
    identity = ref["recording_agent_uuid_binding"]["uuid"]
    target = knowledge._uuids.index(identity)
    map_id = ref["recording_map_uuid"]
    projector.references = [r for r in projector.references if r[1] == map_id]
    assets = projector.bindings["asset_sha256s"]
    atlas = atlas_distances_for(args.map_catalog, map_id, assets[map_id], knowledge.map_references)
    native = timeline["native_frames"]
    paths = {
        r["sample"]["sample_sha256"]: Path(r["path"])
        for r in verified(art["native_frame_manifest"])["frames"]
    }
    existing = {p["sample"]["sample_sha256"] for seg in baseline["segments"] for p in seg}
    targets = {
        key
        for r, native_row in zip(baseline["second_rows"], timeline["seconds"], strict=True)
        if not r["recorder_map_observations"]
        for key in native_row["sample_refs"]
    }
    operable = set(ref["comparison_evidence"]["operable_sample_refs"])
    targets &= operable
    witnesses = {
        tuple(m)
        for track in proof["multi_marker_replay"]["track_evidence"].values()
        for m in track["owner_witnesses"]
        if m[0] in existing
    }
    cache = OrderedDict()

    def image(key):
        if key not in cache:
            cache[key] = context.read(
                native[key]["sample"], paths[key], args.pixels, projector.layout
            )
            if len(cache) > 24:
                cache.popitem(last=False)
        else:
            cache.move_to_end(key)
        return cache[key]

    frames = source["frames"]
    added, segments = {}, []
    frame_requests = set()
    counts = Counter()
    for ep in map_view_episodes(timeline):
        scope = ep.current_samples
        if not targets.intersection(scope):
            continue
        anchors = {}
        for i, key in enumerate(scope):
            selected = [
                c
                for c in frames.get(key, ())
                if (key, *c["center_frame_px"], c["palette"]) in witnesses
            ]
            if not selected and key in existing and i % 5 == 0:
                pic = image(key)
                if pic is None:
                    continue
                for candidate in frames.get(key, ()):
                    if candidate["palette"] != "WARM":
                        continue
                    values = knowledge._portrait_scores(pic, candidate["center_frame_px"])
                    if (
                        values is not None
                        and values[target] >= 0.75
                        and values[target] - np.delete(values, target).max() >= 0.08
                    ):
                        selected.append(candidate)
            if not selected:
                continue
            pic = image(key)
            if pic is None:
                continue
            valid = [c for c in selected if enclosing_outline(pic, c["center_frame_px"])]
            if valid:
                valid.sort(key=lambda c: -(c["ring_sectors"] + c["opposing_sectors"]))
                if all(
                    np.linalg.norm(np.asarray(c["center_frame_px"]) - valid[0]["center_frame_px"])
                    <= 4
                    for c in valid
                ):
                    anchors[i] = valid[0]
        indices = sorted(anchors)
        for left, right in zip(indices, indices[1:], strict=False):
            if (
                right - left < 2
                or right - left > 25
                or not targets.intersection(scope[left + 1 : right])
            ):
                continue
            layers = []
            for i in range(left, right + 1):
                key = scope[i]
                pic = image(key)
                pool = [anchors[i]] if i in (left, right) else frames.get(key, [])
                if pic is None:
                    layers.append([])
                    continue
                gray = cv2.cvtColor(pic, cv2.COLOR_BGR2GRAY)
                scale = pic.shape[1] / 1920
                markers = [
                    Marker(
                        key,
                        i,
                        native_time(native[key]["sample"]),
                        tuple(c["center_frame_px"]),
                        c["palette"],
                        c["radius_px"],
                        c["ring_sectors"],
                        c["opposing_sectors"],
                        _appearance(gray, *c["center_frame_px"], scale),
                    )
                    for c in pool
                    if c["palette"] == "WARM"
                ]
                layers.append(representatives(markers, scale))
            solution = solve(layers, 1)
            counts["intervals"] += 1
            if not solution:
                continue
            run = []
            track = digest(
                ["development_global_marker_paths_v1", ep.episode_ref, scope[left], scope[right]]
            )
            for j, node in enumerate(solution[1:-1], 1):
                key = scope[left + j]
                if key not in targets or key in added:
                    continue
                if node is None or solution[j - 1] is None or solution[j + 1] is None:
                    counts["unresolved_global_hypothesis"] += 1
                    continue
                marker, margin = node
                pic = image(key)
                outline = enclosing_outline(pic, marker.center)
                partial = False
                if outline is None:
                    partial = partial_supported(
                        image(scope[left + j - 1]),
                        pic,
                        image(scope[left + j + 1]),
                        solution[j - 1][0],
                        marker,
                        solution[j + 1][0],
                    )
                if outline is None and not partial:
                    counts["unconfirmed_current_pixels"] += 1
                    continue
                actual = _read(native[key]["sample"], paths[key], args.pixels)
                if actual is None:
                    counts["missing_full_frame"] += 1
                    frame_requests.add(key)
                    continue
                values = knowledge._portrait_scores(actual, marker.center)
                if (
                    values is not None
                    and values.max() >= 0.78
                    and values.max() - values[target] >= 0.12
                ):
                    counts["current_agent_conflict"] += 1
                    continue
                fit = current_fit(
                    actual,
                    native[key]["sample"],
                    projector,
                    map_id,
                    args.alignment_cache,
                    contrast_center=marker.center,
                )
                if fit is None:
                    counts["registration_unavailable"] += 1
                    continue
                pool = frames[key]
                selection = _selection(marker, pool, identity, track, j + 1)
                point = project_recorder_witness(
                    actual, native[key]["sample"], pool, selection, fit, reference_sha256s=assets
                )
                if point is None or clearly_outside_atlas(atlas, point["map_reference_px"]):
                    continue
                if run and point["support_count"] != run[-1]["support_count"] + 1:
                    segments.append(run)
                    run = []
                run.append(point)
                added[key] = {
                    "anchor_samples": [scope[left], scope[right]],
                    "margin": None if np.isinf(margin) else margin,
                    "center_frame_px": list(marker.center),
                    "partial_support": partial,
                    "outline": outline,
                }
            if run:
                segments.append(run)
    result = {
        **baseline,
        "segments": sorted(
            [*baseline["segments"], *segments], key=lambda s: native_time(s[0]["sample"])
        ),
    }
    result["second_rows"] = join_recorder_seconds(result, timeline)
    result["operable_coverage"] = measure_operable_coverage(
        result, timeline["seconds"], result["second_rows"], operable
    )
    result["path_quality"] = measure_path_quality(
        result, timeline["seconds"], result["second_rows"], operable
    )
    result["global_marker_replay"] = {
        "formal_outputs": 0,
        "counts": dict(counts),
        "added_evidence": added,
        "required_full_frames": sorted(frame_requests),
        "baseline_sha256": args.baseline["sha256"],
        "split": rec.learning["split"],
        "code_sha256s": {
            n: file_sha(Path(__file__).with_name(n))
            for n in (
                "global_marker_paths.py",
                "partial_marker_support.py",
                "replay_global_marker_paths.py",
            )
        },
    }
    return result


def main():
    p = argparse.ArgumentParser(description=__doc__)
    for key in (
        "handoff",
        "baseline",
        "observations",
        "anchor-report",
        "context",
        "layout",
        "asset-cache",
        "map-catalog",
        "pixels",
        "output",
    ):
        p.add_argument("--" + key, type=Path, required=True)
    p.add_argument("--alignment-cache", type=Path)
    p.add_argument("--index", type=int, required=True)
    args = p.parse_args()
    args.baseline = read_json(args.baseline)
    cv2.setNumThreads(1)
    result = replay(args)
    write_private(args.output, result)
    print(
        result["global_marker_replay"]["counts"],
        len(result["global_marker_replay"]["added_evidence"]),
        flush=True,
    )


if __name__ == "__main__":
    main()
