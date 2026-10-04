"""Configurable OpenCV HUD templates.

Profiles are JSON files next to a layout by default, named
``<layout-stem>.templates.json``. Asset paths are relative to the profile.
Anchor entries have ``template``, ``search_region`` (a layout ROI name or
normalized ``[x1, y1, x2, y2]``), and optional ``threshold``. Reader entries
use ``kind`` values ``digits``, ``strict_timer_glyphs``, ``template_values``,
``fields``, ``ability_slots``, ``weapon_templates``, or opt-in
``strict_hp_glyphs``. Missing assets produce no match.
"""

from __future__ import annotations

import hashlib
import json
import math
import re
import shutil
import subprocess
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

import cv2
import numpy as np
from numpy.typing import NDArray

from valorant_ai_coach.resources import resource_path

from .hp_glyphs import StrictHpGlyphReader, UnavailableStrictHpGlyphReader
from .layout import HudLayout, NormalizedRoi
from .readers import HudReader, ReaderResult
from .report_header import ReportHeader, report_header_evidence
from .spectator import PanelReference, detect_panel
from .spectator_icon import detect_icon, menu_overlay_candidate
from .timer_glyphs import StrictTimerGlyphReader, UnavailableStrictTimerGlyphReader
from .value_identity import MATCHER, value_invariant_score
from .weapon_consensus import MATCHER as WEAPON_MATCHER
from .weapon_consensus import consensus_score
from .weapon_identity import masked_score, structural_score

ImageU8 = NDArray[np.uint8]


def _bounds(value: Sequence[Any]) -> tuple[float, float, float, float]:
    x1, y1, x2, y2 = (float(item) for item in value)
    if not (0 <= x1 < x2 <= 1 and 0 <= y1 < y2 <= 1):
        raise ValueError("reader ROI must be normalized x1,y1,x2,y2 bounds")
    return x1, y1, x2, y2


@dataclass(frozen=True, slots=True)
class LoadedTemplate:
    name: str
    path: Path
    image: ImageU8
    threshold: float


