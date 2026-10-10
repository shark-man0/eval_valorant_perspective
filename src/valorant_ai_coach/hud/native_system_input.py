"""Native global observations, with source binding and no owned facts or proofs.

This transport is separate from qualification: measured timer/phase/score inputs
cannot attest source continuity or authorize a boundary merely by being present.
"""

from __future__ import annotations

import re
from collections.abc import Callable, Sequence
from copy import deepcopy
from typing import Any

from valorant_ai_coach.video.native import NativeSourceFrame

from .models import HudObservationV2, empty_hud_values
from .semantic_text import CONFIDENCE_KEY as PHASE_CONFIDENCE_KEY

GLOBAL_VALUES = frozenset({
    'round_time_remaining_sec', 'round_time_remaining_display',
    'round_time_remaining_display_provenance', 'score_ally', 'score_enemy',
    'buy_phase_visible', 'round_end_text', 'combat_report_visible',
})
GLOBAL_CONFIDENCES = frozenset({
    'round_timer_value', 'score_ally_value', 'score_enemy_value',
    'ally_score_value', 'enemy_score_value', PHASE_CONFIDENCE_KEY,
})


def collect_native_system_observations(
    frames: Sequence[NativeSourceFrame],
    *,
    native_step_ticks: int,
    observe: Callable[[Sequence[NativeSourceFrame]], Sequence[dict[str, Any]]],
    fingerprint: Callable[[], str],
) -> tuple[dict[str, Any], ...]:
    """Buffer one contiguous decoder epoch; reject terminal input/code changes.

    ``observe`` is the configured production analyzer, never an external evidence
    file. There are no GT, timestamp substitutions or supplemental signal inputs.
    Context state/flags remain intact so spectator/menu/remote guards survive.
    """
    frames = tuple(frames)
    if not frames or type(native_step_ticks) is not int or native_step_ticks <= 0:
        raise ValueError('nonempty native window and positive cadence required')
    first = frames[0]
    if (
        not isinstance(first, NativeSourceFrame)
        or not first.source_epoch or first.time_base <= 0
        or re.fullmatch(r'[0-9a-f]{64}', first.source_video_sha256) is None
    ):
        raise ValueError('decoder-owned source identity required')
    for index, frame in enumerate(frames):
        if (
            not isinstance(frame, NativeSourceFrame)
            or type(frame.pts_ticks) is not int or frame.pts_ticks < 0
            or frame.time_base != first.time_base
            or frame.source_epoch != first.source_epoch
            or frame.source_video_sha256 != first.source_video_sha256
            or (frame.width, frame.height) != (first.width, first.height)
            or (index and frame.pts_ticks - frames[index - 1].pts_ticks != native_step_ticks)
        ):
            raise ValueError('one contiguous native decoder epoch required')
        frame.read_image()
    initial_fingerprint = fingerprint()
    observations = tuple(observe(frames))
    if len(observations) != len(frames):
        raise ValueError('native observation coverage mismatch')
    rows = []
    for index, (frame, raw) in enumerate(zip(frames, observations, strict=True)):
        observation = HudObservationV2.from_dict(raw)
        if observation.time_sec != frame.time_sec or observation.frame_index != index:
            raise ValueError('native observation PTS/index mismatch')
        values = empty_hud_values()
        values.update({key: deepcopy(value) for key, value in observation.values.items()
                       if key in GLOBAL_VALUES})
        quality = deepcopy(observation.quality)
        quality['roi_confidence'] = {
            key: value for key, value in quality['roi_confidence'].items()
            if key in GLOBAL_CONFIDENCES
        }
        projected = HudObservationV2(
            time_sec=frame.time_sec, frame_index=index,
            primary_state=observation.primary_state, state_flags=observation.state_flags,
            values=values, quality=quality, remote_view_type=observation.remote_view_type,
            is_player_world_view_trustworthy=False,
        )
        rows.append({
            'source_video_sha256': frame.source_video_sha256,
            'source_epoch': frame.source_epoch, 'source_pts_ticks': frame.pts_ticks,
            'source_time_base': str(frame.time_base), 'source_pts_sec': frame.time_sec,
            'source_pixel_sha256': frame.pixel_sha256,
            'input_fingerprint': initial_fingerprint,
            'system_observation': projected.to_dict(),
            'system_evidence': {},
        })
    for frame in frames:
        frame.read_image()
    if fingerprint() != initial_fingerprint:
        raise ValueError('native analyzer inputs changed during observation')
    return tuple(rows)
