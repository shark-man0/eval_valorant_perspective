"""Synthetic authorization/transport contracts, never real-video qualification."""
import hashlib
import json
from dataclasses import replace

import pytest

from tests.unit.test_subject_death_probe import evidence, frame, source
from valorant_ai_coach.experimental.numeric_death_release import (
    NumericSelfDeathEventConsumer,
    QualifiedNumericDeathContract,
    release_fingerprint,
)
from valorant_ai_coach.experimental.subject_death import (
    DeathProbeDecision,
    ReviewStatus,
    SubjectRelation,
    SubjectRole,
)


@pytest.fixture
def qualified_release(tmp_path):
    # Entire certificate and all evidence below are explicitly synthetic.
    # No real qualification report is shipped with the implementation.
    report = {
        'schema_version': 'numeric_self_death_qualification_v1', 'source_sha256': 'a'*64,
        'code_fingerprint': 'a'*64, 'profile_fingerprint': 'a'*64,
        'dependencies_fingerprint': 'a'*64, 'native_step_ticks': 1,
        'split_review_sha256': 'c'*64, 'qualification_review_sha256': 'd'*64,
        'component_reviews': {name: 'e'*64 for name in (
            'source_player_binding', 'victim_role', 'report_transition',
            'native_temporal_continuity', 'negative_controls')},
        'release_fingerprint': release_fingerprint(),
        'source_player_subject_token': 'b'*64,
        'evaluation_scope': 'qualified_candidate_evaluation',
    }
    path = tmp_path/'synthetic-release.json'
    path.write_text(json.dumps(report), encoding='utf-8')
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    return QualifiedNumericDeathContract.load(path, expected_report_sha256=digest), path


def proof():
    methods = {
        SubjectRole.SOURCE_PLAYER_BINDING: 'killfeed_highlight_shape_color_v1',
        SubjectRole.VICTIM: 'killfeed_weapon_template_ncc_v1',
        SubjectRole.DEATH_TRANSITION: 'fresh_self_referential_report_caption_ncc_v1',
        SubjectRole.REPORT: 'self_referential_report_caption_ncc_v1',
    }
    chain = []
    for tick in range(7):
        binding = source(tick, pixel_sha256=hashlib.sha256(str(tick).encode('utf-8')).hexdigest())
        observations = []
        if tick == 1:
            observations.append(evidence(tick, SubjectRole.DEATH_TRANSITION,
                source=binding, confidence=.91, method=methods[SubjectRole.DEATH_TRANSITION]))
        if tick >= 2:
            observations.extend(
                evidence(tick, role, source=binding, method=methods[role]) for role in (
                    SubjectRole.SOURCE_PLAYER_BINDING, SubjectRole.VICTIM, SubjectRole.REPORT))
        chain.append(frame(tick, observations, source=binding))
    witnesses = (chain[-1].observations[0], chain[-1].observations[1],
                 chain[1].observations[0])
    decision = DeathProbeDecision('candidate', (
        'recognizer_qualification_missing', 'production_adoption_not_authorized',
    ), chain[-1].source, 1/60, 6/60, .95, witnesses)
    return decision, tuple(chain)


def test_no_qualification_or_unknown_subject_cannot_release_even_a_high_scoring_prediction(
    qualified_release,
):
    decision, chain = proof()
    assert NumericSelfDeathEventConsumer().consume(decision, chain) is None
    consumer = NumericSelfDeathEventConsumer(qualified_release[0])
    for change in ({'relation': SubjectRelation.UNKNOWN}, {'review_status': ReviewStatus.CANDIDATE},
                   {'confidence': None}, {'confidence': .89}):
        changed = replace(decision.evidence[0], **change)
        assert consumer.consume(replace(decision, evidence=(changed, *decision.evidence[1:])),
                                chain) is None
    assert consumer.checkpoint()['released_event_ids'] == []


