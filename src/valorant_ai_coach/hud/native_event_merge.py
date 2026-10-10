"""Revalidate native system boundaries before joining sampled processing.

This consumes an in-memory production result, not a saved event/GT file. Native
observations never replace sampled player facts or sampling timestamps.
"""

from __future__ import annotations

import hashlib
from collections.abc import Sequence
from copy import deepcopy
from fractions import Fraction
from typing import Any

from valorant_ai_coach.video import FrameSample

from .global_lifecycle import GlobalLifecycleQualification, GlobalRoundLifecycle
from .models import timer_display_evidence
from .native_lifecycle import NativeLifecycleAnalysis
from .temporal import _event

SOURCE_KEYS = (
    'source_video_sha256', 'source_epoch', 'source_pts_ticks',
    'source_time_base', 'source_pts_sec', 'source_pixel_sha256',
)


def validate_sampled_source_images(frames: Sequence[FrameSample]) -> None:
    """Recheck decoder-bound images before publishing joined observations."""
    for frame in frames:
        if (frame.source_pts_ticks is not None
                and hashlib.sha256(frame.path.read_bytes()).hexdigest()
                != frame.source_image_sha256):
            raise ValueError('sampled decoder image changed')


def merge_native_timer_displays(
    sampled: Sequence[dict[str, Any]], analysis: NativeLifecycleAnalysis,
    *, frames: Sequence[FrameSample] | None = None,
) -> list[dict[str, Any]]:
    """Join source-preserved global clocks at exact PTS after boundary validation.

    The processor validates the analyzer-owned analysis against its source and
    current qualification before calling this and revalidates it at completion.
    No nearest-frame lookup, interpolation, state replacement or player facts.
    Existing conflicting sampled values are retained rather than overwritten.
    """
    qualification = analysis.qualification
    if qualification is None or 'timer' not in qualification.components:
        raise ValueError('qualified native timer required')
    if tuple(r['system_observation'] for r in analysis.source_rows) != analysis.observations:
        raise ValueError('native observation transport mismatch')
    by_time = {row['source_pts_sec']: row for row in analysis.source_rows}
    if len(by_time) != len(analysis.source_rows):
        raise ValueError('duplicate native observation timestamp')
    merged = deepcopy(list(sampled))
    if frames is not None:
        validate_sampled_source_images(frames)
    if frames is not None and len(frames) != len(merged):
        raise ValueError('sampled frame/observation coverage mismatch')
    by_tick = {(row['source_video_sha256'], row['source_pts_ticks'],
                Fraction(row['source_time_base'])): row for row in analysis.source_rows}
    for index, observation in enumerate(merged):
        source = by_time.get(observation['time_sec'])
        if frames is not None:
            source = None  # Legacy sampled images have no decoder identity.
            frame = frames[index]
            if frame.time_sec != observation['time_sec']:
                raise ValueError('sampled frame/observation timestamp mismatch')
            if frame.source_pts_ticks is not None:
                if frame.source_video_sha256 not in {
                    row['source_video_sha256'] for row in analysis.source_rows
                }:
                    raise ValueError('sampled decoder source differs from native source')
                source = by_tick.get((frame.source_video_sha256, frame.source_pts_ticks,
                                      Fraction(str(frame.source_time_base))))
        if source is None:
            continue
        native = source['system_observation']
        if (native['primary_state'] not in {'unknown', 'live_first_person'}
                or native['quality'].get('occluded_rois')
                or observation['quality'].get('occluded_rois')):
            continue
        timer = timer_display_evidence(native['values'])
        confidence = native['quality']['roi_confidence'].get('round_timer_value')
        if (timer is None or timer['provenance']['confidence'] < .90
                or isinstance(confidence, bool) or not isinstance(confidence, (int, float))
                or not .90 <= confidence <= 1):
            continue
        values = observation['values']
        if (values.get('round_time_remaining_sec') not in {
                None, native['values']['round_time_remaining_sec'],
            } or values.get('round_time_remaining_display') is not None
                or values.get('round_time_remaining_display_provenance') is not None):
            continue
        for key in ('round_time_remaining_sec', 'round_time_remaining_display',
                    'round_time_remaining_display_provenance'):
            values[key] = deepcopy(native['values'][key])
        observation['quality']['roi_confidence']['round_timer_value'] = confidence
    return merged


def native_source_breaks(analysis: NativeLifecycleAnalysis) -> tuple[float, ...]:
    """Recover assured source cuts from replay, never saved diagnostic claims."""
    if analysis.unedited_input_contract is None:
        return ()
    from .native_assured_start import replay_assured_starts

    if analysis.qualification is None:
        raise ValueError('native source breaks require qualification')
    _, diagnostics = replay_assured_starts(
        analysis.source_rows, analysis.qualification, analysis.unedited_input_contract,
    )
    previous = 0
    cuts = []
    for row, diagnostic in zip(analysis.source_rows, diagnostics, strict=True):
        segment = diagnostic['continuity_segment']
        if segment != previous and row['source_pts_sec'] > 0:
            cuts.append(float(row['source_pts_sec']))
        previous = segment
    return tuple(cuts)


