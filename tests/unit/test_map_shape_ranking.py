import cv2
import numpy as np
import pytest

from valorant_ai_coach.temporal.map_shape_ranking import rank_white_arrow_shapes


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
