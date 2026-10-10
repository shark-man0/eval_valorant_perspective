import numpy as np
import pytest

from scripts.diagnostics.audit_native_ui_localization import measure_pair


def fixture():
    image = np.random.default_rng(53).integers(0, 256, (120, 180, 3), np.uint8)
    return image, {'phase_box': (60, 30, 120, 60), 'timer_box': (60, 0, 120, 20),
                   'background_boxes': [(0, 30, 40, 60), (130, 30, 170, 60),
                                        (0, 80, 40, 110)]}


def test_timer_change_is_excluded_and_cannot_authorize_phase_disappearance():
    image, options = fixture()
    changed = image.copy()
    changed[:20, 60:120] = 0
    result = measure_pair(image, changed, **options)
    assert result['changed_pixels_inside_phase'] == 0
    assert result['changed_pixels_outside_phase_and_timer'] == 0
    assert not result['phase_absence_authorized']
    assert not result['runtime_continuity_authorized']


def test_blank_phase_has_unavailable_ncc_even_with_identical_backgrounds():
    image, options = fixture()
    changed = image.copy()
    changed[30:60, 60:120] = 120
    result = measure_pair(image, changed, **options)
    assert result['changed_pixels_inside_phase'] > 0
    assert result['changed_pixels_outside_phase_and_timer'] == 0
    assert result['phase_gray_ncc'] is None
    assert all(row['unwarped_ncc'] > .99 for row in result['reviewed_background_measurements'])
    assert not result['phase_absence_authorized']


def test_background_change_is_measured_instead_of_hidden_by_ui_exclusion():
    image, options = fixture()
    other = np.random.default_rng(54).integers(0, 256, image.shape, np.uint8)
    result = measure_pair(image, other, **options)
    assert result['changed_pixels_outside_phase_and_timer'] > 0
    assert all(abs(row['unwarped_ncc']) < .1
               for row in result['reviewed_background_measurements'])
    assert not result['runtime_continuity_authorized']


def test_matching_backgrounds_do_not_hide_a_large_non_ui_foreground_change():
    image, options = fixture()
    other = image.copy()
    other[65:120, 45:180] = np.random.default_rng(61).integers(
        0, 256, (55, 135, 3), np.uint8,
    )
    result = measure_pair(image, other, **options)
    assert all(row['unwarped_ncc'] > .99 for row in result['reviewed_background_measurements'])
    assert result['changed_pixels_outside_phase_and_timer'] > 7000
    assert result['outside_gray_ncc'] < .8
    assert not result['runtime_continuity_authorized']


@pytest.mark.parametrize('field,box', [
    ('timer_box', (60, 30, 120, 50)), ('phase_box', (-1, 0, 10, 10)),
])
def test_invalid_or_overlapping_input_bounds_are_rejected(field, box):
    image, options = fixture()
    options[field] = box
    with pytest.raises(ValueError):
        measure_pair(image, image, **options)
