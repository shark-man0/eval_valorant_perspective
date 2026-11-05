"""Opt-in current-view hypotheses when a combat report remains visible.

Only current supplier measurements are inputs. The shared game engine still
owns state, history, uncertainty, transitions and Map attribution.
"""

from __future__ import annotations

import math
from copy import deepcopy
from pathlib import Path
from typing import Any

from .evidence import digest
from .replay import file_sha


def _purchase_self_supported(base: dict[str, Any], view: dict[str, Any]) -> bool:
    raw = view["raw"]
    ui = base["raw"].get("ui", {})
    signals = set(base["signals"])
    if not (
        ui.get("buy_phase_template") is True
        and "buy" in signals
        and not signals & {
            "active", "result", "intermission", "spectator", "remote", "death", "downed"
        }
    ):
        return False
    if not (
        view["context"].get("unqualified_view_model") is True
        and raw.get("camera_hypothesis") == "SELF"
        and raw.get("current_HUD_component_supported") is True
        and raw.get("owner_hypothesis_exclusions") == ["combat_report_visible"]
        and raw.get("owned_verb_phrase") is None
        and not set(view["signals"]) & {
            "spectator", "remote", "death", "downed", "recorder_elimination_display"
        }
    ):
        return False
    hp = raw.get("view_hp")
    if not isinstance(hp, dict):
        return False
    display, confidence = hp.get("display"), hp.get("confidence")
    return (
        isinstance(display, str)
        and display.isascii()
        and display.isdigit()
        and 1 <= int(display) <= 150
        and isinstance(confidence, (int, float))
        and not isinstance(confidence, bool)
        and math.isfinite(confidence)
        and confidence >= .90
    )


def project_purchase_self_claim(measurement: dict[str, Any]) -> tuple[dict[str, Any], int]:
    """Preserve a weak SELF observation supported by BUY, view pixels and HP.

    A report's presence alone does not identify a current victim. Other view
    blockers and a read owned-death relation still withhold this proposal.
    Retain the original measurement, parent constraints and producer binding;
    consumers must keep the existing unqualified-view/Map gates.
    """
    result = deepcopy(measurement)
    base = result["supplier_observations"][0]
    rule_sha = file_sha(Path(__file__))
    changed = 0
    for view in result["supplier_observations"]:
        if view["context"].get("unqualified_view_model") is not True:
            continue
        prior = view["raw"].get("current_buy_self_report_hypothesis", {})
        parent = (
            view["raw"]["parent_view_producer_fingerprint"]
            if prior.get("rule_sha256") == rule_sha
            else view["producer_fingerprint"]
        )
        view["producer_fingerprint"] = digest(
            {"parent_view_producer": parent, "current_buy_self_rule_sha256": rule_sha}
        )
        view["raw"]["parent_view_producer_fingerprint"] = parent
        supported = _purchase_self_supported(base, view)
        view["raw"]["current_buy_self_report_hypothesis"] = {
            "supported": supported,
            "rule_sha256": rule_sha,
            "scope": "weak current view; report age and current victim identity unresolved",
            "competing_views_if_supported": ["SELF", "SPECTATOR", "REMOTE", "UNKNOWN"]
            if supported else [],
            "Map_authority": False,
            "qualification": "development_only",
        }
        if supported and "owner_hud" not in view["signals"]:
            view["signals"] = sorted(set(view["signals"]) | {"owner_hud"})
            changed += 1
    result["signals"] = sorted(
        {signal for row in result["supplier_observations"] for signal in row["signals"]}
    )
    return result, changed
