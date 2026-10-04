"""Reproducibility and privacy for the offline timer contract audit."""

import numpy as np

from scripts.diagnose_timer_reader_contract import _render, audit


def test_audit_exercises_runtime_and_returns_only_synthetic_characterization():
    result = audit()
    cases = {row["case"]: row for row in result["cases"]}
    assert result["threshold"] == .90
    assert len(result["reader_source_sha256"]) == 64
    assert cases["complete_timer"]["value"] == "1:14"
    assert cases["complete_timer"]["confidence"] >= .90
    assert cases["complete_timer"]["alphabet_size"] == 10
    assert cases["partial_alphabet"]["alphabet_size"] == 2
    assert set(result) == {"scope", "threshold", "reader_source_sha256", "cases"}
    for row in result["cases"]:
        assert set(row) == {"case", "value", "confidence", "alphabet_size"}


def test_clipping_counterfactual_removes_visible_ink_instead_of_only_padding():
    intact = _render(":")
    clipped = _render(":", clip=14)
    assert not np.any(intact[:, 0])
    assert np.any(clipped[:, 0])
    assert np.array_equal(clipped, intact[:, 14:])
