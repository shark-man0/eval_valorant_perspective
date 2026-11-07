"""Opt-in research candidate for the on-screen Credits display.

The bottom-right display is read from a frozen, source-blind ROI profile. Its
geometry is not independently calibrated and its value is never attributed to
the recorder or a spectated player. It cannot supply game-state signals.
"""

from __future__ import annotations

import importlib
import math
import re
import subprocess
from copy import deepcopy
from pathlib import Path
from typing import Any

import numpy as np
from numpy.typing import NDArray

from valorant_ai_coach.hud.templates import TesseractDigitsReader

from .evidence import digest
from .hud_values import VERSION as VALUE_SCHEMA
from .replay import file_sha, read_json

SCHEMA = "development_credits_display_v1"
_TEXT = re.compile(r"(?:0|[1-9][0-9]{0,2}|[1-9][0-9]?,[0-9]{3})\Z")


def _box(value: Any) -> tuple[int, int, int, int]:
    if (
        not isinstance(value, list)
        or len(value) != 4
        or any(type(v) is not int for v in value)
        or min(value[:2]) < 0
        or min(value[2:]) <= 0
    ):
        raise ValueError("Credits ROI requires nonnegative integer xywh")
    return value[0], value[1], value[2], value[3]


def default_language_binding(executable: str) -> dict[str, str]:
    """Resolve Tesseract's effective default data rather than assume a host path."""
    result = subprocess.run(
        [executable, "--list-langs"], capture_output=True, timeout=5, check=True
    )
    text = (result.stdout + result.stderr).decode("utf-8", errors="strict")
    match = re.search(r'List of available languages in "([^"\n]+)"', text)
    if match is None:
        raise ValueError("Effective Credits OCR language directory cannot be bound")
    asset = Path(match.group(1)) / "eng.traineddata"
    if not asset.is_file():
        raise ValueError("Default English Credits OCR language asset required")
    return {"language": "eng", "traineddata_sha256": file_sha(asset)}


class CreditsCandidateReader:
    """OCR one bounded number; preserve every rejection as UNKNOWN evidence."""

    def __init__(self, profile: dict[str, Any]) -> None:
        if (
            set(profile)
            != {
                "method",
                "frame_size_px",
                "roi_xywh_native",
                "digits_xywh_relative",
                "minimum_ocr_confidence",
            }
            or profile["method"] != SCHEMA
            or profile["minimum_ocr_confidence"] != 0.90
        ):
            raise ValueError("Frozen research Credits profile required")
        size = profile["frame_size_px"]
        if (
            not isinstance(size, list)
            or len(size) != 2
            or any(type(v) is not int or not 64 <= v <= 4096 for v in size)
        ):
            raise ValueError("Explicit Credits reference frame size required")
        self.frame_size = tuple(size)
        self.roi = _box(profile["roi_xywh_native"])
        self.digits = _box(profile["digits_xywh_relative"])
        if (
            self.roi[0] + self.roi[2] > size[0]
            or self.roi[1] + self.roi[3] > size[1]
            or self.digits[0] + self.digits[2] > self.roi[2]
            or self.digits[1] + self.digits[3] > self.roi[3]
        ):
            raise ValueError("Credits OCR crop must remain inside the frozen frame ROI")
        self.ocr = TesseractDigitsReader(psm=7, whitelist="0123456789,")
        self.profile = deepcopy(profile)

    def measure(self, image: NDArray[np.uint8]) -> dict[str, Any]:
        result: dict[str, Any] = {
            "name": "credits",
            "value": None,
            "status": "UNKNOWN",
            "reason": "frame_geometry_unmatched",
            "reader_roi": "credits_display",
            "confidence": None,
            "sources": [],
            "cross_checked": False,
            "subject": "screen_credits_display; actor_ownership_unresolved",
            "value_scope": "displayed_credits_unattributed",
            "roi_geometry_qualification": "unqualified_fixed_profile",
        }
        if image.ndim not in (2, 3) or image.shape[1::-1] != self.frame_size:
            return result
        x, y, _, _ = self.roi
        dx, dy, dw, dh = self.digits
        crop = image[y + dy : y + dy + dh, x + dx : x + dx + dw]
        read = self.ocr.read(image, crop)
        result.update(
            raw_ocr_text=read.value,
            confidence=read.confidence,
            sources=list(read.sources),
            digit_roi_xywh_native=[x + dx, y + dy, dw, dh],
        )
        if (
            not isinstance(read.confidence, (float, int))
            or isinstance(read.confidence, bool)
            or not math.isfinite(read.confidence)
        ):
            result["reason"] = "invalid_ocr_confidence"
            return result
        if read.confidence < 0.90:
            result["reason"] = "ocr_below_fixed_threshold"
            return result
        if not isinstance(read.value, str) or _TEXT.fullmatch(read.value) is None:
            result["reason"] = "numeric_format_unresolved"
            return result
        number = int(read.value.replace(",", ""))
        if not 0 <= number <= 9999:
            result["reason"] = "out_of_display_range"
            return result
        result.update(value=number, status="CANDIDATE", reason="bounded_display_ocr")
        return result


