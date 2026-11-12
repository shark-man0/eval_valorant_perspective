"""Stateless contracts for unqualified current-view HUD location measurements.

Only the common game engine may associate a viewed label with recorder state.
Names are symbolic display evidence, not geometric ZoneResolution or positions.
"""

from __future__ import annotations

import math
import unicodedata
from copy import deepcopy
from typing import Any

from .evidence import digest, freeze_native_sample, is_sha

MEASUREMENT_SCHEMA = "development_hud_zone_measurement_v1"
ZONE_KIND = "hud_location_label"
ZONE_CONTEXT_CONTRACT = "development_zone_context_v1"
MODES = ("gray_inverted", "bright_strokes_inverted")


def normalized_label(text: str) -> str:
    return "".join(unicodedata.normalize("NFKC", text).split())


def _number(value: Any) -> bool:
    return not isinstance(value, bool) and isinstance(value, (int, float)) and math.isfinite(value)


def validate_profile(profile: dict[str, Any]) -> None:
    size, roi = profile.get("frame_size_px"), profile.get("roi_xywh_native")
    if (
        not isinstance(size, list)
        or len(size) != 2
        or any(type(v) is not int or not 64 <= v <= 4096 for v in size)
        or not isinstance(roi, list)
        or len(roi) != 4
        or any(type(v) is not int for v in roi)
        or min(roi[:2]) < 0
        or min(roi[2:]) < 8
        or roi[0] + roi[2] > size[0]
        or roi[1] + roi[3] > size[1]
        or type(profile.get("scale")) is not int
        or not 1 <= profile["scale"] <= 8
        or type(profile.get("padding")) is not int
        or not 0 <= profile["padding"] <= 128
        or not _number(profile.get("minimum_word_confidence"))
        or profile["minimum_word_confidence"] != 0.90
        or profile.get("modes") != list(MODES)
        or not is_sha(profile.get("model_sha256"))
        or not is_sha(profile.get("binary_sha256"))
    ):
        raise ValueError("Bounded frozen location profile and fixed 0.90 confidence required")


def _validate_reading(reading: dict[str, Any], profile: dict[str, Any]) -> bool:
    if reading.get("valid_TSV_output") is not True or not is_sha(reading.get("tsv_sha256")):
        raise ValueError("Successful validated TSV output required; errors are not absence")
    words = reading.get("words")
    if not isinstance(words, list) or len(words) > 32:
        raise ValueError("Bounded measured word list required")
    scale, padding = profile["scale"], profile["padding"]
    width, height = profile["roi_xywh_native"][2:]
    text, confidence, inside = [], 1.0, True
    for word in words:
        token, score, box = word.get("text"), word.get("confidence"), word.get("bbox")
        if (
            not isinstance(token, str)
            or not 1 <= len(token) <= 64
            or not _number(score)
            or not 0 <= score <= 1
            or not isinstance(box, list)
            or len(box) != 4
            or any(type(v) is not int or v < 0 for v in box)
            or min(box[2:]) <= 0
        ):
            raise ValueError("Finite bounded OCR word measurements required")
        text.append(token)
        confidence = min(confidence, score)
        inside = inside and (
            box[0] > padding + scale
            and box[1] > padding + scale
            and box[0] + box[2] < padding + width * scale - scale
            and box[1] + box[3] < padding + height * scale - scale
        )
    label = normalized_label("".join(text))
    confidence = confidence if words else 0.0
    japanese = any("\u3040" <= c <= "\u30ff" or "\u3400" <= c <= "\u9fff" for c in label)
    passed = bool(words and 2 <= len(label) <= 32 and japanese and inside and confidence >= 0.90)
    if (
        reading.get("text") != label
        or reading.get("minimum_confidence") != confidence
        or reading.get("box_inside_roi") is not inside
        or reading.get("candidate_passed") is not passed
    ):
        raise ValueError("OCR decision must match original words, boxes and fixed threshold")
    return bool(passed)


def validate_measurement(record: dict[str, Any], profile: dict[str, Any]) -> None:
    validate_profile(profile)
    sample = freeze_native_sample(record["sample"])
    if (
        record["sample"] != sample
        or sample["frame_size_px"] != profile["frame_size_px"]
        or record.get("profile_sha256") != digest(profile)
        or record.get("roi_xywh_native") != profile["roi_xywh_native"]
        or record.get("qualification") != "development_only"
        or record.get("ownership") != "UNKNOWN"
        or record.get("position_subject") != "unassigned_viewed_actor"
        or record.get("formal_outputs") != 0
    ):
        raise ValueError("Exact native unassigned location measurement required")
    readings = record.get("measurements")
    if not isinstance(readings, list) or [r.get("mode") for r in readings] != list(MODES):
        raise ValueError("Two explicitly correlated rendering measurements required")
    passed = [_validate_reading(r, profile) for r in readings]
    accepted = all(passed) and readings[0]["text"] == readings[1]["text"]
    expected = readings[0]["text"] if accepted else None
    confidence = min(r["minimum_confidence"] for r in readings) if accepted else None
    if (
        record.get("status") != ("OBSERVED_LABEL_CANDIDATE" if accepted else "UNKNOWN")
        or record.get("zone_label_candidate") != expected
        or record.get("confidence") != confidence
    ):
        raise ValueError("Location candidate must match the measured correlated renderings")


def viewed_zone_candidate(row: dict[str, Any]) -> dict[str, Any] | None:
    raw = row["raw"]
    if raw.get("schema") != MEASUREMENT_SCHEMA:
        return None
    if (
        raw.get("qualification") != "development_only"
        or raw.get("ownership") != "UNKNOWN"
        or raw.get("formal_outputs") != 0
        or row["signals"]
        or row["map_candidates"]
        or raw.get("producer_fingerprint") != row["producer_fingerprint"]
        or row["context"].get("stream_kind") != "hud_zone"
    ):
        raise ValueError("Location observer cannot assert game state, ownership or markers")
    profile, record = raw["profile"], raw["measurement"]
    validate_measurement(record, profile)
    if record["sample"] != row["sample"] or row["context"].get("profile_fingerprint") != digest(
        profile
    ):
        raise ValueError("Location measurement belongs to another native sample/profile")
    if record["zone_label_candidate"] is None:
        return None
    result = {
        "kind": ZONE_KIND,
        "label_text": record["zone_label_candidate"],
        "confidence": record["confidence"],
        "observation_id": row["observation_id"],
        "sample": deepcopy(row["sample"]),
        "producer_fingerprint": row["producer_fingerprint"],
        "zone_subject": "unassigned_viewed_actor",
        "uncertainty": "correlated_OCR_unqualified",
        "map_position_norm": None,
        "zone_resolution": None,
        "ownership": "UNKNOWN",
        "qualification": "development_only",
        "formal_outputs": 0,
    }
    result["candidate_id"] = digest(result)
    return result
