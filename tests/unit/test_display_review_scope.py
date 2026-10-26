from copy import deepcopy

import pytest

from scripts.diagnostics.display_review_scope import validate_display_review
from scripts.temporal_gt.contract import canonical_hash


def example():
    frames = [
        {
            "id": str(i),
            "source_id": "development",
            "source_sha256": "a" * 64,
            "tick": i * 100,
            "time_base": "1/1000",
            "epoch": "native",
            "encoded_sha256": f"{i + 1:064x}",
            "pixel_sha256": f"{i + 11:064x}",
            "expected_step_ticks": 100,
        }
        for i in range(4)
    ]
    packet = {
        "kind": "development_display_review_packet_v2_1",
        "cases": [{"id": "case", "frames": frames}],
    }
    answer = {
        "kind": "development_display_review_response_v2_1",
        "packet_sha256": canonical_hash(packet),
        "origin": "human",
        "reviewer": "curator",
        "internal_End_tick": None,
        "formal_events": [],
        "cases": [
            {"id": "case", "points": [], "scopes": [], "boundaries": [], "interval_claims": []}
        ],
    }
    return packet, answer


def point(i, state="UNKNOWN", score=None, reviewed=True):
    return {
        "id": f"p{i}",
        "frame_id": str(i),
        "reviewed": reviewed,
        "result_state": state,
        "score": score,
    }


def run(packet, response):
    return validate_display_review(packet, response, trusted_packet_sha256=canonical_hash(packet))


@pytest.mark.parametrize("occurred", ["UNKNOWN", "YES"])
@pytest.mark.parametrize("kind", ["RESULT_APPEARANCE", "SCORE_CHANGE"])
def test_nonnegative_interval_answers_do_not_claim_point_contradictions(occurred, kind):
    p, r = example()
    c = r["cases"][0]
    c["points"] = [point(0, "ABSENT", [1, 2]), point(2, "PRESENT", [1, 3])]
    c["scopes"] = [
        {
            "id": "s", "start": "0", "end": "3",
            "coverage": "PARTIAL", "full_interval_reviewed": False,
        }
    ]
    c["interval_claims"] = [{"kind": kind, "scope_id": "s", "occurred": occurred}]
    result = run(p, r)["cases"][0]
    assert result["brackets"] == [] and result["eligible_interval_negatives"] == []
    claim = result["unknown_claims"][0]
    assert claim["occurred"] == occurred and claim["status"] == "UNKNOWN"
    assert claim["reasons"] == [
        "interval_answer_unknown" if occurred == "UNKNOWN"
        else "positive_interval_claim_not_negative_evidence"
    ]


def test_point_presence_and_score_endpoints_never_generate_an_event():
    p, r = example()
    r["cases"][0]["points"] = [point(0, "PRESENT", [0, 1]), point(2, "PRESENT", [0, 2])]
    result = run(p, r)
    assert len(result["cases"][0]["points"]) == 2
    assert result["cases"][0]["brackets"] == []
    assert result["formal_events"] == [] and result["internal_End_tick"] is None
    assert not result["approved_gt"] and not result["qualification_created"]


@pytest.mark.parametrize(
    "kind,before,after",
    [
        ("RESULT_APPEARANCE", "ABSENT", "PARTIAL"),
        ("RESULT_DISAPPEARANCE", "COMPLETE", "ABSENT"),
        ("RESULT_COMPLETE", "PARTIAL", "COMPLETE"),
    ],
)
def test_explicit_display_state_brackets_stay_intervals(kind, before, after):
    p, r = example()
    c = r["cases"][0]
    c["points"] = [point(0, before), point(2, after)]
    c["boundaries"] = [{"id": "b", "kind": kind, "before": "p0", "after": "p2"}]
    b = run(p, r)["cases"][0]["brackets"][0]
    assert (b["lower_tick"], b["upper_tick"], b["time_base"]) == (0, 200, "1/1000")
    assert b["kind"] == kind and b["internal_End_tick"] is None
    assert b["physical_episode_id"] is None and not b["full_interval_reviewed"]


