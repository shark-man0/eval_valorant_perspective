from pathlib import Path, PurePosixPath
from unittest.mock import Mock

import pytest

from scripts.diagnostics.prepare_boundary_review import review_html, source_playback_html


def test_original_source_link_encodes_private_path_without_changing_timebase(tmp_path):
    video = tmp_path / '録画 & #.mp4'
    video.write_bytes(b"original recording")
    page = review_html([], source_playback_html(video, [82, 91]))
    assert video.resolve().as_uri() + "#t=82.000000,91.000000" in page
    assert 'preload="none"' in page
    assert "NOT continuity proof" in page and "No automatic approval" in page
    assert video.read_bytes() == b"original recording"
    assert sorted(tmp_path.iterdir()) == [video]
    assert "<script" not in page


def test_reserved_character_source_uri_without_creating_illegal_windows_filename():
    video = Mock(spec=Path)
    video.expanduser.return_value = video
    video.resolve.return_value = video
    uri = PurePosixPath('/recordings/録画 "<& #.mp4').as_uri()
    video.as_uri.return_value = uri
    page = review_html([], source_playback_html(video, [82, 91]))
    assert uri + "#t=82.000000,91.000000" in page
    assert "%22%3C%26%20%23" in page
    assert "<script" not in page
    video.as_uri.assert_called_once()


@pytest.mark.parametrize("window", [[-1, 2], [2, 2], [3, 2], [0, float("inf")],
                                  [float("nan"), 1]])
def test_playback_rejects_invalid_windows(window):
    with pytest.raises(ValueError, match="playback window"):
        source_playback_html(Path("recording.mp4"), window)


def test_sparse_review_does_not_link_original_source_by_default():
    page = review_html([{"image": "frame.jpg", "source_frame_pts": 4}])
    assert "<video" not in page and "file://" not in page
    assert "Sparse frames do not prove boundaries or continuity" in page
