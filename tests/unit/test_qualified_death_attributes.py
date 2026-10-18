"""Synthetic semantic transport certificates, never real image qualification."""
import hashlib
import json
from dataclasses import replace

import pytest

from tests.unit import test_numeric_death_release as release_tests
from valorant_ai_coach.experimental.death_episode_fields import DeathEpisodeFields, EpisodeField
from valorant_ai_coach.experimental.killfeed_subject import KillfeedSubjectReading
from valorant_ai_coach.experimental.numeric_death_release import (
    NumericSelfDeathEventConsumer,
    release_fingerprint,
)
from valorant_ai_coach.experimental.qualified_death_attributes import (
    QualifiedDeathAttributeContract,
)
from valorant_ai_coach.experimental.report_fatal_row import FatalReportRowReading
from valorant_ai_coach.experimental.self_death_image import SelfDeathImageReading
from valorant_ai_coach.experimental.subject_death import SubjectRelation

qualified_release = release_tests.qualified_release
REPORT = ('b'*64, 'c'*64, 'd'*64)
FATAL = ('e'*64, 'f'*64, 'a'*64)


def attribute_contract(tmp_path, event_qualification, **changes):
    data = {
        'schema_version': 'numeric_self_death_attributes_v1',
        'evaluation_scope': 'qualified_candidate_evaluation',
        'event_qualification_sha256': event_qualification.report_sha256,
        'release_fingerprint': release_fingerprint(), 'split_review_sha256': 'a'*64,
        'component_reviews': {k: 'b'*64 for k in (
            'victim_name', 'killer_agent', 'combat_report_damage_received')},
        'report_producer': list(REPORT), 'fatal_row_producer': list(FATAL),
    }
    data.update(changes)
    path = tmp_path/'synthetic-attribute-review.json'
    path.write_text(json.dumps(data), encoding='utf-8')
    return QualifiedDeathAttributeContract.load(path,
        expected_report_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
        parent_qualification_sha256=event_qualification.report_sha256)


def episode_fields(chain):
    source = chain[3].source
    victim = KillfeedSubjectReading(source, 'victim', (0, 0, 10, 10), (20, 0, 30, 10),
        (31, 0, 39, 10), (.96, .97, .98), .99, 'Recorder', .94, 'synthetic', .96)
    image = SelfDeathImageReading('pending', 'synthetic', source, .96, (victim,))
    report = replace(source, code_fingerprint=REPORT[0], profile_fingerprint=REPORT[1],
                     dependencies_fingerprint=REPORT[2])
    marker = replace(report, code_fingerprint=FATAL[0], profile_fingerprint=FATAL[1],
                     dependencies_fingerprint=FATAL[2])
    damage_roi = (100, 100, 130, 115)
    fatal = FatalReportRowReading(marker, report, 'unqualified_fatal_damage_row',
                                 (100, 116, 130, 125), damage_roi, .92, .96, .92)
    fields = (
        EpisodeField('victim_name', 'Recorder', 'Recorder', source, .94, victim.name_roi,
                     ('killfeed_victim_name_reader',), False, .92, image),
        EpisodeField('damage_received', 150, '150', report, .95, damage_roi,
                     ('tesseract_digits', 'report_header_pose'), False, .92, image, fatal),
        EpisodeField('report_portrait_label', 'agent-class', 'agent-class', report, .96,
                     (140, 100, 160, 120), ('template:agent-class', 'report_header_pose'),
                     False, .92, image),
    )
    return DeathEpisodeFields(chain[1].source, chain[-1].source, fields, ())


def run(qualified_release, tmp_path, *, transform=lambda x: x, attribute_changes=None):
    grant, _ = qualified_release
    contract = attribute_contract(tmp_path, grant)
    if attribute_changes:
        contract = replace(contract, **attribute_changes)
    consumer = NumericSelfDeathEventConsumer(grant, attribute_qualification=contract)
    decision, chain = release_tests.proof()
    episode = transform(episode_fields(chain))
    result = consumer.consume(decision, chain, episode_fields=episode)
    return consumer, result, episode


def test_existing_event_gets_only_separately_qualified_original_attributes(
    qualified_release, tmp_path,
):
    consumer, event, episode = run(qualified_release, tmp_path)
    assert event['time_sec'] == 1/60 and event['actor'] == 'player'
    assert event['confidence'] == .91  # attributes cannot raise the Death score
    assert event['attributes']['victim_name'] == 'Recorder'
    assert event['attributes']['killer_agent'] == 'agent-class'
    assert event['attributes']['combat_report_damage_received'] == 150
    provenance = event['attributes']['evidence_provenance']['qualified_attributes']
    assert all(v['observations'][0]['source']['pts_ticks'] == 3 for v in provenance.values())
    assert provenance['combat_report_damage_received']['observations'][0]['fatal_row']
    assert episode.qualified is False and not consumer.attribute_blockers


