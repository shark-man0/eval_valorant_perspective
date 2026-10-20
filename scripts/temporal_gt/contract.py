"""Offline temporal-label integrity checks; no recognizer, evaluator or decoder call."""

from __future__ import annotations

import hashlib
import json
from collections import Counter
from fractions import Fraction
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator

from valorant_ai_coach.hud.global_lifecycle import global_recognizer_fingerprint
from valorant_ai_coach.hud.templates import HudTemplateProfile
from valorant_ai_coach.hud.unedited_input import UneditedInputContract
from valorant_ai_coach.video.native import NativeSourceFrame, _sha256

VERSION = "round-end-temporal-v1"
NEGATIVE_CLASSES = (
    "countdown",
    "score_only",
    "clock_only",
    "spike_only",
    "decimal_only",
    "partial_caption",
    "stale_caption",
    "buy",
    "menu",
    "spectator",
    "source_break",
    "pts_gap",
    "repeated_raster",
)
EXPOSURE_TYPES = (
    "training",
    "reference",
    "threshold_or_timing_tuning",
    "prediction",
    "prediction_review",
    "source_only_view",
    "gt_creation",
    "holdout_evaluation",
    "verified_unused",
    "unknown",
)
SCHEMA = Path(__file__).resolve().parents[2] / "schemas/round_end_temporal_dataset_v1.json"


class ContractError(ValueError):
    """Messages contain rule names only, never private labels, paths or PTS."""


def canonical_hash(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(
            value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False
        ).encode("utf-8")
    ).hexdigest()


def require(condition: bool, rule: str) -> None:
    if not condition:
        raise ContractError(rule)


def indexed(rows: list[dict[str, Any]], rule: str) -> dict[str, dict[str, Any]]:
    result = {row["id"]: row for row in rows}
    require(len(result) == len(rows), rule)
    return result


def valid_pts(value: Any) -> bool:
    return type(value) is int and value >= 0


def ticks(row: dict[str, Any]) -> tuple[int, int, Fraction]:
    require(valid_pts(row["start_tick"]) and valid_pts(row["end_tick"]), "integer_pts")
    require(row["start_tick"] <= row["end_tick"], "reversed_window")
    base = Fraction(row["time_base"])
    require(base > 0 and str(base) == row["time_base"], "canonical_positive_timebase")
    return row["start_tick"], row["end_tick"], base


def overlap(a: dict[str, Any], b: dict[str, Any], guard: int = 0) -> bool:
    x, y, tb = ticks(a)
    u, v, ub = ticks(b)
    return x * tb - guard <= v * ub and u * ub - guard <= y * tb


