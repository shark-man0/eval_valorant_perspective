"""No synthetic source chain grants Self identity, ownership or a Death event."""
from dataclasses import replace

import pytest

from tests.unit.test_self_victim_link import owner_and_victim, source
from valorant_ai_coach.experimental.subject_continuity import link_continuous_subject
from valorant_ai_coach.experimental.subject_death import ProbeFrame


def chain():
    owner, victim = owner_and_victim()
    frames = tuple(ProbeFrame(
        source(i), (owner,) if i == 100 else (victim,) if i == 110 else (),
        previous_pts_ticks=i-1 if i > 100 else None,
        continuity_proof_sha256='a'*64 if i > 100 else None,
    ) for i in range(100, 111))
    return owner, victim, frames


def test_complete_chain_retains_native_provenance_without_releasing_event():
    owner, victim, frames = chain()
    result = link_continuous_subject(owner, victim, frames, native_step_ticks=1)
    assert result.link.status == 'unqualified_self_victim_candidate'
    assert result.frames == frames
    stored = result.to_dict()
    assert len(stored['source_chain']) == 11
    assert stored['source_chain'][0]['source']['pts_ticks'] == 100
    assert stored['source_chain'][-1]['source']['pixel_sha256'] == victim.source.pixel_sha256
    assert stored['qualified'] is False and stored['content_continuity_qualified'] is False
    assert stored['formal_events'] == []
    assert stored['confidence'] <= min(owner.confidence, victim.confidence)


@pytest.mark.parametrize('failure', ['gap', 'reordered', 'duplicated', 'break', 'proof',
                                     'foreign_context', 'previous_pts', 'repeated_pixels'])
def test_shared_endpoint_segment_cannot_hide_an_intermediate_failure(failure):
    owner, victim, original = chain()
    frames = list(original)
    if failure == 'gap':
        del frames[5]
    elif failure == 'reordered':
        frames[4], frames[5] = frames[5], frames[4]
    elif failure == 'duplicated':
        frames.insert(5, frames[5])
    else:
        changes = {
            'break': {'discontinuity': True},
            'proof': {'continuity_proof_sha256': None},
            'foreign_context': {'source': source(105, segment='other')},
            'previous_pts': {'previous_pts_ticks': 103},
            'repeated_pixels': {'source': replace(source(105),
                                                pixel_sha256=source(104).pixel_sha256)},
        }
        frames[5] = replace(frames[5], **changes[failure])
    result = link_continuous_subject(owner, victim, tuple(frames), native_step_ticks=1)
    assert result.link.status == 'unknown' and result.to_dict()['formal_events'] == []
    assert owner.source.context == victim.source.context  # endpoint labels alone are insufficient


def test_endpoint_binding_must_be_present_in_chain_not_just_matching_pts():
    owner, victim, frames = chain()
    result = link_continuous_subject(replace(owner, subject_token='9'*64), victim,
                                     frames, native_step_ticks=1)
    assert result.link.status == 'unknown'
    assert 'endpoint_observations_not_in_source_chain' in result.link.blockers


def test_missing_inputs_and_bad_cadence_do_not_link():
    owner, victim, frames = chain()
    absent = link_continuous_subject(None, victim, frames, native_step_ticks=1)
    assert absent.link.status == 'unknown'
    assert absent.frames == frames
    assert link_continuous_subject(owner, victim, (), native_step_ticks=1).link.status == 'unknown'
    for invalid in (True, 0, -1, '1', None):
        with pytest.raises(ValueError):
            link_continuous_subject(owner, victim, frames, native_step_ticks=invalid)
