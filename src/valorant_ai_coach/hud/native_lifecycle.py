"""Qualified native system observations through lifecycle and event contract.

Only the analyzer-owned entrance gathers inputs. Neither saved diagnostic proofs
nor GT are runtime inputs. A positive absence reference is distinct from a failed
presence match and remains subject to independent whole-producer qualification.
"""

from __future__ import annotations

import hashlib
import math
from collections.abc import Sequence
from copy import deepcopy
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any

from valorant_ai_coach.video import VideoMetadata
from valorant_ai_coach.video.native import NativeSourceFrame

from .global_lifecycle import (
    GlobalLifecycleQualification,
    GlobalRoundLifecycle,
    global_recognizer_fingerprint,
)
from .native_system_input import collect_native_system_observations
from .round_lifecycle import SEMANTIC_PHASE_CONFIDENCE_KEY
from .temporal import _event
from .unedited_input import UneditedInputContract

if TYPE_CHECKING:
    from .analyzers import RealHudAnalyzer


@dataclass(frozen=True)
class NativeLifecycleAnalysis:
    source_rows: tuple[dict[str, Any], ...]
    observations: tuple[dict[str, Any], ...]
    hud_events: tuple[dict[str, Any], ...]
    diagnostics: tuple[dict[str, Any], ...]
    qualification: GlobalLifecycleQualification | None = None
    unedited_input_contract: UneditedInputContract | None = None
    input_contract_path: Path | None = None


def _accepted(value: Any) -> float:
    return float(value) if (
        type(value) in (int, float) and math.isfinite(value) and .90 <= value <= 1
    ) else 0.0


def _join_native_lifecycle(
    system_rows: Sequence[dict[str, Any]],
    scene_rows: Sequence[dict[str, Any]],
    ui_measurements: Sequence[dict[str, Any]],
    qualification: GlobalLifecycleQualification,
) -> NativeLifecycleAnalysis:
    """Internal join of measurements gathered from the same verified frames."""
    if not {'scene_continuity', 'ui_transition'} <= qualification.components:
        raise ValueError('paired native lifecycle qualification required')
    if not system_rows or not len(system_rows) == len(scene_rows) == len(ui_measurements):
        raise ValueError('native producer coverage mismatch')
    binding_keys = (
        'source_video_sha256', 'source_epoch', 'source_pts_ticks',
        'source_time_base', 'source_pts_sec', 'source_pixel_sha256',
    )
    lifecycle = GlobalRoundLifecycle(qualification)
    events, diagnostics, rows = [], [], []
    by_time = {row['source_pts_sec']: row for row in system_rows}
    for index, (system, scene, measurement) in enumerate(zip(
        system_rows, scene_rows, ui_measurements, strict=True,
    )):
        if any(system.get(key) != scene.get(key) for key in binding_keys):
            raise ValueError('native scene/system source binding mismatch')
        observation = system['system_observation']
        if observation['time_sec'] != system['source_pts_sec']:
            raise ValueError('native observation source timestamp mismatch')
        evidence = deepcopy(scene['system_scene_evidence'])
        if set(evidence) - {'global_scene_continuity'}:
            raise ValueError('scene producer cannot supply UI or owned evidence')
        proof = evidence.get('global_scene_continuity')
        if proof is not None:
            prior = system_rows[index - 1] if index else None
            if (
                prior is None
                or any(proof.get(key) != system.get(key) for key in binding_keys)
                or proof.get('previous_source_pts_ticks') != prior['source_pts_ticks']
                or proof.get('previous_source_pts_sec') != prior['source_pts_sec']
                or proof.get('previous_source_pixel_sha256') != prior['source_pixel_sha256']
            ):
                raise ValueError('native scene proof belongs to another frame pair')
            previous_observation = prior['system_observation']
            phase_score = _accepted(previous_observation['quality']['roi_confidence'].get(
                SEMANTIC_PHASE_CONFIDENCE_KEY,
            ))
            absence_score = _accepted(measurement.get('confidence'))
            if (
                phase_score and absence_score
                and measurement.get('phase_absence_matched') is True
                and 'buy_phase_banner' in previous_observation['state_flags']
                and previous_observation['values'].get('buy_phase_visible') is True
                and observation['primary_state'] in {'unknown', 'live_first_person'}
                and not observation['state_flags']
            ):
                evidence['global_ui_transition'] = {
                    **{key: system[key] for key in binding_keys},
                    'qualification_sha256': qualification.report_sha256,
                    'profile_fingerprint': qualification.profile_fingerprint,
                    'recognizer_fingerprint': qualification.recognizer_fingerprint,
                    'kind': 'phase_disappearance',
                    'method': 'positive_phase_absence_reference_v1',
                    'confidence': min(phase_score, absence_score),
                }
            result_score = _accepted(measurement.get('round_result_confidence'))
            if measurement.get('round_result_matched') is True and result_score:
                evidence['global_round_result_present'] = True
                evidence['global_round_result_confidence'] = result_score
        decisions = lifecycle.advance(observation, evidence)
        for decision in decisions:
            source = by_time.get(decision.time_sec)
            if source is None:
                raise ValueError('native boundary has no source frame')
            attributes = deepcopy(decision.attributes)
            attributes['evidence_provenance'].update({
                key: source[key] for key in binding_keys
            })
            event = _event(
                decision.kind, decision.time_sec, 'system', attributes,
                decision.confidence, cross_checked=True,
            )
            # Candidate bookkeeping is private to the HUD builder, and must
            # not escape into the native RoundPackage event schema.
            event.pop('_candidate_confidence')
            event.pop('_cross_checked')
            events.append(event)
        rows.append({**deepcopy(system), 'system_evidence': evidence})
        diagnostics.append({
            'source_pts_ticks': system['source_pts_ticks'], 'state': lifecycle.state,
            'reason': lifecycle.diagnostic_reason,
        })
    return NativeLifecycleAnalysis(
        tuple(rows), tuple(row['system_observation'] for row in rows),
        tuple(events), tuple(diagnostics),
        qualification,
    )