class HudTemplateProfile:
    """Load a non-authoritative template profile and its referenced images."""

    def __init__(self, path: Path, raw: Mapping[str, Any]) -> None:
        self.path = path.resolve()
        self.raw = dict(raw)
        self.reader_diagnostics: list[str] = []
        if self.raw.get("schema_version") != "1.0":
            raise ValueError("HUD template profile schema_versionは1.0である必要があります")
        for section in ("anchors", "readers", "signals"):
            value = self.raw.get(section, {})
            if not isinstance(value, dict):
                raise ValueError(f"HUD template profile {section}はobjectである必要があります")
        self.asset_paths = tuple(sorted(self._find_asset_paths(self.raw)))
        self._signal_templates: dict[str, tuple[str, LoadedTemplate]] = {}
        self._signal_bounds: dict[str, tuple[float, float, float, float]] = {}
        self._signal_masks: dict[str, ImageU8] = {}
        self._edge_signals: set[str] = set()
        self._value_regions: dict[str, ImageU8] = {}
        self._consensus_allowed: dict[str, ImageU8] = {}
        for name, spec in self.raw.get("signals", {}).items():
            try:
                if not isinstance(spec, Mapping) or not isinstance(spec.get("roi"), str):
                    raise ValueError("signal requires roi and template")
                if (
                    spec.get("matcher") in ("oriented_edges_v1", MATCHER, WEAPON_MATCHER)
                    and "mask" not in spec
                ):
                    raise ValueError("oriented identity requires its independent edge mask")
                template = self.load_template(
                    str(name), str(spec["template"]), float(spec.get("threshold", 0.90))
                )
                if "roi_bounds" in spec:
                    self._signal_bounds[str(name)] = _bounds(spec["roi_bounds"])
                if "mask" in spec:
                    value_matcher = spec.get("matcher") in (MATCHER, WEAPON_MATCHER)
                    if spec.get("matcher") == WEAPON_MATCHER and name != "weapon_ammo_structure":
                        raise ValueError("consensus slots require Weapon role")
                    if (
                        name not in {"weapon_ammo_structure", "hp_hud_structure"}
                        or (name != "weapon_ammo_structure" and not value_matcher)
                        or template.threshold < 0.90
                    ):
                        raise ValueError(
                            "masked identity requires weapon structure and similarity >= .90"
                        )
                    mask = cv2.imdecode(
                        np.frombuffer(self.resolve_asset(str(spec["mask"])).read_bytes(), np.uint8),
                        cv2.IMREAD_GRAYSCALE,
                    )
                    if (
                        mask is None
                        or mask.shape != template.image.shape[:2]
                        or np.count_nonzero(mask) < 32
                        or not set(np.unique(mask)).issubset({0, 255})
                    ):
                        raise ValueError("invalid identity mask")
                    self._signal_masks[str(name)] = np.asarray(mask, dtype=np.uint8)
                    matcher = spec.get("matcher", "masked_ncc")
                    if matcher not in ("masked_ncc", "oriented_edges_v1", MATCHER, WEAPON_MATCHER):
                        raise ValueError("unsupported identity matcher")
                    if matcher == "oriented_edges_v1":
                        self._edge_signals.add(str(name))
                    if value_matcher:
                        regions = cv2.imdecode(
                            np.frombuffer(
                                self.resolve_asset(str(spec["support_regions"])).read_bytes(),
                                np.uint8,
                            ),
                            cv2.IMREAD_GRAYSCALE,
                        )
                        if (
                            regions is None
                            or regions.shape != mask.shape
                            or not 2 <= int(regions.max()) <= 4
                            or set(np.unique(regions)) != set(range(int(regions.max()) + 1))
                            or np.any(mask[regions == 0])
                            or any(
                                np.count_nonzero(mask[regions == g]) < 32
                                for g in range(1, int(regions.max()) + 1)
                            )
                        ):
                            raise ValueError("invalid value-invariant support regions")
                        if matcher == WEAPON_MATCHER:
                            allowed = cv2.imdecode(
                                np.frombuffer(
                                    self.resolve_asset(str(spec["allowed_regions"])).read_bytes(),
                                    np.uint8,
                                ),
                                cv2.IMREAD_GRAYSCALE,
                            )
                            if (
                                allowed is None
                                or allowed.shape != mask.shape
                                or not set(np.unique(allowed)).issubset({0, 255})
                                or np.any((regions > 0) & (allowed == 0))
                            ):
                                raise ValueError("invalid consensus allowed regions")
                            self._consensus_allowed[str(name)] = np.asarray(allowed, dtype=np.uint8)
                        self._value_regions[str(name)] = np.asarray(regions, dtype=np.uint8)
                self._signal_templates[str(name)] = (spec["roi"], template)
            except (KeyError, ValueError, OSError, cv2.error) as exc:
                self.reader_diagnostics.append(f"signal {name}: {exc}")
        self._report_header: ReportHeader | None = None
        report = self.raw.get("report_header_detector")
        if "report_header_detector" in self.raw:
            try:
                required = {
                    "version",
                    "method",
                    "roi",
                    "threshold",
                    "template",
                    "mask",
                    "support_regions",
                    "input_shape",
                    "reference_x",
                }
                if (
                    not isinstance(report, Mapping)
                    or set(report) != required
                    or type(report.get("version")) is not int
                    or report.get("version") != 1
                    or report.get("method") != "independent_static_header_v1"
                    or report.get("roi") != "combat_report"
                    or not isinstance(report.get("input_shape"), list)
                    or len(report["input_shape"]) != 2
                    or any(type(value) is not int for value in report["input_shape"])
                ):
                    raise ValueError("invalid Report header specification")
                report_assets = []
                for key in ("template", "mask", "support_regions"):
                    data = self.resolve_asset(str(report[key])).read_bytes()
                    decoded = cv2.imdecode(np.frombuffer(data, np.uint8), cv2.IMREAD_GRAYSCALE)
                    if decoded is None:
                        raise ValueError("invalid Report header asset")
                    report_assets.append(np.asarray(decoded, dtype=np.uint8))
                model = ReportHeader(
                    report_assets[0],
                    report_assets[1],
                    report_assets[2],
                    (report["input_shape"][0], report["input_shape"][1]),
                    report["reference_x"],
                    report["threshold"],
                )
                model.validate()
                self._report_header = model
            except (KeyError, ValueError, TypeError, OSError, cv2.error) as exc:
                self.reader_diagnostics.append(f"report_header_detector: {exc}")
        self._panel_components: ImageU8 | None = None
        clear = self.raw.get("spectator_panel_detector")
        if isinstance(clear, Mapping):
            try:
                data = self.resolve_asset(str(clear["template"])).read_bytes()
                reference = cv2.imdecode(np.frombuffer(data, np.uint8), cv2.IMREAD_GRAYSCALE)
                if (
                    reference is None
                    or reference.size == 0
                    or clear.get("version") not in (1, 2)
                    or not set(np.unique(reference)).issubset({0, 1, 2, 3})
                    or any(np.count_nonzero(reference == k) < 12 for k in (1, 2, 3))
                ):
                    raise ValueError("invalid panel structure")
                self._panel_components = np.asarray(reference, dtype=np.uint8)
                if clear.get("version") == 2:
                    assets = []
                    for key in ("support_regions", "orientation"):
                        data = self.resolve_asset(str(clear[key])).read_bytes()
                        asset = cv2.imdecode(np.frombuffer(data, np.uint8), cv2.IMREAD_GRAYSCALE)
                        if asset is None:
                            raise ValueError("invalid panel support asset")
                        assets.append(asset)
                    self._panel_components = PanelReference(reference, *assets)
            except (KeyError, ValueError, OSError, cv2.error):
                self._panel_components = None
                self.reader_diagnostics.append("spectator_panel_detector: invalid asset")

    def detect_signals(
        self, frame: ImageU8, layout: HudLayout, *, context: Mapping[str, Any] | None = None
    ) -> dict[str, Any]:
        """UI matches and checked spectator absence; unreadable regions stay unknown."""
        signals: dict[str, Any] = {}
        height, width = frame.shape[:2]
        icon_spec = self.raw.get("spectator_icon_detector")
        icon_active = "spectator_icon_detector" in self.raw
        for name, (roi_name, template) in self._signal_templates.items():
            if icon_active and name == "spectated_player_panel":
                continue
            if roi_name not in layout.regions:
                continue
            x1, y1, x2, y2 = layout.normalized_roi(roi_name).pixel_bounds(width, height)
            crop = frame[y1:y2, x1:x2]
            if name in self._signal_bounds:
                left, top, right, bottom = self._signal_bounds[name]
                ch, cw = crop.shape[:2]
                crop = crop[
                    round(top * ch) : round(bottom * ch), round(left * cw) : round(right * cw)
                ]
            if name in self._signal_masks:
                reference = template.image
                if reference.ndim == 3:
                    reference = np.asarray(
                        cv2.cvtColor(reference, cv2.COLOR_BGR2GRAY), dtype=np.uint8
                    )
                score = structural_score if name in self._edge_signals else masked_score
                confidence = (
                    consensus_score(
                        reference,
                        crop,
                        self._signal_masks[name],
                        self._value_regions[name],
                        self._consensus_allowed[name],
                    )
                    if name in self._consensus_allowed
                    else value_invariant_score(
                        reference, crop, self._signal_masks[name], self._value_regions[name]
                    )
                    if name in self._value_regions
                    else score(reference, crop, self._signal_masks[name])
                )
                result: ReaderResult[Any] = ReaderResult(
                    True if confidence >= template.threshold else None, confidence
                )
            else:
                result = _best_template_match(crop, (template,))
            # Legacy pixel templates can prove presence, never absence.
            if name == "spectated_player_panel" and result.value is not None:
                signals["self_hud_identity_trustworthy"] = False
            if result.value is not None and result.confidence >= 0.85:
                signals[name] = True
                signals[f"{name}_confidence"] = result.confidence
                confidence_key = {
                    "cypher_camera_template": "remote_confidence",
                    "sova_drone_template": "remote_confidence",
                    "skye_trailblazer_template": "remote_confidence",
                    "other_remote_view_template": "remote_confidence",
                    "spectated_player_panel": "spectator_confidence",
                    "plant_timer_visible": "plant_timer_confidence",
                    "combat_report_visible": "combat_report_confidence",
                    "smoke_template_confirmed": "smoke_confidence",
                }.get(name)
                if confidence_key is not None:
                    signals[confidence_key] = min(
                        signals.get(confidence_key, 1.0), result.confidence
                    )
        panel_result = {"checked": False, "panel_present": None, "reason": "roi_unavailable"}
        if icon_active:
            valid = (
                isinstance(icon_spec, Mapping)
                and type(icon_spec.get("version")) is int
                and icon_spec.get("version") == 1
                and icon_spec.get("method") == "fixed_slot_structure_v1"
                and icon_spec.get("roi") == "spectator_icon"
            )
            if valid and "spectator_icon" in layout.regions:
                x1, y1, x2, y2 = layout.normalized_roi("spectator_icon").pixel_bounds(width, height)
                hints = {} if context is None else context
                obscured = any(
                    hints.get(key)
                    for key in (
                        "map_transition",
                        "partial_expanded_map",
                        "expanded_map_present",
                        "expanded_map_stable",
                        "flash_candidate",
                        "abrupt_luminance_spike",
                        "visual_transition",
                        "buy_menu_grid_present",
                    )
                )
                if "buy_menu_close_anchor" in layout.regions:
                    cx1, cy1, cx2, cy2 = layout.normalized_roi(
                        "buy_menu_close_anchor"
                    ).pixel_bounds(width, height)
                    obscured = obscured or menu_overlay_candidate(frame[cy1:cy2, cx1:cx2])
                panel_result = detect_icon(frame[y1:y2, x1:x2], obscured=bool(obscured))
            else:
                panel_result = detect_icon(np.empty((0, 0), np.uint8), configured=False)
        elif "spectated_player_panel" in layout.regions:
            x1, y1, x2, y2 = layout.normalized_roi("spectated_player_panel").pixel_bounds(
                width, height
            )
            panel_result = detect_panel(frame[y1:y2, x1:x2], self._panel_components)
        signals["spectator_detector_checked"] = panel_result["checked"]
        signals["spectator_panel_present"] = panel_result["panel_present"]
        signals["spectator_detector_reason"] = panel_result["reason"]
        signals["spectator_panel_absent"] = (
            panel_result["checked"] is True
            and panel_result["panel_present"] is False
            and not signals.get("spectated_player_panel", False)
        )
        if panel_result["panel_present"] is True:
            signals.update(
                spectated_player_panel=True,
                spectator_confidence=0.90,
                self_hud_identity_trustworthy=False,
            )
        if self._report_header is not None and "combat_report" in layout.regions:
            x1, y1, x2, y2 = layout.normalized_roi("combat_report").pixel_bounds(width, height)
            report_evidence = report_header_evidence(frame[y1:y2, x1:x2], self._report_header)
            if report_evidence["present"] is True:
                signals.update(
                    combat_report_visible=True,
                    combat_report_confidence=report_evidence["score"],
                )
        return signals

    @classmethod
    def load(cls, path: Path) -> HudTemplateProfile:
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise ValueError(f"HUD template profileを読み込めません: {path}: {exc}") from exc
        if not isinstance(raw, dict):
            raise ValueError("HUD template profileのrootはobjectである必要があります")
        return cls(path, raw)

    @staticmethod
    def _find_asset_paths(value: Any) -> set[Path]:
        found: set[Path] = set()
        if isinstance(value, Mapping):
            for key, child in value.items():
                if key == "templates":

                    def collect_template_paths(value: Any) -> None:
                        if isinstance(value, str):
                            found.add(Path(value))
                        elif isinstance(value, Mapping):
                            for nested in value.values():
                                collect_template_paths(nested)
                        elif isinstance(value, list):
                            for nested in value:
                                collect_template_paths(nested)

                    collect_template_paths(child)
                elif key in {
                    "template",
                    "mask",
                    "values",
                    "available_template",
                    "unavailable_template",
                    "support_regions",
                    "allowed_regions",
                    "orientation",
                }:
                    if isinstance(child, str):
                        found.add(Path(child))
                    elif isinstance(child, Mapping):
                        found.update(
                            Path(str(path)) for path in child.values() if isinstance(path, str)
                        )
                else:
                    found.update(HudTemplateProfile._find_asset_paths(child))
        elif isinstance(value, list):
            for child in value:
                found.update(HudTemplateProfile._find_asset_paths(child))
        return found

    def resolve_asset(self, value: str) -> Path:
        candidate = Path(value)
        return candidate if candidate.is_absolute() else self.path.parent / candidate

    def load_template(self, name: str, value: str, threshold: float = 0.90) -> LoadedTemplate:
        if not math.isfinite(threshold) or not 0.0 <= threshold <= 1.0:
            raise ValueError(f"template thresholdが不正です: {name}")
        path = self.resolve_asset(value)
        image = cv2.imdecode(np.frombuffer(path.read_bytes(), np.uint8), cv2.IMREAD_COLOR)
        if image is None or image.size == 0:
            raise ValueError(f"HUD template画像を読み込めません: {path}")
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        if float(gray.std()) < 1.0:
            raise ValueError(f"HUD template画像のコントラストが不足しています: {path}")
        return LoadedTemplate(name, path, np.asarray(gray, dtype=np.uint8), threshold)

    def fingerprint(self, layout_path: Path) -> str:
        digest = hashlib.sha256()
        digest.update(layout_path.read_bytes())
        digest.update(self.path.read_bytes())
        for relative in self.asset_paths:
            asset = self.resolve_asset(str(relative))
            digest.update(str(relative).encode("utf-8"))
            try:
                digest.update(asset.read_bytes())
            except OSError:
                digest.update(b"<missing>")
        return digest.hexdigest()

    def detect_anchors(
        self,
        frame: ImageU8,
        layout: HudLayout,
    ) -> tuple[dict[str, NormalizedRoi], dict[str, float], tuple[str, ...]]:
        anchors = self.raw.get("anchors", {})
        detected: dict[str, NormalizedRoi] = {}
        scores: dict[str, float] = {}
        diagnostics: list[str] = []
        height, width = frame.shape[:2]
        for name, raw_spec in anchors.items():
            if name not in {"round_timer", "top_match_bar", "player_hp_armor", "abilities"}:
                continue
            if not isinstance(raw_spec, Mapping) or not isinstance(raw_spec.get("template"), str):
                diagnostics.append(f"anchor {name}: missing template path")
                continue
            try:
                template = self.load_template(
                    str(name),
                    str(raw_spec["template"]),
                    float(raw_spec.get("threshold", 0.90)),
                )
                search = self._search_region(raw_spec.get("search_region"), layout, width, height)
                x0, y0, x1, y1 = search
                haystack = cv2.cvtColor(frame[y0:y1, x0:x1], cv2.COLOR_BGR2GRAY)
                if (
                    template.image.shape[0] > haystack.shape[0]
                    or template.image.shape[1] > haystack.shape[1]
                ):
                    diagnostics.append(f"anchor {name}: template exceeds search region")
                    continue
                mask = None
                if "mask" in raw_spec:
                    mask = cv2.imdecode(
                        np.frombuffer(
                            self.resolve_asset(str(raw_spec["mask"])).read_bytes(), np.uint8
                        ),
                        cv2.IMREAD_GRAYSCALE,
                    )
                    if mask is None or mask.shape != template.image.shape:
                        raise ValueError("anchor mask must match template dimensions")
                    mask = np.where(mask > 0, 255, 0).astype(np.uint8)
                    selected_pixels = template.image[mask > 0]
                    if selected_pixels.size < 64 or float(selected_pixels.std()) < 1.0:
                        raise ValueError("anchor mask has insufficient informative pixels")
                scores_map = cv2.matchTemplate(
                    haystack, template.image, cv2.TM_CCOEFF_NORMED, mask=mask
                )
                # Masked NCC is undefined for constant patches. Such locations
                # provide no evidence; never clamp NaN/Inf to a perfect score.
                scores_map = np.where(np.isfinite(scores_map), scores_map, -1.0)
                _, max_score, _, max_location = cv2.minMaxLoc(scores_map)
                score = max(0.0, min(1.0, float(max_score)))
                scores[str(name)] = score
                if score < template.threshold:
                    diagnostics.append(f"anchor {name}: template score {score:.3f} below threshold")
                    continue
                left = x0 + int(max_location[0])
                top = y0 + int(max_location[1])
                detected[str(name)] = NormalizedRoi(
                    left / width,
                    top / height,
                    template.image.shape[1] / width,
                    template.image.shape[0] / height,
                )
            except (OSError, TypeError, ValueError, cv2.error) as exc:
                diagnostics.append(f"anchor {name}: {exc}")
        return detected, scores, tuple(diagnostics)

    @staticmethod
    def _search_region(
        value: Any,
        layout: HudLayout,
        width: int,
        height: int,
    ) -> tuple[int, int, int, int]:
        if isinstance(value, str):
            roi = layout.normalized_roi(value)
        elif (
            isinstance(value, Sequence) and not isinstance(value, (str, bytes)) and len(value) == 4
        ):
            x1, y1, x2, y2 = (float(part) for part in value)
            if not (0 <= x1 < x2 <= 1 and 0 <= y1 < y2 <= 1):
                raise ValueError("search_region normalized bboxが不正です")
            roi = NormalizedRoi(x1, y1, x2 - x1, y2 - y1)
        else:
            raise ValueError("anchor search_regionにはROI名またはnormalized bboxが必要です")
        return roi.pixel_bounds(width, height)

    def build_readers(self) -> dict[str, Any]:
        readers: dict[str, Any] = {}
        for roi_name, raw_spec in self.raw.get("readers", {}).items():
            if not isinstance(raw_spec, Mapping):
                continue
            kind = raw_spec.get("kind")
            try:
                subregion: tuple[float, float, float, float] | None
                if kind == "strict_hp_glyphs" and "subregion_norm" in raw_spec:
                    raw_subregion = raw_spec["subregion_norm"]
                    if (
                        not isinstance(raw_subregion, Sequence)
                        or isinstance(raw_subregion, (str, bytes))
                        or len(raw_subregion) != 4
                        or any(
                            isinstance(item, bool)
                            or not isinstance(item, (int, float))
                            or not math.isfinite(float(item))
                            for item in raw_subregion
                        )
                    ):
                        raise ValueError(
                            "strict HP subregion_norm must contain four finite numbers"
                        )
                    subregion = _bounds(raw_subregion)
                else:
                    subregion = (
                        _bounds(raw_spec["subregion_norm"])
                        if "subregion_norm" in raw_spec
                        else None
                    )
                if kind == "digits":
                    readers[str(roi_name)] = SegmentedDigitsReader(
                        self,
                        raw_spec,
                        fallback=TesseractDigitsReader(
                            psm=int(raw_spec.get("psm", 7)),
                            whitelist=str(raw_spec.get("whitelist", "0123456789:")),
                            executable=str(raw_spec.get("executable", "tesseract")),
                            white_text_threshold=raw_spec.get("white_text_threshold"),
                        ),
                    )
                elif kind == "text":
                    reader = TesseractTextReader(
                        language=str(raw_spec.get("language", "")),
                        executable=str(raw_spec.get("executable", "tesseract")),
                        tessdata_dir=(
                            str(self.resolve_asset(str(raw_spec["tessdata_dir"])))
                            if raw_spec.get("tessdata_dir")
                            else None
                        ),
                        psm=int(raw_spec.get("psm", 7)),
                    )
                    readers[str(roi_name)] = reader
                    self.reader_diagnostics.extend(
                        f"reader {roi_name}: {message}" for message in reader.diagnostics
                    )
                elif kind == "template_values":
                    values = raw_spec.get("values", {})
                    if isinstance(values, Mapping):
                        loaded = self._load_values(values, float(raw_spec.get("threshold", 0.90)))
                        readers[str(roi_name)] = TemplateValueReader(loaded)
                elif kind == "strict_timer_glyphs":
                    if str(roi_name) != "round_timer":
                        raise ValueError("strict_timer_glyphs is only supported for round_timer")
                    threshold = raw_spec.get("glyph_threshold", 0.90)
                    margin = raw_spec.get("glyph_margin", 0.04)
                    if (
                        isinstance(threshold, bool)
                        or not isinstance(threshold, (int, float))
                        or not math.isfinite(float(threshold))
                        or float(threshold) != StrictTimerGlyphReader.THRESHOLD
                    ):
                        raise ValueError("strict timer glyph_threshold is fixed at 0.90")
                    if (
                        isinstance(margin, bool)
                        or not isinstance(margin, (int, float))
                        or not math.isfinite(float(margin))
                        or float(margin) != StrictTimerGlyphReader.CLASS_MARGIN
                    ):
                        raise ValueError("strict timer glyph_margin is fixed at 0.04")
                    raw_templates = raw_spec.get("templates")
                    if not isinstance(raw_templates, Mapping) or set(raw_templates) != set(
                        "0123456789"
                    ):
                        raise ValueError(
                            "strict timer templates must contain exactly digits 0 through 9"
                        )
                    loaded_templates: dict[str, list[ImageU8]] = {}
                    for digit in "0123456789":
                        asset = raw_templates[digit]
                        if not isinstance(asset, str):
                            raise ValueError(f"strict timer digit {digit} template path is invalid")
                        path = self.resolve_asset(asset)
                        encoded = np.frombuffer(path.read_bytes(), dtype=np.uint8)
                        reference = cv2.imdecode(encoded, cv2.IMREAD_GRAYSCALE)
                        if reference is None:
                            raise ValueError(
                                f"strict timer digit {digit} template cannot be decoded"
                            )
                        loaded_templates[digit] = [np.asarray(reference, dtype=np.uint8)]
                    readers[str(roi_name)] = StrictTimerGlyphReader(loaded_templates)
                elif kind == "strict_hp_glyphs":
                    if str(roi_name) != "player_hp_armor":
                        raise ValueError("strict_hp_glyphs is only supported for player_hp_armor")
                    if subregion is None:
                        raise ValueError("strict HP reader requires subregion_norm")
                    threshold = raw_spec.get("glyph_threshold", StrictHpGlyphReader.THRESHOLD)
                    margin = raw_spec.get("glyph_margin", StrictHpGlyphReader.CLASS_MARGIN)
                    if (
                        isinstance(threshold, bool)
                        or not isinstance(threshold, (int, float))
                        or not math.isfinite(float(threshold))
                        or float(threshold) != StrictHpGlyphReader.THRESHOLD
                    ):
                        raise ValueError("strict HP glyph_threshold is fixed at 0.90")
                    if (
                        isinstance(margin, bool)
                        or not isinstance(margin, (int, float))
                        or not math.isfinite(float(margin))
                        or float(margin) != StrictHpGlyphReader.CLASS_MARGIN
                    ):
                        raise ValueError("strict HP glyph_margin is fixed at 0.04")
                    raw_geometry = raw_spec.get("geometry")
                    if not isinstance(raw_geometry, Mapping):
                        raise ValueError("strict HP reader requires profile geometry bounds")
                    raw_templates = raw_spec.get("templates")
                    if not isinstance(raw_templates, Mapping) or set(raw_templates) != set(
                        "0123456789"
                    ):
                        raise ValueError(
                            "strict HP templates must contain exactly digits 0 through 9"
                        )
                    hp_templates: dict[str, list[ImageU8]] = {}
                    for digit in "0123456789":
                        asset_spec = raw_templates[digit]
                        asset_paths = (
                            [asset_spec]
                            if isinstance(asset_spec, str)
                            else list(asset_spec)
                            if isinstance(asset_spec, Sequence)
                            and not isinstance(asset_spec, (str, bytes))
                            else []
                        )
                        if not asset_paths or not all(
                            isinstance(path, str) for path in asset_paths
                        ):
                            raise ValueError(f"strict HP digit {digit} reference paths are invalid")
                        images: list[ImageU8] = []
                        for asset in asset_paths:
                            encoded = np.frombuffer(
                                self.resolve_asset(asset).read_bytes(), dtype=np.uint8
                            )
                            reference = cv2.imdecode(encoded, cv2.IMREAD_GRAYSCALE)
                            if reference is None:
                                raise ValueError(
                                    f"strict HP digit {digit} template cannot be decoded"
                                )
                            images.append(np.asarray(reference, dtype=np.uint8))
                        hp_templates[digit] = images
                    readers[str(roi_name)] = StrictHpGlyphReader(
                        hp_templates,
                        center_offset_norm=cast(
                            Sequence[float], raw_geometry.get("center_offset_norm")
                        ),
                        gap_ratio_bounds=cast(
                            Sequence[float], raw_geometry.get("gap_ratio_bounds")
                        ),
                        tolerance_norm=cast(float, raw_geometry.get("tolerance_norm")),
                    )
                elif kind == "fields":
                    fields = raw_spec.get("fields", {})
                    if isinstance(fields, Mapping):
                        readers[str(roi_name)] = NumericFieldsReader(
                            {
                                str(field_name): _bounds(bounds)
                                for field_name, bounds in fields.items()
                                if isinstance(bounds, Sequence) and len(bounds) == 4
                            },
                            SegmentedDigitsReader(
                                self,
                                raw_spec,
                                fallback=TesseractDigitsReader(
                                    psm=int(raw_spec.get("psm", 7)),
                                    whitelist="0123456789",
                                    executable=str(raw_spec.get("executable", "tesseract")),
                                    white_text_threshold=raw_spec.get("white_text_threshold"),
                                ),
                            ),
                        )
                elif kind == "ability_slots":
                    readers[str(roi_name)] = AbilitySlotsReader(self, raw_spec.get("slots", []))
                elif kind == "weapon_templates":
                    values = raw_spec.get("values", {})
                    if isinstance(values, Mapping):
                        loaded = self._load_values(values, float(raw_spec.get("threshold", 0.90)))
                        readers[str(roi_name)] = WeaponTemplateReader(loaded)
                if subregion is not None and str(roi_name) in readers:
                    readers[str(roi_name)] = SubregionReader(readers[str(roi_name)], subregion)
            except (OSError, TypeError, ValueError, cv2.error) as exc:
                self.reader_diagnostics.append(f"reader {roi_name}: {exc}")
                if kind == "strict_timer_glyphs" and str(roi_name) == "round_timer":
                    # Keep the configured timer reader present: HudAnalyzer otherwise
                    # substitutes its legacy OCR reader when round_timer is absent.
                    readers[str(roi_name)] = UnavailableStrictTimerGlyphReader()
                if kind == "strict_hp_glyphs":
                    # Explicit opt-in HP configurations fail closed, including wrong roles.
                    readers[str(roi_name)] = UnavailableStrictHpGlyphReader()
        return readers

    def _load_values(
        self, values: Mapping[str, Any], threshold: float
    ) -> tuple[LoadedTemplate, ...]:
        loaded: list[LoadedTemplate] = []
        for name, path in values.items():
            if isinstance(path, str):
                loaded.append(self.load_template(str(name), path, threshold))
        return tuple(loaded)


