import hashlib
import json
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest

from tests.e2e.trace_adapter import to_e2e_trace
from tests.unit.test_global_start_hypothesis import observation
from valorant_ai_coach.events import EventSourceContract
from valorant_ai_coach.hud.analyzers import RealHudAnalyzer
from valorant_ai_coach.hud.global_lifecycle import (
    GlobalLifecycleQualification,
    global_recognizer_fingerprint,
)
from valorant_ai_coach.hud.readers import FrameFeatureObservation
from valorant_ai_coach.hud.semantic_text import MATCHER
from valorant_ai_coach.hud.temporal import HudDirectEventBuilder
from valorant_ai_coach.resources import resource_path
from valorant_ai_coach.rounds import RoundPackageBuilder
from valorant_ai_coach.schema_validation import SchemaValidator
from valorant_ai_coach.video import VideoMetadata


def digest(text):
    return hashlib.sha256(text.encode()).hexdigest()


def report():
    return {
        'schema_version': '1.0', 'profile_fingerprint': digest('synthetic-profile'),
        'recognizer_fingerprint': global_recognizer_fingerprint(),
        'components': {
            name: {
                'training_hashes': [digest(f'{name}/training/{i}') for i in range(3)],
                'holdout_hashes': [digest(f'{name}/holdout/{i}') for i in range(3)],
                'negative_hashes': [digest(f'{name}/negative/{i}') for i in range(3)],
                'holdout_correct': 3, 'holdout_unknown': 0, 'holdout_wrong': 0,
                'negative_false_positive': 0,
                'review_provenance': 'synthetic unit fixture; not real qualification',
            }
            for name in ('timer', 'purchase_phase', 'continuity', 'score', 'round_result')
        },
    }


def qualification(tmp_path, data=None):
    path = tmp_path / 'qualification.json'
    path.write_text(json.dumps(data or report()))
    return GlobalLifecycleQualification.load(path, digest('synthetic-profile'))


def starts():
    return [
        observation(0, 0, phase=True, timer=0),
        observation(1, .1, phase=True, timer=0),
        observation(2, .2, timer=100),
        observation(3, .3, timer=None, timer_score=0),
        observation(4, .4, timer=99),
    ]


def proofs(rows, qualified):
    return {row['frame_index']: {'global_continuity': {
        'segment': 'source-segment-a', 'confidence': .96,
        'qualification_sha256': qualified.report_sha256,
        'source_pts_sec': row['time_sec'],
    }} for row in rows}


def build(rows, qualified, evidence=None):
    return HudDirectEventBuilder().build(
        rows, evidence_by_frame=evidence if evidence is not None else proofs(rows, qualified),
        global_qualification=qualified,
    )


def test_unknown_identity_global_start_is_system_only_and_never_changes_player_inputs(tmp_path):
    rows = starts()
    original = deepcopy(rows)
    qualified = qualification(tmp_path)
    events = build(rows, qualified)
    assert [(e['type'], e['actor'], e['time_sec']) for e in events] == [
        ('round_start', 'system', .2)
    ]
    assert rows == original
    proof = events[0]['attributes']['evidence_provenance']
    assert proof['scope'] == 'global_system'
    assert proof['neutral_timer_pts_sec'] == [.3]
    assert proof['confirmation_pts_sec'] == .4
    assert proof['qualification_sha256'] == qualified.report_sha256
    assert proof['recognizer_fingerprint'] == global_recognizer_fingerprint()
    assert all(not r['values']['player_specific_hud_valid'] for r in rows)
    assert all(r['primary_state'] == 'unknown' for r in rows)
    assert not HudDirectEventBuilder().build(rows)


def test_phase_confirmation_duration_must_be_inside_current_continuity_segment(tmp_path):
    qualified = qualification(tmp_path)
    rows = [
        observation(0, 0, phase=True, timer=0),
        observation(1, .01, phase=True, timer=0),
        observation(2, .02, timer=100),
        observation(3, .1, timer=99),
    ]
    # These flags can originate from older semantic text confirmation. Two
    # source-attested phase samples 10 ms apart cannot import that older span.
    evidence = proofs(rows, qualified)
    for row in evidence.values():
        row['semantic_buy_phase_source_pts'] = [-10, .01]
    assert not build(rows, qualified, evidence)


