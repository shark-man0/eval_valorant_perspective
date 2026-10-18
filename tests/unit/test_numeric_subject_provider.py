"""Real pixel/code wiring with SYNTHETIC qualification, never video accuracy."""
import hashlib
import json
from dataclasses import replace
from fractions import Fraction

import cv2
import numpy as np
import pytest

from tests.unit import test_numeric_death_release as release_tests
from tests.unit.test_numeric_death_session import qualification_for
from tests.unit.test_qualified_ui_transition import scene_qualification
from tests.unit.test_self_death_image_recognizer import HASH, setup
from tests.unit.test_unedited_ui_start import make_contract
from valorant_ai_coach.experimental.numeric_death_release import (
    NumericSelfDeathEventConsumer,
    QualifiedNumericDeathContract,
)
from valorant_ai_coach.experimental.numeric_death_session import NumericDeathImageSession
from valorant_ai_coach.experimental.numeric_subject_provider import QualifiedNumericImageProvider
from valorant_ai_coach.experimental.subject_death import SourceBinding, SubjectRole
from valorant_ai_coach.hud.global_lifecycle import GlobalLifecycleQualification
from valorant_ai_coach.hud.models import HudObservationV2, empty_hud_values
from valorant_ai_coach.hud.native_lifecycle import NativeLifecycleAnalysis
from valorant_ai_coach.video.native import NativeSourceFrame

qualified_release = release_tests.qualified_release


def context(tmp_path, qualified_release, *, killer=False, persistent=False):
    model, base, header = setup(killer=killer)
    qualification = qualification_for(model, qualified_release)
    scene = scene_qualification(tmp_path)
    # This producer's synthetic numeric certificate explicitly references the
    # exact separate scene qualification. No actual report is generated here.
    _, certificate = qualified_release
    data = json.loads(certificate.read_text(encoding='utf-8'))
    data['component_reviews']['native_temporal_continuity'] = scene.report_sha256
    certificate.write_text(json.dumps(data), encoding='utf-8')
    qualification = QualifiedNumericDeathContract.load(certificate,
        expected_report_sha256=hashlib.sha256(certificate.read_bytes()).hexdigest())
    frames, rows = [], []
    for tick in range(9):
        image = base.copy()
        if not persistent and tick < 2:
            image[20:40, :90] = image[20:40, 170:220] = 0
        if persistent or tick >= 1:
            image[50:62, 10:60] = np.repeat(header[:, :, None], 3, axis=2)
        image[79, 239] = tick
        path = tmp_path/f'{tick}.png'
        assert cv2.imwrite(str(path), image)
        frame = NativeSourceFrame(path, tick, Fraction(1, 60), 'segment', HASH,
            hashlib.sha256(path.read_bytes()).hexdigest(),
            hashlib.sha256(image.tobytes()).hexdigest(),
            240, 80)
        source = {'source_video_sha256': HASH, 'source_epoch': 'segment',
            'source_pts_ticks': tick, 'source_time_base': '1/60',
            'source_pts_sec': tick/60, 'source_pixel_sha256': frame.pixel_sha256}
        evidence = {}
        if tick:
            evidence['global_scene_continuity'] = {
                **source, 'previous_source_pts_ticks': tick-1,
                'previous_source_pts_sec': (tick-1)/60,
                'previous_source_pixel_sha256': frames[-1].pixel_sha256,
                'segment': 'scene-segment', 'scope': 'scene_only',
                'clock_independent': True, 'background_checked': True,
                'qualification_sha256': scene.report_sha256,
                'profile_fingerprint': scene.profile_fingerprint,
                'recognizer_fingerprint': scene.recognizer_fingerprint,
                'witness_cells': [[0, 0], [0, 2], [2, 1]],
                'witness_ncc': [.96, .97, .98], 'confidence': .96,
            }
        rows.append({**source, 'system_evidence': evidence,
                     'system_observation': {'time_sec': tick/60, 'primary_state': 'unknown'}})
        frames.append(frame)
    lifecycle = NativeLifecycleAnalysis(tuple(rows), (), (), (), scene)
    return model, qualification, tuple(frames), lifecycle


