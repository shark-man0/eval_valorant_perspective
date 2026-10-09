import numpy as np

from valorant_ai_coach.hud.analyzers import RealHudAnalyzer, _enrich_temporal_evidence
from valorant_ai_coach.hud.classifier import HudStateClassifier
from valorant_ai_coach.hud.models import empty_hud_values
from valorant_ai_coach.hud.readers import OpenCvHudFeatureReader, ReaderResult
from valorant_ai_coach.resources import resource_path


def test_texture_and_score_change_do_not_prove_result_banner():
    analyzer = RealHudAnalyzer(resource_path("config/hud_layout_1080p_v3.json"))
    frame = np.random.default_rng(42).integers(0, 255, (1080, 1920, 3), dtype=np.uint8)
    feature = OpenCvHudFeatureReader(analyzer.layout).observe(frame)
    assert feature.signals["phase_banner_candidate"] is True
    assert "shared_banner" not in feature.signals
    assert "banner_confidence" not in feature.signals
    values = empty_hud_values()
    values.update(score_ally=0, score_enemy=2)
    previous = {"values": {**values, "score_enemy": 1}}
    signals = dict(feature.signals)
    _enrich_temporal_evidence(signals, values, previous)
    classified = HudStateClassifier().classify(signals)
    assert signals["score_changed"] is True
    assert "round_end_banner" not in classified.state_flags
    assert "buy_phase_banner" not in classified.state_flags


def test_configured_semantic_result_still_promotes_separately():
    values = empty_hud_values()
    values.update(score_ally=0, score_enemy=2)
    signals = {"phase_banner_candidate": True, "phase_banner_candidate_confidence": 1.0,
               "round_end_template": True, "round_end_template_confidence": .96}
    _enrich_temporal_evidence(signals, values, {"values": {**values, "score_enemy": 1}})
    assert signals["shared_banner"] is True
    assert signals["banner_confidence"] == .96
    assert "round_end_banner" in HudStateClassifier().classify(signals).state_flags


def test_native_texture_score_transition_cannot_emit_boundary():
    class Scores:
        def __init__(self, values):
            self.values = iter(values)

        def read(self, image, roi):
            return ReaderResult(next(self.values), .95)

    analyzer = RealHudAnalyzer(resource_path("config/hud_layout_1080p_v3.json"),
                               readers={"ally_score": Scores([0, 0, 0]),
                                        "enemy_score": Scores([1, 2, 2])})
    anchors = {name: analyzer.layout.normalized_roi(name)
               for name in ("round_timer", "top_match_bar", "player_hp_armor", "abilities")}
    image = np.random.default_rng(42).integers(0, 255, (1080, 1920, 3), dtype=np.uint8)
    result = analyzer.observe_frames([image] * 3, anchor_detections=anchors)
    assert all("round_end_banner" not in row["state_flags"] for row in result.observations)
    assert not {"round_start", "round_end"} & {row["type"] for row in result.hud_events}
