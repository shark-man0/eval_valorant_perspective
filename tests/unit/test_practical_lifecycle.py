"""Synthetic producer/admission tests, not real reader qualification."""
from copy import deepcopy

import pytest

from tests.unit.test_unedited_ui_end import fixture
from valorant_ai_coach.hud.practical_lifecycle import replay_practical_boundaries
from valorant_ai_coach.hud.unedited_lifecycle import UneditedRoundLifecycle


def practical(rows, tracker):
    # Synthetic producer scan fields; no real reader qualification is implied.
    for row in rows:
        phase = row['system_observation']['values']['buy_phase_visible']
        row['system_evidence'].setdefault('assured_phase_present', phase)
        row['system_evidence'].setdefault('assured_phase_confidence', .95 if phase else 0.0)
    return replay_practical_boundaries(
        rows, tracker.start.contract, native_step_ticks=20, profile_fingerprint='a' * 64,
    )


def test_practical_reuses_delayed_end_and_next_start_without_qualification(tmp_path):
    rows, tracker = fixture(tmp_path, next_round=True)
    boundaries, diagnostics = practical(rows, tracker)
    assert [b.kind for b in boundaries] == ['round_start', 'round_end', 'round_start']
    assert all(b.boundary_status == 'provisional' for b in boundaries)
    assert boundaries[1].boundary_time_sec == .44
    assert boundaries[1].confirmation_time_sec == .82
    assert boundaries[1].provenance['qualification_status'] == 'unverified'
    assert 'qualification_sha256' not in boundaries[1].provenance
    assert diagnostics[-1]['state'] == 'round_active'


def test_strict_constructor_cannot_omit_qualification(tmp_path):
    _, tracker = fixture(tmp_path)
    with pytest.raises(ValueError, match='requires qualification'):
        UneditedRoundLifecycle(tracker.start, None)


@pytest.mark.parametrize('invalid', ['menu', 'spectator', 'owned', 'source_hash', 'score_low'])
def test_practical_never_relaxes_current_frame_or_owned_contracts(tmp_path, invalid):
    rows, tracker = fixture(tmp_path)
    original = deepcopy(rows)
    if invalid == 'source_hash':
        rows[20]['source_video_sha256'] = 'b' * 64
    elif invalid == 'owned':
        rows[20]['system_observation']['values']['hp'] = 100
    elif invalid == 'score_low':
        for row in rows:
            row['system_observation']['quality']['roi_confidence']['score_enemy_value'] = .89
    else:
        for row in rows[14:]:
            row['system_observation']['primary_state'] = (
                'buy_menu' if invalid == 'menu' else 'spectator_first_person'
            )
    if invalid in {'owned', 'source_hash'}:
        with pytest.raises(ValueError):
            practical(rows, tracker)
    else:
        boundaries, _ = practical(rows, tracker)
        assert not any(b.kind == 'round_end' for b in boundaries)
    # Replay cannot rewrite observed values or displays.
    if invalid == 'score_low':
        assert all(a['system_observation']['values'] == b['system_observation']['values']
                   for a, b in zip(rows, original, strict=True))


@pytest.mark.parametrize('break_kind', ['gap', 'epoch', 'explicit'])
def test_practical_source_break_abandons_pending_end(tmp_path, break_kind):
    rows, tracker = fixture(tmp_path)
    if break_kind == 'gap':
        rows.pop(30)
        for index, row in enumerate(rows):
            row['system_observation']['frame_index'] = index
    elif break_kind == 'epoch':
        for row in rows[30:]:
            row['source_epoch'] = 'next-recording-epoch'
    else:
        rows[30]['system_evidence']['discontinuity'] = True
    boundaries, diagnostics = practical(rows, tracker)
    assert not any(b.kind == 'round_end' for b in boundaries)
    assert any(d['source_break'] for d in diagnostics)


