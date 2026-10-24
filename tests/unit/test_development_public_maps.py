import hashlib
import json

import cv2
import numpy as np
import pytest

from valorant_ai_coach.maps.outline_calibration import OutlineMinimapCalibrator
from valorant_ai_coach.maps.registry import MapRegistry
from valorant_ai_coach.visual.development_map import development_registry


@pytest.mark.parametrize('map_id,site_count', [('lotus', 3), ('corrode', 2), ('summit', 2)])
def test_public_shaded_footprints_are_isolated_and_content_bound(map_id, site_count):
    registry = development_registry(map_id)
    definition = registry.load(map_id)
    provenance = json.loads((registry.root/'provenance.json').read_text(encoding='utf-8'))
    assert registry.registry['maps'][map_id]['production'] is False
    assert definition.data['observed_client_builds'] == []
    assert len(definition.data['zones']) == len(definition.data['sites']) == site_count
    assert definition.callouts['records'] == {} and definition.data['topology_edges'] == []
    assert hashlib.sha256(definition.reference_asset.read_bytes()).hexdigest() == (
        provenance['reference_sha256'])
    floor = registry.root/provenance['visible_floor_asset']
    assert hashlib.sha256(floor.read_bytes()).hexdigest() == provenance['visible_floor_sha256']
    assert provenance['metadata_source'].startswith('https://valorant-api.com/v1/maps/')
    if map_id == 'summit':
        production = MapRegistry()
        assert production.registry['maps']['summit']['production'] is True
        assert production.load('summit').geometry_version != definition.geometry_version
    else:
        with pytest.raises(KeyError):
            MapRegistry().select(manual_map_id=map_id)


@pytest.mark.parametrize('map_id', ['lotus', 'corrode', 'summit'])
def test_synthetic_public_map_alignment_is_distinct_from_real_video_precision(map_id):
    old_threads = cv2.getNumThreads()
    cv2.setNumThreads(1)
    try:
        definition = development_registry(map_id).load(map_id)
        reference = cv2.imread(str(definition.reference_asset))
        frame = np.zeros((480, 480, 3), np.uint8)
        frame[20:460, 20:460] = cv2.resize(reference, (440, 440), interpolation=cv2.INTER_AREA)
        result = OutlineMinimapCalibrator().analyze(frame, [0, 0, 1, 1], definition)
        assert result.status == 'ok'
        assert 'client_build_unverified' in result.diagnostics
        rejected = OutlineMinimapCalibrator().analyze(
            frame, [0, 0, 1, 1], definition, profile={'known_geometry_change': True})
        assert rejected.status == 'calibration_required'
    finally:
        cv2.setNumThreads(old_threads)
