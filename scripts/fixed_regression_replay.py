"""Private fixed-frame execution through the production service factory.

Only manifests and aggregate comparisons are publishable. Replay rows and decoded
frames remain private; source PTS is capture metadata, never an expected event.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from collections import Counter
from copy import deepcopy
from dataclasses import replace
from fractions import Fraction
from pathlib import Path
from typing import Any

from fixed_replay_manifest import (
    ffprobe_native_locators,
    manifest_hash,
    normalize_time_base,
    sha256_file,
    validate_manifest,
    write_manifest_immutable,
)


def stable_hash(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
    ).hexdigest()


def decoded_hash(path: Path) -> str:
    import cv2

    image = cv2.imread(str(path))
    if image is None:
        raise ValueError("fixed frame cannot be decoded")
    return hashlib.sha256(image.tobytes()).hexdigest()


def bind_frames(
    manifest: dict[str, Any], frames: list[Any], *, require_pixels: bool = True
) -> None:
    """Reject population, PTS or decoded-input drift before invoking detectors."""
    validate_manifest(manifest)
    if len(frames) != len(manifest["frames"]):
        raise ValueError("fixed frame population mismatch")
    base = Fraction(manifest["time_base"]["num"], manifest["time_base"]["den"])
    for record, frame in zip(manifest["frames"], frames, strict=True):
        if abs(frame.time_sec - float(record["pts"] * base)) > 1e-6:
            raise ValueError("fixed frame PTS mismatch")
        expected = record.get("pixel_sha256")
        if require_pixels and expected is None:
            raise ValueError("fixed manifest requires decoded pixel hashes")
        if expected is not None and decoded_hash(frame.path) != expected:
            raise ValueError("fixed frame decoded pixel mismatch")


def extract_frames(
    video: Any,
    source: Path,
    manifest: dict[str, Any],
    private_dir: Path,
    *,
    require_pixels: bool = True,
) -> tuple[Any, list[Any]]:
    validate_manifest(manifest, expected_source_sha=sha256_file(source))
    native_base, stream, native = ffprobe_native_locators(source, str(video.ffprobe_path))
    if (
        stream != manifest["stream_index"]
        or normalize_time_base(native_base) != manifest["time_base"]
    ):
        raise ValueError("fixed native stream mismatch")
    by_index = {row["source_frame_index"]: row["pts"] for row in native}
    if any(by_index.get(row["source_frame_index"]) != row["pts"] for row in manifest["frames"]):
        raise ValueError("fixed native locator mismatch")
    metadata = video.probe(source)
    base = Fraction(manifest["time_base"]["num"], manifest["time_base"]["den"])
    frames = video.extract_frames(
        source,
        [float(row["pts"] * base) for row in manifest["frames"]],
        private_dir,
        max_frames=len(manifest["frames"]),
        jpeg_quality=92,
        max_dimension=None,
        metadata=metadata,
    )
    bind_frames(manifest, frames, require_pixels=require_pixels)
    return metadata, frames


def snapshot(
    observation: dict[str, Any],
    trace: dict[str, Any],
    visual: dict[str, Any] | None,
    zone: dict[str, Any] | None,
) -> dict[str, Any]:
    signals = trace["signals"]
    quality = observation["quality"]
    structures = {}
    for name in ("hp_hud_structure", "ability_bar_structure", "weapon_ammo_structure"):
        score = signals.get(name + "_confidence")
        structures[name] = {
            "accepted": signals.get(name) is True
            and isinstance(score, (float, int))
            and not isinstance(score, bool)
            and 0.90 <= score <= 1.0,
            "score": score,
            "threshold": 0.90,
            "measured": name in signals or score is not None,
        }
    return {
        "primary_state": observation["primary_state"],
        "state_confidence": quality["state_confidence"],
        "hud_confidence": quality["hud_confidence"],
        "ownership": observation["values"]["player_specific_hud_valid"],
        "world_eligible": observation.get("view_context", {}).get(
            "is_player_world_view_trustworthy", False
        ),
        "reader_values": {
            key: deepcopy(observation["values"].get(key))
            for key in (
                "round_time_remaining_sec",
                "score_ally",
                "score_enemy",
                "ally_alive",
                "enemy_alive",
                "hp",
                "armor",
                "ammo_current",
                "ammo_reserve",
                "weapon_text",
                "ability_slots",
                "spike_state",
                "location_text",
                "kill_feed_rows",
                "round_end_text",
            )
        },
        "accepted_reader_values": deepcopy(trace["raw_accepted_reader_values"]),
        "relevant_roi_confidences": deepcopy(quality["roi_confidence"]),
        "identity": deepcopy(trace["identity"]),
        "geometry_valid": trace["geometry_calibrated"],
        "structures": structures,
        "spectator": {
            "checked": signals.get("spectator_detector_checked"),
            "present": signals.get("spectator_panel_present"),
            "absent": signals.get("spectator_panel_absent"),
            "reason": signals.get("spectator_detector_reason", "not_evaluated"),
        },
        "evidence": {
            key: deepcopy(signals.get(key))
            for key in (
                "combat_report_visible",
                "combat_report_confidence",
                "buy_menu_grid_present",
                "buy_menu_grid_confidence",
                "buy_menu_close_anchor_present",
                "buy_menu_close_anchor_confidence",
                "expanded_map_present",
                "expanded_map_stable",
                "map_transition",
                "remote_texture_candidate",
                "remote_control_candidate",
                "astral_geometry",
                "purple_palette",
                "astra_hand_interface",
                "astral_geometry_confidence",
                "purple_palette_confidence",
                "astra_hand_interface_confidence",
                "cypher_camera_template",
                "sova_drone_template",
                "skye_trailblazer_template",
                "other_remote_view_template",
            )
        },
        "remote_view_type": observation.get("remote_view_type"),
        "map_result": {
            "zone": deepcopy(zone),
            "minimap": deepcopy(visual.get("minimap")) if visual else None,
        },
        "visual_eligibility": deepcopy(visual.get("analysis_eligibility")) if visual else None,
        "state_flags": deepcopy(observation["state_flags"]),
    }


def replay_frames(
    processor: Any, metadata: Any, frames: list[Any], manifest: dict[str, Any]
) -> dict[str, Any]:
    """Use production postprocessing and its actual passive HUD trace."""
    bind_frames(manifest, frames)
    traces: list[dict[str, Any]] = []
    analyzer = processor.analyzer
    previous = analyzer.diagnostic_sink
    analyzer.diagnostic_sink = traces.append
    try:
        result = processor.process_frames(
            metadata=metadata, match_id="fixed-regression", frames=frames
        )
    finally:
        analyzer.diagnostic_sink = previous
    if len(traces) != len(frames) or len(result.observations) != len(frames):
        raise ValueError("production replay trace population mismatch")
    visual = {row["frame_index"]: row for row in result.visual_observations}
    zones = {row["frame_index"]: row for row in result.zone_resolutions}
    rows = []
    for index, (record, observation, trace) in enumerate(
        zip(manifest["frames"], result.observations, traces, strict=True)
    ):
        if trace["frame_index"] != index:
            raise ValueError("production replay trace order mismatch")
        frame_key = f"{manifest['stream_index']}:{record['pts']}:{record['source_frame_index']}"
        rows.append(
            {
                "frame_key": frame_key,
                "snapshot": snapshot(observation, trace, visual.get(index), zones.get(index)),
            }
        )
    return {
        "manifest_sha256": manifest_hash(manifest),
        "source_sha256": manifest["sourceSHA"],
        "frames": rows,
    }


def aggregate(replay: dict[str, Any]) -> dict[str, Any]:
    rows = [row["snapshot"] for row in replay["frames"]]
    return {
        "manifest_sha256": replay["manifest_sha256"],
        "source_sha256": replay["source_sha256"],
        "frame_count": len(rows),
        "logical_output_sha256": stable_hash(
            {key: value for key, value in replay.items() if key != "provenance"}
        ),
        "primary_states": dict(sorted(Counter(row["primary_state"] for row in rows).items())),
        "ownership": sum(row["ownership"] is True for row in rows),
        "world_eligible": sum(row["world_eligible"] is True for row in rows),
        "identity_reasons": dict(
            sorted(Counter(row["identity"]["reason"] for row in rows).items())
        ),
        "published_hp": sum(type(row["reader_values"].get("hp")) is int for row in rows),
        "published_timer": sum(
            row["reader_values"].get("round_time_remaining_sec") is not None for row in rows
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--hud-layout", type=Path, required=True)
    parser.add_argument("--private-dir", type=Path, required=True)
    parser.add_argument("--manual-map-id", default="")
    parser.add_argument("--seal-manifest", type=Path)
    parser.add_argument("--aggregate-output", type=Path)
    parser.add_argument("--repeat-check", action="store_true")
    args = parser.parse_args()
    from valorant_ai_coach.bootstrap import build_services
    from valorant_ai_coach.settings import AppSettings, SettingsStore

    args.private_dir.mkdir(parents=True, exist_ok=True)
    manifest = validate_manifest(json.loads(args.manifest.read_text(encoding="utf-8")))
    settings = AppSettings(
        data_dir=args.private_dir / "services",
        hud_mode="real",
        mock_ai=True,
        hud_layout_path=str(args.hud_layout.resolve()),
        manual_map_id=args.manual_map_id,
        visual_semantic_enabled=False,
    )
    services = build_services(SettingsStore(args.private_dir / "settings.json"), settings=settings)
    metadata, frames = extract_frames(
        services.video,
        args.source,
        manifest,
        args.private_dir / "frames",
        require_pixels=args.seal_manifest is None,
    )
    if args.seal_manifest:
        sealed = deepcopy(manifest)
        for record, frame in zip(sealed["frames"], frames, strict=True):
            record["pixel_sha256"] = decoded_hash(frame.path)
        print(write_manifest_immutable(args.seal_manifest, sealed))
        return 0
    processor = services.pipeline.hud_video_processor
    if processor is None:
        raise ValueError("real production processor required")
    replay = replay_frames(processor, metadata, frames, manifest)
    repeat_hash = None
    if args.repeat_check:
        repeated_settings = replace(settings, data_dir=args.private_dir / "repeat-services")
        repeated_services = build_services(
            SettingsStore(args.private_dir / "repeat-settings.json"), settings=repeated_settings
        )
        repeated_processor = repeated_services.pipeline.hud_video_processor
        if repeated_processor is None:
            raise ValueError("real repeated production processor required")
        repeated = replay_frames(repeated_processor, metadata, frames, manifest)
        repeat_hash = stable_hash(repeated)
        if repeat_hash != stable_hash(replay):
            raise ValueError("same-input fresh-service replay stability failed")
    implementation = hashlib.sha256()
    paths = sorted(Path("src").rglob("*.py")) + sorted(Path("scripts").glob("*replay*.py"))
    for path in paths:
        implementation.update(path.as_posix().encode())
        implementation.update(path.read_bytes())
    replay["provenance"] = {
        "analyzer_commit": subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip(),
        "git_is_dirty": bool(subprocess.check_output(["git", "status", "--porcelain"], text=True)),
        "implementation_sha256": implementation.hexdigest(),
        "hud_fingerprint": processor.analyzer.fingerprint(),
        "visual_fingerprint_sha256": stable_hash(processor.visual_analyzer.fingerprint()),
    }
    with (args.private_dir / "replay.json").open("x", encoding="utf-8") as handle:
        json.dump(replay, handle, sort_keys=True, allow_nan=False)
    summary = aggregate(replay)
    summary["provenance"] = replay["provenance"]
    summary["fresh_service_repeat_sha256"] = repeat_hash
    summary["fresh_service_repeat_exact"] = repeat_hash == summary["logical_output_sha256"]
    if repeat_hash is None:
        summary["fresh_service_repeat_exact"] = None
    if args.aggregate_output:
        with args.aggregate_output.open("x", encoding="utf-8") as handle:
            json.dump(summary, handle, indent=2, sort_keys=True, allow_nan=False)
    print(json.dumps(summary, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
