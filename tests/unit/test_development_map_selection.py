import numpy as np
import pytest

from tests.unit.test_development_map import bind_case as bind_case
from tests.unit.test_development_map import bounded_opencv as bounded_opencv
from valorant_ai_coach.maps.calibration import CalibrationResult
from valorant_ai_coach.visual.development_map_selection import DevelopmentOutlineMapSelector


def inspect(selector, frame, **kwargs):
    return selector.inspect(frame, [0, 0, 1, 1], source_id='synthetic',
                            source_sha256='a'*64, acquisition_id='test', **kwargs)


def test_unique_real_outline_selects_only_development_candidate(bind_case):
    _, _, frame, _, _ = bind_case
    result = inspect(DevelopmentOutlineMapSelector(), frame)
    assert result['map_id_candidate'] == 'bind'
    assert result['ownership'] == 'UNKNOWN' and result['map_identity_qualified'] is False


def test_empty_and_explicit_geometry_change_do_not_choose_the_nearest_map(bind_case):
    selector = DevelopmentOutlineMapSelector()
    blank = np.zeros((427, 455, 3), np.uint8)
    assert inspect(selector, blank)['map_id_candidate'] is None
    _, _, frame, _, _ = bind_case
    assert inspect(selector, frame, profile={'known_geometry_change': True})[
        'map_id_candidate'] is None


def test_multiple_accepted_maps_are_unknown_even_when_scores_differ(monkeypatch):
    selector = DevelopmentOutlineMapSelector()
    for i, calibrator in enumerate(selector.calibrators.values()):
        result = CalibrationResult('ok', .9-i*.2, None, 'synthetic', ())
        monkeypatch.setattr(calibrator, 'analyze', lambda *a, r=result, **kw: r)
    decision = inspect(selector, np.zeros((200, 300, 3), np.uint8))
    assert decision['map_id_candidate'] is None
    assert decision['reason'] == 'multiple_registered_outlines_match'


def test_unregistered_maps_cannot_be_silently_substituted():
    with pytest.raises(ValueError):
        DevelopmentOutlineMapSelector(('unregistered',))
