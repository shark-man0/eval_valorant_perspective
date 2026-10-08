import numpy as np

from valorant_ai_coach.hud.analyzers import RealHudAnalyzer
from valorant_ai_coach.hud.readers import ReaderResult
from valorant_ai_coach.resources import resource_path
from valorant_ai_coach.schema_validation import SchemaValidator


class Reader:
    def __init__(self, rows):
        self.rows = iter(rows)
        self.calls = 0

    def read(self, image, roi):
        self.calls += 1
        return next(self.rows)


def test_shared_score_provenance_is_current_and_independent_of_identity():
    ally = Reader([ReaderResult("0", .95), ReaderResult(None, .99),
                   ReaderResult("1", .8, cross_checked=True)])
    enemy = Reader([ReaderResult("2", .96), ReaderResult("3", .8),
                    ReaderResult("3", .97)])
    analyzer = RealHudAnalyzer(resource_path("config/hud_layout_1080p_v3.json"),
                               readers={"ally_score": ally, "enemy_score": enemy})
    anchors = {name: analyzer.layout.normalized_roi(name)
               for name in ("round_timer", "top_match_bar", "player_hp_armor", "abilities")}
    image = np.full((1080, 1920, 3), 60, np.uint8)
    result = analyzer.observe_frames([image] * 3, anchor_detections=anchors)
    assert [row["values"]["score_ally"] for row in result.observations] == [0, None, 1]
    assert [row["values"]["score_enemy"] for row in result.observations] == [2, None, 3]
    assert [row["quality"]["roi_confidence"]["score_ally_value"]
            for row in result.observations] == [.95, 0, .8]
    assert [row["quality"]["roi_confidence"]["score_enemy_value"]
            for row in result.observations] == [.96, 0, .97]
    for row in result.observations:
        assert row["primary_state"] == "unknown"
        assert row["values"]["player_specific_hud_valid"] is False
        assert row["quality"]["hud_confidence"] == 0
        SchemaValidator().validate_hud_observation(row)
    assert not result.hud_events


def test_missing_or_uncalibrated_score_does_not_borrow_geometry_confidence():
    image = np.full((1080, 1920, 3), 60, np.uint8)
    reader = Reader([ReaderResult("0", .99)])
    analyzer = RealHudAnalyzer(resource_path("config/hud_layout_1080p_v3.json"),
                               readers={"ally_score": reader})
    row = analyzer.observe_frames([image], anchor_detections={}).observations[0]
    assert reader.calls == 0
    assert row["quality"]["roi_confidence"]["score_ally_value"] == 0
    assert row["quality"]["roi_confidence"]["score_enemy_value"] == 0
    assert row["values"]["score_ally"] is None
