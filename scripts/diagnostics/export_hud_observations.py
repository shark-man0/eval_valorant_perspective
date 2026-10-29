"""Private HUD supplier replay; no video decode, common state engine or events."""
from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

from scripts.diagnostics.analyze_personal_candidates import development_sources
from scripts.diagnostics.register_private_sources import write_private
from scripts.e2e.run_dataset_case import read_json, sha256_file
from scripts.temporal_gt.review_session import append_exposure, load_plan, private_directory
from valorant_ai_coach.hud.development_observation_export import (
    export_boundary_hint,
    export_owner_ui,
    export_round_readers,
    validate_packet,
)
from valorant_ai_coach.visual.development_learning_dataset import (
    FrameRecord,
    SourceAcceptance,
    Split,
)


def convert(bundle: dict[str, Any], sources: list[dict[str, Any]], *,
            manifest_sha256: str, allocation_sha256: str) -> dict[str, Any]:
    """Registry checks precede any owner/round packet or hint processing."""
    if bundle.get("version") != "hud_supplier_replay_input_v1":
        raise ValueError("Existing reader replay bundle required")
    owner, rounds = bundle.get("owner_frames", []), bundle.get("round_frames", [])
    if (not isinstance(owner, list) or not isinstance(rounds, list)
            or not 0 < len(owner) + len(rounds) <= 50_000):
        raise ValueError("Bounded nonempty HUD observation inputs required")
    allowed = {(s["video_id"], s["source_sha256"]): s for s in sources
               if s["status"] == "accepted" and s["split"] == "DEVELOPMENT"
               and s["exposure"] == "DEVELOPMENT"}

    def frame(item: dict[str, Any]) -> FrameRecord:
        raw = item["frame_contract"]
        source_id = item.get("source_id", item.get("row", {}).get("source_id"))
        source = allowed.get((source_id, raw["source_sha256"]))
        if (source is None or raw["leakage_group_id"] != source["physical_match_id"]):
            raise ValueError("Registered DEVELOPMENT Source/physical match required")
        acceptance = raw["source_acceptance"]
        if (acceptance["manifest_sha256"] != manifest_sha256
                or acceptance["trusted_manifest_sha256"] != manifest_sha256
                or acceptance["allocation_sha256"] != allocation_sha256
                or acceptance["trusted_allocation_sha256"] != allocation_sha256):
            raise ValueError("Current trusted registry anchors required")
        result = FrameRecord(**{**raw, "source_acceptance": SourceAcceptance(**acceptance),
                                "split": Split(raw["split"]),
                                "frame_size_px": tuple(raw["frame_size_px"]),
                                "roi_xywh": tuple(raw["roi_xywh"])})
        result.validate()
        return result

    # Validate all Source contracts before projecting any observations.
    owner_inputs = [(frame(x), x) for x in owner]
    round_inputs = [(frame(x), x) for x in rounds]
    packets = [export_owner_ui(f, x["source_id"], x["ui"], x["profile"])
               for f, x in owner_inputs]
    packets.extend(export_round_readers(
        f, x["row"], reader_fingerprint=x["reader_fingerprint"],
        profile_fingerprint=x["profile_fingerprint"], rois=x["rois"],
    ) for f, x in round_inputs)
    for packet in packets:
        validate_packet(packet)
    hints = [export_boundary_hint(
        h["kind"], h["bracket"], packets=packets,
        producer_fingerprint=h["producer_fingerprint"],
        confirmation_witness=h.get("confirmation_witness"),
        producer_evidence=h.get("producer_evidence"),
    ) for h in bundle.get("boundary_hints", [])]
    return {"version": "hud_supplier_export_v1", "packets": packets, "boundary_hints": hints,
            "common_game_state_computed": False, "qualification": "development_only",
            "formal_events": [], "formal_outputs": 0}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--review-session", type=Path, required=True)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True,
                        help="File inside a new external private run directory")
    args = parser.parse_args()
    if args.output.parent.exists():
        raise ValueError("New private output directory required; existing runs are not overwritten")
    if args.input.stat().st_size > 64 * 1024 * 1024:
        raise ValueError("Bounded private replay bundle required")
    plan = load_plan(args.review_session)
    input_sha = sha256_file(args.input)
    result = convert(read_json(args.input), development_sources(args.review_session),
                     manifest_sha256=plan["inventory_sha256"],
                     allocation_sha256=plan["allocation_sha256"])
    if input_sha != sha256_file(args.input):
        raise ValueError("Replay inputs changed during export")
    # Recheck the frozen registry before releasing the buffered export.
    load_plan(args.review_session)
    private_directory(args.output.parent)
    result["input_sha256"] = input_sha
    result["export_cli_sha256"] = sha256_file(Path(__file__))
    write_private(args.output, result)
    orders = {}
    for source_id in sorted({p["sample"]["source_id"] for p in result["packets"]}):
        orders[source_id] = append_exposure(
            args.review_session, "prediction", args.output,
            "Replay existing HUD observations/native candidate brackets for common timeline "
            "handoff. No video decode, state inference, new GT, qualification or formal events.",
            source_id=source_id,
        )
    write_private(args.output.with_suffix(args.output.suffix + ".exposure.json"),
                  {"orders": orders})
    print(f"Exported {len(result['packets'])} frame packets and {len(result['boundary_hints'])} "
          "boundary hints; common state/qualification/formal events: 0")


if __name__ == "__main__":
    main()