def test_dense_phase_confirmation_keeps_actual_source_pts_and_system_actor(tmp_path):
    qualified = qualification(tmp_path)
    rows = [
        observation(0, 0, phase=True, timer=0),
        observation(1, .025, phase=True, timer=0),
        observation(2, .05, phase=True, timer=0),
        observation(3, .1, timer=100),
        observation(4, .2, timer=99),
    ]
    events = build(rows, qualified)
    assert [(e['type'], e['actor'], e['time_sec']) for e in events] == [
        ('round_start', 'system', .1)
    ]
    provenance = events[0]['attributes']['evidence_provenance']
    assert provenance['preparation_pts_sec'] == [0, .05]
    assert provenance['preparation_observation_count'] == 3
    assert provenance['pts_sec'] == [.05, .1, .2]


def test_active_round_phase_jitter_cannot_rearm_or_hide_a_valid_end(tmp_path):
    qualified = qualification(tmp_path)
    rows = starts()
    rows += [
        observation(5, .5, phase=True, timer=0),
        observation(6, .6, phase=True, timer=0),
        observation(7, .7, timer=100),
        observation(8, .8, timer=99),
        observation(9, .9, phase=True, timer=6),
        observation(10, 1.0, phase=True, timer=6),
    ]
    for row in rows[-2:]:
        row['values'].update(score_ally=0, score_enemy=1)
        row['quality']['roi_confidence'].update(ally_score_value=.97, enemy_score_value=.98)
    rows[-1]['values']['score_enemy'] = 2
    evidence = proofs(rows, qualified)
    evidence[10].update(global_round_result_present=True, global_round_result_confidence=.95)
    original = deepcopy(rows)
    events = build(rows, qualified, evidence)
    assert [(event['type'], event['time_sec']) for event in events] == [
        ('round_start', .2), ('round_end', 1.0),
    ]
    assert rows == original
    assert all(event['actor'] == 'system' for event in events)


def test_source_cut_requires_fresh_preparation_before_another_start(tmp_path):
    qualified = qualification(tmp_path)
    rows = starts()
    rows += [
        observation(5, .5, phase=True, timer=0),
        observation(6, .6, timer=100),
        observation(7, .7, timer=99),
        observation(8, .8, phase=True, timer=0),
        observation(9, .9, phase=True, timer=0),
        observation(10, 1.0, timer=100),
        observation(11, 1.1, timer=99),
    ]
    evidence = proofs(rows, qualified)
    evidence[5]['content_jump'] = True
    for frame_index in range(5, 12):
        evidence[frame_index]['global_continuity']['segment'] = 'new-source-segment'
    events = build(rows, qualified, evidence)
    assert [(event['type'], event['time_sec']) for event in events] == [
        ('round_start', .2), ('round_start', 1.0),
    ]
    assert events[-1]['attributes']['evidence_provenance']['preparation_pts_sec'] == [.8, .9]


