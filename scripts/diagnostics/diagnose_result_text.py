"""Frozen local result-text OCR on hash-bound native development frames.

No expected states, timestamps, round IDs or Validation Pack enter recognition.
Recognized text is not a qualified round-end event, including at a content cut.
"""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

import cv2

from scripts.diagnostics.diagnose_round_lifecycle import sha256_file
from valorant_ai_coach.hud.calibrate_temporal import _check_output_privacy
from valorant_ai_coach.hud.layout import HudLayout, NormalizedRoi
from valorant_ai_coach.hud.templates import TesseractTextReader

VOCABULARY = frozenset({"TEAM ACE", "VICTORY", "DEFEAT", "FLAWLESS", "THRIFTY", "ACE"})
REPORT_VOCABULARY = frozenset({"ラウンドが進行中", "アビリティー"})


def accepted_result(text: str | None, confidence: float) -> str | None:
    if (not isinstance(text, str) or type(confidence) not in (int, float)
            or not math.isfinite(confidence) or not .90 <= confidence <= 1):
        return None
    normalized = " ".join(text.upper().split())
    return normalized if normalized in VOCABULARY else None


def accepted_report_text(text: str | None, confidence: float) -> str | None:
    if (not isinstance(text, str) or type(confidence) not in (int, float)
            or not math.isfinite(confidence) or not .90 <= confidence <= 1):
        return None
    # Japanese TSV tokenization inserts spaces. Remove spacing only, never
    # replace a character or interpret missing text as a different report mode.
    normalized = "".join(text.split())
    return normalized if normalized in REPORT_VOCABULARY else None


def load_method(path: Path) -> dict:
    raw = json.loads(path.read_bytes())
    valid_role = (
        raw.get("version") == "semantic_result_ocr_diagnostic_v1"
        and raw.get("language") == "eng"
        or raw.get("version") == "combat_report_text_ocr_diagnostic_v1"
        and raw.get("language") == "jpn" and raw.get("roi") == "combat_report"
    )
    if (not valid_role or type(raw.get("psm")) is not int
            or raw["psm"] != 7 or type(raw.get("minimum_confidence")) not in (int, float)
            or raw["minimum_confidence"] != .90
            or not isinstance(raw.get("roi"), str)
            or raw.get("preprocessing", "gray_v1") not in {
                "gray_v1", "white210_v1", "white210_horizontal2_v1"
            }):
        raise ValueError("unsupported frozen result-text method")
    bounds = raw.get("subregion_norm")
    if (not isinstance(bounds, list) or len(bounds) != 4
            or any(type(v) not in (int, float) or not math.isfinite(v) for v in bounds)
            or not 0 <= bounds[0] < bounds[2] <= 1
            or not 0 <= bounds[1] < bounds[3] <= 1):
        raise ValueError("invalid configured text subregion")
    return raw


