"""HUD supplier handoff, not the common game-state engine or a Fact producer.

Packets preserve current image measurements and exact native evidence. A one-second
index is an address on the native clock, not a rounded or inferred event time.
"""
from __future__ import annotations

import hashlib
from collections.abc import Sequence
from copy import deepcopy
from dataclasses import asdict
from fractions import Fraction
from pathlib import Path
from typing import Any

from valorant_ai_coach.video.geometry import normalized_roi_bounds
from valorant_ai_coach.visual.development_learning_dataset import FrameRecord
from valorant_ai_coach.visual.development_marker_attribution import _sha, freeze_native_sample
from valorant_ai_coach.visual.development_marker_features import _digest

_VERSION = "development_hud_observations_v1"


def _sample(frame: FrameRecord, source_id: str) -> dict[str, Any]:
    frame.validate()
    return freeze_native_sample({
        "source_id": source_id, "source_sha256": frame.source_sha256,
        "acquisition_id": frame.acquisition_id, "native_epoch": frame.native_epoch,
        "native_pts_tick": frame.native_pts_tick, "native_time_base": frame.native_time_base,
        "acquired_frame_sha256": frame.frame_sha256,
        "native_pixel_sha256": frame.pixel_sha256,
    }, frame_size_px=frame.frame_size_px)


def _roi(value: Any, size: tuple[int, int]) -> list[int] | None:
    if value is None:
        return None
    if (not isinstance(value, (list, tuple)) or len(value) != 4
            or any(type(n) not in (int, float) for n in value)):
        raise ValueError("Explicit numeric normalized HUD ROI required")
    bounds = normalized_roi_bounds(value, *size)
    if bounds is None:
        raise ValueError("Explicit in-frame normalized HUD ROI required")
    left, top, right, bottom = bounds
    return [left, top, right - left, bottom - top]


def _packet(frame: FrameRecord, source_id: str, reader: str, profile: str,
            fields: list[dict[str, Any]], continuity: dict[str, Any]) -> dict[str, Any]:
    if not _sha(reader) or not _sha(profile):
        raise ValueError("Frozen reader and Profile fingerprints required")
    sample = _sample(frame, source_id)
    seconds = Fraction(frame.native_pts_tick) * Fraction(frame.native_time_base)
    payload = {
        "version": _VERSION, "sample": sample, "frame_contract": asdict(frame),
        "native_second_index": seconds.numerator // seconds.denominator,
        "reader_fingerprint": reader, "profile_fingerprint": profile,
        "adapter_fingerprint": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "measurements": deepcopy(fields), "continuity_observations": deepcopy(continuity),
        "semantic_source_continuity": "UNVERIFIED", "qualification": "development_only",
        "ownership": "UNKNOWN", "formal_events": [], "formal_outputs": 0, "qualified": False,
        "state_owner": "common_engine_not_this_supplier",
    }
    _digest(payload)  # Reject NaN/Infinity or non-JSON evidence, without coercion.
    return payload


