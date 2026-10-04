"""Offline comparison of legacy global-detail veto and local icon measurement.

Private JSON input: an ordered array of objects with frame_path/time_sec only.
Times come from analyzer extraction, never GT. Output is aggregate only. This
script does not supply identity or facts to the production pipeline.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path

import cv2

from valorant_ai_coach.hud.layout import HudLayout
from valorant_ai_coach.hud.readers import (
    FrameFeatureObservation,
    _flash_features,
    _region_candidate,
    measure_roi,
)
from valorant_ai_coach.hud.spectator_icon import detect_icon, menu_overlay_candidate
from valorant_ai_coach.hud.templates import HudTemplateProfile

# Frozen legacy policy for reproducibility after any production refinement.
LEGACY_HINTS = (
    "map_transition",
    "partial_expanded_map",
    "expanded_map_present",
    "expanded_map_stable",
    "flash_candidate",
    "abrupt_luminance_spike",
    "scene_detail_collapse",
    "visual_transition",
    "buy_menu_grid_present",
)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("private_frames", type=Path)
    parser.add_argument("layout", type=Path)
    parser.add_argument("aggregate_output", type=Path)
    args = parser.parse_args()
    cv2.setNumThreads(3)
    manifest = json.loads(args.private_frames.read_text(encoding="utf-8"))
    if not isinstance(manifest, list) or not manifest:
        raise ValueError("ordered private frame manifest required")
    if any(set(row) != {"frame_path", "time_sec"} for row in manifest):
        raise ValueError("manifest may contain only native frame paths/extraction times")
    paths = [Path(row["frame_path"]) for row in manifest]
    layout = HudLayout.load(args.layout)
    profile = HudTemplateProfile.load(args.layout.with_suffix(".templates.json"))
    spec = profile.raw.get("spectator_icon_detector", {})
    if spec != {"version": 1, "roi": "spectator_icon", "method": "fixed_slot_structure_v1"}:
        raise ValueError("dedicated calibrated icon detector required")
    # Replay only the native fields actually consumed by icon obscuration.
    # Unrelated roster/remote/value readers do not participate in this experiment.
    initial = []
    icon_crops = []
    close_candidates = []
    for path, row in zip(paths, manifest, strict=True):
        frame = cv2.imread(str(path), cv2.IMREAD_COLOR)
        if frame is None:
            raise ValueError("unreadable diagnostic frame")
        h, w = frame.shape[:2]

        def crop(name, frame=frame, width=w, height=h):
            x1, y1, x2, y2 = layout.normalized_roi(name).pixel_bounds(width, height)
            return frame[y1:y2, x1:x2]

        metrics = {
            name: measure_roi(crop(name)) for name in ["center_crosshair_area", "buy_menu_grid"]
        }
        hints = {
            "buy_menu_grid_present": _region_candidate(metrics["buy_menu_grid"], min_edge=0.055)
            >= 0.72
        }
        initial.append(FrameFeatureObservation(float(row["time_sec"]), metrics, hints, {}, {}))
        icon_crops.append(crop("spectator_icon").copy())
        close_candidates.append(menu_overlay_candidate(crop("buy_menu_close_anchor")))
    reasons_before: Counter[str] = Counter()
    reasons_after: Counter[str] = Counter()
    transitions: Counter[str] = Counter()
    for index, (feature, icon, close) in enumerate(
        zip(initial, icon_crops, close_candidates, strict=True)
    ):
        hints = dict(feature.signals)
        hints.update(
            _flash_features(
                initial[index - 1] if index else None,
                feature,
                initial[index + 1] if index + 1 < len(initial) else None,
            )
        )
        before = detect_icon(icon, obscured=close or any(hints.get(k) for k in LEGACY_HINTS))
        after = detect_icon(
            icon,
            obscured=close
            or any(hints.get(k) for k in LEGACY_HINTS if k != "scene_detail_collapse"),
        )
        reasons_before[before["reason"]] += 1
        reasons_after[after["reason"]] += 1
        transitions[f"{before['reason']} -> {after['reason']}"] += 1
    result = {
        "diagnostic_only": True,
        "frame_count": len(paths),
        "legacy_hint_policy": list(LEGACY_HINTS),
        "removed_hint": "scene_detail_collapse",
        "before": dict(reasons_before),
        "after": dict(reasons_after),
        "transitions": dict(transitions),
        "limit": "Obscuration policy comparison only; no live identity/state simulation.",
        "layout_sha256": hashlib.sha256(args.layout.read_bytes()).hexdigest(),
        "profile_fingerprint": profile.fingerprint(args.layout),
    }
    args.aggregate_output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()

