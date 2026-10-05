"""Opt-in, bounded HUD crops. Images require human privacy review before Git add."""

from __future__ import annotations

import math
from pathlib import Path


def failure_times(evaluation, assertions, limit):
    identifiers = {
        part
        for code in evaluation.get("failures", [])
        if isinstance(code, str)
        for part in code.split(":")[1:]
    }
    times = set()
    for group in assertions.values():
        if not isinstance(group, list):
            continue
        for req in group:
            if not isinstance(req, dict) or req.get("id") not in identifiers:
                continue
            timestamp = req.get("time_sec")
            window = req.get("acceptance_window") or req.get("core_interval") or req.get("window")
            if timestamp is None and isinstance(window, list) and len(window) == 2:
                timestamp = sum(window) / 2
            if (
                isinstance(timestamp, (int, float))
                and not isinstance(timestamp, bool)
                and math.isfinite(timestamp)
                and timestamp >= 0
            ):
                times.add(float(timestamp))
    return sorted(times)[:limit]


def export_evidence(
    *, video, trace, evaluation, assertions, output, shared, limit, ffprobe_bin="ffprobe"
):
    import cv2

    from valorant_ai_coach.hud.layout import HudLayout
    from valorant_ai_coach.resources import resource_path
    from valorant_ai_coach.video import VideoService

    del trace
    if not 1 <= limit <= 10:
        raise ValueError("Evidence limit must be in [1,10]")
    service = VideoService(ffprobe_bin)
    metadata = service.probe(video)
    layout = HudLayout.load(resource_path("config/hud_layout_1080p_v3.json"))
    if layout.reference_resolution != (metadata.width, metadata.height):
        raise ValueError("Evidence crop requires native reference resolution")
    times = failure_times(evaluation, assertions, limit)
    frames = service.extract_frames(
        video,
        times,
        Path(output) / "evidence-local",
        max_dimension=None,
        max_frames=limit,
        metadata=metadata,
    )
    target = Path(shared) / "evidence"
    target.mkdir(parents=True, exist_ok=True)
    files = []
    for index, frame in enumerate(frames):
        image = cv2.imread(str(frame.path))
        if image is None:
            raise ValueError("Evidence image unreadable")
        # Never export the whole screen, minimap, chat, kill feed or player labels.
        left, top, right, bottom = layout.normalized_roi("player_hp_armor").pixel_bounds(
            metadata.width, metadata.height
        )
        crop = image[top:bottom, left:right]
        name = f"hud_{index:02d}.jpg"
        if not cv2.imwrite(str(target / name), crop, [cv2.IMWRITE_JPEG_QUALITY, 75]):
            raise OSError("Evidence export failed")
        files.append(name)
    return files
