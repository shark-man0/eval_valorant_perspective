from copy import deepcopy
from dataclasses import asdict

import pytest

from tests.unit.test_development_marker_temporal import observation
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
from valorant_ai_coach.visual.development_marker_features import _digest


def case(tick=0, **overrides):
    sample, _ = observation(tick, **overrides)
    frame = FrameRecord(
        source_sha256=sample["source_sha256"], acquisition_id=sample["native_epoch"],
        native_epoch=sample["native_epoch"], native_pts_tick=sample["native_pts_tick"],
        native_time_base=sample["native_time_base"],
        frame_sha256=sample["acquired_frame_sha256"], pixel_sha256=sample["native_pixel_sha256"],
        frame_size_px=tuple(sample["frame_size_px"]), roi_xywh=(0, 0, *sample["frame_size_px"]),
        extraction_fingerprint="1" * 64, exposure_fingerprint="2" * 64,
        leakage_group_id="synthetic_match", split=Split.DEVELOPMENT_TRAIN,
        source_acceptance=SourceAcceptance(True, *["3" * 64] * 4),
    )
    profile = {"development_ownership_evidence": {"probes": [{
        "claim": "death_report", "roi": [0, 0, .5, .5],
    }]}}
    ui = {"sample_sha256": sample["sample_sha256"], "qualified": False, "formal_outputs": 0,
          "source_profile_fingerprint": _digest(profile), "fingerprint": "4" * 64,
          "own_hud_support": False, "remote_ui": False,
          "screen_measurements": {"observed_cues": [{
              "claim": "death_report", "status": "not_detected", "similarity": .2,
          }]}}
    packet = export_owner_ui(frame, sample["source_id"], ui, profile)
    witness = {k: sample[v] for k, v in (
        ("source_id", "source_id"), ("source_sha256", "source_sha256"),
        ("epoch", "native_epoch"), ("tick", "native_pts_tick"),
        ("time_base", "native_time_base"), ("encoded_sha256", "acquired_frame_sha256"),
        ("pixel_sha256", "native_pixel_sha256"),
    )}
    return packet, witness, frame, ui, profile


def test_owner_export_is_observations_not_a_new_life_state_machine():
    packet, _, _, _, _ = case()
    validate_packet(packet)
    fields = {f["name"]: f for f in packet["measurements"]}
    assert fields["death_report"]["status"] == "not_detected"
    assert fields["death_report"]["value"] is None
    assert fields["death_report"]["uncalibrated_score"] == .2
    assert fields["current_owner_hud_support"]["status"] == "UNKNOWN"
    assert fields["current_remote_support"]["status"] == "UNKNOWN"
    assert packet["formal_events"] == []
    assert "life" not in packet and "round_state" not in packet


def test_exact_native_clock_survives_the_one_second_address():
    packet, _, _, _, _ = case(61)
    assert packet["native_second_index"] == 1
    assert packet["sample"]["native_pts_tick"] == 61
    assert packet["sample"]["native_time_base"] == "1/60"
    assert packet["frame_contract"]["native_pts_tick"] == 61


@pytest.mark.parametrize("bad", ["sample", "profile", "qualified"])
def test_foreign_or_promoted_ui_is_rejected(bad):
    _, _, frame, ui, profile = case()
    if bad == "sample":
        ui["sample_sha256"] = "f" * 64
    elif bad == "profile":
        profile["changed"] = True
    else:
        ui["qualified"] = True
    with pytest.raises(ValueError):
        export_owner_ui(frame, "synthetic", ui, profile)


def test_round_reader_exports_literal_unknown_geometry_without_accepting_value():
    _, witness, frame, _, _ = case()
    row = {**witness, "geometry_consistent": False}
    for name in ("ally_score", "enemy_score", "timer", "result"):
        row[name] = {"value": "00.71" if name == "timer" else None,
                     "confidence": .61, "sources": ["synthetic_reader"]}
    packet = export_round_readers(frame, row, reader_fingerprint="a" * 64,
                                 profile_fingerprint="b" * 64, rois={})
    validate_packet(packet)
    timer = next(f for f in packet["measurements"] if f["name"] == "timer")
    assert timer["value"] == "00.71" and timer["uncalibrated_score"] == .61
    assert timer["roi_xywh_px"] is None
    assert packet["formal_outputs"] == 0


def boundary_inputs():
    cases = [case(tick) for tick in (59, 60, 75)]
    packets = [c[0] for c in cases]
    bracket = {"before": cases[0][1], "after": cases[1][1],
               "lower_tick": 59, "upper_tick": 60,
               "time_base": "1/60", "epoch": cases[0][1]["epoch"]}
    return packets, bracket, cases[2][1]


