"""Image-reader UI association proposals, not qualified recorder ownership.

The roster describes a recording, not which marker to choose. A current ability
signature and visible HP form one HUD evidence family; a distinct minimap rim
measurement selects the candidate ID. A spectator/name-slot contradiction vetoes
the association. This is an automatic, testable *research hypothesis*, not an
account identity proof. No absence-of-spectator-only SELF fallback exists.
"""

from __future__ import annotations

import math
from typing import Any

from valorant_ai_coach.hud.readers import TextOcrReader
from valorant_ai_coach.hud.templates import TesseractTextReader

from .development_identity_metrics import marker_binding_matches
from .development_marker_features import Array, _digest
from .development_marker_topk import _native
from .self_marker import MarkerReferenceInspector


class DevelopmentOwnerAppearance:
    """Contrast existing recorder-agent references at current UI candidates."""

    def __init__(self) -> None:
        self.inspector = MarkerReferenceInspector()

    def inspect(
        self,
        frame: Array,
        sample: dict[str, Any],
        pool: dict[str, Any],
        *,
        spec: dict[str, Any],
        binding: dict[str, Any] | None,
        roster: dict[str, Any],
    ) -> dict[str, Any]:
        frozen = _native(frame, sample)
        left, top, width, height = pool["roi_xywh"]
        measured = self.inspector.inspect(frame[top : top + height, left : left + width], spec)
        supported = bool(
            binding is not None
            and marker_binding_matches(
                binding,
                source_id=frozen["source_id"],
                source_sha256=frozen["source_sha256"],
                recorder_agent_id=roster.get("recorder_agent_id"),
                reference_fingerprint=measured.get("reference_fingerprint"),
            )
        )
        consistent = []
        for i, point in enumerate(pool["candidates"][: pool["parent_count"]]):
            # Reuse the inspector's frozen .80 peak / .12 contrast policy.
            # A second, unrelated HUD glyph threshold would discard its output.
            if any(
                m["reference_category"] == "self_reference_appearance"
                and math.dist(
                    point["center_frame_px"],
                    (left + m["x_roi_norm"] * width, top + m["y_roi_norm"] * height),
                )
                <= 2
                for m in measured["matches"]
            ):
                consistent.append(i)
        return {
            "sample_sha256": frozen["sample_sha256"],
            "reference_source_agent_supported": supported,
            "consistent_indices": consistent if supported else [],
            "reference_measurements": measured,
            "ownership": "UNKNOWN",
            "qualification": "development_only",
            "formal_outputs": 0,
        }


class DevelopmentVisibleHp:
    """Reuse the existing optional OCR reader on a visible-subject HUD slot.

    HP can belong to a spectated subject. Neither HP>0 nor HP=0 determines
    recorder life, camera ownership or death. Unknown geometry stays unknown.
    """

    def __init__(self, reader: TextOcrReader | None = None) -> None:
        self.reader = reader

    def inspect(self, frame: Array, sample: dict[str, Any]) -> dict[str, Any]:
        frozen = _native(frame, sample)
        result: dict[str, Any] = {
            "sample_sha256": frozen["sample_sha256"],
            "value": None,
            "confidence": 0.0,
            "slot_role": "visible_subject_HP_not_recorder_proof",
            "qualification": "development_only",
            "ownership": "UNKNOWN",
        }
        if frozen["frame_size_px"] != [1920, 1080]:
            return {**result, "reason": "unsupported_HUD_geometry"}
        if self.reader is None:
            self.reader = TesseractTextReader(language="eng")
        value = self.reader.read(frame, frame[997:1052, 587:646])
        text = value.value
        valid = (
            isinstance(text, str)
            and text.isascii()
            and text.isdecimal()
            and 0 <= int(text) <= 100
            and value.confidence >= 0.90
        )
        return {
            **result,
            "value": int(text) if valid and text is not None else None,
            "confidence": value.confidence,
            "sources": list(value.sources),
            "native_roi_xywh": [587, 997, 59, 55],
            "reason": "visible_HP_observation" if valid else "HP_UNKNOWN",
        }


