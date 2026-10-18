"""Episode transport regression; synthetic success is not image qualification."""
from dataclasses import replace

import pytest

from tests.unit.test_self_death_image_recognizer import observe, setup
from valorant_ai_coach.experimental.death_episode_fields import (
    DeathEpisodeFieldCollector,
    ReportCandidateFrame,
)
from valorant_ai_coach.experimental.numeric_death_release import NumericSelfDeathEventConsumer
from valorant_ai_coach.experimental.numeric_death_session import NumericDeathImageSession


def readings():
    model, image, header = setup()
    rows = [observe(model, image, header, 0, report=False, marker=False),
            observe(model, image, header, 1, marker=False)]
    rows.extend(observe(model, image, header, tick) for tick in range(2, 9))
    # Exactly one original name reading, absent at confirmation. No copying it
    # into other frames to satisfy the test.
    return [replace(r, subjects=tuple(replace(s, name_text='Player' if i == 3 else None,
               name_confidence=.94 if i == 3 else None) for s in r.subjects))
            for i, r in enumerate(rows)]


def fields(value=150):
    return {
        'damage_received': {'display': str(value), 'value': value, 'confidence': .95,
            'sources': ['tesseract_digits', 'report_header_pose'], 'cross_checked': False,
            'roi_bounds_norm': [.5, .5, .9, .8]},
        'report_portrait_label': {'label': 'agent-class', 'confidence': .96,
            'sources': ['template:agent-class', 'report_header_pose'], 'cross_checked': False,
            'roi_bounds_norm': [.1, .1, .4, .4]},
    }


def report(row, *, value=150, **source_changes):
    source = replace(row.source, code_fingerprint='a'*64, profile_fingerprint='b'*64,
                     dependencies_fingerprint='c'*64, **source_changes)
    return ReportCandidateFrame.from_fields(source, (0, 45, 80, 78), fields(value))


def run(rows, reports):
    collector = DeathEpisodeFieldCollector(1)
    results = [collector.observe(row, reports.get(i)) for i, row in enumerate(rows)]
    return collector, [r for r in results if r is not None]


def test_preserves_earlier_name_and_same_frame_report_with_separate_producer_provenance():
    rows = readings()
    original = report(rows[3])
    collector, results = run(rows, {3: original})
    assert collector.last_blocker is None and len(results) == 1
    result = results[0]
    assert result.onset_source == rows[1].source
    assert result.confirmation_source == rows[5].source
    assert {f.name for f in result.fields} == {
        'victim_name', 'damage_received', 'report_portrait_label'}
    assert all(f.source.pts_ticks == 3 for f in result.fields)
    assert all(f.image_witness == rows[3] for f in result.fields)
    assert all(f.association_support <= f.source_confidence for f in result.fields)
    damage = next(f for f in result.fields if f.name == 'damage_received')
    assert damage.source == original.source and damage.value == 150
    assert damage.source.code_fingerprint != damage.image_witness.source.code_fingerprint
    assert rows[5].subjects[0].name_text is None
    assert result.qualified is False and result.formal_events == ()
    assert 'killer_agent' not in {f.name for f in result.fields}


@pytest.mark.parametrize('change', [
    {'pts_ticks': 30}, {'pixel_sha256': 'd'*64}, {'segment_id': 'other'},
    {'video_sha256': 'd'*64}, {'time_base_den': 120},
])
def test_different_physical_source_never_joins(change):
    rows = readings()
    collector, results = run(rows, {3: report(rows[3], **change)})
    assert results == []
    assert collector.last_blocker == 'episode_report_source_or_producer_mismatch'


def test_mid_episode_report_producer_change_is_not_resigned():
    rows = readings()
    changed = replace(report(rows[4]), source=replace(report(rows[4]).source,
                                                     profile_fingerprint='d'*64))
    collector, results = run(rows, {3: report(rows[3]), 4: changed})
    assert not results and collector.failed


