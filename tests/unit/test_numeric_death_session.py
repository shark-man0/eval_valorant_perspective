"""Synthetic image/provider wiring, never independent real-source qualification."""
import hashlib
import json
from dataclasses import replace

import numpy as np
import pytest

from tests.unit import test_numeric_death_release as release_tests
from tests.unit.test_self_death_image_recognizer import HASH, setup
from valorant_ai_coach.experimental.numeric_death_release import (
    NumericSelfDeathEventConsumer,
    QualifiedNumericDeathContract,
    release_fingerprint,
)
from valorant_ai_coach.experimental.numeric_death_session import NumericDeathImageSession
from valorant_ai_coach.experimental.subject_death import (
    ProbeFrame,
    ReviewStatus,
    SourceBinding,
    SubjectObservation,
    SubjectRelation,
    SubjectRole,
)

qualified_release = release_tests.qualified_release


def qualification_for(recognizer, qualified_release):
    _, path = qualified_release
    data = json.loads(path.read_text(encoding='utf-8'))
    data['code_fingerprint'] = recognizer.code_fingerprint
    data['profile_fingerprint'] = recognizer.profile_fingerprint
    path.write_text(json.dumps(data), encoding='utf-8')
    return QualifiedNumericDeathContract.load(path, expected_report_sha256=hashlib.sha256(
        path.read_bytes()).hexdigest())


def provider_for(recognizer, *, damage=None):
    def provider(reading):
        # This entire source review/continuity provider is explicitly SYNTHETIC.
        # No actual qualification provider is installed in the application.
        observations = []

        def add(role, score, method, roi):
            observations.append(SubjectObservation(
                f'{role}-{reading.source.pts_ticks}', reading.source, role,
                SubjectRelation.UNKNOWN if role == SubjectRole.REPORT else SubjectRelation.SELF,
                None if role == SubjectRole.REPORT else 'b'*64, score, method, roi,
                ReviewStatus.SOURCE_REVIEWED, HASH))

        victims = [s for s in reading.subjects if s.role == 'victim']
        if len(victims) == 1:
            victim = victims[0]
            add(SubjectRole.SOURCE_PLAYER_BINDING,
                min(*victim.marker_support, victim.yellow_fraction),
                'killfeed_highlight_shape_color_v1', victim.marker_roi)
            if victim.weapon_support is not None:
                add(SubjectRole.VICTIM, victim.weapon_support,
                    'killfeed_weapon_template_ncc_v1', victim.weapon_roi)
        if reading.report_support is not None and reading.report_support >= .90:
            add(SubjectRole.REPORT, reading.report_support,
                'self_referential_report_caption_ncc_v1', recognizer.report_search_roi)
            if (recognizer.episode.pending_onset == reading.source
                    and recognizer.report_predecessor is not None):
                add(SubjectRole.DEATH_TRANSITION, reading.report_support,
                    'fresh_self_referential_report_caption_ncc_v1', recognizer.report_search_roi)
        tick = reading.source.pts_ticks
        frame = ProbeFrame(reading.source, tuple(observations), tick-1 if tick else None,
                           HASH if tick else None)
        return damage(frame) if damage is not None else frame
    return provider


def observe(session, base, header, tick, *, report=True, marker=True):
    image = base.copy()
    if not marker:
        image[20:40, :90] = image[20:40, 170:220] = 0
    if report:
        image[50:62, 10:60] = np.repeat(header[:, :, None], 3, axis=2)
    image[79, 239] = tick
    recognizer = session.recognizer
    source = SourceBinding(HASH, tick, 1, 60, 'segment',
        hashlib.sha256(image.tobytes()).hexdigest(), recognizer.code_fingerprint,
        recognizer.profile_fingerprint, HASH)
    return session.observe(image, source)


def episode(session, base, header):
    return [observe(session, base, header, 0, report=False, marker=False),
            observe(session, base, header, 1, marker=False),
            *(observe(session, base, header, tick) for tick in range(2, 9))]