def propose_owner_marker_binding(
    *,
    sample: dict[str, Any],
    pool: dict[str, Any],
    ui: dict[str, Any],
    roster: dict[str, Any],
    hud: dict[str, Any],
    hp: dict[str, Any],
    spectator: dict[str, Any],
    appearance: dict[str, Any],
) -> dict[str, Any]:
    """The candidate ID comes exclusively from current image UI measurements.

    The caller verifies roster admission and the current native sample before
    invoking readers. Exact-frame human roles and marker IDs are not inputs.
    """
    key = sample["sample_sha256"]
    if (
        pool.get("sample") != sample
        or pool.get("ownership") != "UNKNOWN"
        or pool.get("formal_outputs") != 0
        or pool.get("pool_sha256") != _digest({k: v for k, v in pool.items() if k != "pool_sha256"})
        or any(x.get("sample_sha256") != key for x in (ui, hud, hp, spectator, appearance))
        or ui.get("pool_sha256") != pool["pool_sha256"]
    ):
        raise ValueError("Same-frame native candidate/UI/HUD bindings required")
    measurement = hud["measurement"]
    alias = measurement.get("actor_alias_evidence", {})
    spectating = spectator.get("status") == "spectator_ui" or (
        alias.get("slot_kind") == "spectated_player_name" and alias.get("status") == "observed"
    )
    result: dict[str, Any] = {
        "sample_sha256": key,
        "kind": "recorder_association_candidate",
        "marker_id": None,
        "candidate_index": None,
        "binding_origin": "none",
        "camera": "spectator" if spectating else "unknown",
        "life_evidence": "none",
        "recorder_account_identity_qualified": False,
        "qualification": "development_only",
        "ownership": "UNKNOWN",
        "formal_outputs": 0,
    }
    reasons = []
    if spectating:
        reasons.append("positive_spectator_UI_or_name_slot")
    if measurement.get("block_position_candidate") is True:
        reasons.append("HUD_subject_contradiction_or_unavailable")
    if (
        roster.get("review_kind") != "human_source_roster"
        or roster.get("source_id") != sample["source_id"]
        or roster.get("source_sha256") != sample["source_sha256"]
        or not roster.get("recorder_agent_id")
    ):
        reasons.append("source_recorder_roster_missing")
    if not (
        measurement.get("positive_agent_association") is True
        and measurement.get("visible_agent_candidate") == roster.get("recorder_agent_id")
        and measurement.get("recorder_agent_id") == roster.get("recorder_agent_id")
    ):
        reasons.append("current_recorder_agent_HUD_support_missing")
    if type(hp.get("value")) is not int or not 1 <= hp["value"] <= 100:
        reasons.append("current_visible_subject_alive_HP_unavailable")
    # Joint selection: a high-ranked Spike/highlight must not erase a lower
    # camera-rim candidate consistent with the observed recorder agent.
    eligible = [
        r
        for r in ui["rows"]
        if r["warm_rim_arc"] >= 0.15
        and r["radial_alignment"] >= 0.55
        and r["candidate_index"] in appearance.get("consistent_indices", [])
    ]
    eligible.sort(key=lambda r: (-r["score"], r["candidate_index"]))
    unique = bool(
        eligible and (len(eligible) == 1 or eligible[0]["score"] - eligible[1]["score"] >= 0.12)
    )
    index = eligible[0]["candidate_index"] if unique else None
    if appearance.get("reference_source_agent_supported") is not True:
        reasons.append("source_marker_reference_binding_missing")
    if index is None:
        reasons.append("unique_joint_marker_UI_and_appearance_missing")
    elif type(index) is not int or not 0 <= index < pool["parent_count"]:
        raise ValueError("Current existing marker candidate required")
    if reasons:
        return {
            **result,
            "reasons": reasons,
            "evidence_sha256": _digest(
                {
                    "sample": key,
                    "hud": hud,
                    "hp": hp,
                    "spectator": spectator,
                    "ui": ui,
                    "appearance": appearance,
                }
            ),
        }
    record = next(r for r in ui["rows"] if r["candidate_index"] == index)
    evidence = {
        "sample": sample,
        "pool_sha256": pool["pool_sha256"],
        "roster": roster,
        "hud": hud,
        "hp": hp,
        "spectator": spectator,
        "ui": ui,
        "appearance": appearance,
        "families": [
            "recording_roster",
            "current_HUD_agent_and_HP_one_family",
            "minimap_highlight_rim_geometry",
        ],
        "account_link": "UNQUALIFIED_ASSOCIATION_NOT_IDENTITY_PROOF",
    }
    return {
        **result,
        "marker_id": record["marker_observation_id"],
        "candidate_index": index,
        "binding_origin": "automatic_ui",
        "camera": "first_person_candidate",
        "life_evidence": "none",
        "visible_subject_alive": True,
        "evidence_sha256": _digest(evidence),
        "evidence": evidence,
        "reasons": [
            "source_roster_and_current_HUD_plus_unique_marker_UI",
            "development_association_requires_independent_evaluation",
        ],
    }
