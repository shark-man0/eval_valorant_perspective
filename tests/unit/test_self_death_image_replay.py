"""Synthetic cache replay contracts; these tests do not qualify real images."""
import hashlib
import json
from dataclasses import replace

import cv2
import numpy as np
import pytest

from scripts.diagnostics.replay_self_death_images import load_profile, replay_cache
from tests.unit.test_killfeed_subject_reader import HASH, glyph_fixture
from valorant_ai_coach.experimental.self_death_image import (
    SelfDeathImageRecognizer,
    image_runtime_fingerprint,
)
from valorant_ai_coach.video.service import VideoProbeError


def detector():
    reader, base = glyph_fixture()
    header = np.random.default_rng(24).integers(20, 220, (12, 50), dtype=np.uint8)
    model = SelfDeathImageRecognizer(reader.profile, reader.reader, header, (0, 45, 80, 78),
        runtime_fingerprint=image_runtime_fingerprint(), dependencies_fingerprint=HASH,
        native_step_ticks=1)
    return model, base, header


def cache(tmp_path, name, base, header, *, persistent):
    directory = tmp_path/name
    directory.mkdir()
    rows = []
    for tick in range(6):
        image = base.copy()
        if tick or persistent:
            image[50:62, 10:60] = np.repeat(header[:, :, None], 3, axis=2)
        else:
            image[20:40, 170:220] = 0
        image[79, 239] = tick
        path = directory/f'{tick}.png'
        assert cv2.imwrite(str(path), image)
        rows.append({'path': path.name, 'pts_ticks': tick, 'time_base_num': 1,
                     'time_base_den': 60, 'source_epoch': name,
                     'pixel_sha256': hashlib.sha256(image.tobytes()).hexdigest(),
                     'encoded_sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
                     'width': 240, 'height': 80})
    manifest = directory/'manifest.json'
    manifest.write_text(json.dumps({
        'cache_kind': 'lossless_decoded_native_frames_v1_no_recognition',
        'source_sha256': HASH, 'terminal_source_hash_verified': True, 'frames': 6,
        'windows': [{'window': [0, 5/60], 'rows': rows}],
    }), encoding='utf-8')
    return manifest


def test_positive_and_negative_datasets_share_model_identity_without_joining_contexts(tmp_path):
    model, base, header = detector()
    positive = cache(tmp_path, 'positive', base, header, persistent=False)
    negative = cache(tmp_path, 'negative', base, header, persistent=True)
    first = replay_cache(positive, model, HASH)
    second = replay_cache(negative, model, HASH)
    assert first[0]['prediction_count'] == 1
    assert second[0]['prediction_count'] == 0
    rows = [row for windows in (first, second) for window in windows for row in window['rows']]
    assert {r['source']['code_fingerprint'] for r in rows} == {model.code_fingerprint}
    assert {r['source']['profile_fingerprint'] for r in rows} == {model.profile_fingerprint}
    assert {r['source']['segment_id'] for r in rows} == {'positive', 'negative'}
    assert all(window['formal_events'] == [] and window['qualified'] is False
               for window in (*first, *second))


def test_tampered_image_is_an_error_not_a_successful_negative(tmp_path):
    model, base, header = detector()
    manifest = cache(tmp_path, 'tampered', base, header, persistent=False)
    (manifest.parent/'1.png').write_bytes(b'tampered source input')
    with pytest.raises(VideoProbeError, match='decoded asset changed'):
        replay_cache(manifest, model, HASH)


@pytest.mark.parametrize('changed', [
    {'cache_kind': 'saved_recognition_results'},
    {'source_sha256': 'b'*64},
    {'terminal_source_hash_verified': False},
    {'frames': 5},
])
def test_cache_contract_errors_cannot_be_scored_as_valid_replay(tmp_path, changed):
    model, base, header = detector()
    manifest = cache(tmp_path, 'invalid', base, header, persistent=False)
    data = json.loads(manifest.read_text(encoding='utf-8'))
    data.update(changed)
    manifest.write_text(json.dumps(data), encoding='utf-8')
    with pytest.raises(ValueError):
        replay_cache(manifest, model, HASH)