@pytest.mark.parametrize("kind", ["round_start", "round_end"])
def test_boundary_confirmation_and_uncertainty_remain_separate(kind):
    packets, bracket, confirm = boundary_inputs()
    result = export_boundary_hint(
        kind, bracket, packets=packets, producer_fingerprint="a" * 64,
        confirmation_witness=confirm, producer_evidence={"status": "DEVELOPMENT_CANDIDATE"},
    )
    assert result["uncertainty_interval_ticks"] == [59, 60]
    assert result["boundary_candidate_tick"] == 60
    assert result["confirmation_observation_tick"] == 75
    assert result["internal_game_event_tick"] is None
    assert result["source_continuity"] == "UNVERIFIED"


def test_unknown_hint_and_missing_confirmation_are_not_promoted():
    packets, bracket, _ = boundary_inputs()
    result = export_boundary_hint("round_end", bracket, packets=packets,
                                  producer_fingerprint="a" * 64,
                                  producer_evidence={"status": "UNKNOWN", "reasons": ["timer"]})
    assert result["status"] == "UNKNOWN"
    assert result["confirmation_observation_tick"] is None
    assert result["producer_evidence"]["reasons"] == ["timer"]


@pytest.mark.parametrize("bad", ["epoch", "hash", "order", "formal", "nested_foreign"])
def test_unsafe_boundary_join_is_rejected(bad):
    packets, bracket, confirm = boundary_inputs()
    evidence = {"status": "DEVELOPMENT_CANDIDATE"}
    if bad == "epoch":
        bracket["after"]["epoch"] = "other"
    elif bad == "hash":
        confirm["encoded_sha256"] = "f" * 64
    elif bad == "order":
        bracket["lower_tick"] = 80
    elif bad == "formal":
        evidence["formal_events"] = [{"type": "round_end"}]
    else:
        evidence["witnesses"] = [{**confirm, "source_sha256": "e" * 64}]
    with pytest.raises(ValueError):
        export_boundary_hint("round_end", bracket, packets=packets,
                             producer_fingerprint="a" * 64,
                             confirmation_witness=confirm, producer_evidence=evidence)


@pytest.mark.parametrize("bad", ["life", "second", "ROI", "source", "nan"])
def test_serialized_transport_mutations_reject(bad):
    packet = deepcopy(case()[0])
    if bad == "life":
        packet["life"] = "ALIVE"
    elif bad == "second":
        packet["native_second_index"] = 9
    elif bad == "ROI":
        packet["measurements"][0]["roi_xywh_px"] = [-1, 0, 20, 20]
    elif bad == "source":
        packet["frame_contract"]["source_acceptance"]["accepted"] = False
    else:
        packet["measurements"][0]["uncalibrated_score"] = float("nan")
    with pytest.raises(ValueError):
        validate_packet(packet)


@pytest.mark.parametrize("bad", [None, "protected", "manifest", "physical_match"])
def test_cli_conversion_rechecks_registry_split_exposure_and_anchors(bad):
    from scripts.diagnostics.export_hud_observations import convert
    packet, _, frame, ui, profile = case()
    source_id = packet["sample"]["source_id"]
    source = {"video_id": source_id, "source_sha256": frame.source_sha256,
              "physical_match_id": frame.leakage_group_id, "status": "accepted",
              "split": "DEVELOPMENT", "exposure": "DEVELOPMENT"}
    item = {"frame_contract": asdict(frame), "source_id": source_id,
            "ui": ui, "profile": profile}
    if bad == "protected":
        source["split"] = "FINAL_HOLDOUT_CANDIDATE"
    elif bad == "manifest":
        item["frame_contract"]["source_acceptance"]["manifest_sha256"] = "f" * 64
    elif bad == "physical_match":
        item["frame_contract"]["leakage_group_id"] = "other"
    bundle = {"version": "hud_supplier_replay_input_v1", "owner_frames": [item]}
    if bad:
        with pytest.raises(ValueError):
            convert(bundle, [source], manifest_sha256="3" * 64, allocation_sha256="3" * 64)
    else:
        result = convert(bundle, [source], manifest_sha256="3" * 64,
                         allocation_sha256="3" * 64)
        assert len(result["packets"]) == 1 and result["formal_outputs"] == 0
        assert result["common_game_state_computed"] is False


