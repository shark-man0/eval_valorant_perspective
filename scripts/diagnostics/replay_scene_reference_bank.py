"""Replay descriptive background support with archived actual phase/display outputs.

Images are scored first in the bound bank report. Numeric/phase annotations do
not select references or score correspondence. Never creates runtime evidence.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path

from scripts.diagnostics.ui_transition_contract import TransientUiDiagnostic


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bank-report", type=Path, required=True)
    parser.add_argument("--source-report", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        parser.error("output exists")
    inputs = {
        str(p): p.read_bytes()
        for p in (
            args.bank_report,
            args.source_report,
            Path(__file__),
            Path(__file__).with_name("ui_transition_contract.py"),
        )
    }
    bank = json.loads(inputs[str(args.bank_report)])
    source = json.loads(inputs[str(args.source_report)])
    if bank["source_video_sha256"] != source["source_video_sha256"]:
        raise ValueError("different source videos")
    hashes = {p: hashlib.sha256(data).hexdigest() for p, data in inputs.items()}
    if hashes[str(args.source_report)] != bank["file_sha256"][str(args.source_report)]:
        raise ValueError("source annotation binding changed")
    results = []
    for window in bank["sets"]:
        model = TransientUiDiagnostic()
        annotated = source["windows"][window["window_index"]]["rows"]
        if len(annotated) != len(window["rows"]):
            raise ValueError("native coverage mismatch")
        rows = []
        previous_pixel = None
        for image_row, annotation in zip(window["rows"], annotated, strict=True):
            if (
                image_row["source_pts_ticks"] != annotation["source_pts_ticks"]
                or image_row["source_pixel_sha256"] != annotation["source_pixel_sha256"]
            ):
                raise ValueError("source join mismatch")
            row = model.advance(
                image_row["pts_sec"],
                phase_confirmed=annotation["phase_confirmed"],
                display=annotation["timer_display"],
                scene_supported=image_row["link_supported_descriptive"],
                duplicate_pixels=image_row["source_pixel_sha256"] == previous_pixel,
            )
            rows.append(row)
            previous_pixel = image_row["source_pixel_sha256"]
        results.append(
            {
                "window_index": window["window_index"],
                "rows": rows,
                "state_counts": dict(Counter(r["state"] for r in rows)),
                "raw_display_history": model.display_history,
            }
        )
    if any(Path(path).read_bytes() != data for path, data in inputs.items()):
        raise ValueError("terminal input/code binding changed")
    report = {
        "scope": "Descriptive bank temporal replay; archived observed readers, no qualification",
        "source_video_sha256": bank["source_video_sha256"],
        "input_sha256": hashes,
        "sets": results,
        "production_changed": False,
        "runtime_events_created": 0,
        "qualification_created": False,
        "canonical_current": None,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps([r["state_counts"] for r in results]))


if __name__ == "__main__":
    main()
