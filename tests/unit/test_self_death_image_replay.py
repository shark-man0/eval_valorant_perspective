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


@pytest.mark.parametrize('count', ['missing', None, True, '6', -1, 5, 7])
def test_invalid_total_count_rejects_before_any_image_recognition(tmp_path, monkeypatch, count):
    model, base, header = detector()
    manifest = cache(tmp_path, 'bad-count', base, header, persistent=False)
    data = json.loads(manifest.read_text(encoding='utf-8'))
    if count == 'missing':
        del data['frames']
    else:
        data['frames'] = count
    manifest.write_text(json.dumps(data), encoding='utf-8')
    monkeypatch.setattr('scripts.diagnostics.replay_self_death_images._observe_native_frames',
                        lambda *a, **k: pytest.fail('recognition began before count validation'))
    with pytest.raises(ValueError, match='cache frame count mismatch'):
        replay_cache(manifest, model, HASH)


@pytest.mark.parametrize('groups', [None, {}, [None], [{'rows': None}]])
def test_invalid_window_rows_reject_before_any_image_recognition(tmp_path, monkeypatch, groups):
    model, base, header = detector()
    manifest = cache(tmp_path, 'bad-groups', base, header, persistent=False)
    data = json.loads(manifest.read_text(encoding='utf-8'))
    data['windows'] = groups
    manifest.write_text(json.dumps(data), encoding='utf-8')
    monkeypatch.setattr('scripts.diagnostics.replay_self_death_images._observe_native_frames',
                        lambda *a, **k: pytest.fail('recognition began before row validation'))
    with pytest.raises(ValueError, match='cache windows'):
        replay_cache(manifest, model, HASH)


def test_cli_bad_count_rejects_before_profile_source_or_dependency_work(tmp_path, monkeypatch):
    from scripts.diagnostics.replay_self_death_images import main

    manifest = tmp_path/'missing-count.json'
    manifest.write_text(json.dumps({'windows': [{'rows': []}]}), encoding='utf-8')
    arguments = ['replay', '--cache-manifest', str(manifest), '--native-step-ticks', '1']
    for name in ('source', 'profile', 'owner-review', 'tesseract', 'engine-binary', 'tessdata',
                 'output'):
        arguments.extend(['--'+name, str(tmp_path/('unused-'+name))])
    monkeypatch.setattr('sys.argv', arguments)
    monkeypatch.setattr('scripts.diagnostics.replay_self_death_images.load_profile',
                        lambda *a: pytest.fail('profile work began before cache count validation'))
    monkeypatch.setattr('scripts.diagnostics.replay_self_death_images.sha',
                        lambda *a: pytest.fail('hashing began before cache count validation'))
    with pytest.raises(ValueError, match='cache frame count mismatch'):
        main()


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