def validated_native_boundaries(
    analysis: NativeLifecycleAnalysis,
    qualification: GlobalLifecycleQualification,
    source_video_sha256: str,
    *, continuity_breaks: Sequence[float] | None = None,
) -> tuple[dict[str, Any], ...]:
    """Replay the qualified lifecycle and reject altered/stale transport output."""
    if analysis.unedited_input_contract is not None:
        from .native_assured_start import replay_assured_starts
        from .unedited_input import UneditedInputContract

        if analysis.input_contract_path is None or analysis.qualification != qualification:
            raise ValueError('assured contract/qualification required')
        contract = UneditedInputContract.load(
            analysis.input_contract_path, source_video_sha256=source_video_sha256,
        )
        if contract != analysis.unedited_input_contract:
            raise ValueError('native input contract changed')
        if tuple(r['system_observation'] for r in analysis.source_rows) != analysis.observations:
            raise ValueError('native observation transport mismatch')
        events, diagnostics = replay_assured_starts(analysis.source_rows, qualification, contract)
        if events != analysis.hud_events:
            raise ValueError('assured boundary differs from qualified lifecycle replay')
        if continuity_breaks is not None:
            if tuple(continuity_breaks) != native_source_breaks(analysis):
                raise ValueError('native source-break transport mismatch')
        elif events:
            first_event = min(event['time_sec'] for event in events)
            segment = events[0]['attributes']['evidence_provenance']['continuity_segment']
            # The package builder does not yet receive native break timestamps.
            # Publishing even a lone earlier start could extend a partial package
            # across the break. Reject the join until segment-local fragments are
            # transported; do not manufacture an end to truncate the package.
            if any(row['source_pts_sec'] >= first_event
                   and diagnostic['continuity_segment'] != segment
                   for row, diagnostic in zip(analysis.source_rows, diagnostics, strict=True)):
                raise ValueError('native discontinuity requires segment-local package transport')
        return deepcopy(events)
    if continuity_breaks:
        raise ValueError('unexpected source breaks for paired native lifecycle')
    if analysis.input_contract_path is not None:
        raise ValueError('unexpected native input contract path')
    if not {'scene_continuity', 'ui_transition'} <= qualification.components:
        raise ValueError('paired native lifecycle qualification required')
    if analysis.qualification != qualification:
        raise ValueError('native transport qualification/code/profile changed')
    rows = analysis.source_rows
    if not rows or tuple(row['system_observation'] for row in rows) != analysis.observations:
        raise ValueError('native observation transport mismatch')
    first = rows[0]
    lifecycle = GlobalRoundLifecycle(qualification)
    expected = []
    by_time = {row['source_pts_sec']: row for row in rows}
    cadence = rows[1]['source_pts_ticks'] - first['source_pts_ticks'] if len(rows) > 1 else None
    for index, row in enumerate(rows):
        if (
            row['source_video_sha256'] != source_video_sha256
            or row['source_epoch'] != first['source_epoch']
            or row['source_time_base'] != first['source_time_base']
            or type(row['source_pts_ticks']) is not int
            or row['source_pts_ticks'] < 0
            or float(row['source_pts_ticks'] * Fraction(row['source_time_base']))
            != row['source_pts_sec']
            or row['system_observation']['time_sec'] != row['source_pts_sec']
            or (index and (
                cadence is None or cadence <= 0
                or row['source_pts_ticks'] - rows[index - 1]['source_pts_ticks'] != cadence
            ))
        ):
            raise ValueError('native source identity/cadence mismatch')
        values = row['system_observation']['values']
        if values.get('player_specific_hud_valid') is not False or any(
            values.get(key) is not None
            for key in ('hp', 'armor', 'weapon_text', 'ammo_current', 'ammo_reserve')
        ):
            raise ValueError('native lifecycle cannot transport player-owned facts')
        evidence = row['system_evidence']
        if set(evidence) - {
            'global_scene_continuity', 'global_ui_transition',
            'global_round_result_present', 'global_round_result_confidence',
        }:
            raise ValueError('unexpected native lifecycle evidence')
        proof = evidence.get('global_scene_continuity')
        if proof is not None and (
            not index or any(proof.get(key) != row[key] for key in SOURCE_KEYS)
            or proof.get('previous_source_pts_ticks') != rows[index - 1]['source_pts_ticks']
            or proof.get('previous_source_pixel_sha256') != rows[index - 1]['source_pixel_sha256']
        ):
            raise ValueError('native scene source pair mismatch')
        transition = evidence.get('global_ui_transition')
        if transition is not None and any(
            transition.get(key) != row[key] for key in SOURCE_KEYS
        ):
            raise ValueError('native UI source identity mismatch')
        for decision in lifecycle.advance(row['system_observation'], evidence):
            source = by_time.get(decision.time_sec)
            if source is None:
                raise ValueError('native boundary source frame missing')
            attributes = deepcopy(decision.attributes)
            attributes['evidence_provenance'].update({key: source[key] for key in SOURCE_KEYS})
            event = _event(decision.kind, decision.time_sec, 'system', attributes,
                           decision.confidence, cross_checked=True)
            event.pop('_candidate_confidence')
            event.pop('_cross_checked')
            expected.append(event)
    if tuple(expected) != analysis.hud_events:
        raise ValueError('native boundary transport differs from qualified lifecycle replay')
    return tuple(deepcopy(expected))


def merge_native_boundaries(
    sampled_events: Sequence[dict[str, Any]], native_events: Sequence[dict[str, Any]],
) -> tuple[dict[str, Any], ...]:
    """Keep sampled facts; reject competing boundary producers rather than relabel."""
    combined = deepcopy(list(sampled_events))
    sampled_boundaries = [e for e in combined if e['type'] in {'round_start', 'round_end'}]
    for event in native_events:
        if event['type'] not in {'round_start', 'round_end'} or event['actor'] != 'system':
            raise ValueError('native merge accepts only system round boundaries')
    if native_events and any(event not in native_events for event in sampled_boundaries):
        raise ValueError('sampled/native boundary conflict')
    for event in native_events:
        if event not in combined:
            combined.append(deepcopy(event))
    combined.sort(key=lambda event: float(event['time_sec']))
    identifiers = [event['event_id'] for event in combined]
    if len(identifiers) != len(set(identifiers)):
        raise ValueError('sampled/native event ID collision')
    return tuple(combined)
