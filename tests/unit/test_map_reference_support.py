import cv2
import numpy as np
import pytest

from valorant_ai_coach.temporal.map_reference_support import (
    clearly_outside_atlas,
    read_atlas_void_distances,
)
from valorant_ai_coach.temporal.replay import file_sha


def test_atlas_void_rejects_distant_artwork_false_positive_and_keeps_fringe(tmp_path):
    path = tmp_path / "reference.png"
    image = np.zeros((80, 80, 4), dtype=np.uint8)
    image[30:60, 30:60] = [124, 124, 124, 255]
    assert cv2.imwrite(str(path), image)
    sha = file_sha(path)
    distances = read_atlas_void_distances(path, sha)
    assert clearly_outside_atlas(distances, [2, 50])
    assert not clearly_outside_atlas(distances, [22, 50])
    assert not clearly_outside_atlas(distances, [33, 50])
    assert clearly_outside_atlas(distances, [-0.01, 40])
    assert cv2.imwrite(str(path), image[:, :, :3])
    with pytest.raises(ValueError, match="artwork changed"):
        read_atlas_void_distances(path, sha)
    assert read_atlas_void_distances(path, file_sha(path)) is None