def run(video: Path, native_run: Path, layout_path: Path, method_path: Path,
        output_dir: Path, tessdata_dir: Path) -> dict:
    _check_output_privacy(output_dir.resolve() / "results.json")
    reader_implementation = Path(__file__).parents[2] / "src/valorant_ai_coach/hud/templates.py"
    paths = (video, native_run / "results.json", layout_path, method_path,
             Path(__file__), reader_implementation)
    hashes = [sha256_file(path) for path in paths]
    source = json.loads(paths[1].read_bytes())
    if (source.get("native_pts_coverage_verified") is not True
            or source.get("source_video_sha256") != hashes[0]
            or not source.get("windows")):
        raise ValueError("verified native source frames and matching video required")
    method = load_method(method_path)
    layout = HudLayout.load(layout_path)
    roi = layout.normalized_roi(method["roi"])
    reader = TesseractTextReader(language=method["language"], psm=method["psm"],
                                tessdata_dir=str(tessdata_dir))
    if reader.diagnostics:
        raise ValueError("configured OCR unavailable: " + ",".join(reader.diagnostics))
    report_role = method["version"] == "combat_report_text_ocr_diagnostic_v1"
    model_path = tessdata_dir / f"{method['language']}.traineddata"
    model_hash = sha256_file(model_path)
    executable_path = Path(reader.executable)
    executable_hash = sha256_file(executable_path)
    output_dir.mkdir(parents=True, exist_ok=False)
    freeze = {
        "scope": __doc__, "source_video_sha256": hashes[0],
        "native_diagnostic_sha256": hashes[1], "layout_sha256": hashes[2],
        "method_sha256": hashes[3], "method": method,
        "diagnostic_implementation_sha256": hashes[4],
        "reader_implementation_sha256": hashes[5],
        "executable_sha256": executable_hash,
        "trained_language_sha256": model_hash,
        "vocabulary": sorted(REPORT_VOCABULARY if report_role else VOCABULARY),
        "text_role": "combat_report" if report_role else "result",
        "qualification_created": False,
        "events_emitted": 0, "profile_adopted": False,
        "geometry_assumed": "configured reference ROI; diagnostic only",
    }
    (output_dir / "selection.json").write_text(json.dumps(freeze, indent=2) + "\n")
    windows = []
    for window_index, window in enumerate(source["windows"]):
        results = []
        if len(window["rows"]) < 2:
            raise ValueError("at least two native frames per declared window required")
        previous_pts = None
        for index, row in enumerate(window["rows"], 1):
            pts = row["pts_sec"]
            if (type(pts) not in (int, float) or not math.isfinite(pts)
                    or previous_pts is not None and pts <= previous_pts):
                raise ValueError("finite increasing native source PTS required")
            previous_pts = pts
            path = native_run / f"window-{window_index:03d}" / f"frame_{index:06d}.png"
            if sha256_file(path) != row["frame_sha256"]:
                raise ValueError("native frame hash mismatch")
            image = cv2.imread(str(path))
            if image is None:
                raise ValueError("native frame unreadable")
            x1, y1, x2, y2 = roi.pixel_bounds(image.shape[1], image.shape[0])
            crop = image[y1:y2, x1:x2]
            left, top, right, bottom = method["subregion_norm"]
            sub = NormalizedRoi(left, top, right - left, bottom - top)
            a, b, c, d = sub.pixel_bounds(crop.shape[1], crop.shape[0])
            text_crop = crop[b:d, a:c]
            preprocessing = method.get("preprocessing", "gray_v1")
            if preprocessing in {"white210_v1", "white210_horizontal2_v1"}:
                gray = cv2.cvtColor(text_crop, cv2.COLOR_BGR2GRAY)
                _, text_crop = cv2.threshold(gray, 210, 255, cv2.THRESH_BINARY_INV)
                if preprocessing == "white210_horizontal2_v1":
                    text_crop = cv2.resize(text_crop, (text_crop.shape[1] * 2, text_crop.shape[0]),
                                           interpolation=cv2.INTER_NEAREST)
            result = reader.read(image, text_crop)
            if sha256_file(path) != row["frame_sha256"]:
                raise ValueError("native frame changed during OCR")
            results.append({
                "pts_sec": pts, "frame_sha256": row["frame_sha256"],
                "text": result.value, "reader_confidence": result.confidence,
                "sources": result.sources,
                "accepted_result_text": (
                    None if report_role else accepted_result(result.value, result.confidence)
                ),
                "accepted_report_text": (
                    accepted_report_text(result.value, result.confidence) if report_role else None
                ),
                "round_end_emitted": False,
            })
        windows.append({"window_sec": window["window_sec"], "rows": results})
    if (hashes != [sha256_file(path) for path in paths]
            or sha256_file(model_path) != model_hash
            or sha256_file(executable_path) != executable_hash):
        raise ValueError("diagnostic input changed during OCR")
    report = {**freeze, "windows": windows}
    (output_dir / "results.json").write_text(json.dumps(report, indent=2) + "\n")
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("video", "native-run", "layout", "method", "output-dir", "tessdata-dir"):
        parser.add_argument(f"--{name}", type=Path, required=True)
    args = parser.parse_args()
    report = run(args.video, args.native_run, args.layout, args.method, args.output_dir,
                 args.tessdata_dir)
    print(json.dumps({"frames": sum(len(w["rows"]) for w in report["windows"]),
                      "accepted_texts": sum(r["accepted_result_text"] is not None
                                            or r["accepted_report_text"] is not None
                                            for w in report["windows"] for r in w["rows"]),
                      "events_emitted": 0, "qualification_created": False}))


if __name__ == "__main__":
    main()