def validate(dataset: dict[str, Any], *, verify_files: bool = True) -> dict[str, Any]:
    """Consistency is not proof that a curator's historical claims are truthful."""
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    require(not list(Draft202012Validator(schema).iter_errors(dataset)), "schema")
    require(dataset["version"] == VERSION, "version")
    sources = indexed(dataset["sources"], "duplicate_source")
    events = indexed(dataset["events"], "duplicate_event")
    require(len({s["sha256"] for s in sources.values()}) == len(sources), "aliased_source_sha")
    require(
        len({e["physical_event_key"] for e in events.values()}) == len(events),
        "aliased_physical_event",
    )
    actors = indexed(dataset["actors"], "duplicate_actor")
    evidence = indexed(dataset["evidence"], "duplicate_evidence")
    method = dataset["method"]
    require(method["developer_id"] in actors, "method_developer")
    require(set(dataset["audit"]["evidence_ids"]) <= set(evidence), "audit_evidence")
    policy_path = SCHEMA.parent.parent / "docs/temporal_gt/readiness_policy_v1.json"
    require(
        method["evaluation_policy_version"] == "round-end-temporal-readiness-v1"
        and method["evaluation_policy_sha256"] == _sha256(policy_path),
        "evaluation_policy",
    )
    method_files_verified = False
    if verify_files and all(
        method[k] is not None
        for k in ["profile_path", "template_profile_path", "assets_manifest_path"]
    ):
        try:
            profile = HudTemplateProfile.load(Path(method["template_profile_path"]))
            require(
                profile.fingerprint(Path(method["profile_path"])) == method["profile_sha256"],
                "profile_fingerprint",
            )
            path = Path(method["assets_manifest_path"])
            require(_sha256(path) == method["assets_sha256"], "assets_manifest_hash")
            assets = json.loads(path.read_text(encoding="utf-8"))["files"]
            require(bool(assets), "empty_assets")
            for asset in assets:
                require(_sha256(Path(asset["path"])) == asset["sha256"], "asset_hash")
            bound_paths = {str(Path(x["path"]).resolve()) for x in assets}
            require(
                {str(profile.resolve_asset(str(x)).resolve()) for x in profile.asset_paths}
                <= bound_paths,
                "missing_profile_asset",
            )
            method_files_verified = True
        except (OSError, KeyError, ValueError) as exc:
            raise ContractError("method_asset_integrity") from exc
    for item in evidence.values():
        require(type(item["order"]) is int, "evidence_order")
        if verify_files:
            try:
                require(_sha256(Path(item["path"])) == item["sha256"], "evidence_hash")
            except OSError as exc:
                raise ContractError("evidence_unavailable") from exc
    verified_sources = set()
    for source in sources.values():
        if verify_files and source["path"] is not None:
            try:
                require(_sha256(Path(source["path"])) == source["sha256"], "source_sha")
                if source["contract_path"] is not None:
                    contract = UneditedInputContract.load(
                        Path(source["contract_path"]), source_video_sha256=source["sha256"]
                    )
                    require(contract.fingerprint == source["contract_sha256"], "source_contract")
                    verified_sources.add(source["id"])
            except (OSError, ValueError) as exc:
                raise ContractError("source_integrity") from exc
    for event in events.values():
        require(event["source_id"] in sources, "unknown_source")
        source = sources[event["source_id"]]
        require(event["source_sha256"] == source["sha256"], "event_source_sha")
        ticks(event["window"])
        if source["time_base"] is not None:
            require(event["window"]["time_base"] == source["time_base"], "event_timebase")
    allocation: dict[str, dict[str, Any]] = {}
    for row in dataset["allocations"]:
        eid = row["event_id"]
        require(eid in events, "unknown_event")
        require(eid not in allocation, "duplicate_split_event")
        require(type(row["assigned_order"]) is int, "allocation_order")
        allocation[eid] = row
        if sources[events[eid]["source_id"]]["sealed_reserved"]:
            require(row["split"] == "unknown" and not row["opened"], "sealed_reserved_source")
        if row["split"].startswith("holdout"):
            require(row["assigned_order"] >= method["frozen_order"], "method_not_frozen")
            require(
                events[eid]["physical_event_key"] not in method["reference_parent_keys"],
                "reference_parent_leak",
            )
            require(
                row["independence"] == "verified" and row["reviewer_id"] in actors,
                "holdout_independence",
            )
            actor = actors[row["reviewer_id"]]
            require(
                actor["independent"] and actor["id"] != method["developer_id"],
                "independent_curator",
            )
            require(row["authority_evidence_id"] in evidence, "allocation_authority")
            require(
                evidence[row["authority_evidence_id"]]["order"] <= row["assigned_order"],
                "allocation_authority_order",
            )
            require(row["consumed_methods"] == [], "holdout_reuse")
            require(events[eid]["physical_identity_verified"], "physical_event_identity")
        if row["opened"]:
            require(row["opening_authority_id"] in evidence, "unauthorized_opening")
            require(
                type(row["opened_order"]) is int and row["opened_order"] >= row["assigned_order"],
                "opening_order",
            )
    require(set(allocation) == set(events), "unallocated_event")
    for exposure in dataset["exposures"]:
        require(type(exposure["order"]) is int, "exposure_order")
        require(
            exposure["source_id"] in sources and exposure["evidence_id"] in evidence,
            "exposure_reference",
        )
        require(
            evidence[exposure["evidence_id"]]["order"] <= exposure["order"],
            "exposure_evidence_order",
        )
        if exposure["event_id"] is not None:
            require(exposure["event_id"] in events, "exposure_event")
            require(
                events[exposure["event_id"]]["source_id"] == exposure["source_id"],
                "exposure_source",
            )
        if exposure["window"] is not None:
            ticks(exposure["window"])
        for eid, event in events.items():
            assigned = allocation[eid]
            applies = (
                exposure["source_id"] == event["source_id"]
                and (exposure["event_id"] in (None, eid))
                and (exposure["window"] is None or overlap(exposure["window"], event["window"]))
            )
            if applies and assigned["split"].startswith("holdout"):
                prior = exposure["order"] < assigned["assigned_order"]
                require(not prior or exposure["kind"] == "verified_unused", "exposed_holdout")
                require(
                    exposure["kind"]
                    not in {
                        "training",
                        "reference",
                        "threshold_or_timing_tuning",
                        "prediction_review",
                        "unknown",
                    },
                    "holdout_exposure",
                )
                if exposure["kind"] == "prediction":
                    require(
                        assigned["opened"] and exposure["order"] >= assigned["opened_order"],
                        "sealed_prediction",
                    )
    event_list = list(events.values())
    for i, a in enumerate(event_list):
        for b in event_list[i + 1 :]:
            sa, sb = allocation[a["id"]]["split"], allocation[b["id"]]["split"]
            if a["source_id"] == b["source_id"] and sa != sb:
                require(
                    not overlap(a["window"], b["window"], dataset["adjacency_guard_sec"]),
                    "cross_split_adjacent_or_overlapping",
                )
    frame_splits: dict[str, str] = {}
    for frame in dataset["frames"]:
        require(frame["event_id"] in events, "frame_event")
        event = events[frame["event_id"]]
        split = allocation[frame["event_id"]]["split"]
        prior_split = frame_splits.setdefault(frame["pixel_sha256"], split)
        require(prior_split == split, "cross_split_duplicate_raster")
        require(frame["source_sha256"] == event["source_sha256"], "frame_source_sha")
        require(
            frame["epoch"] == event["epoch"] and frame["time_base"] == event["window"]["time_base"],
            "frame_epoch_or_timebase_mix",
        )
        require(
            valid_pts(frame["tick"])
            and event["window"]["start_tick"] <= frame["tick"] <= event["window"]["end_tick"],
            "frame_pts",
        )
        if verify_files:
            try:
                NativeSourceFrame(
                    Path(frame["path"]),
                    frame["tick"],
                    Fraction(frame["time_base"]),
                    frame["epoch"],
                    frame["source_sha256"],
                    frame["encoded_sha256"],
                    frame["pixel_sha256"],
                    frame["width"],
                    frame["height"],
                ).read_image()
            except (OSError, ValueError, RuntimeError) as exc:
                raise ContractError("native_frame_integrity") from exc
    labels: dict[str, dict[str, Any]] = {}
    for label in dataset["annotations"]:
        eid = label["event_id"]
        require(eid in events and eid not in labels, "annotation_event")
        labels[eid] = label
        event, assigned = events[eid], allocation[eid]
        require(
            label["annotation_target"] != "internal_game_end" or label["verdict"] == "unknown",
            "video_does_not_prove_internal_end",
        )
        require(label["source_sha256"] == event["source_sha256"], "annotation_source_sha")
        require(
            label["epoch"] == event["epoch"] and label["time_base"] == event["window"]["time_base"],
            "annotation_epoch_mix",
        )
        for key in [
            "last_old_frame_pts",
            "first_new_frame_pts",
            "last_partial_caption_pts",
            "first_complete_caption_pts",
            "active_start_pts",
            "next_round_pts",
        ]:
            value = label[key]
            require(value is None or valid_pts(value), "annotation_integer_pts")
            if value is not None:
                require(
                    event["window"]["start_tick"] <= value <= event["window"]["end_tick"],
                    "annotation_outside_window",
                )
        for left, right in [
            ("last_old_frame_pts", "first_new_frame_pts"),
            ("last_partial_caption_pts", "first_complete_caption_pts"),
        ]:
            if label[left] is not None and label[right] is not None:
                require(label[left] < label[right], "reversed_bracket")
        if label["active_start_pts"] is not None and label["next_round_pts"] is not None:
            require(label["active_start_pts"] < label["next_round_pts"], "reversed_trajectory")
        if label["first_complete_caption_pts"] is not None:
            require(
                label["caption_state"] == "complete"
                and label["caption_type"] in {"LOST", "WON", "CLUTCH", "TEAM ACE"},
                "partial_is_not_complete",
            )
            require(label["caption_literal"] == label["caption_type"], "complete_caption_literal")
        if label["verdict"] == "negative":
            require(
                label["event_type"] == "non_end" and label["annotation_target"] == "no_end_display",
                "negative_target",
            )
        require(
            label["provenance_ids"] and set(label["provenance_ids"]) <= set(evidence),
            "annotation_provenance",
        )
        if label["status"] == "independently_reviewed":
            require(label["review_order"] >= assigned["assigned_order"], "review_before_allocation")
            require(label["reviewer_id"] in actors, "annotation_reviewer")
            actor = actors[label["reviewer_id"]]
            require(
                actor["independent"] and actor["id"] != method["developer_id"],
                "annotation_independence",
            )
        require(type(label["review_order"]) is int, "review_order")
        require(
            all(evidence[x]["order"] <= label["review_order"] for x in label["provenance_ids"]),
            "annotation_provenance_order",
        )
        if assigned["split"] == "holdout_negative":
            require(
                label["verdict"] == "negative"
                and label["status"] == "independently_reviewed"
                and label["negative_class"] in NEGATIVE_CLASSES,
                "unknown_is_not_negative",
            )
        if assigned["split"] == "holdout_positive":
            require(
                label["verdict"] == "positive" and label["status"] == "independently_reviewed",
                "positive_truth_required",
            )
        if label["verdict"] == "unknown":
            require(label["unscorable_reason"] is not None, "unknown_reason")
    for eid, row in allocation.items():
        require(
            not row["split"].startswith("holdout") or eid in labels, "holdout_annotation_missing"
        )
    counts = Counter(x["split"] for x in allocation.values())
    negative = {
        kind: sum(
            allocation[eid]["split"] == "holdout_negative" and x["negative_class"] == kind
            for eid, x in labels.items()
        )
        for kind in NEGATIVE_CLASSES
    }
    missing = [kind for kind, count in negative.items() if count == 0]
    blockers = []
    if not dataset["audit"]["history_complete"]:
        blockers.append("exposure_history_incomplete")
    if not dataset["audit"]["reference_lineage_complete"]:
        blockers.append("reference_lineage_incomplete")
    if counts["holdout_positive"] < 2:
        blockers.append("fewer_than_two_independent_positive_events")
    if missing:
        blockers.append("natural_negative_coverage_incomplete")
    if (
        method["profile_sha256"] is None
        or method["assets_sha256"] is None
        or not method_files_verified
    ):
        blockers.append("method_assets_not_frozen")
    if method["recognizer_sha256"] != global_recognizer_fingerprint():
        blockers.append("method_code_not_current")
    if not verify_files:
        blockers.append("source_integrity_not_verified")
    typed = sum(
        allocation[eid]["split"] == "holdout_positive"
        and label["clock_before"]["type"] == "spike"
        and label["clock_after"]["type"] == "decimal"
        for eid, label in labels.items()
    )
    if typed < 2:
        blockers.append("fewer_than_two_spike_decimal_replications")
    for eid, row in allocation.items():
        if row["split"].startswith("holdout"):
            event, label = events[eid], labels[eid]
            source = sources[event["source_id"]]
            if not label["interval_fully_reviewed"]:
                blockers.append("annotation_coverage_incomplete")
            support_ticks = {f["tick"] for f in dataset["frames"] if f["event_id"] == eid}
            witnesses = {
                label[k]
                for k in [
                    "last_old_frame_pts",
                    "first_new_frame_pts",
                    "last_partial_caption_pts",
                    "first_complete_caption_pts",
                    "active_start_pts",
                    "next_round_pts",
                ]
                if label[k] is not None
            }
            if not support_ticks or not witnesses <= support_ticks:
                blockers.append("source_witness_frames_incomplete")
            if label["annotation_target"] not in {"display_end_episode", "no_end_display"}:
                blockers.append("annotation_target_is_not_temporal_episode")
            if event["source_id"] not in verified_sources:
                blockers.append("source_bytes_and_contract_not_verified")
            if source["preflight_path"] is None or source["contract_path"] is None:
                blockers.append("source_preflight_missing")
            elif verify_files:
                try:
                    path = Path(source["preflight_path"])
                    require(_sha256(path) == source["preflight_sha256"], "preflight_hash")
                    preflight = json.loads(path.read_text(encoding="utf-8"))
                    require(
                        preflight["source_video_sha256"] == source["sha256"]
                        and preflight["input_contract_sha256"] == source["contract_sha256"]
                        and preflight["terminal_integrity_verified"] is True
                        and preflight["recognizer_fingerprint"] == method["recognizer_sha256"]
                        and preflight["qualification_established"] is False
                        and preflight["recognition_executed"] is False,
                        "preflight_binding",
                    )
                except (OSError, KeyError, ValueError) as exc:
                    raise ContractError("preflight_integrity") from exc
            if (
                not event["continuity_reviewed"]
                or event["epoch"] is None
                or event["continuity_segment"] is None
            ):
                blockers.append("source_continuity_unproven")
            if row["split"] == "holdout_positive" and (
                label["round_context"] is None
                or label["score_before"] is None
                or label["score_after"] is None
                or label["source_discontinuity"] is not False
                or label["clock_before"]["type"] in {"unknown", "occluded"}
                or label["clock_after"]["type"] in {"unknown", "occluded"}
            ):
                blockers.append("temporal_context_incomplete")
            if row["split"] == "holdout_positive" and any(
                label[k] is None
                for k in [
                    "last_old_frame_pts",
                    "first_new_frame_pts",
                    "last_partial_caption_pts",
                    "first_complete_caption_pts",
                    "active_start_pts",
                    "next_round_pts",
                ]
            ):
                blockers.append("full_temporal_brackets_incomplete")
    return {
        "version": VERSION,
        "dataset_sha256": canonical_hash(dataset),
        "readiness": "BLOCKED" if blockers else "QUALIFICATION_READY",
        "blockers": sorted(set(blockers)),
        "source_count": len(sources),
        "event_record_count": len(events),
        "verified_physical_event_count": sum(
            e["physical_identity_verified"] for e in events.values()
        ),
        "unresolved_event_identity_count": sum(
            not e["physical_identity_verified"] for e in events.values()
        ),
        "split_counts": dict(counts),
        "annotation_status_counts": dict(Counter(x["status"] for x in labels.values())),
        "negative_physical_event_counts": negative,
        "missing_negative_classes": missing,
        "formal_End_qualified": False,
        "recognition_executed": False,
        "mechanical_consistency_only": True,
    }
