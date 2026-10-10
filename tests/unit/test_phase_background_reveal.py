import numpy as np
import pytest

from scripts.diagnostics.phase_background_reveal import measure_reveal


def fixture():
    yy, xx = np.mgrid[:60, :90]
    image = np.repeat((80 + xx + yy)[..., None], 3, axis=2).astype(np.uint8)
    return image, [(0, 0, 20, 10), (70, 0, 90, 10), (0, 40, 20, 60)], [
        (30, 15, 60, 20), (30, 30, 60, 35), (40, 22, 50, 28)]


def test_background_fit_excludes_targets_and_reports_occlusion():
    image, context, targets = fixture()
    clean = measure_reveal(image, context, targets)
    other = image.copy()
    other[15:20, 30:60] = 0
    obscured = measure_reveal(other, context, targets)
    assert obscured['coefficients'] == clean['coefficients']
    assert max(row['mean_max_channel_residual'] for row in clean['targets']) < 1e-9
    assert obscured['targets'][0]['mean_max_channel_residual'] > 100
    assert obscured['phase_absent'] is None


def test_uniform_background_is_not_a_semantic_absence_proof():
    _, context, targets = fixture()
    result = measure_reveal(np.full((60, 90, 3), 120, np.uint8), context, targets)
    assert max(row['mean_max_channel_residual'] for row in result['targets']) < 1e-9
    assert not result['runtime_authorized']
    assert not result['scene_continuity_proven']
    assert not result['qualification_created']
    assert result['phase_absent'] is None


def test_context_model_failure_is_visible_in_leave_one_region_out_residual():
    image, context, targets = fixture()
    image[:10, :20] = 255
    result = measure_reveal(image, context, targets)
    assert result['context_leave_one_region_out'][0]['residual']['mean_max_channel_residual'] > 100


@pytest.mark.parametrize('context,targets', [
    ([(0, 0, 20, 10)]*3, [(30, 15, 60, 20)]*3),
    ([(0, 0, 20, 10), (70, 0, 90, 10), (0, 40, 20, 60)],
     [(0, 0, 20, 10), (30, 30, 60, 35), (40, 22, 50, 28)]),
])
def test_overlap_rejected(context, targets):
    with pytest.raises(ValueError):
        measure_reveal(np.zeros((60, 90, 3), np.uint8), context, targets)