def run(model, qualification, frames, lifecycle, *, source_mode='scene'):
    provider = QualifiedNumericImageProvider(model, qualification, frames=frames,
                                            lifecycle=lifecycle, source_mode=source_mode)
    session = NumericDeathImageSession(model, NumericSelfDeathEventConsumer(qualification),
                                      provider)
    readings = []
    for native in frames:
        source = SourceBinding(HASH, native.pts_ticks, 1, 60, 'segment', native.pixel_sha256,
            model.code_fingerprint, model.profile_fingerprint, model.dependencies_fingerprint)
        readings.append(session.observe(native.read_image(), source))
    return provider, session, readings


def assured_context(tmp_path, qualified_release, **kwargs):
    """Synthetic source contract and reviews; never qualify an actual video."""
    model, q, frames, lifecycle = context(tmp_path, qualified_release, **kwargs)
    path, contract = make_contract(tmp_path, HASH)
    report_path = tmp_path/'qualification.json'
    data = json.loads(report_path.read_text())
    for name in ('scene_continuity', 'continuity'):
        data['components'].pop(name)
    report_path.write_text(json.dumps(data))
    native_q = GlobalLifecycleQualification.load(report_path,
        lifecycle.qualification.profile_fingerprint, unedited_input_contract=contract)
    _, certificate = qualified_release
    numeric_data = json.loads(certificate.read_text())
    numeric_data['component_reviews']['native_temporal_continuity'] = native_q.report_sha256
    certificate.write_text(json.dumps(numeric_data))
    q = QualifiedNumericDeathContract.load(certificate,
        expected_report_sha256=hashlib.sha256(certificate.read_bytes()).hexdigest())
    rows = tuple({**row, 'system_evidence': {'assured_phase_scan_valid': False},
        'system_observation': HudObservationV2(frame.time_sec, index, 'unknown',
            values=empty_hud_values()).to_dict()}
        for index, (row, frame) in enumerate(zip(lifecycle.source_rows, frames, strict=True)))
    return model, q, frames, replace(lifecycle, source_rows=rows, qualification=native_q,
        unedited_input_contract=contract, input_contract_path=path)


def test_explicit_assured_source_needs_no_scene_score_or_accepted_timer_for_subject(
    tmp_path, qualified_release,
):
    args = assured_context(tmp_path, qualified_release)
    model, q, frames, lifecycle = args
    assert 'scene_continuity' not in lifecycle.qualification.components
    with pytest.raises(ValueError, match='qualified native source'):
        run(*args)  # No implicit fallback from the default scene entrance.
    provider, session, rows = run(*args, source_mode='source_assured')
    events = [r.event for r in rows if r.event is not None]
    assert len(events) == 1 and events[0]['time_sec'] == 1/60
    assert not provider.failed and not session.failed
    export = provider.continuity_provenance()
    proof_hash = session.frames[3].continuity_proof_sha256
    proof = export['source_assured_proofs'][proof_hash]
    assert proof_hash == hashlib.sha256(json.dumps(proof, sort_keys=True).encode()).hexdigest()
    assert proof['scope'] == 'source_assured_native' and 'confidence' not in proof
    assert export['input_contract_sha256'] == lifecycle.unedited_input_contract.fingerprint
    assert proof['source']['source_pixel_sha256'] == frames[3].pixel_sha256
    assert proof['previous_source']['source_pts_ticks'] == frames[2].pts_ticks
    assert proof['source_evidence'] == {'assured_phase_scan_valid': False}
    assert export['source_qualification_sha256'] == dict(q.component_reviews)[
        'native_temporal_continuity']
    assert all(row['system_observation']['primary_state'] == 'unknown'
               and row['system_observation']['values']['hp'] is None
               and row['system_observation']['values']['round_time_remaining_sec'] is None
               for row in lifecycle.source_rows)
    assert all(not r.image_reading.qualified for r in rows)
    assert events[0]['confidence'] <= min(o.confidence for o in session.frames[3].observations)


@pytest.mark.parametrize('change', ['contract_missing', 'path_missing', 'foreign_contract',
    'changed_contract', 'foreign_qualification', 'missing_component', 'cadence', 'epoch',
    'owner', 'owned_values', 'frame_index', 'source_time', 'invalid_break_flag'])