def test_cli_writes_private_run_once_and_preserves_input(tmp_path, monkeypatch, capsys):
    import json
    import os
    import sys

    from scripts.diagnostics import export_hud_observations as cli
    packet, _, frame, ui, profile = case()
    source_id = packet["sample"]["source_id"]
    source = {"video_id": source_id, "source_sha256": frame.source_sha256,
              "physical_match_id": frame.leakage_group_id, "status": "accepted",
              "split": "DEVELOPMENT", "exposure": "DEVELOPMENT"}
    input_path = tmp_path / "input.json"
    content = json.dumps({"version": "hud_supplier_replay_input_v1", "owner_frames": [{
        "frame_contract": asdict(frame), "source_id": source_id, "ui": ui, "profile": profile,
    }]})
    input_path.write_text(content, encoding="utf-8")
    output = tmp_path / "new-run" / "observations.json"
    monkeypatch.setattr(cli, "load_plan", lambda _: {"inventory_sha256": "3" * 64,
                                                   "allocation_sha256": "3" * 64})
    monkeypatch.setattr(cli, "development_sources", lambda _: [source])
    calls = []
    monkeypatch.setattr(cli, "append_exposure", lambda *a, **k: calls.append(k) or 1)
    monkeypatch.setattr(sys, "argv", ["export", "--review-session", str(tmp_path / "session"),
                                      "--input", str(input_path), "--output", str(output)])
    cli.main()
    result = json.loads(output.read_text(encoding="utf-8"))
    assert result["formal_events"] == [] and result["common_game_state_computed"] is False
    if os.name == "posix":
        assert output.stat().st_mode & 0o777 == 0o600
    assert input_path.read_text(encoding="utf-8") == content
    assert len(calls) == 1 and "frame packets" in capsys.readouterr().out
    with pytest.raises(ValueError, match="New private output directory"):
        cli.main()
    assert len(calls) == 1


@pytest.mark.parametrize("flag", ["qualified", "qualification_created", "approved_gt"])
def test_boundary_export_never_accepts_promoted_producer_labels(flag):
    packets, bracket, _ = boundary_inputs()
    with pytest.raises(ValueError):
        export_boundary_hint("round_end", bracket, packets=packets,
                             producer_fingerprint="a" * 64,
                             producer_evidence={"status": "UNKNOWN", flag: True})


def test_boolean_native_witness_is_not_a_pts_integer():
    a, b = case(1), case(2)
    before = {**a[1], "tick": True}
    bracket = {"before": before, "after": b[1], "lower_tick": True, "upper_tick": 2,
               "time_base": "1/60", "epoch": a[1]["epoch"]}
    with pytest.raises(ValueError):
        export_boundary_hint("round_end", bracket, packets=[a[0], b[0]],
                             producer_fingerprint="a" * 64)


def test_boolean_normalized_roi_is_not_numeric_geometry():
    _, _, frame, ui, profile = case()
    profile["development_ownership_evidence"]["probes"][0]["roi"] = [False, False, True, True]
    ui["source_profile_fingerprint"] = _digest(profile)
    with pytest.raises(ValueError):
        export_owner_ui(frame, "synthetic", ui, profile)


def test_unanalysed_native_rows_are_not_reader_absence():
    _, witness, frame, _, _ = case()
    row = {**witness, "analysed": False, "geometry_consistent": False}
    for name in ("ally_score", "enemy_score", "timer", "result"):
        row[name] = {"value": None, "confidence": 0.0, "sources": []}
    packet = export_round_readers(frame, row, reader_fingerprint="a" * 64,
                                 profile_fingerprint="b" * 64, rois={})
    assert all(x["status"] == "NOT_ANALYSED" for x in packet["measurements"])
    assert packet["measurements"][-1]["value"]["analysed"] is False
    assert packet["formal_events"] == []


def test_original_screen_rejection_and_obscuration_diagnostics_survive_export():
    _, _, frame, ui, profile = case()
    ui["screen_measurements"].update(
        status="unavailable", block_position_candidate=True,
        reasons=["configured_screen_probe_unavailable"],
        spectator_slot={"checked": False, "panel_present": None, "reason": "icon_roi_obscured"},
    )
    ui["remote_detection"] = "not_configured_UNVERIFIED"
    ui["spectator_absence_checked"] = False
    packet = export_owner_ui(frame, "synthetic", ui, profile)
    diagnostic = next(m for m in packet["measurements"] if m["name"] == "owner_reader_diagnostics")
    assert diagnostic["status"] == "unavailable"
    assert diagnostic["value"]["screen_measurements"] == ui["screen_measurements"]
    assert diagnostic["value"]["remote_detection"] == "not_configured_UNVERIFIED"
    assert diagnostic["value"]["spectator_absence_checked"] is False
    assert packet["formal_outputs"] == 0 and packet["qualified"] is False
