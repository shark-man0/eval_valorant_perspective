"""Synthetic contract checks only; no real GT, game images or sealed Pack."""

from __future__ import annotations

import copy
import json
import subprocess
import sys
from pathlib import Path

import pytest

from scripts.temporal_gt.contract import ContractError, canonical_hash, validate
from scripts.temporal_gt.validate_dataset import POLICY, check_freeze, freeze_record
from valorant_ai_coach.hud.global_lifecycle import global_recognizer_fingerprint
from valorant_ai_coach.video.native import _sha256


@pytest.fixture
def dataset(tmp_path):
    evidence = tmp_path / "synthetic-review.json"
    evidence.write_text('{"origin":"synthetic"}', encoding="utf-8")
    return {
        "version": "round-end-temporal-v1",
        "adjacency_guard_sec": 1,
        "audit": {
            "history_complete": True,
            "reference_lineage_complete": True,
            "scope": "synthetic fixture, never real-video proof",
            "evidence_ids": ["proof"],
        },
        "method": {
            "recognizer_sha256": global_recognizer_fingerprint(),
            "profile_sha256": None,
            "assets_sha256": None,
            "evaluation_policy_version": "round-end-temporal-readiness-v1",
            "evaluation_policy_sha256": _sha256(POLICY),
            "developer_id": "dev",
            "frozen_order": 0,
            "reference_parent_keys": [],
            "profile_path": None,
            "template_profile_path": None,
            "assets_manifest_path": None,
        },
        "actors": [
            {"id": "dev", "role": "developer", "independent": False},
            {"id": "human", "role": "curator", "independent": True},
        ],
        "evidence": [
            {
                "id": "proof",
                "path": str(evidence),
                "sha256": _sha256(evidence),
                "kind": "synthetic_source_review",
                "order": 0,
            }
        ],
        "sources": [
            {
                "id": "recording",
                "sha256": "a" * 64,
                "path": None,
                "contract_path": None,
                "contract_sha256": None,
                "time_base": "1/1000",
                "sealed_reserved": False,
                "preflight_path": None,
                "preflight_sha256": None,
            }
        ],
        "events": [
            {
                "id": "event",
                "physical_event_key": "physical-1",
                "source_id": "recording",
                "source_sha256": "a" * 64,
                "physical_identity_verified": True,
                "window": {"start_tick": 100, "end_tick": 1000, "time_base": "1/1000"},
                "epoch": "epoch-1",
                "continuity_segment": None,
                "continuity_reviewed": False,
            }
        ],
        "exposures": [
            {
                "source_id": "recording",
                "event_id": "event",
                "window": None,
                "kind": "verified_unused",
                "order": 0,
                "evidence_id": "proof",
                "actor_id": "human",
                "recorded_at": None,
                "code_sha256": None,
                "profile_sha256": None,
                "assets_sha256": None,
                "notes": "synthetic",
            }
        ],
        "allocations": [
            {
                "event_id": "event",
                "split": "holdout_positive",
                "assigned_order": 10,
                "independence": "verified",
                "reviewer_id": "human",
                "authority_evidence_id": "proof",
                "opened": False,
                "opened_order": None,
                "opening_authority_id": None,
                "consumed_methods": [],
            }
        ],
        "frames": [],
        "annotations": [
            {
                "id": "label",
                "event_id": "event",
                "source_sha256": "a" * 64,
                "time_base": "1/1000",
                "epoch": "epoch-1",
                "annotation_target": "display_end_episode",
                "event_type": "end_display",
                "verdict": "positive",
                "status": "independently_reviewed",
                "round_context": None,
                "last_old_frame_pts": 140,
                "first_new_frame_pts": 150,
                "last_partial_caption_pts": 155,
                "first_complete_caption_pts": 160,
                "active_start_pts": 110,
                "next_round_pts": 170,
                "score_before": [1, 1],
                "score_after": [1, 2],
                "clock_before": {"type": "spike", "literal": None},
                "clock_after": {"type": "decimal", "literal": "10.52"},
                "caption_state": "complete",
                "caption_type": "LOST",
                "caption_literal": "LOST",
                "source_discontinuity": None,
                "reviewer_id": "human",
                "provenance_ids": ["proof"],
                "uncertainty": "synthetic assumed point labels, incomplete context",
                "unscorable_reason": None,
                "negative_class": None,
                "review_order": 20,
                "interval_fully_reviewed": False,
            }
        ],
    }


