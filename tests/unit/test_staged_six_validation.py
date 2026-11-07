"""Synthetic metadata only; no media decoder or private match is used."""

import json
from copy import deepcopy
from pathlib import Path

import pytest

from valorant_ai_coach.temporal import staged_validation as staged
from valorant_ai_coach.temporal.replay import SourcePolicy, read_json, write_private


@pytest.fixture
def setup(tmp_path, monkeypatch):
    protocol = tmp_path / "protocol.json"
    write_private(protocol, {"synthetic": True})
    flags = {
        "coarse_seconds": "1",
        "dense_seconds": "1/5",
        "max_refinement_windows": 40,
        "refinement_selection_policy": "chronological",
        "refinement_padding_seconds": "1",
        "report_view_bridge": True,
        "buy_clock_expiry": False,
        "provisional_map_roles": False,
        "active_clock_bridge": False,
        "return_display_tail": False,
        "buy_clock_tail": False,
        "retain_frames": False,
        "audit_sample_plan": None,
    }
    plan = {
        "observer": "valorant_ai_coach.temporal.match_observer:ProfileHudObserver",
        "reader_config": str(tmp_path / "reader.json"),
        "settings": {
            key: value
            for key, value in flags.items()
            if key not in {"retain_frames", "audit_sample_plan"}
        },
    }
    monkeypatch.setattr(staged, "verify_protocol", lambda _: plan)
    monkeypatch.setattr(staged, "_verify_active_runtime", lambda _: None)
    monkeypatch.setattr(
        staged,
        "prior_catalog",
        lambda _: {
            "ids": set(),
            "matches": set(),
            "hashes": set(),
            "paths": set(),
            "anchors": {},
        },
    )
    monkeypatch.setattr(
        staged,
        "file_sha",
        lambda path: (
            pytest.fail("registration read media")
            if str(path).endswith(".mp4")
            else __import__("hashlib").sha256(Path(path).read_bytes()).hexdigest()
        ),
    )
    records = []
    for i in range(6):
        source = tmp_path / f"recording_{i}.mp4"
        source.write_bytes(b"synthetic")
        records.append(
            {
                "path": str(source),
                "filename": source.name,
                "source_id": f"personal_20261108_{i + 1:03d}",
                "size_bytes": source.stat().st_size,
                "source_sha256": f"{i + 1:064x}",
                "duration_sec": "1000",
                "width": 1920,
                "height": 1080,
                "fps": "60",
                "native_time_base": "1/15360",
                "video_codec": "h264",
                "physical_match_id": f"physical_{i}",
            }
        )
    request = {
        "version": staged.VERSION,
        "seed": staged.SEED,
        "content_kind": "VALORANT_FULL_MATCH",
        "declarations": {key: True for key in staged.DECLARATIONS},
        "records": records,
        "run_flags": flags,
    }
    declaration = tmp_path / "declaration.json"
    write_private(declaration, request)
    return tmp_path, protocol, declaration, request


def test_metadata_only_allocation_and_single_source_policy(setup):
    tmp, protocol, declaration, _ = setup
    registry = tmp / "registry"
    first = staged.register_six(
        declaration=declaration,
        protocol=protocol,
        registry=registry,
        batch_id="six",
        prior_registries=[],
    )
    batch = registry / "six"
    assert len(first["records"]) == 6
    assert {r["split"] for r in first["records"]} == {
        "DEVELOPMENT",
        "QUALIFICATION",
        "FINAL_HOLDOUT",
    }
    assert {
        split: sum(r["split"] == split for r in first["records"])
        for split in ("DEVELOPMENT", "QUALIFICATION", "FINAL_HOLDOUT")
    } == {"DEVELOPMENT": 2, "QUALIFICATION": 2, "FINAL_HOLDOUT": 2}
    assert [r["video_id"] for r in first["records"]] == [
        f"personal_20261108_{i:03d}" for i in range(1, 7)
    ]
    assert first["metadata_only"] and first["media_bytes_read_by_registration"] == 0
    assert not (batch / "first_development").exists()
    with pytest.raises(ValueError, match="already reserved"):
        staged.register_six(
            declaration=declaration,
            protocol=protocol,
            registry=registry,
            batch_id="six",
            prior_registries=[],
        )
    policy_path = staged.activate_first_development(batch)
    policy = SourcePolicy(read_json(policy_path))
    assert len(policy.allowed) == 1
    assert {r["video_id"] for r in policy.allowed.values()} == {
        first["first_development_source_id"]
    }
    assert len(read_json(policy_path)["protected_source_sha256s"]) == 5
    with pytest.raises(ValueError, match="already exists"):
        staged.activate_first_development(batch)