@pytest.mark.parametrize('problem', ['gap', 'duplicate', 'discontinuity', 'producer'])
def test_native_chain_break_poisons_until_explicit_rearm(problem):
    rows = readings()
    if problem == 'gap':
        rows.pop(2)
    elif problem == 'duplicate':
        rows[2] = replace(rows[2], source=replace(rows[2].source,
                                               pixel_sha256=rows[1].source.pixel_sha256))
    elif problem == 'discontinuity':
        rows[2] = replace(rows[2], reason='source_invalid_or_discontinuous')
    else:
        rows[2] = replace(rows[2], source=replace(rows[2].source, code_fingerprint='d'*64))
    collector, results = run(rows, {})
    assert not results and collector.failed and not collector.frames
    collector.reset()
    fresh = [collector.observe(row) for row in readings()]
    assert sum(r is not None for r in fresh) == 1


def test_conflict_drops_only_conflicting_field_and_never_selects_highest_score():
    rows = readings()
    rows[4] = replace(rows[4], subjects=tuple(replace(s, name_text='Other', name_confidence=.99)
                                             for s in rows[4].subjects))
    _, results = run(rows, {3: report(rows[3]), 4: report(rows[4], value=160)})
    result = results[0]
    assert result.conflicting_fields == ('damage_received', 'victim_name')
    assert {f.name for f in result.fields} == {'report_portrait_label'}


@pytest.mark.parametrize('bad', [float('nan'), float('inf'), -.1, 1.1, True, '.99', None, .89])
def test_invalid_report_confidence_cannot_be_transported(bad):
    data = fields()
    data['damage_received']['confidence'] = bad
    with pytest.raises(ValueError):
        ReportCandidateFrame.from_fields(readings()[3].source, (0, 45, 80, 78), data)


@pytest.mark.parametrize('bad', ['victim', 'report', 'name', 'marker', 'ambiguous'])
def test_field_frame_needs_its_own_role_marker_and_report(bad):
    rows = readings()
    original = rows[3]
    subject = original.subjects[0]
    if bad == 'victim':
        rows[3] = replace(original, subjects=(replace(subject, role='killer'),))
    elif bad == 'report':
        rows[3] = replace(original, report_support=.2, report_presence_support=None)
    elif bad == 'name':
        rows[3] = replace(original, subjects=(replace(subject, name_confidence=.89),))
    elif bad == 'marker':
        rows[3] = replace(original, subjects=(replace(subject, yellow_fraction=.89),))
    else:
        rows[3] = replace(original, subjects=(subject, subject))
    _, results = run(rows, {3: report(rows[3])})
    assert all(f.name != 'victim_name' for f in results[0].fields)
    if bad != 'name':
        assert not results[0].fields


def test_report_after_confirmation_not_backfilled_and_inputs_immutable():
    rows = readings()
    data = fields()
    frame = ReportCandidateFrame.from_fields(report(rows[6]).source, (0, 45, 80, 78), data)
    data['damage_received']['value'] = 999
    _, results = run(rows, {6: frame})
    assert {f.name for f in results[0].fields} == {'victim_name'}
    assert '999' not in frame.payload_json


def test_persistent_report_does_not_create_episode():
    model, image, header = setup()
    rows = [observe(model, image, header, i) for i in range(8)]
    _, results = run(rows, {i: report(r) for i, r in enumerate(rows)})
    assert results == []


def test_session_keeps_candidate_fields_even_without_formal_qualification():
    from tests.unit.test_numeric_death_session import episode

    model, image, header = setup()

    def provider(pixels, source):
        del pixels
        if source.pts_ticks != 3:
            return None
        bound = replace(source, profile_fingerprint='b'*64)
        return ReportCandidateFrame.from_fields(bound, (0, 45, 80, 78), fields())

    session = NumericDeathImageSession(model, NumericSelfDeathEventConsumer(),
                                      report_provider=provider)
    rows = episode(session, image, header)
    associated = [r for r in rows if r.episode_fields is not None]
    assert len(associated) == 1
    assert 'damage_received' in {f.name for f in associated[0].episode_fields.fields}
    assert all(r.event is None and r.blocker == 'independent_numeric_qualification_missing'
               for r in rows)


