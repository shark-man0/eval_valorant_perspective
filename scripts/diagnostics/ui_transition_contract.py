"""Diagnostic temporal prototype; never produces continuity proofs or events.

Input scene support is descriptive, not runtime qualification. All display
values are retained. Stable text does not prove uninterrupted game time.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from valorant_ai_coach.hud.round_lifecycle import (
    MAX_SAMPLE_GAP_SEC,
    MIN_START_CONFIRMATION_SEC,
)


@dataclass
class TransientUiDiagnostic:
    state: str = "unobserved"
    previous_pts: float | None = None
    phase_first_pts: float | None = None
    phase_last_pts: float | None = None
    phase_count: int = 0
    armed: bool = False
    transient_pts: float | None = None
    display_run_start: float | None = None
    last_display: str | None = None
    display_history: list[dict[str, Any]] = field(default_factory=list)

    def reset_context(self) -> None:
        self.state = "unobserved"
        self.phase_first_pts = self.phase_last_pts = self.transient_pts = None
        self.display_run_start = None
        self.last_display = None
        self.phase_count = 0
        self.armed = False

    def advance(
        self,
        pts: float,
        *,
        phase_confirmed: bool,
        display: str | None,
        scene_supported: bool,
        content_jump: bool = False,
        duplicate_pixels: bool = False,
    ) -> dict[str, Any]:
        if type(pts) not in (int, float) or not math.isfinite(pts):
            raise ValueError("finite source PTS required")
        gap_invalid = self.previous_pts is not None and not (
            0 < pts - self.previous_pts <= MAX_SAMPLE_GAP_SEC
        )
        veto = content_jump or duplicate_pixels or gap_invalid
        supported = scene_supported and not veto
        self.display_history.append({"pts_sec": pts, "display": display})
        if veto or not scene_supported:
            self.reset_context()
        elif phase_confirmed:
            if self.state == "transient_ui_transition":
                self.reset_context()
            if self.phase_first_pts is None:
                self.phase_first_pts = pts
            self.phase_last_pts = pts
            self.phase_count += 1
            self.armed = (
                self.phase_count >= 2 and pts - self.phase_first_pts >= MIN_START_CONFIRMATION_SEC
            )
            self.state = "pre_round" if self.armed else "phase_candidate"
            self.transient_pts = None
        elif self.armed:
            if self.transient_pts is None:
                self.transient_pts = pts
                self.display_run_start = None
                self.last_display = None
            self.state = "transient_ui_transition"
        else:
            # Separated phase observations must not add up to a confirmed span.
            self.phase_first_pts = self.phase_last_pts = None
            self.phase_count = 0
            self.state = "unobserved"
        if self.state == "transient_ui_transition":
            if display is None or display != self.last_display:
                self.display_run_start = pts if display is not None else None
            self.last_display = display
        display_stable = (
            self.state == "transient_ui_transition"
            and self.display_run_start is not None
            and pts - self.display_run_start >= MIN_START_CONFIRMATION_SEC
        )
        self.previous_pts = pts
        return {
            "pts_sec": pts,
            "state": self.state,
            "scene_supported_descriptive": supported,
            "content_veto": veto,
            "transient_begin_pts_sec": self.transient_pts,
            "raw_display": display,
            "display_stable": display_stable,
            "clock_semantics": "unqualified",
            "round_event_authorized": False,
        }


def descriptive_support(metrics: Mapping[str, Any]) -> bool:
    """Conservative frozen diagnostic predicate; no runtime qualification.

    It intentionally abstains on low texture/occlusion and camera motion. It
    cannot exclude scene-preserving edits and must never be an event gate.
    """
    regions = metrics["regions"]
    return (
        len(regions) == 6
        and all(r["ncc"] is not None and r["ncc"] >= 0.90 for r in regions)
        and len(metrics["lk_supported_regions"]) >= 3
        and metrics["lk_patch_ncc_0_90_tracks"] >= 3
        and metrics["lk_affine_inliers"] >= 0.90 * metrics["lk_patch_ncc_0_90_tracks"]
    )


def replay(window: Mapping[str, Any]) -> dict[str, Any]:
    links = {r["source_pts_ticks"]: r["image_measurements"] for r in window["rows"]}
    model = TransientUiDiagnostic()
    results = []
    for row in window["historical_display_annotations"]:
        metrics = links.get(row["source_pts_ticks"])
        results.append(
            model.advance(
                row["pts_sec"],
                phase_confirmed=row["phase_confirmed"],
                display=row["timer_display"],
                scene_supported=metrics is not None and descriptive_support(metrics),
            )
        )
    return {
        "rows": results,
        "raw_display_history": model.display_history,
        "scope": "diagnostic prototype only; no events, qualification or canonical result",
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        parser.error("output already exists")
    content = args.input.read_bytes()
    code_hash = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    data = json.loads(content)
    result = {"r1": replay(data["r1"]), "r2": replay(data["r2_frozen_method_transfer"])}
    if (
        args.input.read_bytes() != content
        or hashlib.sha256(Path(__file__).read_bytes()).hexdigest() != code_hash
    ):
        raise ValueError("source/code binding changed")
    result["input_sha256"] = hashlib.sha256(content).hexdigest()
    result["script_sha256"] = code_hash
    result["source_video_sha256"] = data["r1"]["source_video_sha256"]
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + "\n")


if __name__ == "__main__":
    main()
