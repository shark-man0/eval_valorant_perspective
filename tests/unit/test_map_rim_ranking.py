import cv2
import numpy as np

from valorant_ai_coach.temporal.map_rim_ranking import measure_warm_rims, rank_rim_candidates


def test_warm_rim_prefers_enclosed_portrait_over_filled_ui_and_keeps_unknown_ownership():
    image = np.zeros((160, 1920, 3), dtype=np.uint8)
    image[45:55, 55:60] = (70, 90, 130)
    image[45:55, 60:65] = (110, 170, 75)
    cv2.circle(image, (60, 50), 8, (0, 220, 255), 2)
    cv2.line(image, (67, 50), (75, 50), (0, 220, 255), 2)
    cv2.circle(image, (120, 50), 12, (0, 220, 255), -1)
    pool = [{"center_frame_px": xy} for xy in ([63, 50], [120, 50], [2, 2])]
    rims = measure_warm_rims(image, pool)
    assert rims[0]["features"]["warm_shell_support"] > 0
    assert rims[1]["features"] is None
    assert rims[0]["features"]["direction_tip_frame_px"][0] > 70
    assert rims[2]["features"] is None
    legacy = [{"candidate_index": i, "score": score} for i, score in [(1, 1.), (0, .8), (2, 0.)]]
    revised = rank_rim_candidates(legacy, rims, rim_weight=6, direction_weight=2)
    assert [row["candidate_index"] for row in revised] == [0, 1, 2]
    assert all(row["ownership"] == "UNKNOWN" and not row["qualified"]
               and not row["position_authority"] for row in revised)
