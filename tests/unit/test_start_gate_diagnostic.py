import sys
from copy import deepcopy
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.diagnostics.diagnose_round_lifecycle import start_gate_rows  # noqa: E402
from tests.unit.test_round_lifecycle import sample  # noqa: E402


def test_shared_values_cannot_hypothetically_promote_unknown_identity():
    observations = [sample(0, 0, phase=True, timer=0), sample(1, .2)]
    for row in observations:
        row["primary_state"] = "unknown"
        row["quality"]["hud_confidence"] = 0
        row["quality"]["roi_confidence"] = {
            "round_timer_value": .99, "score_ally_value": .98, "score_enemy_value": .97}
    before = deepcopy(observations)
    diagnostics = [{"frame_index": 0, "signals": {}}, {"frame_index": 1, "signals": {}}]
    result = start_gate_rows(observations, diagnostics)[0]
    assert result["timer_reset_observed"] is True
    assert result["score_pair_continuous"] is True
    assert result["native_start_predicate"] is False
    assert result["minimum_player_hud_confidence"] == 0
    assert result["current_shared_value_confidence"]["round_timer_value"] == .99
    assert result["absence_of_cut_marker_is_not_continuity_proof"] is True
    assert observations == before


def test_diagnostic_uses_native_score_predicate_and_cut_marker():
    observations = [sample(0, 0, phase=True, timer=0), sample(1, .2)]
    observations[1]["values"]["score_enemy"] = None
    diagnostics = [{"frame_index": 0, "signals": {}},
                   {"frame_index": 1, "signals": {"content_jump": True}}]
    result = start_gate_rows(observations, diagnostics)[0]
    assert result["score_pair_continuous"] is False
    assert result["native_start_predicate"] is False
    assert result["native_discontinuity_or_gap"] is True