class SubregionReader:
    """Configurable inner ROI without modifying the canonical HUD geometry."""

    def __init__(self, reader: HudReader[Any], bounds: tuple[float, float, float, float]):
        self.reader = reader
        self.bounds = bounds

    def read(self, image: ImageU8, roi: ImageU8) -> ReaderResult[Any]:
        height, width = roi.shape[:2]
        x1, y1, x2, y2 = self.bounds
        crop = roi[round(y1 * height) : round(y2 * height), round(x1 * width) : round(x2 * width)]
        if not crop.size:
            return ReaderResult(None, 0.0, ("empty_reader_subregion",))
        return self.reader.read(image, crop)


class TesseractDigitsReader:
    """Optional local digits-only OCR using the Tesseract executable."""

    def __init__(
        self,
        psm: int = 7,
        whitelist: str = "0123456789:",
        executable: str = "tesseract",
        white_text_threshold: int | None = None,
    ) -> None:
        if white_text_threshold is not None and (
            type(white_text_threshold) is not int or not 0 <= white_text_threshold <= 255
        ):
            raise ValueError("white_text_threshold must be an integer in [0,255]")
        self.executable = shutil.which(executable)
        self.psm = psm
        self.whitelist = whitelist
        self.white_text_threshold = white_text_threshold

    def read(self, image: ImageU8, roi: ImageU8) -> ReaderResult[str]:
        del image
        if self.executable is None or roi.size == 0:
            return ReaderResult(None, 0.0, ("tesseract_unavailable",))
        gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY) if roi.ndim == 3 else roi
        if self.white_text_threshold is not None:
            gray = cv2.threshold(gray, self.white_text_threshold, 255, cv2.THRESH_BINARY_INV)[1]
        enlarged = cv2.resize(gray, None, fx=3, fy=3, interpolation=cv2.INTER_CUBIC)
        ok, encoded = cv2.imencode(".png", enlarged)
        if not ok:
            return ReaderResult(None, 0.0, ("tesseract_encode_failed",))
        command = [
            self.executable,
            "stdin",
            "stdout",
            "--psm",
            str(self.psm),
            "-c",
            f"tessedit_char_whitelist={self.whitelist}",
            "tsv",
        ]
        try:
            result = subprocess.run(
                command,
                input=encoded.tobytes(),
                capture_output=True,
                check=False,
                timeout=2.0,
            )
        except (OSError, subprocess.TimeoutExpired):
            return ReaderResult(None, 0.0, ("tesseract_failed",))
        if result.returncode != 0:
            return ReaderResult(None, 0.0, ("tesseract_failed",))
        words: list[str] = []
        confidences: list[float] = []
        lines = result.stdout.decode("utf-8", errors="replace").splitlines()
        for line in lines[1:]:
            parts = line.split("\t")
            if len(parts) < 12 or parts[0] != "5" or not parts[11].strip():
                continue
            try:
                confidence = float(parts[10]) / 100.0
            except ValueError:
                return ReaderResult(None, 0.0, ("tesseract_invalid_digit_confidence",))
            if not math.isfinite(confidence) or not 0.0 <= confidence <= 1.0:
                return ReaderResult(None, 0.0, ("tesseract_invalid_digit_confidence",))
            words.append(parts[11].strip())
            confidences.append(confidence)
        text = "".join(words)
        if not text or any(character not in self.whitelist for character in text):
            return ReaderResult(None, 0.0, ("tesseract_no_digits",))
        confidence = min(confidences, default=0.0)
        return ReaderResult(text, confidence, ("tesseract_digits",))


