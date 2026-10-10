"""Qualified source-assured boundaries from producer-owned native observations.

Historical start-named entry points remain compatible; qualified result/score
components optionally enable end and subsequent preparation within the epoch.
"""
from __future__ import annotations

from collections.abc import Sequence
from copy import deepcopy
from fractions import Fraction
from pathlib import Path
from typing import TYPE_CHECKING, Any

from valorant_ai_coach.video import VideoMetadata
from valorant_ai_coach.video.native import NativeSourceFrame

from .global_lifecycle import GlobalLifecycleQualification, global_recognizer_fingerprint
from .models import empty_hud_values
from .native_lifecycle import NativeLifecycleAnalysis
from .native_system_input import GLOBAL_VALUES, collect_native_system_observations
from .temporal import _event
from .unedited_input import UneditedInputContract
from .unedited_lifecycle import UneditedRoundLifecycle
from .unedited_ui_start import UneditedUiStartTracker

if TYPE_CHECKING:
    from .analyzers import RealHudAnalyzer

SOURCE_KEYS = (
    'source_video_sha256', 'source_epoch', 'source_pts_ticks',
    'source_time_base', 'source_pts_sec', 'source_pixel_sha256',
)


def current_assured_qualification(
    analyzer: Any, contract: UneditedInputContract,
) -> GlobalLifecycleQualification:
    if getattr(analyzer, '_native_profile_readers', False) is not True:
        raise ValueError('injected readers cannot inherit assured qualification')
    base = analyzer._base_fingerprint()
    if base != analyzer._native_loaded_base_fingerprint:
        raise ValueError('native analyzer profile changed; reload analyzer')
    return GlobalLifecycleQualification.load(
        analyzer.global_qualification_path, base, unedited_input_contract=contract,
    )


def replay_assured_starts(
    rows: Sequence[dict[str, Any]], qualification: GlobalLifecycleQualification,
    contract: UneditedInputContract,
) -> tuple[tuple[dict[str, Any], ...], tuple[dict[str, Any], ...]]:
    if (not {'timer', 'purchase_phase', 'ui_transition'} <= qualification.components
            or qualification.recognizer_fingerprint != global_recognizer_fingerprint()):
        raise ValueError('current reader/UI qualification required')
    if len(rows) < 2:
        raise ValueError('complete native source required')
    first = rows[0]
    step = rows[1]['source_pts_ticks'] - first['source_pts_ticks']
    tracker = UneditedRoundLifecycle(
        UneditedUiStartTracker(contract, native_step_ticks=step), qualification,
    )
    events, diagnostics = [], []
    continuity_segment = 0
    by_time = {r['source_pts_sec']: r for r in rows}
    for index, row in enumerate(rows):
        obs = row['system_observation']
        if (
            row['source_video_sha256'] != contract.source_video_sha256
            or row['source_epoch'] != first['source_epoch']
            or row['source_time_base'] != first['source_time_base']
            or type(row['source_pts_ticks']) is not int
            or float(row['source_pts_ticks'] * Fraction(row['source_time_base']))
            != row['source_pts_sec']
            or obs['time_sec'] != row['source_pts_sec'] or obs['frame_index'] != index
            or (index and row['source_pts_ticks'] - rows[index-1]['source_pts_ticks'] != step)
        ):
            raise ValueError('native source identity/cadence mismatch')
        values = obs['values']
        if (
            values.get('player_specific_hud_valid') is not False
            or obs['view_context']['is_player_world_view_trustworthy'] is not False
            or any(k not in empty_hud_values()
                   or type(v) is not type(empty_hud_values()[k])
                   or v != empty_hud_values()[k]
                   for k, v in values.items() if k not in GLOBAL_VALUES)
        ):
            raise ValueError('assured start cannot transport player-owned facts')
        evidence = row['system_evidence']
        end_keys = {'assured_round_result_present', 'assured_round_result_confidence'}
        phase_keys = {'assured_phase_present', 'assured_phase_confidence'}
        break_keys = {'content_jump', 'discontinuity'}
        if (set(evidence) - break_keys - phase_keys not in ({'assured_phase_scan_valid'},
                                              {'assured_phase_scan_valid'} | end_keys)
                or any(type(evidence[k]) is not bool for k in break_keys & set(evidence))
                or type(evidence['assured_phase_scan_valid']) is not bool):
            raise ValueError('producer-owned phase scan evidence required')
        if set(evidence) & phase_keys and (
            not phase_keys <= set(evidence)
            or type(evidence['assured_phase_present']) is not bool
            or type(evidence['assured_phase_confidence']) not in (int, float)
            or not 0 <= evidence['assured_phase_confidence'] <= 1
            or evidence['assured_phase_present'] is True
            and (evidence['assured_phase_scan_valid'] is not True
                 or evidence['assured_phase_confidence'] < .90)
        ):
            raise ValueError('producer-owned current phase presence evidence required')
        if set(evidence) & end_keys and (
            not {'score', 'round_result'} <= qualification.components
            or type(evidence['assured_round_result_present']) is not bool
            or type(evidence['assured_round_result_confidence']) not in (int, float)
            or not 0 <= evidence['assured_round_result_confidence'] <= 1
        ):
            raise ValueError('qualified producer-owned result evidence required')
        if (any(evidence.get(k) is True for k in break_keys)
                or index and row['source_pixel_sha256'] == rows[index-1]['source_pixel_sha256']):
            continuity_segment += 1
        decision = tracker.advance(row, phase_scan_valid=evidence['assured_phase_scan_valid'])
        if decision:
            attributes = deepcopy(decision.attributes)
            proof = attributes['evidence_provenance']
            proof.pop('reader_qualification_required', None)
            proof.update(
                qualification_sha256=qualification.report_sha256,
                profile_fingerprint=qualification.profile_fingerprint,
                recognizer_fingerprint=qualification.recognizer_fingerprint,
                continuity_segment=continuity_segment,
            )
            proof.update({key: by_time[decision.time_sec][key] for key in SOURCE_KEYS})
            event = _event(decision.kind, decision.time_sec, 'system', attributes,
                           decision.confidence, cross_checked=True)
            event.pop('_candidate_confidence')
            event.pop('_cross_checked')
            events.append(event)
        diagnostics.append({'source_pts_ticks': row['source_pts_ticks'], 'state': tracker.state,
                            'continuity_segment': continuity_segment})
    return tuple(events), tuple(diagnostics)


