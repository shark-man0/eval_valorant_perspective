"""Invalid experimental settings must fail before Source or media access."""

from pathlib import Path

import pytest

from valorant_ai_coach.temporal.match import run_match


@pytest.mark.parametrize(
    "flag,tail,reason", [(True, False, "requires offline"), ("yes", True, "Explicit development")]
)
def test_positive_return_configuration_is_checked_before_input_access(tmp_path, flag, tail, reason):
    with pytest.raises(ValueError, match=reason):
        run_match(
            policy_path=Path("/nonexistent/policy.json"),
            source_id="synthetic",
            reader_config=Path("/nonexistent/reader.json"),
            output=tmp_path / "unused",
            current_hp_return_candidate=flag,
            return_display_tail=tail,
        )
    assert not (tmp_path / "unused").exists()