def collect_qualified_native_lifecycle(
    analyzer: RealHudAnalyzer,
    frames: Sequence[NativeSourceFrame],
    *,
    native_step_ticks: int,
    deferred_initialization: bool = False,
    video_metadata: VideoMetadata | None = None,
) -> NativeLifecycleAnalysis:
    """Gather producer-owned inputs and withhold all output on terminal changes."""
    if analyzer.scene_source_binding is None or analyzer.global_qualification is None:
        raise ValueError('bound scene assets and global qualification required')
    qualification = GlobalLifecycleQualification.load(
        analyzer.global_qualification_path, analyzer._base_fingerprint(),
    )
    if qualification != analyzer.global_qualification:
        raise ValueError('native qualification changed; reload analyzer')
    ui_measurements: list[dict[str, Any]] = []

    def observe(source: Sequence[NativeSourceFrame]) -> Sequence[dict[str, Any]]:
        analysis = analyzer.observe_frames(source, video_metadata, _build_events=False)
        ui_measurements.extend(analysis.native_ui_measurements)
        return analysis.observations

    def fingerprint() -> str:
        if analyzer._base_fingerprint() != analyzer._native_loaded_base_fingerprint:
            raise ValueError('native analyzer profile changed; reload analyzer')
        return hashlib.sha256(
            (analyzer.fingerprint() + global_recognizer_fingerprint()).encode()
        ).hexdigest()

    initial = fingerprint()
    systems = collect_native_system_observations(
        frames, native_step_ticks=native_step_ticks, observe=observe, fingerprint=fingerprint,
    )
    scenes = analyzer.collect_qualified_native_scene_window(
        frames, native_step_ticks=native_step_ticks,
        deferred_initialization=deferred_initialization,
    )
    result = _join_native_lifecycle(systems, scenes, ui_measurements, qualification)
    for frame in frames:
        frame.read_image()
    if fingerprint() != initial:
        raise ValueError('native lifecycle inputs changed during processing')
    return result
