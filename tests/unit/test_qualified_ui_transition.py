from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace

import pytest

from tests.e2e.trace_adapter import to_e2e_trace
from tests.unit.test_global_round_lifecycle import build, digest, qualification, report
from tests.unit.test_global_start_hypothesis import observation
from valorant_ai_coach.events import EventSourceContract
from valorant_ai_coach.hud.global_lifecycle import GlobalRoundLifecycle
from valorant_ai_coach.resources import resource_path
from valorant_ai_coach.rounds import RoundPackageBuilder
from valorant_ai_coach.schema_validation import SchemaValidator
from valorant_ai_coach.video import VideoMetadata


def scene_qualification(tmp_path):
    data = report()
    for name in ("scene_continuity", "ui_transition"):
        data["components"][name] = {
            "training_hashes": [digest(f"{name}/training/{i}") for i in range(3)],
            "holdout_hashes": [digest(f"{name}/holdout/{i}") for i in range(3)],
            "negative_hashes": [digest(f"{name}/negative/{i}") for i in range(3)],
            "holdout_correct": 3,
            "holdout_unknown": 0,
            "holdout_wrong": 0,
            "negative_false_positive": 0,
            "review_provenance": "SYNTHETIC UNIT FIXTURE; not runtime qualification",
        }
    return qualification(tmp_path, data)


def sequence():
    # Arbitrary synthetic clocks and PTS; no acceptance-window values.
    spec = [
        (0, 0, "0:00", True),
        (0.1, 0, "0:00", True),
        (0.12, 0, "0:00", False),
        (0.14, 128, "2:08", False),
        (0.16, 128, "2:08", False),
        (0.18, 93, "1:33", False),
        (0.20, 93, "1:33", False),
        (0.22, 93, "1:33", False),
        (0.24, 93, "1:33", False),
        (0.28, 93, "1:33", False),
    ]
    rows = []
    for i, (pts, value, display, phase) in enumerate(spec):
        row = observation(i, pts, phase=phase, timer=value)
        row["values"].update(
            round_time_remaining_display=display,
            round_time_remaining_display_provenance={
                "reader": "round_timer",
                "sources": ["synthetic-reader"],
                "confidence": 0.95,
                "cross_checked": True,
            },
        )
        rows.append(row)
    return rows


def scene_proofs(rows, q):
    evidence = {}
    for i, row in enumerate(rows):
        proof = {
            "segment": "synthetic-scene-a",
            "confidence": 0.96,
            "qualification_sha256": q.report_sha256,
            "source_pts_sec": row["time_sec"],
            "previous_source_pts_sec": rows[i - 1]["time_sec"] if i else -0.01,
            "source_pixel_sha256": digest(f"synthetic-source-{i}"),
            "previous_source_pixel_sha256": digest(f"synthetic-source-{i - 1}"),
            "scope": "scene_only",
            "clock_independent": True,
            "background_checked": True,
            "profile_fingerprint": q.profile_fingerprint,
            "recognizer_fingerprint": q.recognizer_fingerprint,
            "witness_cells": [[0, 0], [0, 2], [2, 1]],
            "witness_ncc": [0.96, 0.95, 0.97],
        }
        evidence[row["frame_index"]] = {"global_scene_continuity": proof}
    evidence[2]["global_ui_transition"] = {
        "qualification_sha256": q.report_sha256,
        "source_pts_sec": rows[2]["time_sec"],
        "source_pixel_sha256": evidence[2]["global_scene_continuity"]["source_pixel_sha256"],
        "kind": "phase_disappearance",
        "confidence": 0.96,
    }
    return evidence


