"""Menu/map supplier hints can request inspection without claiming a Round."""

from copy import deepcopy
from fractions import Fraction
from types import SimpleNamespace

import numpy as np
from test_conditional_state_tails import row

from valorant_ai_coach.temporal.expanded_observer import ExpandedDevelopmentObserver
from valorant_ai_coach.temporal.match import frame_observations, refinement_windows


def test_expanded_sampling_summary_retains_supplier_claims_and_new_hints():
    parent = {
        "signals": [],
        "context": {},
        "map_candidates": [],
        "supplier_observations": [
            {
                "producer_fingerprint": "b" * 64,
                "signals": [],
                "map_candidates": [],
                "context": {"stream_kind": "hud_menu_geometry"},
                "raw": {"menu_grid_measurement": {"supported": True}},
            }
        ],
    }
    measured = {
        "signals": [],
        "context": {"stream_kind": "map_generic"},
        "raw": {},
        "map_candidates": [{"ownership": "UNKNOWN"}],
    }
    before = deepcopy(parent)
    observer = ExpandedDevelopmentObserver.__new__(ExpandedDevelopmentObserver)
    observer.parent = SimpleNamespace(inspect=lambda _: parent)
    observer.map = SimpleNamespace(inspect=lambda _: measured, fingerprint="c" * 64)
    result = observer.inspect(np.zeros((2, 2, 3), np.uint8))
    assert parent == before
    assert result["signals"] == []
    assert result["context"]["menu_grid_candidate"] is True
    assert result["map_candidates"] == measured["map_candidates"]
    transported = frame_observations(result, row(0)["sample"], "d" * 64)
    assert len(transported) == 2
    assert all(not r["signals"] for r in transported)


def test_menu_change_requests_dense_observation_without_phase_signal():
    records = [
        {
            "sample": row(t)["sample"],
            "measurement": {"signals": [], "context": {"menu_grid_candidate": value}},
        }
        for t, value in [(0, False), (1, True)]
    ]
    windows, _ = refinement_windows(records, max_windows=40, selection_policy="balanced")
    assert windows == [(Fraction(0), Fraction(2))]
    for item in records:
        item["measurement"]["context"].clear()
    assert refinement_windows(records, max_windows=40)[0] == []