class TesseractTextReader:
    """Optional local UTF-8 text OCR with explicit trained-language selection."""

    def __init__(
        self,
        *,
        language: str,
        executable: str = "tesseract",
        tessdata_dir: str | None = None,
        psm: int = 7,
    ) -> None:
        self.executable = shutil.which(executable)
        self.language = language.strip()
        self.tessdata_dir = tessdata_dir
        if type(psm) is not int or not 0 <= psm <= 13:
            raise ValueError("text OCR psm must be an integer in [0,13]")
        self.psm = psm
        self.diagnostics: list[str] = []
        self.available_languages: frozenset[str] = frozenset()
        if not self.language:
            self.diagnostics.append("tesseract_language_not_configured")
        elif self.executable is None:
            self.diagnostics.append("tesseract_unavailable")
        else:
            self._load_languages()

    def _load_languages(self) -> None:
        command = [self.executable or "tesseract"]
        if self.tessdata_dir:
            command.extend(("--tessdata-dir", self.tessdata_dir))
        command.append("--list-langs")
        try:
            result = subprocess.run(command, capture_output=True, check=False, timeout=2.0)
        except (OSError, subprocess.TimeoutExpired):
            self.diagnostics.append("tesseract_language_query_failed")
            return
        if result.returncode != 0:
            self.diagnostics.append("tesseract_language_query_failed")
            return
        lines = result.stdout.decode("utf-8", errors="replace").splitlines()
        # Tesseract prints one explanatory header followed by one language per line.
        self.available_languages = frozenset(line.strip() for line in lines[1:] if line.strip())
        requested = {part for part in self.language.split("+") if part}
        missing = sorted(requested - self.available_languages)
        if missing:
            self.diagnostics.append("tesseract_language_missing:" + ",".join(missing))

    def read(self, image: ImageU8, roi: ImageU8) -> ReaderResult[str]:
        del image
        if roi.size == 0:
            return ReaderResult(None, 0.0, ("tesseract_empty_roi",))
        if self.executable is None:
            return ReaderResult(None, 0.0, ("tesseract_unavailable",))
        if not self.language:
            return ReaderResult(None, 0.0, ("tesseract_language_not_configured",))
        if self.diagnostics:
            return ReaderResult(None, 0.0, tuple(self.diagnostics))
        gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY) if roi.ndim == 3 else roi
        enlarged = cv2.resize(gray, None, fx=3, fy=3, interpolation=cv2.INTER_CUBIC)
        ok, encoded = cv2.imencode(".png", enlarged)
        if not ok:
            return ReaderResult(None, 0.0, ("tesseract_encode_failed",))
        command = [self.executable, "stdin", "stdout"]
        if self.tessdata_dir:
            command.extend(("--tessdata-dir", self.tessdata_dir))
        command.extend(("-l", self.language, "--psm", str(self.psm), "tsv"))
        try:
            result = subprocess.run(
                command,
                input=encoded.tobytes(),
                capture_output=True,
                check=False,
                timeout=2.0,
            )
        except (OSError, subprocess.TimeoutExpired):
            return ReaderResult(None, 0.0, ("tesseract_text_failed",))
        if result.returncode != 0:
            return ReaderResult(None, 0.0, ("tesseract_text_failed",))
        words: list[str] = []
        confidences: list[float] = []
        lines = result.stdout.decode("utf-8", errors="replace").splitlines()
        for line in lines[1:]:
            parts = line.split("\t")
            if len(parts) < 12 or parts[0] != "5" or not parts[11].strip():
                continue
            try:
                confidence = float(parts[10]) / 100.0
            except ValueError:
                return ReaderResult(None, 0.0, ("tesseract_invalid_text_confidence",))
            if not math.isfinite(confidence) or not 0.0 <= confidence <= 1.0:
                # Do not drop one malformed word and return a plausible-looking
                # partial label at the confidence of the remaining words.
                return ReaderResult(None, 0.0, ("tesseract_invalid_text_confidence",))
            words.append(parts[11].strip())
            confidences.append(confidence)
        text = " ".join(words)
        if not text:
            return ReaderResult(None, 0.0, ("tesseract_no_text",))
        return ReaderResult(text, min(confidences, default=0.0), ("tesseract_text",))


