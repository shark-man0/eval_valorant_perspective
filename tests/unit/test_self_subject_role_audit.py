"""Offline count/binding tests only; no synthetic image qualification claims."""
import json
import sys
from copy import deepcopy

import pytest

from scripts.diagnostics.evaluate_self_subject_roles import (
    audit_roles,
    main,
    verify_decode_bindings,
)
from scripts.diagnostics.verify_self_death_review import sha256_file


def data():
    source = {'video_sha256': 'a'*64, 'pts_ticks': 1, 'time_base_num': 1,
              'time_base_den': 60, 'segment_id': 'synthetic', 'pixel_sha256': 'b'*64,
              'code_fingerprint': 'c'*64, 'profile_fingerprint': 'd'*64,
              'dependencies_fingerprint': 'e'*64}
    subject = {'source': source.copy(), 'role': 'victim', 'marker_roi': [100, 20, 140, 40],
               'marker_support': [.96, .97, .98], 'yellow_fraction': 1.,
               'weapon_roi': [50, 20, 80, 40], 'weapon_support': .95,
               'weapon_plate_fraction': .96, 'name_text': 'source-observed',
               'name_confidence': .94}
    prediction = {'source_sha256': 'a'*64, 'reader_code_fingerprint': 'c'*64,
                  'profile_fingerprint': 'd'*64, 'dependencies_fingerprint': 'e'*64,
                  'frame_count': 1, 'continuity_qualified': False,
                  'independent_qualification_granted': False, 'formal_events': 0,
                  'terminal_source_code_profile_asset_dependency_hashes_verified': True,
                  'rows': [{'index': 1, 'source': source, 'subjects': [subject]}]}
    review = {'source_sha256': 'a'*64, 'labels': [{
        'index': 1, 'source_pts_ticks': 1, 'source_time_base': '1/60',
        'source_pixel_sha256': 'b'*64,
        'expected_self_rows': [{'role': 'victim', 'row_from_top': 1,
                                'name_display': 'source-observed'}],
        'additional_partial_row_unresolved': False,
        'known_native_or_nearby_episode_exposure': False,
        'additional_known_full_image_context_pts_ticks': [],
    }]}
    return prediction, review


def audit(predictions, review, **kwargs):
    return audit_roles(predictions, review, row_origin=kwargs.get('row_origin', 30),
                       row_pitch=kwargs.get('row_pitch', 40))


def test_positive_counts_do_not_grant_qualification_or_continuity():
    result = audit(*data())
    assert result['counts']['correct_roles'] == 1
    assert result['counts']['correct_own_names'] == 1
    assert result['counts']['numeric_victim_rows'] == 1
    assert result['counts']['false_self_markers'] == 0
    assert result['independent_qualification_granted'] is False
    assert result['continuity_qualified'] is False
    assert result['formal_events'] == 0
    assert result['canonical_current'] == 'not_measured'
    # Missing episode records cannot attest blind/independent exposure.
    assert 'no_known_episode_record_not_blind' in result['exposure_strata']


@pytest.mark.parametrize('field', ['video', 'pts', 'timebase', 'pixel', 'code', 'profile',
                                 'dependencies', 'subject_source', 'index', 'coverage'])
def test_foreign_or_incomplete_readings_cannot_create_valid_counts(field):
    predictions, review = data()
    if field == 'subject_source':
        predictions['rows'][0]['subjects'][0]['source']['pixel_sha256'] = 'f'*64
    elif field == 'index':
        review['labels'][0]['index'] = 2
    elif field == 'coverage':
        predictions['frame_count'] = 2
    elif field in {'code', 'profile', 'dependencies'}:
        key = {'code': 'reader_code_fingerprint', 'profile': 'profile_fingerprint',
               'dependencies': 'dependencies_fingerprint'}[field]
        predictions[key] = 'f'*64
    else:
        key = {'video': 'source_sha256', 'pts': 'source_pts_ticks',
               'timebase': 'source_time_base', 'pixel': 'source_pixel_sha256'}[field]
        (review if field == 'video' else review['labels'][0])[key] = {
            'video': 'f'*64, 'pts': 2, 'timebase': '1/30', 'pixel': 'f'*64,
        }[field]
    with pytest.raises(ValueError):
        audit(predictions, review)


