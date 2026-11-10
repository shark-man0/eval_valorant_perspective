"""Image-only native phase/result, barrier and viewed-Zone observations."""

from __future__ import annotations

import hashlib
import importlib
import re
from copy import deepcopy
from pathlib import Path
from typing import Any

import cv2
import numpy as np
from numpy.typing import NDArray

from .evidence import digest
from .hud_visibility import HUDVisibilityReader
from .replay import file_sha, read_json

VERSION = "development_screen_cues_v1"


def classify_screen_words(words: list[dict[str, Any]]) -> dict[str, Any]:
    """Unique match-result wording is distinct from a Round WON/LOST card."""
    accepted = [w for w in words if isinstance(w.get("confidence"), (int, float))
                and .85 <= w["confidence"] <= 1 and isinstance(w.get("text"), str)]
    tokens = [re.sub(r"[^A-Z0-9ぁ-んァ-ヶー一-龯]", "", w["text"].upper()) for w in accepted]
    text = "".join(tokens)
    buy = "BUYPHASE" in text or "購入フェーズ" in text
    result = next((w for w in ("VICTORY", "DEFEAT") if w in tokens), None)
    if result is None and any(s in text for s in ("マッチ結果", "対戦結果", "MATCHRESULTS")):
        result = "RESULT_SCREEN"
    ending = next((w for w in ("WON", "LOST") if w in tokens), None)
    return {"buy_caption": buy, "round_result": ending,
            "match_result": {"visible": result is not None, "outcome_candidate": result,
                             "basis": "observed_unique_match_result_words",
                             "qualified": False},
            "accepted_words": accepted, "unknown_possible": True}


