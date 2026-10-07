import json

import numpy as np
import pytest

from valorant_ai_coach.hud.analyzers import RealHudAnalyzer
from valorant_ai_coach.hud.readers import ReaderResult
from valorant_ai_coach.resources import resource_path


class Reader:
    def __init__(self, value):
        self.value = value
        self.calls = 0

    def read(self, image, roi):
        self.calls += 1
        return ReaderResult(self.value, 0.96)


def analyzer_for(tmp_path, profile, fallback, readers=None):
    path = tmp_path / "profile.json"
    path.write_text(json.dumps({"schema_version": "1.0", **profile}), encoding="utf-8")
    return RealHudAnalyzer(
        resource_path("config/hud_layout_1080p_v3.json"),
        template_profile_path=path,
        ocr_reader=fallback,
        readers=readers,
    )


def observe(analyzer, signals=None):
    anchors = {
        name: analyzer.layout.normalized_roi(name)
        for name in ("round_timer", "top_match_bar", "player_hp_armor", "abilities")
    }
    return analyzer.observe_frames(
        [np.full((1080, 1920, 3), 60, dtype=np.uint8)],
        anchor_detections=anchors,
        additional_signals=[signals or {}],
    ).observations[0]


def test_hp_reader_does_not_implicitly_enable_other_ocr(tmp_path, live_identity_signals):
    fallback = Reader(8)
    hp = Reader({"hp": 80})
    analyzer = analyzer_for(
        tmp_path, {"ocr_fallback_rois": []}, fallback, {"player_hp_armor": hp}
    )
    result = observe(analyzer, {**live_identity_signals, "live_first_person": True})
    assert result["values"]["hp"] == 80
    assert hp.calls == 1
    assert fallback.calls == 0
    for field in ("round_time_remaining_sec", "score_ally", "score_enemy"):
        assert result["values"][field] is None


def test_explicit_timer_fallback_does_not_enable_scores(tmp_path):
    fallback = Reader("1:30")
    result = observe(analyzer_for(tmp_path, {"ocr_fallback_rois": ["round_timer"]}, fallback))
    assert result["values"]["round_time_remaining_sec"] == 90
    assert result["values"]["score_ally"] is None
    assert result["values"]["score_enemy"] is None
    assert fallback.calls == 1


def test_explicit_reader_overrides_fallback_policy(tmp_path):
    fallback = Reader(8)
    score = Reader(2)
    result = observe(analyzer_for(
        tmp_path, {"ocr_fallback_rois": []}, fallback, {"enemy_score": score}
    ))
    assert result["values"]["score_enemy"] == 2
    assert score.calls == 1
    assert fallback.calls == 0


def test_legacy_profile_preserves_implicit_ocr(tmp_path):
    fallback = Reader(8)
    result = observe(analyzer_for(tmp_path, {}, fallback))
    assert fallback.calls == 3
    assert result["values"]["score_ally"] == 8
    assert result["values"]["score_enemy"] == 8


@pytest.mark.parametrize("policy", [None, True, "round_timer", {}, ["round_timer", "typo"], [1]])
def test_malformed_policy_reports_diagnostic_and_abstains(tmp_path, policy):
    fallback = Reader(8)
    analyzer = analyzer_for(tmp_path, {"ocr_fallback_rois": policy}, fallback)
    result = observe(analyzer)
    assert any("ocr_fallback_rois" in reason for reason in analyzer.profile_diagnostics)
    assert fallback.calls == 0
    assert result["values"]["score_ally"] is None
    assert result["values"]["score_enemy"] is None
