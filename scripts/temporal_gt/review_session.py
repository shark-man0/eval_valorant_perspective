"""Prediction-blind DEVELOPMENT review preparation and human-response import.

Round annotations use the unchanged Temporal GT contract. A Self Death companion
only adds labels, referring to the same source/event/frame/exposure backbone.
"""

from __future__ import annotations

import argparse
import json
import math
import os
import shutil
import subprocess
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from fractions import Fraction
from pathlib import Path
from typing import Any, cast

from jsonschema import Draft202012Validator

from scripts.diagnostics.register_private_sources import validate_inventory, write_private
from scripts.e2e.preflight_round_source import summarize_pixels
from scripts.e2e.run_dataset_case import read_json, sha256_file, valid_id
from scripts.temporal_gt.contract import (
    EXPOSURE_TYPES,
    NEGATIVE_CLASSES,
    SCHEMA,
    canonical_hash,
    require,
    validate,
)
from scripts.temporal_gt.validate_dataset import POLICY, check_freeze, freeze_record
from valorant_ai_coach.hud.calibrate_temporal import _check_output_privacy
from valorant_ai_coach.hud.global_lifecycle import global_recognizer_fingerprint
from valorant_ai_coach.video.native import NativeSourceFrame, decode_native_window

ROOT = Path(__file__).resolve().parents[2]
DEATH_SCHEMA = ROOT / "schemas/self_death_source_annotations_v1.json"


def private_directory(path: Path) -> None:
    path = path.resolve()
    _check_output_privacy(path)
    require(not any((p / ".git").exists() for p in (path, *path.parents)), "external_private_path")
    path.mkdir(parents=True, mode=0o700)


def registry_source(plan: dict[str, Any]) -> dict[str, Any]:
    batch = Path(plan["batch"])
    require(sha256_file(batch / "manifest.json") == plan["inventory_sha256"], "inventory_anchor")
    require(
        sha256_file(batch / "allocation.json") == plan["allocation_sha256"], "allocation_anchor"
    )
    value = read_json(batch / "manifest.json")
    validate_inventory(value)
    found = [r for r in value["records"] if r["video_id"] == plan["video_id"]]
    require(len(found) == 1, "source_identity")
    row = found[0]
    require(row["status"] == "accepted" and row["split"] == "DEVELOPMENT", "development_only")
    require(row["exposure"] == "DEVELOPMENT", "development_exposure")
    return cast(dict[str, Any], row)


def create_session(
    batch: Path, output: Path, inventory_anchor: str, allocation_anchor: str
) -> None:
    value = read_json(batch / "manifest.json")
    require(sha256_file(batch / "manifest.json") == inventory_anchor, "inventory_anchor")
    require(sha256_file(batch / "allocation.json") == allocation_anchor, "allocation_anchor")
    validate_inventory(value)
    rows = sorted(
        (r for r in value["records"] if r["split"] == "DEVELOPMENT"), key=lambda r: r["video_id"]
    )
    require(bool(rows), "development_source_required")
    row = rows[0]  # content-blind: no predictions, images or outcomes select this source
    intake = read_json(Path(row["intake_path"]))
    require(sha256_file(Path(row["intake_path"])) == row["intake_sha256"], "intake_integrity")
    base = Fraction(intake["native_time_base"])
    end = math.ceil(Fraction(str(intake["duration_sec"])) / base)
    step = math.ceil(Fraction(60) / base)
    plan = {
        "version": "personal-source-review-v1",
        "batch": str(batch.resolve()),
        "inventory_sha256": inventory_anchor,
        "allocation_sha256": allocation_anchor,
        "video_id": row["video_id"],
        "source_sha256": row["source_sha256"],
        "time_base": str(base),
        "planned_duration_ticks": end,
        "selection": "first_DEVELOPMENT_id_before_content",
        "coverage_policy": "consecutive_whole_timeline_60_second_windows_not_predictions",
        "planned_windows": [
            {"start_tick": t, "end_tick": min(end, t + step), "review_status": "UNREVIEWED"}
            for t in range(0, end, step)
        ],
        "protected_evaluation_ids": [
            r["video_id"] for r in value["records"] if r["split"] != "DEVELOPMENT"
        ],
        "recognizer_fingerprint": global_recognizer_fingerprint(),
        "contract_sha256": sha256_file(ROOT / "docs/temporal_gt/annotation_contract_v1.md"),
        "schema_sha256": sha256_file(SCHEMA),
        "death_schema_sha256": sha256_file(DEATH_SCHEMA),
        "recognition_executed": False,
        "labels_approved": False,
        "maximum_acquisition_seconds": 2,
        "maximum_frames": 180,
        "maximum_acquisition_png_bytes": 256 * 1024 * 1024,
        "maximum_session_png_bytes": 512 * 1024 * 1024,
        "unedited_user_attestation": value["declarations"]["unedited_full_match"],
    }
    registry_source(plan)  # gate before any source decode, including UNKNOWN_EXPOSURE
    private_directory(output)
    write_private(output / "plan.json", plan)
    contract = {
        "schema_version": 1,
        "source_video_sha256": row["source_sha256"],
        "no_user_edit": True,
        "no_intentional_frame_deletion_join_or_reorder": True,
        "no_intentional_speed_change": True,
        "scene_preserving_edit_excluded": True,
        "assurance_provenance": "Explicit user attestation: all nine are unedited full matches; "
        "not machine continuity certification",
    }
    require(plan["unedited_user_attestation"] is True, "explicit_unedited_attestation")
    write_private(output / "input_contract.json", contract)
    write_private(
        output / "plan.freeze.json",
        {"plan_sha256": sha256_file(output / "plan.json"), "recognition_executed": False},
    )


