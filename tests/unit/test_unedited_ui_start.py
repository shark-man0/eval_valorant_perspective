import hashlib
import json
from copy import deepcopy
from dataclasses import asdict
from pathlib import Path

import pytest

from tests.unit.test_native_lifecycle import source_sequence
from tests.unit.test_qualified_ui_transition import scene_qualification
from valorant_ai_coach.hud.unedited_input import UneditedInputContract
from valorant_ai_coach.hud.unedited_ui_start import UneditedUiStartTracker


def make_contract(tmp_path, source_hash):
    value = json.loads(Path('datasets/input_contracts/match_001.unedited.json').read_text())
    value['source_video_sha256'] = source_hash
    p = tmp_path / 'input.json'
    p.write_text(json.dumps(value))
    return p, UneditedInputContract.load(p, source_video_sha256=source_hash)


def sequence(tmp_path):
    q = scene_qualification(tmp_path)
    rows, _, _ = source_sequence(q, two_rounds=True)
    _, contract = make_contract(tmp_path, rows[0]['source_video_sha256'])
    return rows, UneditedUiStartTracker(contract, native_step_ticks=20)


def test_source_assurance_never_applies_to_another_video(tmp_path):
    path, contract = make_contract(tmp_path, 'a' * 64)
    assert contract.source_video_sha256 == 'a' * 64
    with pytest.raises(ValueError, match='matching'):
        UneditedInputContract.load(path, source_video_sha256='b' * 64)
    value = json.loads(path.read_text())
    value['no_user_edit'] = 1
    path.write_text(json.dumps(value))
    with pytest.raises(ValueError):
        UneditedInputContract.load(path, source_video_sha256='a' * 64)


def test_transient_values_preserved_stability_restarts_duplicate_start_suppressed(tmp_path):
    rows, tracker = sequence(tmp_path)
    original = deepcopy(rows)
    candidates = [c for r in rows if (c := tracker.advance(r, phase_scan_valid=True))]
    assert len(candidates) == 1
    c = candidates[0]
    assert c.time_sec == .12
    p = c.attributes['evidence_provenance']
    assert p['coherent_clock_begin_pts_sec'] == .18
    assert [s['observed_display'] for s in p['clock_display_samples']][:4] == [
        '0:00', '2:08', '2:08', '1:33',
    ]
    assert p['reader_qualification_required'] is True
    assert rows == original


@pytest.mark.parametrize('invalid', ['gap', 'epoch', 'marker', 'scan', 'menu', 'occluded'])
def test_safety_failures_drop_preparation_before_confirmation(tmp_path, invalid):
    rows, tracker = sequence(tmp_path)
    for i, row in enumerate(rows[:9]):
        valid = True
        if i == 6:
            if invalid == 'gap':
                continue
            if invalid == 'epoch':
                row['source_epoch'] = 'other'
            elif invalid == 'marker':
                row['system_evidence']['discontinuity'] = True
            elif invalid == 'scan':
                valid = False
            elif invalid == 'menu':
                row['system_observation']['primary_state'] = 'menu_overlay'
            elif invalid == 'occluded':
                row['system_observation']['quality']['occluded_rois'] = ['center_phase_banner']
        assert tracker.advance(row, phase_scan_valid=valid) is None
    assert tracker.pending is None


def test_display_confidence_is_not_replaced_by_source_assurance(tmp_path):
    rows, tracker = sequence(tmp_path)
    for row in rows:
        row['system_observation']['quality']['roi_confidence']['round_timer_value'] = .89
        assert tracker.advance(row, phase_scan_valid=True) is None


def test_unconfirmed_current_phase_text_is_not_a_disappearance(tmp_path):
    rows, tracker = sequence(tmp_path)
    original = deepcopy(rows)
    # A source matcher sees preparation text on a frame whose debounced flag
    # is absent. The reset-looking timer must not authorize a start.
    rows[6]['system_evidence'].update(assured_phase_present=True,
                                      assured_phase_confidence=.95)
    assert not [d for row in rows[:14] if (d := tracker.advance(row, phase_scan_valid=True))]
    assert rows[6]['system_observation'] == original[6]['system_observation']


@pytest.mark.parametrize('transition', [
    'menu', 'spectator', 'remote', 'scan', 'occluded', 'unqualified_result',
])
def test_display_transition_cannot_rearm_an_already_started_round(tmp_path, transition):
    rows, tracker = sequence(tmp_path)
    candidates = []
    for index, row in enumerate(rows):
        valid = True
        if index == 14:
            obs = row['system_observation']
            if transition in {'menu', 'spectator', 'remote'}:
                obs['primary_state'] = {
                    'menu': 'buy_menu_open', 'spectator': 'spectator_first_person',
                    'remote': 'remote_control_view',
                }[transition]
            elif transition == 'scan':
                valid = False
            elif transition == 'occluded':
                obs['quality']['occluded_rois'] = ['center_phase_banner']
            else:
                obs['state_flags'] = ['round_end_banner']
        candidate = tracker.advance(row, phase_scan_valid=valid)
        if candidate:
            candidates.append(candidate)
    # Later preparation and a reset-looking clock cannot replace a qualified end.
    assert [c.time_sec for c in candidates] == [.12]
    assert tracker.started is True


