import importlib.util
import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

from scripts.e2e.prepare_state_negatives import fragments

PACK = Path(__file__).resolve().parents[2] / "ValorantData/valorant_e2e_validation_pack_v3"


def fixture():
    approval = {"kind": "independently_approved_source_state_intervals",
                "approved_ground_truth": True, "production_input": False,
                "source_video_sha256": "source", "review_provenance": {
                    "reviewer": "human user in current chat",
                    "approval_quote": "synthetic approval"},
                "items": [{"review_item_id": "omen", "round_id": "r6",
                           "core_interval": [10, 11], "observation": "remote_control_view",
                           "agent_context_human_corrected": "omen",
                           "rejected_subtype": "astra_astral"}]}
    evidence = {"kind": "source_overview_not_gt", "source_hash_verified_after_extraction": True,
                "recognizer_outputs_consulted": False, "source_video_sha256": "source",
                "review_tasks": [{"review_item_id": "omen", "review_window_sec": [10, 11]}],
                "frames": [{"source_frame_pts": 10.2, "requested_sec": 10.2,
                            "image": "frame.jpg", "evidence_frame_sha256": "hash"}]}
    return approval, evidence


def evaluator():
    spec = importlib.util.spec_from_file_location("state_reference_evaluator",
                                                PACK / "tests/reference_evaluator.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.evaluate


def test_omen_correction_is_generic_remote_positive_and_not_astra_negative():
    states, negatives, bindings = fragments(*fixture())
    state = states[0]["state_interval"]
    assert state["state"] == "remote_control_view" and state["subtype"] is None
    assert state["exhaustive"] is False and "edge_brackets" not in state
    schema = json.loads((PACK / "schemas/e2e_ground_truth_schema_v3.json").read_text(
        encoding="utf-8",
    ))
    Draft202012Validator({"$ref": "#/$defs/state_interval",
                         "$defs": schema["$defs"]}).validate(state)
    Draft202012Validator(json.loads(
        (PACK / "schemas/negative_assertions_schema_v3.json").read_text(
            encoding="utf-8",
        ))).validate(negatives)
    assert bindings[0]["source_frame_pts"] == 10.2
    assertions = {key: [] for key in ("required_point_events", "ordering_constraints",
                                    "required_snapshots", "event_count_constraints")}
    assertions["required_state_intervals"] = [{**state, "round_id": "r6"}]
    assertions["negative_assertions"] = negatives["assertions"]
    trace = {"events": [{"round_id": "r6", "type": "round_start", "actor": "system",
                         "time_sec": 10.3, "confidence": .95}],
             "state_intervals": [{"round_id": "r6", "state": "remote_control_view",
                                  "subtype": "unknown", "interval": [10, 11], "confidence": .95}],
             "snapshots": [], "temporal_features": []}
    assert evaluator()(assertions, trace) == []  # Independent system start is allowed.
    trace["state_intervals"][0]["subtype"] = "astra_astral"
    assert any("corrected-subtype" in x for x in evaluator()(assertions, trace))
    trace["state_intervals"] = []
    assert any(x.startswith("state_coverage:") for x in evaluator()(assertions, trace))
    trace["events"].append({"type": "shot", "actor": "player", "time_sec": 10.4,
                            "confidence": .95})
    assert any("no-owned-mechanics" in x for x in evaluator()(assertions, trace))


@pytest.mark.parametrize("fault", ["unapproved", "source", "time", "duplicate", "missing",
                                  "path_escape", "duplicate_frame"])
def test_changed_or_unapproved_core_cannot_be_promoted(fault):
    approval, evidence = fixture()
    if fault == "unapproved":
        approval["approved_ground_truth"] = False
    elif fault == "source":
        evidence["source_video_sha256"] = "other"
    elif fault == "time":
        approval["items"][0]["core_interval"] = [9, 11]
    elif fault == "duplicate":
        approval["items"] *= 2
    elif fault == "missing":
        approval["items"] = []
    elif fault == "path_escape":
        approval["items"][0]["review_item_id"] = "../../../escape"
        evidence["review_tasks"][0]["review_item_id"] = "../../../escape"
    else:
        evidence["frames"] *= 2
    with pytest.raises(ValueError):
        fragments(approval, evidence)


def test_purchase_does_not_imply_menu_self_or_mechanics_suppression():
    approval, evidence = fixture()
    approval["items"][0]["observation"] = "buy_phase_banner"
    approval["items"][0].pop("rejected_subtype")
    states, negatives, _ = fragments(approval, evidence)
    assert states[0]["state_interval"]["state_class"] == "flag"
    assert len(negatives["assertions"]) == 1
    assert negatives["assertions"][0]["must_not_emit_matching"] == {
        "type": "round_start", "actor": "system"}