def load_plan(session: Path) -> dict[str, Any]:
    plan = read_json(session / "plan.json")
    require(
        sha256_file(session / "plan.json")
        == read_json(session / "plan.freeze.json")["plan_sha256"],
        "plan_changed",
    )
    require(
        sha256_file(ROOT / "docs/temporal_gt/annotation_contract_v1.md") == plan["contract_sha256"],
        "annotation_contract_changed",
    )
    require(sha256_file(SCHEMA) == plan["schema_sha256"], "round_contract_changed")
    require(sha256_file(DEATH_SCHEMA) == plan["death_schema_sha256"], "death_contract_changed")
    registry_source(plan)
    return plan


def append_exposure(session: Path, kind: str, evidence: Path, notes: str) -> int:
    plan = load_plan(session)
    require(kind in EXPOSURE_TYPES, "exposure_kind")
    batch = Path(plan["batch"])
    lock = batch / ".review-exposure-lock"
    lock.mkdir(mode=0o700)
    try:
        path = batch / "exposure_journal.jsonl"
        previous = (
            []
            if not path.exists()
            else [json.loads(t) for t in path.read_text(encoding="utf-8").splitlines()]
        )
        for index, item in enumerate(previous):
            require(item["event"]["order"] == index + 1, "exposure_sequence")
            require(
                item["previous_sha256"] == (canonical_hash(previous[index - 1]) if index else None),
                "exposure_chain",
            )
        order = len(previous) + 1
        event = {
            "source_id": plan["video_id"],
            "event_id": None,
            "window": None,
            "kind": kind,
            "order": order,
            "evidence_id": f"journal_{order}",
            "actor_id": "user" if kind == "gt_creation" else "source_curator",
            "recorded_at": datetime.now(UTC).isoformat(),
            "code_sha256": plan["recognizer_fingerprint"],
            "profile_sha256": None,
            "assets_sha256": None,
            "notes": notes,
        }
        schema = read_json(SCHEMA)["properties"]["exposures"]["items"]
        require(not list(Draft202012Validator(schema).iter_errors(event)), "exposure_schema")
        entry = {
            "previous_sha256": canonical_hash(previous[-1]) if previous else None,
            "evidence_path": str(evidence.resolve()),
            "evidence_sha256": sha256_file(evidence),
            "event": event,
        }
        with open(path, "a", encoding="utf-8", opener=lambda p, f: os.open(p, f, 0o600)) as out:
            out.write(json.dumps(entry, allow_nan=False) + "\n")
        return order
    finally:
        lock.rmdir()


@contextmanager
def exclusive_operation(path: Path) -> Iterator[None]:
    path.mkdir(mode=0o700)
    try:
        yield
    finally:
        path.rmdir()


def acquire(session: Path, acquisition_id: str, start: str, end: str) -> Path:
    load_plan(session)
    with exclusive_operation(session / ".acquisition-lock"):
        return _acquire(session, acquisition_id, start, end)