def test_duplicate_source_frames_cannot_inflate_positive_support():
    predictions, review = data()
    predictions['rows'].append(deepcopy(predictions['rows'][0]))
    review['labels'].append(deepcopy(review['labels'][0]))
    predictions['rows'][1]['index'] = review['labels'][1]['index'] = 2
    predictions['frame_count'] = 2
    with pytest.raises(ValueError, match='duplicate physical'):
        audit(predictions, review)


def test_geometry_only_victim_is_not_numeric_qualification_support():
    predictions, review = data()
    predictions['rows'][0]['subjects'][0]['weapon_support'] = None
    counts = audit(predictions, review)['counts']
    assert counts['correct_roles'] == 1
    assert counts.get('numeric_victim_rows', 0) == 0


def test_no_output_on_a_positive_is_a_miss_not_a_successful_negative():
    predictions, review = data()
    predictions['rows'][0]['subjects'] = []
    counts = audit(predictions, review)['counts']
    assert counts['missed_self_markers'] == counts['missed_known_roles'] == 1
    assert counts.get('true_negative_frames', 0) == 0


def test_wrong_side_is_wrong_role_even_when_the_marker_row_matches():
    predictions, review = data()
    predictions['rows'][0]['subjects'][0]['role'] = 'killer'
    counts = audit(predictions, review)['counts']
    assert counts['correct_self_markers'] == counts['wrong_roles'] == 1
    assert counts.get('correct_roles', 0) == 0


def test_nonself_or_duplicate_marker_is_not_a_true_self_row():
    predictions, review = data()
    predictions['rows'][0]['subjects'].append(deepcopy(predictions['rows'][0]['subjects'][0]))
    review['labels'][0]['additional_partial_row_unresolved'] = True
    counts = audit(predictions, review)['counts']
    assert counts['correct_roles'] == 1 and counts['false_self_markers'] == 1
    assert counts['unreviewed_output_rows'] == 0
    review['labels'][0]['expected_self_rows'] = []
    review['labels'][0]['additional_partial_row_unresolved'] = False
    counts = audit(predictions, review)['counts']
    assert counts['false_self_markers'] == 2


def test_matching_role_in_another_row_cannot_borrow_the_reviewed_subject():
    predictions, review = data()
    predictions['rows'][0]['subjects'][0]['marker_roi'] = [100, 60, 140, 80]
    counts = audit(predictions, review)['counts']
    assert counts['false_self_markers'] == counts['missed_known_roles'] == 1
    assert counts.get('correct_roles', 0) == 0


def test_repeated_pixels_are_disclosed_without_granting_independent_support():
    predictions, review = data()
    row = deepcopy(predictions['rows'][0])
    row['index'] = 2
    row['source']['pts_ticks'] = 2
    row['subjects'][0]['source']['pts_ticks'] = 2
    predictions['rows'].append(row)
    label = deepcopy(review['labels'][0])
    label.update(index=2, source_pts_ticks=2)
    review['labels'].append(label)
    predictions['frame_count'] = 2
    result = audit(predictions, review)
    assert result['counts']['correct_roles'] == 2
    assert result['counts']['distinct_source_pixels'] == 1
    assert result['counts']['repeated_pixel_frames'] == 1
    assert result['independent_qualification_granted'] is False


def test_unresolved_partial_row_is_never_a_successful_negative():
    predictions, review = data()
    predictions['rows'][0]['subjects'] = []
    review['labels'][0].update(expected_self_rows=[], additional_partial_row_unresolved=True)
    counts = audit(predictions, review)['counts']
    assert counts['unresolved_truth_frames'] == 1
    assert counts.get('true_negative_frames', 0) == 0


