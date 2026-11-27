"""Write a Map report bound exactly to one repaired canonical timeline (development only).

Inputs, all private and outside the checkout:

* ``--index``: compact index of the canonical timeline from ``index_timeline.py``
  (its ``input_sha256`` is the SHA-256 of the full ``timeline_PRIVATE.json``);
* ``--decode``: the ``decode_minimap.py`` output directory (``done/*.json`` rows and
  ``crops/<sample>.png`` minimap crops of frames whose pixels matched the timeline);
* ``--map-report`` and ``--atlas``: the Map library report of the same source and the
  reference image its coordinates use (only needed for ``map_library_rim``);
* ``--zones``: optional Zone polygons (``{"maps": [...]}``) on that reference.

The report is ``development_recorder_map_path_v1`` with ``timeline_sha256`` set to the
canonical file, so ``load_map_timeline`` reads it unchanged. Nothing is promoted.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import tempfile
import time
from collections import defaultdict
from pathlib import Path
from typing import Any

import cv2
import numpy as np

from valorant_ai_coach.temporal.evidence import freeze_native_sample
from valorant_ai_coach.temporal.map_canonical_pass import (
    ROI_1080P,
    FrameInput,
    RegistrationModes,
    build_report,
    measure_frame,
    own_live_samples,
)
from valorant_ai_coach.temporal.map_recorder_path import ReferenceZones, join_recorder_seconds
from valorant_ai_coach.temporal.public_map_pixels import PublicMapPixels

LAYOUT = Path(__file__).resolve().parents[2] / "config" / "hud_layout_1080p_v3.json"


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_crops(decode: Path) -> tuple[dict[str, dict[str, Any]], str]:
    rows: dict[str, dict[str, Any]] = {}
    digest = hashlib.sha256()
    for path in sorted((decode / "done").glob("*.json"), key=lambda p: int(p.stem)):
        data = path.read_bytes()
        digest.update(data)
        for row in json.loads(data):
            rows[row["sample_sha256"]] = row
    return rows, digest.hexdigest()


def library_points(report: dict[str, Any]) -> dict[int, list[dict[str, Any]]]:
    by_tick: dict[int, list[dict[str, Any]]] = defaultdict(list)
    for segment in report.get("segments", []):
        for point in segment:
            sample = point["sample"]
            if sample["native_time_base"] != "1/15360":
                continue
            by_tick[int(sample["native_pts_tick"])].append(point)
    return by_tick


def single_atlas_projector(
    atlas: Path, map_id: str,
) -> tuple[PublicMapPixels, tempfile.TemporaryDirectory[str]]:
    folder = tempfile.TemporaryDirectory()
    root = Path(folder.name)
    (root / "atlas.png").write_bytes(atlas.read_bytes())
    (root / "index.json").write_text(json.dumps({
        "catalog_version": "canonical_pass_single_reference",
        "maps": [{"id": map_id, "name": map_id, "reference": "atlas.png"}],
    }), encoding="utf-8")
    return PublicMapPixels(root / "index.json", LAYOUT), folder


def frame_fit(projector: PublicMapPixels, roi: np.ndarray) -> np.ndarray | None:
    canvas = np.zeros((1080, 1920, 3), np.uint8)
    left, top, right, bottom = ROI_1080P
    canvas[top:bottom, left:right] = roi
    raw = projector.inspect_exact(canvas)["raw"]
    candidates = raw["map_name_candidates"]
    if len(candidates) != 1 or candidates[0]["fit_residual_p95_reference_px"] > 8:
        return None
    return np.asarray(candidates[0]["reference_to_roi_homography_candidate"], dtype=float)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--index", type=Path, required=True)
    parser.add_argument("--decode", type=Path, required=True)
    parser.add_argument("--map-report", type=Path, required=True)
    parser.add_argument("--atlas", type=Path, required=True)
    parser.add_argument("--zones", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--no-library", action="store_true",
                        help="Measure the self ring only (comparison run)")
    parser.add_argument("--records", type=Path, help="Also write per-frame readings here")
    args = parser.parse_args(argv)
    started = time.monotonic()
    index = json.loads(args.index.read_text(encoding="utf-8"))
    timeline = {"version": index["version"], "qualification": index["qualification"],
                "formal_outputs": index["formal_outputs"], "source": index["source"],
                "seconds": index["seconds"], "native_frames": index["native_frames"]}
    source = timeline["source"]["source_sha256"]
    crops, receipt_sha = load_crops(args.decode)
    report = json.loads(args.map_report.read_text(encoding="utf-8"))
    points = library_points(report)
    map_ids = {(p["map_id"], p["reference_sha256"]) for rows in points.values() for p in rows}
    if len(map_ids) != 1:
        raise SystemExit(f"One Map reference expected in the library report, found {map_ids}")
    map_id, reference_sha = next(iter(map_ids))
    if _sha(args.atlas) != reference_sha:
        raise SystemExit("The atlas is not the library report's reference image")
    projector, holder = single_atlas_projector(args.atlas, map_id)
    atlas = cv2.imread(str(args.atlas), cv2.IMREAD_UNCHANGED)
    reference_size = (int(atlas.shape[1]), int(atlas.shape[0]))

    own = own_live_samples(timeline)
    inputs: dict[str, FrameInput] = {}
    fits: dict[str, np.ndarray] = {}
    missing_pixels = 0
    for key in own:
        row = crops.get(key)
        if row is None or not row["pixel_identical"]:
            missing_pixels += 1
            continue
        sample = freeze_native_sample(timeline["native_frames"][key]["sample"])
        if sample["source_sha256"] != source or row["native_pts_tick"] != sample["native_pts_tick"]:
            raise SystemExit("Decode rows do not belong to this timeline")
        roi = cv2.imread(str(args.decode / "crops" / f"{key}.png"), cv2.IMREAD_COLOR)
        if roi is None or hashlib.sha256(roi.tobytes()).hexdigest() != row["roi_pixel_sha256"]:
            raise SystemExit(f"Canonical crop changed: {key}")
        fit = frame_fit(projector, roi)
        if fit is not None:
            fits[key] = fit
        library = () if args.no_library else tuple(points.get(sample["native_pts_tick"], ()))
        inputs[key] = FrameInput(sample, roi, row["roi_pixel_sha256"], fit, library)
    modes = RegistrationModes.from_fits(map_id, reference_sha, atlas, fits.values())
    records = {key: measure_frame(item, modes, reference_size=reference_size)
               for key, item in inputs.items()}
    zones = []
    if args.zones is not None:
        zones = [ReferenceZones(z["map_id"], z["reference_sha256"], z["polygons"])
                 for z in json.loads(args.zones.read_text(encoding="utf-8"))["maps"]
                 if z["map_id"] == map_id and z["reference_sha256"] == reference_sha]
    result = build_report(
        timeline, index["input_sha256"], records, modes, zones=zones,
        receipt_sha256=receipt_sha,
        provenance={
            "recording_id": timeline["source"].get("source_id"),
            "source_sha256": source,
            "map_library_report_sha256": _sha(args.map_report),
            "map_library_points_used": not args.no_library,
            "atlas_sha256": reference_sha,
            "zone_catalog_sha256": _sha(args.zones) if args.zones else None,
            "own_live_frames": len(own),
            "own_live_frames_without_identical_pixels": missing_pixels,
            "frame_fits": len(fits),
            "elapsed_seconds": round(time.monotonic() - started, 1),
        },
    )
    if join_recorder_seconds(result, timeline) != result["second_rows"]:
        raise SystemExit("Second rows do not match the canonical samples")
    args.output.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    args.output.write_text(json.dumps(result, separators=(",", ":")), encoding="utf-8")
    os.chmod(args.output, 0o600)
    if args.records is not None:
        args.records.write_text(json.dumps(records, separators=(",", ":")), encoding="utf-8")
    holder.cleanup()
    print(json.dumps(result["canonical_pass"]["counts"]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