@pytest.mark.parametrize(
    "change",
    [
        "prior_hash",
        "duplicate_physical",
        "unknown_overlap",
        "extra_content",
        "missing_flag",
        "changed_size",
    ],
)
def test_registration_fails_closed_before_any_activation(setup, monkeypatch, change):
    tmp, protocol, _, request = setup
    request = deepcopy(request)
    if change == "prior_hash":
        monkeypatch.setattr(
            staged,
            "prior_catalog",
            lambda _: {
                "ids": set(),
                "matches": set(),
                "hashes": {request["records"][0]["source_sha256"]},
                "paths": set(),
                "anchors": {},
            },
        )
    elif change == "duplicate_physical":
        request["records"][1]["physical_match_id"] = request["records"][0]["physical_match_id"]
    elif change == "unknown_overlap":
        request["declarations"]["distinct_from_prior_physical_matches"] = False
    elif change == "extra_content":
        request["records"][0]["life_state"] = "ALIVE"
    elif change == "missing_flag":
        del request["run_flags"]["buy_clock_tail"]
    else:
        request["records"][0]["size_bytes"] += 1
    declaration = tmp / "invalid.json"
    write_private(declaration, request)
    with pytest.raises(ValueError):
        staged.register_six(
            declaration=declaration,
            protocol=protocol,
            registry=tmp / "new-registry",
            batch_id="six",
            prior_registries=[],
        )
    assert not (tmp / "new-registry/six").exists()


def test_pilot_preserves_first_prediction_and_gates_full(setup, monkeypatch):
    tmp, protocol, declaration, _ = setup
    batch = tmp / "registry/six"
    allocation = staged.register_six(
        declaration=declaration,
        protocol=protocol,
        registry=batch.parent,
        batch_id=batch.name,
        prior_registries=[],
    )
    first = allocation["first_development_source_id"]
    staged.activate_first_development(batch)
    with pytest.raises(ValueError, match="Successful pilot"):
        staged.run_first(batch=batch, source_id=first, output=tmp / "full", phase="full")
    other = next(r["video_id"] for r in allocation["records"] if r["video_id"] != first)
    with pytest.raises(ValueError, match="Only the first"):
        staged.run_first(batch=batch, source_id=other, output=tmp / "other", phase="pilot")
    called = []

    def fake_run_match(**kwargs):
        called.append(kwargs)
        output = kwargs["output"]
        write_private(output / "timeline_PRIVATE.json", {"candidate": "UNKNOWN"})
        write_private(output / "completion_PRIVATE.json", {"formal_outputs": 0})
        return {"formal_outputs": 0}

    monkeypatch.setattr("valorant_ai_coach.temporal.match.run_match", fake_run_match)
    staged.run_first(
        batch=batch, source_id=first, output=tmp / "pilot", phase="pilot", pilot_seconds=90
    )
    assert called[-1]["stop_after"] == 90
    assert read_json(batch / "first_pilot_prediction_receipt_PRIVATE.json")["accuracy"] is None
    with pytest.raises(ValueError, match="already preserved"):
        staged.run_first(batch=batch, source_id=first, output=tmp / "pilot-again", phase="pilot")
    with pytest.raises(ValueError, match="Explicit successful pilot review"):
        staged.run_first(batch=batch, source_id=first, output=tmp / "full", phase="full")
    pilot_receipt = batch / "first_pilot_prediction_receipt_PRIVATE.json"
    pilot_check = tmp / "pilot_check_PRIVATE.json"
    write_private(
        pilot_check,
        {
            "processing": "COMPLETE_WITH_INFORMATION",
            "structural_pass": True,
            "JSON_CSV_content_equal": True,
            "evaluation_handoff": True,
            "formal_outputs": 0,
        },
    )
    staged.confirm_pilot(
        batch=batch,
        pilot_receipt_sha256=staged.file_sha(pilot_receipt),
        pilot_check=pilot_check,
        review={
            "input_integrity_checked": True,
            "candidate_output_checked": True,
            "pilot_timeline_checked": True,
            "proceed_to_full": True,
        },
    )
    staged.run_first(batch=batch, source_id=first, output=tmp / "full", phase="full")
    assert called[-1]["stop_after"] is None
    assert (batch / "first_full_prediction_receipt_PRIVATE.json").exists()
    assert [
        e["phase"]
        for e in map(json.loads, (batch / "attempts_PRIVATE.jsonl").read_text().splitlines())
        if e["kind"] == "recognition_attempt_started"
    ] == ["pilot", "full"]
