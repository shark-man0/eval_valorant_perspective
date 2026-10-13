import importlib.util
import json
from pathlib import Path

import pytest

from scripts.e2e.compose_boundary_timeline import compose

PACK = Path(__file__).resolve().parents[2] / "ValorantData/valorant_e2e_validation_pack_v3"


def fixture():
    def point(kind, time):
        return {"round_id": "r1", "point": {
            "id": kind, "kind": "point_event", "type": kind, "actor": "system",
            "evidence_bracket": {"last_absent_sec": time - .1, "first_present_sec": time},
            "tolerance_before_sec": .1, "tolerance_after_sec": .1, "facts": {},
            "evidence": ["assets/synthetic.jpg"], "required_event_attributes": {}}}

    fragments = {"source_video_sha256": "source", "ledger_sha256": "ledger",
                 "points": [point("round_start", 1), point("round_end", 2)]}
    approval = {"kind": "independently_approved_score_number_mapping", "video_id": "synthetic",
                "source_video_sha256": "source", "approved_ground_truth": True,
                "production_input": False, "round_numbers": {"r1": 1, "r2": 2},
                "review_provenance": {"reviewer": "human user in current chat",
                                      "approval_quote": "synthetic explicit approval"}}
    fragments["points"].append({**point("round_start", 3), "round_id": "r2"})
    fragments["points"][-1]["point"]["id"] = "r2-start"
    review = {"kind": "private_score_number_review_not_gt",
              "source_video_sha256": "source", "ledger_sha256": "ledger",
              "recognizer_outputs_consulted": False,
              "items": [{"annotation_round_id": "r1"}, {"annotation_round_id": "r2"}]}
    declared = {"source_video_sha256": "source", "ledger_sha256": "ledger", "round_id": "r2",
                "first_native_onset_verified": False, "last_absent_sec": None,
                "round_package_expectations": {"event_count_constraints": [{
                    "type": "round_end", "actor": "system", "min": 1, "max": 1,
                    "window": [3.9, 4.1]}]}}
    continuity = {"source_video_sha256": "source", "production_input": False,
                  "approved_ground_truth": True, "items": [{
                      "continuity_approval": True, "approval_quote": "synthetic approval",
                      "continuity_status": "independently_reviewed_interval",
                      "review_item_id": "source1", "review_window_sec": [0, 2.5]}]}
    schema = json.loads((PACK / "schemas/e2e_ground_truth_schema_v3.json").read_text())
    policy = {"utility_used": "unannotated", "shot_granularity": "burst_start"}
    return [fragments, approval, review, declared, continuity, schema, policy]


def test_composition_keeps_unknowns_and_exact_review_scope():
    timeline = compose(*fixture())
    first, second = timeline["rounds"]
    assert first["match_round_number_from_score"] == 1
    assert second["match_round_number_from_score"] == 2
    assert len(second["point_events"]) == 1  # No fabricated end bracket.
    assert timeline["continuous_segments"][0]["interval"] == [0, 2.5]
    assert all(not r["state_intervals"] and not r["snapshots"] for r in timeline["rounds"])


@pytest.mark.parametrize("fault", ["source", "approval", "mapping", "duplicate",
                                  "onset", "continuity", "missing"])
def test_composition_rejects_unapproved_or_inconsistent_inputs(fault):
    args = fixture()
    if fault == "source":
        args[1]["source_video_sha256"] = "other"
    elif fault == "approval":
        args[1]["approved_ground_truth"] = False
    elif fault == "mapping":
        args[1]["round_numbers"]["r2"] = True
    elif fault == "duplicate":
        args[0]["points"].append(args[0]["points"][0])
    elif fault == "onset":
        args[3]["last_absent_sec"] = 3.8
    elif fault == "continuity":
        args[4]["items"][0]["continuity_approval"] = False
    else:
        args[0]["points"].pop(1)
    with pytest.raises(ValueError):
        compose(*args)


def test_unchanged_compiler_and_evaluator_keep_all_positive_and_duplicate_checks():
    def module(name):
        spec = importlib.util.spec_from_file_location(name, PACK / "tests" / f"{name}.py")
        result = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(result)
        return result

    timeline = compose(*fixture())
    compiler = module("build_assertions")
    vocab = json.loads((PACK / "contracts/event_attribute_vocab_v1.json").read_text())
    values = {"ground_truth/timeline_ground_truth_v3.json": timeline,
              "ground_truth/negative_assertions_v3.json": {"assertions": []},
              "contracts/event_attribute_vocab_v1.json": vocab}
    compiler.load = values.__getitem__
    assertions = compiler.build()
    evaluator = module("reference_evaluator")
    events = [{"round_id": rid, "type": kind, "actor": "system", "time_sec": t,
               "confidence": .95, "attributes": {}}
              for rid, kind, t in [("r1", "round_start", 1), ("r1", "round_end", 2),
                                   ("r2", "round_start", 3), ("r2", "round_end", 4)]]
    trace = {"events": events, "state_intervals": [], "snapshots": [],
             "ownership_intervals": [], "visual_observations": [], "temporal_features": []}
    assert evaluator.evaluate(assertions, trace) == []
    trace["events"] = events[:-1]
    assert evaluator.evaluate(assertions, trace)
    trace["events"] = events + [{**events[-1], "time_sec": 5}]
    assert evaluator.evaluate(assertions, trace)  # Duplicate outside the narrow end window.
    trace["events"] = [*events[:-1], {**events[-1], "round_id": "r1"}]
    assert evaluator.evaluate(assertions, trace)