@pytest.mark.parametrize('interruption', [
    'cut', 'segment', 'no_attestation', 'weak_continuity', 'wrong_qualification',
    'gap', 'timeout', 'weak_timer', 'increasing_timer', 'spectator', 'menu', 'phase', 'stale_pts',
])
def test_global_start_fails_closed_across_interruptions(tmp_path, interruption):
    qualified = qualification(tmp_path)
    rows = starts()
    evidence = proofs(rows, qualified)
    last = rows[-1]
    proof = evidence[4]['global_continuity']
    if interruption == 'cut':
        evidence[4]['content_jump'] = True
    elif interruption == 'segment':
        proof['segment'] = 'another-source-segment'
    elif interruption == 'no_attestation':
        evidence[3] = {}
    elif interruption == 'weak_continuity':
        proof['confidence'] = .89
    elif interruption == 'wrong_qualification':
        proof['qualification_sha256'] = digest('wrong')
    elif interruption == 'stale_pts':
        proof['source_pts_sec'] = .2
    elif interruption == 'gap':
        last['time_sec'] = 1.5
        proof['source_pts_sec'] = 1.5
    elif interruption == 'timeout':
        rows[3]['time_sec'] = 1.1
        last['time_sec'] = 1.3
        evidence[3]['global_continuity']['source_pts_sec'] = 1.1
        proof['source_pts_sec'] = 1.3
    elif interruption == 'weak_timer':
        last['quality']['roi_confidence']['round_timer_value'] = .89
    elif interruption == 'increasing_timer':
        last['values']['round_time_remaining_sec'] = 101
    elif interruption == 'spectator':
        last['primary_state'] = 'spectator_first_person'
    elif interruption == 'menu':
        last['primary_state'] = 'buy_menu_open'
    else:
        last['state_flags'] = ['buy_phase_banner']
        last['values']['buy_phase_visible'] = True
    assert not build(rows, qualified, evidence)


def test_two_rounds_end_once_and_no_inferred_second_end(tmp_path):
    qualified = qualification(tmp_path)
    rows = starts()
    rows += [observation(5, .6, timer=99), observation(6, .8, timer=6)]
    for row in rows[-2:]:
        row['values'].update(score_ally=0, score_enemy=1)
        row['quality']['roi_confidence'].update(ally_score_value=.97, enemy_score_value=.98)
    rows[-1]['values']['score_enemy'] = 2
    evidence = proofs(rows, qualified)
    evidence[6].update(global_round_result_present=True, global_round_result_confidence=.95)
    for i, row in enumerate(starts(), start=7):
        row['frame_index'] = i
        row['time_sec'] += 1.1
        rows.append(row)
    evidence.update(proofs(rows[7:], qualified))
    events = build(rows, qualified, evidence)
    assert [(e['type'], e['time_sec']) for e in events] == [
        ('round_start', .2), ('round_end', .8), ('round_start', 1.3)
    ]
    assert all(e['actor'] == 'system' for e in events)
    packages = RoundPackageBuilder(
        contract=EventSourceContract.load(resource_path('config/event_source_contract_v1.json')),
        validator=SchemaValidator(),
    ).build(
        match_id='independent-system',
        video_metadata=VideoMetadata(Path('source.mp4'), 2, 1920, 1080, 60, 'h264', None, False, 1),
        hud_observations=rows, hud_events=events,
    )
    assert len(packages) == 2
    trace = to_e2e_trace(SimpleNamespace(
        round_packages=packages, observations=rows, visual_observations=(),
    ))
    boundary_rows = [e for e in trace['events'] if e['type'] in {'round_start', 'round_end'}]
    assert [(e['type'], e['actor'], e['time_sec']) for e in boundary_rows] == [
        ('round_start', 'system', .2), ('round_end', 'system', .8),
        ('round_start', 'system', 1.3),
    ]
    assert boundary_rows[0]['round_id'] != boundary_rows[2]['round_id']
    assert boundary_rows[0]['attributes'] == events[0]['attributes']
    assert not any(i['owner'] == 'self' for i in trace['ownership_intervals'])


@pytest.mark.parametrize('missing', ['banner', 'score', 'score_confidence', 'continuity'])
def test_end_requires_independent_current_evidence_in_same_segment(tmp_path, missing):
    qualified = qualification(tmp_path)
    rows = starts() + [observation(5, .6), observation(6, .8)]
    for row in rows[-2:]:
        row['values'].update(score_ally=0, score_enemy=1)
        row['quality']['roi_confidence'].update(ally_score_value=.97, enemy_score_value=.98)
    rows[-1]['values']['score_enemy'] = 2
    evidence = proofs(rows, qualified)
    evidence[6].update(global_round_result_present=True, global_round_result_confidence=.95)
    if missing == 'banner':
        evidence[6]['global_round_result_present'] = False
    elif missing == 'score':
        rows[-1]['values']['score_enemy'] = None
    elif missing == 'score_confidence':
        rows[-1]['quality']['roi_confidence']['enemy_score_value'] = .89
    else:
        evidence[6]['global_continuity']['segment'] = 'after-cut'
    assert [e['type'] for e in build(rows, qualified, evidence)] == ['round_start']