def test_event_qualification_never_qualifies_attributes_by_itself(qualified_release):
    decision, chain = release_tests.proof()
    consumer = NumericSelfDeathEventConsumer(qualified_release[0])
    event = consumer.consume(decision, chain, episode_fields=episode_fields(chain))
    assert 'victim_name' not in event['attributes']
    assert 'killer_agent' not in event['attributes']
    assert 'combat_report_damage_received' not in event['attributes']
    assert consumer.attribute_blockers == ('independent_attribute_qualification_missing',)


def test_attribute_certificate_cannot_substitute_for_subject_or_episode_qualification(
    qualified_release, tmp_path,
):
    attributes = attribute_contract(tmp_path, qualified_release[0])
    consumer = NumericSelfDeathEventConsumer(attribute_qualification=attributes)
    decision, chain = release_tests.proof()
    assert consumer.consume(decision, chain, episode_fields=episode_fields(chain)) is None
    assert consumer.last_blocker == 'independent_numeric_qualification_missing'
    assert not consumer.released


def test_image_session_passes_collected_original_name_to_the_qualified_consumer(
    qualified_release, tmp_path,
):
    from tests.unit.test_numeric_death_session import episode, provider_for, qualification_for
    from tests.unit.test_self_death_image_recognizer import setup
    from valorant_ai_coach.experimental.numeric_death_session import NumericDeathImageSession

    model, image, header = setup()
    qualification = qualification_for(model, qualified_release)
    consumer = NumericSelfDeathEventConsumer(qualification,
        attribute_qualification=attribute_contract(tmp_path, qualification))
    session = NumericDeathImageSession(model, consumer, provider_for(model))
    events = [r.event for r in episode(session, image, header) if r.event is not None]
    assert len(events) == 1
    attributes = events[0]['attributes']
    assert attributes['victim_name'] == 'observed-name'
    assert 'killer_agent' not in attributes and 'combat_report_damage_received' not in attributes
    name_provenance = attributes['evidence_provenance']['qualified_attributes']['victim_name']
    sources = name_provenance['observations']
    assert sources[0]['source']['pts_ticks'] == 2
    assert events[0]['time_sec'] == 1/60
    assert len(consumer.released) == 1


@pytest.mark.parametrize('missing', ['victim_name', 'report_portrait_label', 'damage_received'])
def test_missing_attribute_is_not_invented_or_copied_from_another_frame(
    qualified_release, tmp_path, missing,
):
    _, event, _ = run(qualified_release, tmp_path, transform=lambda e: replace(
        e, fields=tuple(f for f in e.fields if f.name != missing)))
    key = {'victim_name': 'victim_name', 'report_portrait_label': 'killer_agent',
           'damage_received': 'combat_report_damage_received'}[missing]
    assert key not in event['attributes']
    assert event['type'] == 'player_death'  # count proof is independent of attribute proof


@pytest.mark.parametrize('bad', [float('nan'), float('inf'), -.1, True, '.95', None, .89, 1.1])
def test_invalid_source_support_cannot_be_an_event_attribute(qualified_release, tmp_path, bad):
    _, event, _ = run(qualified_release, tmp_path, transform=lambda e: replace(
        e, fields=tuple(replace(f, source_confidence=bad) for f in e.fields)))
    assert 'qualified_attributes' not in event['attributes']['evidence_provenance']


@pytest.mark.parametrize('problem', [
    'pixel', 'pts', 'segment', 'video', 'producer', 'fatal_producer', 'fatal_roi',
    'fatal_missing', 'fatal_support', 'name_value', 'name_roi', 'name_support',
    'source_confidence', 'episode', 'conflict',
])
def test_mismatched_source_or_semantics_is_rejected(qualified_release, tmp_path, problem):
    def damage(e):
        fields = list(e.fields)
        if problem in {'pixel', 'pts', 'segment', 'video', 'producer'}:
            changes = {'pixel': {'pixel_sha256': '1'*64}, 'pts': {'pts_ticks': 4},
                'segment': {'segment_id': 'other'}, 'video': {'video_sha256': '1'*64},
                'producer': {'code_fingerprint': '1'*64}}[problem]
            fields = [replace(f, source=replace(f.source, **changes)) for f in fields]
        elif problem.startswith('fatal'):
            row = fields[1].fatal_row
            row = {'fatal_producer': replace(row, source=replace(
                       row.source, profile_fingerprint='1'*64)),
                   'fatal_roi': replace(row, damage_roi=(0, 0, 1, 1)),
                   'fatal_missing': None,
                   'fatal_support': replace(row, marker_support=.89)}[problem]
            fields[1] = replace(fields[1], fatal_row=row)
        elif problem.startswith('name'):
            change = {'name_value': {'value': 'Other'}, 'name_roi': {'roi': (0, 0, 1, 1)},
                      'name_support': {'source_confidence': .99}}[problem]
            fields[0] = replace(fields[0], **change)
        elif problem == 'source_confidence':
            fields = [replace(f, association_support=1.0) for f in fields]
        elif problem == 'episode':
            return replace(e, onset_source=replace(e.onset_source, pts_ticks=0))
        else:
            return replace(e, conflicting_fields=('victim_name', 'report_portrait_label',
                                                  'damage_received'))
        return replace(e, fields=tuple(fields))

    consumer, event, _ = run(qualified_release, tmp_path, transform=damage)
    assert event is not None and consumer.attribute_blockers
    if problem.startswith('fatal'):
        assert 'killer_agent' not in event['attributes']
        assert 'combat_report_damage_received' not in event['attributes']
    elif problem.startswith('name'):
        assert 'victim_name' not in event['attributes']
    else:
        assert 'qualified_attributes' not in event['attributes']['evidence_provenance']