def test_transient_values_retained_before_one_system_start_and_native_trace(tmp_path):
    rows = sequence()
    original = deepcopy(rows)
    q = scene_qualification(tmp_path)
    evidence = scene_proofs(rows, q)
    model = GlobalRoundLifecycle(q)
    decisions = []
    states = []
    for row in rows:
        decisions.extend(model.advance(row, evidence[row["frame_index"]]))
        states.append(model.state)
    assert states[2:8] == ["transient_ui_transition"] * 6
    assert [(d.kind, d.time_sec) for d in decisions] == [("round_start", 0.12)]
    provenance = decisions[0].attributes["evidence_provenance"]
    assert provenance["confirmation_pts_sec"] == 0.24
    assert provenance["coherent_clock_begin_pts_sec"] == 0.18
    assert [s["observed_display"] for s in provenance["clock_display_samples"]] == [
        "0:00",
        "2:08",
        "2:08",
        "1:33",
        "1:33",
        "1:33",
        "1:33",
    ]
    assert rows == original
    events = build(rows, q, evidence)
    assert [(e["type"], e["actor"], e["time_sec"]) for e in events] == [
        ("round_start", "system", 0.12)
    ]
    packages = RoundPackageBuilder(
        contract=EventSourceContract.load(resource_path("config/event_source_contract_v1.json")),
        validator=SchemaValidator(),
    ).build(
        match_id="synthetic-ui-contract",
        video_metadata=VideoMetadata(Path("source.mp4"), 1, 1920, 1080, 60, "h264", None, False, 1),
        hud_observations=rows,
        hud_events=events,
    )
    trace = to_e2e_trace(
        SimpleNamespace(round_packages=packages, observations=rows, visual_observations=())
    )
    boundary = [e for e in trace["events"] if e["type"] == "round_start"]
    assert len(boundary) == 1
    assert boundary[0]["actor"] == "system"
    assert boundary[0]["attributes"] == events[0]["attributes"]
    assert not any(i["owner"] == "self" for i in trace["ownership_intervals"])


@pytest.mark.parametrize(
    "missing",
    ["scene", "ui", "display", "background", "spatial", "display_provenance", "clock_independence"],
)
def test_each_new_positive_source_contract_is_required(tmp_path, missing):
    rows = sequence()
    q = scene_qualification(tmp_path)
    evidence = scene_proofs(rows, q)
    if missing == "scene":
        for r in evidence.values():
            r["global_continuity"] = r.pop("global_scene_continuity")
    elif missing == "ui":
        evidence[2].pop("global_ui_transition")
    elif missing == "display":
        for row in rows:
            row["values"]["round_time_remaining_display"] = None
    elif missing == "display_provenance":
        for row in rows:
            row["values"]["round_time_remaining_display_provenance"]["confidence"] = 0.89
    elif missing == "background":
        for r in evidence.values():
            r["global_scene_continuity"]["background_checked"] = False
    elif missing == "spatial":
        for r in evidence.values():
            r["global_scene_continuity"]["witness_cells"] = [[0, 0], [0, 1], [0, 2]]
    elif missing == "clock_independence":
        for r in evidence.values():
            r["global_scene_continuity"]["clock_independent"] = False
    assert not build(rows, q, evidence)


@pytest.mark.parametrize("kind", ["cut", "gap", "duplicate", "chain", "epoch", "menu", "spectator"])
def test_no_transition_is_combined_across_source_or_state_interruption(tmp_path, kind):
    rows = sequence()
    q = scene_qualification(tmp_path)
    evidence = scene_proofs(rows, q)
    if kind == "cut":
        evidence[5]["content_jump"] = True
    elif kind == "gap":
        rows[5]["time_sec"] = 2
        rows = rows[:6]
    elif kind == "duplicate":
        evidence[5]["global_scene_continuity"]["source_pixel_sha256"] = evidence[5][
            "global_scene_continuity"
        ]["previous_source_pixel_sha256"]
    elif kind == "chain":
        evidence[5]["global_scene_continuity"]["previous_source_pixel_sha256"] = digest(
            "wrong-previous-source"
        )
    elif kind == "epoch":
        evidence[5]["global_scene_continuity"]["segment"] = "new-scene"
    else:
        rows[5]["primary_state"] = "buy_menu_open" if kind == "menu" else "spectator_first_person"
    assert not build(rows, q, evidence)


def test_pair_qualification_is_mandatory_and_old_route_is_not_upgraded(tmp_path):
    data = report()
    data["components"]["ui_transition"] = data["components"]["timer"]
    with pytest.raises(ValueError, match="paired qualification"):
        qualification(tmp_path, data)
    rows = sequence()
    old = qualification(tmp_path)
    evidence = scene_proofs(rows, old)
    assert not build(rows, old, evidence)


