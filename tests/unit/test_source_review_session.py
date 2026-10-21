"""Synthetic sources/frames, never human GT or private-video evidence."""

from __future__ import annotations

import hashlib
import json
from contextlib import contextmanager
from fractions import Fraction
from pathlib import Path

import cv2
import numpy as np
import pytest

from scripts.diagnostics import register_private_sources as inventory
from scripts.e2e.run_dataset_case import read_json, sha256_file
from scripts.temporal_gt import review_session as review
from scripts.temporal_gt.contract import ContractError, canonical_hash
from scripts.temporal_gt.packet_timing import classify_packets
from scripts.temporal_gt.validate_dataset import check_freeze
from valorant_ai_coach.video.native import NativeSourceFrame


@pytest.fixture
def session(tmp_path, monkeypatch):
    inputs = tmp_path / "inputs"
    inputs.mkdir()
    for number in range(9):
        (inputs / f"synthetic-{number}.mp4").write_bytes(str(number).encode("ascii"))
    monkeypatch.setattr(inventory, "decode_source", lambda *a: None)
    monkeypatch.setattr(
        inventory,
        "inspect_recording",
        lambda video, *a, **k: {
            "source_sha256": sha256_file(video),
            "native_time_base": "1/10",
            "duration_sec": 1,
        },
    )
    batch, _ = inventory.register(
        inputs, tmp_path / "private", "synthetic", unused_and_distinct=True, unedited=True
    )
    folder = batch / "review"
    review.create_session(
        batch, folder, sha256_file(batch / "manifest.json"), sha256_file(batch / "allocation.json")
    )

    @contextmanager
    def decode(video, **kwargs):
        frames = []
        for tick in range(3):
            image = np.full((8, 8, 3), tick * 32, dtype=np.uint8)
            path = tmp_path / f"native-{tick}.png"
            assert cv2.imwrite(str(path), image)
            frames.append(
                NativeSourceFrame(
                    path,
                    tick,
                    Fraction(1, 10),
                    "synthetic-epoch",
                    sha256_file(video),
                    sha256_file(path),
                    hashlib.sha256(image.tobytes()).hexdigest(),
                    8,
                    8,
                )
            )
        yield frames

    monkeypatch.setattr(review, "decode_native_window", decode)
    return folder


def human_response(acq, domain="round", verdict="unknown"):
    response = review.response_defaults(acq)
    response["human_source_review_confirmed"] = True
    label = response[domain]
    label.update(
        reviewed=True,
        verdict=verdict,
        uncertainty="Synthetic human-response fixture",
        physical_event_key="synthetic-event",
        physical_identity_verified=True,
    )
    if verdict == "negative":
        label.update(interval_fully_reviewed=True)
        if domain == "round":
            label["negative_class"] = "menu"
        else:
            label["case"] = "confirmed_alive"
    elif verdict == "positive":
        if domain == "round":
            label.update(
                last_old_frame_pts=0,
                first_new_frame_pts=1,
                first_complete_caption_pts=1,
                caption_state="complete",
                caption_type="WON",
                caption_literal="WON",
            )
        else:
            label.update(
                case="self_death",
                last_confirmed_alive_tick=0,
                first_confirmed_dead_tick=1,
                self_identity_confirmed=True,
                victim_role="self",
            )
    return response


def acquire(session, name="pilot"):
    review.acquire(session, name, "0", "1/5")
    return review.read_acquisition(session, name)


@pytest.mark.parametrize("domain", ["round", "death"])
@pytest.mark.parametrize("verdict", ["positive", "negative", "unknown"])
def test_existing_contract_export_and_freeze(session, tmp_path, domain, verdict):
    acq = acquire(session)
    response = human_response(acq, domain, verdict)
    raw = tmp_path / "human.json"
    raw.write_text(json.dumps(response, indent=3), encoding="utf-8")
    output = review.record_response(session, "pilot", raw)
    assert (session / "pilot/human_response.raw.json").read_bytes() == raw.read_bytes()
    counts = read_json(output / "public_counts.json")
    assert counts["readiness"] == "BLOCKED"
    assert counts["recognition_executed"] is False
    assert counts["protected_evaluation_sources"] == 4
    assert counts["unreviewed_windows_are_negative"] is False
    assert counts["human_self_death_positive_physical_events"] == (
        domain == "death" and verdict == "positive"
    )
    data = read_json(output / "round_dataset.json")
    check_freeze(data, output / "round.freeze.json", sha256_file(output / "round.freeze.json"))
    review.validate_deaths(data, read_json(output / "self_death_annotations.json"))
    public = json.dumps(counts)
    assert str(session) not in public and "Synthetic human" not in public
    assert acq["source_sha256"] not in public