@pytest.mark.parametrize('mode', ['whole_source', 'bounded'])
def test_native_source_window_replay_matches_png_pixels_without_sampling_or_context_join(
    tmp_path, monkeypatch, mode,
):
    import shutil
    import subprocess
    from fractions import Fraction

    from scripts.diagnostics.replay_self_death_images import (
        replay_bounded_source_windows,
        replay_source_windows,
        sha,
    )

    ffmpeg = shutil.which('ffmpeg')
    if ffmpeg is None or shutil.which('ffprobe') is None:
        pytest.skip('FFmpeg/ffprobe required for native source integration')
    model, base, header = detector()
    manifest = cache(tmp_path, 'source-frames', base, header, persistent=False)
    if mode == 'bounded':
        # Interior endpoints must have probe coverage after the requested
        # interval; the final two physical frames are deliberately unrecognized.
        for tick in (6, 7):
            image = base.copy()
            image[79, 239] = tick
            assert cv2.imwrite(str(manifest.parent/f'{tick}.png'), image)
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
    run = replay_source_windows if mode == 'whole_source' else replay_bounded_source_windows
    options = ({'max_buffer_bytes': 240*80*3*3} if mode == 'whole_source'
               else {'max_png_bytes': 240*80*3*3})
    if mode == 'bounded':
        from scripts.diagnostics import replay_self_death_images as replay_module
        from valorant_ai_coach.video import VideoService

        monkeypatch.setattr(VideoService, 'native_replay',
                            lambda *a, **k: pytest.fail('whole-source decoder called'))
        native_paths = []
        original_observe = replay_module._observe_native_frames

        def capture_paths(frames, *args):
            assert all(not p.exists() for p in native_paths)
            native_paths.extend(frame.path for frame in frames)
            return original_observe(frames, *args)

        monkeypatch.setattr(replay_module, '_observe_native_frames', capture_paths)
    native, proof = run(video, [(Fraction(0), Fraction(5, 60))], model, HASH, **options)
    assert cached[0]['prediction_count'] == native[0]['prediction_count'] == 1
    assert native[0]['source_blocked_frames'] == 0
    assert [x['status'] for x in native[0]['rows']] == [x['status'] for x in cached[0]['rows']]
    assert [x['source']['pixel_sha256'] for x in native[0]['rows']] == [
        x['pixel_sha256'] for x in data['windows'][0]['rows']]
    assert [x['source']['pts_ticks'] for x in native[0]['rows']] == list(range(6))
    assert proof['source_terminal_verified'] is True
    if mode == 'whole_source':
        assert proof['whole_source_verified_frames'] == 6
        assert proof['max_buffer_bytes'] == 240*80*3*3
    else:
        assert proof['verified_native_frames'] == 6
        assert proof['max_window_png_bytes'] == 240*80*3*3
        assert proof['peak_retained_png_bytes'] <= 240*80*3*3
        assert proof['whole_source_pts_pixels_verified'] is False
        assert proof['cross_window_continuity_asserted'] is False
    split, split_proof = run(video, [
        (Fraction(0), Fraction(2, 60)), (Fraction(4, 60), Fraction(5, 60))], model, HASH)
    assert [x['prediction_count'] for x in split] == [0, 0]
    assert [[r['source']['pts_ticks'] for r in w['rows']] for w in split] == [[0, 1, 2], [4, 5]]
    if mode == 'whole_source':
        assert (split_proof['native_pts_pixel_sequence_sha256']
                == proof['native_pts_pixel_sequence_sha256'])
    else:
        assert split_proof['verified_native_frames'] == 5
        assert split[0]['rows'][0]['source']['segment_id'] != (
            split[1]['rows'][0]['source']['segment_id'])
        # Distinct rational limits can round to the same float. The excluded
        # origin frame must not reach recognition even in that case.
        epsilon = Fraction(1, 10**30)
        for begin, expected_ticks in ((epsilon, list(range(1, 6))),
                                      (Fraction(1, 60)+epsilon, list(range(2, 6)))):
            exact, exact_proof = run(video, [(begin, Fraction(5, 60))], model, HASH)
            assert [r['source']['pts_ticks'] for r in exact[0]['rows']] == expected_ticks
            assert exact_proof['windows'][0]['processed_native_frames'] == len(expected_ticks)
        with pytest.raises(VideoProbeError, match='PNG storage budget'):
            run(video, [(Fraction(0), Fraction(5, 60))], model, HASH, max_png_bytes=1)
        assert all(not p.exists() for p in native_paths)

        def change_source(frames, *args):
            output = capture_paths(frames, *args)
            with video.open('ab') as stream:
                stream.write(b'changed original source during recognition')
            return output

        monkeypatch.setattr(replay_module, '_observe_native_frames', change_source)
        with pytest.raises(VideoProbeError, match='source video changed during consumption'):
            run(video, [(Fraction(0), Fraction(5, 60))], model, HASH)
        assert all(not p.exists() for p in native_paths)
    assert all(w['formal_events'] == [] and w['qualified'] is False
               for w in (*cached, *native, *split))


@pytest.mark.parametrize('ranges,budget', [
    ([], 100), ([(1, 1)], 100), ([(2, 1)], 100), ([(0, 2), (1, 3)], 100),
    ([(2, 3), (0, 1)], 100), ([(0, 2), (2, 3)], 100),
    ([(0, 1)], 0), ([(0, 1)], True), ([(0, 1)], float('inf')),
])
def test_invalid_bounded_windows_fail_before_decoder_work(tmp_path, monkeypatch, ranges, budget):
    from fractions import Fraction

    from scripts.diagnostics.replay_self_death_images import replay_bounded_source_windows
    from valorant_ai_coach.video import VideoService

    model, _, _ = detector()
    monkeypatch.setattr(VideoService, 'native_window',
                        lambda *a, **k: pytest.fail('decoder called'))
    with pytest.raises(ValueError, match='bounded native windows'):
        replay_bounded_source_windows(tmp_path/'unused.mov',
            [(Fraction(a), Fraction(b)) for a, b in ranges], model, HASH, max_png_bytes=budget)


