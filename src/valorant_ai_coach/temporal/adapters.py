"""Observation-only HUD/Map adapters; neither supplier owns temporal state here."""

from __future__ import annotations

import math
from copy import deepcopy
from typing import Any

from valorant_ai_coach.hud.models import accept_hud_value

from .evidence import digest, freeze_native_sample, is_sha
from .game import observation


def sample_from_frame(frame: dict[str, Any], source_id: str) -> dict[str, Any]:
    return freeze_native_sample(
        {
            "source_id": source_id,
            **{
                k: frame[k]
                for k in (
                    "source_sha256",
                    "acquisition_id",
                    "native_epoch",
                    "native_pts_tick",
                    "native_time_base",
                    "frame_size_px",
                )
            },
            "acquired_frame_sha256": frame["frame_sha256"],
            "native_pixel_sha256": frame["pixel_sha256"],
        }
    )


def owner_ui(item: dict[str, Any]) -> dict[str, Any]:
    """Reuse PR111 current UI measurements, excluding its independent timeline.

    Report presence is never death. False detector support is not explicit NO.
    Raw reader outputs and profile digest remain attached to exact native PTS.
    """
    sample = sample_from_frame(item["frame_contract"], item["source_id"])
    ui = item["ui"]
    if (
        ui.get("sample_sha256") != sample["sample_sha256"]
        or ui.get("qualified") is not False
        or ui.get("formal_outputs") != 0
        or not is_sha(ui.get("fingerprint"))
        or not is_sha(ui.get("source_profile_fingerprint"))
    ):
        raise ValueError("Source-bound unqualified owner UI required")
    signals = [
        signal
        for key, signal in (
            ("own_hud_support", "owner_hud"),
            ("spectator_ui", "spectator"),
            ("remote_ui", "remote"),
            ("death_animation_ui", "death"),
            ("downed_ui", "downed"),
            ("revival_ui", "revival"),
            ("ability_return_ui", "ability_return"),
            ("combat_report_visible", "report"),
            ("purchase_phase_visible", "buy"),
            ("active_phase_visible", "active"),
            ("round_result_visible", "result"),
        )
        if ui.get(key) is True
    ]
    cues = ui.get("screen_measurements", {}).get("observed_cues", [])
    if any(
        c.get("claim") == "first_person_hud" and c.get("status") == "not_detected" for c in cues
    ):
        signals.append("hud_not_detected")
    return observation(
        sample=sample,
        producer=ui["fingerprint"],
        signals=signals,
        raw=ui,
        context={
            "stream_kind": "hud_owner",
            "profile_fingerprint": ui["source_profile_fingerprint"],
        },
        continuity={"source_discontinuity": ui.get("source_discontinuity")},
    )


def _accepted(raw: dict[str, Any]) -> str | None:
    # Same .90 floor and acceptance predicate as the existing offline producer.
    value, confidence = raw.get("value"), raw.get("confidence")
    if (
        not isinstance(value, str)
        or not isinstance(confidence, (int, float))
        or isinstance(confidence, bool)
        or not math.isfinite(confidence)
        or not 0.90 <= confidence <= 1
    ):
        return None
    accepted = accept_hud_value(value, confidence)
    return accepted if isinstance(accepted, str) else None


def _clock(value: str | None) -> int | None:
    if not value:
        return None
    parts = value.split(":")
    if len(parts) == 2 and all(p.isascii() and p.isdigit() for p in parts):
        minute, second = map(int, parts)
        if 0 <= minute <= 9 and 0 <= second < 60:
            return 60 * minute + second
    return None


def round_readers(item: dict[str, Any]) -> dict[str, Any]:
    row = item["row"]
    sample = sample_from_frame(item["frame_contract"], row["source_id"])
    for key, field in (
        ("source_sha256", "source_sha256"),
        ("epoch", "native_epoch"),
        ("tick", "native_pts_tick"),
        ("time_base", "native_time_base"),
        ("encoded_sha256", "acquired_frame_sha256"),
        ("pixel_sha256", "native_pixel_sha256"),
    ):
        if row[key] != sample[field]:
            raise ValueError("Round native measurement mismatch")
    geometry = row.get("component_geometry") or {}
    roles = geometry.get("roles", {})
    score = None
    if roles.get("score") is True:
        pair = [_accepted(row[k]) for k in ("ally_score", "enemy_score")]
        if all(
            isinstance(v, str) and v.isascii() and v.isdigit() and 0 <= int(v) <= 99 for v in pair
        ):
            score = [int(str(v)) for v in pair]
    timer = _clock(_accepted(row["timer"])) if roles.get("timer") is True else None
    signals = []
    if row.get("buy_phase") is True:
        signals.append("buy")
    elif timer is not None and timer > 45:
        # A positive active-clock hypothesis, never current owner/life evidence.
        signals.append("active")
    result = _accepted(row["result"])
    vocabulary = {"TEAM ACE", "VICTORY", "DEFEAT", "FLAWLESS", "THRIFTY", "ACE", "WON", "LOST"}
    if result and " ".join(result.upper().split()) in vocabulary and roles.get("result") is True:
        signals.append("result")
    return observation(
        sample=sample,
        producer=item["reader_fingerprint"],
        signals=signals,
        raw=row,
        context={
            "profile_fingerprint": item["profile_fingerprint"],
            "stream_kind": "hud_round",
            "score": score,
            "timer_seconds": timer,
        },
        continuity={
            "discontinuity": row.get("discontinuity"),
            "expected_step_ticks": row.get("expected_step_ticks"),
        },
    )