def test_score_before_after_and_explicit_change_are_distinct():
    p, r = example()
    c = r["cases"][0]
    c["points"] = [point(0, score=[3, 4]), point(1, score=[3, 5])]
    assert run(p, r)["cases"][0]["brackets"] == []
    c["boundaries"] = [{"id": "s", "kind": "SCORE_CHANGE", "before": "p0", "after": "p1"}]
    assert run(p, r)["cases"][0]["brackets"][0]["kind"] == "SCORE_CHANGE"


@pytest.mark.parametrize("coverage", ["PARTIAL", "UNKNOWN", "FULL"])
def test_only_explicit_full_contiguous_review_can_support_a_no_change_claim(coverage):
    p, r = example()
    c = r["cases"][0]
    c["scopes"] = [
        {
            "id": "scope",
            "start": "0",
            "end": "3",
            "coverage": coverage,
            "full_interval_reviewed": coverage == "FULL",
        }
    ]
    c["interval_claims"] = [{"kind": "SCORE_CHANGE", "scope_id": "scope", "occurred": "NO"}]
    result = run(p, r)["cases"][0]
    assert len(result["eligible_interval_negatives"]) == (coverage == "FULL")


@pytest.mark.parametrize("gap", ["epoch", "missing_native_frame", "duplicate_pixels"])
def test_source_discontinuity_or_identical_pixels_cannot_prove_a_state_transition(gap):
    p, r = example()
    c = r["cases"][0]
    c["points"] = [point(0, "ABSENT"), point(2, "COMPLETE")]
    c["boundaries"] = [{"id": "b", "kind": "RESULT_APPEARANCE", "before": "p0", "after": "p2"}]
    if gap == "epoch":
        p["cases"][0]["frames"][2]["epoch"] = "second"
    elif gap == "missing_native_frame":
        p["cases"][0]["frames"].pop(1)
    else:
        p["cases"][0]["frames"][2]["pixel_sha256"] = p["cases"][0]["frames"][0]["pixel_sha256"]
    r["packet_sha256"] = canonical_hash(p)
    result = run(p, r)["cases"][0]
    assert result["brackets"] == [] and result["unknown_claims"]


def test_full_review_flag_does_not_hide_a_native_gap():
    p, r = example()
    p["cases"][0]["frames"].pop(1)
    r["packet_sha256"] = canonical_hash(p)
    c = r["cases"][0]
    c["scopes"] = [
        {
            "id": "scope",
            "start": "0",
            "end": "3",
            "coverage": "FULL",
            "full_interval_reviewed": True,
        }
    ]
    c["interval_claims"] = [{"kind": "SCORE_CHANGE", "scope_id": "scope", "occurred": "NO"}]
    assert run(p, r)["cases"][0]["eligible_interval_negatives"] == []


def test_unreviewed_or_wrong_state_claim_stays_unknown():
    p, r = example()
    c = r["cases"][0]
    c["points"] = [point(0, "PRESENT", reviewed=False), point(1, "PRESENT")]
    c["boundaries"] = [{"id": "b", "kind": "RESULT_APPEARANCE", "before": "p0", "after": "p1"}]
    assert run(p, r)["cases"][0]["brackets"] == []


def test_unreviewed_raw_point_claim_is_not_a_validated_observation():
    p, r = example()
    r["cases"][0]["points"] = [point(0, "PRESENT", [3, 4], reviewed=False)]
    observed = run(p, r)["cases"][0]["points"][0]
    assert observed["result_state"] == "UNKNOWN" and observed["score"] is None
    assert observed["claimed_result_state"] == "PRESENT"


def test_conflicting_point_answers_for_the_same_frame_are_rejected():
    p, r = example()
    a, b = point(0, "PRESENT"), point(0, "ABSENT")
    b["id"] = "second_answer"
    r["cases"][0]["points"] = [a, b]
    with pytest.raises(ValueError, match="one point response"):
        run(p, r)


def test_unrecognized_claim_flags_do_not_leak_into_validated_observations():
    p, r = example()
    r["cases"][0]["points"] = [{**point(0), "qualified": True, "approved_gt": True}]
    result = run(p, r)
    observed = result["cases"][0]["points"][0]
    assert "qualified" not in observed and "approved_gt" not in observed
    assert not result["approved_gt"]