def _acquire(session: Path, acquisition_id: str, start: str, end: str) -> Path:
    plan = load_plan(session)
    row = registry_source(plan)
    begin, finish = Fraction(start), Fraction(end)
    require(0 <= begin < finish and finish - begin <= 2, "bounded_two_second_acquisition")
    require(finish <= plan["planned_duration_ticks"] * Fraction(plan["time_base"]), "inside_source")
    acquisition_id = valid_id(acquisition_id)
    folder = session / acquisition_id
    private_directory(folder)
    write_private(
        folder / "request.json",
        {
            "start_sec_rational": str(begin),
            "end_sec_rational": str(finish),
            "plan_sha256": sha256_file(session / "plan.json"),
        },
    )
    # Conservative whole-source development exposure, NOT a claim of full viewing.
    append_exposure(
        session,
        "source_only_view",
        folder / "request.json",
        "Bounded source-only evidence acquisition. Page references only this DEVELOPMENT "
        "source; conservative source-wide exposure, no full-interval review or predictions.",
    )
    frames_dir = folder / "frames"
    frames_dir.mkdir(mode=0o700)
    used = sum(p.stat().st_size for p in session.rglob("*.png"))
    require(used < plan["maximum_session_png_bytes"], "session_storage_budget")
    budget = min(plan["maximum_acquisition_png_bytes"], plan["maximum_session_png_bytes"] - used)
    with decode_native_window(
        Path(row["managed_path"]),
        start_sec=float(begin),
        end_sec=float(finish),
        source_video_sha256=row["source_sha256"],
        ffmpeg=shutil.which("ffmpeg") or "ffmpeg",
        ffprobe=shutil.which("ffprobe") or "ffprobe",
        timeout_sec=600,
        png_prediction="up",
        max_png_bytes=budget,
    ) as frames:
        selected = [f for f in frames if begin <= f.pts_ticks * f.time_base <= finish]
        require(2 <= len(selected) <= plan["maximum_frames"], "native_frame_budget")
        proof = summarize_pixels(selected)
        saved = []
        for index, frame in enumerate(selected):
            frame.read_image()
            target = frames_dir / f"{index:04d}.png"
            with target.open("xb") as out, frame.path.open("rb") as src:
                shutil.copyfileobj(src, out)
            os.chmod(target, 0o600)
            require(sha256_file(target) == frame.encoded_sha256, "retained_native_hash")
            saved.append(
                {
                    "tick": frame.pts_ticks,
                    "time_base": str(frame.time_base),
                    "epoch": frame.source_epoch,
                    "source_sha256": frame.source_video_sha256,
                    "encoded_sha256": frame.encoded_sha256,
                    "pixel_sha256": frame.pixel_sha256,
                    "width": frame.width,
                    "height": frame.height,
                    "path": str(target.resolve()),
                }
            )
    report = {
        "version": "native-human-review-acquisition-v1",
        "acquisition_id": acquisition_id,
        "plan_sha256": sha256_file(session / "plan.json"),
        "source_sha256": row["source_sha256"],
        "video_path": row["managed_path"],
        "frames": saved,
        "proof": proof,
        "recognition_executed": False,
        "human_reviewed": False,
    }
    write_private(folder / "acquisition.json", report)
    from scripts.temporal_gt.review_ui import write_page

    write_page(session, folder, plan, report)
    return folder


def read_acquisition(session: Path, acquisition_id: str) -> dict[str, Any]:
    plan = load_plan(session)
    folder = session / valid_id(acquisition_id)
    acq = read_json(folder / "acquisition.json")
    require(acq["plan_sha256"] == sha256_file(session / "plan.json"), "acquisition_plan")
    require(acq["source_sha256"] == plan["source_sha256"], "acquisition_source")
    for f in acq["frames"]:
        require(Path(f["path"]).resolve().is_relative_to(folder.resolve()), "evidence_path")
        NativeSourceFrame(
            Path(f["path"]),
            f["tick"],
            Fraction(f["time_base"]),
            f["epoch"],
            f["source_sha256"],
            f["encoded_sha256"],
            f["pixel_sha256"],
            f["width"],
            f["height"],
        ).read_image()
    require(
        len({(f["epoch"], f["time_base"], f["source_sha256"]) for f in acq["frames"]}) == 1,
        "one_real_acquisition_epoch",
    )
    return acq


def response_defaults(acq: dict[str, Any]) -> dict[str, Any]:
    return {
        "version": "human-source-review-response-v1",
        "acquisition_sha256": canonical_hash(acq),
        "reviewer_id": "user",
        "human_source_review_confirmed": False,
        "predictions_consulted": False,
        "round": {
            "reviewed": False,
            "verdict": "unknown",
            "physical_event_key": "",
            "physical_identity_verified": False,
            "interval_fully_reviewed": False,
            "last_old_frame_pts": None,
            "first_new_frame_pts": None,
            "last_partial_caption_pts": None,
            "first_complete_caption_pts": None,
            "active_start_pts": None,
            "next_round_pts": None,
            "score_before": None,
            "score_after": None,
            "clock_before": {"type": "unknown", "literal": None},
            "clock_after": {"type": "unknown", "literal": None},
            "caption_state": "unknown",
            "caption_type": "UNKNOWN",
            "caption_literal": None,
            "source_discontinuity": None,
            "round_context": None,
            "negative_class": None,
            "uncertainty": "",
        },
        "death": {
            "reviewed": False,
            "verdict": "unknown",
            "physical_event_key": "",
            "physical_identity_verified": False,
            "interval_fully_reviewed": False,
            "case": "unknown",
            "last_confirmed_alive_tick": None,
            "first_confirmed_dead_tick": None,
            "self_identity_confirmed": False,
            "victim_role": "unknown",
            "killer_role": "unknown",
            "view_context": "unknown",
            "combat_report": "unknown",
            "source_discontinuity": None,
            "uncertainty": "",
        },
    }