def test_numeric_release_keeps_onset_actor_all_sources_and_conservative_confidence(
    qualified_release,
):
    decision, chain = proof()
    original = decision.to_dict()
    consumer = NumericSelfDeathEventConsumer(qualified_release[0])
    result = consumer.consume(decision, chain)
    assert result is not None and result['type'] == 'player_death' and result['actor'] == 'player'
    assert result['time_sec'] == 1/60 and result['confidence'] == .91
    provenance = result['attributes']['evidence_provenance']
    assert provenance['native_event_id'] == result['event_id']
    assert provenance['onset_source']['pts_ticks'] == 1
    assert provenance['confirmation_source']['pts_ticks'] == 6
    assert len(provenance['source_chain']) == 7
    assert len(provenance['corroboration_evidence']) == 4
    assert decision.to_dict() == original and original['formal_events'] == []
    assert 'victim_name' not in result['attributes'] and 'damage' not in result['attributes']


@pytest.mark.parametrize('failure', ['gap', 'duplicate_pixels', 'break', 'missing_proof',
                                   'context', 'missing_witness', 'corroboration_gap',
                                   'corroboration_low', 'respawn', 'bad_fingerprint'])
def test_source_corroboration_conflicts_and_missing_numeric_support_reject(
    qualified_release, failure,
):
    decision, original = proof()
    chain = list(original)
    if failure == 'gap':
        del chain[2]
    elif failure == 'duplicate_pixels':
        chain[3] = replace(chain[3], observations=(), source=replace(
            chain[3].source, pixel_sha256=chain[2].source.pixel_sha256))
    elif failure == 'break':
        chain[3] = replace(chain[3], discontinuity=True)
    elif failure == 'missing_proof':
        chain[3] = replace(chain[3], continuity_proof_sha256=None)
    elif failure == 'context':
        chain[3] = replace(chain[3], observations=(), source=replace(
            chain[3].source, segment_id='other'))
    elif failure == 'missing_witness':
        chain[1] = replace(chain[1], observations=())
    elif failure == 'corroboration_gap':
        chain[4] = replace(chain[4], observations=chain[4].observations[:2])
    elif failure == 'corroboration_low':
        chain[4] = replace(chain[4], observations=(
            *chain[4].observations[:2], replace(chain[4].observations[2], confidence=.89)))
    elif failure == 'respawn':
        chain[3] = replace(chain[3], observations=(*chain[3].observations,
            evidence(3, SubjectRole.RESPAWN, source=chain[3].source)))
    else:
        decision = replace(decision, source=replace(decision.source, code_fingerprint='f'*64))
    consumer = NumericSelfDeathEventConsumer(qualified_release[0])
    assert consumer.consume(decision, tuple(chain)) is None
    assert consumer.last_blocker and not consumer.released


def test_event_identity_ignores_decode_session_and_resume_suppresses_duplicates(qualified_release):
    decision, chain = proof()
    consumer = NumericSelfDeathEventConsumer(qualified_release[0])
    result = consumer.consume(decision, chain)
    assert result is not None and consumer.consume(decision, chain) is None
    restored = NumericSelfDeathEventConsumer(qualified_release[0])
    restored.restore(json.loads(json.dumps(consumer.checkpoint())))
    assert restored.consume(decision, chain) is None
    changed_chain = tuple(replace(f, source=replace(f.source, segment_id='fresh-decode'),
        observations=tuple(replace(o, source=replace(o.source, segment_id='fresh-decode'))
                           for o in f.observations)) for f in chain)
    changed = replace(decision, source=changed_chain[-1].source,
        evidence=(changed_chain[-1].observations[0], changed_chain[-1].observations[1],
                  changed_chain[1].observations[0]))
    other = NumericSelfDeathEventConsumer(qualified_release[0]).consume(changed, changed_chain)
    assert other is not None and other['event_id'] == result['event_id']
    assert restored.consume(changed, changed_chain) is None


