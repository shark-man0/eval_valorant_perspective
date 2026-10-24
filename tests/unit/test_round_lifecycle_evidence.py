"""Offline lifecycle evidence must not repair gaps or infer internal events."""
from copy import deepcopy

import pytest

from scripts.diagnostics.round_lifecycle_evidence import lifecycle, review_scores
from scripts.temporal_gt.contract import canonical_hash
from tests.unit.test_round_transition_evidence import frame, transition


def chain():
    rows = transition()
    rows += [frame(t, score=(2, 4), timer=None) for t in range(6, 42)]
    for tick, timer, buy in [(9, "0:00", False), (10, "0:30", True),
                             (11, "0:29", True), (38, "0:02", True),
                             (39, "0:01", True), (40, "1:40", False),
                             (41, "1:39", False)]:
        rows[tick]["timer"]["value"] = timer
        rows[tick]["buy_phase"] = buy
    for f in rows:
        f["time_base"] = "1/1"
    return rows


def test_end_buy_start_output_is_display_diagnostic_and_input_unchanged():
    rows = chain()
    before = deepcopy(rows)
    report = lifecycle(rows)
    c = report["chains"][0]
    assert c["status"] == "DEVELOPMENT_LIFECYCLE_CANDIDATE"
    assert c["buy_support_interval"]["lower_tick"] == 10
    assert c["next_clock_reset_bracket"]["lower_tick"] == 39
    assert c["next_clock_reset_bracket"]["upper_tick"] == 40
    assert c["internal_End_tick"] is None and report["formal_events"] == []
    assert c["purchase_onset_status"] == "UNVERIFIED"
    assert rows == before


@pytest.mark.parametrize("fault,reason", [
    ("epoch", "purchase_not_observed"),
    ("gap", "purchase_not_observed"),
    ("geometry", "purchase_not_observed"),
    ("score", "score_changed_before_next_start"),
    ("clock", "next_active_clock_not_observed"),
    ("buy_overlap", "next_active_clock_not_observed"),
])
def test_shortages_and_contradictions_remain_unknown(fault, reason):
    rows = chain()
    if fault == "epoch":
        for f in rows[10:]:
            f["epoch"] = "new"
    elif fault == "gap":
        rows.pop(6)
    elif fault == "geometry":
        for f in rows[10:]:
            f["geometry_consistent"] = False
    elif fault == "score":
        rows[10]["ally_score"]["value"] = "3"
    elif fault == "clock":
        for f in rows[-2:]:
            f["timer"]["value"] = "0:29"
    elif fault == "buy_overlap":
        for f in rows[-2:]:
            f["buy_phase"] = True
    c = lifecycle(rows)["chains"][0]
    assert c["status"] == "UNKNOWN" and reason in c["reasons"]


def packet_response():
    f = frame(1)
    p = {"kind": "DEVELOPMENT_blind_transcription_score_NOT_GT", "cases": [
        {"id": "one", "frame": f, "candidate_id": "c"}]}
    a = {"packet_sha256": canonical_hash(p), "origin": "human", "reviewer": "user",
         "cases": [{"id": "one", "reviewed": True, "left_score": 1, "right_score": 4}]}
    return p, a


def test_score_transcription_is_independent_receipt_bound_observation_not_gt():
    p, a = packet_response()
    output = review_scores(p, a)
    assert output["observations"][0]["score"] == [1, 4]
    assert output["approved_gt"] is False


@pytest.mark.parametrize("fault", ["packet", "duplicate", "bool", "unreviewed", "reviewer"])
def test_invalid_score_review_cannot_become_human_evidence(fault):
    p, a = packet_response()
    if fault == "packet":
        a["packet_sha256"] = "a" * 64
    elif fault == "duplicate":
        a["cases"] *= 2
    elif fault == "bool":
        a["cases"][0]["left_score"] = True
    elif fault == "unreviewed":
        a["cases"][0]["reviewed"] = False
    else:
        a["reviewer"] = ""
    with pytest.raises(ValueError):
        review_scores(p, a)


def test_unanalysed_native_frames_are_not_positives_or_negatives():
    rows = chain()
    for f in rows[12:38]:
        f["ally_score"]["value"] = None
        f["enemy_score"]["value"] = None
        f["geometry_consistent"] = False
    c = lifecycle(rows)["chains"][0]
    assert c["status"] == "DEVELOPMENT_LIFECYCLE_CANDIDATE"
    assert len(c["unread_score_witnesses"]) == 26
    assert c["next_start_semantic_status"] == "UNVERIFIED"


