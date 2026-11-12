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
from copy import deepcopy
from fractions import Fraction
from pathlib import Path
from typing import Any

from .evidence import digest, native_time
from .game import DevelopmentGameTimeline, observation, round_number_summary
from .hud_value_projection import attach_hud_values
from .hud_visibility import visibility_summary
from .map_correspondence import correspondence_review
from .replay import SourcePolicy, file_sha, read_json, write_private
from .visibility_projection import attach_visibility
from .zone_projection import attach_viewed_zones

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
    unavailable: dict[str, list[dict[str, Any]]] = defaultdict(list)
    aliases = {"round_timer": "timer", "weapon_text": "weapon"}

    def add(
        name: str,
        value: Any,
        row: dict[str, Any],
        confidence: Any = None,
        scope: dict[str, Any] | None = None,
    ) -> None:
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
                **(
                    {
                        k: scope[k]
                        for k in (
                            "value_scope",
                            "current_weapon_selection",
                            "roi_geometry_qualification",
                        )
                        if isinstance(scope.get(k), str)
                    }
                    if scope
                    else {}
                ),
            }
        )

    for row in rows:
        raw, context = row["raw"], row["context"]
        for measured in raw.get("measurements", []) + raw.get("hud_value_measurements", []):
            if isinstance(measured, dict) and isinstance(measured.get("name"), str):
                name = aliases.get(measured["name"], measured["name"])
                if name in {*HUD_FIELDS, "ammo_current", "ammo_reserve"}:
                    value_only = measured in raw.get("hud_value_measurements", [])
                    if not value_only or measured.get("status") == "CANDIDATE":
                        add(name, measured.get("value"), row, measured.get("confidence"), measured)
                    if value_only:
                        fields.setdefault(name, [])
                        if measured.get("status") == "UNKNOWN":
                            unavailable[name].append(
                                {
                                    "reason": measured.get("reason", "unread"),
                                    "reader_roi": measured.get("reader_roi"),
                                    "evidence_ref": row["observation_id"],
                                    "sample_ref": row["sample"]["sample_sha256"],
                                }
                            )
        for key, value in raw.get("values", {}).items():
            name = aliases.get(key, key)
            if isinstance(value, dict):
                item = value.get("value")
                if key in {"player_hp_armor", "ammo_current_weapon", "weapon_inventory"}:
                    if isinstance(item, dict):
                        for component, observed in item.items():
                            target = aliases.get(component, component)
                            if target in {*HUD_FIELDS, "ammo_current", "ammo_reserve"}:
                                add(target, observed, row, value.get("confidence"))
                else:
                    add(name, item, row, value.get("confidence"))
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
        k: {
            "status": "CANDIDATES" if v else "UNKNOWN",
            "candidates": _unique(v),
            **({"unavailable_reasons": _unique(unavailable[k])} if unavailable[k] else {}),
        }
        for k, v in fields.items()
    }


def _exact_map_ui_rows(
    frame: dict[str, Any], observations: dict[str, dict[str, Any]]
) -> list[dict[str, Any]] | None:
    """Use scores only when their local indices address this exact Map pool."""
    packets = [
        observations[k]
        for k in frame["observation_ids"]
        if k in observations
        and observations[k]["sample"] == frame["sample"]
        and observations[k]["raw"].get("schema") == "map_consumer_provisional_v1"
    ]
    if len(packets) != 1 or packets[0]["map_candidates"] != frame["map"]["candidates"]:
        return None
    rows = packets[0]["raw"].get("ui", {}).get("rows", [])
    return rows if isinstance(rows, list) else None