def validate_response(acq: dict[str, Any], response: dict[str, Any]) -> None:
    require(response["version"] == "human-source-review-response-v1", "response_version")
    require(response["acquisition_sha256"] == canonical_hash(acq), "response_acquisition")
    require(response["human_source_review_confirmed"] is True, "human_confirmation_required")
    require(response["predictions_consulted"] is False, "prediction_blind_source_review_required")
    require(response["reviewer_id"] == "user", "declared_user_curator")
    require(set(response) == set(response_defaults(acq)), "response_keys")
    ticks = {f["tick"] for f in acq["frames"]}
    for domain in ("round", "death"):
        label = response[domain]
        require(set(label) == set(response_defaults(acq)[domain]), "observation_keys")
        for name in ("reviewed", "physical_identity_verified", "interval_fully_reviewed"):
            require(type(label[name]) is bool, "explicit_boolean")
        require(isinstance(label["physical_event_key"], str), "physical_key_string")
        require(type(label["reviewed"]) is bool, "explicit_review_status")
        if not label["reviewed"]:
            continue
        require(label["verdict"] in {"positive", "negative", "unknown"}, "three_way_verdict")
        require(
            isinstance(label["uncertainty"], str) and bool(label["uncertainty"].strip()),
            "human_observation_and_uncertainty_required",
        )
        if label["physical_identity_verified"]:
            require(bool(label["physical_event_key"].strip()), "physical_identity_key")
        if label["verdict"] != "unknown":
            require(label["physical_identity_verified"] is True, "physical_identity_confirmation")
        if label["verdict"] == "negative":
            require(label["interval_fully_reviewed"] is True, "unreviewed_is_not_negative")
        point_names = (
            (
                "last_old_frame_pts",
                "first_new_frame_pts",
                "last_partial_caption_pts",
                "first_complete_caption_pts",
                "active_start_pts",
                "next_round_pts",
            )
            if domain == "round"
            else ("last_confirmed_alive_tick", "first_confirmed_dead_tick")
        )
        for key in point_names:
            require(
                label[key] is None or (type(label[key]) is int and label[key] in ticks),
                "actual_native_frame_witness_required",
            )
        if domain == "round":
            if label["verdict"] == "positive":
                require(
                    (
                        label["last_old_frame_pts"] is not None
                        and label["first_new_frame_pts"] is not None
                    )
                    or (
                        label["last_partial_caption_pts"] is not None
                        and label["first_complete_caption_pts"] is not None
                    ),
                    "observed_round_bracket_required",
                )
                require(
                    label["caption_state"] == "complete"
                    and label["caption_type"] in {"WON", "LOST", "CLUTCH", "TEAM ACE"}
                    and label["caption_literal"] == label["caption_type"]
                    and label["first_complete_caption_pts"] is not None,
                    "independent_visible_round_result_required",
                )
            if label["verdict"] == "negative":
                require(label["negative_class"] in NEGATIVE_CLASSES, "reviewed_natural_negative")
            for left, right in (
                ("last_old_frame_pts", "first_new_frame_pts"),
                ("last_partial_caption_pts", "first_complete_caption_pts"),
            ):
                if label[left] is not None and label[right] is not None:
                    require(label[left] < label[right], "ordered_round_bracket")
        else:
            if label["verdict"] == "positive":
                require(
                    label["case"] == "self_death"
                    and label["self_identity_confirmed"] is True
                    and label["victim_role"] == "self",
                    "self_victim_evidence",
                )
                a, b = label["last_confirmed_alive_tick"], label["first_confirmed_dead_tick"]
                require(a is not None and b is not None and a < b, "alive_dead_bracket")
            if label["verdict"] == "negative":
                require(
                    label["case"]
                    in {
                        "confirmed_alive",
                        "nonself_victim",
                        "self_killer",
                        "report_persistence",
                        "report_redisplay",
                        "spectator",
                    },
                    "death_negative_source_context",
                )
                require(label["first_confirmed_dead_tick"] is None, "negative_self_death_conflict")
    require(
        response["round"]["reviewed"] or response["death"]["reviewed"], "at_least_one_human_review"
    )
    for domain in ("round", "death"):
        label = response[domain]
        if not label["reviewed"]:
            continue
        shaped = {
            k: v
            for k, v in label.items()
            if k not in {"reviewed", "physical_event_key", "physical_identity_verified"}
        }
        shaped.update(
            id="validation",
            event_id="validation",
            source_sha256=acq["source_sha256"],
            time_base=acq["frames"][0]["time_base"],
            epoch=acq["frames"][0]["epoch"],
            status="historical_source_review",
            reviewer_id="user",
            review_order=0,
            provenance_ids=["validation"],
        )
        if domain == "round":
            shaped.update(
                annotation_target="no_end_display"
                if label["verdict"] == "negative"
                else "display_end_episode",
                event_type={"positive": "end_display", "negative": "non_end", "unknown": "unknown"}[
                    label["verdict"]
                ],
                unscorable_reason=label["uncertainty"] if label["verdict"] == "unknown" else None,
            )
            schema = read_json(SCHEMA)["properties"]["annotations"]["items"]
        else:
            schema = read_json(DEATH_SCHEMA)["properties"]["annotations"]["items"]
        require(not list(Draft202012Validator(schema).iter_errors(shaped)), "observation_schema")


