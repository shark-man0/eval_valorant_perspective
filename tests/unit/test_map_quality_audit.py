
import pytest

from scripts.map_learning.audit_quality import review_metrics, trajectory_flags
from valorant_ai_coach.temporal.evidence import freeze_native_sample


def point(tick, center):
    sample = freeze_native_sample({
        "source_id": "recording", "source_sha256": "a" * 64,
        "acquisition_id": "b" * 64, "native_epoch": "b" * 64,
        "native_pts_tick": tick, "native_time_base": "1/1000",
        "acquired_frame_sha256": "c" * 64, "native_pixel_sha256": "d" * 64,
        "frame_size_px": [1920, 1080],
    })
    return {"sample": sample, "kind": "selected", "map_reference_px": center,
            "map_id": "map", "reference_sha256": "e" * 64, "support_count": tick // 200 + 1}


def test_abnormal_observed_edge_is_flagged_without_fabricating_identity():
    first, second = point(0, [10, 10]), point(200, [90, 10])
    keys = [p["sample"]["sample_sha256"] for p in (first, second)]
    report = {"segments": [[first, second]], "multi_marker_replay": {
        "added_evidence": {keys[0]: {"track": "first"}, keys[1]: {"track": "other"}},
    }}
    flagged = trajectory_flags(report)
    assert len(flagged) == 1
    assert set(flagged[0]["reasons"]) == {"large_reference_displacement", "track_id_changed"}
    report["segments"] = [[first], [second]]
    assert trajectory_flags(report) == []


def test_identity_center_and_map_error_have_separate_provenance_and_denominators():
    row = point(200, [10, 10])
    key = row["sample"]["sample_sha256"]
    report = {"segments": [[row]], "multi_marker_replay": {
        "added_evidence": {key: {"proposal": [key, 5, 5, "WARM"]}},
    }}
    common = {"index": 1, "sample_ref": key, "report_sha256": "f" * 64}
    reviews = [
        {**common, "reviewer": "AI_VISUAL", "role": "UNKNOWN", "center_frame_px": [10, 10]},
        {**common, "reviewer": "HUMAN", "role": "SELF", "center_frame_px": [8, 9],
         "map_reference_px": [10, 12], "map_id": "map", "reference_sha256": "e" * 64},
    ]
    summary = review_metrics(reviews, {1: (report, "f" * 64)})
    assert summary["AI_VISUAL"]["center_errors_px"] == []
    assert summary["AI_VISUAL"]["wrong_selection_fraction_on_known_reviews"] is None
    assert summary["HUMAN"]["center_errors_px"] == [5]
    assert summary["HUMAN"]["map_errors_reference_px"] == [2]
    with pytest.raises(ValueError, match="Duplicate"):
        review_metrics([reviews[0], reviews[0]], {1: (report, "f" * 64)})
    reviews[1]["reference_sha256"] = "1" * 64
    with pytest.raises(ValueError, match="geometry"):
        review_metrics(reviews, {1: (report, "f" * 64)})



def test_withdrawn_observation_is_reviewable_without_becoming_a_current_prediction():
    row = point(0, [10, 10])
    key = row["sample"]["sample_sha256"]
    current = {"segments": []}
    old = {"segments": [[row]], "multi_marker_replay": {
        "added_evidence": {key: {"proposal": [key, 2, 3, "WARM"]}},
    }}
    review = {"index": 1, "sample_ref": key, "report_sha256": "f" * 64,
              "reviewer": "AI_VISUAL", "role": "NON_SELF"}
    result = review_metrics([review], {1: (current, "f" * 64)}, {1: old})
    assert set(result) == {"AI_VISUAL_WITHDRAWN"}
    assert result["AI_VISUAL_WITHDRAWN"]["old_selection_wrong_fraction_on_known_reviews"] == 1
    assert "wrong_selection_fraction_on_known_reviews" not in result["AI_VISUAL_WITHDRAWN"]


def test_canonical_comparison_uses_the_same_instant_and_retains_pixel_uncertainty():
    from scripts.map_learning.compare_canonical_quality import compare

    first = point(0, [10, 10])
    second = point(0, [12, 10])
    # A different acquisition epoch may retain the same source clock and pixels.
    second["sample"] = {**second["sample"], "sample_sha256": "9" * 64}
    sample = second["sample"]
    counts, cases = compare({"segments": [[first]]}, {"segments": [[second]]},
                           {"sample": {"sample": sample}})
    assert counts["coordinate_agreement_8px"] == 1
    assert cases[0]["distance_reference_px"] == 2
    assert cases[0]["identical_full_pixels"]
    sample["native_pixel_sha256"] = "8" * 64
    counts, _ = compare({"segments": [[first]]}, {"segments": [[second]]},
                        {"sample": {"sample": sample}})
    assert counts["pixel_identity_unverified"] == 1