def test_consistent_partial_contract_stays_blocked_and_does_not_mutate(dataset):
    original = copy.deepcopy(dataset)
    report = validate(dataset)
    assert report["readiness"] == "BLOCKED"
    assert report["negative_physical_event_counts"] == dict.fromkeys(
        report["missing_negative_classes"], 0
    )
    assert "full_temporal_brackets_incomplete" not in report["blockers"]  # Supplied, not proven.
    assert "source_witness_frames_incomplete" in report["blockers"]
    assert "source_continuity_unproven" in report["blockers"]
    assert report["formal_End_qualified"] is report["recognition_executed"] is False
    assert dataset == original
    assert canonical_hash(dataset) == report["dataset_sha256"]


@pytest.mark.parametrize(
    "fault",
    [
        "source_sha",
        "missing_event",
        "duplicate_split",
        "exposed_training",
        "old_source_review",
        "unknown_exposure",
        "prediction_before_open",
        "reference_parent",
        "source_alias",
        "event_alias",
        "bool_pts",
        "float_pts",
        "zero_timebase",
        "noncanonical_timebase",
        "reversed_bracket",
        "mixed_epoch",
        "unknown_negative",
        "partial_complete",
        "bad_caption_literal",
        "missing_provenance",
        "developer_reviewer",
        "policy_hash",
        "version",
        "sealed_match002",
        "consumed_holdout",
        "unauthorized_open",
        "early_open",
        "internal_game_GT",
        "late_authority",
        "reversed_trajectory",
    ],
)
def test_invalid_contracts_fail_closed(dataset, fault):
    event, alloc, label = dataset["events"][0], dataset["allocations"][0], dataset["annotations"][0]
    if fault == "late_authority":
        dataset["evidence"][0]["order"] = 11
    elif fault == "reversed_trajectory":
        label["next_round_pts"] = 100
    elif fault == "source_sha":
        event["source_sha256"] = "b" * 64
    elif fault == "missing_event":
        alloc["event_id"] = "missing"
    elif fault == "duplicate_split":
        dataset["allocations"].append(alloc | {"split": "development"})
    elif fault == "exposed_training":
        dataset["exposures"][0]["kind"] = "training"
    elif fault == "old_source_review":
        dataset["exposures"][0]["kind"] = "source_only_view"
    elif fault == "unknown_exposure":
        dataset["exposures"][0]["kind"] = "unknown"
    elif fault == "prediction_before_open":
        dataset["exposures"][0].update(kind="prediction", order=15)
    elif fault == "reference_parent":
        dataset["method"]["reference_parent_keys"] = ["physical-1"]
    elif fault == "source_alias":
        dataset["sources"].append(dataset["sources"][0] | {"id": "alias"})
    elif fault == "event_alias":
        dataset["events"].append(event | {"id": "alias"})
    elif fault == "bool_pts":
        event["window"]["start_tick"] = True
    elif fault == "float_pts":
        event["window"]["start_tick"] = 100.0
    elif fault == "zero_timebase":
        event["window"]["time_base"] = "0/1000"
    elif fault == "noncanonical_timebase":
        event["window"]["time_base"] = "2/2000"
    elif fault == "reversed_bracket":
        label["last_old_frame_pts"] = 151
    elif fault == "mixed_epoch":
        label["epoch"] = "other"
    elif fault == "unknown_negative":
        alloc["split"] = "holdout_negative"
        label.update(verdict="unknown", unscorable_reason="unreadable", negative_class="countdown")
    elif fault == "partial_complete":
        label["caption_state"] = "partial"
    elif fault == "bad_caption_literal":
        label["caption_literal"] = "LO"
    elif fault == "missing_provenance":
        label["provenance_ids"] = []
    elif fault == "developer_reviewer":
        label["reviewer_id"] = "dev"
    elif fault == "policy_hash":
        dataset["method"]["evaluation_policy_sha256"] = "0" * 64
    elif fault == "version":
        dataset["version"] = "invented"
    elif fault == "sealed_match002":
        dataset["sources"][0]["sealed_reserved"] = True
    elif fault == "consumed_holdout":
        alloc["consumed_methods"] = ["b" * 64]
    elif fault == "unauthorized_open":
        alloc.update(opened=True, opened_order=15)
    elif fault == "early_open":
        alloc.update(opened=True, opened_order=9, opening_authority_id="proof")
    elif fault == "internal_game_GT":
        label["annotation_target"] = "internal_game_end"
    with pytest.raises(ContractError):
        validate(dataset, verify_files=False)


def test_adjacent_regions_cannot_hide_a_cross_split_event(dataset):
    event = dataset["events"][0]
    dataset["events"].append(event | {"id": "second", "physical_event_key": "physical-2"})
    dataset["allocations"].append(
        dataset["allocations"][0] | {"event_id": "second", "split": "development"}
    )
    with pytest.raises(ContractError, match="cross_split"):
        validate(dataset, verify_files=False)