def test_buy_timer_reversal_remains_unknown():
    rows = chain()
    rows[11]["timer"]["value"] = "0:35"
    c = lifecycle(rows)["chains"][0]
    assert c["status"] == "UNKNOWN" and "purchase_clock_contradiction" in c["reasons"]


def test_next_clock_observations_must_be_temporally_consistent():
    rows = chain()
    rows[-1]["timer"]["value"] = "2:00"
    c = lifecycle(rows)["chains"][0]
    assert c["status"] == "UNKNOWN" and "next_clock_contradiction" in c["reasons"]


def test_transient_clock_prefix_is_retained_before_later_consistent_witnesses():
    rows = chain()
    rows[40]["timer"]["value"] = "2:25"
    rows[41]["timer"]["value"] = "1:39"
    later = frame(42, score=(2, 4), timer="1:39")
    later["time_base"] = "1/1"
    rows.append(later)
    c = lifecycle(rows)["chains"][0]
    assert c["status"] == "DEVELOPMENT_LIFECYCLE_CANDIDATE"
    assert c["next_clock_reset_bracket"]["upper_tick"] == 41
    assert c["rejected_clock_prefixes"][0]["witnesses"][0]["tick"] == 40
    assert c["rejected_clock_prefixes"][0]["status"] == "UNKNOWN"
    assert rows[40]["timer"]["value"] == "2:25"


def test_later_clock_support_cannot_cross_acquisition_boundary():
    rows = chain()
    rows[40]["timer"]["value"] = "2:25"
    rows[41]["timer"]["value"] = "1:39"
    later = frame(42, score=(2, 4), timer="1:39", epoch="other")
    later["time_base"] = "1/1"
    rows.append(later)
    c = lifecycle(rows)["chains"][0]
    assert c["status"] == "UNKNOWN"


def test_purchase_reappearance_cannot_create_reversed_next_clock_bracket():
    rows = chain()
    rows[41]["timer"]["value"] = "0:00"
    rows[41]["buy_phase"] = True
    for t in [42, 43]:
        f = frame(t, score=(2, 4), timer="1:39")
        f["time_base"] = "1/1"
        rows.append(f)
    c = lifecycle(rows)["chains"][0]
    b = c["next_clock_reset_bracket"]
    assert b["lower_tick"] == 41 and b["upper_tick"] == 42
    assert c["rejected_clock_prefixes"][0]["reason"] == "preparation_reappeared"


def test_unconfirmed_clock_before_long_observation_hole_is_retained_unknown():
    rows = chain()
    rows[41]["timer"]["value"] = None
    f = frame(42, score=(2, 4), timer="1:38")
    f["time_base"] = "1/1"
    rows.append(f)
    c = lifecycle(rows)["chains"][0]
    assert c["status"] == "UNKNOWN"
    assert c["rejected_clock_prefixes"][0]["reason"] == "clock_support_gap"


def test_clock_reset_far_from_last_countdown_is_not_a_boundary():
    rows = chain()
    for f in rows[38:40]:
        f["timer"]["value"] = "0:15"
    c = lifecycle(rows)["chains"][0]
    assert c["status"] == "UNKNOWN" and c["next_clock_reset_bracket"] is None


def test_countdown_without_banner_at_last_frame_can_bound_reset_but_is_not_onset():
    rows = chain()
    rows[39]["buy_phase"] = False
    c = lifecycle(rows)["chains"][0]
    assert c["next_clock_reset_bracket"]["lower_tick"] == 39
    assert c["purchase_onset_status"] == "UNVERIFIED"


def test_human_digit_disagreement_vetoes_candidate_without_replacing_reader():
    rows = chain()
    p, a = packet_response()
    p["cases"][0]["frame"] = rows[2]
    a["packet_sha256"] = canonical_hash(p)
    observation = review_scores(p, a)["observations"][0]
    rows[2]["human_score_observation"] = observation
    c = lifecycle(rows)["chains"][0]
    assert "human_score_disagrees_with_reader" in c["reasons"]
    assert rows[2]["ally_score"]["value"] == "2"


def test_human_score_from_other_source_cannot_be_used():
    rows = chain()
    p, a = packet_response()
    observation = review_scores(p, a)["observations"][0]
    observation["frame"]["source_sha256"] = "b" * 64
    rows[2]["human_score_observation"] = observation
    with pytest.raises(ValueError, match="bound human"):
        lifecycle(rows)