@pytest.mark.parametrize('value', [True, '0.99', float('nan'), float('inf'), -1., 1.1])
def test_invalid_marker_confidence_is_rejected(value):
    predictions, review = data()
    predictions['rows'][0]['subjects'][0]['marker_support'][0] = value
    with pytest.raises(ValueError):
        audit(predictions, review)


def test_wrong_source_observed_name_remains_an_error_without_string_cleanup():
    predictions, review = data()
    predictions['rows'][0]['subjects'][0]['name_text'] = '<> source-observed'
    counts = audit(predictions, review)['counts']
    assert counts['wrong_own_names'] == 1
    assert counts.get('correct_own_names', 0) == 0


@pytest.mark.parametrize('value', [True, float('nan'), 0, -1])
def test_review_layout_must_be_explicit_and_valid(value):
    with pytest.raises(ValueError):
        audit(*data(), row_pitch=value)


def test_cli_verifies_frozen_utf8_files_and_preserves_previous_output(tmp_path, monkeypatch):
    predictions, review = data()
    manifest = tmp_path/'元画像.json'
    review['labels'][0]['source_encoded_sha256'] = 'f'*64
    manifest.write_text(json.dumps(decode_manifest()), encoding='utf-8')
    review_path, input_path, output_path = [tmp_path/name for name in (
        'レビュー.json', '読取.json', '集計.json')]
    review['manifest_sha256'] = sha256_file(manifest)
    review_path.write_text(json.dumps(review), encoding='utf-8')
    predictions.update(manifest_sha256=sha256_file(manifest),
                       review_sha256=sha256_file(review_path))
    input_path.write_text(json.dumps(predictions), encoding='utf-8')
    monkeypatch.setattr(sys, 'argv', ['audit', '--readings', str(input_path),
        '--review', str(review_path), '--manifest', str(manifest), '--output', str(output_path),
        '--row-origin', '30', '--row-pitch', '40'])
    assert main() == 0
    result = json.loads(output_path.read_text(encoding='utf-8'))
    assert result['counts']['correct_roles'] == 1
    assert result['input_sha256'][str(review_path)] == sha256_file(review_path)
    with pytest.raises(FileExistsError):
        main()
    review_path.write_text('{}', encoding='utf-8')
    with pytest.raises(ValueError, match='frozen review'):
        main()


def decode_manifest():
    return {'processed_frames': 1, 'qualifies_continuity': False, 'formal_events': 0,
            'terminal_source_code_profile_asset_hashes_verified': True,
            'rows': [{'source_video_sha256': 'a'*64, 'pts_ticks': 1,
                      'time_base_num': 1, 'time_base_den': 60, 'source_epoch': 'synthetic',
                      'pixel_sha256': 'b'*64, 'encoded_sha256': 'f'*64}]}


@pytest.mark.parametrize('changed', ['source', 'pts', 'timebase', 'epoch', 'pixels',
                                    'encoding', 'coverage', 'terminal', 'continuity'])
def test_hashed_manifest_must_also_describe_the_original_reading(changed):
    predictions, review = data()
    review['labels'][0]['source_encoded_sha256'] = 'f'*64
    manifest = decode_manifest()
    verify_decode_bindings(predictions, review, manifest)
    if changed == 'coverage':
        manifest['processed_frames'] = 2
    elif changed == 'terminal':
        manifest['terminal_source_code_profile_asset_hashes_verified'] = False
    elif changed == 'continuity':
        manifest['qualifies_continuity'] = True
    else:
        key, value = {'source': ('source_video_sha256', 'f'*64), 'pts': ('pts_ticks', 2),
                      'timebase': ('time_base_den', 30), 'epoch': ('source_epoch', 'foreign'),
                      'pixels': ('pixel_sha256', 'e'*64),
                      'encoding': ('encoded_sha256', 'e'*64)}[changed]
        manifest['rows'][0][key] = value
    with pytest.raises(ValueError):
        verify_decode_bindings(predictions, review, manifest)