def record_response(session: Path, acquisition_id: str, response_path: Path) -> Path:
    plan = load_plan(session)
    with exclusive_operation(Path(plan["batch"]) / ".human-record-lock"):
        return _record_response(session, acquisition_id, response_path)


def _record_response(session: Path, acquisition_id: str, response_path: Path) -> Path:
    acq = read_acquisition(session, acquisition_id)
    raw_bytes = response_path.read_bytes()
    response = read_json(response_path)
    require(json.loads(raw_bytes.decode("utf-8")) == response, "human_response_changed_during_read")
    if response.get("predictions_consulted") is True:
        append_exposure(
            session,
            "prediction_review",
            response_path,
            "Human reports prediction exposure; source-independent GT import rejected.",
        )
    validate_response(acq, response)
    require(
        not (session / valid_id(acquisition_id) / "human_response.json").exists(),
        "human_response_already_recorded",
    )
    plan = load_plan(session)
    journal = Path(plan["batch"]) / "exposure_journal.jsonl"
    if journal.exists():
        for text in journal.read_text(encoding="utf-8").splitlines():
            entry = json.loads(text)
            event = entry["event"]
            if event["source_id"] != plan["video_id"]:
                continue
            require(
                event["kind"] not in {"prediction", "prediction_review"},
                "prior_prediction_exposure_requires_separate_workflow",
            )
            if event["kind"] == "gt_creation":
                prior = read_json(Path(entry["evidence_path"]))
                for domain in ("round", "death"):
                    a, b = prior[domain], response[domain]
                    if a["reviewed"] and b["reviewed"]:
                        require(
                            not (
                                a["physical_event_key"]
                                and a["physical_event_key"] == b["physical_event_key"]
                            ),
                            "duplicate_physical_event_requires_amendment",
                        )
                        if domain == "death" and a["verdict"] == b["verdict"] == "positive":
                            require(
                                a["first_confirmed_dead_tick"] < b["last_confirmed_alive_tick"]
                                or b["first_confirmed_dead_tick"] < a["last_confirmed_alive_tick"],
                                "overlapping_physical_death_brackets",
                            )
    folder = session / valid_id(acquisition_id)
    target = folder / "human_response.json"
    require(not target.exists(), "human_response_already_recorded")
    raw = folder / "human_response.raw.json"
    with raw.open("xb") as out:
        out.write(raw_bytes)
    os.chmod(raw, 0o600)
    write_private(target, response)
    order = append_exposure(
        session,
        "gt_creation",
        target,
        "Human-source review for DEVELOPMENT only, not independent qualification.",
    )
    pending = folder / "human_receipt.pending.json"
    write_private(
        pending,
        {
            "response_sha256": sha256_file(target),
            "raw_response_sha256": sha256_file(raw),
            "review_order": order,
            "acquisition_sha256": canonical_hash(acq),
        },
    )
    snapshot = export_dataset(session, pending=folder)
    pending.rename(folder / "human_receipt.json")
    return snapshot


