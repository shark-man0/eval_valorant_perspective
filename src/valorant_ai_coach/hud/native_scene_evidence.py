"""Profile-qualified native scene transport, independent of timer/player facts.

The common image measurement alone never authorizes a proof. This entrance
requires a separately reviewed paired scene/UI qualification bound to the
analyzer's complete configuration. It does not produce UI transitions or events.
"""

from __future__ import annotations

import hashlib
import json
import math
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from valorant_ai_coach.video.native import NativeSourceFrame

from .global_lifecycle import (
    GlobalLifecycleQualification,
    _scene_attested,
    global_recognizer_fingerprint,
)
from .native_scene_input import observe_native_scene_window
from .scene_source_binding import SceneSourceBinding


def collect_native_scene_evidence(
    frames: Sequence[NativeSourceFrame],
    binding: SceneSourceBinding,
    *,
    qualification_path: Path,
    profile_fingerprint: str,
    native_step_ticks: int,
    deferred_initialization: bool = False,
) -> tuple[dict[str, Any], ...]:
    """Buffer source-owned proofs until terminal source/report/code checks pass.

    ``profile_fingerprint`` comes from the analyzer's current base configuration,
    including its configured scene assets. Neither a caller's diagnostic mapping
    nor a saved appearance report is accepted as evidence input.
    """
    if not frames:
        raise ValueError('native source frames required')
    binding.verify()
    qualification = GlobalLifecycleQualification.load(qualification_path, profile_fingerprint)
    if not {'scene_continuity', 'ui_transition'} <= qualification.components:
        raise ValueError('paired scene/UI qualification required for native scene evidence')
    reference_boxes = {
        item['id']: item['world_boxes_640x360']
        for item in json.loads(binding.profile_path.read_bytes())['references']
    }
    measured = observe_native_scene_window(
        frames, binding, native_step_ticks=native_step_ticks,
        deferred_initialization=deferred_initialization,
    )
    segment = f'native_reviewed_scene_v1:{binding.fingerprint()}:{frames[0].source_epoch}'
    rows = []
    for index, (frame, row) in enumerate(zip(frames, measured, strict=True)):
        result = row['scene_measurement']
        evidence: dict[str, Any] = {}
        if result.get('descriptive_scene_link') is True:
            if index == 0:
                raise ValueError('source seed cannot attest a previous native frame')
            prior = frames[index-1]
            if (
                result['source_pts_ticks'] != frame.pts_ticks
                or result['previous_source_pts_ticks'] != prior.pts_ticks
                or result['source_pixel_sha256'] != frame.pixel_sha256
                or result['previous_source_pixel_sha256'] != prior.pixel_sha256
                or result['source_epoch'] != frame.source_epoch
                or result['profile_sha256'] != binding.profile_sha256
            ):
                raise ValueError('measured native scene provenance mismatch')
            # Multiple reviewed domains may share a spatial cell. Preserve all
            # domains in the measurement; aggregate each cell by its worst NCC.
            cells: dict[tuple[int, int], float] = {}
            seen_regions: set[int] = set()
            boxes = reference_boxes[result['reference_id']]
            for witness in result['witnesses']:
                region = witness['region']
                if (
                    type(region) is not int or not 0 <= region < len(boxes)
                    or region in seen_regions
                ):
                    raise ValueError('invalid measured source region')
                seen_regions.add(region)
                box = boxes[region]
                if witness['previous_box_640x360'] != box:
                    raise ValueError('measured source region belongs to another profile')
                x1, y1, x2, y2 = box
                cell = (int((y1+y2)/240), int((x1+x2)*3/1280))
                value = witness['fixed_projection_ncc']
                if type(value) not in (int, float):
                    raise ValueError('numeric measured domain score required')
                score = float(value)
                if not math.isfinite(score) or not 0.90 <= score <= 1.0:
                    raise ValueError('qualified finite domain NCC >= 0.90 required')
                cells[cell] = min(cells.get(cell, score), score)
            ordered = sorted(cells)
            proof = {
                'segment': segment, 'scope': 'scene_only',
                'clock_independent': True, 'background_checked': True,
                'qualification_sha256': qualification.report_sha256,
                'profile_fingerprint': qualification.profile_fingerprint,
                'recognizer_fingerprint': qualification.recognizer_fingerprint,
                'source_video_sha256': frame.source_video_sha256,
                'source_epoch': frame.source_epoch, 'source_time_base': str(frame.time_base),
                'source_pts_ticks': frame.pts_ticks, 'previous_source_pts_ticks': prior.pts_ticks,
                'source_pts_sec': frame.time_sec, 'previous_source_pts_sec': prior.time_sec,
                'source_pixel_sha256': frame.pixel_sha256,
                'previous_source_pixel_sha256': prior.pixel_sha256,
                'scene_profile_sha256': binding.profile_sha256,
                'witness_cells': [list(cell) for cell in ordered],
                'witness_ncc': [cells[cell] for cell in ordered],
                'confidence': min(cells.values()) if cells else 0.0,
                'confidence_semantics': 'minimum qualified domain appearance NCC',
                'method': 'native_reviewed_scene_v1',
            }
            if not _scene_attested(proof, {'time_sec': prior.time_sec}, qualification):
                raise ValueError('native scene evidence fails lifecycle source contract')
            evidence['global_scene_continuity'] = proof
        rows.append({**row, 'system_scene_evidence': evidence})
    binding.verify()
    for frame in frames:
        frame.read_image()  # Verify buffered source assets before returning any proof.
    if (
        hashlib.sha256(qualification_path.read_bytes()).hexdigest() != qualification.report_sha256
        or global_recognizer_fingerprint() != qualification.recognizer_fingerprint
    ):
        raise ValueError('native qualification or recognition code changed during measurement')
    return tuple(rows)