@pytest.mark.parametrize('bad', [None, True, '0.95', float('nan'), float('inf'), .89, 1.01])
def test_invalid_parent_confidence_cannot_be_replaced_by_high_witness_scores(
    qualified_release, bad,
):
    decision, chain = proof()
    assert NumericSelfDeathEventConsumer(qualified_release[0]).consume(
        replace(decision, confidence=bad), chain) is None


@pytest.mark.parametrize('failure', ['timestamp', 'killer', 'overlap', 'method', 'unknown_blocker',
                                   'other_self_token', 'releasing_code'])
def test_semantic_or_independence_mismatch_is_not_approved_by_certificate(
    qualified_release, failure,
):
    decision, chain = proof()
    qualification = qualified_release[0]
    if failure == 'timestamp':
        decision = replace(decision, boundary_time_sec=decision.confirmation_time_sec)
    elif failure == 'unknown_blocker':
        decision = replace(decision, blockers=(*decision.blockers, 'unproved_continuity'))
    elif failure == 'other_self_token':
        decision = replace(decision, evidence=tuple(
            replace(w, subject_token='c'*64) for w in decision.evidence))
    elif failure == 'releasing_code':
        qualification = replace(qualification, release_code_fingerprint='f'*64)
    else:
        changed = decision.evidence[1]
        if failure == 'killer':
            changed = replace(changed, role=SubjectRole.KILLER)
        elif failure == 'overlap':
            changed = replace(changed, roi=decision.evidence[0].roi)
        else:
            changed = replace(changed, method=decision.evidence[0].method)
        decision = replace(decision, evidence=(decision.evidence[0], changed, decision.evidence[2]))
    assert NumericSelfDeathEventConsumer(qualification).consume(decision, chain) is None


@pytest.mark.parametrize('failure', ['digest', 'source', 'producer', 'bool_step', 'missing_control',
                                   'extra_gt', 'production_scope'])
def test_unapproved_altered_or_incomplete_report_cannot_authorize(qualified_release, failure):
    qualification, path = qualified_release
    data = json.loads(path.read_text(encoding='utf-8'))
    digest = qualification.report_sha256
    if failure == 'source':
        data['source_sha256'] = 'not a source hash'
    elif failure == 'producer':
        data['release_fingerprint'] = '0'*64
    elif failure == 'bool_step':
        data['native_step_ticks'] = True
    elif failure == 'missing_control':
        del data['component_reviews']['negative_controls']
    elif failure == 'production_scope':
        data['evaluation_scope'] = 'production'
    else:
        data['expected_timestamp'] = 1.0
    path.write_text(json.dumps(data), encoding='utf-8')
    if failure != 'digest':
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
    with pytest.raises(ValueError):
        QualifiedNumericDeathContract.load(path, expected_report_sha256=digest)


@pytest.mark.parametrize('change', [
    {'qualification_sha256': 'f'*64}, {'release_fingerprint': 'f'*64}, {'schema_version': True},
    {'released_event_ids': [[]]}, {'released_event_ids': ['SELF-DEATH-'+'z'*64]},
])
def test_mismatched_or_invalid_resume_cannot_reuse_release_state(qualified_release, change):
    consumer = NumericSelfDeathEventConsumer(qualified_release[0])
    with pytest.raises(ValueError):
        consumer.restore({**consumer.checkpoint(), **change})


@pytest.mark.parametrize('value', [True, False])
def test_boolean_flag_cannot_replace_independent_qualification(value):
    with pytest.raises(ValueError, match='no Boolean override'):
        NumericSelfDeathEventConsumer(value)


