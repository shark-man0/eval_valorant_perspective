"""A pilot window is not the original recording's duration."""

from copy import deepcopy

import pytest
from test_development_timeline_application import build

from valorant_ai_coach.temporal.viewer import recording_view_metadata


def test_pilot_original_length_does_not_extend_analysed_seek_range():
    bundle = build()
    bundle.update(coverage_scope="PILOT_ONLY", original_recording_duration_seconds="41021/20")
    before = deepcopy(bundle)
    metadata = recording_view_metadata(bundle)
    assert metadata["duration_float_seconds"] == 3.5
    assert metadata["original_duration_float_seconds"] == 2051.05
    assert metadata["coverage_scope"] == "PILOT_ONLY"
    assert bundle == before
    bundle["original_recording_duration_seconds"] = "1"
    with pytest.raises(ValueError, match="shorter"):
        recording_view_metadata(bundle)
