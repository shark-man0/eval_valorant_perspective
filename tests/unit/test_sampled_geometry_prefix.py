"""Fail-closed sampled HUD geometry bridge; not real R2 acceptance."""

from dataclasses import replace

import pytest

from tests.unit.test_native_calibration_prefix import case as case
from valorant_ai_coach.hud.native_system_input import (
    sampled_calibration_prefix_provenance,
)
from valorant_ai_coach.hud.unedited_input import UneditedInputContract
from valorant_ai_coach.video.service import FrameSample


def sample(native):
    return FrameSample(
        time_sec=native.time_sec,
        path=native.path,
        source_pts_ticks=native.pts_ticks,
        source_time_base=str(native.time_base),
        source_video_sha256=native.source_video_sha256,
        source_image_sha256=native.encoded_sha256,
    )


def test_sampled_source_prefix_reads_geometry_not_reference_values(case) -> None:
    analyzer, prefix, frames, contract_path, timer_calls, anchor_calls = case
    current = sample(frames[0])
    contract = UneditedInputContract.load(
        contract_path, source_video_sha256="a" * 64,
    )
    cold = analyzer.observe_frames([current], _build_events=False)
    assert cold.calibration.calibrated is False
    assert timer_calls == []
    warm = analyzer.observe_frames(
        [current], _build_events=False,
        _native_calibration_prefix=prefix, _native_input_contract=contract,
    )
    assert warm.calibration.calibrated is True
    assert timer_calls == [61]
    assert 60 in anchor_calls
    assert warm.hud_events == ()
    assert analyzer.last_calibration_diagnostics[
        "native_calibration_prefix"]["scope"] == "sampled_calibration_only"


@pytest.mark.parametrize("wrong", ["source", "future", "timebase", "sample_bytes", "bool_pts"])
def test_sampled_provenance_blocks_unbound_inputs(case, wrong) -> None:
    _, prefix, frames, *_ = case
    current = sample(frames[0])
    if wrong == "source":
        current = replace(current, source_video_sha256="d" * 64)
    elif wrong == "future":
        prefix = replace(prefix, pts_ticks=frames[0].pts_ticks)
    elif wrong == "timebase":
        # A mathematically equal but noncanonical timebase still represents
        # a different supplied source metadata contract.
        current = replace(current, source_time_base="2/30720")
    elif wrong == "sample_bytes":
        current.path.write_bytes(current.path.read_bytes() + b"mutated")
    else:
        # FrameSample itself rejects boolean ticks.
        with pytest.raises(ValueError):
            replace(current, source_pts_ticks=True)
        return
    with pytest.raises((ValueError, RuntimeError)):
        sampled_calibration_prefix_provenance(prefix, current)


def test_ordinary_sampled_run_never_uses_native_prefix(case) -> None:
    analyzer, _, frames, _, timer_calls, anchor_calls = case
    result = analyzer.observe_frames([sample(frames[0])], _build_events=False)
    assert result.calibration.calibrated is False
    assert timer_calls == []
    assert 60 not in anchor_calls


def test_sampled_prefix_requires_explicit_contract(case) -> None:
    analyzer, prefix, frames, *_ = case
    with pytest.raises(ValueError, match="source contract"):
        analyzer.observe_frames(
            [sample(frames[0])], _build_events=False,
            _native_calibration_prefix=prefix,
        )