@pytest.mark.parametrize('field,value', [
    ('time_base_num', True), ('time_base_den', 60.0), ('pts_ticks', False), ('width', '240'),
])
def test_cache_integer_types_cannot_be_normalized_into_source_proof(tmp_path, field, value):
    model, base, header = detector()
    manifest = cache(tmp_path, 'bad_coordinate', base, header, persistent=False)
    data = json.loads(manifest.read_text(encoding='utf-8'))
    data['windows'][0]['rows'][0][field] = value
    manifest.write_text(json.dumps(data), encoding='utf-8')
    with pytest.raises(ValueError, match='coordinate'):
        replay_cache(manifest, model, HASH)


def test_runtime_profile_accepts_only_reader_configuration_not_evaluation_labels(tmp_path):
    model, _, header = detector()
    p = replace(model.reader.profile, name_gap_inset=3)
    arrays = {'reference': p.marker_reference, 'gold_mask': p.yellow_mask,
              'weapon_reference': p.weapon_reference, 'headshot_reference': p.headshot_reference,
              'report_header_reference': header}
    arrays.update({f'mask{i}': mask for i, mask in enumerate(p.marker_masks)})
    assets = tmp_path/'assets.npz'
    np.savez_compressed(assets, **arrays)
    data = {'schema_version': 'self_death_image_profile_v1', 'source_sha256': HASH,
            'owner_marker_review_sha256': HASH, 'frame_shape': list(p.frame_shape),
            'search_roi': list(p.search_roi), 'name_y_offsets': list(p.name_y_offsets),
            'assets_file': assets.name,
            'assets_sha256': hashlib.sha256(assets.read_bytes()).hexdigest(),
            'separator_method': p.separator_method, 'name_gap_inset': p.name_gap_inset,
            'marker_feature_kind': p.marker_feature_kind,
            'report_header_search_roi': list(model.report_search_roi)}
    path = tmp_path/'runtime.json'
    path.write_text(json.dumps(data), encoding='utf-8')
    loaded, _, _, _ = load_profile(path)
    assert loaded.fingerprint() == p.fingerprint()
    data['expected_subject_name'] = 'evaluation-only'
    path.write_text(json.dumps(data), encoding='utf-8')
    with pytest.raises(ValueError, match='only'):
        load_profile(path)


def test_v2_presence_assets_round_trip_without_changing_v1_profile_contract(tmp_path):
    from scripts.diagnostics.replay_self_death_images import load_report_presence
    from tests.unit.test_self_death_image_recognizer import setup_with_presence

    model, _, caption = setup_with_presence()
    p, presence = model.reader.profile, model.report_presence_header
    arrays = {'reference': p.marker_reference, 'gold_mask': p.yellow_mask,
              'weapon_reference': p.weapon_reference, 'headshot_reference': p.headshot_reference,
              'report_header_reference': caption,
              'report_presence_reference': presence.reference,
              'report_presence_mask': presence.mask, 'report_presence_regions': presence.regions}
    arrays.update({f'mask{i}': mask for i, mask in enumerate(p.marker_masks)})
    assets = tmp_path/'v2-assets.npz'
    np.savez_compressed(assets, **arrays)
    data = {'schema_version': 'self_death_image_profile_v2', 'source_sha256': HASH,
            'owner_marker_review_sha256': HASH, 'frame_shape': list(p.frame_shape),
            'search_roi': list(p.search_roi), 'name_y_offsets': list(p.name_y_offsets),
            'assets_file': assets.name,
            'assets_sha256': hashlib.sha256(assets.read_bytes()).hexdigest(),
            'separator_method': p.separator_method, 'name_gap_inset': p.name_gap_inset,
            'marker_feature_kind': p.marker_feature_kind,
            'report_header_search_roi': list(model.report_search_roi),
            'report_presence_header': {'input_shape': list(presence.input_shape),
                                      'reference_x': presence.reference_x,
                                      'threshold': presence.threshold}}
    path = tmp_path/'v2.json'
    path.write_text(json.dumps(data), encoding='utf-8')
    loaded, _, _, _ = load_profile(path)
    assert loaded.fingerprint() == p.fingerprint()
    reloaded = load_report_presence(path)
    assert np.array_equal(reloaded.reference, presence.reference)
    assert reloaded.input_shape == presence.input_shape
    # Source-reviewed report presence alone confers no subject/event authority.
    assert reloaded.threshold == .90
    for bad in [.89, True, float('nan'), '0.99']:
        data['report_presence_header']['threshold'] = bad
        path.write_text(json.dumps(data), encoding='utf-8')
        with pytest.raises(ValueError, match='Report header'):
            load_report_presence(path)
    data['report_presence_header']['threshold'] = .90
    data['expected_subject'] = 'not a runtime input'
    path.write_text(json.dumps(data), encoding='utf-8')
    with pytest.raises(ValueError, match='only the versioned'):
        load_report_presence(path)


