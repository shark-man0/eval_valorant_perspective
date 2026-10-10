"""Deliver verified native decoder pixels/ticks to the common scene episode.

Results remain descriptive. This entrance never manufactures global proofs,
player facts or events from unqualified reference appearance.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from valorant_ai_coach.video.native import NativeSourceFrame

from .scene_episode import ObservedSceneEpisode
from .scene_references import WorldDomainBootstrap
from .scene_source_binding import SceneSourceBinding


def observe_native_scene_window(
    frames: Sequence[NativeSourceFrame],
    binding: SceneSourceBinding,
    *,
    native_step_ticks: int,
    deferred_initialization: bool = False,
) -> tuple[dict[str, Any], ...]:
    binding.verify()
    if not frames:
        raise ValueError('verified native source window required')
    first = frames[0]
    if any(
        frame.time_base != first.time_base
        or frame.source_video_sha256 != first.source_video_sha256
        or frame.source_epoch != first.source_epoch
        for frame in frames
    ):
        raise ValueError('one decoder-owned native source epoch required')
    episode = ObservedSceneEpisode(
        lambda: WorldDomainBootstrap(binding.profile_path),
        native_step_ticks=native_step_ticks,
        deferred_initialization=deferred_initialization,
    )
    rows = []
    for frame in frames:
        result = episode.observe(
            frame.read_image(), frame.pts_ticks, source_epoch=frame.source_epoch,
        )
        rows.append({
            'source_video_sha256': frame.source_video_sha256,
            'source_epoch': frame.source_epoch,
            'source_pts_ticks': frame.pts_ticks,
            'source_time_base': str(frame.time_base),
            'source_pts_sec': frame.time_sec,
            'source_pixel_sha256': frame.pixel_sha256,
            'scene_measurement': result,
        })
    binding.verify()
    return tuple(rows)
