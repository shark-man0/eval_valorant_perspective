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
