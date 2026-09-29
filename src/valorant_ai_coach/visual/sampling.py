from __future__ import annotations

import json
import math
from collections.abc import Sequence

from valorant_ai_coach.resources import resource_path
from valorant_ai_coach.video.sampling import SampleRequest


def micro_requests(
    duration: float, triggers: Sequence[tuple[float, str]]
) -> tuple[SampleRequest, ...]:
    policy = json.loads(
        resource_path("config/visual_v2/config/visual_sampling_policy_v2.json").read_text()
    )
    fps = next(item["fps"] for item in policy["passes"] if item["id"] == "C_micro_candidate")
    intervals = []
    for timestamp, kind in triggers:
        if not math.isfinite(timestamp) or not 0 <= timestamp <= duration:
            continue
        left, right = policy["candidate_windows"].get(kind, [-0.5, 1.0])
        intervals.append((max(0.0, timestamp + left), min(duration, timestamp + right)))
    merged: list[list[float]] = []
    for left, right in sorted(intervals):
        if merged and left <= merged[-1][1]:
            merged[-1][1] = max(merged[-1][1], right)
        else:
            merged.append([left, right])
    requests: dict[float, SampleRequest] = {}
    for left, right in merged:
        for index in range(math.ceil((right - left) * fps) + 1):
            timestamp = round(min(right, left + index / fps), 6)
            requests[timestamp] = SampleRequest(timestamp, ("visual_micro",))
    return tuple(requests[key] for key in sorted(requests))
