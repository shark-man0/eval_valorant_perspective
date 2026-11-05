"""Source-blind observation adapter over the existing configured HUD readers.

This class receives pixels only. Match identity, native time, labels, previous
states and a recorder roster are deliberately unavailable to its recognizer.
It does not issue qualified ownership or implement another state machine.
"""

from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import Any

import cv2
import numpy as np
from numpy.typing import NDArray

from valorant_ai_coach.hud.analyzers import RealHudAnalyzer, _detect_letterbox
from valorant_ai_coach.hud.identity import live_identity
from valorant_ai_coach.hud.templates import HudTemplateProfile, SubregionReader
from valorant_ai_coach.hud.timer_glyphs import StrictTimerGlyphReader

from .clock_components import clock_components
from .evidence import digest
from .replay import file_sha, read_json
from .round_scope import PixelRoundScope


def _reject_identity_configuration(value: Any) -> None:
    forbidden = {
        "source_id",
        "source_sha256",
        "physical_match_id",
        "recorder_agent_id",
        "acquisition_ids",
        "initial_state",
        "review_sha256",
    }
    if isinstance(value, dict):
        if forbidden & set(value):
            raise ValueError(
                "Observer configuration cannot contain match identity or initialization"
            )
        for key, child in value.items():
            # Asset provenance may retain training Source hashes. Those records
            # are not recognizer conditions and are never supplied to inspect().
            if key != "phase_reference_provenance":
                _reject_identity_configuration(child)
    elif isinstance(value, list):
        for child in value:
            _reject_identity_configuration(child)