def export_dataset(session: Path, *, pending: Path | None = None) -> Path:
    plan = load_plan(session)
    source = registry_source(plan)
    contract = session / "input_contract.json"
    preflight = session / "source_preflight.json"
    exposures = []
    evidence = [
        {
            "id": "plan",
            "path": str(session / "plan.json"),
            "sha256": sha256_file(session / "plan.json"),
            "kind": "frozen_source_schedule",
            "order": 0,
        }
    ]
    journal = Path(plan["batch"]) / "exposure_journal.jsonl"
    if journal.exists():
        previous_hash = None
        for order, text in enumerate(journal.read_text(encoding="utf-8").splitlines(), 1):
            entry = json.loads(text)
            require(
                entry["previous_sha256"] == previous_hash and entry["event"]["order"] == order,
                "exposure_chain",
            )
            previous_hash = canonical_hash(entry)
            if entry["event"]["source_id"] != plan["video_id"]:
                continue
            event = entry["event"]
            require(
                sha256_file(Path(entry["evidence_path"])) == entry["evidence_sha256"],
                "exposure_evidence_changed",
            )
            evidence.append(
                {
                    "id": event["evidence_id"],
                    "path": entry["evidence_path"],
                    "sha256": entry["evidence_sha256"],
                    "kind": event["kind"],
                    "order": event["order"],
                }
            )
            exposures.append(event)
    dataset: dict[str, Any] = {
        "version": "round-end-temporal-v1",
        "adjacency_guard_sec": 1,
        "audit": {
            "history_complete": False,
            "reference_lineage_complete": False,
            "scope": "One DEVELOPMENT source; prediction-blind user review; no qualification",
            "evidence_ids": ["plan"],
        },
        "method": {
            "recognizer_sha256": plan["recognizer_fingerprint"],
            "profile_sha256": None,
            "assets_sha256": None,
            "evaluation_policy_version": "round-end-temporal-readiness-v1",
            "evaluation_policy_sha256": sha256_file(POLICY),
            "developer_id": "dataset_owner",
            "frozen_order": 0,
            "reference_parent_keys": [],
            "profile_path": None,
            "template_profile_path": None,
            "assets_manifest_path": None,
        },
        "actors": [
            {"id": k, "role": role, "independent": False}
            for k, role in [
                ("dataset_owner", "developer"),
                ("source_curator", "curator"),
                ("user", "curator"),
            ]
        ],
        "evidence": evidence,
        "sources": [
            {
                "id": plan["video_id"],
                "sha256": plan["source_sha256"],
                "path": source["managed_path"],
                "contract_path": str(contract),
                "contract_sha256": sha256_file(contract),
                "time_base": plan["time_base"],
                "sealed_reserved": False,
                "preflight_path": str(preflight) if preflight.exists() else None,
                "preflight_sha256": sha256_file(preflight) if preflight.exists() else None,
            }
        ],
        "events": [],
        "exposures": exposures,
        "allocations": [],
        "frames": [],
        "annotations": [],
    }
    deaths = []
    physical_keys: set[str] = set()
    positive_death_windows: list[tuple[int, int]] = []
    folders = sorted(p.parent for p in session.glob("*/human_receipt.json"))
    if pending is not None:
        require(pending not in folders, "duplicate_pending_receipt")
        folders.append(pending)
    for folder in folders:
        receipt = read_json(
            folder / ("human_receipt.pending.json" if folder == pending else "human_receipt.json")
        )
        require(
            sha256_file(folder / "human_response.raw.json") == receipt["raw_response_sha256"],
            "raw_human_response_hash",
        )
        require(
            sha256_file(folder / "human_response.json") == receipt["response_sha256"],
            "human_response_hash",
        )
        acq = read_acquisition(session, folder.name)
        response = read_json(folder / "human_response.json")
        validate_response(acq, response)
        require(canonical_hash(acq) == receipt["acquisition_sha256"], "human_acquisition_receipt")
        require(response["reviewer_id"] == "user", "declared_user_curator")
        for domain in ("round", "death"):
            label = response[domain]
            if not label["reviewed"]:
                continue
            eid = f"{folder.name}_{domain}"
            key = f"{plan['video_id']}:{domain}:{label['physical_event_key'] or eid}"
            require(key not in physical_keys, "duplicate_physical_event_requires_amendment")
            physical_keys.add(key)
            frames = acq["frames"]
            start, end = frames[0]["tick"], frames[-1]["tick"]
            dataset["events"].append(
                {
                    "id": eid,
                    "physical_event_key": key,
                    "source_id": plan["video_id"],
                    "source_sha256": plan["source_sha256"],
                    "physical_identity_verified": label["physical_identity_verified"],
                    "window": {
                        "start_tick": start,
                        "end_tick": end,
                        "time_base": plan["time_base"],
                    },
                    "epoch": frames[0]["epoch"],
                    "continuity_segment": None,
                    "continuity_reviewed": False,
                }
            )
            dataset["allocations"].append(
                {
                    "event_id": eid,
                    "split": "development",
                    "assigned_order": 0,
                    "independence": "not_certified",
                    "reviewer_id": None,
                    "authority_evidence_id": None,
                    "opened": False,
                    "opened_order": None,
                    "opening_authority_id": None,
                    "consumed_methods": [],
                }
            )
            dataset["frames"].extend(dict(f, event_id=eid) for f in frames)
            common = {
                "id": eid + "_label",
                "event_id": eid,
                "source_sha256": plan["source_sha256"],
                "time_base": plan["time_base"],
                "epoch": frames[0]["epoch"],
                "verdict": label["verdict"],
                "status": "historical_source_review",
                "reviewer_id": "user",
                "review_order": receipt["review_order"],
                "provenance_ids": [f"journal_{receipt['review_order']}"],
                "uncertainty": label["uncertainty"],
                "interval_fully_reviewed": label["interval_fully_reviewed"],
            }
            if domain == "round":
                observation = {
                    k: v
                    for k, v in label.items()
                    if k
                    not in {
                        "reviewed",
                        "verdict",
                        "physical_event_key",
                        "physical_identity_verified",
                        "interval_fully_reviewed",
                    }
                }
                dataset["annotations"].append(
                    {
                        **common,
                        **observation,
                        "annotation_target": "no_end_display"
                        if label["verdict"] == "negative"
                        else "display_end_episode",
                        "event_type": {
                            "positive": "end_display",
                            "negative": "non_end",
                            "unknown": "unknown",
                        }[label["verdict"]],
                        "unscorable_reason": label["uncertainty"]
                        if label["verdict"] == "unknown"
                        else None,
                    }
                )
            else:
                death = {
                    **common,
                    **{
                        k: v
                        for k, v in label.items()
                        if k
                        not in {
                            "reviewed",
                            "verdict",
                            "physical_event_key",
                            "physical_identity_verified",
                            "interval_fully_reviewed",
                        }
                    },
                }
                if death["verdict"] == "positive":
                    a, b = death["last_confirmed_alive_tick"], death["first_confirmed_dead_tick"]
                    require(
                        not any(a <= y and x <= b for x, y in positive_death_windows),
                        "overlapping_physical_death_brackets",
                    )
                    positive_death_windows.append((a, b))
                deaths.append(death)
    report = validate(dataset)
    companion = {
        "version": "self-death-source-annotations-v1",
        "temporal_dataset_sha256": canonical_hash(dataset),
        "annotations": deaths,
    }
    validate_deaths(dataset, companion)
    snapshot = session / f"snapshot_{len(list(session.glob('snapshot_*'))):03d}"
    private_directory(snapshot)
    write_private(snapshot / "round_dataset.json", dataset)
    write_private(snapshot / "round.freeze.json", freeze_record(dataset))
    write_private(snapshot / "self_death_annotations.json", companion)
    report.update(
        {
            "human_round_reviews": len(dataset["annotations"]),
            "human_round_positive_physical_events": sum(
                x["verdict"] == "positive" for x in dataset["annotations"]
            ),
            "human_self_death_reviews": len(deaths),
            "human_self_death_positive_physical_events": sum(
                x["verdict"] == "positive" for x in deaths
            ),
            "reviewed_natural_negative_physical_events": sum(
                x["verdict"] == "negative" for x in dataset["annotations"]
            ),
            "reviewed_unknown_annotations": sum(
                x["verdict"] == "unknown" for x in [*dataset["annotations"], *deaths]
            ),
            "unreviewed_schedule_windows": len(plan["planned_windows"]),
            "unreviewed_windows_are_negative": False,
            "protected_evaluation_sources": len(plan["protected_evaluation_ids"]),
        }
    )
    write_private(snapshot / "public_counts.json", report)
    return snapshot