@pytest.mark.parametrize(
    "mutate,rule",
    [
        (lambda r: r.update(human_source_review_confirmed=False), "human_confirmation"),
        (lambda r: r.update(predictions_consulted=True), "prediction_blind"),
        (lambda r: r["round"].update(first_new_frame_pts=0.1), "native_frame"),
        (lambda r: r["round"].update(first_new_frame_pts=True), "native_frame"),
        (lambda r: r["round"].update(first_new_frame_pts=99), "native_frame"),
        (lambda r: r["round"].update(first_new_frame_pts=0), "ordered_round"),
        (lambda r: r["round"].update(last_old_frame_pts=None), "observed_round"),
        (lambda r: r["round"].update(physical_identity_verified=False), "physical_identity"),
        (lambda r: r["round"].update(uncertainty=""), "human_observation"),
    ],
)
def test_human_and_real_frame_requirements(session, mutate, rule):
    acq = acquire(session)
    response = human_response(acq, verdict="positive")
    mutate(response)
    with pytest.raises(ContractError, match=rule):
        review.validate_response(acq, response)


def test_report_or_other_victim_cannot_be_self_death(session):
    acq = acquire(session)
    response = human_response(acq, "death", "positive")
    response["death"].update(self_identity_confirmed=False, combat_report="first")
    with pytest.raises(ContractError, match="self_victim"):
        review.validate_response(acq, response)
    response["death"].update(self_identity_confirmed=True, victim_role="nonself")
    with pytest.raises(ContractError, match="self_victim"):
        review.validate_response(acq, response)


def test_unreviewed_interval_is_not_negative(session):
    acq = acquire(session)
    response = human_response(acq, verdict="negative")
    response["round"]["interval_fully_reviewed"] = False
    with pytest.raises(ContractError, match="unreviewed_is_not_negative"):
        review.validate_response(acq, response)


def test_duplicate_physical_event_and_overwrite_rejected_before_receipt(session, tmp_path):
    acq = acquire(session)
    raw = tmp_path / "human.json"
    raw.write_text(json.dumps(human_response(acq, "death", "positive")), encoding="utf-8")
    review.record_response(session, "pilot", raw)
    with pytest.raises(ContractError, match="already_recorded"):
        review.record_response(session, "pilot", raw)
    acq2 = acquire(session, "second")
    response = human_response(acq2, "death", "positive")
    raw.write_text(json.dumps(response), encoding="utf-8")
    with pytest.raises(ContractError, match="duplicate_physical"):
        review.record_response(session, "second", raw)
    assert not (session / "second/human_receipt.json").exists()
    response["death"]["physical_event_key"] = "different-alias"
    raw.write_text(json.dumps(response), encoding="utf-8")
    with pytest.raises(ContractError, match="overlapping_physical"):
        review.record_response(session, "second", raw)
    assert not (session / "second/human_response.json").exists()


def test_protected_source_and_tampered_anchor_rejected(session):
    plan = review.load_plan(session)
    data = read_json(Path(plan["batch"]) / "manifest.json")
    protected = next(r for r in data["records"] if r["split"] != "DEVELOPMENT")
    other = dict(plan, video_id=protected["video_id"])
    with pytest.raises(ContractError, match="development_only"):
        review.registry_source(other)
    with pytest.raises(ContractError, match="inventory_anchor"):
        review.registry_source(dict(plan, inventory_sha256="0" * 64))
    with pytest.raises(ContractError, match="bounded_two_second"):
        review.acquire(session, "oversize", "0", "3")
    assert not (session / "oversize").exists()


