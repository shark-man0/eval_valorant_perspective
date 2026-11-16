"""Read the shared timeline's exact-sample Camera evidence for Map research."""

from __future__ import annotations

import math
from collections.abc import Sequence
from typing import Any

from .evidence import digest, is_sha

_VETO_SIGNALS = frozenset({
    "spectator", "remote", "downed", "death", "revival", "result", "intermission", "report",
})


def measure_recorder_view(
    frame: dict[str, Any], observations: Sequence[dict[str, Any]],
) -> tuple[str | None, bool]:
    """Return the measured Camera supplier and whether any current rows veto it.

    The producer fingerprint identifies a recording's ability-bar prototype.
    This consumer neither learns it nor interprets the panel image.
    """
    ids = frame.get("observation_ids", ())
    if not observations or set(ids) != {row.get("observation_id") for row in observations}:
        return None, bool(observations)
    if len(observations) != len(set(ids)):
        return None, True
    if any(
        row.get("sample") != frame.get("sample")
        or digest({k: v for k, v in row.items() if k != "observation_id"})
        != row.get("observation_id")
        for row in observations
    ):
        return None, True
    if any(set(row.get("signals", ())) & _VETO_SIGNALS for row in observations):
        return None, True
    if frame.get("round", {}).get("value") in {"ENDED", "INTERMISSION"}:
        return None, True
    rows = [
        row for row in observations if row.get("context", {}).get("stream_kind") == "camera_panel"
    ]
    if len(rows) != 1:
        return None, len(rows) > 1
    row = rows[0]
    camera = frame.get("camera", {})
    mapped = frame.get("map", {})
    if (
        row["observation_id"] not in camera.get("evidence_ids", ())
        and row["observation_id"] not in mapped.get("current_recorder_view_evidence_ids", ())
    ):
        return None, False
    raw = row.get("raw", {})
    panel = raw.get("camera_panel") or {}
    label = panel.get("label") or {}
    score = panel.get("own_ability_bar_score")
    if (
        row.get("signals") != ["owner_hud"]
        or row["context"].get("unqualified_view_model") is True
        or raw.get("qualified") is not False or raw.get("formal_outputs") != 0
        or label.get("checked") is not True or label.get("state") != "ABSENT"
        or not isinstance(score, (float, int)) or isinstance(score, bool)
        or not math.isfinite(score) or not 0 <= score <= 1
        or not is_sha(row.get("producer_fingerprint"))
    ):
        return None, False
    return str(row["producer_fingerprint"]), False