def validate_deaths(dataset: dict[str, Any], companion: dict[str, Any]) -> None:
    require(
        not list(Draft202012Validator(read_json(DEATH_SCHEMA)).iter_errors(companion)),
        "self_death_schema",
    )
    require(
        companion["temporal_dataset_sha256"] == canonical_hash(dataset), "death_backbone_binding"
    )
    events = {e["id"]: e for e in dataset["events"]}
    seen: set[str] = set()
    positive_windows: list[tuple[int, int]] = []
    for label in companion["annotations"]:
        require(label["event_id"] not in seen, "duplicate_death_annotation")
        seen.add(label["event_id"])
        require(
            label["reviewer_id"] == "user" and label["status"] == "historical_source_review",
            "human_development_annotation_only",
        )
        evidence = {e["id"]: e for e in dataset["evidence"]}
        require(
            all(
                p in evidence and evidence[p]["order"] <= label["review_order"]
                for p in label["provenance_ids"]
            ),
            "death_review_provenance",
        )
        require(label["event_id"] in events, "death_event_reference")
        event = events[label["event_id"]]
        require(
            label["source_sha256"] == event["source_sha256"]
            and label["epoch"] == event["epoch"]
            and label["time_base"] == event["window"]["time_base"],
            "death_source_epoch",
        )
        points = {f["tick"] for f in dataset["frames"] if f["event_id"] == label["event_id"]}
        for k in ("last_confirmed_alive_tick", "first_confirmed_dead_tick"):
            require(
                label[k] is None or (type(label[k]) is int and label[k] in points),
                "death_native_witness",
            )
        if label["verdict"] != "unknown":
            require(event["physical_identity_verified"] is True, "death_physical_identity")
        if label["verdict"] == "negative":
            require(
                label["interval_fully_reviewed"] is True
                and label["first_confirmed_dead_tick"] is None
                and label["case"]
                in {
                    "confirmed_alive",
                    "nonself_victim",
                    "self_killer",
                    "report_persistence",
                    "report_redisplay",
                    "spectator",
                },
                "death_negative_source_context",
            )
        if label["verdict"] == "positive":
            require(
                label["case"] == "self_death"
                and label["self_identity_confirmed"]
                and label["victim_role"] == "self"
                and label["last_confirmed_alive_tick"] is not None
                and label["first_confirmed_dead_tick"] is not None
                and label["last_confirmed_alive_tick"] < label["first_confirmed_dead_tick"],
                "report_presence_is_not_death",
            )
            a, b = label["last_confirmed_alive_tick"], label["first_confirmed_dead_tick"]
            require(
                not any(a <= y and x <= b for x, y in positive_windows),
                "overlapping_physical_death_brackets",
            )
            positive_windows.append((a, b))