def collect_qualified_assured_start(
    analyzer: RealHudAnalyzer, frames: Sequence[NativeSourceFrame], *,
    native_step_ticks: int, input_contract_path: Path,
    video_metadata: VideoMetadata | None = None,
) -> NativeLifecycleAnalysis:
    if not frames:
        raise ValueError('native frames required')
    contract = UneditedInputContract.load(
        input_contract_path, source_video_sha256=frames[0].source_video_sha256,
    )
    qualification = current_assured_qualification(analyzer, contract)
    code = global_recognizer_fingerprint()
    scans: list[dict[str, Any]] = []

    def observe(source: Sequence[NativeSourceFrame]) -> Sequence[dict[str, Any]]:
        measured = analyzer.observe_frames(source, video_metadata, _build_events=False)
        scans.extend(measured.native_ui_measurements)
        return measured.observations

    systems = collect_native_system_observations(
        frames, native_step_ticks=native_step_ticks, observe=observe,
        fingerprint=analyzer.fingerprint,
    )
    if len(scans) != len(systems):
        raise ValueError('native phase scan coverage mismatch')
    rows = tuple({**deepcopy(row), 'system_evidence': {
        'assured_phase_scan_valid': scan.get('phase_scan_valid') is True,
        **({'assured_phase_present': scan['phase_present'],
            'assured_phase_confidence': scan['phase_confidence']}
           if 'phase_present' in scan else {}),
        **{key: True for key in ('content_jump', 'discontinuity') if scan.get(key) is True},
        **({'assured_round_result_present': scan.get('round_result_matched') is True,
            'assured_round_result_confidence': scan.get('round_result_confidence', 0.0)}
           if {'score', 'round_result'} <= qualification.components else {}),
    }} for row, scan in zip(systems, scans, strict=True))
    events, diagnostics = replay_assured_starts(rows, qualification, contract)
    for frame in frames:
        frame.read_image()
    if (code != global_recognizer_fingerprint()
            or current_assured_qualification(analyzer, contract) != qualification
            or UneditedInputContract.load(input_contract_path,
                                         source_video_sha256=contract.source_video_sha256)
            != contract):
        raise ValueError('terminal assured lifecycle inputs changed')
    return NativeLifecycleAnalysis(
        rows, tuple(r['system_observation'] for r in rows), events, diagnostics,
        qualification, contract, Path(input_contract_path),
    )