def test_non_string_interval_answer_is_rejected_as_invalid_input():
    p, r = example()
    r["cases"][0]["scopes"] = [
        {"id": "s", "start": "0", "end": "3", "coverage": "FULL", "full_interval_reviewed": True}
    ]
    r["cases"][0]["interval_claims"] = [{"kind": "SCORE_CHANGE", "scope_id": "s", "occurred": []}]
    with pytest.raises(ValueError, match="explicit typed interval"):
        run(p, r)


@pytest.mark.parametrize(
    "kind,before,after,scores",
    [
        ("RESULT_APPEARANCE", "ABSENT", "PRESENT", [None, None]),
        ("RESULT_DISAPPEARANCE", "COMPLETE", "ABSENT", [None, None]),
        ("SCORE_CHANGE", "UNKNOWN", "UNKNOWN", [[1, 2], [1, 3]]),
    ],
)
def test_points_veto_a_contradictory_negative_without_generating_a_boundary(
    kind,
    before,
    after,
    scores,
):
    p, r = example()
    c = r["cases"][0]
    c["points"] = [point(0, before, scores[0]), point(2, after, scores[1])]
    c["scopes"] = [
        {"id": "s", "start": "0", "end": "3", "coverage": "FULL", "full_interval_reviewed": True}
    ]
    c["interval_claims"] = [{"kind": kind, "scope_id": "s", "occurred": "NO"}]
    result = run(p, r)["cases"][0]
    assert result["brackets"] == [] and result["eligible_interval_negatives"] == []
    assert "contradictory_reviewed_points" in result["unknown_claims"][0]["reasons"]


def test_a_single_point_is_not_a_reviewed_negative_interval():
    p, r = example()
    c = r["cases"][0]
    c["scopes"] = [
        {"id": "s", "start": "0", "end": "0", "coverage": "FULL", "full_interval_reviewed": True}
    ]
    c["interval_claims"] = [{"kind": "SCORE_CHANGE", "scope_id": "s", "occurred": "NO"}]
    assert run(p, r)["cases"][0]["eligible_interval_negatives"] == []


def test_explicit_source_cut_inside_an_otherwise_regular_ledger_blocks_a_boundary():
    p, r = example()
    p["cases"][0]["frames"][1]["discontinuity"] = True
    r["packet_sha256"] = canonical_hash(p)
    c = r["cases"][0]
    c["points"] = [point(0, "PRESENT"), point(2, "ABSENT")]
    c["boundaries"] = [{"id": "b", "kind": "RESULT_DISAPPEARANCE", "before": "p0", "after": "p2"}]
    assert run(p, r)["cases"][0]["brackets"] == []


@pytest.mark.parametrize(
    "mutation",
    [
        "AI",
        "wrong_anchor",
        "internal_end",
        "formal_event",
        "foreign_frame",
        "duplicate_case",
        "bad_timebase",
        "duplicate_PTS",
        "foreign_source",
        "bad_score_bool",
    ],
)
def test_invalid_binding_or_qualification_injection_is_rejected(mutation):
    p, r = example()
    c = r["cases"][0]
    c["points"] = [point(0)]
    if mutation == "AI":
        r["origin"] = "AI"
    elif mutation == "wrong_anchor":
        r["packet_sha256"] = "b" * 64
    elif mutation == "internal_end":
        r["internal_End_tick"] = 100
    elif mutation == "formal_event":
        r["formal_events"] = [{"end": 1}]
    elif mutation == "foreign_frame":
        c["points"][0]["frame_id"] = "foreign"
    elif mutation == "duplicate_case":
        r["cases"].append(deepcopy(c))
    elif mutation == "bad_timebase":
        p["cases"][0]["frames"][0]["time_base"] = "0/1"
    elif mutation == "duplicate_PTS":
        p["cases"][0]["frames"][1]["tick"] = 0
    elif mutation == "foreign_source":
        p["cases"][0]["frames"][1]["source_sha256"] = "b" * 64
    elif mutation == "bad_score_bool":
        c["points"][0]["score"] = [True, 2]
    if mutation in {"bad_timebase", "duplicate_PTS", "foreign_source"}:
        r["packet_sha256"] = canonical_hash(p)
    with pytest.raises(ValueError):
        run(p, r)