def validate_snapshot(snapshot: Path, freeze_anchor: str, death_anchor: str) -> dict[str, Any]:
    dataset = read_json(snapshot / "round_dataset.json")
    check_freeze(dataset, snapshot / "round.freeze.json", freeze_anchor)
    require(
        sha256_file(snapshot / "self_death_annotations.json") == death_anchor,
        "death_external_anchor",
    )
    report = validate(dataset)
    validate_deaths(dataset, read_json(snapshot / "self_death_annotations.json"))
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    new = sub.add_parser("create")
    new.add_argument("--batch", type=Path, required=True)
    new.add_argument("--output", type=Path, required=True)
    new.add_argument("--trusted-inventory-sha256", required=True)
    new.add_argument("--trusted-allocation-sha256", required=True)
    for command in ("acquire", "record", "export"):
        child = sub.add_parser(command)
        child.add_argument("--session", type=Path, required=True)
        if command != "export":
            child.add_argument("--acquisition-id", required=True)
        if command == "acquire":
            child.add_argument("--start", required=True)
            child.add_argument("--end", required=True)
        if command == "record":
            child.add_argument("--response", type=Path, required=True)
    check = sub.add_parser("validate")
    check.add_argument("--snapshot", type=Path, required=True)
    check.add_argument("--trusted-freeze-sha256", required=True)
    check.add_argument("--trusted-death-sha256", required=True)
    args = parser.parse_args()
    try:
        if args.command == "validate":
            validate_snapshot(args.snapshot, args.trusted_freeze_sha256, args.trusted_death_sha256)
        elif args.command == "create":
            create_session(
                args.batch,
                args.output,
                args.trusted_inventory_sha256,
                args.trusted_allocation_sha256,
            )
        elif args.command == "acquire":
            acquire(args.session, args.acquisition_id, args.start, args.end)
        elif args.command == "record":
            record_response(args.session, args.acquisition_id, args.response)
        else:
            export_dataset(args.session)
        print(
            json.dumps(
                {
                    "operation": args.command,
                    "recognition_executed": False,
                    "qualification_completed": False,
                }
            )
        )
    except (
        OSError,
        ValueError,
        KeyError,
        TypeError,
        RuntimeError,
        ZeroDivisionError,
        subprocess.SubprocessError,
    ):
        parser.exit(2, "SOURCE_REVIEW_CONTRACT_REJECTED\n")


if __name__ == "__main__":
    main()