def test_assured_entrance_rejects_invalid_source_or_owned_data(
    tmp_path, qualified_release, change,
):
    model, q, frames, lifecycle = assured_context(tmp_path, qualified_release)
    if change == 'contract_missing':
        lifecycle = replace(lifecycle, unedited_input_contract=None)
    elif change == 'path_missing':
        lifecycle = replace(lifecycle, input_contract_path=None)
    elif change == 'foreign_contract':
        data = json.loads(lifecycle.input_contract_path.read_text())
        data['source_video_sha256'] = 'b'*64
        lifecycle.input_contract_path.write_text(json.dumps(data))
    elif change == 'changed_contract':
        data = json.loads(lifecycle.input_contract_path.read_text())
        data['assurance_provenance'] += ' changed'
        lifecycle.input_contract_path.write_text(json.dumps(data))
    elif change == 'foreign_qualification':
        lifecycle = replace(lifecycle, qualification=replace(lifecycle.qualification,
                                                           report_sha256='b'*64))
    elif change == 'missing_component':
        lifecycle = replace(lifecycle, qualification=replace(lifecycle.qualification,
            components=lifecycle.qualification.components - {'ui_transition'}))
    elif change == 'cadence':
        frames = (*frames[:3], *frames[4:])
        lifecycle = replace(lifecycle, source_rows=(*lifecycle.source_rows[:3],
                                                   *lifecycle.source_rows[4:]))
    else:
        row = lifecycle.source_rows[3]
        if change == 'epoch':
            frames = (*frames[:3], replace(frames[3], source_epoch='foreign'), *frames[4:])
            row['source_epoch'] = 'foreign'
        elif change == 'owner':
            row['system_observation']['view_context']['is_player_world_view_trustworthy'] = True
        elif change == 'owned_values':
            row['system_observation']['values']['hp'] = 100
        elif change == 'frame_index':
            row['system_observation']['frame_index'] = 2
        elif change == 'source_time':
            row['system_observation']['time_sec'] = 100
        else:
            row['system_evidence']['discontinuity'] = 1
    with pytest.raises(ValueError):
        run(model, q, frames, lifecycle, source_mode='source_assured')


@pytest.mark.parametrize('change', ['content_jump', 'discontinuity', 'contract_removed',
                                  'contract_changed', 'repeated_pixels'])
def test_assured_source_break_or_revocation_cannot_release_death(
    tmp_path, qualified_release, change,
):
    model, q, frames, lifecycle = assured_context(tmp_path, qualified_release)
    if change in {'content_jump', 'discontinuity'}:
        lifecycle.source_rows[3]['system_evidence'][change] = True
    elif change == 'repeated_pixels':
        frames[3].path.write_bytes(frames[2].path.read_bytes())
        frames = (*frames[:3], replace(frames[3], encoded_sha256=frames[2].encoded_sha256,
                                      pixel_sha256=frames[2].pixel_sha256), *frames[4:])
        lifecycle.source_rows[3]['source_pixel_sha256'] = frames[2].pixel_sha256
    provider = QualifiedNumericImageProvider(model, q, frames=frames, lifecycle=lifecycle,
                                            source_mode='source_assured')
    if change == 'contract_removed':
        lifecycle.input_contract_path.unlink()
    elif change == 'contract_changed':
        data = json.loads(lifecycle.input_contract_path.read_text())
        data['assurance_provenance'] += ' revoked'
        lifecycle.input_contract_path.write_text(json.dumps(data))
    session = NumericDeathImageSession(model, NumericSelfDeathEventConsumer(q), provider)
    for native in frames:
        source = SourceBinding(HASH, native.pts_ticks, 1, 60, 'segment', native.pixel_sha256,
            model.code_fingerprint, model.profile_fingerprint, model.dependencies_fingerprint)
        assert session.observe(native.read_image(), source).event is None
    assert session.failed
    if change == 'repeated_pixels':
        # The owning image session checks pixels before invoking the provider.
        assert provider.index == 3
    else:
        assert provider.failed


@pytest.mark.parametrize('killer,persistent', [(True, False), (False, True)])
def test_assured_source_is_neither_self_binding_nor_death_transition(
    tmp_path, qualified_release, killer, persistent,
):
    args = assured_context(tmp_path, qualified_release, killer=killer, persistent=persistent)
    provider, session, rows = run(*args, source_mode='source_assured')
    assert not provider.failed and not session.failed
    assert not any(row.event is not None for row in rows)