@pytest.mark.parametrize("bad", ["stale_pts", "wrong_pixel", "wrong_kind"])
def test_ui_transition_must_be_current_and_bound_to_same_source(tmp_path, bad):
    rows = sequence()
    q = scene_qualification(tmp_path)
    evidence = scene_proofs(rows, q)
    proof = evidence[2]["global_ui_transition"]
    if bad == "stale_pts":
        proof["source_pts_sec"] = 0.1
    elif bad == "wrong_pixel":
        proof["source_pixel_sha256"] = digest("other-source")
    else:
        proof["kind"] = "menu_disappearance"
    assert not build(rows, q, evidence)


def test_phase_jitter_cancels_candidate_and_needs_new_preparation_span(tmp_path):
    rows = sequence()
    rows[6]["state_flags"] = ["buy_phase_banner"]
    rows[6]["values"].update(
        buy_phase_visible=True, round_time_remaining_sec=0, round_time_remaining_display="0:00"
    )
    rows[6]["quality"]["roi_confidence"]["center_phase_banner_semantic_text"] = 0.96
    q = scene_qualification(tmp_path)
    assert not build(rows, q, scene_proofs(rows, q))


def test_source_proof_abstention_reports_reason_instead_of_using_timer_proof(tmp_path):
    rows = sequence()
    q = scene_qualification(tmp_path)
    records = []
    from valorant_ai_coach.hud.temporal import HudDirectEventBuilder

    assert not HudDirectEventBuilder().build(
        rows,
        global_qualification=q,
        lifecycle_sink=records.append,
    )
    assert all(
        r["global_transition_reason"] == "qualified_scene_proof_unavailable" for r in records
    )


def test_scene_contract_rearms_second_round_and_associates_preparation(tmp_path):
    rows = sequence()
    q = scene_qualification(tmp_path)
    before = deepcopy(rows[-1])
    after = deepcopy(before)
    before.update(frame_index=10, time_sec=0.4)
    after.update(frame_index=11, time_sec=0.5)
    for row in (before, after):
        row["values"].update(score_ally=2, score_enemy=3)
        row["quality"]["roi_confidence"].update(score_ally_value=0.96, score_enemy_value=0.96)
    after["values"]["score_ally"] = 3
    rows.extend([before, after])
    for i, row in enumerate(sequence(), start=12):
        row.update(frame_index=i, time_sec=row["time_sec"] + 0.6)
        rows.append(row)
    evidence = scene_proofs(rows, q)
    evidence[11].update(global_round_result_present=True, global_round_result_confidence=0.96)
    evidence[14]["global_ui_transition"] = {
        **evidence[2]["global_ui_transition"],
        "source_pts_sec": rows[14]["time_sec"],
        "source_pixel_sha256": evidence[14]["global_scene_continuity"]["source_pixel_sha256"],
    }
    events = build(rows, q, evidence)
    assert [(e["type"], e["time_sec"]) for e in events] == [
        ("round_start", 0.12), ("round_end", 0.5), ("round_start", 0.72)
    ]
    packages = RoundPackageBuilder(
        contract=EventSourceContract.load(resource_path("config/event_source_contract_v1.json")),
        validator=SchemaValidator(),
    ).build(
        match_id="synthetic-two-ui-rounds",
        video_metadata=VideoMetadata(Path("source.mp4"), 2, 1920, 1080, 60, "h264", None, False, 1),
        hud_observations=rows,
        hud_events=events,
    )
    assert len(packages) == 2
    trace = to_e2e_trace(
        SimpleNamespace(round_packages=packages, observations=rows, visual_observations=())
    )
    starts = [e for e in trace["events"] if e["type"] == "round_start"]
    assert starts[0]["round_id"] != starts[1]["round_id"]
    assert starts[1]["attributes"]["evidence_provenance"]["preparation_pts_sec"] == [0.6, 0.7]
    assert sum(e["type"] == "round_end" for e in trace["events"]) == 1
    assert all(e["actor"] == "system" for e in trace["events"] if e["type"].startswith("round_"))