def test_pre_onset_values_are_not_carried_into_a_new_episode():
    rows = readings()
    # The accepted marker/name/Report reading precedes the detector's onset.
    # It must not fill a missing name or Report field inside that episode.
    early = replace(rows[3], source=replace(rows[3].source, pts_ticks=0))
    early = replace(early, subjects=tuple(replace(s, source=early.source) for s in early.subjects))
    rows[0] = early
    rows[3] = replace(rows[3], subjects=tuple(replace(s, name_text=None, name_confidence=None)
                                             for s in rows[3].subjects))
    # Preserve the original detector's source links, not its original tick-0 pixels.
    rows[5] = replace(rows[5], evidence_sources=tuple(
        early.source if s.pts_ticks == 0 else s for s in rows[5].evidence_sources))
    _, results = run(rows, {0: report(early)})
    assert len(results) == 1 and not results[0].fields


def test_serialized_reader_round_trip_preserves_all_original_sources():
    from dataclasses import asdict

    from scripts.diagnostics.replay_death_episode_fields import load_reading

    for row in readings():
        import json

        assert load_reading(json.loads(json.dumps(asdict(row)))) == row


def test_fatal_row_witness_retains_its_producer_and_caps_only_association():
    from valorant_ai_coach.experimental.report_fatal_row import FatalReportRowReading

    rows = readings()
    original = report(rows[3])
    damage_roi = (40, 61, 72, 71)
    marker = FatalReportRowReading(
        replace(original.source, code_fingerprint='d'*64), original.source,
        'unqualified_fatal_damage_row', (45, 72, 65, 76), damage_roi, .92, .96, .92)
    collector = DeathEpisodeFieldCollector(1)
    results = [collector.observe(r, original if i == 3 else None, marker if i == 3 else None)
               for i, r in enumerate(rows)]
    result = next(r for r in results if r is not None)
    damage = next(f for f in result.fields if f.name == 'damage_received')
    assert damage.fatal_row == marker and damage.source == original.source
    assert damage.source_confidence == .95 and damage.association_support == .92
    assert not marker.qualified and not result.qualified
    assert all(f.fatal_row is None for f in result.fields if f.name != 'damage_received')


def test_fatal_row_from_another_frame_never_joins():
    from valorant_ai_coach.experimental.report_fatal_row import FatalReportRowReading

    rows = readings()
    original = report(rows[3])
    marker = FatalReportRowReading(replace(original.source, pts_ticks=999), original.source,
                                  'unqualified_fatal_damage_row')
    collector = DeathEpisodeFieldCollector(1)
    results = [collector.observe(r, original if i == 3 else None, marker if i == 3 else None)
               for i, r in enumerate(rows)]
    assert all(r is None for r in results)
    assert collector.last_blocker == 'fatal_row_source_mismatch'


@pytest.mark.parametrize('bad', [float('nan'), float('inf'), True, '.99', None, .89])
def test_invalid_fatal_label_support_does_not_qualify_damage(bad):
    from valorant_ai_coach.experimental.report_fatal_row import FatalReportRowReading

    rows = readings()
    original = report(rows[3])
    marker = FatalReportRowReading(original.source, original.source,
        'unqualified_fatal_damage_row', (45, 72, 65, 76), (40, 61, 72, 71), bad, .99, .99)
    collector = DeathEpisodeFieldCollector(1)
    results = [collector.observe(r, original if i == 3 else None, marker if i == 3 else None)
               for i, r in enumerate(rows)]
    result = next(r for r in results if r is not None)
    damage = next(f for f in result.fields if f.name == 'damage_received')
    assert damage.fatal_row is None and damage.source_confidence == .95
