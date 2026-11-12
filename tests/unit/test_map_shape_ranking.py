import cv2
import numpy as np
import pytest

from valorant_ai_coach.temporal.map_shape_ranking import (
    rank_marker_context,
    rank_white_arrow_shapes,
)


def test_shape_ranking_is_diagnostic_and_does_not_change_pool():
    image = np.zeros((1080, 1920, 3), np.uint8)
    cv2.fillConvexPoly(image, np.array([[95, 105], [100, 93], [105, 105]]), (255, 255, 255))
    pool = [{"center_frame_px": [100, 100]}, {"center_frame_px": [200, 200]}]
    result = rank_white_arrow_shapes(image, pool)
    assert result[0]["candidate_index"] == 0 and result[0]["score"] > 0
    assert all(r["ownership"] == "UNKNOWN" and r["position_authority"] is False for r in result)
    assert pool[0] == {"center_frame_px": [100, 100]}
    with pytest.raises(ValueError, match="outside"):
        rank_white_arrow_shapes(image, [{"center_frame_px": [-1, 20]}])


def test_amber_accent_can_reorder_equal_shapes_without_assigning_owner():
    image = np.zeros((1080, 1920, 3), np.uint8)
    for x in (100, 200):
        cv2.fillConvexPoly(image, np.array([[x - 5, 105], [x, 93], [x + 5, 105]]), (255, 255, 255))
    cv2.circle(image, (208, 100), 3, (0, 190, 255), -1)
    pool = [{"center_frame_px": [100, 100]}, {"center_frame_px": [200, 100]}]
    ranked = rank_marker_context(image, pool)
    assert ranked[0]["candidate_index"] == 1
    assert ranked[0]["accent_score"] > 0
    assert all(
        row["ownership"] == "UNKNOWN"
        and row["qualified"] is False
        and row["position_authority"] is False
        for row in ranked
    )
    assert pool == [{"center_frame_px": [100, 100]}, {"center_frame_px": [200, 100]}]
