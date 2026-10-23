"""Small reviewed windows cannot imply population FPR or unreviewed negatives."""

from copy import deepcopy

import pytest

from scripts.diagnostics.hud_failure_corpus import review_natural_windows
from scripts.diagnostics.round_lifecycle_evidence import lifecycle
from scripts.temporal_gt.contract import canonical_hash
from tests.unit.test_round_lifecycle_evidence import chain


def evidence():
    packet = {
        "kind": "DEVELOPMENT_fixed_time_natural_windows_NOT_GT",
        "cases": [{"id": "a"}, {"id": "b"}, {"id": "c"}],
    }
    answers = {
        "origin": "human",
        "reviewer": "user",
        "predictions_consulted": False,
        "packet_sha256": canonical_hash(packet),
        "cases": [
            {"id": "a", "reviewed": True, "end": "NO", "start": "YES", "states": ["BUY", "PLAY"]},
            {"id": "b", "reviewed": True, "end": "UNKNOWN", "start": "NO", "states": ["UNKNOWN"]},
            {"id": "c", "reviewed": False, "end": "UNKNOWN", "start": "UNKNOWN", "states": []},
        ],
    }
    reports = {v["id"]: lifecycle(chain()) for v in packet["cases"]}
    return packet, answers, reports


def test_negative_denominators_are_separate_and_never_include_unknown():
    p, a, r = evidence()
    out = review_natural_windows(p, a, r)
    assert out["end_negative_denominator"] == 1 and out["start_negative_denominator"] == 1
    assert out["false_end_hypotheses"] == 1 and out["false_next_clock_hypotheses"] == 1
    assert out["reviewed_windows"] == 2 and out["formal_events"] == []
    assert not out["unreviewed_is_negative"] and not out["approved_gt"]


@pytest.mark.parametrize(
    "fault", ["duplicate", "unreviewed", "packet", "predictions", "boolean", "states"]
)
def test_unbound_or_ambiguous_answers_are_rejected(fault):
    p, a, r = evidence()
    a = deepcopy(a)
    if fault == "duplicate":
        a["cases"][1]["id"] = "a"
    if fault == "unreviewed":
        a["cases"][2]["end"] = "NO"
    if fault == "packet":
        a["packet_sha256"] = "a" * 64
    if fault == "predictions":
        a["predictions_consulted"] = True
    if fault == "boolean":
        a["cases"][0]["reviewed"] = 1
    if fault == "states":
        a["cases"][0]["states"] = ["ANY"]
    with pytest.raises(ValueError):
        review_natural_windows(p, a, r)