def test_numeric_image_producer_reaches_event_without_hand_assembled_subject_labels(
    qualified_release, tmp_path,
):
    args = context(tmp_path, qualified_release)
    provider, session, rows = run(*args)
    events = [r.event for r in rows if r.event is not None]
    assert len(events) == 1 and events[0]['time_sec'] == 1/60
    assert events[0]['actor'] == 'player'
    assert events[0]['attributes']['evidence_provenance']['confirmation_source']['pts_ticks'] == 5
    assert len(session.consumer.released) == 1 and not provider.failed
    assert all(not r.image_reading.qualified and r.image_reading.formal_events == () for r in rows)
    proof = session.frames[3].continuity_proof_sha256
    original = args[3].source_rows[3]['system_evidence']['global_scene_continuity']
    assert proof == hashlib.sha256(json.dumps(original, sort_keys=True).encode('utf-8')).hexdigest()
    assert provider.continuity_provenance()['scene_proofs'][proof] == original
    assert session.frames[3].observations[0].review_sha256 == dict(
        args[1].component_reviews)['source_player_binding']


@pytest.mark.parametrize('change', ['numeric_missing', 'numeric_code', 'scene_missing',
                                   'scene_code', 'scene_binding', 'coverage', 'foreign_video'])
def test_no_missing_mismatched_or_foreign_qualification_can_install_provider(
    qualified_release, tmp_path, change,
):
    model, q, frames, lifecycle = context(tmp_path, qualified_release)
    if change == 'numeric_missing':
        q = None
    elif change == 'numeric_code':
        q = replace(q, code_fingerprint='1'*64)
    elif change == 'scene_missing':
        lifecycle = replace(lifecycle, qualification=None)
    elif change == 'scene_code':
        lifecycle = replace(lifecycle, qualification=replace(lifecycle.qualification,
                                                           recognizer_fingerprint='1'*64))
    elif change == 'scene_binding':
        q = replace(q, component_reviews=tuple((k, '1'*64 if k == 'native_temporal_continuity'
                                               else v) for k, v in q.component_reviews))
    elif change == 'coverage':
        frames = frames[:-1]
    else:
        frames = (replace(frames[0], source_video_sha256='1'*64), *frames[1:])
    with pytest.raises(ValueError):
        QualifiedNumericImageProvider(model, q, frames=frames, lifecycle=lifecycle)


@pytest.mark.parametrize('change', ['missing', 'confidence', 'single_cell', 'same_row',
    'cell_duplicate', 'low_cell', 'previous_tick', 'previous_pixel', 'source_pixel',
    'source_epoch', 'source_time', 'timebase', 'foreign_review', 'foreign_profile',
    'clock_dependent', 'background_unchecked', 'segment_change', 'explicit_break'])
def test_missing_weak_or_cross_source_scene_proof_poison_without_an_event(
    qualified_release, tmp_path, change,
):
    model, q, frames, lifecycle = context(tmp_path, qualified_release)
    evidence = lifecycle.source_rows[3]['system_evidence']
    proof = evidence['global_scene_continuity']
    mutations = {
        'confidence': {'confidence': .89}, 'single_cell': {'witness_cells': [[0, 0]],
                                                          'witness_ncc': [.99]},
        'same_row': {'witness_cells': [[0, 0], [0, 1], [0, 2]]},
        'cell_duplicate': {'witness_cells': [[0, 0], [0, 0], [2, 1]]},
        'low_cell': {'witness_ncc': [.96, .89, .98]},
        'previous_tick': {'previous_source_pts_ticks': 0},
        'previous_pixel': {'previous_source_pixel_sha256': '1'*64},
        'source_pixel': {'source_pixel_sha256': '1'*64},
        'source_epoch': {'source_epoch': 'foreign'}, 'source_time': {'source_pts_sec': 100},
        'timebase': {'source_time_base': '1/30'},
        'foreign_review': {'qualification_sha256': '1'*64},
        'foreign_profile': {'profile_fingerprint': '1'*64},
        'clock_dependent': {'clock_independent': False},
        'background_unchecked': {'background_checked': False},
        'segment_change': {'segment': 'other-scene'},
    }
    if change == 'missing':
        evidence.clear()
    elif change == 'explicit_break':
        evidence['discontinuity'] = True
    else:
        proof.update(mutations[change])
    provider, session, rows = run(model, q, frames, lifecycle)
    assert all(r.event is None for r in rows)
    assert provider.failed and session.failed