def test_cli_overlapping_bounded_windows_reject_before_profile_or_source_hashing(
    tmp_path, monkeypatch,
):
    from scripts.diagnostics.replay_self_death_images import main

    arguments = ['replay', '--bounded-native-window', '0:2',
                 '--bounded-native-window', '1:3', '--native-step-ticks', '1']
    for name in ('source', 'profile', 'owner-review', 'tesseract', 'engine-binary', 'tessdata',
                 'output'):
        arguments.extend(['--'+name, str(tmp_path/('unused-'+name))])
    monkeypatch.setattr('sys.argv', arguments)
    monkeypatch.setattr('scripts.diagnostics.replay_self_death_images.load_profile',
                        lambda *a: pytest.fail('profile work began before window validation'))
    monkeypatch.setattr('scripts.diagnostics.replay_self_death_images.sha',
                        lambda *a: pytest.fail('hashing began before window validation'))
    with pytest.raises(ValueError, match='bounded native windows'):
        main()


def bank_profile_file(tmp_path, extras):
    model, _, header = detector()
    p = model.reader.profile
    arrays = {'reference': p.marker_reference, 'gold_mask': p.yellow_mask,
              'weapon_reference': p.weapon_reference, 'headshot_reference': p.headshot_reference,
              'report_header_reference': header, **extras}
    arrays.update({f'mask{i}': mask for i, mask in enumerate(p.marker_masks)})
    assets = tmp_path/'bank.npz'
    np.savez_compressed(assets, **arrays)
    data = {'schema_version': 'self_death_image_profile_v1', 'source_sha256': HASH,
            'owner_marker_review_sha256': HASH, 'frame_shape': list(p.frame_shape),
            'search_roi': list(p.search_roi), 'name_y_offsets': list(p.name_y_offsets),
            'assets_file': assets.name,
            'assets_sha256': hashlib.sha256(assets.read_bytes()).hexdigest(),
            'separator_method': p.separator_method, 'name_gap_inset': p.name_gap_inset,
            'marker_feature_kind': p.marker_feature_kind,
            'report_header_search_roi': list(model.report_search_roi)}
    path = tmp_path/'bank.json'
    path.write_text(json.dumps(data), encoding='utf-8')
    return path, p


def test_profile_preserves_legacy_and_numbered_weapon_references_in_fingerprint(tmp_path):
    arrays = [np.random.default_rng(seed).integers(20, 220, (12, 20), dtype=np.uint8)
              for seed in [125, 126, 127]]
    path, original = bank_profile_file(tmp_path, {
        'additional_weapon_reference': arrays[0],
        'additional_weapon_reference_000': arrays[1],
        'additional_weapon_reference_001': arrays[2],
    })
    loaded, _, _, _ = load_profile(path)
    assert len(loaded.additional_weapon_references) == 3
    assert all(np.array_equal(a, b)
               for a, b in zip(loaded.additional_weapon_references, arrays, strict=True))
    assert loaded.fingerprint() == replace(original,
        additional_weapon_references=tuple(arrays)).fingerprint()
    assert loaded.fingerprint() != original.fingerprint()
    assert all(not array.flags.writeable for array in loaded.additional_weapon_references)


@pytest.mark.parametrize('key', ['additional_weapon_reference_001',
                                'additional_weapon_reference_1',
                                'additional_weapon_reference_expected_subject', 'unknown_asset'])
def test_profile_rejects_incomplete_or_noncanonical_bank_names(tmp_path, key):
    array = np.random.default_rng(128).integers(20, 220, (12, 20), dtype=np.uint8)
    path, _ = bank_profile_file(tmp_path, {key: array})
    with pytest.raises(ValueError):
        load_profile(path)


