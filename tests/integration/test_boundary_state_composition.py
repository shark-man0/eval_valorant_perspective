import json
from copy import deepcopy

import pytest
from test_composed_boundary_timeline import PACK
from test_composed_boundary_timeline import fixture as boundary_fixture
from test_source_state_negatives import fixture as state_fixture

from scripts.e2e.compose_boundary_timeline import compose, merge_states
from scripts.e2e.prepare_state_negatives import fragments


def inputs():
    boundary = boundary_fixture()
    timeline = compose(*boundary)
    states, negatives, bindings = fragments(*state_fixture())
    states[0]["round_id"] = "r2"
    report = {"kind": "private_v3_source_state_fragments_not_complete_pack",
              "production_input": False, "source_video_sha256": "source",
              "states": states, "negatives": negatives, "evidence_bindings": bindings}
    negative_schema = json.loads((PACK / "schemas/negative_assertions_schema_v3.json").read_text(
        encoding="utf-8",
    ))
    return timeline, report, "source", boundary[5], negative_schema


def test_composition_preserves_boundary_contracts_and_no_subtype_promotion():
    args = inputs()
    before = deepcopy(args[0])
    timeline, negatives = merge_states(*args)
    assert args[0] == before
    assert timeline["rounds"][1]["state_intervals"][0]["subtype"] is None
    assert timeline["rounds"][1]["point_events"] == before["rounds"][1]["point_events"]
    assert timeline["rounds"][1]["round_package_expectations"] == (
        before["rounds"][1]["round_package_expectations"])
    assert timeline["continuous_segments"] == before["continuous_segments"]
    assert negatives == args[1]["negatives"]
    assert "ownership_intervals" not in timeline["rounds"][1]
    with pytest.raises(ValueError, match="duplicate"):
        merge_states(timeline, *args[1:])


@pytest.mark.parametrize("fault", ["source", "production", "unknown_round", "reversed_core",
                                  "duplicate_negative", "reversed_negative"])
def test_unsafe_state_merge_rejected(fault):
    args = inputs()
    report = args[1]
    if fault == "source":
        report["source_video_sha256"] = "other"
    elif fault == "production":
        report["production_input"] = True
    elif fault == "unknown_round":
        report["states"][0]["round_id"] = "absent"
    elif fault == "reversed_core":
        report["states"][0]["state_interval"]["core_interval"] = [11, 10]
    elif fault == "duplicate_negative":
        report["negatives"]["assertions"] *= 2
    else:
        report["negatives"]["assertions"][0]["window"] = [11, 10]
    with pytest.raises(ValueError):
        merge_states(*args)
