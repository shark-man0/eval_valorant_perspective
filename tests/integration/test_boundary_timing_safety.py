"""Timing tolerance cannot authorize an event rejected by production evidence gates."""
import pytest

from scripts.e2e.practical_accuracy import evaluate_matched_boundary
from tests.unit.test_unedited_ui_end import fixture, replay


@pytest.mark.parametrize('failure', ['unqualified', 'source_break'])
def test_time_tolerance_does_not_restore_rejected_end(tmp_path, failure):
    rows, tracker = fixture(tmp_path, enabled=failure != 'unqualified')
    if failure == 'source_break':
        # Break after the score update and before independent result corroboration.
        rows[30]['system_evidence']['content_jump'] = True
    decisions = replay(rows, tracker)
    assert not any(d.kind == 'round_end' for d in decisions)
    result = evaluate_matched_boundary(None, truth_kind='round_end', truth_time_sec=.44)
    assert result['status'] == 'FAIL' and result['reason'] == 'boundary_unavailable'