def v3_profile_file(tmp_path):
    from tests.unit.test_self_death_image_recognizer import setup_with_presence

    original, _, _ = setup_with_presence()
    presence = original.report_presence_header
    path, _ = bank_profile_file(tmp_path, {})
    data = json.loads(path.read_text(encoding='utf-8'))
    assets = path.parent/data['assets_file']
    with np.load(assets, allow_pickle=False) as source:
        arrays = {k: source[k].copy() for k in source.files}
    arrays.update(report_presence_reference=presence.reference,
                  report_presence_mask=presence.mask, report_presence_regions=presence.regions)
    np.savez_compressed(assets, **arrays)
    data.update(schema_version='self_death_image_profile_v3',
        report_header_search_roi=[0, 0, 80, 78], report_presence_search_roi=[0, 45, 80, 78],
        report_presence_header={'input_shape': list(presence.input_shape),
                                'reference_x': presence.reference_x, 'threshold': .90},
        assets_sha256=hashlib.sha256(assets.read_bytes()).hexdigest())
    path.write_text(json.dumps(data), encoding='utf-8')
    return path


def test_v3_separate_presence_roi_survives_loader_and_native_window_clone(tmp_path):
    from scripts.diagnostics.replay_self_death_images import (
        load_report_presence,
        load_report_presence_search_roi,
    )

    path = v3_profile_file(tmp_path)
    profile, caption, search, _ = load_profile(path)
    original, base, header = detector()
    assert np.array_equal(caption, header)
    roi = load_report_presence_search_roi(path)
    assert roi == (0, 45, 80, 78) and search == (0, 0, 80, 78)
    model = SelfDeathImageRecognizer(profile, original.reader.reader, caption, search,
        runtime_fingerprint=image_runtime_fingerprint(), dependencies_fingerprint=HASH,
        native_step_ticks=1, report_presence_header=load_report_presence(path),
        report_presence_search_roi=roi)
    manifest = cache(tmp_path, 'v3-cache', base, header, persistent=False)
    result = replay_cache(manifest, model, HASH)
    assert result[0]['prediction_count'] == 1
    assert {r['source']['code_fingerprint'] for r in result[0]['rows']} == {model.code_fingerprint}


@pytest.mark.parametrize('roi', [None, [0, 45, 80, 77], [False, 45, 80, 78], [-1, 45, 79, 78]])
def test_v3_invalid_presence_roi_cannot_reinterpret_old_calibration(tmp_path, roi):
    path = v3_profile_file(tmp_path)
    data = json.loads(path.read_text(encoding='utf-8'))
    data['report_presence_search_roi'] = roi
    path.write_text(json.dumps(data), encoding='utf-8')
    with pytest.raises(ValueError, match='presence'):
        load_profile(path)


def v4_profile_file(tmp_path):
    path = v3_profile_file(tmp_path)
    data = json.loads(path.read_text(encoding='utf-8'))
    assets = path.parent/data['assets_file']
    with np.load(assets, allow_pickle=False) as source:
        arrays = {k: source[k].copy() for k in source.files}
    arrays['ability_separator_reference_000'] = np.random.default_rng(234).integers(
        20, 220, (19, 22), dtype=np.uint8)
    np.savez_compressed(assets, **arrays)
    data.update(schema_version='self_death_image_profile_v4',
                assets_sha256=hashlib.sha256(assets.read_bytes()).hexdigest())
    path.write_text(json.dumps(data), encoding='utf-8')
    return path


def test_v4_explicit_ability_bank_preserves_separate_presence_calibration(tmp_path):
    from scripts.diagnostics.replay_self_death_images import load_report_presence_search_roi

    path = v4_profile_file(tmp_path)
    profile, _, _, _ = load_profile(path)
    assert len(profile.ability_separator_references) == 1
    assert load_report_presence_search_roi(path) == (0, 45, 80, 78)
    data = json.loads(path.read_text(encoding='utf-8'))
    data['schema_version'] = 'self_death_image_profile_v3'
    path.write_text(json.dumps(data), encoding='utf-8')
    with pytest.raises(ValueError, match='v4 profile contract'):
        load_profile(path)


def test_v4_requires_ability_bank_instead_of_silently_using_weapon_references(tmp_path):
    path = v3_profile_file(tmp_path)
    data = json.loads(path.read_text(encoding='utf-8'))
    data['schema_version'] = 'self_death_image_profile_v4'
    path.write_text(json.dumps(data), encoding='utf-8')
    with pytest.raises(ValueError, match='explicit ability separator bank'):
        load_profile(path)
