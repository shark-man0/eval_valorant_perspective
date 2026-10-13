"""Combine explicit private source candidates into one review page, never GT.

No video decoding, recognizer, evaluator, profile or validation pack is used.
Input hashes and selected source images are verified before creating output.
"""
from __future__ import annotations

import argparse
import html
import json
import math
from pathlib import Path

from scripts.e2e.run_dataset_case import sha256_file
from valorant_ai_coach.hud.calibrate_temporal import _check_output_privacy


def _finite_time(value: object) -> bool:
    return (isinstance(value, (int, float)) and not isinstance(value, bool)
            and math.isfinite(value) and value >= 0)


def assemble(candidate_paths: list[Path], evidence_paths: list[Path]) -> dict:
    if not candidate_paths or not evidence_paths:
        raise ValueError("explicit candidates and evidence required")
    sources = {}
    identity = None
    for path in evidence_paths:
        record = json.loads(path.read_text(encoding="utf-8"))
        if (record.get("kind") != "source_overview_not_gt"
                or record.get("recognizer_outputs_consulted") is not False
                or record.get("source_hash_verified_after_extraction") is not True):
            raise ValueError("verified source-only evidence required")
        current = (record["video_id"], record["source_video_sha256"])
        if identity is not None and current != identity:
            raise ValueError("source identity mismatch")
        identity = current
        digest = sha256_file(path)
        if digest in sources:
            raise ValueError("duplicate evidence manifest")
        frames = {}
        for frame in record["frames"]:
            time = frame["source_frame_pts"]
            if not _finite_time(time) or time in frames:
                raise ValueError("invalid or duplicate source PTS")
            frames[time] = frame
        sources[digest] = (path.resolve(), frames)

    rows, inputs, seen = [], [], set()
    for path in candidate_paths:
        record = json.loads(path.read_text(encoding="utf-8"))
        if (record.get("production_input") is not False
                or record.get("approved_ground_truth") is not False
                or record.get("review_provenance", {}).get(
                    "recognizer_outputs_consulted") is not False):
            raise ValueError("unapproved source-only candidates required")
        if (record["video_id"], record["source_video_sha256"]) != identity:
            raise ValueError("source identity mismatch")
        digests = [record["review_evidence_sha256"]]
        if "prefix_review_evidence_sha256" in record:
            digests.append(record["prefix_review_evidence_sha256"])
        if any(digest not in sources for digest in digests):
            raise ValueError("candidate manifest binding unavailable")
        candidate_hash = sha256_file(path)
        inputs.append({"sha256": candidate_hash, "file": path.name})
        for item in record["items"]:
            time = item.get("candidate_time_sec")
            kind = item.get("evidence_type", item.get("event_type"))
            key = (item["round_id"], kind)
            if (item.get("event_time_sec") is not None
                    or item.get("approved_ground_truth", False) is not False
                    or (time is not None and not _finite_time(time))
                    or not isinstance(kind, str) or key in seen):
                raise ValueError("invalid, approved or duplicate candidate")
            seen.add(key)
            points = item.get("evidence")
            if points is None:
                points = [{"source_frame_pts": pts} for pts in item["evidence_pts"]]
            if not points:
                raise ValueError("candidate evidence is empty")
            links, times = [], set()
            for point in points:
                pts = point["source_frame_pts"]
                if not _finite_time(pts) or pts in times:
                    raise ValueError("invalid or duplicate candidate PTS")
                times.add(pts)
                matches = [(digest, *sources[digest], sources[digest][1][pts])
                           for digest in digests if pts in sources[digest][1]]
                if not matches:
                    raise ValueError("candidate PTS absent from bound evidence")
                expected = point.get("evidence_frame_hash")
                if expected is not None:
                    matches = [match for match in matches
                               if match[3]["evidence_frame_sha256"] == expected]
                if (not matches or len({match[3]["evidence_frame_sha256"]
                                        for match in matches}) != 1):
                    raise ValueError("candidate image binding mismatch or ambiguity")
                digest, manifest, _, frame = matches[0]
                image = (manifest.parent / frame["image"]).resolve()
                if (not image.is_relative_to(manifest.parent)
                        or sha256_file(image) != frame["evidence_frame_sha256"]):
                    raise ValueError("source image integrity failed")
                links.append({"source_frame_pts": pts,
                              "evidence_frame_sha256": frame["evidence_frame_sha256"],
                              "evidence_manifest_sha256": digest,
                              "image_uri": image.as_uri()})
            if time is not None and time not in times:
                raise ValueError("candidate time must reference a bound source frame")
            rows.append({"round_id": item["round_id"], "evidence_type": kind,
                         "candidate_time_sec": time, "event_time_sec": None,
                         "approved_ground_truth": False,
                         "continuity_status": "not_independently_verified",
                         "candidate_input_sha256": candidate_hash,
                         "notes": item.get("notes", ""), "evidence": links})
    rows.sort(key=lambda row: min(p["source_frame_pts"] for p in row["evidence"]))
    return {"kind": "private_boundary_review_batch_not_gt",
            "video_id": identity[0], "source_video_sha256": identity[1],
            "production_input": False, "approved_ground_truth": False,
            "recognizer_outputs_consulted": False, "inputs": inputs, "items": rows}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidate", type=Path, action="append", required=True)
    parser.add_argument("--evidence", type=Path, action="append", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    output = args.output.resolve()
    _check_output_privacy(output)
    if output.exists():
        raise FileExistsError("use a new private output directory")
    report = assemble(args.candidate, args.evidence)
    cards = []
    for row in report["items"]:
        images = " ".join(
            f'<a href="{html.escape(p["image_uri"], quote=True)}">'
            f'PTS {p["source_frame_pts"]}<br><img loading="lazy" width="480" '
            f'src="{html.escape(p["image_uri"], quote=True)}"></a>'
            for p in row["evidence"])
        cards.append(f'<li><h2>{html.escape(row["round_id"])} — '
                     f'{html.escape(row["evidence_type"])}: '
                     f'{row["candidate_time_sec"]}</h2>'
                     f'<p>{html.escape(row["notes"])}</p>{images}</li>')
    page = ('<!doctype html><meta charset="utf-8"><h1>Private candidates — NOT GT</h1>'
            '<p>All candidates remain unapproved. Images do not prove continuity, '
            'player ownership or production qualification. Review may approve only '
            'explicitly checked items; no automatic approval or GT is generated.</p><ol>'
            + ''.join(cards) + '</ol>')
    output.mkdir(parents=True)
    (output / "review_batch.json").write_text(
        json.dumps(report, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    (output / "index.html").write_text(page, encoding="utf-8")
    print(f'Prepared {len(report["items"])} private candidates; no GT approved')


if __name__ == "__main__":
    main()