class CreditsSupplementObserver:
    """Append Credits research evidence to an existing observer without state claims."""

    def __init__(self, path: Path) -> None:
        cfg = read_json(path)
        if set(cfg) != {"parent_observer", "parent_config", "credits_profile"}:
            raise ValueError("Explicit parent and separate Credits profile required")
        module, name = cfg["parent_observer"].split(":")
        self.parent = getattr(importlib.import_module(module), name)(Path(cfg["parent_config"]))
        profile_path = Path(cfg["credits_profile"])
        self.reader = CreditsCandidateReader(read_json(profile_path))
        executable = self.reader.ocr.executable
        if executable is None:
            raise ValueError("Configured Credits OCR executable required")
        self.bindings = {
            "schema": "development_credits_supplement_v1",
            "parent": self.parent.bindings,
            "parent_fingerprint": self.parent.fingerprint,
            "credits_profile_sha256": file_sha(profile_path),
            "credits_code_sha256": file_sha(Path(__file__)),
            "OCR_binary_sha256": file_sha(Path(executable)),
            "OCR_default_language": default_language_binding(executable),
            "state_authority": False,
            "field": "credits",
        }
        self.credits_fingerprint = digest(
            {k: v for k, v in self.bindings.items() if k not in {"parent", "parent_fingerprint"}}
        )
        parent_suppliers = self.parent.bindings.get(
            "supplier_producer_fingerprints", [self.parent.fingerprint]
        )
        self.bindings.update(
            baseline_producer_fingerprints=list(parent_suppliers),
            supplier_producer_fingerprints=[*parent_suppliers, self.credits_fingerprint],
        )
        self.fingerprint = digest(self.bindings)

    def inspect_credits(self, image: NDArray[np.uint8]) -> dict[str, Any]:
        measurement = self.reader.measure(image)
        return {
            "signals": [],
            "map_candidates": [],
            "context": {
                "stream_kind": "hud_values",
                "profile_fingerprint": self.bindings["credits_profile_sha256"],
            },
            "raw": {
                "schema": VALUE_SCHEMA,
                "value_reader_method": SCHEMA,
                "hud_value_measurements": [measurement],
                "ownership": "UNKNOWN",
                "formal_outputs": 0,
            },
        }

    def inspect(self, image: NDArray[np.uint8]) -> dict[str, Any]:
        original: dict[str, Any] = self.parent.inspect(image)
        result = deepcopy(original)
        suppliers = result.get("supplier_observations")
        if suppliers is None:
            suppliers = [
                {
                    k: deepcopy(v)
                    for k, v in original.items()
                    if k in {"signals", "raw", "context", "map_candidates"}
                }
            ]
            suppliers[0]["producer_fingerprint"] = self.parent.fingerprint
        result["supplier_observations"] = suppliers + [
            {**self.inspect_credits(image), "producer_fingerprint": self.credits_fingerprint}
        ]
        return result