def test_actual_synthetic_images_reach_existing_consumer_without_mutating_predictions(
    qualified_release,
):
    recognizer, base, header = setup()
    consumer = NumericSelfDeathEventConsumer(qualification_for(recognizer, qualified_release))
    session = NumericDeathImageSession(recognizer, consumer, provider_for(recognizer))
    rows = episode(session, base, header)
    emitted = [r.event for r in rows if r.event is not None]
    assert len(emitted) == 1
    event = emitted[0]
    assert event['time_sec'] == 1/60 and event['actor'] == 'player'
    assert event['attributes']['evidence_provenance']['confirmation_source']['pts_ticks'] == 5
    assert event['confidence'] <= rows[5].image_reading.support
    assert all(not r.image_reading.qualified and r.image_reading.formal_events == () for r in rows)
    assert len(consumer.released) == 1


@pytest.mark.parametrize('missing', ['qualification', 'provider'])
def test_no_default_qualification_or_provider_can_issue_an_event(qualified_release, missing):
    recognizer, base, header = setup()
    grant = qualification_for(recognizer, qualified_release) if missing == 'provider' else None
    provider = provider_for(recognizer) if missing == 'qualification' else None
    session = NumericDeathImageSession(recognizer, NumericSelfDeathEventConsumer(grant), provider)
    rows = episode(session, base, header)
    assert sum(r.image_reading.status == 'prediction' for r in rows) == 1
    assert all(r.event is None for r in rows)
    assert not session.frames


@pytest.mark.parametrize('failure', ['source', 'continuity', 'discontinuity',
                                   'wrong_roi', 'unknown_subject', 'candidate_review'])
def test_provider_cannot_invent_pixels_identity_review_or_continuity(qualified_release, failure):
    recognizer, base, header = setup()
    grant = qualification_for(recognizer, qualified_release)

    def damage(frame):
        if frame.source.pts_ticks != 3:
            return frame
        if failure == 'source':
            return replace(frame, source=replace(frame.source, pts_ticks=30), observations=())
        if failure == 'continuity':
            return replace(frame, continuity_proof_sha256=None)
        if failure == 'discontinuity':
            return replace(frame, discontinuity=True)
        changed = frame.observations[0]
        if failure == 'wrong_roi':
            changed = replace(changed, roi=(0, 0, 1, 1))
        elif failure == 'unknown_subject':
            changed = replace(changed, relation=SubjectRelation.UNKNOWN)
        else:
            changed = replace(changed, review_status=ReviewStatus.CANDIDATE, review_sha256=None)
        return replace(frame, observations=(changed, *frame.observations[1:]))

    session = NumericDeathImageSession(recognizer, NumericSelfDeathEventConsumer(grant),
                                      provider_for(recognizer, damage=damage))
    rows = episode(session, base, header)
    assert all(r.event is None for r in rows)


def test_review_cannot_inflate_the_recorded_numeric_report_support(qualified_release):
    recognizer, base, header = setup()
    session = NumericDeathImageSession(recognizer, NumericSelfDeathEventConsumer())
    reading = observe(session, base, header, 0).image_reading
    # Explicit synthetic transport corruption, not a new image-recognition score.
    measured = replace(reading, report_support=.95)
    frame = provider_for(recognizer)(measured)
    assert session._measurements_match(measured, frame)
    inflated = replace(frame, observations=tuple(
        replace(o, confidence=.96) if o.role == SubjectRole.REPORT else o
        for o in frame.observations))
    assert not session._measurements_match(measured, inflated)


def test_skipped_native_frame_cannot_reuse_pending_evidence(qualified_release):
    recognizer, base, header = setup()
    session = NumericDeathImageSession(recognizer,
        NumericSelfDeathEventConsumer(qualification_for(recognizer, qualified_release)),
        provider_for(recognizer))
    observe(session, base, header, 0, report=False, marker=False)
    observe(session, base, header, 1, marker=False)
    rows = [observe(session, base, header, tick) for tick in range(3, 9)]
    assert all(r.event is None for r in rows)
    assert session.failed and not session.frames


