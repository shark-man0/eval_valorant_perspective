from valorant_ai_coach.temporal.map_correspondence import correspondence_review


def test_provisional_highlight_keeps_same_appearance_alternatives_unowned():
    pool = [
        {"x": 1, "appearance_evidence": {"reference_fingerprint": "a"}},
        {"appearance_evidence": {"reference_fingerprint": "a"}},
        {"appearance_evidence": {"reference_fingerprint": "b"}},
    ]
    review = correspondence_review(pool, [], [{"candidate": pool[0]}], ["current_view"])
    assert review["contract"] == "development_map_correspondence_review_v2"
    assert review["provisional_highlight_indices"] == [0]
    assert review["same_appearance_competitor_indices"] == {"0": [1]}
    assert review["provisional_highlight_ambiguous"] is True
    assert review["strict_recorder_marker_count"] == 0
    assert review["ownership"] == "UNKNOWN"


def test_missing_appearance_does_not_invent_competitor_or_owner():
    pool = [{"marker_id": "unknown"}, {"marker_id": "other"}]
    review = correspondence_review(pool, [], [{"candidate": pool[0]}], [])
    assert review["same_appearance_competitor_indices"] == {"0": []}
    assert review["provisional_highlight_ambiguous"] is False
    assert review["strict_recorder_marker_count"] == 0


def test_archived_ui_features_rank_disjoint_same_appearance_without_ownership():
    pool = [
        {
            "appearance_evidence": {
                "reference_fingerprint": "same",
                "center_roi_px": [0.0, 0.0],
                "size_roi_px": [17.0, 17.0],
                "support_similarity": 0.81,
            }
        },
        {
            "appearance_evidence": {
                "reference_fingerprint": "same",
                "center_roi_px": [50.0, 0.0],
                "size_roi_px": [17.0, 17.0],
                "support_similarity": 0.96,
            }
        },
    ]
    review = correspondence_review(
        pool,
        [],
        [{"candidate": pool[0]}],
        [],
        ui_rows=[{"candidate_index": 0, "score": 1.2}, {"candidate_index": 1, "score": 0.2}],
    )
    ranking = review["independent_ui_rankings"]["0"]
    assert ranking["ui_ranked_indices"] == [0, 1]
    assert ranking["highlight_over_best_competitor_margin"] == 1.0
    assert ranking["competitors"][0]["footprints_disjoint"] is True
    assert ranking["ranking_is_owner_evidence"] is False
    assert review["strict_recorder_marker_count"] == 0


def test_missing_ui_score_abstains_from_ranking():
    pool = [
        {"appearance_evidence": {"reference_fingerprint": "same"}},
        {"appearance_evidence": {"reference_fingerprint": "same"}},
    ]
    review = correspondence_review(
        pool,
        [],
        [{"candidate": pool[0]}],
        [],
        ui_rows=[{"candidate_index": 0, "score": 1.2}],
    )
    ranking = review["independent_ui_rankings"]["0"]
    assert ranking["ui_ranked_indices"] == []
    assert ranking["highlight_over_best_competitor_margin"] is None
    assert ranking["competitors"][0]["footprints_disjoint"] is None