class SegmentedDigitsReader:
    """Use configured per-glyph templates first and local OCR as fallback."""

    def __init__(
        self,
        profile: HudTemplateProfile,
        spec: Mapping[str, Any],
        *,
        fallback: TesseractDigitsReader,
    ) -> None:
        self.fallback = fallback
        self.value_format = spec.get("format", "integer")
        if self.value_format not in {"integer", "timer_mmss"}:
            raise ValueError("digit format must be integer or timer_mmss")
        raw_templates = spec.get("templates", {})
        self.templates: dict[str, ImageU8] = {}
        if isinstance(raw_templates, Mapping):
            for character, path in raw_templates.items():
                digit = str(character)
                if digit not in "0123456789" or not isinstance(path, str):
                    continue
                try:
                    loaded = profile.load_template(
                        f"digit_{digit}", path, float(spec.get("glyph_threshold", 0.72))
                    )
                except (OSError, ValueError) as exc:
                    profile.reader_diagnostics.append(f"digit template {digit}: {exc}")
                    continue
                self.templates[digit] = self._normalize(loaded.image)
        self.threshold = float(spec.get("glyph_threshold", 0.72))

    def read(self, image: ImageU8, roi: ImageU8) -> ReaderResult[str]:
        del image
        candidate = self._read_templates(roi)
        ocr = self.fallback.read(roi, roi)
        # Never reinterpret an OCR-missed colon (e.g. 1:14 -> 1714)
        # as thousands of seconds or insert punctuation speculatively.
        if (
            self.value_format == "timer_mmss"
            and ocr.value is not None
            and re.fullmatch(r"[0-9]{1,2}:[0-5][0-9]", ocr.value) is None
        ):
            ocr = ReaderResult(None, 0.0, ("timer_ocr_format_invalid",))
        if candidate is not None and self.value_format == "timer_mmss":
            digits = candidate.value or ""
            if len(digits) not in {3, 4} or int(digits[-2:]) >= 60:
                candidate = None
            else:
                candidate = ReaderResult(
                    f"{int(digits[:-2])}:{digits[-2:]}", candidate.confidence, candidate.sources
                )
        if candidate is None:
            return ocr
        if ocr.value is not None and ocr.confidence >= 0.65:
            if candidate.value != ocr.value:
                return ReaderResult(None, 0.0, ("digit_template_ocr_conflict",))
            return ReaderResult(
                candidate.value,
                min(candidate.confidence, ocr.confidence),
                ("digit_templates", "tesseract_digits"),
                True,
            )
        return candidate

    def _read_templates(self, roi: ImageU8) -> ReaderResult[str] | None:
        if not self.templates or roi.size == 0:
            return None
        gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY) if roi.ndim == 3 else roi
        gray = cv2.resize(gray, None, fx=2, fy=2, interpolation=cv2.INTER_CUBIC)
        _, otsu = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        candidates: list[tuple[str, float]] = []
        for mask in (otsu, cv2.bitwise_not(otsu)):
            count, _, stats, _ = cv2.connectedComponentsWithStats(mask, connectivity=8)
            min_height = max(4, round(mask.shape[0] * 0.22))
            components = [
                (int(x), int(y), int(width), int(height))
                for x, y, width, height, area in stats[1:count]
                if height >= min_height and width >= 1 and area >= 4
            ]
            components.sort(key=lambda item: item[0])
            if not 1 <= len(components) <= 8:
                continue
            digits: list[str] = []
            scores: list[float] = []
            for x, y, width, height in components:
                glyph = self._normalize(
                    np.asarray(mask[y : y + height, x : x + width], dtype=np.uint8)
                )
                ranked = sorted(
                    (
                        float(cv2.matchTemplate(glyph, template, cv2.TM_CCOEFF_NORMED)[0, 0]),
                        digit,
                    )
                    for digit, template in self.templates.items()
                )
                score, digit = ranked[-1]
                if score < self.threshold or (len(ranked) > 1 and score - ranked[-2][0] < 0.04):
                    break
                digits.append(digit)
                scores.append(max(0.0, min(1.0, score)))
            if len(digits) == len(components):
                candidates.append(("".join(digits), sum(scores) / len(scores)))
        if not candidates:
            return None
        candidates.sort(key=lambda item: item[1], reverse=True)
        if (
            len(candidates) > 1
            and candidates[0][0] != candidates[1][0]
            and candidates[0][1] - candidates[1][1] < 0.05
        ):
            return None
        value, confidence = candidates[0]
        return ReaderResult(value, confidence, ("digit_templates",))

    @staticmethod
    def _normalize(image: ImageU8) -> ImageU8:
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY) if image.ndim == 3 else image
        _, mask = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        if float(mask.mean()) > 127:
            mask = cv2.bitwise_not(mask)
        points = cv2.findNonZero(mask)
        if points is not None:
            left, top, width, height = cv2.boundingRect(points)
            mask = mask[top : top + height, left : left + width]
        height, width = mask.shape[:2]
        scale = min(18 / max(width, 1), 26 / max(height, 1))
        resized = cv2.resize(
            mask,
            (max(1, round(width * scale)), max(1, round(height * scale))),
            interpolation=cv2.INTER_NEAREST,
        )
        canvas = np.zeros((32, 24), dtype=np.uint8)
        y = (32 - resized.shape[0]) // 2
        x = (24 - resized.shape[1]) // 2
        canvas[y : y + resized.shape[0], x : x + resized.shape[1]] = resized
        return canvas


