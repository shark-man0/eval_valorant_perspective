import sys
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.diagnostics.diagnose_roster_window import roster_row  # noqa: E402


def test_roster_diagnostic_preserves_unknown_and_distinguishes_roi_confidence():
    observation = {
        "time_sec": 1.25, "primary_state": "unknown",
        "quality": {"hud_confidence": 0.0, "roi_confidence": {"ally_roster": .99}},
        "values": {"ally_alive": None, "enemy_alive": 0, "score_ally": 0},
        "state_flags": [],
    }
    slots = [{"alive": None, "confidence": .99}]
    feature = SimpleNamespace(signals={"ally_liveness_candidates": slots})
    row = roster_row(observation, feature)
    assert row["roster"]["ally"]["accepted_count"] is None
    assert row["roster"]["enemy"]["accepted_count"] == 0
    assert row["roster"]["ally"]["reported_roi_confidence"] == .99
    assert "value_reader_confidence" not in row["roster"]["ally"]
    assert row["roster"]["ally"]["slot_candidates"] == slots
    assert row["score"] == {"ally": 0, "enemy": None}
    assert row["timer"] is None
    assert row["primary_state"] == "unknown"
    assert observation["values"]["ally_alive"] is None
