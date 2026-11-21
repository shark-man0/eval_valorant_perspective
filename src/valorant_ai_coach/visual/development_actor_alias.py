"""Optional, positively activated actor-name slot; not an ownership recognizer."""

from __future__ import annotations

import hashlib
import math
from typing import Any

import numpy as np
from numpy.typing import NDArray

from valorant_ai_coach.hud.readers import TextOcrReader
from valorant_ai_coach.hud.templates import TesseractTextReader
from valorant_ai_coach.video.geometry import normalized_roi_bounds

from .development_view import DevelopmentViewVeto


class DevelopmentActorAlias:
    """Read a reviewed name slot only after its current-frame chrome matches.

    An alias may be nonunique, anonymized or OCR-corrupted. Even an exact match
    is unqualified support only; a spectated-player slot never proves self.
    The optional OCR engine and its existing thresholds are reused read-only.
    """

    def __init__(self, reader: TextOcrReader | None = None) -> None:
        self.reader = reader
        self.activation = DevelopmentViewVeto()

    def inspect(
        self, frame: NDArray[Any], spec: Any, *, minimap_roi: Any, recorder_alias: Any,
    ) -> dict[str, Any]:
        result: dict[str, Any] = {
            "qualification": "development_only", "ownership": "UNKNOWN", "status": "disabled",
            "alias_association": "UNKNOWN", "observed_alias": None,
            "block_position_candidate": False, "current_account_identity_qualified": False,
        }
        if spec is None:
            return result
        result.update(status="unavailable", block_position_candidate=True)
        if (not isinstance(frame, np.ndarray) or frame.ndim != 3 or frame.shape[2] != 3
                or frame.dtype != np.uint8 or not isinstance(spec, dict)
                or spec.get("frame_size_px") != [frame.shape[1], frame.shape[0]]
                or spec.get("slot_review") != "source_reviewed_not_qualified"
                or spec.get("slot_kind") not in {
                    "spectated_player_name", "current_actor_identifier"}
                or not isinstance(recorder_alias, str) or not 1 <= len(recorder_alias) <= 64):
            return result
        size = frame.shape[1], frame.shape[0]
        minimap = normalized_roi_bounds(minimap_roi, *size)
        name = normalized_roi_bounds(spec.get("name_roi"), *size)
        activation = spec.get("activation")
        if not isinstance(activation, dict):
            return result
        chrome = normalized_roi_bounds(activation.get("roi"), *size)
        if minimap is None or name is None or chrome is None:
            return result
        for box in (name, chrome):
            if (not (box[2] <= minimap[0] or minimap[2] <= box[0]
                     or box[3] <= minimap[1] or minimap[3] <= box[1])
                    or (box[2]-box[0])*(box[3]-box[1]) > 250_000):
                return result
        observed = self.activation.inspect(frame, activation)
        if observed["status"] == "unavailable":
            return {**result, "reason": "configured_name_slot_activation_unavailable"}
        result.update(activation_reference_sha256=observed["reference_sha256"],
                      activation_similarity=observed["similarity"])
        if observed["veto"] is not True:
            return {**result, "status": "not_detected", "block_position_candidate": False,
                    "reason": "name_slot_not_positively_activated"}
        if self.reader is None:
            self.reader = TesseractTextReader(language="eng")
        left, top, right, bottom = name
        text = self.reader.read(frame, frame[top:bottom, left:right])
        valid_confidence = (isinstance(text.confidence, (int, float))
                            and not isinstance(text.confidence, bool)
                            and math.isfinite(text.confidence) and 0 <= text.confidence <= 1)
        known = (isinstance(text.value, str) and bool(text.value.strip())
                 and valid_confidence and text.confidence >= .90)
        alias = text.value.strip() if known and text.value is not None else None
        same = alias == recorder_alias
        spectator = spec["slot_kind"] == "spectated_player_name"
        return {
            **result, "status": "observed", "observed_alias": alias,
            "ocr_confidence": text.confidence if valid_confidence else None,
            "ocr_sources": list(text.sources),
            "alias_association": "alias_matches_recorder" if same else
                                 "different_alias_supported" if known else "UNKNOWN",
            "block_position_candidate": spectator or (known and not same),
            "positive_current_alias_support": same and not spectator,
            "slot_kind": spec["slot_kind"],
            "current_name_pixels_sha256": hashlib.sha256(
                frame[top:bottom, left:right].tobytes()).hexdigest(),
            "reason": "spectator_slot_is_not_recorder_view" if spectator else
                      "display_alias_is_not_qualified_account_identity",
        }