class ProfileHudObserver:
    """One frozen pixel reader configuration for every admitted match.

    Geometry/identity gates are reused, never relaxed for unread frames. Other
    agents, unconfigured views and unclear pixels may therefore stay UNKNOWN.
    """

    def __init__(self, config_path: Path) -> None:
        config = read_json(config_path)
        keys = set(config) - {"clock_prefix"}
        if keys not in (
            {"layout", "profile"},
            {"layout", "profile", "structural_bank", "result_method"},
        ):
            raise ValueError("Common pixel reader configuration required")
        self.clock_prefix = config.get("clock_prefix", False)
        if type(self.clock_prefix) is not bool:
            raise ValueError("clock_prefix must be a boolean")
        layout, profile = (Path(config[k]).expanduser().resolve() for k in ("layout", "profile"))
        _reject_identity_configuration(read_json(profile))
        self.analyzer = RealHudAnalyzer(layout, template_profile_path=profile)
        self.layout = self.analyzer.layout
        self.profile = self.analyzer.template_profile
        if self.profile is None:
            raise ValueError("Existing readable HUD profile required")
        self.round_scope = None
        if "structural_bank" in config:
            self.round_scope = PixelRoundScope(
                Path(config["structural_bank"]), Path(config["result_method"])
            )
            # Explicitly reuse the foreground mode from the old Round CLI.
            # Historical unsupported profile mode stays untouched on disk.
            raw = deepcopy(self.profile.raw)
            for role in ("ally_score", "enemy_score"):
                spec = raw.get("readers", {}).get(role, {})
                if spec.get("kind") != "strict_score_glyphs":
                    raise ValueError("Existing strict score glyph readers required")
                spec["foreground_preprocessing"] = "white200_rowcontrast_v1"
            local = HudTemplateProfile(profile, raw)
            readers = local.build_readers()
            for role in ("ally_score", "enemy_score"):
                self.analyzer.readers[role] = readers[role]
        # Freeze every existing profile asset, including optional references.
        assets: dict[str, str] = {}

        def visit(value: Any) -> None:
            if isinstance(value, dict):
                for child in value.values():
                    visit(child)
            elif isinstance(value, list):
                for child in value:
                    visit(child)
            elif isinstance(value, str):
                candidate = Path(value)
                if not candidate.is_absolute():
                    candidate = profile.parent / candidate
                if candidate.is_file():
                    assets[str(candidate.resolve())] = file_sha(candidate)

        visit(self.profile.raw)
        package = Path(__file__).parents[1]
        self.bindings = {
            "layout": file_sha(layout),
            "profile": file_sha(profile),
            "assets": assets,
            "code": {
                name: file_sha(package / name)
                for name in (
                    "temporal/match_observer.py",
                    "hud/analyzers.py",
                    "hud/templates.py",
                    "hud/identity.py",
                    "hud/spectator_icon.py",
                    "hud/layout.py",
                    "hud/score_glyphs.py",
                    "hud/timer_glyphs.py",
                    "temporal/round_scope.py",
                    "temporal/clock_components.py",
                )
            },
            "opencv": cv2.__version__,
            "numpy": np.__version__,
            "round_scope": None if self.round_scope is None else self.round_scope.bindings,
            "clock_prefix": self.clock_prefix,
            "explicit_score_foreground": None
            if self.round_scope is None
            else "white200_rowcontrast_v1",
        }
        self.fingerprint = digest(self.bindings)

    def inspect(self, image: NDArray[np.uint8]) -> dict[str, Any]:
        assert self.profile is not None
        if image.dtype != np.uint8 or image.ndim != 3 or image.shape[2] != 3:
            raise ValueError("Native BGR pixels required")
        anchors, scores, diagnostics = self.profile.detect_anchors(image, self.layout)
        calibration = self.layout.validate_calibration(
            image.shape[1],
            image.shape[0],
            detected_anchors=anchors,
            letterboxed=_detect_letterbox(image),
            crop_applied=False,
        )
        measurements: dict[str, Any] = {}
        ui = self.profile.detect_signals(
            image, self.layout, context={}, semantic_diagnostics=measurements
        )
        values: dict[str, Any] = {}
        for name in ("ally_score", "enemy_score", "round_timer"):
            reader = self.analyzer.readers.get(name)
            if reader is None or name not in self.layout.regions:
                values[name] = {"value": None, "confidence": 0.0, "sources": ["unconfigured"]}
                continue
            left, top, right, bottom = self.layout.normalized_roi(name).pixel_bounds(
                image.shape[1], image.shape[0]
            )
            value = reader.read(image, image[top:bottom, left:right])
            values[name] = {
                "value": value.value,
                "confidence": value.confidence,
                "sources": list(value.sources),
            }
        component = (
            None if self.round_scope is None else self.round_scope.measure(image, self.layout)
        )
        round_supported = calibration.calibrated or bool(
            component and component["top_structure_supported"]
        )
        signals = []
        if ui.get("buy_phase_template") is True and round_supported:
            signals.append("buy")
        # Reuse the existing acceptance floor and clock range, without time or
        # Source-specific recovery. The temporal engine owns low-clock context.
        from .adapters import _accepted, _clock

        timer = _clock(_accepted(values["round_timer"])) if round_supported else None
        if "buy" not in signals and timer is not None and timer > 45:
            signals.append("active")
        if ui.get("round_end_template") is True and calibration.calibrated:
            signals.append("result")
        if component and component["top_structure_supported"] and component["result"]["value"]:
            signals.append("result")
        partial_clock = self._observe_clock_prefix(image, round_supported, timer, signals)
        pair = [_accepted(values[k]) for k in ("ally_score", "enemy_score")]
        score = (
            [int(str(v)) for v in pair]
            if round_supported
            and all(
                v is not None and v.isascii() and v.isdigit() and 0 <= int(v) <= 99 for v in pair
            )
            else None
        )
        identity = live_identity(ui, geometry_valid=calibration.calibrated)
        if identity.live:
            signals.append("owner_hud")
        if (
            ui.get("spectator_detector_checked") is True
            and ui.get("spectator_panel_present") is True
        ):
            signals.append("spectator")
        if any(
            ui.get(k) is True
            for k in (
                "cypher_camera_template",
                "sova_drone_template",
                "skye_trailblazer_template",
                "other_remote_view_template",
            )
        ):
            signals.append("remote")
        if ui.get("combat_report_visible") is True:
            signals.append("report")
        return {
            "signals": sorted(set(signals)),
            "context": {
                "timer_seconds": timer,
                "score": score,
                "stream_kind": "hud_generic",
                "profile_fingerprint": self.bindings["profile"],
            },
            "raw": {
                "ui": ui,
                "values": values,
                "semantic_measurements": measurements,
                "round_component_measurement": component,
                "clock_components": partial_clock,
                "calibration": {
                    "calibrated": calibration.calibrated,
                    "reasons": list(calibration.reasons),
                },
                "anchor_scores": scores,
                "anchor_diagnostics": list(diagnostics),
                "identity_reason": identity.reason,
            },
            "map_candidates": [],
            "map_observation_status": "UNCONFIGURED",
        }

    def _observe_clock_prefix(
        self,
        image: NDArray[np.uint8],
        round_supported: bool,
        timer: int | None,
        signals: list[str],
    ) -> dict[str, Any] | None:
        if not self.clock_prefix:
            return None
        partial = self._clock_components(image)
        if (
            round_supported
            and timer is None
            and partial["active_prefix_supported"]
            and "buy" not in signals
            and "result" not in signals
        ):
            # A recognized minute >= 1 supports the existing >45 phase rule.
            # Neither missing seconds nor an event time is filled.
            signals.append("active")
        return partial

    def _clock_components(self, image: NDArray[np.uint8]) -> dict[str, Any]:
        reader = self.analyzer.readers.get("round_timer")
        if reader is None or "round_timer" not in self.layout.regions:
            return {"active_prefix_supported": False, "reason": "timer_unconfigured"}
        left, top, right, bottom = self.layout.normalized_roi("round_timer").pixel_bounds(
            image.shape[1], image.shape[0]
        )
        crop = image[top:bottom, left:right]
        if isinstance(reader, SubregionReader):
            x1, y1, x2, y2 = reader.bounds
            height, width = crop.shape[:2]
            crop = crop[
                round(y1 * height) : round(y2 * height), round(x1 * width) : round(x2 * width)
            ]
            reader = reader.reader
        if not isinstance(reader, StrictTimerGlyphReader):
            return {"active_prefix_supported": False, "reason": "strict_timer_unavailable"}
        return clock_components(crop, reader)
