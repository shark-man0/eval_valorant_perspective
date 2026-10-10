import hashlib
import json
import shutil

import cv2
import numpy as np
import pytest

from tests.unit.test_global_round_lifecycle import report
from valorant_ai_coach.hud.analyzers import RealHudAnalyzer
from valorant_ai_coach.hud.scene_source_binding import SceneSourceBinding
from valorant_ai_coach.resources import resource_path


@pytest.fixture
def inputs(tmp_path):
    native = np.random.default_rng(71).integers(0, 256, (1080, 1920, 3), np.uint8)
    asset = tmp_path / 'scene.png'
    assert cv2.imwrite(str(asset), native)
    data = {
        'schema_version': 1, 'scope': 'diagnostic_reviewed_domains',
        'references': [{
            'id': 'synthetic-scene', 'asset': 'scene.png',
            'asset_sha256': hashlib.sha256(asset.read_bytes()).hexdigest(),
            'source_pixel_sha256': hashlib.sha256(native.tobytes()).hexdigest(),
            'world_boxes_640x360': [[40, 50, 100, 110], [40, 160, 100, 220],
                                  [460, 160, 540, 220]],
            'review_provenance': 'synthetic unit input; no real qualification',
        }],
    }
    path = tmp_path / 'scene.json'
    path.write_text(json.dumps(data))
    layout = tmp_path / 'hud_layout.json'
    layout.write_bytes(resource_path('config/hud_layout_1080p_v3.json').read_bytes())
    return layout, path, asset, data


def test_relative_asset_binding_survives_host_directory_relocation(inputs, tmp_path):
    _, path, asset, _ = inputs
    original = SceneSourceBinding.load(path)
    other = tmp_path / 'relocated'
    other.mkdir()
    shutil.copy(path, other / path.name)
    shutil.copy(asset, other / asset.name)
    assert original.fingerprint() == SceneSourceBinding.load(other / path.name).fingerprint()


@pytest.mark.parametrize('changed', ['profile', 'asset', 'missing_asset', 'escaped_asset'])
def test_bound_input_mutation_is_rejected_before_fingerprint_or_observation(inputs, changed):
    layout, path, asset, _ = inputs
    analyzer = RealHudAnalyzer(layout, scene_reference_profile_path=path)
    if changed == 'profile':
        path.write_bytes(path.read_bytes() + b'\n')
    elif changed == 'asset':
        asset.write_bytes(asset.read_bytes() + b'\n')
    elif changed == 'missing_asset':
        asset.unlink()
    else:
        outside = asset.parent.parent / 'escaped-scene.png'
        shutil.copy(asset, outside)
        asset.unlink()
        asset.symlink_to(outside)
    with pytest.raises((ValueError, OSError)):
        analyzer.fingerprint()
    with pytest.raises((ValueError, OSError)):
        analyzer.observe_frames([])


def test_old_hud_only_qualification_cannot_authorize_configured_scene_assets(inputs):
    layout, path, _, _ = inputs
    hud = RealHudAnalyzer(layout)
    data = report()
    data['profile_fingerprint'] = hud.fingerprint()
    qualification = layout.with_name('hud_layout.global_qualification.json')
    qualification.write_text(json.dumps(data))
    assert RealHudAnalyzer(layout).global_qualification is not None
    scene = RealHudAnalyzer(layout, scene_reference_profile_path=path)
    assert scene.global_qualification is None
    assert scene._base_fingerprint() != hud._base_fingerprint()


def test_profile_binding_does_not_install_producer_or_create_qualification(inputs):
    layout, path, _, _ = inputs
    analyzer = RealHudAnalyzer(layout, scene_reference_profile_path=path)
    assert analyzer.global_qualification is None
    data = report()
    data['profile_fingerprint'] = analyzer.fingerprint()
    data['components']['scene_continuity'] = data['components']['continuity'].copy()
    data['components']['ui_transition'] = data['components']['continuity'].copy()
    layout.with_name('hud_layout.global_qualification.json').write_text(json.dumps(data))
    analyzer = RealHudAnalyzer(layout, scene_reference_profile_path=path)
    assert analyzer.global_qualification is not None
    assert any('producer is not installed' in note for note in analyzer.profile_diagnostics)


def test_changed_review_provenance_invalidates_previously_bound_report(inputs):
    layout, path, _, raw = inputs
    analyzer = RealHudAnalyzer(layout, scene_reference_profile_path=path)
    data = report()
    data['profile_fingerprint'] = analyzer.fingerprint()
    layout.with_name('hud_layout.global_qualification.json').write_text(json.dumps(data))
    raw['references'][0]['review_provenance'] += '; amended review'
    path.write_text(json.dumps(raw))
    assert RealHudAnalyzer(layout, scene_reference_profile_path=path).global_qualification is None


def test_decoded_reference_pixel_binding_is_required(inputs):
    _, path, _, raw = inputs
    raw['references'][0]['source_pixel_sha256'] = '0' * 64
    path.write_text(json.dumps(raw))
    with pytest.raises(ValueError, match='pixels changed'):
        SceneSourceBinding.load(path)