def test_frame_and_journal_tampering_rejected(session):
    acq = acquire(session)
    frame = Path(acq["frames"][0]["path"])
    original = frame.read_bytes()
    frame.write_bytes(b"changed")
    with pytest.raises((RuntimeError, ValueError)):
        review.read_acquisition(session, "pilot")
    frame.write_bytes(original)
    journal = session.parent / "exposure_journal.jsonl"
    entry = json.loads(journal.read_text(encoding="utf-8"))
    entry["previous_sha256"] = "f" * 64
    journal.write_text(json.dumps(entry) + "\n", encoding="utf-8")
    with pytest.raises(ContractError, match="exposure_chain"):
        review.export_dataset(session)


def test_page_starts_unconfirmed_and_escapes_script_payload(session):
    acq = acquire(session)
    page = (session / "pilot/review.html").read_text(encoding="utf-8")
    assert 'id="human" type="checkbox"' in page
    assert '"human_source_review_confirmed": false' in page
    assert "__PAYLOAD__" not in page
    assert 'controls preload="none"' in page
    assert canonical_hash(acq) in page


@pytest.mark.parametrize(
    "packets,category",
    [
        (
            [{"pts": 0, "dts": 0}, {"pts": 256, "dts": 256}, {"pts": 513, "dts": 512}],
            "NORMAL_CADENCE",
        ),
        ([{"pts": 0, "dts": 0}, {"pts": 512, "dts": 256}], "POSSIBLE_FRAME_LOSS"),
        ([{"pts": 0, "dts": 0}, {"pts": 0, "dts": 256}], "POSSIBLE_PTS_INCONSISTENCY"),
        ([{"pts": 0, "dts": 0}, {"pts": 256, "dts": 0}], "POSSIBLE_PTS_INCONSISTENCY"),
        ([{"dts": 0}], "POSSIBLE_PTS_INCONSISTENCY"),
        ([], "INDETERMINATE"),
    ],
)
def test_packet_only_diagnostics_never_certify_content(packets, category):
    result = classify_packets(packets, "1/15360", "60")
    assert result["category"].startswith(category)
    assert result["visual_continuity"] == "UNVERIFIED"
    assert result["unedited_or_corrupted_verdict"] == "NOT_ESTABLISHED"


def test_decode_order_pts_reordering_is_not_presentation_discontinuity():
    packets = [{"pts": p, "dts": d * 256} for d, p in enumerate([0, 512, 256])]
    assert classify_packets(packets, "1/15360", "60")["category"].startswith("NORMAL")


def test_insufficient_or_short_cadence_is_indeterminate():
    for packets in ([{"pts": 0}], [{"pts": 0}, {"pts": 1}]):
        assert classify_packets(packets, "1/15360", "60")["category"] == "INDETERMINATE"


def test_prediction_exposure_is_recorded_and_blocks_later_blind_import(session, tmp_path):
    acq = acquire(session)
    response = human_response(acq)
    response["predictions_consulted"] = True
    raw = tmp_path / "human.json"
    raw.write_text(json.dumps(response), encoding="utf-8")
    with pytest.raises(ContractError, match="prediction_blind"):
        review.record_response(session, "pilot", raw)
    response["predictions_consulted"] = False
    raw.write_text(json.dumps(response), encoding="utf-8")
    with pytest.raises(ContractError, match="prior_prediction_exposure"):
        review.record_response(session, "pilot", raw)
    assert not (session / "pilot/human_receipt.json").exists()


def test_contract_rejection_does_not_publish_an_accepted_receipt(session, tmp_path):
    acq = acquire(session)
    response = human_response(acq, verdict="positive")
    response["round"].update(
        first_complete_caption_pts=1,
        caption_state="complete",
        caption_type="WON",
        caption_literal="wrong literal",
    )
    raw = tmp_path / "human.json"
    raw.write_text(json.dumps(response), encoding="utf-8")
    with pytest.raises(ContractError, match="independent_visible_round_result"):
        review.record_response(session, "pilot", raw)
    assert not (session / "pilot/human_receipt.json").exists()
    assert not (session / "pilot/human_receipt.pending.json").exists()
    assert (
        read_json(review.export_dataset(session) / "public_counts.json")["human_round_reviews"] == 0
    )