class TemplateValueReader:
    def __init__(self, templates: tuple[LoadedTemplate, ...]) -> None:
        self.templates = templates

    def read(self, image: ImageU8, roi: ImageU8) -> ReaderResult[str]:
        del image
        return _best_template_match(roi, self.templates)


class WeaponTemplateReader:
    def __init__(self, templates: tuple[LoadedTemplate, ...]) -> None:
        self.templates = templates

    def read(self, image: ImageU8, roi: ImageU8) -> ReaderResult[dict[str, str] | None]:
        del image
        result = _best_template_match(roi, self.templates)
        value = {"weapon_text": result.value} if result.value is not None else None
        return ReaderResult(value, result.confidence, result.sources, result.cross_checked)


class NumericFieldsReader:
    def __init__(
        self,
        fields: Mapping[str, tuple[float, float, float, float]],
        reader: HudReader[str],
    ) -> None:
        self.fields = dict(fields)
        self.reader = reader

    def read(self, image: ImageU8, roi: ImageU8) -> ReaderResult[dict[str, int]]:
        del image
        values: dict[str, int] = {}
        confidences: list[float] = []
        corroborated: list[bool] = []
        has_corroboration = False
        sources: set[str] = set()
        for name, bounds in self.fields.items():
            x1, y1, x2, y2 = bounds
            if not (0 <= x1 < x2 <= 1 and 0 <= y1 < y2 <= 1):
                continue
            height, width = roi.shape[:2]
            left, top = round(x1 * width), round(y1 * height)
            right, bottom = max(left + 1, round(x2 * width)), max(top + 1, round(y2 * height))
            result = self.reader.read(roi, roi[top:bottom, left:right])
            if result.value is None or not result.value.isdecimal():
                continue
            values[name] = int(result.value)
            confidences.append(result.confidence)
            corroborated.append(result.cross_checked or result.confidence >= 0.85)
            has_corroboration = has_corroboration or result.cross_checked
            sources.update(result.sources)
        return ReaderResult(
            values if values else None,
            min(confidences, default=0.0),
            tuple(sorted(sources | {"field_digits"})),
            has_corroboration and all(corroborated),
        )


