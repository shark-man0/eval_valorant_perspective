import hashlib

import pytest

from valorant_ai_coach.visual.development_map_version import gate_map_version


def example():
    pixels = b'public asset bytes'
    reference = {'map_id': 'corrode', 'reference_sha256': hashlib.sha256(pixels).hexdigest(),
                 'client_build': None, 'build_evidence_sha256': None}
    record = {'qualification': 'development_only', 'ownership': {'identity': 'UNKNOWN'},
              'source_sha256': '1'*64, 'acquisition_id': 'epoch', 'map_id': 'corrode',
              'formal_self_position_fact': None, 'map_position_norm': [.2, .3],
              'map_segment': 1, 'map_speed_norm_per_sec': .1,
              'zone_resolution': {'zone_id': 'plant_a', 'candidate_zone_ids': ['plant_a']},
              'development_region_candidate': {'region_id': 'plant_a'},
              'development_events': [{'candidate_kind': 'zone_transition'}],
              'calibration': {'status': 'ok', 'confidence': .99}}
    return record, reference, pixels


def test_unknown_build_does_not_turn_outline_fit_into_compatible_geometry():
    record, reference, pixels = example()
    result = gate_map_version(record, reference, pixels, source_build_evidence=None)
    assert result['map_position_norm'] is None
    assert result['zone_resolution']['zone_id'] is None
    assert result['zone_resolution']['candidate_zone_ids'] == []
    assert result['development_events'] == []
    assert result['map_segment'] is None and result['map_speed_norm_per_sec'] is None
    assert result['calibration']['status'] == 'calibration_required'
    assert result['map_version_evidence']['status'] == 'UNKNOWN'
    assert result['unverified_geometry_candidate']['map_position_norm'] == [.2, .3]
    assert record['map_position_norm'] == [.2, .3]


def test_same_evidenced_build_preserves_candidates_without_qualifying_ownership():
    record, ref, pixels = example()
    ref.update(client_build='release-a', build_evidence_sha256='2'*64)
    source = {'source_sha256': '1'*64, 'acquisition_id': 'epoch', 'client_build': 'release-a',
              'evidence_sha256': '3'*64}
    result = gate_map_version(record, ref, pixels, source_build_evidence=source)
    assert result['map_position_norm'] == record['map_position_norm']
    assert result['map_version_evidence']['status'] == 'SAME_EVIDENCED_BUILD'
    assert result['map_version_evidence']['qualified_geometry'] is False
    assert result['ownership']['identity'] == 'UNKNOWN'
    source['client_build'] = 'release-b'
    assert gate_map_version(record, ref, pixels, source_build_evidence=source)[
        'map_version_evidence']['status'] == 'MISMATCH'


@pytest.mark.parametrize('change', ['source', 'reference', 'map', 'unknown', 'no_evidence'])
def test_hash_binding_and_unknown_build_labels_fail_closed(change):
    record, ref, pixels = example()
    ref.update(client_build='release-a', build_evidence_sha256='2'*64)
    source = {'source_sha256': '1'*64, 'acquisition_id': 'epoch', 'client_build': 'release-a',
              'evidence_sha256': '3'*64}
    if change == 'source':
        source['source_sha256'] = '4'*64
    elif change == 'reference':
        pixels += b'changed'
    elif change == 'map':
        ref['map_id'] = 'bind'
    elif change == 'unknown':
        source['client_build'] = ref['client_build'] = 'unknown'
    else:
        ref['build_evidence_sha256'] = None
    result = gate_map_version(record, ref, pixels, source_build_evidence=source)
    assert result['map_position_norm'] is None
    assert result['map_version_evidence']['status'] in {'UNKNOWN', 'MISMATCH'}
