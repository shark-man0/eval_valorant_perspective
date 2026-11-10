import cv2
import numpy as np

from valorant_ai_coach.temporal.screen_cues import (
    barrier_pixels,
    classify_screen_words,
    zone_words,
)


def word(text, confidence=.98, x=0):
    return {"text": text, "confidence": confidence, "native_roi_box": [x, 5, 12, 8]}


def test_unique_match_result_is_not_round_end_or_match_point():
    for text in ["WON", "LOST", "MATCH POINT", "最終ラウンド"]:
        assert not classify_screen_words([word(text)])["match_result"]["visible"]
    assert classify_screen_words([word("VICTORY")])["match_result"]["visible"]
    assert not classify_screen_words([word("DEFEAT", .4)])["match_result"]["visible"]
    assert classify_screen_words([word("購入"), word("フェーズ", x=20)])["buy_caption"]


def test_zone_is_current_display_candidate_without_map_or_owner_truth():
    candidate = zone_words([word("B"), word("ロング", x=20)])[0]
    assert candidate["zone_name"] == "Bロング"
    assert candidate["ownership"] == "UNKNOWN" and candidate["qualified"] is False
    assert zone_words([word("100"), word("クレジット", x=20)]) == []


def test_barrier_measurement_retains_pixels_without_phase_authority():
    hsv = np.full((180, 320, 3), (110, 50, 220), dtype=np.uint8)
    pixels = cv2.cvtColor(hsv, cv2.COLOR_HSV2BGR)
    measurement = barrier_pixels(pixels)
    assert measurement["present"] and not measurement["map_view_supported"]
    assert len(measurement["roi_pixel_sha256"]) == 64
    assert measurement["qualified"] is False
    assert barrier_pixels(np.zeros_like(pixels))["not_detected"]