def test_unknown_evidence_is_not_mutated_into_reviewed_self(qualified_release):
    recognizer, base, header = setup()
    original = []
    provider = provider_for(recognizer)

    def unknown(reading):
        frame = provider(reading)
        changed = replace(frame, observations=tuple(replace(o, relation=SubjectRelation.UNKNOWN,
            subject_token=None, review_status=ReviewStatus.CANDIDATE, review_sha256=None)
            for o in frame.observations))
        original.append(changed)
        return changed

    session = NumericDeathImageSession(recognizer,
        NumericSelfDeathEventConsumer(qualification_for(recognizer, qualified_release)), unknown)
    rows = episode(session, base, header)
    assert all(r.event is None for r in rows)
    assert all(o.relation == SubjectRelation.UNKNOWN and o.review_status == ReviewStatus.CANDIDATE
               for f in original for o in f.observations)


@pytest.mark.parametrize('killer', [False, True])
def test_persistent_report_or_self_killer_does_not_open_a_new_event(qualified_release, killer):
    recognizer, base, header = setup(killer=killer)
    session = NumericDeathImageSession(recognizer,
        NumericSelfDeathEventConsumer(qualification_for(recognizer, qualified_release)),
        provider_for(recognizer))
    rows = [observe(session, base, header, tick) for tick in range(8)]
    assert all(r.event is None for r in rows)


def test_session_code_changes_invalidate_release_contract(qualified_release, monkeypatch):
    from pathlib import Path

    before = release_fingerprint()
    original = Path.read_bytes

    def changed(path):
        data = original(path)
        return data+b'\n# modified session\n' if path.name == 'numeric_death_session.py' else data

    monkeypatch.setattr(Path, 'read_bytes', changed)
    assert release_fingerprint() != before


def test_restored_consumer_suppresses_same_image_episode_in_a_new_session(qualified_release):
    recognizer, base, header = setup()
    qualification = qualification_for(recognizer, qualified_release)
    consumer = NumericSelfDeathEventConsumer(qualification)
    session = NumericDeathImageSession(recognizer, consumer, provider_for(recognizer))
    assert sum(r.event is not None for r in episode(session, base, header)) == 1
    checkpoint = json.loads(json.dumps(consumer.checkpoint()))
    fresh, base, header = setup()
    restored = NumericSelfDeathEventConsumer(qualification)
    restored.restore(checkpoint)
    resumed = NumericDeathImageSession(fresh, restored, provider_for(fresh))
    assert all(r.event is None for r in episode(resumed, base, header))
    assert restored.checkpoint() == checkpoint


def test_native_session_retains_only_the_bounded_onset_window(qualified_release):
    recognizer, base, header = setup()
    session = NumericDeathImageSession(recognizer,
        NumericSelfDeathEventConsumer(qualification_for(recognizer, qualified_release)),
        provider_for(recognizer))
    for tick in range(180):
        assert observe(session, base, header, tick, report=False, marker=False).event is None
        assert len(session.frames) <= 122  # both existing horizons + one predecessor
    assert len(session.frames) == 122


def test_earlier_marker_predecessor_survives_delayed_report_confirmation(qualified_release):
    recognizer, base, header = setup()
    session = NumericDeathImageSession(recognizer,
        NumericSelfDeathEventConsumer(qualification_for(recognizer, qualified_release)),
        provider_for(recognizer))
    rows = [observe(session, base, header, tick, report=tick >= 59, marker=tick >= 1)
            for tick in range(66)]
    events = [r.event for r in rows if r.event is not None]
    assert len(events) == 1
    assert events[0]['time_sec'] == 59/60
    assert events[0]['attributes']['evidence_provenance']['source_chain'][0]['pts_ticks'] == 0


@pytest.mark.parametrize('field', ['source_sha256', 'code_fingerprint', 'profile_fingerprint',
                                 'dependencies_fingerprint', 'native_step_ticks'])
def test_mismatched_qualification_never_calls_the_frame_provider(qualified_release, field):
    recognizer, base, header = setup()
    qualification = qualification_for(recognizer, qualified_release)
    qualification = replace(qualification, **{field: 2 if field == 'native_step_ticks' else 'f'*64})

    def must_not_run(reading):
        raise AssertionError('mismatched qualification must reject before consulting provider')

    session = NumericDeathImageSession(recognizer, NumericSelfDeathEventConsumer(qualification),
                                      must_not_run)
    row = observe(session, base, header, 0, report=False, marker=False)
    assert row.event is None and row.blocker == 'source_or_fingerprint_mismatch'
    assert session.failed and not session.frames
