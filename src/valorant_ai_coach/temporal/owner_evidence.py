"""Opt-in repair of current-frame supplier gates; no temporal state inference.

A configured dedicated slot's checked absence is positive observation evidence.
An intentionally unconfigured redundant veto contributes no evidence either way.
An unavailable configured veto still blocks eligibility. No threshold is changed.
"""

from __future__ import annotations

import argparse
from copy import deepcopy
from pathlib import Path
from typing import Any

from .adapters import owner_ui
from .evidence import digest, is_sha
from .replay import SourcePolicy, file_sha, read_json, write_private

VERSION = "development_owner_gate_recovery_v1"


def recover_owner_item(item: dict[str, Any]) -> dict[str, Any]:
    original = owner_ui(item)
    sample = original["sample"]
    profile, ui = item["profile"], item["ui"]
    if "gate_recovery" in ui:
        raise ValueError("Already recovered owner observation")
    if digest(profile) != ui["source_profile_fingerprint"]:
        raise ValueError("Owner profile must match the measured profile fingerprint")
    spec = profile.get("development_ownership_evidence", {})
    binding = profile.get("development_recorder_view", {}).get("binding", {})
    screen, agent = ui.get("screen_measurements", {}), ui.get("agent_measurements", {})
    if (
        spec.get("frame_size_px") != sample["frame_size_px"]
        or spec.get("slot_review") != "source_reviewed_not_qualified"
        or screen.get("source_id") != sample["source_id"]
        or screen.get("acquisition_id") != sample["native_epoch"]
        or screen.get("frame_pixel_sha256") != sample["native_pixel_sha256"]
    ):
        raise ValueError("Exact current pixels and configured slot required")
    if binding and (
        binding.get("source_id") != sample["source_id"]
        or binding.get("source_sha256") != sample["source_sha256"]
        or binding.get("physical_match_id") != item["frame_contract"].get("leakage_group_id")
        or sample["native_epoch"] not in binding.get("acquisition_ids", [])
    ):
        raise ValueError("Configured recorder binding belongs to another Source/match/epoch")
    identity_supported = (
        binding.get("review_kind") == "human_source_roster"
        and is_sha(binding.get("review_sha256"))
        and bool(binding.get("recorder_agent_id"))
    )
    cues = screen.get("observed_cues", [])
    present = {c["claim"] for c in cues if c.get("status") == "present"}
    slot = screen.get("spectator_slot", {})
    veto = ui.get("spectator_measurements", {})
    veto_configured = profile.get("development_view_veto") is not None
    veto_clear = (
        veto.get("status") == "not_detected" and veto.get("veto") is False
        if veto_configured
        else veto.get("status") == "disabled" and veto.get("veto") is False
    )
    spectator = (
        "spectator_controls" in present
        or (slot.get("checked") is True and slot.get("panel_present") is True)
        or (veto.get("status") == "spectator_ui" and veto.get("veto") is True)
    )
    absent = (
        screen.get("status") == "observed"
        and not any(c.get("status") == "unavailable" for c in cues)
        and slot.get("checked") is True
        and slot.get("panel_present") is False
        and veto_clear
        and not spectator
    )
    owner = (
        absent
        and identity_supported
        and "first_person_hud" in present
        and agent.get("status") == "observed"
        and agent.get("positive_agent_association") is True
        and agent.get("block_position_candidate") is False
        and agent.get("recorder_agent_id") == binding.get("recorder_agent_id")
        and agent.get("binding_review_sha256") == binding.get("review_sha256")
    )
    result = deepcopy(item)
    recovered = result["ui"]
    recovered.update(
        own_hud_support=owner,
        spectator_ui=spectator,
        spectator_absence_checked=absent,
        fingerprint=digest(
            {"version": VERSION, "code": file_sha(Path(__file__)), "upstream": ui["fingerprint"]}
        ),
        gate_recovery={
            "version": VERSION,
            "upstream_ui": deepcopy(ui),
            "redundant_veto_configured": veto_configured,
            "dedicated_slot_checked": slot.get("checked") is True,
            "spectator_controls_observed": "spectator_controls" in present,
            "recorder_roster_supported": identity_supported,
            "threshold_changes": 0,
            "new_human_labels": 0,
            "semantic_continuity": "UNKNOWN",
        },
    )
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--policy", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    policy = SourcePolicy(read_json(args.policy))
    input_sha = file_sha(args.input)
    data = read_json(args.input)
    if data.get("version") != "hud_supplier_replay_input_v1":
        raise ValueError("Frozen native HUD observation input required")
    recovered = []
    for item in data["owner_frames"]:
        row = owner_ui(item)
        policy.admit(row["sample"], item["frame_contract"])
        recovered.append(recover_owner_item(item))
    if file_sha(args.input) != input_sha:
        raise ValueError("Input changed during recovery")
    data["owner_frames"] = recovered
    data["owner_gate_recovery_provenance"] = {
        "version": VERSION,
        "input_sha256": input_sha,
        "policy_sha256": file_sha(args.policy),
        "code_sha256": file_sha(Path(__file__)),
        "raw_reader_rerun": False,
        "new_human_labels": 0,
        "formal_outputs": 0,
    }
    write_private(args.output, data)


if __name__ == "__main__":
    main()
