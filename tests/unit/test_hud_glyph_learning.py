from pathlib import Path

import numpy as np
import pytest

from scripts.diagnostics.hud_glyph_learning import (
    StructureConfig,
    fit_slot_readout,
    fit_structure_ssl,
    fit_supervised_structure,
    load_structure,
    score_digits,
    score_sequence_report,
    slot_candidates,
    supervised_candidates,
)


@pytest.mark.parametrize("kwargs", [dict(height=2000), dict(pooling="unknown"),
                                    dict(pooling="none"), dict(grid=(100, 100))])
def test_invalid_or_unbounded_structure_config_rejected(kwargs):
    with pytest.raises(ValueError):
        StructureConfig(**kwargs)


def test_config_identity_and_untrained_checkpoint_rejected_before_torch(tmp_path: Path):
    a, b = StructureConfig(), StructureConfig(grid=(4, 8))
    assert a.fingerprint == StructureConfig().fingerprint
    assert a.fingerprint != b.fingerprint
    with pytest.raises(ValueError, match="config_mismatch"):
        load_structure(tmp_path/"not_downloaded.pt", "a"*64, b,
                       expected_config_hash=a.fingerprint)


def test_corrupt_structure_and_supervised_weights_rejected_before_optional_load(tmp_path: Path):
    weights = tmp_path/"corrupt.pt"
    weights.write_bytes(b"corrupt checkpoint")
    config = StructureConfig()
    with pytest.raises(ValueError, match="weights"):
        load_structure(weights, "a"*64, config, expected_config_hash=config.fingerprint)
    with pytest.raises(ValueError, match="weights"):
        supervised_candidates(weights, {"config_sha256": config.fingerprint,
                                         "weights_sha256": "a"*64}, config, [])


@pytest.mark.parametrize("limit", [float("nan"), float("inf"), 0, -1, True])
def test_invalid_fit_budget_never_loads_optional_dependencies(tmp_path: Path, limit):
    with pytest.raises(ValueError, match="budget"):
        fit_structure_ssl([np.zeros((4, 4, 3), np.uint8)]*2, StructureConfig(),
                          seed=1, steps=1, batch_size=2, max_seconds=limit,
                          output=tmp_path/"never.pt")
    assert not (tmp_path/"never.pt").exists()


def test_all_ten_digits_and_all_two_digit_grammar_are_preserved():
    for value in range(100):
        digits = score_digits(str(value))
        assert len(digits) == len(str(value))
        assert "".join(map(str, digits)) == str(value)
    for invalid in ["", "01", "000", "100", "1.0", "UNKNOWN", "-1"]:
        with pytest.raises(ValueError):
            score_digits(invalid)


def test_supervised_head_preserves_slot_count_and_physical_group_boundary():
    features = np.eye(5, dtype=np.float32)
    truth = ["0", "9", "10", "11", "12"]
    groups = ["match_a", "match_b", "match_c", "match_d", "match_e"]
    fitted = fit_slot_readout(features, truth, physical_groups=groups,
                              forbidden_groups={"frozen_match"}, alpha=.01)
    assert slot_candidates(fitted, features) == truth
    assert fitted["semantic_qualified"] is False
    assert len(fitted["first"]["weights"][0]) == 10
    assert len(fitted["second"]["weights"][0]) == 10
    with pytest.raises(ValueError, match="leaked"):
        fit_slot_readout(features, truth, physical_groups=groups,
                         forbidden_groups={"match_a"})


def test_absent_two_digit_labels_cannot_create_a_second_digit():
    x = np.eye(2, dtype=np.float32)
    fitted = fit_slot_readout(x, ["1", "2"], physical_groups=["a", "b"],
                              forbidden_groups=set())
    assert fitted["second"] is None
    # An unsupported length prediction is withheld, not completed from rules.
    fitted["length"] = {"weights": [[0., 1.]]*3, "seen": [1]}
    assert slot_candidates(fitted, x) == [None, None]


@pytest.mark.parametrize("label_kind,forbidden", [("READER_PREDICTION", set()),
                                                 ("HUMAN_CONFIRMED", {"frozen_match"})])
def test_supervised_fit_refuses_pseudo_truth_or_frozen_match_before_torch(
    tmp_path: Path, label_kind: str, forbidden: set[str],
):
    with pytest.raises(ValueError, match="leaked_supervised"):
        fit_supervised_structure([np.zeros((4, 4, 3), np.uint8)], ["1"], StructureConfig(),
                                 physical_groups=["frozen_match"], forbidden_groups=forbidden,
                                 label_kind=label_kind, seed=1, steps=1, max_seconds=1,
                                 output=tmp_path/"never.pt")


def test_digit_drop_and_extra_digit_are_not_hidden_as_partial_success():
    report = score_sequence_report(["12", "2", "3", None], ["2", "12", None, "9"])
    assert report["labelled_scores"] == 3
    assert report["digit_drop"] == 1 and report["one_to_two_digit_error"] == 1
    assert report["wrong_complete_candidate"] == 2 and report["UNKNOWN"] == 1
    assert report["two_digit_correct"] == 0 and report["two_digit_truth"] == 1
    assert report["unlabelled_predictions_not_FP"] == 1
    assert report["confusion"][1][11] == 1
    assert report["digits"][6]["support"] == 0
    assert report["digits"][6]["recall_on_labelled_points"] is None