def export_owner_ui(frame: FrameRecord, source_id: str, ui: dict[str, Any],
                    profile: dict[str, Any]) -> dict[str, Any]:
    """Project existing DevelopmentOwnerUI; never run its legacy timeline.

    The caller retains the original image/cache receipt and checks its pixels.
    A failed reader is UNKNOWN, not a reviewed negative or proof of UI absence.
    """
    sample = _sample(frame, source_id)
    if (ui.get("sample_sha256") != sample["sample_sha256"]
            or ui.get("qualified") is not False or type(ui.get("formal_outputs")) is not int
            or ui.get("formal_outputs") != 0
            or ui.get("source_profile_fingerprint") != _digest(profile)):
        raise ValueError("Current UI/Profile/exact native frame binding required")
    screen = ui.get("screen_measurements", {})
    probes = profile.get("development_ownership_evidence", {}).get("probes", [])
    cues = screen.get("observed_cues", [])
    if cues and (len(cues) != len(probes)
                 or any(c["claim"] != p["claim"] for c, p in zip(cues, probes, strict=True))):
        raise ValueError("Original reader probe order and Profile binding required")
    fields = []
    for cue, probe in zip(cues, probes, strict=False):
        fields.append({
            "name": cue["claim"], "status": cue["status"],
            "roi_xywh_px": _roi(probe.get("roi"), frame.frame_size_px),
            "roi_qualification": "author_profile_not_independent_calibration",
            "value": True if cue["status"] == "present" else None,
            "uncalibrated_score": cue.get("similarity"), "evidence": deepcopy(cue),
        })
    actor = profile.get("development_recorder_view", {})
    for name, value, roi in (
        ("ability_agent_signature", ui.get("agent_measurements", {}), None),
        ("spectator_controls", ui.get("spectator_measurements", {}),
         profile.get("development_view_veto", {}).get("roi")),
        ("spectated_subject_display", ui.get("spectated_subject_observation"),
         actor.get("actor_alias", {}).get("name_roi")),
    ):
        fields.append({
            "name": name, "status": value.get("status", "measured")
            if isinstance(value, dict) else "UNKNOWN",
            "roi_xywh_px": _roi(roi, frame.frame_size_px),
            "roi_qualification": "author_profile_not_independent_calibration",
            "value": deepcopy(value), "uncalibrated_score": value.get("similarity",
                value.get("ocr_confidence")) if isinstance(value, dict) else None,
            "evidence": {"glyph_rois_xywh_px": [
                _roi(r, frame.frame_size_px) for r in actor.get("slots", [])
            ]} if name == "ability_agent_signature" else {},
        })
    # False support is not a demonstrated negative ownership label. Unconfigured
    # death/remote/return observations stay explicit UNKNOWNs for the engine.
    for name, raw_key in (
        ("current_owner_hud_support", "own_hud_support"),
        ("current_spectator_support", "spectator_ui"),
        ("current_remote_support", "remote_ui"),
        ("current_death_animation_support", "death_animation_ui"),
        ("current_revival_support", "revival_ui"),
        ("current_downed_support", "downed_ui"),
        ("current_ability_return_support", "ability_return_ui"),
        ("current_active_display_support", "active_phase_visible"),
        ("current_round_result_support", "round_result_visible"),
        ("current_purchase_support", "purchase_phase_visible"),
    ):
        value = ui.get(raw_key)
        fields.append({"name": name, "status": "supported" if value is True else "UNKNOWN",
                       "roi_xywh_px": None, "roi_qualification": "see_constituent_probes",
                       "value": True if value is True else None, "uncalibrated_score": None,
                       "evidence": {"reader_output": value}})
    fields.append({
        "name": "owner_reader_diagnostics", "status": screen.get("status", "UNKNOWN"),
        "roi_xywh_px": None, "roi_qualification": "see_constituent_probes",
        "value": {"screen_measurements": deepcopy(screen),
                  "remote_detection": ui.get("remote_detection"),
                  "spectator_absence_checked": ui.get("spectator_absence_checked")},
        "uncalibrated_score": None, "evidence": {},
    })
    return _packet(frame, source_id, ui["fingerprint"], _digest(profile), fields,
                   {"source_discontinuity": ui.get("source_discontinuity"),
                    "spectator_slot": deepcopy(screen.get("spectator_slot"))})


def export_round_readers(frame: FrameRecord, row: dict[str, Any], *,
                         reader_fingerprint: str, profile_fingerprint: str,
                         rois: dict[str, Any]) -> dict[str, Any]:
    """Transport existing offline Score/Timer/Result output without accepting it.

    Geometry, raw literals, score/confidence and reader sources are retained;
    this function does not parse a number, relax a threshold or associate events.
    """
    sample = _sample(frame, row["source_id"])
    expected = {"source_sha256": frame.source_sha256, "tick": frame.native_pts_tick,
                "epoch": frame.native_epoch, "time_base": frame.native_time_base,
                "encoded_sha256": frame.frame_sha256, "pixel_sha256": frame.pixel_sha256}
    if type(row.get("tick")) is not int or any(row.get(k) != v for k, v in expected.items()):
        raise ValueError("Round reader native evidence mismatch")
    fields = []
    for name in ("ally_score", "enemy_score", "timer", "result"):
        raw = row.get(name)
        if not isinstance(raw, dict):
            raise ValueError("Existing Round reader mapping required")
        fields.append({"name": name, "status": "NOT_ANALYSED"
                       if row.get("analysed") is False else "reader_output"
                       if raw.get("value") is not None else "UNKNOWN",
                       "value": deepcopy(raw.get("value")),
                       "uncalibrated_score": raw.get("confidence"),
                       "roi_xywh_px": _roi(rois.get(name), frame.frame_size_px),
                       "roi_qualification": "see_geometry_evidence",
                       "evidence": deepcopy(raw)})
    fields.append({"name": "round_geometry_and_display_context",
                   "status": "NOT_ANALYSED" if row.get("analysed") is False else "measured",
                   "value": {k: deepcopy(row.get(k)) for k in (
                       "analysed", "geometry_consistent", "component_geometry", "buy_phase",
                       "phase_structure", "visual_result")},
                   "uncalibrated_score": None, "roi_xywh_px": None,
                   "roi_qualification": "not_global_ownership", "evidence": {}})
    result = _packet(frame, row["source_id"], reader_fingerprint, profile_fingerprint, fields,
                     {"discontinuity": row.get("discontinuity"),
                      "expected_step_ticks": row.get("expected_step_ticks")})
    assert result["sample"] == sample
    return result