@pytest.mark.parametrize('ordering', ['result_before_score', 'result_after_score',
                                    'result_and_score_after_cut'])
def test_separated_end_evidence_cannot_be_backfilled_into_prior_round(tmp_path, ordering):
    qualified = qualification(tmp_path)
    rows = starts() + [observation(i, .6 + (i-5)*.1) for i in range(5, 9)]
    for row in rows[5:]:
        row['values'].update(score_ally=0, score_enemy=1)
        row['quality']['roi_confidence'].update(ally_score_value=.97, enemy_score_value=.98)
    for row in rows[7:]:
        row['values']['score_enemy'] = 2
    evidence = proofs(rows, qualified)
    result_index = 6 if ordering == 'result_before_score' else 8
    if ordering == 'result_and_score_after_cut':
        result_index = 7
        evidence[7]['content_jump'] = True
        for index in (7, 8):
            evidence[index]['global_continuity']['segment'] = 'fresh-segment'
    evidence[result_index].update(global_round_result_present=True,
                                  global_round_result_confidence=.95)
    original = deepcopy(rows)
    events = build(rows, qualified, evidence)
    assert [(event['type'], event['time_sec']) for event in events] == [('round_start', .2)]
    assert rows == original
    assert all(event['actor'] == 'system' for event in events)


@pytest.mark.parametrize('bad', [
    'profile', 'code', 'overlap', 'wrong', 'unreviewed', 'negative', 'too_small', 'expected',
])
def test_qualification_rejects_invalid_or_leaky_reports(tmp_path, bad):
    data = report()
    proof = data['components']['timer']
    if bad == 'profile':
        data['profile_fingerprint'] = digest('different')
    elif bad == 'code':
        data['recognizer_fingerprint'] = digest('stale-code')
    elif bad == 'overlap':
        proof['holdout_hashes'][0] = proof['training_hashes'][0]
    elif bad == 'wrong':
        proof.update(holdout_correct=2, holdout_wrong=1)
    elif bad == 'unreviewed':
        proof['holdout_correct'] = 2
    elif bad == 'negative':
        proof['negative_false_positive'] = 1
    elif bad == 'too_small':
        proof['training_hashes'] = proof['training_hashes'][:2]
    else:
        data['expected_timestamp'] = 1.3
    with pytest.raises(ValueError):
        qualification(tmp_path, data)


def test_qualification_cannot_share_training_and_holdout_across_components(tmp_path):
    data = report()
    data['components']['timer']['holdout_hashes'][0] = (
        data['components']['purchase_phase']['training_hashes'][0]
    )
    with pytest.raises(ValueError, match='across global components'):
        qualification(tmp_path, data)


def test_analyzer_loads_profile_bound_report_and_invalidates_injected_readers(tmp_path):
    layout = tmp_path / 'hud_layout.json'
    layout.write_bytes(resource_path('config/hud_layout_1080p_v3.json').read_bytes())
    baseline = RealHudAnalyzer(layout)
    base_fingerprint = baseline.fingerprint()
    data = report()
    data['profile_fingerprint'] = base_fingerprint
    path = layout.with_name('hud_layout.global_qualification.json')
    path.write_text(json.dumps(data))
    qualified = RealHudAnalyzer(layout)
    assert qualified.global_qualification is not None
    assert qualified.global_qualification.profile_fingerprint == base_fingerprint
    assert qualified.fingerprint() != base_fingerprint
    overridden = RealHudAnalyzer(layout, readers={'round_timer': object()})
    assert overridden.global_qualification is None
    assert any('Injected readers' in note for note in overridden.profile_diagnostics)
    path.write_text(json.dumps({**data, 'profile_fingerprint': digest('another-profile')}))
    assert RealHudAnalyzer(layout).global_qualification is None


