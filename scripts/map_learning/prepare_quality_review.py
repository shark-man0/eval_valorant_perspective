"""Restore verified native pixels for fixed Map quality review cases."""

import argparse
from collections import defaultdict
from pathlib import Path

import cv2
import numpy as np

from valorant_ai_coach.recordings.catalog import RecordingCatalog
from valorant_ai_coach.temporal.camera_panel import decode_samples
from valorant_ai_coach.temporal.map_recorder_export import _pixels_match
from valorant_ai_coach.temporal.replay import file_sha, read_json, write_private


def prepare(a):
    audit, portfolio, handoff = (read_json(p) for p in (a.audit, a.portfolio, a.handoff))
    records = {r["index"]: r for r in handoff["recordings"]}
    reports = {}
    for r in portfolio["recordings"]:
        if file_sha(Path(r["candidate"]["path"])) != r["candidate"]["sha256"]:
            raise ValueError("The review portfolio changed")
        reports[r["index"]] = read_json(Path(r["candidate"]["path"]))
    wanted, cases = defaultdict(set), []
    counters = defaultdict(int)
    for case in audit["cases"]:
        kind = case["kind"]
        if kind not in {"trajectory_suspect", "control"}:
            continue
        counters[kind] += 1
        label = ("A" if kind == "trajectory_suspect" else "C") + f"{counters[kind]:02d}"
        refs = case.get("samples") or [case["sample_ref"]]
        cases.append({**case, "label": label, "samples": refs})
        wanted[case["index"]].update(refs)
    catalog = RecordingCatalog(Path(handoff["catalog"]))
    a.output.mkdir(parents=True, exist_ok=False, mode=0o700)
    missing = []
    for index, keys in wanted.items():
        row = records[index]
        rid = row["recording_id"]
        catalog.guard([rid], "development_analysis")
        rec = catalog.state.recordings[rid]
        if rec.split != "DEVELOPMENT":
            raise ValueError("Only DEVELOPMENT video can be reviewed")
        m = row["artifacts"]["native_frame_manifest"]
        if file_sha(Path(m["path"])) != m["sha256"]:
            raise ValueError("The original review observations changed")
        entries = {e["sample"]["sample_sha256"]: e for e in read_json(Path(m["path"]))["frames"]}
        samples = [entries[key]["sample"] for key in sorted(keys)]
        location = rec.locations.get("managed") or rec.locations["original"]
        video = catalog.local_path(location["path"])
        if file_sha(video) != rec.source_sha256:
            raise ValueError("Source video changed")
        catalog.record_exposure(rid, "development_use", "Map independent fixed quality review")
        for sample, frame in decode_samples(video, samples, missing):
            if not _pixels_match(frame, sample):
                raise ValueError("Review frame differs from original native pixels")
            key = sample["sample_sha256"]
            # Retain the native minimap crop without changing recognition results.
            crop = frame[:480, :550]
            (a.output / f"{key}.png").write_bytes(cv2.imencode(".png", crop)[1].tobytes())
        print("Native review acquisition completed:", index, flush=True)
    packets = []
    for case in cases:
        available = [key for key in case["samples"] if (a.output / f"{key}.png").exists()]
        case["available"] = available
        report = reports[case["index"]]
        selected = {p["sample"]["sample_sha256"]: p for s in report["segments"] for p in s}
        canvas = np.full((390, 800, 3), 24, np.uint8)
        cv2.putText(canvas, f"{case['label']} match {case['index']} {case['kind']}",
                    (8, 18), cv2.FONT_HERSHEY_SIMPLEX, .5, (255,255,255), 1)
        for n, key in enumerate(case["samples"]):
            path = a.output / f"{key}.png"
            x = n * 400
            if path.exists():
                image = cv2.imdecode(np.frombuffer(path.read_bytes(), np.uint8), 1)
                image = cv2.resize(image, (395, 345))
                canvas[24:369, x:x+395] = image
            else:
                cv2.putText(canvas, "UNKNOWN - pixels unavailable", (x+10, 80),
                            cv2.FONT_HERSHEY_SIMPLEX, .5, (0,150,255), 1)
            point = selected[key]
            cv2.putText(canvas, str([round(v, 1) for v in point["map_reference_px"]]),
                        (x+8, 385), cv2.FONT_HERSHEY_SIMPLEX, .5, (230,150,230), 1)
        destination = a.output / f"{case['label']}.jpg"
        destination.write_bytes(cv2.imencode(".jpg", canvas)[1].tobytes())
        packets.append({**case, "image": destination.name, "image_sha256": file_sha(destination)})
    for kind, prefix in (("trajectory_suspect", "A"), ("control", "C")):
        group = [row for row in packets if row["kind"] == kind]
        for start in range(0, len(group), 8):
            board = np.full((1560, 1600, 3), 24, np.uint8)
            for offset, row in enumerate(group[start:start+8]):
                image = cv2.imdecode(np.frombuffer((a.output/row["image"]).read_bytes(),
                                                  np.uint8), 1)
                x, y = (offset % 2)*800, (offset//2)*390
                board[y:y+390, x:x+800] = image
            (a.output/f"{prefix}_sheet_{start//8+1}.jpg").write_bytes(
                cv2.imencode(".jpg", board)[1].tobytes())
    write_private(a.output/"review_manifest_PRIVATE.json", {
        "schema": "development_map_native_quality_review_v1", "formal_outputs": 0,
        "audit_sha256": file_sha(a.audit), "portfolio_sha256": file_sha(a.portfolio),
        "cases": packets, "missing_samples": missing, "human_gt": False,
    })


def main():
    p = argparse.ArgumentParser(description=__doc__)
    for key in ("audit", "portfolio", "handoff", "output"):
        p.add_argument(f"--{key}", required=True, type=Path)
    a = p.parse_args()
    if any((v / ".git").exists() for v in a.output.resolve().parents):
        p.error("Keep review frames outside Git")
    prepare(a)


if __name__ == "__main__":
    main()
