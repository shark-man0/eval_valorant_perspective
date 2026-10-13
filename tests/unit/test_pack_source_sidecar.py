import pytest

from scripts.e2e.prepare_pack_source import sidecar


def binding(time, name="assets/reference_frames/frame.jpg"):
    return {"source_frame_pts": time, "evidence_path": name}


def test_display_sorted_explicit_ticks_keep_packet_index_without_inferring_cadence():
    report = sidecar([2, 0, 1, 4], "1/60", [binding(.016667)], 60, "source.mp4")
    row = report["entries"][0]
    assert row["presentation_index"] == 1 and row["packet_pts_ticks"] == 1
    assert row["time_base"] == "1/60"
    assert row["decoded_frame_pts_sec"] == .016667
    assert report["max_abs_delta_sec"] == 0
    assert "confidence" not in row


@pytest.mark.parametrize("ticks,base,fps", [([], "1/60", 60), ([0, 0], "1/60", 60),
                                         ([True], "1/60", 60), ([-1, 0], "1/60", 60),
                                         ([0], "0/1", 60), ([0], "1/0", 60),
                                         ([0], "invalid", 60), ([0], "1/60", 0),
                                         ([0], "1/60", float("nan"))])
def test_invalid_or_missing_exact_identity_is_not_fabricated(ticks, base, fps):
    with pytest.raises(ValueError):
        sidecar(ticks, base, [binding(0)], fps, "source.mp4")


@pytest.mark.parametrize("time", [.008, 1, float("nan"), float("inf"), True, None])
def test_witness_cannot_be_moved_to_another_packet_to_pass_the_delta_bound(time):
    with pytest.raises(ValueError):
        sidecar([0, 1, 2], "1/60", [binding(time)], 60, "source.mp4")


def test_empty_and_duplicate_evidence_are_not_silently_accepted():
    with pytest.raises(ValueError):
        sidecar([0], "1/60", [], 60, "source.mp4")
    with pytest.raises(ValueError):
        sidecar([0], "1/60", [binding(0), binding(0)], 60, "source.mp4")