def zone_words(words: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Transport read location text; do not claim map geometry or recorder role."""
    accepted = [w for w in words if isinstance(w.get("confidence"), (int, float))
                and .85 <= w["confidence"] <= 1 and isinstance(w.get("text"), str)]
    result = []
    groups: dict[int, list[dict[str, Any]]] = {}
    for w in accepted:
        box = w.get("native_roi_box", [0, 0, 0, 0])
        groups.setdefault(round(float(box[1]) / 10), []).append(w)
    for values in groups.values():
        values.sort(key=lambda w: w.get("native_roi_box", [0])[0])
        text = "".join(w["text"] for w in values).strip()
        normalized = re.sub(r"\s+", "", text)
        if re.search(r"^[ABC](?:サイト|ロング|ショート|リンク|メイン|ロビー|ガレージ|タワー|"
                     r"ホール|ヘブン|トンネル|ベント|ツリー|ランプ|窓|ドア|中庭|通路|小屋)$",
                     normalized, re.IGNORECASE) or re.search(
                     r"^[ABC](?:SITE|LONG|SHORT|LINK|MAIN|LOBBY|GARAGE|TOWER|HALL|"
                     r"HEAVEN|TUNNEL|VENT|TREE|RAMP|WINDOW|DOOR|COURTYARD|HUT)$",
                     normalized, re.IGNORECASE):
            result.append({"zone_name": text, "raw_display": text,
                           "basis": "current_HUD_location_text", "map_name": None,
                           "position_subject": "viewed_actor_candidate_not_recorder",
                           "ownership": "UNKNOWN", "qualified": False})
    return result


def barrier_pixels(image: NDArray[np.uint8]) -> dict[str, Any]:
    """Measure a broad pale-blue world veil, excluding HUD and weapon regions.

    A measurement alone never starts a Round. The shared owner compares its loss
    with the prior observed veil, current BUY contradictions and map visibility.
    """
    h, w = image.shape[:2]
    hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
    roi = hsv[round(.22*h):round(.60*h), round(.28*w):round(.85*w)]
    pale_blue = ((roi[:, :, 0] >= 90) & (roi[:, :, 0] <= 125)
                 & (roi[:, :, 1] >= 12) & (roi[:, :, 1] <= 110)
                 & (roi[:, :, 2] >= 140))
    fraction = float(pale_blue.mean())
    map_roi = image[round(.05*h):round(.40*h), round(.02*w):round(.25*w)]
    edges = cv2.Canny(cv2.cvtColor(map_roi, cv2.COLOR_BGR2GRAY), 70, 140)
    signature = cv2.resize(edges, (32, 32), interpolation=cv2.INTER_AREA)
    return {"pale_blue_fraction": fraction, "present": fraction >= .35,
            "not_detected": fraction < .08,
            "map_signature": signature.flatten().tolist(),
            "map_view_supported": .015 <= float((edges > 0).mean()) <= .35,
            "normalized_world_roi": [.28, .22, .85, .60],
            "roi_pixel_sha256": hashlib.sha256(roi.tobytes()).hexdigest(),
            "meaning": "barrier_appearance_candidate_not_phase_or_continuity_proof",
            "qualified": False}


class ScreenCueObserver:
    """Wrap the existing native observer; no Source/time/roster enters inspect."""

    def __init__(self, config_path: Path) -> None:
        cfg = read_json(config_path)
        if set(cfg) != {"parent_observer", "parent_config", "tessdata"}:
            raise ValueError("Explicit native parent and local OCR assets required")
        module, name = cfg["parent_observer"].split(":", 1)
        self.parent = getattr(importlib.import_module(module), name)(Path(cfg["parent_config"]))
        self.phase = HUDVisibilityReader(Path(cfg["tessdata"]),
                                        normalized_roi=(.35, .14, .65, .25))
        self.result = HUDVisibilityReader(Path(cfg["tessdata"]), language="eng",
                                         normalized_roi=(.31, .40, .69, .59))
        self.zone = HUDVisibilityReader(Path(cfg["tessdata"]),
                                        normalized_roi=(.015, 0, .25, .075))
        self.cue_fingerprint = digest({"code_sha256": file_sha(Path(__file__)),
                                       "phase_reader": self.phase.bindings,
                                       "result_reader": self.result.bindings,
                                       "zone_reader": self.zone.bindings,
                                       "opencv": cv2.__version__})
        self.bindings = {"schema": VERSION, "parent": self.parent.bindings,
                         "parent_fingerprint": self.parent.fingerprint,
                         "screen_fingerprint": self.cue_fingerprint,
                         "config_sha256": file_sha(config_path),
                         "baseline_producer_fingerprints": self.parent.bindings.get(
                             "baseline_producer_fingerprints", [self.parent.fingerprint]),
                         "supplier_producer_fingerprints": [
                             *self.parent.bindings.get("supplier_producer_fingerprints",
                                                       [self.parent.fingerprint]),
                             self.cue_fingerprint]}
        self.fingerprint = digest(self.bindings)

    def inspect(self, image: NDArray[np.uint8]) -> dict[str, Any]:
        result: dict[str, Any] = deepcopy(self.parent.inspect(image))
        suppliers = result.get("supplier_observations")
        if suppliers is None:
            suppliers = [{k: deepcopy(result.get(k, {} if k in {"raw", "context"} else []))
                          for k in ("signals", "raw", "context", "map_candidates")}]
            suppliers[0]["producer_fingerprint"] = self.parent.fingerprint
        ui: dict[str, Any] = next((r["raw"]["ui"] for r in suppliers
                   if isinstance(r["raw"].get("ui"), dict)), {})
        visibility = self.phase.inspect(image, ui)
        ending = self.result.inspect(image, ui)
        location = self.zone.inspect(image, ui)
        cues = classify_screen_words(visibility["words"] + ending["words"])
        cues["barrier"] = barrier_pixels(image)
        cues["analysis_performed"] = visibility["analysis_performed"]
        signals = ["buy"] if cues["buy_caption"] else []
        if cues["round_result"]:
            signals.append("result")
        suppliers.append({"producer_fingerprint": self.cue_fingerprint,
                          "signals": signals, "map_candidates": [],
                          "context": {"stream_kind": "screen_cues"},
                          "raw": {"schema": "development_generic_map_pixels_v1",
                                  "method": VERSION, "screen_cues": cues,
                                  "hud_visibility": visibility,
                                  "result_OCR": ending,
                                  "zone_candidates": zone_words(location["words"]),
                                  "zone_OCR": location,
                                  "dependency_group": "current_screen_pixels",
                                  "ownership": "UNKNOWN", "qualified": False}})
        result["supplier_observations"] = suppliers
        result["signals"] = sorted(set(result["signals"]) | set(signals))
        return result
