"""Retain a complete native diagnostic chain before attempting a subject link.

This is not content-continuity qualification or a production event producer.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

from .self_victim_link import SelfVictimLink, link_source_player_to_victim
from .subject_death import ProbeFrame, SubjectObservation


@dataclass(frozen=True)
class ContinuousSubjectLink:
    link: SelfVictimLink
    frames: tuple[ProbeFrame, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            'status': self.link.status, 'blockers': list(self.link.blockers),
            'confidence': self.link.confidence,
            'owner': self.link.owner.to_dict() if self.link.owner else None,
            'victim': self.link.victim.to_dict() if self.link.victim else None,
            'source_chain': [asdict(frame) for frame in self.frames],
            'qualified': False, 'content_continuity_qualified': False, 'formal_events': [],
        }


def link_continuous_subject(
    owner: SubjectObservation | None,
    victim: SubjectObservation | None,
    frames: tuple[ProbeFrame, ...], *, native_step_ticks: int,
) -> ContinuousSubjectLink:
    """Verify endpoint inclusion and every intervening native source record.

    A shared segment label alone does not establish adjacency. Unknown, skipped,
    repeated or declared-broken evidence is rejected. Proof hashes are retained,
    not treated as independent qualification of their semantic contents. The
    supplied native cadence is a source contract, never inferred from endpoints.
    """
    if type(native_step_ticks) is not int or native_step_ticks < 1:
        raise ValueError('positive native source cadence required')
    if not isinstance(frames, tuple) or any(not isinstance(f, ProbeFrame) for f in frames):
        raise ValueError('immutable typed frame chain required')

    def unknown(reason: str) -> ContinuousSubjectLink:
        return ContinuousSubjectLink(SelfVictimLink('unknown', (reason,), owner, victim), frames)

    if owner is None or victim is None:
        return unknown('missing_owner_or_victim')
    if not frames:
        return unknown('source_chain_missing')
    if any(a.source.time >= b.source.time for a, b in zip(frames, frames[1:], strict=False)):
        return unknown('source_chain_reordered_or_duplicated')
    owner_positions = [i for i, f in enumerate(frames) if owner in f.observations]
    victim_positions = [i for i, f in enumerate(frames) if victim in f.observations]
    if len(owner_positions) != 1 or len(victim_positions) != 1:
        return unknown('endpoint_observations_not_in_source_chain')
    lo, hi = sorted((owner_positions[0], victim_positions[0]))
    chain = frames[lo:hi+1]
    if any(f.source.context != owner.source.context for f in chain):
        return unknown('source_chain_context_mismatch')
    if any(f.discontinuity for f in chain):
        return unknown('source_chain_discontinuity')
    for previous, current in zip(chain, chain[1:], strict=False):
        if (current.source.pts_ticks-previous.source.pts_ticks != native_step_ticks
                or current.previous_pts_ticks != previous.source.pts_ticks
                or current.continuity_proof_sha256 is None
                or current.source.pixel_sha256 == previous.source.pixel_sha256):
            return unknown('source_chain_gap_or_unproved_continuity')
    linked = link_source_player_to_victim(owner, victim)
    return ContinuousSubjectLink(linked, chain)
