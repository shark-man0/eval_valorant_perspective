import hashlib
import json
from fractions import Fraction

import cv2
import numpy as np
import pytest

from tests.unit.test_global_round_lifecycle import report
from tests.unit.test_scene_source_binding import inputs as inputs
from valorant_ai_coach.hud import native_scene_evidence
from valorant_ai_coach.hud.analyzers import HudAnalysisError, RealHudAnalyzer
from valorant_ai_coach.hud.global_lifecycle import _scene_attested
from valorant_ai_coach.video.native import NativeSourceFrame


@pytest.fixture
def setup(inputs, tmp_path, monkeypatch):
    layout, profile, asset, data = inputs
    boxes = [[40,50,100,110], [110,50,150,110], [40,160,100,220], [460,160,540,220]]
    data['references'][0]['world_boxes_640x360'] = boxes
    profile.write_text(json.dumps(data))
    frames = []
    native = cv2.imread(str(asset))
    for index in range(2):
        image = np.roll(native, index, axis=1)
        path = tmp_path / f'frame{index}.png'
        assert cv2.imwrite(str(path), image)
        frames.append(NativeSourceFrame(
            path, 1000+index*256, Fraction(1,15360), 'synthetic-native-epoch', '9'*64,
            hashlib.sha256(path.read_bytes()).hexdigest(),
            hashlib.sha256(image.tobytes()).hexdigest(), 1920, 1080,
        ))

    def measure(source, binding, **options):
        for frame in source:
            frame.read_image()
        first, second = source
        linked = {
            'descriptive_scene_link': True, 'runtime_proof_authorized': False,
            'source_pts_ticks': second.pts_ticks, 'previous_source_pts_ticks': first.pts_ticks,
            'source_pixel_sha256': second.pixel_sha256,
            'previous_source_pixel_sha256': first.pixel_sha256,
            'source_epoch': second.source_epoch, 'profile_sha256': binding.profile_sha256,
            'reference_id': 'synthetic-scene',
            'witnesses': [{'region': i, 'previous_box_640x360': box,
                           'fixed_projection_ncc': score}
                          for i, (box, score) in enumerate(zip(
                              boxes, [.97,.91,.95,.96], strict=True))],
        }
        return tuple({
            'source_video_sha256': frame.source_video_sha256,
            'source_epoch': frame.source_epoch, 'source_pts_ticks': frame.pts_ticks,
            'source_time_base': str(frame.time_base), 'source_pts_sec': frame.time_sec,
            'source_pixel_sha256': frame.pixel_sha256, 'scene_measurement': measurement,
        } for frame, measurement in zip(
            source, ({'descriptive_scene_link': False}, linked), strict=True,
        ))

    monkeypatch.setattr(native_scene_evidence, 'observe_native_scene_window', measure)
    analyzer = RealHudAnalyzer(layout, scene_reference_profile_path=profile)
    qualification_data = report()
    qualification_data['profile_fingerprint'] = analyzer._base_fingerprint()
    for key in ('scene_continuity', 'ui_transition'):
        qualification_data['components'][key] = (
            qualification_data['components']['continuity'].copy()
        )
    qpath = layout.with_name('hud_layout.global_qualification.json')
    qpath.write_text(json.dumps(qualification_data))
    analyzer = RealHudAnalyzer(layout, scene_reference_profile_path=profile)
    return analyzer, frames, qpath, qualification_data, asset, measure


def test_qualified_scene_transport_preserves_native_contract_without_ui_or_player_facts(setup):
    analyzer, frames, _, _, _, _ = setup
    rows = analyzer.collect_qualified_native_scene_window(frames, native_step_ticks=256)
    assert rows[0]['system_scene_evidence'] == {}
    proof = rows[1]['system_scene_evidence']['global_scene_continuity']
    assert proof['confidence'] == .91  # Worst score of domains sharing a cell.
    assert proof['witness_cells'] == [[0,0], [1,0], [1,2]]
    assert proof['previous_source_pts_ticks'] == frames[0].pts_ticks
    assert proof['source_pixel_sha256'] == frames[1].pixel_sha256
    assert _scene_attested(proof, {'time_sec': frames[0].time_sec}, analyzer.global_qualification)
    assert set(rows[1]['system_scene_evidence']) == {'global_scene_continuity'}


def test_missing_qualification_blocks_native_evidence(setup):
    analyzer, frames, _, _, _, _ = setup
    analyzer.global_qualification = None
    with pytest.raises(HudAnalysisError, match='global qualification required'):
        analyzer.collect_qualified_native_scene_window(frames, native_step_ticks=256)


def test_legacy_qualification_cannot_authorize_scene_only_route(setup):
    analyzer, frames, path, data, _, _ = setup
    del data['components']['scene_continuity']
    del data['components']['ui_transition']
    path.write_text(json.dumps(data))
    with pytest.raises(ValueError, match='paired scene/UI'):
        analyzer.collect_qualified_native_scene_window(frames, native_step_ticks=256)


@pytest.mark.parametrize('mutated', ['report', 'reference', 'native'])
def test_mutated_terminal_binding_releases_no_buffered_proofs(setup, monkeypatch, mutated):
    analyzer, frames, report_path, _, asset, original = setup

    def changed(*args, **kwargs):
        measured = original(*args, **kwargs)
        path = {'report': report_path, 'reference': asset, 'native': frames[-1].path}[mutated]
        path.write_bytes(path.read_bytes()+b'changed')
        return measured

    monkeypatch.setattr(native_scene_evidence, 'observe_native_scene_window', changed)
    with pytest.raises((ValueError, RuntimeError)):
        analyzer.collect_qualified_native_scene_window(frames, native_step_ticks=256)


def test_scene_provenance_mismatch_is_rejected(setup, monkeypatch):
    analyzer, frames, _, _, _, original = setup

    def changed(*args, **kwargs):
        measured = original(*args, **kwargs)
        measured[1]['scene_measurement']['previous_source_pts_ticks'] += 1
        return measured

    monkeypatch.setattr(native_scene_evidence, 'observe_native_scene_window', changed)
    with pytest.raises(ValueError, match='provenance mismatch'):
        analyzer.collect_qualified_native_scene_window(frames, native_step_ticks=256)


@pytest.mark.parametrize('score', [.89, float('nan'), True])
def test_invalid_domain_cannot_be_hidden_by_another_domain_in_same_cell(
    setup, monkeypatch, score
):
    analyzer, frames, _, _, _, original = setup

    def changed(*args, **kwargs):
        measured = original(*args, **kwargs)
        measured[1]['scene_measurement']['witnesses'][1]['fixed_projection_ncc'] = score
        return measured

    monkeypatch.setattr(native_scene_evidence, 'observe_native_scene_window', changed)
    with pytest.raises(ValueError):
        analyzer.collect_qualified_native_scene_window(frames, native_step_ticks=256)
