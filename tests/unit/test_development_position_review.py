import copy

import pytest

from tests.unit.test_development_trajectory import observation
from valorant_ai_coach.visual.development_position_review import (
    compare_position_review,
    fixed_review_indices,
    observation_fingerprint,
)


def review_case():
    record = observation(0)
    record['appearance'].update(x_roi_norm=.5, y_roi_norm=.5)
    review = {k: record[k] for k in ['source_id', 'acquisition_id', 'frame_index', 'time_sec',
                                    'map_id', 'geometry_version']}
    review.update(status='human_confirmed', label_origin='source_image_review',
                  not_used_for_fitting=True, frame_sha256='frame', reference_sha256='ref',
                  prediction_sha256=observation_fingerprint(record), role='SELF',
                  source_tolerance_px=2, reference_tolerance_px=2,
                  landmark_roi_px=[[0, 0], [90, 0], [0, 90]],
                  landmark_reference_px=[[0, 0], [900, 0], [0, 900]],
                  center_roi_px=[50, 50])
    return record, review


def compare(record, review):
    return compare_position_review(record, review, frame_sha256='frame', reference_sha256='ref',
                                   roi_size_px=(100, 100), reference_bbox=(0, 0, 1000, 1000))


def test_reviewed_residual_has_no_population_bound_or_ownership_promotion():
    record, review = review_case()
    result = compare(record, review)
    assert result['roi_center_difference_px'] == 0
    assert result['map_affine_reference_difference_px'] == pytest.approx(0)
    assert result['affine_extrapolation'] is True
    assert result['roi_difference_annotation_interval_px'] == [0, 2]
    assert result['transferable_error_radius_reference_px'] is None
    assert result['ownership'] == 'UNKNOWN' and result['human_reviewed_role'] == 'SELF'


@pytest.mark.parametrize('key,value', [('status', 'prediction_confirmed'),
    ('label_origin', 'model_output'), ('not_used_for_fitting', False),
    ('source_id', 'other'), ('frame_index', 1), ('time_sec', 1),
    ('frame_sha256', 'other'), ('reference_sha256', 'other'), ('prediction_sha256', 'other'),
    ('source_tolerance_px', float('nan')), ('reference_tolerance_px', -1)])
def test_wrong_scope_or_unconfirmed_labels_rejected(key, value):
    record, review = review_case()
    review[key] = value
    with pytest.raises(ValueError):
        compare(record, review)


def test_changed_prediction_or_collinear_landmarks_rejected():
    record, review = review_case()
    changed = copy.deepcopy(record)
    changed['map_position_norm'] = [.6, .5]
    with pytest.raises(ValueError):
        compare(changed, review)
    review['landmark_roi_px'] = [[0, 0], [1, 1], [2, 2]]
    with pytest.raises(ValueError):
        compare(record, review)


def test_unknown_position_is_counted_not_dropped():
    record, review = review_case()
    record['map_position_norm'] = None
    record['appearance']['x_roi_norm'] = None
    review['prediction_sha256'] = observation_fingerprint(record)
    result = compare(record, review)
    assert result['roi_center_difference_px'] is None
    assert result['map_affine_reference_difference_px'] is None


def test_fixed_review_ordinals_ignore_acceptance():
    assert fixed_review_indices(30) == [0, 14, 29]
    assert fixed_review_indices(1) == [0]
    with pytest.raises(ValueError):
        fixed_review_indices(True)