def validate_packet(packet: dict[str, Any]) -> None:
    """Validate serialized transport, not Source bytes, GT or semantic correctness."""
    if (packet.get("version") != _VERSION
            or packet.get("qualification") != "development_only"
            or packet.get("ownership") != "UNKNOWN"
            or type(packet.get("formal_outputs")) is not int
            or packet.get("formal_outputs") != 0 or packet.get("qualified") is not False
            or packet.get("formal_events") != []
            or packet.get("semantic_source_continuity") != "UNVERIFIED"
            or packet.get("state_owner") != "common_engine_not_this_supplier"):
        raise ValueError("Unqualified HUD supplier packet required")
    expected_keys = {"version", "sample", "frame_contract", "native_second_index",
                     "reader_fingerprint", "profile_fingerprint", "adapter_fingerprint",
                     "measurements", "continuity_observations", "semantic_source_continuity",
                     "qualification", "ownership", "formal_events", "formal_outputs", "state_owner",
                     "qualified"}
    if set(packet) != expected_keys:
        raise ValueError("HUD supplier cannot add final game-state fields")
    raw = packet["frame_contract"]
    from valorant_ai_coach.visual.development_learning_dataset import SourceAcceptance, Split
    frame = FrameRecord(**{**raw, "source_acceptance": SourceAcceptance(**raw["source_acceptance"]),
                           "split": Split(raw["split"]),
                           "frame_size_px": tuple(raw["frame_size_px"]),
                           "roi_xywh": tuple(raw["roi_xywh"])})
    sample = _sample(frame, packet["sample"]["source_id"])
    second = Fraction(frame.native_pts_tick) * Fraction(frame.native_time_base)
    if (sample != packet["sample"] or type(packet.get("native_second_index")) is not int
            or packet["native_second_index"] != second.numerator // second.denominator
            or not all(_sha(packet.get(k)) for k in (
                "reader_fingerprint", "profile_fingerprint", "adapter_fingerprint"))
            or not isinstance(packet.get("measurements"), list)):
        raise ValueError("Exact native packet and fingerprints required")
    for measurement in packet["measurements"]:
        if not isinstance(measurement, dict) or not isinstance(measurement.get("name"), str):
            raise ValueError("Named current-frame measurement required")
        roi = measurement.get("roi_xywh_px")
        if roi is not None:
            if (not isinstance(roi, list) or len(roi) != 4
                    or any(type(n) is not int for n in roi)):
                raise ValueError("Pixel ROI must use exact integer geometry")
            x, y, width, height = roi
            if (min(x, y) < 0 or min(width, height) <= 0
                    or x + width > frame.frame_size_px[0]
                    or y + height > frame.frame_size_px[1]):
                raise ValueError("HUD ROI outside native frame")
    _digest(packet)