def test_native_image_change_is_rejected_before_issuing_subject_proof(
    qualified_release, tmp_path,
):
    model, q, frames, lifecycle = context(tmp_path, qualified_release)
    provider = QualifiedNumericImageProvider(model, q, frames=frames, lifecycle=lifecycle)
    image = frames[0].read_image()
    source = SourceBinding(HASH, 0, 1, 60, 'segment', frames[0].pixel_sha256,
                           model.code_fingerprint, model.profile_fingerprint, HASH)
    reading = model.observe(image, source)
    frames[0].path.write_bytes(b'corrupt encoded frame')
    result = provider(reading)
    assert result.discontinuity and not result.observations and provider.failed
    assert provider.last_blocker == 'native_encoded_or_pixel_hash_mismatch'


def test_skipped_native_source_cannot_create_continuity(qualified_release, tmp_path):
    model, q, frames, lifecycle = context(tmp_path, qualified_release)
    frames = (*frames[:3], *frames[4:])
    lifecycle = replace(lifecycle, source_rows=(*lifecycle.source_rows[:3],
                                               *lifecycle.source_rows[4:]))
    provider, session, rows = run(model, q, frames, lifecycle)
    assert all(r.event is None for r in rows) and session.failed
    # The image session itself rejects the missing native input before asking
    # the provider to qualify it; neither path can continue the old episode.
    assert provider.index == 3


def test_scene_proof_cannot_inflate_confidence_above_its_measured_cells(
    qualified_release, tmp_path,
):
    model, q, frames, lifecycle = context(tmp_path, qualified_release)
    lifecycle.source_rows[3]['system_evidence']['global_scene_continuity']['confidence'] = .99
    provider, _, rows = run(model, q, frames, lifecycle)
    assert all(r.event is None for r in rows)
    assert provider.failed


def test_event_confidence_is_capped_by_accepted_current_source_support(
    qualified_release, tmp_path,
):
    model, q, frames, lifecycle = context(tmp_path, qualified_release)
    for row in lifecycle.source_rows[1:]:
        proof = row['system_evidence']['global_scene_continuity']
        proof['confidence'] = .90
    _, _, rows = run(model, q, frames, lifecycle)
    event = next(r.event for r in rows if r.event is not None)
    assert event['confidence'] == .90


@pytest.mark.parametrize('killer,persistent', [(True, False), (False, True)])
def test_killer_or_persistent_report_cannot_create_a_new_subject_death(
    qualified_release, tmp_path, killer, persistent,
):
    args = context(tmp_path, qualified_release, killer=killer, persistent=persistent)
    provider, _, rows = run(*args)
    assert not provider.failed and all(r.event is None for r in rows)
    if killer:
        assert any(s.role == 'killer' for r in rows for s in r.image_reading.subjects)


def test_scene_proofs_are_frozen_and_cannot_be_mutated_by_the_caller(qualified_release, tmp_path):
    model, q, frames, lifecycle = context(tmp_path, qualified_release)
    provider = QualifiedNumericImageProvider(model, q, frames=frames, lifecycle=lifecycle)
    lifecycle.source_rows[3]['system_evidence'].clear()
    session = NumericDeathImageSession(model, NumericSelfDeathEventConsumer(q), provider)
    events = []
    for native in frames:
        source = SourceBinding(HASH, native.pts_ticks, 1, 60, 'segment', native.pixel_sha256,
                               model.code_fingerprint, model.profile_fingerprint, HASH)
        result = session.observe(native.read_image(), source)
        events.extend([result.event] if result.event is not None else [])
    assert len(events) == 1


def test_absent_numeric_victim_never_gets_a_synthetic_geometry_score(qualified_release, tmp_path):
    model, q, frames, lifecycle = context(tmp_path, qualified_release)
    provider = QualifiedNumericImageProvider(model, q, frames=frames, lifecycle=lifecycle)
    from tests.unit.test_self_death_image_recognizer import observe, setup

    reader, image, header = setup()
    # Exercise actual measurements, then remove only the numeric role witness.
    # The provider may retain marker/Report facts but cannot turn geometry into NCC.
    for tick in range(3):
        reading = observe(reader, image, header, tick, report=tick >= 1, marker=tick >= 2)
        reading = replace(reading, source=SourceBinding(HASH, tick, 1, 60, 'segment',
            frames[tick].pixel_sha256, model.code_fingerprint, model.profile_fingerprint, HASH))
        reading = replace(reading, subjects=tuple(replace(s, source=reading.source,
            weapon_support=None) for s in reading.subjects))
        result = provider(reading)
    assert not result.discontinuity
    assert all(o.role != SubjectRole.VICTIM for o in result.observations)
