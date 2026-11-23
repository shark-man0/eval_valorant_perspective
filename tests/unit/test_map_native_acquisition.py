from fractions import Fraction

import pytest

from scripts.map_learning.acquire_native import _decoded_frames


@pytest.mark.parametrize("clock_label", ["time_base", "time base"])
def test_decoder_log_requires_exact_independent_packet_clock(tmp_path, clock_label):
    log = tmp_path / "decode_PRIVATE.log"
    log.write_text(
        f"config in {clock_label}: 1/1000, frame_rate: 60/1\n"
        "n: 0 pts: 100 pts_time:0.1\n"
        "n: 1 pts: 305 pts_time:0.305\n",
        encoding="utf-8",
    )
    first, next_frame = (tmp_path / f"frame_{n:06d}.png" for n in (1, 2))
    first.touch()
    next_frame.touch()
    assert _decoded_frames(tmp_path, Fraction(1, 1000), [100, 305]) == [
        [100, str(first)], [305, str(next_frame)],
    ]
    with pytest.raises(ValueError, match="packet selection differs"):
        _decoded_frames(tmp_path, Fraction(1, 1000), [100, 300])