def export_boundary_hint(kind: str, bracket: dict[str, Any], *,
                         packets: Sequence[dict[str, Any]], producer_fingerprint: str,
                         confirmation_witness: dict[str, Any] | None = None,
                         producer_evidence: dict[str, Any] | None = None) -> dict[str, Any]:
    """Transport an existing candidate/bracket, never infer a new transition.

    Confirmation is a producer-supplied evidence time, not this adapter's choice
    of a midpoint, timeout or later frame. Every witness must exist in packets.
    """
    if kind not in {"round_start", "round_end"} or not _sha(producer_fingerprint):
        raise ValueError("Existing Round candidate kind and producer fingerprint required")
    index: dict[tuple[str, str, int], dict[str, Any]] = {}
    for packet in packets:
        validate_packet(packet)
        sample = packet["sample"]
        key = sample["source_sha256"], sample["native_epoch"], sample["native_pts_tick"]
        if key in index and index[key] != sample:
            raise ValueError("Conflicting native witnesses")
        index[key] = sample

    def witness(raw: dict[str, Any]) -> dict[str, Any]:
        if type(raw.get("tick")) is not int:
            raise ValueError("Integer native witness PTS required")
        key = raw["source_sha256"], raw["epoch"], raw["tick"]
        sample = index.get(key)
        if sample is None or any(raw.get(k) != sample[v] for k, v in (
            ("source_id", "source_id"), ("time_base", "native_time_base"),
            ("encoded_sha256", "acquired_frame_sha256"),
            ("pixel_sha256", "native_pixel_sha256"),
        )):
            raise ValueError("Boundary requires exact exported native witness")
        return sample

    if any(type(bracket.get(k)) is not int for k in ("lower_tick", "upper_tick")):
        raise ValueError("Integer native bracket PTS required")
    before, after = witness(bracket["before"]), witness(bracket["after"])
    confirmed = witness(confirmation_witness) if confirmation_witness is not None else None
    if (any(before[k] != after[k] for k in (
            "source_sha256", "native_epoch", "native_time_base", "frame_size_px"))
            or before["native_pts_tick"] >= after["native_pts_tick"]
            or bracket["lower_tick"] != before["native_pts_tick"]
            or bracket["upper_tick"] != after["native_pts_tick"]
            or bracket["epoch"] != before["native_epoch"]
            or bracket["time_base"] != before["native_time_base"]):
        raise ValueError("Ordered same-source/epoch native bracket required")
    if confirmed is not None and (
        any(confirmed[k] != after[k] for k in (
            "source_sha256", "native_epoch", "native_time_base", "frame_size_px"))
        or confirmed["native_pts_tick"] < after["native_pts_tick"]
    ):
        raise ValueError("Confirmation must follow the boundary in the same acquisition")
    evidence = deepcopy(producer_evidence or {})
    if (evidence.get("status", "UNKNOWN") not in {"UNKNOWN", "DEVELOPMENT_CANDIDATE",
            "DEVELOPMENT_TRANSITION_CANDIDATE", "DEVELOPMENT_LIFECYCLE_CANDIDATE",
            "DEVELOPMENT_PURCHASE_CLOCK_CANDIDATE"}
            or evidence.get("formal_events", []) != []
            or evidence.get("qualified", False) is not False
            or evidence.get("qualification_created", False) is not False
            or evidence.get("approved_gt", False) is not False
            or evidence.get("internal_End_tick") is not None
            or evidence.get("internal_Start_tick") is not None):
        raise ValueError("Producer hint must remain unqualified")

    def check_witnesses(value: Any) -> None:
        if isinstance(value, dict):
            keys = {"source_id", "source_sha256", "epoch", "tick", "time_base",
                    "encoded_sha256", "pixel_sha256"}
            if keys <= set(value):
                observed = witness(value)
                if any(observed[k] != after[k] for k in (
                    "source_sha256", "native_epoch", "native_time_base")):
                    raise ValueError("Candidate evidence crosses Source/acquisition")
            for child in value.values():
                check_witnesses(child)
        elif isinstance(value, (list, tuple)):
            for child in value:
                check_witnesses(child)
    check_witnesses(evidence)
    result = {
        "kind": kind, "status": "UNKNOWN" if evidence.get("status", "UNKNOWN") == "UNKNOWN"
        else "DEVELOPMENT_CANDIDATE", "before": deepcopy(before),
        "after": deepcopy(after), "boundary_candidate_tick": after["native_pts_tick"],
        "confirmation_observation_tick": confirmed["native_pts_tick"] if confirmed else None,
        "confirmation_witness": deepcopy(confirmed), "internal_game_event_tick": None,
        "uncertainty_interval_ticks": [before["native_pts_tick"], after["native_pts_tick"]],
        "source_continuity": "UNVERIFIED", "producer_fingerprint": producer_fingerprint,
        "producer_evidence": evidence,
        "confirmation_semantics": "producer_observation_not_qualification",
        "qualification": "development_only", "ownership": "UNKNOWN", "formal_outputs": 0,
        "qualified": False,
    }
    _digest(result)
    return result
