import numpy as np

from scripts.diagnostics.compare_native_pose_correspondence import compare_pose

BOXES = [[940, 750, 1120, 850], [1080, 600, 1190, 740], [1440, 930, 1600, 1050]]


def image(seed):
    return np.random.default_rng(seed).integers(0, 256, (1080, 1920, 3), dtype=np.uint8)


def test_perfect_pose_match_does_not_authorize_source_or_foreground():
    source = image(25)
    result = compare_pose(source, source.copy(), BOXES)
    assert result['descriptive_geometric_quorum']
    assert result['inlier_count'] == result['candidate_count']
    assert not result['runtime_authorized']
    assert not result['foreground_membership_qualified']


def test_timer_phase_pixels_do_not_influence_declared_pose_regions():
    source = image(26)
    changed = source.copy()
    changed[:360, 672:1248] = 0
    assert compare_pose(source, changed, BOXES) == compare_pose(source, source, BOXES)


def test_unrelated_image_abstains_without_matching_structures():
    result = compare_pose(image(27), image(28), BOXES)
    assert result['candidate_count'] == 0
    assert not result['descriptive_geometric_quorum']
    assert not result['runtime_authorized']