def test_practical_end_only_does_not_invent_start(tmp_path):
    rows, tracker = fixture(tmp_path)
    rows = rows[14:]
    for index, row in enumerate(rows):
        row['system_observation']['frame_index'] = index
    boundaries, _ = practical(rows, tracker)
    assert [b.kind for b in boundaries] == ['round_end']
    assert boundaries[0].boundary_time_sec == .44


def test_practical_result_transport_is_revalidated(tmp_path):
    from valorant_ai_coach.hud.global_lifecycle import global_recognizer_fingerprint
    from valorant_ai_coach.hud.practical_lifecycle import (
        PracticalLifecycleAnalysis,
        validated_practical_boundaries,
    )

    rows, tracker = fixture(tmp_path)
    boundaries, diagnostics = practical(rows, tracker)
    analysis = PracticalLifecycleAnalysis(
        tuple(rows), boundaries, diagnostics, 20, tracker.start.contract,
        tmp_path / 'input.json', 'a' * 64, global_recognizer_fingerprint(),
    )
    result, cuts = validated_practical_boundaries(
        analysis, source_video_sha256=analysis.input_contract.source_video_sha256,
        profile_fingerprint='a' * 64,
    )
    assert result == boundaries and cuts == ()
    rows[20]['system_observation']['values']['hp'] = 99
    with pytest.raises(ValueError):
        validated_practical_boundaries(
            analysis, source_video_sha256=analysis.input_contract.source_video_sha256,
            profile_fingerprint='a' * 64,
        )


def test_missing_current_frame_phase_measurement_is_not_absence(tmp_path):
    rows, tracker = fixture(tmp_path)
    for row in rows:
        row['system_evidence'].pop('assured_phase_present', None)
        row['system_evidence'].pop('assured_phase_confidence', None)
    with pytest.raises(ValueError, match='current-frame phase presence'):
        replay_practical_boundaries(rows, tracker.start.contract,
                                   native_step_ticks=20, profile_fingerprint='a' * 64)


def test_opt_in_processor_partitions_without_releasing_formal_events(tmp_path):
    import hashlib
    from dataclasses import replace

    from tests.unit.test_native_event_merge import qualified_processor
    from tests.unit.test_unedited_ui_start import make_contract
    from valorant_ai_coach.hud.global_lifecycle import global_recognizer_fingerprint
    from valorant_ai_coach.hud.practical_lifecycle import PracticalLifecycleAnalysis

    producer_root = tmp_path / 'producer'
    producer_root.mkdir()
    rows, tracker = fixture(producer_root, next_round=True)
    processor, metadata, frames, _ = qualified_processor(tmp_path)
    path, contract = make_contract(producer_root,
                                   hashlib.sha256(metadata.path.read_bytes()).hexdigest())
    for row in rows:
        row['source_video_sha256'] = contract.source_video_sha256
    tracker.start.contract = contract
    boundaries, diagnostics = practical(rows, tracker)
    analysis = PracticalLifecycleAnalysis(
        tuple(rows), boundaries, diagnostics, 20, contract, path,
        'a' * 64, global_recognizer_fingerprint(),
    )
    processor.analyzer._native_profile_readers = True
    processor.analyzer._base_fingerprint = lambda: 'a' * 64
    processor.analyzer._native_loaded_base_fingerprint = 'a' * 64
    metadata = replace(metadata, duration_sec=2.0)
    with pytest.raises(RuntimeError, match='practical opt-in'):
        processor.process_frames(metadata, 'P', frames, practical_lifecycle=analysis)
    result = processor.process_frames(metadata, 'P', frames, boundary_mode='practical',
                                      practical_lifecycle=analysis)
    assert not any(event['type'] in {'round_start', 'round_end'} for event in result.hud_events)
    starts = [p for p in result.round_packages
              if p['round_lifecycle']['start']['status'] == 'provisional']
    assert len(starts) == 2
    assert starts[-1]['round_lifecycle']['end']['status'] == 'unknown'
    assert all(p['observation_quality']['timeline_completeness'] == 0
               for p in result.round_packages)
