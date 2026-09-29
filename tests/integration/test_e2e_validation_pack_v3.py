"""Run the supplied corpus checks, never treating the oracle as runtime output."""

import os
import subprocess
import sys
from pathlib import Path

import pytest

PROJECT = Path(__file__).resolve().parents[2]
PACK = Path(os.environ.get("VALORANT_E2E_PACK", PROJECT.parent / "valorant_e2e_validation_pack_v3"))


def test_validation_corpus_and_production_leakage() -> None:
    """This checks the evaluator/fixtures, NOT real-video perception accuracy."""
    validator = PACK / "tests" / "validate_pack.py"
    if not validator.is_file():
        pytest.skip("Set VALORANT_E2E_PACK to the separately supplied validation pack")
    result = subprocess.run(
        [sys.executable, str(validator), "--project-root", str(PROJECT / "src")],
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "e2e validation pack v3: OK" in result.stdout


def test_production_has_no_validation_corpus_references() -> None:
    """Keep evaluation-only labels and time sidecars out of production modules."""
    forbidden = (
        "ground_truth",
        "expected_event",
        "frame_pts_sidecar",
        "e2e_assertions",
        "valorant_e2e_validation_pack",
        "reference timestamp",
    )
    hits = []
    for directory in ("src", "runtime", "app"):
        for path in (PROJECT / directory).rglob("*.py"):
            content = path.read_text(encoding="utf-8").casefold()
            hits.extend(f"{path.relative_to(PROJECT)}: {token}" for token in forbidden
                        if token in content)
    assert not hits, "Evaluation data leaked into production:\n" + "\n".join(hits)