def test_hard_storage_limit_fails_before_decode(session, monkeypatch):
    plan = review.load_plan(session)
    original = review.load_plan
    monkeypatch.setattr(
        review, "load_plan", lambda p: dict(original(p), maximum_session_png_bytes=0)
    )
    monkeypatch.setattr(review, "decode_native_window", lambda *a, **k: pytest.fail("decode"))
    with pytest.raises(ContractError, match="session_storage_budget"):
        review.acquire(session, "over_budget", "0", "0.2")
    assert plan["maximum_session_png_bytes"] > 0


def test_concurrent_acquisition_cannot_race_session_budget(session, monkeypatch):
    (session / ".acquisition-lock").mkdir()
    monkeypatch.setattr(review, "decode_native_window", lambda *a, **k: pytest.fail("decode"))
    with pytest.raises(FileExistsError):
        review.acquire(session, "concurrent", "0", "0.2")
    assert not (session / "concurrent").exists()


def test_alias_cannot_recount_a_death_in_another_session(session, tmp_path):
    first = acquire(session)
    raw = tmp_path / "human.json"
    raw.write_text(json.dumps(human_response(first, "death", "positive")), encoding="utf-8")
    review.record_response(session, "pilot", raw)
    plan = review.load_plan(session)
    second = session.parent / "second_session"
    review.create_session(
        session.parent, second, plan["inventory_sha256"], plan["allocation_sha256"]
    )
    acq = acquire(second)
    response = human_response(acq, "death", "positive")
    response["death"]["physical_event_key"] = "different-alias"
    raw.write_text(json.dumps(response), encoding="utf-8")
    with pytest.raises(ContractError, match="overlapping_physical"):
        review.record_response(second, "pilot", raw)
    assert not (second / "pilot/human_response.json").exists()


@pytest.mark.parametrize(
    "caption_field,value",
    [
        ("caption_state", "unknown"),
        ("caption_type", "UNKNOWN"),
        ("first_complete_caption_pts", None),
    ],
)
def test_score_change_eof_or_report_without_result_cannot_be_positive(
    session, caption_field, value
):
    acq = acquire(session)
    response = human_response(acq, verdict="positive")
    response["round"].update(
        score_before=[1, 0],
        score_after=[2, 0],
        uncertainty="Score changed; no independent result evidence",
    )
    response["round"][caption_field] = value
    with pytest.raises(ContractError, match="independent_visible_round_result"):
        review.validate_response(acq, response)


def test_round_start_witness_does_not_imply_positive_round_end(session, tmp_path):
    acq = acquire(session)
    response = human_response(acq)
    response["round"].update(
        last_old_frame_pts=0,
        first_new_frame_pts=1,
        active_start_pts=1,
        uncertainty="Human selected buy-to-active witnesses; End unknown",
    )
    raw = tmp_path / "human.json"
    raw.write_text(json.dumps(response), encoding="utf-8")
    snapshot = review.record_response(session, "pilot", raw)
    data = read_json(snapshot / "round_dataset.json")
    assert data["annotations"][0]["active_start_pts"] == 1
    assert data["annotations"][0]["verdict"] == "unknown"
    assert read_json(snapshot / "public_counts.json")["human_round_positive_physical_events"] == 0


def test_report_first_context_does_not_imply_positive_self_death(session, tmp_path):
    acq = acquire(session)
    response = human_response(acq, "death")
    response["death"].update(case="combat_report_first", combat_report="first")
    raw = tmp_path / "human.json"
    raw.write_text(json.dumps(response), encoding="utf-8")
    snapshot = review.record_response(session, "pilot", raw)
    label = read_json(snapshot / "self_death_annotations.json")["annotations"][0]
    assert label["combat_report"] == "first" and label["verdict"] == "unknown"
    assert (
        read_json(snapshot / "public_counts.json")["human_self_death_positive_physical_events"] == 0
    )