@pytest.mark.parametrize('break_kind', ['gap', 'epoch', 'marker'])
def test_started_latch_still_clears_on_source_discontinuity(tmp_path, break_kind):
    rows, tracker = sequence(tmp_path)
    for row in rows[:14]:
        tracker.advance(row, phase_scan_valid=True)
    assert tracker.started is True
    row = rows[14]
    if break_kind == 'gap':
        row = rows[15]
    elif break_kind == 'epoch':
        row['source_epoch'] = 'new-source-epoch'
    else:
        row['system_evidence']['discontinuity'] = True
    assert tracker.advance(row, phase_scan_valid=True) is None
    assert tracker.started is False
    assert tracker.state == 'unobserved'


def test_archived_actual_r1_replay_is_candidate_only(tmp_path):
    path = Path('e2e_reports/match_001/native_system_prefix_validation.json')
    raw = path.read_bytes()
    report = json.loads(raw)
    _, contract = make_contract(tmp_path, report['source_video_sha256'])
    tracker = UneditedUiStartTracker(contract, native_step_ticks=report['native_step_ticks'])
    candidates = [asdict(c) for r in report['rows']
                  if (c := tracker.advance(r, phase_scan_valid=True))]
    assert len(candidates) == 1
    samples = candidates[0]['attributes']['evidence_provenance']['clock_display_samples']
    assert [s['observed_display'] for s in samples[:4]] == ['0:00', '2:25', '2:25', '1:39']
    assert path.read_bytes() == raw
    assert hashlib.sha256(raw).hexdigest()


def test_assured_qualification_removes_edit_components_only(tmp_path):
    from tests.unit.test_global_round_lifecycle import report
    from valorant_ai_coach.hud.global_lifecycle import GlobalLifecycleQualification

    _, contract = make_contract(tmp_path, 'a' * 64)
    data = report()
    components = data['components']
    data['components'] = {key: components[key] for key in ('timer', 'purchase_phase')}
    data['components']['ui_transition'] = components['continuity']
    path = tmp_path / 'qualification.json'
    path.write_text(json.dumps(data))
    with pytest.raises(ValueError):
        GlobalLifecycleQualification.load(path, data['profile_fingerprint'])
    q = GlobalLifecycleQualification.load(
        path, data['profile_fingerprint'], unedited_input_contract=contract,
    )
    assert q.components == frozenset({'timer', 'purchase_phase', 'ui_transition'})
    data['components']['timer']['holdout_wrong'] = 1
    data['components']['timer']['holdout_correct'] = 2
    path.write_text(json.dumps(data))
    with pytest.raises(ValueError, match='Unqualified'):
        GlobalLifecycleQualification.load(
            path, data['profile_fingerprint'], unedited_input_contract=contract,
        )


def test_assurance_does_not_qualify_ui_transition_automatically(tmp_path):
    from tests.unit.test_global_round_lifecycle import report
    from valorant_ai_coach.hud.global_lifecycle import GlobalLifecycleQualification

    _, contract = make_contract(tmp_path, 'a' * 64)
    data = report()
    path = tmp_path / 'qualification.json'
    path.write_text(json.dumps(data))
    with pytest.raises(ValueError, match='Missing'):
        GlobalLifecycleQualification.load(
            path, data['profile_fingerprint'], unedited_input_contract=contract,
        )


def test_assured_joint_evidence_can_share_frames_within_the_same_split(tmp_path):
    from tests.unit.test_global_round_lifecycle import report
    from valorant_ai_coach.hud.global_lifecycle import GlobalLifecycleQualification

    _, contract = make_contract(tmp_path, 'a' * 64)
    data = report()
    # Timer, phase and joint transition are measured on the same physical input.
    # Separate component-specific frames or three distinct round episodes are
    # not prerequisites. Every split still has three distinct reviewed hashes.
    proof = data['components']['timer']
    data['components'] = {name: deepcopy(proof) for name in (
        'timer', 'purchase_phase', 'ui_transition',
    )}
    path = tmp_path / 'joint-qualification.json'
    path.write_text(json.dumps(data))
    result = GlobalLifecycleQualification.load(
        path, data['profile_fingerprint'], unedited_input_contract=contract,
    )
    assert result.components == frozenset(data['components'])


@pytest.mark.parametrize('left,right', [
    ('training_hashes', 'holdout_hashes'),
    ('training_hashes', 'negative_hashes'),
    ('holdout_hashes', 'negative_hashes'),
])
def test_assurance_never_allows_cross_component_split_leakage(tmp_path, left, right):
    from tests.unit.test_global_round_lifecycle import report
    from valorant_ai_coach.hud.global_lifecycle import GlobalLifecycleQualification

    _, contract = make_contract(tmp_path, 'a' * 64)
    data = report()
    data['components'] = {name: data['components'][name] for name in (
        'timer', 'purchase_phase',
    )}
    data['components']['ui_transition'] = deepcopy(data['components']['timer'])
    # Each individual component remains internally disjoint; the leak crosses
    # components and must still invalidate the complete global qualification.
    data['components']['purchase_phase'][right][0] = data['components']['timer'][left][0]
    path = tmp_path / 'leaked-qualification.json'
    path.write_text(json.dumps(data))
    with pytest.raises(ValueError, match='splits overlap across global components'):
        GlobalLifecycleQualification.load(
            path, data['profile_fingerprint'], unedited_input_contract=contract,
        )
