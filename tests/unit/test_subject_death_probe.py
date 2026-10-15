"""Synthetic contract tests: never evidence of real-video subject accuracy."""
import json
from dataclasses import replace

import pytest

from valorant_ai_coach.experimental.subject_death import (
    DeathProbeDecision,
    ProbeFrame,
    ReviewStatus,
    SourceBinding,
    SubjectDeathProbe,
    SubjectObservation,
    SubjectRelation,
    SubjectRole,
    serialize_observation,
)

HASH = 'a' * 64
TOKEN = 'b' * 64


def source(tick=0, **changes):
    return replace(SourceBinding(HASH, tick, 1, 60, 'segment-0', HASH, HASH, HASH, HASH),
                   **changes)


def evidence(tick, role, **changes):
    region = {
        SubjectRole.SOURCE_PLAYER_BINDING: (0, 0, 10, 10),
        SubjectRole.VICTIM: (20, 0, 30, 10),
        SubjectRole.DEATH_TRANSITION: (40, 0, 50, 10),
    }.get(role, (60, 0, 70, 10))
    return replace(SubjectObservation(
        f'{role}-{tick}', source(tick), role, SubjectRelation.SELF, TOKEN, .96,
        str(role), region, ReviewStatus.SOURCE_REVIEWED, HASH,
    ), **changes)


def frame(tick, observations=(), **changes):
    kwargs = dict(source=source(tick), observations=tuple(observations),
                  previous_pts_ticks=tick-1 if tick else None,
                  continuity_proof_sha256=HASH if tick else None)
    kwargs.update(changes)
    return ProbeFrame(**kwargs)


def seeded_probe():
    probe = SubjectDeathProbe(native_step_ticks=1, max_corroboration_sec=1)
    probe.observe(frame(0, [evidence(0, SubjectRole.SOURCE_PLAYER_BINDING),
                            evidence(0, SubjectRole.VICTIM)]))
    return probe


def test_complete_synthetic_candidate_keeps_time_confidence_provenance_but_never_releases():
    probe = seeded_probe()
    decision = probe.observe(frame(1, [evidence(1, SubjectRole.DEATH_TRANSITION,
                                             confidence=.91)]))
    assert decision.status == 'candidate'
    assert decision.boundary_time_sec == 1/60 == decision.confirmation_time_sec
    assert decision.confidence == .91
    assert len(decision.evidence) == 3
    assert decision.to_dict()['formal_events'] == []
    assert decision.to_dict()['qualified'] is False
    assert 'production_adoption_not_authorized' in decision.blockers
    encoded = json.loads(json.dumps(decision.to_dict()))
    assert encoded['evidence'][0]['source']['video_sha256'] == HASH


def test_late_subject_binding_preserves_actual_transition_time():
    probe = SubjectDeathProbe(native_step_ticks=1, max_corroboration_sec=1)
    probe.observe(frame(0, [evidence(0, SubjectRole.VICTIM),
                            evidence(0, SubjectRole.DEATH_TRANSITION)]))
    decision = probe.observe(frame(1, [evidence(1, SubjectRole.SOURCE_PLAYER_BINDING)]))
    assert decision.status == 'candidate'
    assert decision.boundary_time_sec == 0 and decision.confirmation_time_sec == 1/60


@pytest.mark.parametrize('changes', [
    {'relation': SubjectRelation.UNKNOWN}, {'relation': SubjectRelation.NONSELF},
    {'relation': SubjectRelation.TEAMMATE}, {'relation': SubjectRelation.ENEMY},
    {'review_status': ReviewStatus.CANDIDATE}, {'confidence': None}, {'confidence': .89},
])
def test_unproved_self_victim_never_becomes_complete_candidate(changes):
    probe = SubjectDeathProbe(native_step_ticks=1, max_corroboration_sec=1)
    probe.observe(frame(0, [evidence(0, SubjectRole.SOURCE_PLAYER_BINDING),
                            evidence(0, SubjectRole.VICTIM, **changes)]))
    assert probe.observe(frame(1, [evidence(1, SubjectRole.DEATH_TRANSITION)])).status == 'unknown'


@pytest.mark.parametrize('role', [SubjectRole.REPORT, SubjectRole.SPECTATOR, SubjectRole.KILLER])
def test_persistent_report_spectator_or_self_killer_is_not_self_victim(role):
    probe = SubjectDeathProbe(native_step_ticks=1, max_corroboration_sec=1)
    for tick in range(10):
        decision = probe.observe(frame(tick, [evidence(tick, role)]))
        assert decision.status == 'unknown' and decision.to_dict()['formal_events'] == []


@pytest.mark.parametrize('changes', [
    {'segment_id': 'segment-1'}, {'video_sha256': 'c'*64},
    {'profile_fingerprint': 'c'*64}, {'code_fingerprint': 'c'*64},
    {'dependencies_fingerprint': 'c'*64},
])
def test_no_join_across_changed_context(changes):
    probe = seeded_probe()
    src = source(1, **changes)
    e = evidence(1, SubjectRole.DEATH_TRANSITION, source=src)
    assert probe.observe(frame(1, [e], source=src)).status == 'unknown'


@pytest.mark.parametrize('kwargs', [
    {'discontinuity': True}, {'continuity_proof_sha256': None}, {'previous_pts_ticks': 9},
])
def test_no_join_across_broken_or_unproved_continuity(kwargs):
    assert seeded_probe().observe(frame(1, [evidence(1, SubjectRole.DEATH_TRANSITION)],
                                       **kwargs)).status == 'unknown'


def test_missing_and_reordered_native_frames_reset_pending():
    for tick in [2, 0]:
        assert seeded_probe().observe(frame(tick, [evidence(tick, SubjectRole.DEATH_TRANSITION)]
                                            )).status == 'unknown'


