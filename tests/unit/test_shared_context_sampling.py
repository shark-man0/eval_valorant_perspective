"""Opt-in acquisition context without a second state model or identity seed."""

import json
import sys
from fractions import Fraction

import pytest

from tests.unit.test_shared_match_sampling import point
from tests.unit.test_shared_match_transport import native_case as native_case
from valorant_ai_coach.temporal import application
from valorant_ai_coach.temporal.match import refinement_windows


def test_wider_context_survives_balanced_clipping_and_keeps_global_budget():
    rows = [point(i, signals=["spectator"] if (i // 20) % 2 else ["owner_hud"])
            for i in range(501)]
    default, _ = refinement_windows(rows, max_windows=40, selection_policy="balanced")
    explicit, _ = refinement_windows(rows, max_windows=40, selection_policy="balanced",
                                     padding=Fraction(1))
    assert default == explicit
    wide, deferred = refinement_windows(rows, max_windows=40, selection_policy="balanced",
                                       padding=Fraction(6))
    assert sum(b-a for a, b in wide) <= 240
    assert max(b-a for a, b in wide) > 6
    assert deferred > 0
    assert any(a <= 20 <= b for a, b in wide)
    assert any(a <= 480 <= b for a, b in wide)


@pytest.mark.parametrize("policy", ["chronological", "balanced"])
def test_context_is_clipped_at_origin_and_is_not_selected_without_observed_change(policy):
    constant = [point(i, signals=["owner_hud"]) for i in range(30)]
    assert refinement_windows(constant, max_windows=40, padding=Fraction(6),
                              selection_policy=policy) == ([], 0)
    rows = [point(i, signals=["spectator"] if i < 5 else ["owner_hud"])
            for i in range(20)]
    windows, _ = refinement_windows(rows, max_windows=40, padding=Fraction(6),
                                    selection_policy=policy)
    assert all(a >= 0 for a, _ in windows)
    shifted = [{**r, "sample": {**r["sample"],
                                "native_pts_tick": r["sample"]["native_pts_tick"]+1230,
                                "source_id": "unused", "recorder_agent_id": "unused"}}
               for r in rows]
    translated, _ = refinement_windows(shifted, max_windows=40, padding=Fraction(6),
                                       origin=Fraction(123), selection_policy=policy)
    assert translated == [(a+123, b+123) for a, b in windows]


@pytest.mark.parametrize("padding", [Fraction(-1), Fraction(11), 6, True, float("nan")])
def test_invalid_context_is_rejected(padding):
    with pytest.raises(ValueError, match="padding"):
        refinement_windows([], max_windows=40, padding=padding)


class Pixels:
    def __init__(self, config_path):
        self.fingerprint, self.bindings = "a" * 64, {}

    def inspect(self, image):
        assert image.shape == (64, 96, 3)
        return {"signals": [], "context": {}, "raw": {}, "map_candidates": []}


def test_public_application_generate_and_reuse_preserve_actual_acquisition_settings(
    tmp_path, monkeypatch, native_case,
):
    policy, config = native_case
    output = tmp_path / "generated"
    common = ["application", "generate", "--policy", str(policy),
              "--source-id", "registered-synthetic",
              "--reader-config", str(config), "--observer", __name__ + ":Pixels"]
    monkeypatch.setattr(sys, "argv", common + ["--output", str(output),
                        "--refinement-policy", "balanced", "--refinement-padding-seconds", "6"])
    application.main()
    acquisition = output / "acquisition"
    receipt = json.loads((acquisition / "completion_PRIVATE.json").read_text(encoding="utf-8"))
    assert receipt["sampling"]["refinement_padding_seconds"] == "6"
    assert receipt["sampling"]["selection_policy"] == "balanced"
    assert receipt["sampling"]["balanced_proposal_seconds"] == "14"
    assert receipt["sampling"]["max_refinement_seconds"] == 240
    reused = tmp_path / "reused"
    monkeypatch.setattr(sys, "argv", common + ["--output", str(reused),
                        "--reuse-acquisition", str(acquisition),
                        "--refinement-policy", "balanced", "--refinement-padding-seconds", "6"])
    application.main()
    first = json.loads((output/"application/timeline_PRIVATE.json").read_text(encoding="utf-8"))
    second = json.loads((reused/"application/timeline_PRIVATE.json").read_text(encoding="utf-8"))
    assert first == second
    for setting in [["--refinement-padding-seconds", "1"],
                    ["--refinement-policy", "chronological"]]:
        rejected = tmp_path / ("rejected_" + setting[-1])
        monkeypatch.setattr(sys, "argv", common + ["--output", str(rejected),
                            "--reuse-acquisition", str(acquisition)] + setting)
        with pytest.raises(ValueError, match="Reused acquisition has different refinement"):
            application.main()
        assert not rejected.exists()