def test_tampered_evidence_is_not_accepted(dataset):
    Path(dataset["evidence"][0]["path"]).write_text("modified", encoding="utf-8")
    with pytest.raises(ContractError, match="evidence_hash"):
        validate(dataset)


def test_source_byte_mismatch_rejected(dataset, tmp_path):
    path = tmp_path / "source.bin"
    path.write_bytes(b"not declared source")
    dataset["sources"][0]["path"] = str(path)
    with pytest.raises(ContractError, match="source_integrity"):
        validate(dataset)


def test_freeze_requires_external_anchor_and_preserves_gt(dataset, tmp_path):
    frozen = tmp_path / "FREEZE.json"
    frozen.write_text(json.dumps(freeze_record(dataset)), encoding="utf-8")
    trusted = _sha256(frozen)
    check_freeze(dataset, frozen, trusted)
    dataset["annotations"][0]["first_new_frame_pts"] += 1
    with pytest.raises(ContractError, match="frozen_version_or_hash"):
        check_freeze(dataset, frozen, trusted)
    frozen.write_text(json.dumps(freeze_record(dataset)), encoding="utf-8")
    with pytest.raises(ContractError, match="external_freeze_anchor"):
        check_freeze(dataset, frozen, trusted)


def test_cli_public_report_contains_no_private_labels_or_paths(dataset, tmp_path):
    source, frozen, public = (tmp_path / n for n in ["private.json", "FREEZE.json", "public.json"])
    source.write_text(json.dumps(dataset), encoding="utf-8")
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "scripts.temporal_gt.validate_dataset",
            "freeze",
            "--dataset",
            str(source),
            "--freeze",
            str(frozen),
            "--public-report",
            str(public),
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=False,
    )
    assert result.returncode == 0, result.stdout
    text = public.read_text(encoding="utf-8")
    assert str(tmp_path) not in text and '"LOST"' not in text
    assert '"first_new_frame_pts"' not in text and '"epoch-1"' not in text
    report = json.loads(text)
    assert report["readiness"] == "BLOCKED" and report["formal_End_qualified"] is False
    again = subprocess.run(
        [
            sys.executable,
            "-m",
            "scripts.temporal_gt.validate_dataset",
            "freeze",
            "--dataset",
            str(source),
            "--freeze",
            str(frozen),
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=False,
    )
    assert again.returncode == 2  # Existing sealed artifact is never silently replaced.


def test_source_frame_integrity_uses_shared_native_contract(dataset, tmp_path):
    import hashlib

    import cv2
    import numpy as np

    path = tmp_path / "synthetic.png"
    image = np.zeros((8, 12, 3), dtype=np.uint8)
    assert cv2.imwrite(str(path), image)
    frame = {
        "event_id": "event",
        "source_sha256": "a" * 64,
        "tick": 150,
        "time_base": "1/1000",
        "epoch": "epoch-1",
        "pixel_sha256": hashlib.sha256(image.tobytes()).hexdigest(),
        "encoded_sha256": _sha256(path),
        "path": str(path),
        "width": 12,
        "height": 8,
    }
    dataset["frames"] = [frame]
    assert validate(dataset)["readiness"] == "BLOCKED"
    # Preserve PNG validity while replacing the actual original pixels.
    assert cv2.imwrite(str(path), np.ones_like(image))
    frame["encoded_sha256"] = _sha256(path)
    with pytest.raises(ContractError, match="native_frame_integrity"):
        validate(dataset)


def test_identical_pixels_cannot_cross_split_even_at_distant_pts(dataset):
    other = copy.deepcopy(dataset["events"][0])
    other.update(id="other", physical_event_key="physical-2")
    other["window"].update(start_tick=3000, end_tick=4000)
    dataset["events"].append(other)
    dataset["allocations"].append(
        dataset["allocations"][0] | {"event_id": "other", "split": "development"}
    )
    frame = {
        "event_id": "event",
        "source_sha256": "a" * 64,
        "tick": 150,
        "time_base": "1/1000",
        "epoch": "epoch-1",
        "pixel_sha256": "b" * 64,
        "encoded_sha256": "c" * 64,
        "path": "synthetic.png",
        "width": 12,
        "height": 8,
    }
    dataset["frames"] = [frame, frame | {"event_id": "other", "tick": 3100}]
    with pytest.raises(ContractError, match="cross_split_duplicate_raster"):
        validate(dataset, verify_files=False)