def test_confirmation_horizon_is_explicit_not_gt_or_boundary_tolerance():
    probe = SubjectDeathProbe(native_step_ticks=1, max_corroboration_sec=.01)
    probe.observe(frame(0, [evidence(0, SubjectRole.SOURCE_PLAYER_BINDING),
                            evidence(0, SubjectRole.VICTIM)]))
    assert probe.observe(frame(1, [evidence(1, SubjectRole.DEATH_TRANSITION)])).status == 'unknown'


def test_duplicate_episode_suppression_and_ambiguous_respawn_does_not_rearm():
    probe = seeded_probe()
    first = probe.observe(frame(1, [evidence(1, SubjectRole.DEATH_TRANSITION)]))
    assert first.status == 'candidate'
    assert probe.observe(frame(2)).status == 'duplicate'
    probe.observe(frame(3, [evidence(3, SubjectRole.RESPAWN,
                                    relation=SubjectRelation.UNKNOWN)]))
    probe.observe(frame(4, [evidence(4, SubjectRole.SOURCE_PLAYER_BINDING),
                            evidence(4, SubjectRole.VICTIM)]))
    again = probe.observe(frame(5, [evidence(5, SubjectRole.DEATH_TRANSITION)]))
    assert again.status == 'duplicate'


def test_reviewed_self_respawn_clears_episode_and_cannot_reuse_old_pending_evidence():
    probe = seeded_probe()
    probe.observe(frame(1, [evidence(1, SubjectRole.DEATH_TRANSITION)]))
    probe.observe(frame(2, [evidence(2, SubjectRole.RESPAWN)]))
    assert probe.observe(frame(3, [evidence(3, SubjectRole.DEATH_TRANSITION)])).status == 'unknown'


@pytest.mark.parametrize('overrides', [
    {'method': str(SubjectRole.VICTIM)}, {'roi': (20, 0, 30, 10)},
    {'subject_token': 'c'*64},
])
def test_conflicting_subject_or_shared_evidence_cannot_qualify_independence(overrides):
    decision = seeded_probe().observe(frame(1, [evidence(1, SubjectRole.DEATH_TRANSITION,
                                                       **overrides)]))
    assert decision.status == 'unknown'


def test_same_frame_is_not_temporal_corroboration():
    probe = SubjectDeathProbe(native_step_ticks=1, max_corroboration_sec=1)
    assert probe.observe(frame(0, [evidence(0, r) for r in (
        SubjectRole.SOURCE_PLAYER_BINDING, SubjectRole.VICTIM, SubjectRole.DEATH_TRANSITION,
    )])).status == 'unknown'


@pytest.mark.parametrize('confidence', [True, '0.99', float('nan'), float('inf'), -.1, 1.1])
def test_invalid_confidence_rejected(confidence):
    with pytest.raises(ValueError):
        evidence(0, SubjectRole.VICTIM, confidence=confidence)


@pytest.mark.parametrize('changes', [
    {'pts_ticks': True}, {'time_base_den': 0}, {'time_base_num': -1},
    {'pixel_sha256': 'not-a-hash'}, {'segment_id': ''},
])
def test_invalid_source_rejected(changes):
    with pytest.raises(ValueError):
        source(**changes)


def test_serialization_has_no_confidence_defaults_or_review_upgrade():
    observed = evidence(0, SubjectRole.VICTIM, confidence=None,
                        review_status=ReviewStatus.CANDIDATE, review_sha256=None)
    assert SubjectObservation.from_dict(json.loads(serialize_observation(observed))) == observed
    assert observed.review_status == ReviewStatus.CANDIDATE
    with pytest.raises((ValueError, TypeError, KeyError)):
        SubjectObservation.from_dict({'confidence': .99})  # Old/absent data is never a grant.
    with pytest.raises(ValueError):
        evidence(0, SubjectRole.VICTIM, review_sha256=None)


def test_mismatched_frame_and_duplicate_evidence_ids_rejected():
    e = evidence(0, SubjectRole.VICTIM)
    with pytest.raises(ValueError):
        frame(1, [e])
    with pytest.raises(ValueError):
        frame(0, [e, e])
    with pytest.raises(ValueError):
        frame(0, [{}])


def test_unknown_decision_preserves_source_and_never_supplies_alive_or_actor():
    d = DeathProbeDecision('unknown', ('missing_subject',), source()).to_dict()
    assert d['source']['pts_ticks'] == 0
    assert not {'actor', 'player_alive', 'hp', 'weapon'} & set(d)
    assert d['formal_events'] == [] and not d['qualified']


def test_other_subject_respawn_cannot_rearm_a_latched_episode():
    probe = seeded_probe()
    probe.observe(frame(1, [evidence(1, SubjectRole.DEATH_TRANSITION)]))
    probe.observe(frame(2, [evidence(2, SubjectRole.RESPAWN, subject_token='c'*64)]))
    probe.observe(frame(3, [evidence(3, SubjectRole.SOURCE_PLAYER_BINDING),
                            evidence(3, SubjectRole.VICTIM)]))
    decision = probe.observe(frame(4, [evidence(4, SubjectRole.DEATH_TRANSITION)]))
    assert decision.status == 'duplicate'


def test_current_role_contradiction_invalidates_earlier_self_support():
    probe = seeded_probe()
    probe.observe(frame(1, [evidence(1, SubjectRole.VICTIM,
                                    relation=SubjectRelation.NONSELF)]))
    decision = probe.observe(frame(2, [evidence(2, SubjectRole.DEATH_TRANSITION)]))
    assert decision.status == 'unknown'
    assert 'missing_source_player_binding' in decision.blockers
