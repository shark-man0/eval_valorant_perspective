import cv2
import numpy as np
import pytest

from valorant_ai_coach.temporal.match_result_pixels import match_result_candidate


def scoreboard(color):
    image = np.zeros((270, 480, 3), dtype=np.uint8)
    for x in range(98, 368, 44):
        cv2.rectangle(image, (x, 38), (x + 25, 99), color, -1)
    cv2.rectangle(image, (67, 38), (77, 57), (170, 255, 0), -1)
    cv2.rectangle(image, (390, 38), (400, 57), (35, 35, 250), -1)
    cv2.rectangle(image, (205, 252), (258, 261), (35, 35, 250), -1)
    return image


@pytest.mark.parametrize("scale", [1, 2, 4])
@pytest.mark.parametrize("color,result", [((187, 215, 119), "VICTORY"), ((35, 35, 240), "DEFEAT")])
def test_result_layout_supports_both_outcomes_at_different_resolutions(scale, color, result):
    image = cv2.resize(scoreboard(color), (480 * scale, 270 * scale))
    candidate = match_result_candidate(image, [])
    assert (candidate["layout"], candidate["outcome_candidate"]) == ("POSTMATCH_SCOREBOARD", result)
    assert candidate["qualified"] is False


def test_large_colored_text_alone_does_not_establish_scoreboard():
    image = scoreboard((187, 215, 119))
    image[237:] = 0
    assert not match_result_candidate(image, [])["visible"]


def test_round_words_and_small_chat_text_are_not_match_results():
    image = np.zeros((270, 480, 3), dtype=np.uint8)
    for word, box in [("WON", [0, 0, 150, 40]), ("VICTORY", [0, 0, 25, 4])]:
        candidate = match_result_candidate(
            image, [{"text": word, "confidence": .95, "native_roi_box": box}]
        )
        assert not candidate["visible"]
    defeat = {"text": "DEFEAT", "confidence": .95, "native_roi_box": [10, 5, 110, 38]}
    assert match_result_candidate(image, [defeat])["layout"] == "CENTRAL_OVERLAY"
