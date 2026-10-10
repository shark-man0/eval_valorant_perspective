"""Source-bound provisional lifecycle transport; no formal event release."""
from __future__ import annotations

from collections.abc import Sequence
from copy import deepcopy
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any

from valorant_ai_coach.rounds.boundaries import BoundaryObservation
from valorant_ai_coach.video import VideoMetadata
from valorant_ai_coach.video.native import NativeSourceFrame

from .global_lifecycle import global_recognizer_fingerprint
from .native_assured_start import SOURCE_KEYS, validate_assured_row
from .native_system_input import collect_native_system_observations
from .unedited_input import UneditedInputContract
from .unedited_lifecycle import UneditedRoundLifecycle
from .unedited_ui_start import UneditedUiStartTracker

if TYPE_CHECKING:
    from .analyzers import RealHudAnalyzer


@dataclass(frozen=True)
class PracticalLifecycleAnalysis:
    source_rows: tuple[dict[str, Any], ...]
    boundaries: tuple[BoundaryObservation, ...]
    diagnostics: tuple[dict[str, Any], ...]
    native_step_ticks: int
    input_contract: UneditedInputContract
    input_contract_path: Path
    profile_fingerprint: str
    recognizer_fingerprint: str


def validated_practical_boundaries(
    analysis: PracticalLifecycleAnalysis, *, source_video_sha256: str,
    profile_fingerprint: str,
) -> tuple[tuple[BoundaryObservation, ...], tuple[float, ...]]:
    """Revalidate mutable transport before publication and after processing."""
    contract = UneditedInputContract.load(
        analysis.input_contract_path, source_video_sha256=source_video_sha256,
    )
    if (contract != analysis.input_contract
            or analysis.profile_fingerprint != profile_fingerprint
            or analysis.recognizer_fingerprint != global_recognizer_fingerprint()):
        raise ValueError('practical source/profile/recognizer contract changed')
    boundaries, diagnostics = replay_practical_boundaries(
        analysis.source_rows, contract, native_step_ticks=analysis.native_step_ticks,
        profile_fingerprint=profile_fingerprint,
    )
    if boundaries != analysis.boundaries or diagnostics != analysis.diagnostics:
        raise ValueError('practical transport differs from source lifecycle replay')
    cuts = tuple(row['source_pts_sec'] for row, diagnostic in
                 zip(analysis.source_rows, diagnostics, strict=True) if diagnostic['source_break'])
    return boundaries, cuts


def replay_practical_boundaries(
    rows: Sequence[dict[str, Any]], contract: UneditedInputContract, *,
    native_step_ticks: int, profile_fingerprint: str,
) -> tuple[tuple[BoundaryObservation, ...], tuple[dict[str, Any], ...]]:
    """Same temporal predicates as assured strict lifecycle, without qualification.

    Reader acceptance, current-frame context and native source checks remain.
    Missing qualification is represented by provisional status, never a formal
    event. A source gap resets both pending start and end before new evidence.
    """
    if not rows:
        raise ValueError('native source observations required')
    tracker = UneditedRoundLifecycle(
        UneditedUiStartTracker(contract, native_step_ticks=native_step_ticks), None,
        boundary_mode='practical',
    )
    boundaries: list[BoundaryObservation] = []
    diagnostics: list[dict[str, Any]] = []
    segment = 0
    by_time = {row['source_pts_sec']: row for row in rows}
    for index, row in enumerate(rows):
        prior = rows[index - 1] if index else None
        validate_assured_row(row, first=rows[0], prior=prior, index=index,
                             step=native_step_ticks, qualification=None, contract=contract,
                             practical=True)
        evidence = row['system_evidence']
        broken = any(evidence.get(k) is True for k in ('content_jump', 'discontinuity')) or (
            prior is not None and (
                row['source_pts_ticks'] - prior['source_pts_ticks'] != native_step_ticks
                or row['source_epoch'] != prior['source_epoch']
                or row['source_pixel_sha256'] == prior['source_pixel_sha256']
            )
        )
        if broken:
            segment += 1
        decision = tracker.advance(row, phase_scan_valid=evidence['assured_phase_scan_valid'])
        if decision is not None:
            proof = decision.attributes['evidence_provenance']
            proof.update({key: by_time[decision.time_sec][key] for key in SOURCE_KEYS})
            proof.update(profile_fingerprint=profile_fingerprint,
                         recognizer_fingerprint=global_recognizer_fingerprint(),
                         continuity_segment=segment, boundary_mode='practical',
                         qualification_status='unverified', actor='system')
            proof['signals'] = [
                signal.replace('qualified_stable_round_result', 'observed_stable_round_result')
                for signal in proof.get('signals', [])
            ]
            boundaries.append(BoundaryObservation.provisional_from_decision(decision))
        diagnostics.append({'source_pts_ticks': row['source_pts_ticks'], 'state': tracker.state,
                            'continuity_segment': segment, 'source_break': broken})
    return tuple(boundaries), tuple(diagnostics)


def collect_practical_lifecycle(
    analyzer: RealHudAnalyzer, frames: Sequence[NativeSourceFrame], *,
    native_step_ticks: int, input_contract_path: Path,
    video_metadata: VideoMetadata | None = None,
) -> PracticalLifecycleAnalysis:
    """Use configured production readers on decoder-owned pixels, never GT."""
    if not frames or getattr(analyzer, '_native_profile_readers', False) is not True:
        raise ValueError('production native profile readers and source frames required')
    profile = analyzer._base_fingerprint()
    if profile != analyzer._native_loaded_base_fingerprint:
        raise ValueError('native analyzer profile changed; reload analyzer')
    contract = UneditedInputContract.load(
        input_contract_path, source_video_sha256=frames[0].source_video_sha256,
    )
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
        'assured_round_result_present': scan.get('round_result_matched') is True,
        'assured_round_result_confidence': scan.get('round_result_confidence', 0.0),
    }} for row, scan in zip(systems, scans, strict=True))
    boundaries, diagnostics = replay_practical_boundaries(
        rows, contract, native_step_ticks=native_step_ticks, profile_fingerprint=profile,
    )
    for frame in frames:
        frame.read_image()
    if (code != global_recognizer_fingerprint() or profile != analyzer._base_fingerprint()
            or contract != UneditedInputContract.load(
                input_contract_path, source_video_sha256=contract.source_video_sha256)):
        raise ValueError('terminal practical lifecycle inputs changed')
    return PracticalLifecycleAnalysis(rows, boundaries, diagnostics, native_step_ticks,
                                      contract, Path(input_contract_path), profile, code)
