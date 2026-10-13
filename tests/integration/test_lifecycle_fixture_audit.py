import copy
import json

import pytest
from test_fixture_validation import valid_pack
from test_match002_confidence_policy import original
from test_pack_stage_assembly import PACK

from scripts.e2e.audit_lifecycle_fixture import GROUPS, audit, negative_mutations, oracle


def inputs(tmp_path, monkeypatch):
    pack = valid_pack(tmp_path, monkeypatch)
    assertions = json.loads((pack / "tests/generated/e2e_assertions_v3.json").read_text())
    schema = json.loads((PACK / "schemas/e2e_output_trace_schema_v1.json").read_text())
    return assertions, schema


def test_audit_checks_every_boundary_and_actor_negative_without_promoting(tmp_path, monkeypatch):
    assertions, schema = inputs(tmp_path, monkeypatch)
    before = copy.deepcopy(assertions)
    report = audit(assertions, original().evaluate, schema)
    assert report["boundaries"] == 4
    assert report["checks"] == {"missing_boundary": 4, "duplicate_boundary": 4,
                                "wrong_round": 4, "late_boundary": 4,
                                "negative_mutations": 11, "missing_state": 0}
    assert report["synthetic_only"] is True
    assert report["real_video_detection_verified"] is False
    assert report["formal_pack_completed"] is False
    assert assertions == before


def test_always_green_evaluator_is_rejected(tmp_path, monkeypatch):
    assertions, schema = inputs(tmp_path, monkeypatch)
    with pytest.raises(ValueError, match="empty Analyzer trace"):
        audit(assertions, lambda *_: [], schema)


def test_always_failing_evaluator_is_rejected(tmp_path, monkeypatch):
    assertions, schema = inputs(tmp_path, monkeypatch)
    with pytest.raises(ValueError, match="positive synthetic oracle"):
        audit(assertions, lambda *_: ["fake_failure"], schema)


def test_unrelated_failure_cannot_mask_unchecked_negative(tmp_path, monkeypatch):
    assertions, schema = inputs(tmp_path, monkeypatch)
    evaluator = original().evaluate

    def broken(requirements, trace):
        failures = evaluator(requirements, trace)
        return ["unrelated_failure"] if any(f.startswith("negative_") for f in failures) else (
            failures)

    with pytest.raises(ValueError, match="specific negative assertion"):
        audit(assertions, broken, schema)


def test_negative_arrays_each_have_independent_corruption():
    trace = {key: [] for key in GROUPS}
    trace["events"] = [{"round_id": "synthetic"}]
    negative = {"id": "synthetic", "window": [1, 2],
                "must_not_emit_player_event_types": ["shot", "peek"],
                "must_not_span_temporal_features": ["shot.duration_sec", "peek.duration_sec"],
                "must_not_state_match": {"state": "live_first_person"},
                "must_not_match_snapshot_subset": {"view_owner": "self"}}
    variants = list(negative_mutations(trace, negative))
    assert len(variants) == 6
    assert len(trace["events"]) == 1 and not trace["state_intervals"]
    assert {row[0]["temporal_features"][0]["feature"] for row in variants
            if row[0]["temporal_features"]} == {"shot.duration_sec", "peek.duration_sec"}


def test_unimplemented_negative_branch_is_not_ignored():
    with pytest.raises(ValueError, match="silently skipped"):
        list(negative_mutations({}, {"must_not_update_player_fields_to": {"hp": 0}}))


def test_unannotated_end_time_is_never_invented(tmp_path, monkeypatch):
    assertions, _ = inputs(tmp_path, monkeypatch)
    assertions["event_count_constraints"] = [row for row in assertions["event_count_constraints"]
                                              if "window" not in row]
    with pytest.raises(ValueError, match="time-bounded lifecycle"):
        oracle(assertions)


def test_additional_observation_contract_needs_explicit_coverage(tmp_path, monkeypatch):
    assertions, _ = inputs(tmp_path, monkeypatch)
    assertions["required_snapshots"] = [{"id": "unhandled"}]
    with pytest.raises(ValueError, match="additional observation assertions"):
        oracle(assertions)
