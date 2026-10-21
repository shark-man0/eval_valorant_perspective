"""Coverage is human source review, not event GT. Synthetic registry only."""

from __future__ import annotations

import json

import pytest

from scripts.diagnostics import register_private_sources as inventory
from scripts.e2e.run_dataset_case import sha256_file
from scripts.temporal_gt import review_windows as windows
from scripts.temporal_gt.contract import ContractError, canonical_hash
from scripts.temporal_gt.review_session import create_session


@pytest.fixture
def session(tmp_path, monkeypatch):
    source = tmp_path / "inputs"
    source.mkdir()
    for number in range(9):
        (source / f"synthetic-{number}.mp4").write_bytes(str(number).encode("ascii"))
    monkeypatch.setattr(inventory, "decode_source", lambda *a: None)
    monkeypatch.setattr(
        inventory,
        "inspect_recording",
        lambda video, *a, **k: {
            "source_sha256": sha256_file(video),
            "native_time_base": "1/10",
            "duration_sec": 121,
        },
    )
    batch, _ = inventory.register(
        source, tmp_path / "private", "synthetic", unused_and_distinct=True, unedited=True
    )
    folder = batch / "review"
    create_session(
        batch, folder, sha256_file(batch / "manifest.json"), sha256_file(batch / "allocation.json")
    )
    return folder


def response(session, index=1, status="COMPLETE"):
    value = windows.defaults(session, index)
    value.update(
        human_source_review_confirmed=True,
        status=status,
        full_interval_reviewed=True,
        round_searched=True,
        death_searched=True,
    )
    return value


def record(session, tmp_path, value, name="first"):
    path = tmp_path / "human.json"
    path.write_text(json.dumps(value, indent=3), encoding="utf-8")
    return windows.record(session, path, name)


def test_all_windows_require_explicit_human_coverage_and_cues_never_become_gt(session, tmp_path):
    for i in range(1, 4):
        value = response(session, i)
        value["cues"] = [
            {
                "kind": "self_death",
                "approx_source_sec": str((i - 1) * 60),
                "note": "Synthetic human discovery, not verified GT",
            }
        ]
        if i == 1:
            first_raw = json.dumps(value, indent=3).encode("ascii")
        report = record(session, tmp_path, value, f"review_{i}")
        assert report["complete_windows"] == i
        assert report["full_match_review_complete"] == (i == 3)
    assert report["cues_are_gt"] is False and report["source_continuity"] == "UNVERIFIED"
    assert len(report["pending_evidence_cues"]) == 3
    assert not list(session.glob("snapshot_*"))
    assert not list(session.glob("*/human_receipt.json"))
    assert (session / "window_reviews/review_1/response.raw.json").read_bytes() == first_raw


@pytest.mark.parametrize(
    "field",
    ["full_interval_reviewed", "round_searched", "death_searched", "human_source_review_confirmed"],
)
def test_missing_human_confirmation_cannot_complete_window(session, tmp_path, field):
    value = response(session)
    value[field] = False
    with pytest.raises(ContractError):
        record(session, tmp_path, value)
    assert windows.progress(session)["complete_windows"] == 0


def test_legacy_one_second_pilot_is_partial_not_a_complete_minute(session):
    folder = session / "pilot"
    folder.mkdir()
    acq = {
        "source_sha256": windows.load_plan(session)["source_sha256"],
        "frames": [{"tick": 0}, {"tick": 10}],
    }
    (folder / "acquisition.json").write_text(json.dumps(acq), encoding="utf-8")
    value = {"round": {"reviewed": True}, "death": {"reviewed": True}}
    path = folder / "human_response.json"
    path.write_text(json.dumps(value), encoding="utf-8")
    (folder / "human_receipt.json").write_text(
        json.dumps(
            {"response_sha256": sha256_file(path), "acquisition_sha256": canonical_hash(acq)}
        ),
        encoding="utf-8",
    )
    report = windows.progress(session)
    assert report["incomplete_windows"] == 1 and report["unreviewed_windows"] == 2
    assert report["complete_windows"] == 0


def test_recheck_keeps_history_and_prevents_full_match_claim(session, tmp_path):
    record(session, tmp_path, response(session), "first")
    old = (session / "window_reviews/first/response.json").read_bytes()
    value = response(session, status="NEEDS_RECHECK")
    value["notes"] = "Need to inspect obscured source interval"
    report = record(session, tmp_path, value, "second")
    assert report["needs_recheck_windows"] == 1 and report["complete_windows"] == 0
    assert (session / "window_reviews/first/response.json").read_bytes() == old
    with pytest.raises(FileExistsError):
        record(session, tmp_path, value, "second")


def test_wrong_source_order_and_outside_cues_rejected(session, tmp_path):
    with pytest.raises(ContractError, match="timeline_order"):
        record(session, tmp_path, response(session, 2))
    value = response(session)
    value["source_sha256"] = "0" * 64
    with pytest.raises(ContractError, match="binding"):
        record(session, tmp_path, value)
    value = response(session)
    value["cues"] = [{"kind": "round_end", "approx_source_sec": "61", "note": "outside"}]
    with pytest.raises(ContractError, match="inside_planned_window"):
        record(session, tmp_path, value)


def test_corrupt_receipt_is_not_coverage(session, tmp_path):
    record(session, tmp_path, response(session))
    path = session / "window_reviews/first/response.json"
    path.write_text("{}", encoding="utf-8")
    with pytest.raises(ContractError, match="window_response_hash"):
        windows.progress(session)


def test_player_creation_is_not_coverage_and_has_no_predictions(session, tmp_path):
    output = tmp_path / "viewer"
    windows.prepare(session, output, 1)
    report = windows.progress(session)
    assert report["complete_windows"] == 0 and report["unreviewed_windows"] == 3
    page = (output / "review.html").read_text(encoding="utf-8")
    assert "__PAYLOAD__" not in page
    assert 'id="human"' in page and 'id="full"' in page
    assert '"human_source_review_confirmed": false' in page
    assert '"window_index": 1' in page
    assert '"begin": 0.0' in page and '"end": 60.0' in page
    assert "recognition_executed" not in page
    assert windows.load_plan(session)["protected_evaluation_ids"][0] not in page
    with pytest.raises(FileExistsError):
        windows.prepare(session, output, 1)


def test_prediction_exposure_preserves_private_proof_even_if_download_changes(session, tmp_path):
    value = response(session)
    value["predictions_consulted"] = True
    with pytest.raises(ContractError, match="prediction_blind"):
        record(session, tmp_path, value, "exposed")
    proof = session / "window_reviews/exposed/rejected_prediction_response.json"
    before = proof.read_bytes()
    (tmp_path / "human.json").write_text("{}", encoding="utf-8")
    assert proof.read_bytes() == before
    with pytest.raises(ContractError, match="prediction_exposure"):
        record(session, tmp_path, response(session), "retry")
    assert windows.progress(session)["complete_windows"] == 0


def test_recheck_does_not_silently_drop_earlier_discovery_notes(session, tmp_path):
    first = response(session)
    first["cues"] = [{"kind": "self_death", "approx_source_sec": "1", "note": "needs evidence"}]
    record(session, tmp_path, first, "first")
    second = response(session, status="NEEDS_RECHECK")
    second["notes"] = "Need to rewatch the interval"
    report = record(session, tmp_path, second, "second")
    assert report["needs_recheck_windows"] == 1
    assert len(report["pending_evidence_cues"]) == 1
    assert report["pending_evidence_cues"][0]["note"] == "needs evidence"
    assert report["pending_evidence_cues"][0]["cue_id"].startswith("journal_")