def test_replayed_epoch_does_not_duplicate_complete_lifecycle():
    rows = chain()
    replay = deepcopy(rows)
    for f in replay:
        f["epoch"] = "replay"
    report = lifecycle(rows + replay)
    assert len(report["chains"]) == 1
    assert report["chains"][0]["status"] == "DEVELOPMENT_LIFECYCLE_CANDIDATE"


def test_unknown_end_cannot_be_promoted_by_purchase_and_next_clock():
    rows = chain()
    rows[3]["result"]["confidence"] = .89
    c = lifecycle(rows)["chains"][0]
    assert c["status"] == "UNKNOWN" and "insufficient_result_support" in c["reasons"]


def test_full_source_identity_and_duplicate_pts_still_rejected():
    rows = chain()
    with pytest.raises(ValueError, match="duplicate"):
        lifecycle(rows + [deepcopy(rows[-1])])
    rows[-1]["source_sha256"] = "e" * 64
    with pytest.raises(ValueError, match="one source"):
        lifecycle(rows)

def test_purchase_next_clock_is_observable_without_an_end_in_window():
    rows = chain()[9:]
    r = lifecycle(rows)
    assert r["chains"] == []
    c = r["purchase_next_clock_observations"][0]
    assert c["status"] == "DEVELOPMENT_PURCHASE_CLOCK_CANDIDATE"
    assert c["next_clock_reset_bracket"]["lower_tick"] == 39
    assert c["internal_Start_tick"] is None and c["formal_events"] == []


@pytest.mark.parametrize("fault", ["epoch", "gap", "decimal", "geometry", "score"])
def test_standalone_purchase_clock_cannot_join_invalid_evidence(fault):
    rows = chain()[9:]
    for f in rows:
        if f["tick"] >= 40:
            if fault == "epoch":
                f["epoch"] = "new"
            if fault == "decimal":
                f["timer"] = {
                    "value": "99.99",
                    "confidence": 0.99,
                    "sources": ["offline_timer_seconds_hundredths_v1"],
                }
            if fault == "geometry":
                f["geometry_consistent"] = False
            if fault == "score":
                f["ally_score"]["value"] = "3"
    if fault == "gap":
        rows = [f for f in rows if f["tick"] != 39]
    if fault == "gap":
        # A missing frame before the reset breaks the source segment, even if
        # an older preparation observation has a numerically plausible clock.
        rows = [f for f in rows if f["tick"] != 37]
    assert not any(
        c["status"] == "DEVELOPMENT_PURCHASE_CLOCK_CANDIDATE"
        for c in lifecycle(rows)["purchase_next_clock_observations"]
    )


def test_round_timeline_suppresses_repeat_without_joining_epochs_or_claiming_gt():
    from scripts.diagnostics.round_lifecycle_evidence import round_timeline
    report = lifecycle(chain())
    other = deepcopy(report)
    other['chains'][0]['end']['score_boundary']['epoch'] = 'other'
    for side in ['before', 'after']:
        other['chains'][0]['end']['score_boundary'][side]['epoch'] = 'other'
    output = round_timeline([report, report, other])
    assert output['duplicate_reports_suppressed'] == 1
    assert len(output['round_candidates']) == 1
    entry = output['round_candidates'][0]
    assert len(entry['alternatives']) == 2
    assert entry['evidence_joined_across_acquisitions'] is False
    assert entry['physical_event_id'] is None and entry['internal_End_tick'] is None
    assert output['formal_events'] == [] and output['approved_gt'] is False


def test_round_timeline_does_not_fuse_two_incomplete_chains():
    from scripts.diagnostics.round_lifecycle_evidence import round_timeline
    report = lifecycle(chain())
    report['chains'][0]['status'] = 'UNKNOWN'
    other = deepcopy(report)
    report['chains'][0]['next_clock_reset_bracket'] = None
    other['chains'][0]['buy_support_interval'] = None
    result = round_timeline([report, other])['round_candidates'][0]
    assert result['status'] == 'UNKNOWN'


def test_round_timeline_retains_conflicting_score_hypotheses_as_unknown():
    from scripts.diagnostics.round_lifecycle_evidence import round_timeline
    report = lifecycle(chain())
    other = deepcopy(report)
    other['chains'][0]['end']['score_after'] = [3, 4]
    result = round_timeline([report, other])['round_candidates'][0]
    assert result['status'] == 'UNKNOWN' and result['score_conflict'] is True


def test_round_timeline_rejects_cross_source_bracket():
    from scripts.diagnostics.round_lifecycle_evidence import round_timeline
    report = lifecycle(chain())
    report['chains'][0]['end']['score_boundary']['after']['source_id'] = 'other'
    with pytest.raises(ValueError):
        round_timeline([report])
