"""Source-bound recorder/visible-agent association, never qualified ownership.

A reviewed roster supplies the recorder's agent independently of minimap pixels.
Current ability glyphs supply one correlated agent-evidence family. This cannot
prove the account currently controlling that agent, and never promotes SELF.
"""

from __future__ import annotations

import hashlib
import json
import re
from typing import Any

import numpy as np
from numpy.typing import NDArray

from valorant_ai_coach.video.geometry import normalized_roi_bounds

from .development_actor_alias import DevelopmentActorAlias
from .development_view import DevelopmentViewVeto


def _sha(value: Any) -> bool:
    return isinstance(value, str) and re.fullmatch(r"[0-9a-f]{64}", value) is not None


class DevelopmentRecorderView:
    """Bounded, current-frame glyph measurements with explicit source binding.

    Two matching glyphs corroborate an agent signature, not two independent
    identity votes. Incomplete vocabularies, shared/remote views and matching
    another account's agent remain reasons not to claim recorder ownership.
    """

    def __init__(self) -> None:
        self._matchers = [DevelopmentViewVeto() for _ in range(96)]
        self.alias = DevelopmentActorAlias()

    def inspect(
        self, frame: NDArray[Any], spec: Any, *, minimap_roi: Any,
        source_id: str, source_sha256: str | None, acquisition_id: str,
    ) -> dict[str, Any]:
        result: dict[str, Any] = {
            "qualification": "development_only", "ownership": "UNKNOWN",
            "status": "disabled", "association": "UNKNOWN", "visible_agent_candidate": None,
            "block_position_candidate": False, "reference_fingerprint": None,
            "recorder_identity_qualified": False, "scores": [],
            "reasons": ["recorder_agent_binding_unavailable"],
        }
        if spec is None:
            return result
        result.update(status="unavailable", block_position_candidate=True)
        if (not isinstance(frame, np.ndarray) or frame.dtype != np.uint8 or frame.ndim != 3
                or frame.shape[2] != 3 or min(frame.shape[:2]) <= 0
                or not isinstance(spec, dict) or spec.get("mode") != "agent_binding_v1"
                or spec.get("frame_size_px") != [frame.shape[1], frame.shape[0]]):
            return result
        binding = spec.get("binding")
        if (not isinstance(binding, dict) or not _sha(source_sha256)
                or binding.get("source_sha256") != source_sha256
                or binding.get("source_id") != source_id
                or not isinstance(source_id, str) or not source_id
                or not isinstance(binding.get("physical_match_id"), str)
                or not binding["physical_match_id"]
                or binding.get("review_kind") != "human_source_roster"
                or not _sha(binding.get("anchor_frame_sha256"))
                or not _sha(binding.get("review_sha256"))
                or not isinstance(binding.get("acquisition_ids"), list)
                or not isinstance(acquisition_id, str) or not acquisition_id
                or acquisition_id not in binding["acquisition_ids"]
                or not isinstance(binding.get("recorder_agent_id"), str)
                or not binding["recorder_agent_id"]):
            return result
        size = frame.shape[1], frame.shape[0]
        minimap = normalized_roi_bounds(minimap_roi, *size)
        slots, references = spec.get("slots"), spec.get("agents")
        if (minimap is None or not isinstance(slots, list) or not 2 <= len(slots) <= 4
                or not isinstance(references, list) or not 2 <= len(references) <= 8):
            return result
        bounds = [normalized_roi_bounds(s, *size) for s in slots]
        if any(b is None for b in bounds):
            return result
        boxes = [b for b in bounds if b is not None]
        for i, box in enumerate(boxes):
            for other in [minimap, *boxes[:i]]:
                if not (box[2] <= other[0] or other[2] <= box[0]
                        or box[3] <= other[1] or other[3] <= box[1]):
                    return result
        names = []
        for agent in references:
            if not isinstance(agent, dict) or not isinstance(agent.get("agent_id"), str):
                return result
            paths = agent.get("templates")
            if (not agent["agent_id"] or agent["agent_id"] in names
                    or not isinstance(paths, list) or len(paths) != len(slots)
                    or any(not isinstance(p, list) or not 1 <= len(p) <= 3 for p in paths)):
                return result
            names.append(agent["agent_id"])
        if binding["recorder_agent_id"] not in names:
            return result
        alias = self.alias.inspect(
            frame, spec.get("actor_alias"), minimap_roi=minimap_roi,
            recorder_alias=binding.get("recorder_alias"),
        )
        scores, hashes, index = [], [], 0
        for agent in references:
            glyphs = []
            for slot, paths in zip(slots, agent["templates"], strict=True):
                measurements = []
                for path in paths:
                    measurement = self._matchers[index].inspect(frame, {
                        "mode": "spectator_switch_v1", "roi": slot,
                        "reference_frame_size_px": list(size), "template_path": path,
                    })
                    index += 1
                    hashes.append(measurement["reference_sha256"])
                    if measurement["status"] == "unavailable":
                        return {**result, "reasons": ["configured_agent_reference_unavailable"]}
                    measurements.append(measurement["similarity"])
                glyphs.append(max(measurements))
            # At least two distinct, disjoint glyphs, with an explicit runner margin.
            scores.append({"agent_id": agent["agent_id"], "glyph_scores": glyphs,
                           "score": sorted(glyphs, reverse=True)[1]})
        scores.sort(key=lambda s: s["score"], reverse=True)
        first, runner = scores[:2]
        matched = first["score"] >= .90 and first["score"]-runner["score"] >= .12
        candidate = first["agent_id"] if matched else None
        same = candidate == binding["recorder_agent_id"]
        fingerprint = hashlib.sha256(json.dumps(
            {"spec": spec, "reference_sha256": hashes,
             "alias_activation_sha256": alias.get("activation_reference_sha256")},
            sort_keys=True).encode("utf-8")).hexdigest()
        return {
            **result, "status": "observed", "scores": scores,
            "association": "recorder_agent_supported" if same else
                           "different_agent_supported" if matched else "UNKNOWN",
            "visible_agent_candidate": candidate,
            "block_position_candidate": (matched and not same) or alias["block_position_candidate"],
            "actor_alias_evidence": alias,
            "reference_fingerprint": fingerprint,
            "binding_review_sha256": binding["review_sha256"],
            "anchor_frame_sha256": binding["anchor_frame_sha256"],
            "evidence_family": "current_ability_glyphs", "independent_of_minimap_pixels": True,
            "positive_agent_association": same,
            "reasons": ["human_recorder_agent_binding_and_current_glyphs" if same else
                        "different_agent_glyphs" if matched else "agent_signature_unknown",
                        "agent_association_is_not_current_account_ownership",
                        "open_agent_vocabulary_not_qualified"],
        }
