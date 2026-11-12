"""Observed UI occlusion candidates, without phase/life/camera authority."""

from __future__ import annotations

import csv
import io
import math
import re
import subprocess
from pathlib import Path
from typing import Any

import cv2
import numpy as np

from valorant_ai_coach.hud import templates as text_templates
from valorant_ai_coach.hud.templates import TesseractTextReader

from .evidence import digest
from .replay import file_sha

VERSION = "development_HUD_visibility_v1"


def classify_words(words: list[dict[str, Any]], ui: dict[str, Any]) -> dict[str, Any]:
    """UI words identify a candidate overlay; they never identify a recorder."""
    accepted = []
    for word in words:
        confidence = word.get("confidence")
        if (isinstance(confidence, (float, int)) and not isinstance(confidence, bool)
                and math.isfinite(confidence) and .85 <= confidence <= 1
                and isinstance(word.get("text"), str)):
            accepted.append(word)
    text = re.sub(r"[\s\W_]", "", "".join(w["text"] for w in accepted)).upper()
    tracker_brand = any(s in text for s in ["VALORANTTRACKER", "TRACKERNETWORK"])
    tracker_nav = any(s in text for s in ["LIVEMATCH", "HIDESHOWAPP", "MATCHHISTORY"])
    menu_categories = [s for s in ["サイドアーム", "サブマシンガン", "ライフル",
                                  "スナイパー", "防具",
                                  "SIDEARMS", "SMGS", "RIFLES", "SNIPERS", "ARMOR"] if s in text]
    close = ui.get("buy_menu_close_anchor_present") is True
    close_confidence = ui.get("buy_menu_close_anchor_present_confidence", 0)
    menu = (close and type(close_confidence) in (float, int)
            and math.isfinite(close_confidence) and .90 <= close_confidence <= 1
            and len(menu_categories) >= 2)
    candidates = []
    if menu:
        candidates.append({"kind": "BUY_MENU", "reason": "current_close_anchor_and_menu_words",
                           "word_matches": menu_categories})
    if tracker_brand and tracker_nav:
        candidates.append({"kind": "TRACKER", "reason": "current_brand_and_navigation_words"})
    return {"schema": VERSION, "status": "CANDIDATES" if candidates else "UNKNOWN",
            "candidates": candidates, "accepted_words": accepted, "unknown_possible": True,
            "absence_proven": False, "phase_authority": False, "life_authority": False,
            "camera_authority": False, "Map_authority": False, "qualified": False}


class HUDVisibilityReader:
    """Fixed center/header ROI and existing OCR languages; no Source/time inputs."""

    def __init__(
        self, tessdata: Path, *, language: str = "jpn+eng",
        normalized_roi: tuple[float, float, float, float] = (.12, .08, .90, .46),
    ) -> None:
        x1, y1, x2, y2 = normalized_roi
        if not (0 <= x1 < x2 <= 1 and 0 <= y1 < y2 <= 1):
            raise ValueError("Normalized visible OCR region required")
        self.reader = TesseractTextReader(language=language, tessdata_dir=str(tessdata), psm=11)
        if self.reader.diagnostics or self.reader.executable is None:
            raise ValueError("Available configured UI OCR languages required")
        assets = {name: file_sha(tessdata / (name + ".traineddata"))
                  for name in language.split("+")}
        self.bindings: dict[str, Any] = {"schema": VERSION,
                         "OCR_binary_sha256": file_sha(Path(self.reader.executable)),
                         "languages": language, "language_assets_sha256": assets,
                         "code_sha256": file_sha(Path(__file__)),
                         "text_reader_code_sha256": file_sha(Path(text_templates.__file__)),
                         "normalized_roi": list(normalized_roi), "word_floor": .85,
                         "Source_time_roster_initialization_inputs": False}
        self.fingerprint = digest(self.bindings)

    def inspect(self, image: np.typing.NDArray[np.uint8], ui: dict[str, Any]) -> dict[str, Any]:
        if (image.ndim != 3 or image.dtype != np.uint8 or image.shape[2] != 3
                or min(image.shape[:2]) <= 0):
            raise ValueError("Native BGR pixels required")
        h, w = image.shape[:2]
        x1, y1, x2, y2 = self.bindings["normalized_roi"]
        crop = image[round(y1*h):round(y2*h), round(x1*w):round(x2*w)]
        gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
        ok, encoded = cv2.imencode(".png", cv2.resize(gray, None, fx=2, fy=2))
        if not ok:
            raise ValueError("UI OCR encoding failed")
        words = []
        error = None
        try:
            result = subprocess.run([self.reader.executable or "tesseract", "stdin", "stdout",
                "--tessdata-dir", self.reader.tessdata_dir or "", "-l", self.reader.language,
                "--psm", "11", "-c", "tessedit_create_tsv=1"], input=encoded.tobytes(),
                capture_output=True, check=True, timeout=5)
            for row in csv.DictReader(io.StringIO(result.stdout.decode("utf-8")), delimiter="\t"):
                if row["level"] != "5" or not row["text"].strip():
                    continue
                confidence = float(row["conf"])/100
                if not math.isfinite(confidence) or not 0 <= confidence <= 1:
                    raise ValueError("Invalid UI OCR word confidence")
                words.append({"text": row["text"].strip(), "confidence": confidence,
                              "native_roi_box": [float(row[k])/2 for k in
                                                 ["left", "top", "width", "height"]]})
        except (OSError, subprocess.SubprocessError, ValueError, KeyError) as exc:
            words, error = [], type(exc).__name__
        observation = classify_words(words, ui)
        observation.update(analysis_performed=error is None, error=error, words=words,
                           normalized_roi=self.bindings["normalized_roi"])
        return observation


def visibility_summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Application metadata only: never reinterpret an UNKNOWN game state."""
    evidence = []
    candidates = []
    for row in rows:
        measurement = row["raw"].get("hud_visibility")
        if measurement is None:
            continue
        if (not isinstance(measurement, dict) or measurement.get("schema") != VERSION
                or measurement.get("qualified") is not False
                or any(measurement.get(k) is not False for k in
                       ["phase_authority", "life_authority", "camera_authority", "Map_authority"])):
            raise ValueError("Advisory HUD visibility measurement required")
        evidence.append({"evidence_ref": row["observation_id"],
                         "sample_ref": row["sample"]["sample_sha256"], "measurement": measurement})
        for candidate in measurement["candidates"]:
            if candidate.get("kind") not in {"BUY_MENU", "TRACKER"}:
                raise ValueError("Known HUD visibility candidate required")
            candidates.append({**candidate, "evidence_ref": row["observation_id"]})
    return {"status": "CANDIDATES" if candidates else "UNKNOWN", "analysis_present": bool(evidence),
            "candidates": candidates, "native_observations": evidence,
            "reason": "observed_UI_context_only" if evidence else "NOT_ANALYSED",
            "unknown_possible": True, "recorder_ownership": "UNKNOWN", "qualified": False}
