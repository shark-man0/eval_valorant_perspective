"""Opt-in semantic attributes for an already qualified numeric Death.

No real qualification is shipped. A separate reviewed certificate must bind
the event qualification and the original Report/fatal-row producers. Merely
collecting a portrait, damage number or name cannot authorize these attributes.
"""
from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from .death_episode_fields import (
    DeathEpisodeFields,
    EpisodeField,
    _accepted,
    _physical,
)
from .subject_death import SourceBinding, _hash

_FIELDS = {
    'victim_name': 'victim_name',
    'killer_agent': 'report_portrait_label',
    'combat_report_damage_received': 'damage_received',
}


def _producer(source: SourceBinding) -> tuple[str, str, str]:
    return (source.code_fingerprint, source.profile_fingerprint,
            source.dependencies_fingerprint)


@dataclass(frozen=True)
class QualifiedDeathAttributeContract:
    """Internal candidate certificate; no HUD/public Schema or identity change.

    The externally trusted digest follows independent semantic and split review.
    This loader checks bindings, not the truth of reviews or split independence.
    A v1 numeric event qualification alone never qualifies any attribute.
    """

    report_sha256: str
    event_qualification_sha256: str
    release_code_fingerprint: str
    split_review_sha256: str
    component_reviews: tuple[tuple[str, str], ...]
    report_producer: tuple[str, str, str]
    fatal_row_producer: tuple[str, str, str]

    @classmethod
    def load(cls, path: Path, *, expected_report_sha256: str,
             expected_event_qualification_sha256: str) -> QualifiedDeathAttributeContract:
        from .numeric_death_release import release_fingerprint

        _hash(expected_report_sha256)
        _hash(expected_event_qualification_sha256)
        content = path.read_bytes()
        if hashlib.sha256(content).hexdigest() != expected_report_sha256:
            raise ValueError('externally reviewed attribute report digest required')
        data = json.loads(content)
        keys = {'schema_version', 'evaluation_scope', 'event_qualification_sha256',
                'release_fingerprint', 'split_review_sha256', 'component_reviews',
                'report_producer', 'fatal_row_producer'}
        if (not isinstance(data, dict) or set(data) != keys
                or data['schema_version'] != 'numeric_self_death_attributes_v1'
                or data['evaluation_scope'] != 'qualified_candidate_evaluation'
                or data['event_qualification_sha256'] != expected_event_qualification_sha256
                or data['release_fingerprint'] != release_fingerprint()
                or not isinstance(data['component_reviews'], dict)
                or set(data['component_reviews']) != set(_FIELDS)):
            raise ValueError('complete exact-release semantic qualification required')
        _hash(data['split_review_sha256'])
        for value in data['component_reviews'].values():
            _hash(value)
        for name in ('report_producer', 'fatal_row_producer'):
            if not isinstance(data[name], list) or len(data[name]) != 3:
                raise ValueError('original code/profile/dependencies required')
            for value in data[name]:
                _hash(value)
        return cls(expected_report_sha256, expected_event_qualification_sha256,
                   data['release_fingerprint'], data['split_review_sha256'],
                   tuple(sorted(data['component_reviews'].items())),
                   tuple(data['report_producer']), tuple(data['fatal_row_producer']))

    def project(self, episode: DeathEpisodeFields | None, *,
                onset: SourceBinding, confirmation: SourceBinding,
                qualified_sources: Mapping[SourceBinding, float],
                ) -> tuple[dict[str, Any], dict[str, Any], tuple[str, ...]]:
        """Keep original field times; omit an entire conflicting semantic field.

        Only the numeric consumer may supply sources after checking each frame's
        current reviewed Self binding, victim and Report. This projection grants
        no subject identity and cannot construct or rescue an Event.
        """
        if (episode is None or episode.onset_source != onset
                or episode.confirmation_source != confirmation):
            return {}, {}, ('original_attribute_episode_missing_or_mismatched',)
        values: dict[str, Any] = {}
        provenance: dict[str, Any] = {}
        blockers = []
        for attribute, name in _FIELDS.items():
            candidates = [f for f in episode.fields if f.name == name]
            if (name in episode.conflicting_fields or not candidates
                    or any(not self._supported(f, qualified_sources, onset, confirmation)
                           for f in candidates)
                    or len({(type(f.value), f.value) for f in candidates}) != 1):
                blockers.append(attribute + ':missing_unqualified_or_conflicting')
                continue
            if attribute == 'victim_name':
                valid = all(self._name_supported(f) for f in candidates)
            elif attribute == 'killer_agent':
                # A class at an arbitrary Report location is insufficient. The
                # reviewed semantic producer must also identify the same-frame
                # fatal damage row; separate semantic qualification is mandatory.
                valid = all(isinstance(f.value, str) and bool(f.value.strip())
                    and 'damage_received' not in episode.conflicting_fields
                    and any(d.name == 'damage_received' and d.source == f.source
                            and self._supported(d, qualified_sources, onset, confirmation)
                            and self._fatal_supported(d) for d in episode.fields)
                    for f in candidates)
            else:
                valid = all(type(f.value) is int and f.value >= 0
                            and self._fatal_supported(f) for f in candidates)
            if not valid:
                blockers.append(attribute + ':semantic_witness_missing_or_mismatched')
                continue
            values[attribute] = candidates[0].value
            provenance[attribute] = {
                'qualification_report_sha256': self.report_sha256,
                'semantic_review_sha256': dict(self.component_reviews)[attribute],
                'observations': [asdict(f) for f in candidates],
            }
        return values, provenance, tuple(blockers)

    def _supported(self, field: EpisodeField, sources: Mapping[SourceBinding, float],
                   onset: SourceBinding, confirmation: SourceBinding) -> bool:
        witness = field.image_witness
        return (witness.source in sources
                and type(field.value) in (str, int)
                and _physical(field.source) == _physical(witness.source)
                and onset.time <= field.source.time <= confirmation.time
                and _accepted(field.source_confidence) and _accepted(field.association_support)
                and field.association_support <= field.source_confidence
                and field.association_support <= sources[witness.source]
                and (field.name == 'victim_name' and field.source == witness.source
                     or field.name != 'victim_name'
                     and _producer(field.source) == self.report_producer))

    @staticmethod
    def _name_supported(field: EpisodeField) -> bool:
        victims = [s for s in field.image_witness.subjects if s.role == 'victim']
        if len(victims) != 1 or victims[0].name_confidence is None:
            return False
        return (len(victims) == 1 and isinstance(field.value, str)
                and bool(field.value.strip()) and victims[0].source == field.source
                and victims[0].normalized_name == field.value
                and victims[0].name_roi == field.roi
                and field.methods == ('killfeed_victim_name_reader',)
                and _accepted(victims[0].name_confidence)
                and field.source_confidence <= victims[0].name_confidence)

    def _fatal_supported(self, field: EpisodeField) -> bool:
        row = field.fatal_row
        if (row is None or not _accepted(row.marker_support)
                or not _accepted(row.header_support) or not _accepted(row.association_support)):
            return False
        assert row.marker_support is not None and row.header_support is not None
        assert row.association_support is not None
        return (row is not None and row.fields_source == field.source
                and _physical(row.source) == _physical(field.source)
                and _producer(row.source) == self.fatal_row_producer
                and row.reason == 'unqualified_fatal_damage_row'
                and row.damage_roi == field.roi and row.marker_roi is not None
                and field.association_support <= min(row.marker_support,
                                                     row.header_support,
                                                     row.association_support))