def test_downstream_fact_scope_change_invalidates_release_qualification(
    qualified_release, monkeypatch,
):
    from pathlib import Path

    original = Path.read_bytes

    def changed(path):
        data = original(path)
        return data+b'\n# simulated Fact policy change\n' if (
            path.name == 'builder.py' and path.parent.name == 'facts') else data

    monkeypatch.setattr(Path, 'read_bytes', changed)
    decision, chain = proof()
    consumer = NumericSelfDeathEventConsumer(qualified_release[0])
    assert consumer.consume(decision, chain) is None
    assert consumer.last_blocker == 'release_consumer_fingerprint_mismatch'


def test_legacy_death_event_normalization_stays_compatible():
    from valorant_ai_coach.facts.builder import FactBuilder

    facts = FactBuilder().build({'events': [{'event_id': 'synthetic-legacy', 'time_sec': 1.0,
        'type': 'player_death', 'actor': 'player', 'attributes': {'cause_known': False},
        'confidence': .95}], 'state_snapshots': []})
    assert next(f for f in facts if f.key == 'player_died').confidence == .95
    first = next(f for f in facts if f.key == 'first_death_by_player')
    assert first.value is True and first.confidence == .9


@pytest.mark.parametrize('role,method', [
    (SubjectRole.VICTIM, 'killfeed_weapon_glyph_geometry_v2'),
    (SubjectRole.VICTIM, 'killfeed_ability_template_ncc_v1'),
    (SubjectRole.DEATH_TRANSITION, 'independent_report_header_ncc_v1'),
    (SubjectRole.SOURCE_PLAYER_BINDING, 'global_timer_value_ncc_v1'),
])
def test_ineligible_method_cannot_become_numeric_self_proof_with_a_high_score(
    qualified_release, role, method,
):
    decision, original = proof()
    chain = tuple(replace(f, observations=tuple(
        replace(o, method=method, confidence=.99) if o.role == role else o
        for o in f.observations)) for f in original)
    decision = replace(decision, evidence=(chain[-1].observations[0],
        chain[-1].observations[1], chain[1].observations[0]))
    assert NumericSelfDeathEventConsumer(qualified_release[0]).consume(decision, chain) is None


def test_independent_header_only_corroborates_a_separate_self_referential_onset(qualified_release):
    decision, original = proof()
    chain = tuple(replace(f, observations=tuple(
        replace(o, method='independent_report_header_ncc_v1', relation=SubjectRelation.UNKNOWN,
                subject_token=None) if o.role == SubjectRole.REPORT else o
        for o in f.observations)) for f in original)
    event = NumericSelfDeathEventConsumer(qualified_release[0]).consume(decision, chain)
    assert event is not None and event['time_sec'] == 1/60 and event['confidence'] == .91


def test_each_corroborating_victim_requires_its_own_numeric_method(qualified_release):
    decision, original = proof()
    chain = list(original)
    chain[4] = replace(chain[4], observations=tuple(
        replace(o, method='killfeed_weapon_glyph_geometry_v2', confidence=.99)
        if o.role == SubjectRole.VICTIM else o for o in chain[4].observations))
    consumer = NumericSelfDeathEventConsumer(qualified_release[0])
    assert consumer.consume(decision, tuple(chain)) is None


