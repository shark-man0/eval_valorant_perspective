"""Observed HUD values from configured readers, without recorder attribution."""

from __future__ import annotations

from typing import Any

import cv2
import numpy as np
from numpy.typing import NDArray

from valorant_ai_coach.hud.layout import HudLayout
from valorant_ai_coach.hud.models import accept_hud_value
from valorant_ai_coach.hud.templates import SubregionReader

VERSION = "development_configured_hud_values_v1"
_REGIONS = {
    "player_hp_armor": {"hp": "hp", "armor": "armor"},
    "ammo_current_weapon": {"ammo_current": "ammo_current", "ammo_reserve": "ammo_reserve",
                            "weapon_text": "weapon"},
    "weapon_inventory": {"weapon_text": "weapon"},
    "credits": {"credits": "credits"},
}


def configured_hud_values(
    image: NDArray[np.uint8], *, layout: HudLayout, readers: dict[str, Any],
    ui: dict[str, Any], calibrated: bool,
) -> list[dict[str, Any]]:
    """Reuse acceptance/readers; absence/error is UNKNOWN, never numeric zero.

    The value belongs to the viewed HUD, including spectator/remote views. It
    cannot support an owner/life claim. Per-field configuration and failure
    reasons survive even when a peer field is read successfully.
    """
    measurements: list[dict[str, Any]] = []
    for region, fields in _REGIONS.items():
        reader = readers.get(region)
        entries: dict[str, dict[str, Any]] = {
            name: {"name": target, "value": None, "status": "UNKNOWN",
                   "reason": "unconfigured_reader_or_roi", "reader_roi": region,
                   "confidence": None, "sources": [], "cross_checked": False,
                   "subject": "viewed_HUD; recorder_ownership_unresolved"}
            for name, target in fields.items()
        }
        measurements.extend(entries.values())
        if reader is None or region not in layout.regions:
            continue
        inner = reader
        while isinstance(inner, SubregionReader):
            inner = inner.reader
        declared = getattr(inner, "fields", None)
        configured = {k: v for k, v in entries.items()
                      if not isinstance(declared, dict) or k in declared}
        if not configured:
            continue
        structure = "hp_hud_structure" if region == "player_hp_armor" else "weapon_ammo_structure"
        local = (region != "credits" and ui.get(structure) is True
                 and isinstance(ui.get(structure + "_confidence"), (int, float))
                 and not isinstance(ui[structure + "_confidence"], bool)
                 and .90 <= ui[structure + "_confidence"] <= 1)
        for entry in configured.values():
            entry["reason"] = "geometry_unsupported"
        if not calibrated and not local:
            continue
        try:
            left, top, right, bottom = layout.normalized_roi(region).pixel_bounds(
                image.shape[1], image.shape[0]
            )
            value = reader.read(image, image[top:bottom, left:right])
            accepted = accept_hud_value(value.value, value.confidence,
                                        cross_checked=value.cross_checked)
            for name, entry in configured.items():
                entry.update(confidence=value.confidence, sources=list(value.sources),
                             cross_checked=value.cross_checked, reason="unread_or_unaccepted")
                item = accepted.get(name) if isinstance(accepted, dict) else (
                    accepted if len(fields) == 1 else None
                )
                if name == "weapon_text":
                    valid = isinstance(item, str) and bool(item.strip()) and len(item) <= 128
                else:
                    maximum = {"hp": 150, "armor": 50, "credits": 99999}.get(name, 9999)
                    valid = type(item) is int and 0 <= item <= maximum
                if valid and value.sources:
                    entry.update(value=item, status="CANDIDATE", reason="configured_reader_value")
        except (AttributeError, TypeError, ValueError, KeyError, OSError, cv2.error) as exc:
            for entry in configured.values():
                entry.update(reason="reader_error", error_type=type(exc).__name__)
    return measurements