def build_application_timeline(
    timeline: dict[str, Any],
    *,
    source: dict[str, Any],
    duration: Fraction,
    origin: Fraction,
    hud_value_observations: list[dict[str, Any]] | None = None,
    hud_visibility_observations: list[dict[str, Any]] | None = None,
    zone_observations: list[dict[str, Any]] | None = None,
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
            **({"round_membership": transition["round_membership"]}
               if "round_membership" in transition else {}),
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
    seconds: list[dict[str, Any]] = []
    has_composite_views = any("viewed_identity" in f for f in timeline["frames"])
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
                "hud_visibility_observations": visibility_summary(raw),
                "map_observations": {
                    "status": "CANDIDATES"
                    if any(m["candidates"] or m["zone_candidates"] for m in maps)
                    else "UNKNOWN",
                    "observation_present": any(m["observation_present"] for m in maps),
                    "map_name_candidates": [
                        c for m in maps for c in m.get("map_name_candidates", [])
                    ],
                    "position_candidates": [c for m in maps for c in m["candidates"]],
                    "current_self_position_candidates": [
                        c for m in maps for c in m["current_self_position_candidates"]
                    ],
                    "zone_candidates": [c for m in maps for c in m["zone_candidates"]],
                    "marker_associations": [c for m in maps for c in m["marker_associations"]],
                    "movement_candidates": [],
                    "correspondence_reviews": [
                        {
                            "sample_ref": f["sample"]["sample_sha256"],
                            **correspondence_review(
                                f["map"]["candidates"],
                                f["map"]["current_self_position_candidates"],
                                f["map"].get("provisional_recorder_position_hypotheses", []),
                                f["map"]["current_recorder_view_evidence_ids"],
                                ui_rows=_exact_map_ui_rows(f, observations),
                            ),
                        }
                        for f in current
                        if f["map"]["observation_present"]
                    ],
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
        if timeline["configuration"].get("provisional_map_roles"):
            seconds[-1]["map_observations"]["provisional_recorder_position_hypotheses"] = _unique(
                [h for m in maps for h in m.get("provisional_recorder_position_hypotheses", [])]
            )
        if has_composite_views:
            seconds[-1]["map_observations"]["research_view_position_hypotheses"] = [
                h for m in maps for h in m.get("research_view_position_hypotheses", [])
            ]
            seconds[-1]["map_observations"]["marker_ranking_hypotheses"] = [
                m["marker_ranking_hypotheses"] for m in maps
                if "marker_ranking_hypotheses" in m
            ]
            seconds[-1]["viewed_identity_observations"] = [
                {"sample_ref": f["sample"]["sample_sha256"], **f["viewed_identity"]}
                for f in current if "viewed_identity" in f
            ]
    result: dict[str, Any] = {
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
            "map_name": "Generic pixel reader; bundled registry alignment candidates only"
            if any(r["raw"].get("schema") == "development_generic_map_pixels_v1"
                   for r in observations.values())
            else "No current generic reader",
            "movement": "Not inferred",
            "unsupported_HUD": "UNKNOWN; raw supplier output retained",
        },
    }
    if hud_value_observations:
        attach_hud_values(result, hud_value_observations, _hud)
    if hud_visibility_observations:
        attach_visibility(result, hud_visibility_observations)
    if zone_observations:
        attach_viewed_zones(result, zone_observations)
    if has_composite_views:
        from .round_visual import attach_round_visual_candidates

        attach_round_visual_candidates(result)
    if "superseded_transition_candidates" in timeline:
        result["superseded_transition_candidates"] = deepcopy(
            timeline["superseded_transition_candidates"]
        )
    return result


def export_application(
    *,
    timeline_path: Path,
    receipt_path: Path,
    policy_path: Path,
    output: Path,
    supplements: list[Path] | None = None,
    provisional_map_roles: bool = False,
    active_clock_bridge: bool = False,
    hud_values: list[Path] | None = None,
    hud_visibility: list[Path] | None = None,
    zone_observations: list[Path] | None = None,
    return_display_tail: bool = False,
    buy_clock_tail: bool = False,
    current_hp_return_candidate: bool = False,
    current_menu_return_candidate: bool = False,
    practical_visual_state: bool = False,
) -> dict[str, Any]:
    """Admission, optional existing-engine join, JSON/CSV and evaluation handoff."""
    from valorant_ai_coach.rules.development_timeline import review_timeline

    if any(
        type(v) is not bool
        for v in (
            provisional_map_roles,
            active_clock_bridge,
            return_display_tail,
            buy_clock_tail,
            current_hp_return_candidate,
            current_menu_return_candidate,
            practical_visual_state,
        )
    ):
        raise ValueError("Explicit development Map/clock booleans required")
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
        for p in [
            timeline_path,
            receipt_path,
            policy_path,
            *(supplements or []),
            *(hud_values or []),
            *(hud_visibility or []),
            *(zone_observations or []),
        ]
    }
    extra = []
    for path in supplements or []:
        data = read_json(path)
        for row in data["observations"]:
            if row["sample"]["source_sha256"] == source["source_sha256"]:
                policy.admit(row["sample"])
                extra.append(row)
    if (
        extra
        or provisional_map_roles
        or active_clock_bridge
        or return_display_tail
        or buy_clock_tail
        or current_hp_return_candidate
        or current_menu_return_candidate
        or practical_visual_state
    ):
        config = timeline["configuration"]
        engine = DevelopmentGameTimeline(
            fuse_exact_native_evidence=config.get("fuse_exact_native_evidence", False),
            report_view_bridge=bool(config.get("report_view_bridge")),
            forward_only=config.get("forward_only", False),
            mark_round_transition_gaps=config.get("mark_round_transition_gaps", False),
            buy_clock_expiry=bool(config.get("buy_clock_expiry")),
            provisional_map_roles=(
                provisional_map_roles or bool(config.get("provisional_map_roles"))
            ),
            active_clock_bridge=active_clock_bridge or bool(config.get("active_clock_bridge")),
            return_display_tail=return_display_tail or bool(config.get("return_display_tail")),
            buy_clock_tail=buy_clock_tail or bool(config.get("buy_clock_tail")),
            current_hp_return_candidate=current_hp_return_candidate
            or bool(config.get("current_hp_return_candidate")),
            current_menu_return_candidate=current_menu_return_candidate
            or bool(config.get("current_menu_return_candidate")),
            practical_visual_state=practical_visual_state
            or bool(config.get("practical_visual_state")),
        )
        for row in timeline["observations"] + extra:
            engine.add(row)
        timeline = engine.rebuild()
    for row in timeline["observations"]:
        policy.admit(row["sample"])
    value_rows = []
    for path in hud_values or []:
        for row in read_json(path)["observations"]:
            if row["sample"]["source_sha256"] == source["source_sha256"]:
                policy.admit(row["sample"])
                value_rows.append(row)
    base = Fraction(timeline["frames"][0]["sample"]["native_time_base"])
    visibility_rows = []
    for path in hud_visibility or []:
        for row in read_json(path)["observations"]:
            if row["sample"]["source_sha256"] == source["source_sha256"]:
                policy.admit(row["sample"])
                visibility_rows.append(row)
    zone_rows = []
    for path in zone_observations or []:
        for row in read_json(path)["observations"]:
            if row["sample"]["source_sha256"] == source["source_sha256"]:
                policy.admit(row["sample"])
                zone_rows.append(row)
    bundle = build_application_timeline(
        timeline,
        source=source,
        duration=Fraction(receipt["duration_seconds"]),
        origin=receipt["native_start_pts_tick"] * base,
        hud_value_observations=value_rows,
        hud_visibility_observations=visibility_rows,
        zone_observations=zone_rows,
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
                Path(__file__).with_name("map_roles.py"),
                Path(__file__).with_name("hud_value_projection.py"),
                Path(__file__).with_name("pixel_projection.py"),
                Path(__file__).with_name("visibility_projection.py"),
                Path(__file__).with_name("hud_visibility.py"),
                Path(__file__).with_name("zone_projection.py"),
                Path(__file__).with_name("zone_contract.py"),
                Path(__file__).parent.parent / "rules" / "development_timeline.py",
            )
        },
        "inputs": input_bindings,
        "original_recording_sha256": source["source_sha256"],
        "supplement_observations_supplied": len(extra),
        "HUD_value_observations_supplied": len(value_rows),
        "HUD_visibility_observations_supplied": len(visibility_rows),
        "HUD_zone_observations_supplied": len(zone_rows),
        "provisional_map_roles_requested_for_export": provisional_map_roles,
        "active_clock_bridge_requested_for_export": active_clock_bridge,
        "return_display_tail_requested_for_export": return_display_tail,
        "buy_clock_tail_requested_for_export": buy_clock_tail,
        "current_hp_return_candidate_requested_for_export": current_hp_return_candidate,
        "current_menu_return_candidate_requested_for_export": current_menu_return_candidate,
        "practical_visual_state_requested_for_export": practical_visual_state,
        "export_engine_configuration": timeline["configuration"],
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
    export.add_argument("--provisional-map-roles", action="store_true")
    export.add_argument("--active-clock-bridge", action="store_true")
    export.add_argument("--hud-values", type=Path, action="append", default=[])
    export.add_argument("--hud-visibility", type=Path, action="append", default=[])
    export.add_argument("--zone-observations", type=Path, action="append", default=[])
    export.add_argument("--return-display-tail", action="store_true")
    export.add_argument("--buy-clock-tail", action="store_true")
    export.add_argument("--current-hp-return-candidate", action="store_true")
    export.add_argument("--current-menu-return-candidate", action="store_true")
    export.add_argument("--practical-visual-state", action="store_true")
    generate = sub.add_parser("generate")
    for name in ("policy", "reader-config", "output"):
        generate.add_argument("--" + name, type=Path, required=True)
    generate.add_argument("--source-id", required=True)
    generate.add_argument("--observer", help="Optional image-only supplier module:class")
    generate.add_argument("--checkpoint-dir", type=Path,
                          help="Opt-in exact-binding partial native observation reuse")
    generate.add_argument(
        "--reuse-acquisition", type=Path, help="Reuse a completed, hash-verified whole acquisition"
    )
    generate.add_argument("--max-refinement-windows", type=int, default=40)
    generate.add_argument("--coarse-seconds", type=Fraction)
    generate.add_argument("--dense-seconds", type=Fraction)
    generate.add_argument("--max-refinement-seconds", type=Fraction)
    generate.add_argument("--full-density", action="store_true")
    generate.add_argument("--refinement-policy", choices=["chronological", "balanced", "evidence"])
    generate.add_argument("--refinement-padding-seconds", type=Fraction)
    generate.add_argument("--report-view-bridge", action="store_true")
    generate.add_argument("--buy-clock-expiry", action="store_true")
    generate.add_argument("--provisional-map-roles", action="store_true")
    generate.add_argument("--active-clock-bridge", action="store_true")
    generate.add_argument("--return-display-tail", action="store_true")
    generate.add_argument("--buy-clock-tail", action="store_true")
    generate.add_argument("--current-hp-return-candidate", action="store_true")
    generate.add_argument("--current-menu-return-candidate", action="store_true")
    generate.add_argument("--practical-visual-state", action="store_true")
    generate.add_argument("--hud-values", type=Path, action="append", default=[])
    generate.add_argument("--hud-visibility", type=Path, action="append", default=[])
    generate.add_argument("--zone-observations", type=Path, action="append", default=[])
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
            if args.checkpoint_dir is not None:
                raise ValueError("Completed acquisition reuse and checkpoint reuse are separate")
            receipt = read_json(acquisition / "completion_PRIVATE.json")
            if receipt["source_id"] != args.source_id:
                raise ValueError("Reused acquisition belongs to another Source")
            sampling = receipt.get("sampling", {})
            if args.full_density and not sampling.get("full_density"):
                raise ValueError("Reused acquisition is not full-density")
            for field in ("coarse_seconds", "dense_seconds", "max_refinement_seconds"):
                requested = getattr(args, field)
                if requested is not None and Fraction(str(sampling.get(field))) != requested:
                    raise ValueError("Reused acquisition has different " + field)
            if (
                args.refinement_padding_seconds is not None
                and Fraction(sampling.get("refinement_padding_seconds", "1"))
                != args.refinement_padding_seconds
            ):
                raise ValueError("Reused acquisition has different refinement padding")
            if (
                args.refinement_policy is not None
                and sampling.get("selection_policy", "chronological") != args.refinement_policy
            ):
                raise ValueError("Reused acquisition has different refinement selection")
            if args.buy_clock_expiry and not read_json(acquisition / "timeline_PRIVATE.json")[
                "configuration"
            ].get("buy_clock_expiry"):
                raise ValueError("Reused acquisition does not contain BUY clock reconciliation")
            if args.provisional_map_roles and not read_json(acquisition / "timeline_PRIVATE.json")[
                "configuration"
            ].get("provisional_map_roles"):
                raise ValueError("Reused acquisition does not contain provisional Map roles")
            for flag in (
                "return_display_tail", "buy_clock_tail", "current_hp_return_candidate",
                "current_menu_return_candidate",
            ):
                if getattr(args, flag) and not read_json(acquisition / "timeline_PRIVATE.json")[
                    "configuration"
                ].get(flag):
                    raise ValueError("Reused acquisition does not contain requested " + flag)
            if args.active_clock_bridge and not read_json(acquisition / "timeline_PRIVATE.json")[
                "configuration"
            ].get("active_clock_bridge"):
                raise ValueError("Reused acquisition does not contain ACTIVE clock bridge")
        else:
            run_match(
                checkpoint_dir=args.checkpoint_dir,
                policy_path=args.policy,
                source_id=args.source_id,
                reader_config=args.reader_config,
                output=acquisition,
                observer_factory=factory,
                max_refinement_windows=args.max_refinement_windows,
                coarse_seconds=(args.coarse_seconds
                                if args.coarse_seconds is not None else Fraction(1)),
                dense_seconds=(args.dense_seconds
                               if args.dense_seconds is not None else Fraction(1, 5)),
                max_refinement_seconds=(
                    args.max_refinement_seconds
                    if args.max_refinement_seconds is not None else Fraction(240)
                ),
                full_density=args.full_density,
                refinement_selection_policy=args.refinement_policy or "chronological",
                refinement_padding_seconds=(
                    args.refinement_padding_seconds
                    if args.refinement_padding_seconds is not None
                    else Fraction(1)
                ),
                report_view_bridge=args.report_view_bridge,
                buy_clock_expiry=args.buy_clock_expiry,
                provisional_map_roles=args.provisional_map_roles,
                active_clock_bridge=args.active_clock_bridge,
                return_display_tail=args.return_display_tail,
                buy_clock_tail=args.buy_clock_tail,
                current_hp_return_candidate=args.current_hp_return_candidate,
                current_menu_return_candidate=args.current_menu_return_candidate,
                practical_visual_state=args.practical_visual_state,
            )
        result = export_application(
            timeline_path=acquisition / "timeline_PRIVATE.json",
            receipt_path=acquisition / "completion_PRIVATE.json",
            policy_path=args.policy,
            output=args.output / "application",
            practical_visual_state=args.practical_visual_state,
            hud_values=args.hud_values,
            hud_visibility=args.hud_visibility,
            zone_observations=args.zone_observations,
        )
    else:
        result = export_application(
            timeline_path=args.timeline,
            receipt_path=args.receipt,
            policy_path=args.policy,
            output=args.output,
            practical_visual_state=args.practical_visual_state,
            current_menu_return_candidate=args.current_menu_return_candidate,
            supplements=args.supplement,
            provisional_map_roles=args.provisional_map_roles,
            active_clock_bridge=args.active_clock_bridge,
            return_display_tail=args.return_display_tail,
            buy_clock_tail=args.buy_clock_tail,
            current_hp_return_candidate=args.current_hp_return_candidate,
            hud_values=args.hud_values,
            hud_visibility=args.hud_visibility,
            zone_observations=args.zone_observations,
        )
    print(json.dumps({"version": result["version"], "formal_outputs": 0}))


if __name__ == "__main__":
    main()