@pytest.mark.parametrize('with_attributes', [False, True, 'scoped', 'scoped_unknown'])
def test_approved_synthetic_event_reaches_original_round_fact_and_trace_without_hud_promotion(
    qualified_release, tmp_path, with_attributes,
):
    from copy import deepcopy
    from pathlib import Path
    from types import SimpleNamespace

    from tests.e2e.trace_adapter import to_e2e_trace
    from tests.unit.test_round_package_builder import event, observation
    from valorant_ai_coach.events import EventSourceContract
    from valorant_ai_coach.facts.builder import FactBuilder
    from valorant_ai_coach.rounds import RoundPackageBuilder
    from valorant_ai_coach.schema_validation import SchemaValidator
    from valorant_ai_coach.storage.repository import SQLiteRepository
    from valorant_ai_coach.video import VideoMetadata

    decision, chain = proof()
    attribute_qualification = None
    fields = None
    if with_attributes:
        from tests.unit.test_qualified_death_attributes import attribute_contract, episode_fields

        label = 'other-class' if with_attributes == 'scoped_unknown' else 'agent-class'
        class_scope = ({'schema_version': 'numeric_self_death_attributes_v2',
                        'qualified_killer_agent_labels': [label]}
                       if isinstance(with_attributes, str) else {})
        attribute_qualification = attribute_contract(tmp_path, qualified_release[0], **class_scope)
        fields = episode_fields(chain)
    death = NumericSelfDeathEventConsumer(qualified_release[0],
        attribute_qualification=attribute_qualification).consume(decision, chain,
                                                               episode_fields=fields)
    assert death is not None
    observations = [observation(tick/60, hud_confidence=0.0) for tick in range(7)]
    for row in observations:
        row['primary_state'] = 'unknown'
        row['values']['player_specific_hud_valid'] = False
        row['view_context']['is_player_world_view_trustworthy'] = False
        for key in ('hp', 'armor', 'ammo_current', 'ammo_reserve', 'round_time_remaining_sec',
                    'ally_alive', 'enemy_alive'):
            row['values'][key] = None
    original = deepcopy(observations)
    contract = EventSourceContract.load(Path(__file__).resolve().parents[2]/'config'/
                                        'event_source_contract_v1.json')
    builder = RoundPackageBuilder(contract=contract, validator=SchemaValidator())
    packages = builder.build(
        match_id='SYNTHETIC-RELEASE-CONTRACT',
        video_metadata=VideoMetadata(tmp_path/'synthetic.mp4', .2, 1920, 1080, 60,
                                     'h264', None, False, 0),
        hud_observations=observations,
        hud_events=[event('start-a', 0.0, 'round_start'),
                    event('end-a', 3/60, 'round_end'),
                    event('start-b', 5/60, 'round_start'), death],
    )
    assert len(packages) == 2
    assert [e for e in packages[0]['events'] if e['type'] == 'player_death'] == [death]
    assert not any(e['type'] == 'player_death' for e in packages[1]['events'])
    facts = FactBuilder().build(packages[0])
    died = next(f for f in facts if f.key == 'player_died')
    assert died.value is True and died.confidence == .91 and died.time_sec == 1/60
    assert died.provenance_event_ids == (death['event_id'],)
    assert not any(f.key == 'first_death_by_player' for f in facts)
    assert not any(f.key in {'hp', 'armor', 'weapon', 'player_alive'} for f in facts)
    trace = to_e2e_trace(SimpleNamespace(round_packages=packages, observations=observations))
    traced = [e for e in trace['events'] if e['type'] == 'player_death']
    assert len(traced) == 1 and traced[0]['round_id'] == 'sample_round_1'
    assert traced[0]['actor'] == 'player' and traced[0]['time_sec'] == 1/60
    assert traced[0]['attributes'] == death['attributes'] and traced[0]['confidence'] == .91
    if with_attributes:
        assert traced[0]['attributes']['victim_name'] == 'Recorder'
        if with_attributes == 'scoped_unknown':
            assert 'killer_agent' not in traced[0]['attributes']
        else:
            assert traced[0]['attributes']['killer_agent'] == 'agent-class'
        assert traced[0]['attributes']['combat_report_damage_received'] == 150
    assert all(row['owner'] == 'unknown' for row in trace['ownership_intervals'])
    assert observations == original
    store = SQLiteRepository(tmp_path/'events.sqlite')
    for package in packages:
        store.save_round_package(package)
    saved = store.get_round_package('SYNTHETIC-RELEASE-CONTRACT', 1)
    assert saved is not None
    saved_death = next(e for e in saved['events'] if e['type'] == 'player_death')
    assert json.loads(json.dumps(saved_death)) == json.loads(json.dumps(death))
    SchemaValidator().validate_round_package(saved)
