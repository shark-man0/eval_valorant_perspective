"""Development application projection of the existing shared state engine.

No state machine, recognition thresholds or qualification are introduced here.
Recording seconds are views; native samples/observations and conflicts survive.
"""

from __future__ import annotations

import argparse
import csv
import importlib
import json
import math
from collections import defaultdict
from fractions import Fraction
from pathlib import Path
from typing import Any

from .evidence import digest, native_time
from .game import DevelopmentGameTimeline, observation, round_number_summary
from .replay import SourcePolicy, file_sha, read_json, write_private

VERSION = "development_application_timeline_v1"
HUD_FIELDS = ("hp", "armor", "weapon", "ammo", "timer", "score", "credits")


def _unique(values: list[Any]) -> list[Any]:
    return list({json.dumps(v, sort_keys=True, ensure_ascii=False): v for v in values}.values())


def _state(frames: list[dict[str, Any]], domain: str) -> dict[str, Any]:
    states = [f[domain] for f in frames]
    values = {s["value"] for s in states}
    return {
        "value": next(iter(values)) if len(values) == 1 else "UNKNOWN",
        "status": "UNKNOWN"
        if values == {"UNKNOWN"} or len(values) != 1
        else "OBSERVED"
        if all(s.get("origin") == "observation_projection" for s in states)
        else "INFERRED",
        "hypotheses": sorted({v for s in states for v in s["hypotheses"]}),
        "uncertainty": sorted({s["uncertainty"] for s in states}) or ["not_observed"],
        "evidence_refs": sorted({v for s in states for v in s["evidence_ids"]}),
        "native_estimates": [
            {"sample_ref": f["sample"]["sample_sha256"], "estimate": f[domain]} for f in frames
        ],
    }


def _hud(rows: list[dict[str, Any]]) -> dict[str, Any]:
    fields: dict[str, list[dict[str, Any]]] = {k: [] for k in HUD_FIELDS}

    def add(name: str, value: Any, row: dict[str, Any], confidence: Any = None) -> None:
        if value is None or value == "":
            return
        fields.setdefault(name, []).append(
            {
                "value": value,
                "status": "CANDIDATE",
                "subject": "viewed_HUD; recorder_ownership_unresolved",
                "confidence": confidence,
                "evidence_ref": row["observation_id"],
                "sample_ref": row["sample"]["sample_sha256"],
            }
        )

    for row in rows:
        raw, context = row["raw"], row["context"]
        for measured in raw.get("measurements", []):
            if isinstance(measured, dict) and isinstance(measured.get("name"), str):
                name = {"round_timer": "timer"}.get(measured["name"], measured["name"])
                if name in HUD_FIELDS:
                    add(name, measured.get("value"), row, measured.get("confidence"))
        for key, value in raw.get("values", {}).items():
            name = {"round_timer": "timer"}.get(key, key)
            if isinstance(value, dict):
                add(name, value.get("value"), row, value.get("confidence"))
        hp = raw.get("view_hp")
        if isinstance(hp, dict):
            add("hp", hp.get("display"), row, hp.get("confidence"))
        for key in (
            "hp",
            "armor",
            "weapon",
            "ammo",
            "credits",
            "timer",
            "ally_score",
            "enemy_score",
        ):
            value = raw.get(key)
            if isinstance(value, dict):
                add(key, value.get("value", value.get("display")), row, value.get("confidence"))
        add("timer", context.get("timer_seconds"), row)
        add("score", context.get("score"), row)
    return {
        k: {"status": "CANDIDATES" if v else "UNKNOWN", "candidates": _unique(v)}
        for k, v in fields.items()
    }