@pytest.mark.parametrize('source_phase', [False, True])
@pytest.mark.parametrize('cut', [False, True])
def test_qualified_analyzer_rejects_external_global_proof_and_preserves_source_and_cuts(
    tmp_path, monkeypatch, source_phase, cut
):
    # Synthetic producer fixtures test the trust boundary, not real qualification.
    layout = tmp_path / 'hud_layout.json'
    layout.write_bytes(resource_path('config/hud_layout_1080p_v3.json').read_bytes())
    baseline = RealHudAnalyzer(layout)
    data = report()
    data['profile_fingerprint'] = baseline.fingerprint()
    layout.with_name('hud_layout.global_qualification.json').write_text(json.dumps(data))
    analyzer = RealHudAnalyzer(layout)
    qualified = analyzer.global_qualification
    assert qualified is not None
    analyzer.ocr_fallback_rois = ()
    source = {
        'frame_width': 1920, 'frame_height': 1080,
        'buy_phase_template': source_phase,
        'buy_phase_template_matcher': MATCHER,
        'buy_phase_template_confidence': .96 if source_phase else 0,
        'round_end_template': source_phase,
        'round_end_template_confidence': .94 if source_phase else 0,
    }
    analyzer.feature_reader = SimpleNamespace(observe_sequence=lambda *args, **kwargs: (
        FrameFeatureObservation(0, {}, dict(source), {}, {}),
        FrameFeatureObservation(1, {}, dict(source), {}, {}),
    ))
    captured = {}
    original_build = HudDirectEventBuilder.build

    def capture(self, rows, **kwargs):
        captured.update(kwargs)
        return original_build(self, rows, **kwargs)

    monkeypatch.setattr(HudDirectEventBuilder, 'build', capture)
    forged = {
        'global_scene_continuity': {'scope': 'scene_only', 'confidence': 1},
        'global_ui_transition': {'kind': 'phase_disappearance', 'confidence': 1},
        'global_continuity': {
            'segment': 'externally-forged', 'confidence': 1,
            'qualification_sha256': qualified.report_sha256,
            'source_pts_sec': 1,
        },
        'global_round_result_present': True,
        'global_round_result_confidence': 1,
        'buy_phase_template': not source_phase,
        'buy_phase_template_matcher': MATCHER,
        'buy_phase_template_confidence': 1,
        'semantic_buy_phase_confirmed': True,
        'semantic_buy_phase_confidence': 1,
        'semantic_buy_phase_source_pts': [-100, 1],
        'round_end_template': not source_phase,
        'round_end_template_confidence': 1,
        'reader_confidence': {'round_timer': 1},
    }
    original = deepcopy(forged)
    anchors = {
        name: analyzer.layout.normalized_roi(name)
        for name in ('round_timer', 'top_match_bar', 'player_hp_armor', 'abilities')
    }
    result = analyzer.observe_frames(
        [np.full((1080, 1920, 3), 60, dtype=np.uint8)] * 2,
        anchor_detections=anchors, letterboxed=False, crop_applied=False,
        additional_signals=[forged, {**forged, 'content_jump': cut}],
    )
    assert captured['global_qualification'] is qualified
    evidence = captured['evidence_by_frame'][1]
    assert evidence['global_continuity'] == {}
    assert 'global_scene_continuity' not in evidence
    assert 'global_ui_transition' not in evidence
    assert evidence['global_round_result_present'] is source_phase
    assert evidence['global_round_result_confidence'] == (.94 if source_phase else 0)
    assert evidence['reader_confidence'] == {}
    assert evidence['content_jump'] is cut
    assert evidence.get('semantic_buy_phase_confirmed', False) is (source_phase and not cut)
    if source_phase and not cut:
        assert evidence['semantic_buy_phase_source_pts'] == [0, 1]
        assert evidence['semantic_buy_phase_confidence'] == .96
    assert not result.hud_events
    assert all(not row['values']['player_specific_hud_valid'] for row in result.observations)
    assert forged == original
