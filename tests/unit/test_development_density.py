from fractions import Fraction

import pytest

from tests.unit.test_shared_match_transport import native_case as native_case
from valorant_ai_coach.temporal import match
from valorant_ai_coach.temporal.replay import read_json


@pytest.mark.parametrize("native_case", ["off_grid_red"], indirect=True)
def test_dense_native_cli_recovers_off_grid_pixels_and_binds_budget(
    tmp_path, monkeypatch, native_case
):
    policy, config = native_case

    class Pixels:
        def __init__(self, path):
            self.fingerprint, self.bindings = "a" * 64, {}

        def inspect(self, image):
            return {
                "signals": [], "context": {}, "map_candidates": [],
                "raw": {"red_observed": bool(image[:, :, 2].mean() > image[:, :, 0].mean())},
            }

    monkeypatch.setattr(match, "ProfileHudObserver", Pixels)
    sparse = tmp_path / "sparse"
    match.run_match(policy_path=policy, source_id="registered-synthetic",
                    reader_config=config, output=sparse, max_refinement_windows=0)
    dense = tmp_path / "dense"
    cache = tmp_path / "cache"
    monkeypatch.setattr("sys.argv", [
        "match", "--policy", str(policy), "--source-id", "registered-synthetic",
        "--reader-config", str(config), "--output", str(dense),
        "--coarse-seconds", "1/5", "--dense-seconds", "1/10",
        "--max-refinement-windows", "0", "--max-refinement-seconds", "900",
        "--checkpoint-dir", str(cache),
    ])
    match.main()
    assert not any(r["measurement"]["raw"]["red_observed"]
                   for r in read_json(sparse / "observations_PRIVATE.json")["records"])
    assert any(r["measurement"]["raw"]["red_observed"]
               for r in read_json(dense / "observations_PRIVATE.json")["records"])
    receipt = read_json(dense / "completion_PRIVATE.json")
    assert receipt["observed_native_points"] == 4
    assert receipt["sampling"]["coarse_seconds"] == "1/5"
    assert receipt["sampling"]["max_refinement_seconds"] == "900"
    with pytest.raises(ValueError, match="binding mismatch"):
        match.run_match(policy_path=policy, source_id="registered-synthetic",
                        reader_config=config, output=tmp_path / "changed", checkpoint_dir=cache,
                        coarse_seconds=Fraction(1, 5), dense_seconds=Fraction(1, 10),
                        max_refinement_windows=0, max_refinement_seconds=Fraction(901))
    full = tmp_path / "full_density"
    full_receipt = match.run_match(
        policy_path=policy, source_id="registered-synthetic", reader_config=config,
        output=full, max_refinement_windows=0, max_refinement_seconds=Fraction(0),
        full_density=True,
    )
    assert full_receipt["sampling"]["full_density"] is True
    assert full_receipt["sampling"]["refinement_budget_applied"] is False
    assert full_receipt["observed_native_points"] == 4