@pytest.mark.parametrize('text', ['nan:2', '0:inf', '-1:2', '2:1', '1:1', '1:2:3', '0:1/0'])
def test_native_window_parser_rejects_invalid_or_nonfinite_ranges(text):
    import argparse

    from scripts.diagnostics.replay_self_death_images import parse_native_window

    with pytest.raises(argparse.ArgumentTypeError):
        parse_native_window(text)


def test_native_window_parser_preserves_rational_seconds():
    from fractions import Fraction

    from scripts.diagnostics.replay_self_death_images import parse_native_window

    assert parse_native_window('0.1:1/3') == (Fraction(1, 10), Fraction(1, 3))


@pytest.mark.parametrize('ranges', [[(1, 1)], [(2, 1)], [(2, 3), (0, 1)], [(0, 2), (2, 3)]])
def test_invalid_native_window_sequences_fail_before_decoder_work(tmp_path, monkeypatch, ranges):
    from fractions import Fraction

    from scripts.diagnostics.replay_self_death_images import replay_source_windows
    from valorant_ai_coach.video import VideoService

    monkeypatch.setattr(VideoService, 'native_replay',
                        lambda *a, **k: pytest.fail('decoder called'))
    model, _, _ = detector()
    with pytest.raises(ValueError, match='ordered, disjoint'):
        replay_source_windows(tmp_path/'unused.mov',
            [(Fraction(a), Fraction(b)) for a, b in ranges], model, HASH)


def test_native_source_window_replay_matches_png_pixels_without_sampling_or_context_join(tmp_path):
    import shutil
    import subprocess
    from fractions import Fraction

    from scripts.diagnostics.replay_self_death_images import replay_source_windows, sha

    ffmpeg = shutil.which('ffmpeg')
    if ffmpeg is None or shutil.which('ffprobe') is None:
        pytest.skip('FFmpeg/ffprobe required for native source integration')
    model, base, header = detector()
    manifest = cache(tmp_path, 'source-frames', base, header, persistent=False)
    video = tmp_path/'verified-source.mov'
    subprocess.run([ffmpeg, '-v', 'error', '-framerate', '60', '-i',
                    str(manifest.parent/'%d.png'), '-c:v', 'qtrle', '-pix_fmt', 'rgb24',
                    '-video_track_timescale', '60', str(video)],
                   check=True, capture_output=True, timeout=30)
    profile = replace(model.reader.profile, source_sha256=sha(video))
    model = SelfDeathImageRecognizer(profile, model.reader.reader, model.report_reference,
        model.report_search_roi, runtime_fingerprint=image_runtime_fingerprint(),
        dependencies_fingerprint=HASH, native_step_ticks=1)
    data = json.loads(manifest.read_text(encoding='utf-8'))
    data['source_sha256'] = profile.source_sha256
    manifest.write_text(json.dumps(data), encoding='utf-8')
    cached = replay_cache(manifest, model, HASH)
    native, proof = replay_source_windows(video, [(Fraction(0), Fraction(5, 60))], model, HASH,
                                         max_buffer_bytes=240*80*3*3)
    assert cached[0]['prediction_count'] == native[0]['prediction_count'] == 1
    assert native[0]['source_blocked_frames'] == 0
    assert [x['status'] for x in native[0]['rows']] == [x['status'] for x in cached[0]['rows']]
    assert [x['source']['pixel_sha256'] for x in native[0]['rows']] == [
        x['pixel_sha256'] for x in data['windows'][0]['rows']]
    assert [x['source']['pts_ticks'] for x in native[0]['rows']] == list(range(6))
    assert proof['whole_source_verified_frames'] == 6 and proof['source_terminal_verified'] is True
    assert proof['max_buffer_bytes'] == 240*80*3*3
    split, split_proof = replay_source_windows(video, [
        (Fraction(0), Fraction(2, 60)), (Fraction(4, 60), Fraction(5, 60))], model, HASH)
    assert [x['prediction_count'] for x in split] == [0, 0]
    assert [[r['source']['pts_ticks'] for r in w['rows']] for w in split] == [[0, 1, 2], [4, 5]]
    assert (split_proof['native_pts_pixel_sequence_sha256']
            == proof['native_pts_pixel_sequence_sha256'])
    assert all(w['formal_events'] == [] and w['qualified'] is False
               for w in (*cached, *native, *split))