@pytest.mark.parametrize('change', [
    {'event_qualification_sha256': '1'*64}, {'release_code_fingerprint': '1'*64},
])
def test_changed_qualification_never_authorizes_attributes(qualified_release, tmp_path, change):
    _, event, _ = run(qualified_release, tmp_path, attribute_changes=change)
    assert 'qualified_attributes' not in event['attributes']['evidence_provenance']


def test_unknown_or_unreviewed_field_frame_cannot_borrow_confirmation_self(
    qualified_release, tmp_path,
):
    grant, _ = qualified_release
    consumer = NumericSelfDeathEventConsumer(grant,
        attribute_qualification=attribute_contract(tmp_path, grant))
    decision, chain = release_tests.proof()
    episode = episode_fields(chain)
    changed = replace(chain[2], observations=tuple(replace(o, relation=SubjectRelation.UNKNOWN)
                                                 for o in chain[2].observations))
    # Confirmation has an uninterrupted qualified tail (3..6), but the earlier
    # field at tick 2 itself lacks Self; no qualification borrowing is allowed.
    chain = (*chain[:2], changed, *chain[3:])
    episode = replace(episode, fields=tuple(replace(f,
        source=replace(f.source, pts_ticks=2, pixel_sha256=changed.source.pixel_sha256),
        image_witness=replace(f.image_witness, source=changed.source)) for f in episode.fields))
    event = consumer.consume(decision, chain, episode_fields=episode)
    assert event is not None
    assert 'qualified_attributes' not in event['attributes']['evidence_provenance']


def test_attribute_association_cannot_exceed_its_own_reviewed_frame_support(
    qualified_release, tmp_path,
):
    grant, _ = qualified_release
    consumer = NumericSelfDeathEventConsumer(grant,
        attribute_qualification=attribute_contract(tmp_path, grant))
    decision, chain = release_tests.proof()
    episode = episode_fields(chain)
    changed = replace(chain[3], observations=tuple(replace(o, confidence=.90)
                                                  for o in chain[3].observations))
    chain = (*chain[:3], changed, *chain[4:])
    # All field frames remain qualified, but their actual support is below the
    # proposed .92 association. Higher support at confirmation cannot rescue it.
    event = consumer.consume(decision, chain, episode_fields=episode)
    assert event is not None
    assert 'qualified_attributes' not in event['attributes']['evidence_provenance']


def test_checkpoint_binds_optional_attribute_certificate(qualified_release, tmp_path):
    consumer, _, _ = run(qualified_release, tmp_path)
    state = consumer.checkpoint()
    restored = NumericSelfDeathEventConsumer(qualified_release[0],
        attribute_qualification=consumer.attribute_qualification)
    restored.restore(state)
    assert restored.released == consumer.released
    with pytest.raises(ValueError):
        NumericSelfDeathEventConsumer(qualified_release[0]).restore(state)
    state['attribute_qualification_sha256'] = '1'*64
    with pytest.raises(ValueError):
        restored.restore(state)


def test_attribute_consumer_code_change_invalidates_numeric_qualification(
    qualified_release, monkeypatch,
):
    from pathlib import Path

    before = release_fingerprint()
    original = Path.read_bytes

    def changed(path):
        content = original(path)
        return content+b'\n# changed semantic consumer\n' if (
            path.name == 'qualified_death_attributes.py') else content

    monkeypatch.setattr(Path, 'read_bytes', changed)
    assert release_fingerprint() != before
    decision, chain = release_tests.proof()
    consumer = NumericSelfDeathEventConsumer(qualified_release[0])
    assert consumer.consume(decision, chain) is None
    assert consumer.last_blocker == 'release_consumer_fingerprint_mismatch'


@pytest.mark.parametrize('changes', [
    {'schema_version': 'unreviewed'}, {'evaluation_scope': 'production'},
    {'component_reviews': {}}, {'report_producer': []},
    {'event_qualification_sha256': '1'*64}, {'release_fingerprint': '1'*64},
])
def test_incomplete_or_wrong_release_certificate_cannot_load(qualified_release, tmp_path, changes):
    with pytest.raises(ValueError):
        attribute_contract(tmp_path, qualified_release[0], **changes)