class AbilitySlotsReader:
    def __init__(self, profile: HudTemplateProfile, specs: Any) -> None:
        contract = json.loads(
            resource_path("config/ability_slot_contract_v1.json").read_text(encoding="utf-8")
        )
        self.slot_roles = {
            entry["slot"]: (entry["keybind_role"], entry["semantic_role"])
            for entry in contract["slots"]
        }
        self.slots: list[
            tuple[int, tuple[float, float, float, float], tuple[LoadedTemplate, ...]]
        ] = []
        if not isinstance(specs, list):
            return
        for index, spec in enumerate(specs[:4]):
            if not isinstance(spec, Mapping):
                continue
            bounds = spec.get("roi")
            values = {
                key: spec.get(asset_key)
                for key, asset_key in (
                    ("available", "available_template"),
                    ("unavailable", "unavailable_template"),
                )
                if isinstance(spec.get(asset_key), str)
            }
            if not isinstance(bounds, Sequence) or len(bounds) != 4 or len(values) != 2:
                continue
            templates = profile._load_values(values, float(spec.get("threshold", 0.90)))
            slot_index = int(spec.get("slot", index))
            if slot_index not in range(4):
                continue
            self.slots.append((slot_index, _bounds(bounds), templates))

    def read(self, image: ImageU8, roi: ImageU8) -> ReaderResult[list[dict[str, Any]]]:
        del image
        height, width = roi.shape[:2]
        output: list[dict[str, Any]] = []
        confidences: list[float] = []
        for index, bounds, templates in self.slots:
            x1, y1, x2, y2 = bounds
            if not (0 <= x1 < x2 <= 1 and 0 <= y1 < y2 <= 1):
                continue
            left, top = round(x1 * width), round(y1 * height)
            right, bottom = max(left + 1, round(x2 * width)), max(top + 1, round(y2 * height))
            matched = _best_template_match(roi[top:bottom, left:right], templates)
            available: bool | None = None
            if matched.value == "available":
                available = True
            elif matched.value == "unavailable":
                available = False
            keybind, semantic = self.slot_roles[index]
            output.append(
                {
                    "slot": index,
                    "available": available,
                    "charges": None,
                    "confidence": matched.confidence,
                    "keybind_role": keybind,
                    "semantic_role": semantic,
                    "ability_name": None,
                }
            )
            confidences.append(matched.confidence)
        return ReaderResult(
            output if output else None,
            min(confidences, default=0.0),
            ("ability_slot_templates",),
            False,
        )


