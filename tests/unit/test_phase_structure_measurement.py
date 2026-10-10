import numpy as np
import pytest

from scripts.diagnostics.measure_phase_structure import measure_structures

BOXES = [(0, 0, 20, 10), (0, 15, 20, 25), (25, 0, 40, 15)]


def test_blank_and_obscured_inputs_never_authorize_absence():
    for value in (0, 120, 255):
        result = measure_structures(np.full((30, 50, 3), value, np.uint8), BOXES)
        assert all(row['gray_std'] == 0 for row in result['structures'])
        assert result['phase_absent'] is None
        assert result['phase_present'] is None
        assert not result['absence_checked']
        assert not result['runtime_transition_authorized']


def test_local_structures_are_measured_independently():
    image = np.full((30, 50, 3), 120, np.uint8)
    image[4:6, :20] = 255
    result = measure_structures(image, BOXES)
    assert result['structures'][0]['gray_std'] > 0
    assert result['structures'][0]['mean_abs_dy'] > 0
    assert all(row['gray_std'] == 0 for row in result['structures'][1:])


@pytest.mark.parametrize('boxes', [BOXES[:2], [BOXES[0]]*3,
                                  [BOXES[0], (10, 0, 30, 10), BOXES[2]],
                                  [BOXES[0], BOXES[1], (-1, 0, 10, 10)]])
def test_invalid_structure_inputs_fail(boxes):
    with pytest.raises(ValueError):
        measure_structures(np.zeros((30, 50, 3), np.uint8), boxes)