def build_application_timeline(
    timeline: dict[str, Any],
    *,
    source: dict[str, Any],
    duration: Fraction,
    origin: Fraction,
) -> dict[str, Any]:
    """Project one registered recording, without interpreting raw claims as facts."""
    if (
        timeline.get("version") != "development_game_timeline_v2"
        or timeline.get("formal_outputs") != 0
        or timeline.get("qualified_facts") != []
        or timeline.get("qualified_events") != []
    ):
        raise ValueError("Shared development timeline with empty formal outputs required")
    if duration <= 0:
        raise ValueError("Positive recording duration required")
    observations = {r["observation_id"]: r for r in timeline["observations"]}
    for row in observations.values():
        if row != observation(
            sample=row["sample"],
            producer=row["producer_fingerprint"],
            signals=row["signals"],
            raw=row["raw"],
            context=row["context"],
            continuity=row["continuity"],
            map_candidates=row["map_candidates"],
        ):
            raise ValueError("Original observation digest mismatch")
    frames = {f["sample"]["sample_sha256"]: f for f in timeline["frames"]}
    bins: dict[int, list[dict[str, Any]]] = defaultdict(list)
    for frame in frames.values():
        sample = frame["sample"]
        if sample["source_sha256"] != source["source_sha256"]:
            raise ValueError("Application bundle represents exactly one Source")
        second = int((native_time(sample) - origin) // 1)
        if second < 0 or second >= math.ceil(duration):
            raise ValueError("Native sample outside recording")
        if not set(frame["observation_ids"]) <= observations.keys():
            raise ValueError("Unresolvable frame evidence")
        bins[second].append(frame)
    events: dict[str, dict[str, Any]] = {}
    event_bins: dict[int, list[str]] = defaultdict(list)
    for row in observations.values():
        for candidate in row["raw"].get("event_candidates", []):
            if not isinstance(candidate, dict) or not isinstance(candidate.get("kind"), str):
                raise ValueError("Supplier event candidate requires a kind")
            timestamp = native_time(row["sample"]) - origin
            event = {
                "kind": candidate["kind"],
                "status": "CANDIDATE",
                "lower_timestamp": float(timestamp),
                "upper_timestamp": float(timestamp),
                "supplier_candidate": candidate,
                "internal_event_time": None,
                "timing_basis": "observation_time_not_verified_event_time",
                "evidence_refs": [row["observation_id"]],
                "qualified": False,
            }
            event_id = digest(event)
            events[event_id] = event
            second = math.floor(timestamp)
            if 0 <= second < math.ceil(duration):
                event_bins[second].append(event_id)
    for transition in timeline["transitions"]:
        low = native_time(transition["lower_sample"]) - origin
        high = native_time(transition["upper_sample"]) - origin
        event = {
            "kind": transition["kind"],
            "status": "CANDIDATE",
            "lower_timestamp": float(low),
            "upper_timestamp": float(high),
            "native_transition": transition,
            "internal_event_time": None,
            "evidence_refs": transition["evidence_ids"],
            "qualified": False,
        }
        event_id = digest(event)
        events[event_id] = event
        for second in range(
            max(0, math.floor(low)), min(math.ceil(duration), math.floor(high) + 1)
        ):
            event_bins[second].append(event_id)
    seconds = []
    for second in range(math.ceil(duration)):
        current = sorted(bins[second], key=lambda f: native_time(f["sample"]))
        refs = sorted({ref for f in current for ref in f["observation_ids"]})
        raw = [observations[ref] for ref in refs]
        maps = [f["map"] for f in current]
        seconds.append(
            {
                "timestamp": second,
                "end_timestamp": float(min(Fraction(second + 1), duration)),
                "native_start_seconds": str(origin + second),
                "observation_present": bool(current),
                "coverage": "sampled_points_only" if current else "not_observed",
                "confidence": None,
                "round_state": _state(current, "round"),
                "round_number": round_number_summary([f["round_number"] for f in current]),
                "life_state": _state(current, "life"),
                "camera_state": _state(current, "camera"),
                "hud_observations": _hud(raw),
                "map_observations": {
                    "status": "CANDIDATES"
                    if any(m["candidates"] or m["zone_candidates"] for m in maps)
                    else "UNKNOWN",
                    "observation_present": any(m["observation_present"] for m in maps),
                    "map_name_candidates": [],
                    "position_candidates": [c for m in maps for c in m["candidates"]],
                    "current_self_position_candidates": [
                        c for m in maps for c in m["current_self_position_candidates"]
                    ],
                    "zone_candidates": [c for m in maps for c in m["zone_candidates"]],
                    "marker_associations": [c for m in maps for c in m["marker_associations"]],
                    "movement_candidates": [],
                    "continuous_path": None,
                    "native_map_views": [
                        {"sample_ref": f["sample"]["sample_sha256"], "state": f["map"]}
                        for f in current
                        if f["map"]["observation_present"] or f["map"]["zone_candidates"]
                    ],
                },
                "event_candidates": list(dict.fromkeys(event_bins[second])),
                "evidence_refs": refs,
                "sample_refs": [f["sample"]["sample_sha256"] for f in current],
                "uncertainty": "development_unqualified; no truth assigned to entire second",
            }
        )
    return {
        "version": VERSION,
        "qualification": "development_only",
        "formal_outputs": 0,
        "source": {
            "source_id": source["video_id"],
            "source_sha256": source["source_sha256"],
            "physical_match_id": source["physical_match_id"],
        },
        "recording": {
            "duration_seconds": str(duration),
            "native_origin_seconds": str(origin),
            "start_timestamp": 0,
            "end_timestamp": float(duration),
        },
        "engine_configuration": timeline["configuration"],
        "seconds": seconds,
        "events": events,
        "observations": observations,
        "native_frames": frames,
        "revision_history": timeline["revision_history"],
        "field_limits": {
            "map_name": "No current generic reader",
            "movement": "Not inferred",
            "unsupported_HUD": "UNKNOWN; raw supplier output retained",
        },
    }


def export_application(
    *,
    timeline_path: Path,
    receipt_path: Path,
    policy_path: Path,
    output: Path,
    supplements: list[Path] | None = None,
) -> dict[str, Any]:
    """Admission, optional existing-engine join, JSON/CSV and evaluation handoff."""
    from valorant_ai_coach.rules.development_timeline import review_timeline

    if output.exists():
        raise ValueError("New output directory required")
    policy = SourcePolicy(read_json(policy_path))
    receipt, timeline = read_json(receipt_path), read_json(timeline_path)
    if not receipt["whole_file_completed"] or not receipt["source_bytes_verified_before_and_after"]:
        raise ValueError("Completed whole-file acquisition required")
    if file_sha(timeline_path) != receipt["artifact_sha256s"]["timeline_PRIVATE.json"]:
        raise ValueError("Acquired timeline digest mismatch")
    source = policy.allowed[receipt["source_sha256"]]
    video = Path(source["managed_path"])
    if file_sha(video) != source["source_sha256"]:
        raise ValueError("Registered original recording changed")
    input_bindings = {
        str(p.resolve()): file_sha(p)
        for p in [timeline_path, receipt_path, policy_path, *(supplements or [])]
    }
    extra = []
    for path in supplements or []:
        data = read_json(path)
        for row in data["observations"]:
            if row["sample"]["source_sha256"] == source["source_sha256"]:
                policy.admit(row["sample"])
                extra.append(row)
    if extra:
        config = timeline["configuration"]
        engine = DevelopmentGameTimeline(
            fuse_exact_native_evidence=config.get("fuse_exact_native_evidence", False),
            report_view_bridge=bool(config.get("report_view_bridge")),
            forward_only=config.get("forward_only", False),
            mark_round_transition_gaps=config.get("mark_round_transition_gaps", False),
        )
        for row in timeline["observations"] + extra:
            engine.add(row)
        timeline = engine.rebuild()
    for row in timeline["observations"]:
        policy.admit(row["sample"])
    base = Fraction(timeline["frames"][0]["sample"]["native_time_base"])
    bundle = build_application_timeline(
        timeline,
        source=source,
        duration=Fraction(receipt["duration_seconds"]),
        origin=receipt["native_start_pts_tick"] * base,
    )
    output.mkdir(parents=True, mode=0o700)
    write_private(output / "timeline_PRIVATE.json", bundle)
    write_private(output / "evaluation_PRIVATE.json", review_timeline(bundle))
    # A single CSV row per recording second; nested objects use JSON cells.
    with (output / "timeline_1s_PRIVATE.csv").open("w", encoding="utf-8", newline="") as stream:
        fields = list(bundle["seconds"][0])
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        for row in bundle["seconds"]:
            writer.writerow(
                {
                    k: json.dumps(v, ensure_ascii=False) if isinstance(v, (dict, list)) else v
                    for k, v in row.items()
                }
            )
    if any(file_sha(Path(p)) != sha for p, sha in input_bindings.items()):
        raise ValueError("Input changed during export")
    manifest = {
        "version": VERSION,
        "runtime_sha256s": {
            str(p): file_sha(p)
            for p in (
                Path(__file__),
                Path(__file__).with_name("game.py"),
                Path(__file__).parent.parent / "rules" / "development_timeline.py",
            )
        },
        "inputs": input_bindings,
        "original_recording_sha256": source["source_sha256"],
        "supplement_observations_supplied": len(extra),
        "output_sha256s": {p.name: file_sha(p) for p in output.iterdir()},
        "formal_outputs": 0,
    }
    write_private(output / "completion_PRIVATE.json", manifest)
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    export = sub.add_parser("export")
    for name in ("timeline", "receipt", "policy", "output"):
        export.add_argument("--" + name, type=Path, required=True)
    export.add_argument("--supplement", type=Path, action="append", default=[])
    generate = sub.add_parser("generate")
    for name in ("policy", "reader-config", "output"):
        generate.add_argument("--" + name, type=Path, required=True)
    generate.add_argument("--source-id", required=True)
    generate.add_argument("--observer", help="Optional image-only supplier module:class")
    generate.add_argument(
        "--reuse-acquisition", type=Path, help="Reuse a completed, hash-verified whole acquisition"
    )
    generate.add_argument("--max-refinement-windows", type=int, default=40)
    generate.add_argument("--report-view-bridge", action="store_true")
    args = parser.parse_args()
    if args.command == "generate":
        from .match import run_match
        from .match_observer import ProfileHudObserver

        factory: Any = ProfileHudObserver
        if args.observer:
            module, name = args.observer.split(":", 1)
            factory = getattr(importlib.import_module(module), name)
        acquisition = args.reuse_acquisition or args.output / "acquisition"
        if args.reuse_acquisition:
            if read_json(acquisition / "completion_PRIVATE.json")["source_id"] != args.source_id:
                raise ValueError("Reused acquisition belongs to another Source")
        else:
            run_match(
                policy_path=args.policy,
                source_id=args.source_id,
                reader_config=args.reader_config,
                output=acquisition,
                observer_factory=factory,
                max_refinement_windows=args.max_refinement_windows,
                report_view_bridge=args.report_view_bridge,
            )
        result = export_application(
            timeline_path=acquisition / "timeline_PRIVATE.json",
            receipt_path=acquisition / "completion_PRIVATE.json",
            policy_path=args.policy,
            output=args.output / "application",
        )
    else:
        result = export_application(
            timeline_path=args.timeline,
            receipt_path=args.receipt,
            policy_path=args.policy,
            output=args.output,
            supplements=args.supplement,
        )
    print(json.dumps({"version": result["version"], "formal_outputs": 0}))


if __name__ == "__main__":
    main()