def _best_template_match(
    roi: ImageU8,
    templates: tuple[LoadedTemplate, ...],
) -> ReaderResult[str]:
    if roi.size == 0 or not templates:
        return ReaderResult(None, 0.0, ("template_unavailable",))
    gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY) if roi.ndim == 3 else roi
    matches: list[tuple[float, LoadedTemplate]] = []
    for template in templates:
        if template.image.shape[0] > gray.shape[0] or template.image.shape[1] > gray.shape[1]:
            continue
        try:
            scores = cv2.matchTemplate(gray, template.image, cv2.TM_CCOEFF_NORMED)
            if not np.isfinite(scores).all():
                continue
            _, score, _, _ = cv2.minMaxLoc(scores)
        except cv2.error:
            continue
        matches.append((max(0.0, min(1.0, float(score))), template))
    matches.sort(key=lambda item: item[0], reverse=True)
    if not matches:
        return ReaderResult(None, 0.0, ("template_size_mismatch",))
    score, winner = matches[0]
    if score < winner.threshold:
        return ReaderResult(None, score, ("template_below_threshold",))
    if len(matches) > 1 and score - matches[1][0] < 0.035:
        return ReaderResult(None, score, ("template_ambiguous",))
    return ReaderResult(winner.name, score, (f"template:{winner.name}",))


def load_profile_readers(
    profile_path: Path | None,
) -> tuple[HudTemplateProfile | None, dict[str, Any]]:
    if profile_path is None or not profile_path.exists():
        return None, {}
    profile = HudTemplateProfile.load(profile_path)
    return profile, profile.build_readers()
