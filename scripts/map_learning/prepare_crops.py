"""Produce source- and crop-bound weak labels from admitted Map TRAIN observations."""

import argparse
import hashlib
import os
from fractions import Fraction
from pathlib import Path

import cv2
import numpy as np
from crop_lineage import CATEGORIES, SCHEMA, load_crop_lineage

from valorant_ai_coach.hud.layout import HudLayout
from valorant_ai_coach.recordings.catalog import RecordingCatalog
from valorant_ai_coach.temporal.evidence import native_time
from valorant_ai_coach.temporal.replay import SourcePolicy, file_sha, read_json, write_private


def collect_crops(image, bounds, row, rng):
    left, top, right, bottom = bounds
    center = np.asarray(row["selection"]["support_center_frame_px"])
    peaks = [np.asarray(candidate["center_frame_px"]) for candidate in row["pool"]]
    used = set()
    result = []

    def put(kind, label, candidate, max_texture=None):
        x, y = map(round, candidate)
        if not left + 12 <= x < right - 12 or not top + 12 <= y < bottom - 12 or (x, y) in used:
            return False
        patch = image[y - 12 : y + 13, x - 12 : x + 13].copy()
        if max_texture is not None and np.std(patch[5:-5, 5:-5], axis=(0, 1)).max() > max_texture:
            return False
        used.add((x, y))
        result.append((kind, label, [x, y], patch))
        return True

    if not put("positive", "recorder_weak", center):
        return result
    for other in peaks:
        if np.linalg.norm(other - center) > 30 and put("negative", "competing_peak", other):
            break
    low, high = [left + 15, top + 15], [right - 15, bottom - 15]
    for point in rng.integers(low, high, size=(8, 2)):
        if min(np.linalg.norm(point - p) for p in [*peaks, center]) >= 36 and put(
            "background", "empty_background_weak", point, 8
        ):
            break
    for point in rng.integers(low, high, size=(4, 2)):
        if np.linalg.norm(point - center) > 36 and put("negative", "nonrecorder_region", point):
            break
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in (
        "recording-catalog",
        "view-context",
        "replay-report",
        "source-policy",
        "layout",
        "output-directory",
    ):
        parser.add_argument("--" + name, type=Path, required=True)
    parser.add_argument("--method", required=True)
    parser.add_argument("--max-positive", type=int, default=2000)
    args = parser.parse_args()
    if args.max_positive < 1:
        parser.error("Positive crop budget must be positive")
    cv2.setNumThreads(1)
    os.umask(0o077)
    out = args.output_directory.resolve()
    if any((parent / ".git").exists() for parent in (out, *out.parents)):
        parser.error("Private crops must remain outside Git checkouts")
    catalog = RecordingCatalog(args.recording_catalog)
    report = read_json(args.replay_report)
    context = read_json(args.view_context)
    if context["formal_outputs"] != 0 or report["formal_outputs"] != 0:
        parser.error("Unqualified Map replay and view context required")
    (rec,) = (
        r for r in catalog.state.recordings.values() if r.source_sha256 == context["source_sha256"]
    )
    if rec.split != "DEVELOPMENT" or rec.learning["split"] != "TRAIN":
        raise ValueError("Map training requires a registered DEVELOPMENT / TRAIN source")
    catalog.guard([rec.recording_id], "training")
    if report["physical_source"] != rec.source_sha256:
        raise ValueError("Map training replay and view context must use the same source")
    auth = SourcePolicy(read_json(args.source_policy))
    receipt = Path(context["receipt_path"])
    if file_sha(receipt) != context["receipt_sha256"]:
        raise ValueError("Map crop acquisition receipt hash mismatch")
    meta = read_json(receipt)
    if not meta["native_pts_parity"] or not meta["verified_source_before_after"]:
        raise ValueError("Map crops require verified original recording and native PTS")
    files = dict(meta["frames"])
    by_id = {row["sample"]["sample_sha256"]: row for row in context["rows"]}
    layout = HudLayout.load(args.layout)
    frames = {}
    lineage = {kind: [] for kind in CATEGORIES}
    patches = {kind: [] for kind in CATEGORIES}
    rng = np.random.default_rng(663)
    traces = [
        r
        for r in report["modes"][args.method]["traces"]
        if r["projected"] is not None
        and r["selection"]["selection_status"] == "RESEARCH_SELECTED"
        and r["selection"]["support_count"] >= 2
    ]
    last = None
    for row in traces:
        s = row["sample"]
        key = s["sample_sha256"]
        view = by_id[key]
        at = native_time(s)
        if (
            view["camera"] != "SELF"
            or view["life"] != "ALIVE"
            or not view["view_fp"]
            or view["veto"]
            or (last is not None and at - last < Fraction(2, 5))
        ):
            continue
        auth.admit(s)
        data_bytes = Path(files[s["native_pts_tick"]]).read_bytes()
        if hashlib.sha256(data_bytes).hexdigest() != s["acquired_frame_sha256"]:
            raise ValueError("Map crop frame bytes differ from the native observation")
        im = cv2.imdecode(np.frombuffer(data_bytes, np.uint8), cv2.IMREAD_COLOR)
        if im is None or hashlib.sha256(im.tobytes()).hexdigest() != s["native_pixel_sha256"]:
            raise ValueError("Map crop decoded pixels differ from the native observation")
        if im.shape[1] != 1920:
            continue
        bounds = layout.normalized_roi("minimap_normal").pixel_bounds(im.shape[1], im.shape[0])
        for kind, label, center, patch in collect_crops(im, bounds, row, rng):
            frames[key] = s
            patches[kind].append(patch)
            lineage[kind].append(
                {
                    "sample_sha256": key,
                    "label": label,
                    "center": center,
                    "timeline_observation_ids": view.get("observation_ids", []),
                    "patch_sha256": hashlib.sha256(patch.tobytes()).hexdigest(),
                }
            )
            if kind == "positive":
                last = at
        if len(patches["positive"]) >= args.max_positive:
            break
    if not all(patches.values()):
        raise ValueError("The replay must supply positive, negative and background crops")
    out.mkdir(mode=0o700, parents=True, exist_ok=False)
    archive = out / "crops_PRIVATE.npz"
    np.savez_compressed(archive, **{name: np.stack(a) for name, a in patches.items()})
    trace = out / "crop_lineage_PRIVATE.json"
    write_private(
        trace,
        {
            "schema": SCHEMA,
            "samples": frames,
            "source_sha256": rec.source_sha256,
            "native_receipt_sha256": context["receipt_sha256"],
            "rows": lineage,
        },
    )
    with np.load(archive, allow_pickle=False) as arrays:
        load_crop_lineage(trace, file_sha(trace), rec.source_sha256, arrays)
    write_private(
        out / "training_record_PRIVATE.json",
        {
            "recording_id": rec.recording_id,
            "source_sha256": rec.source_sha256,
            "recorder_agent_uuid": report["recording_agent_uuid"],
            "patches": str(archive),
            "sha256": file_sha(archive),
            "lineage": str(trace),
            "lineage_sha256": file_sha(trace),
        },
    )
    print({name: len(a) for name, a in patches.items()}, flush=True)


if __name__ == "__main__":
    main()