def hud_packet(packet: dict[str, Any]) -> dict[str, Any]:
    """Consume HUD's observation-only v1 API without its old state machine."""
    if (
        packet.get("version") != "development_hud_observations_v1"
        or packet.get("qualification") != "development_only"
        or packet.get("qualified") is not False
        or packet.get("formal_events") != []
        or packet.get("formal_outputs") != 0
        or packet.get("ownership") != "UNKNOWN"
    ):
        raise ValueError("Unqualified HUD supplier packet required")
    signals = []
    names = {
        "current_owner_hud_support": "owner_hud",
        "current_spectator_support": "spectator",
        "current_remote_support": "remote",
        "current_death_animation_support": "death",
        "current_revival_support": "revival",
        "current_downed_support": "downed",
        "current_ability_return_support": "ability_return",
        "current_active_display_support": "active",
        "current_round_result_support": "result",
        "current_purchase_support": "buy",
        "purchase_phase": "buy",
        "death_report": "report",
    }
    for field in packet["measurements"]:
        if (
            field["name"] in names
            and field.get("value") is True
            and field.get("status") in {"supported", "present"}
        ):
            signals.append(names[field["name"]])
        if field["name"] == "first_person_hud" and field.get("status") == "not_detected":
            signals.append("hud_not_detected")
    measurements = {f["name"]: f for f in packet["measurements"]}
    context = {"stream_kind": "hud_owner", "profile_fingerprint": packet["profile_fingerprint"]}
    if "round_geometry_and_display_context" in measurements:
        sample = packet["sample"]
        row = {
            "source_id": sample["source_id"],
            "source_sha256": sample["source_sha256"],
            "epoch": sample["native_epoch"],
            "tick": sample["native_pts_tick"],
            "time_base": sample["native_time_base"],
            "encoded_sha256": sample["acquired_frame_sha256"],
            "pixel_sha256": sample["native_pixel_sha256"],
            **measurements["round_geometry_and_display_context"]["value"],
        }
        row.update(
            {
                k: measurements[k]["evidence"]
                for k in ("ally_score", "enemy_score", "timer", "result")
            }
        )
        normalized = round_readers(
            {
                "frame_contract": packet["frame_contract"],
                "row": row,
                "reader_fingerprint": packet["reader_fingerprint"],
                "profile_fingerprint": packet["profile_fingerprint"],
            }
        )
        signals.extend(normalized["signals"])
        context.update(normalized["context"])
    return observation(
        sample=packet["sample"],
        producer=packet["reader_fingerprint"],
        signals=signals,
        raw=packet,
        context=context,
        continuity=packet["continuity_observations"],
    )


def map_packet(packet: dict[str, Any]) -> dict[str, Any]:
    """Retain all marker/Zone hypotheses. Selection never establishes owner life."""
    if (
        packet.get("schema") != "map_consumer_provisional_v1"
        or packet.get("qualification") != "development_only"
        or packet.get("ownership") != "UNKNOWN"
        or packet.get("formal_outputs") != 0
        or packet.get("observation_sha256")
        != digest({k: v for k, v in packet.items() if k != "observation_sha256"})
    ):
        raise ValueError("Sealed development Map supplier packet required")
    if packet["pool"]["sample"] != packet["sample"]:
        raise ValueError("Map candidates belong to another sample")
    return observation(
        sample=packet["sample"],
        producer=packet["ui"]["feature_fingerprint"],
        signals=[],
        raw=packet,
        context={
            "stream_kind": "map",
            "profile_fingerprint": packet["reference_context_fingerprint"],
        },
        map_candidates=deepcopy(packet["pool"]["candidates"]),
    )
