from __future__ import annotations

import json
from pathlib import Path

import cv2
import numpy as np
import pytest

from valorant_ai_coach.hud.analyzers import RealHudAnalyzer
from valorant_ai_coach.hud.layout import CalibrationResult
from valorant_ai_coach.hud.models import empty_hud_values
from valorant_ai_coach.hud.readers import ReaderResult
from valorant_ai_coach.hud.templates import HudTemplateProfile, SubregionReader
from valorant_ai_coach.hud.timer_glyphs import (
    StrictTimerGlyphReader,
    UnavailableStrictTimerGlyphReader,
)
from valorant_ai_coach.resources import resource_path


def _normalize_reference(glyph: np.ndarray) -> np.ndarray:
    points = cv2.findNonZero(glyph)
    assert points is not None
    x, y, width, height = cv2.boundingRect(points)
    crop = glyph[y : y + height, x : x + width]
    scale = min(18 / width, 26 / height)
    resized = cv2.resize(
        crop,
        (max(1, round(width * scale)), max(1, round(height * scale))),
        interpolation=cv2.INTER_NEAREST,
    )
    result = np.zeros((32, 24), np.uint8)
    top, left = (32 - resized.shape[0]) // 2, (24 - resized.shape[1]) // 2
    result[top : top + resized.shape[0], left : left + resized.shape[1]] = resized
    return result


def _templates() -> dict[str, list[np.ndarray]]:
    result = {}
    for digit in "0123456789":
        canvas = np.zeros((60, 120), np.uint8)
        cv2.putText(canvas, digit, (10, 44), cv2.FONT_HERSHEY_SIMPLEX, 1, 255, 2, cv2.LINE_AA)
        _, mask = cv2.threshold(canvas, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        result[digit] = [_normalize_reference(mask)]
    return result


def _render_timer(text: str, *, extra: str = "", clip_left: bool = False) -> np.ndarray:
    """Render a source-like 69x48 field from the known-white digit masks."""
    templates = _templates()
    field = np.zeros((48, 69), np.uint8)
    minute, seconds = text.split(":") if ":" in text else (text, "")
    height = 20 if len(minute) == 2 else 26
    glyphs: list[tuple[str, np.ndarray]] = []
    for digit in minute + seconds:
        ref = templates[digit][0]
        points = cv2.findNonZero(ref)
        assert points is not None
        x0, y0, width, height = cv2.boundingRect(points)
        glyph = ref[y0 : y0 + height, x0 : x0 + width]
        if len(minute) == 2:
            glyph = cv2.resize(
                glyph,
                (max(1, round(width * 20 / height)), 20),
                interpolation=cv2.INTER_NEAREST,
            )
        glyphs.append((digit, glyph))
    minute_count = len(minute)
    if minute_count == 1:
        x_positions = [2, 23, 42]
        colon_x = 17
    else:
        x_positions = [2, 10, 31, 46]
        colon_x = 26
    positions = [(glyph, x) for (_, glyph), x in zip(glyphs, x_positions, strict=True)]
    for glyph, x in positions:
        top = (field.shape[0] - glyph.shape[0]) // 2
        field[top : top + glyph.shape[0], x : x + glyph.shape[1]] = np.maximum(
            field[top : top + glyph.shape[0], x : x + glyph.shape[1]], glyph
        )
    if extra != "missing_colon":
        for y in (18, 26):
            cv2.rectangle(field, (colon_x, y), (colon_x + 2, y + 2), 255, -1)
    if extra == "double_colon":
        for y in (4, 12):
            cv2.rectangle(field, (62, y), (64, y + 2), 255, -1)
    elif extra == "dot":
        cv2.rectangle(field, (63, 36), (65, 38), 255, -1)
    elif extra == "slash":
        cv2.line(field, (3, 5), (8, 37), 255, 1)
    elif extra == "missing_colon":
        pass
    if clip_left:
        field = np.pad(field[:, 3:], ((0, 0), (0, 3)))
    return field


def _render_two_minute_timer() -> np.ndarray:
    templates = _templates()
    field = np.zeros((48, 80), np.uint8)
    for digit, x in zip("1259", (2, 12, 36, 55), strict=True):
        ref = templates[digit][0]
        points = cv2.findNonZero(ref)
        assert points is not None
        x0, y0, width, height = cv2.boundingRect(points)
        glyph = ref[y0 : y0 + height, x0 : x0 + width]
        top = (field.shape[0] - height) // 2
        field[top : top + height, x : x + width] = np.maximum(
            field[top : top + height, x : x + width], glyph
        )
    for y in (18, 26):
        cv2.rectangle(field, (31, y), (33, y + 2), 255, -1)
    return field


def _reader(templates: dict[str, list[np.ndarray]] | None = None) -> StrictTimerGlyphReader:
    return StrictTimerGlyphReader(templates or _templates())


def _save_profile_assets(root: Path) -> dict[str, str]:
    assets = {}
    for digit, refs in _templates().items():
        name = f"digit_{digit}.png"
        assert cv2.imwrite(str(root / name), refs[0])
        assets[digit] = name
    return assets


def _profile(root: Path, roi_name: str = "round_timer", **spec: object) -> HudTemplateProfile:
    path = root / "profile.json"
    path.write_text(
        json.dumps({"schema_version": "1.0", "readers": {roi_name: spec}}), encoding="utf-8"
    )
    return HudTemplateProfile.load(path)


def test_reads_fixed_timer_format_and_returns_minimum_glyph_score() -> None:
    reader = _reader()
    image = _render_timer("1:14")
    result = reader.read(image, image)
    assert result.value == "1:14"
    assert result.confidence >= 0.90
    assert result.sources == ("strict_timer_glyphs",)
    assert result.cross_checked is False
    two_minute_field = _render_two_minute_timer()
    assert reader.read(two_minute_field, two_minute_field).value == "12:59"
    out_of_range = _render_timer("1:60")
    invalid_seconds = reader.read(out_of_range, out_of_range)
    assert invalid_seconds.value is None
    assert "seconds_out_of_range" in invalid_seconds.sources[0]


def test_strict_parser_rejects_malformed_separator_clipping_and_empty_input() -> None:
    reader = _reader()
    assert (
        reader.read(
            np.zeros((48, 69), np.uint8), _render_timer("1:14", extra="missing_colon")
        ).value
        is None
    )
    assert (
        reader.read(np.zeros((48, 69), np.uint8), _render_timer("1:14", extra="double_colon")).value
        is None
    )
    assert (
        reader.read(np.zeros((48, 69), np.uint8), _render_timer("1:14", extra="dot")).value is None
    )
    assert (
        reader.read(np.zeros((48, 69), np.uint8), _render_timer("1:14", extra="slash")).value
        is None
    )
    assert (
        reader.read(np.zeros((48, 69), np.uint8), _render_timer("1:14", clip_left=True)).value
        is None
    )
    assert reader.read(np.zeros((48, 69), np.uint8), np.zeros((48, 69), np.uint8)).value is None
    assert reader.read(np.zeros((0, 0), np.uint8), np.zeros((0, 0), np.uint8)).value is None
    unsupported_dtype = np.zeros((48, 69, 3), np.int64)
    assert reader.read(unsupported_dtype, unsupported_dtype).value is None


def test_partial_alphabet_and_near_class_conflicts_stay_unknown() -> None:
    templates = _templates()
    del templates["8"]
    with pytest.raises(ValueError, match="exactly digits"):
        StrictTimerGlyphReader(templates)
    templates = _templates()
    templates["4"] = [templates["1"][0].copy()]
    result = _reader(templates).read(np.zeros((48, 69), np.uint8), _render_timer("1:14"))
    assert result.value is None
    assert "competitor_gap" in result.sources[0]


def test_malformed_template_keys_shapes_and_masks_are_rejected() -> None:
    templates = _templates()
    templates["x"] = [templates["1"][0]]
    with pytest.raises(ValueError, match="exactly digits"):
        StrictTimerGlyphReader(templates)
    templates = _templates()
    templates["1"] = [np.zeros((24, 32), np.uint8)]
    with pytest.raises(ValueError, match="32x24"):
        StrictTimerGlyphReader(templates)
    templates = _templates()
    templates["1"] = [np.full((32, 24), 255, np.uint8)]
    with pytest.raises(ValueError, match="blank or flat"):
        StrictTimerGlyphReader(templates)
    templates = _templates()
    templates["1"] = [np.full((32, 24), 7, np.uint8)]
    with pytest.raises(ValueError, match="binary mask"):
        StrictTimerGlyphReader(templates)
    templates = _templates()
    templates["1"] = [np.full((32, 24), np.nan)]  # type: ignore[list-item]
    with pytest.raises(ValueError, match="uint8 32x24"):
        StrictTimerGlyphReader(templates)


def test_factory_is_round_timer_only_and_uses_existing_subregion(tmp_path: Path) -> None:
    assets = _save_profile_assets(tmp_path)
    profile = _profile(
        tmp_path,
        kind="strict_timer_glyphs",
        templates=assets,
        glyph_threshold=0.90,
        glyph_margin=0.04,
        subregion_norm=[28 / 125, 18 / 85, 97 / 125, 66 / 85],
    )
    reader = profile.build_readers()["round_timer"]
    assert isinstance(reader, SubregionReader)
    full_roi = np.zeros((85, 125), np.uint8)
    field = _render_timer("1:14")
    full_roi[18:66, 28:97] = field
    assert reader.read(full_roi, full_roi).value == "1:14"

    wrong_role = _profile(tmp_path, "player_hp_armor", kind="strict_timer_glyphs", templates=assets)
    assert not wrong_role.build_readers()
    assert any("only supported for round_timer" in x for x in wrong_role.reader_diagnostics)


def test_factory_reports_empty_incomplete_nan_and_relaxed_threshold_profiles(
    tmp_path: Path,
) -> None:
    assets = _save_profile_assets(tmp_path)
    empty = _profile(tmp_path, kind="strict_timer_glyphs", templates={})
    assert isinstance(empty.build_readers()["round_timer"], UnavailableStrictTimerGlyphReader)
    assert any("exactly digits" in x for x in empty.reader_diagnostics)

    incomplete = dict(assets)
    incomplete.pop("7")
    profile = _profile(tmp_path, kind="strict_timer_glyphs", templates=incomplete)
    assert isinstance(profile.build_readers()["round_timer"], UnavailableStrictTimerGlyphReader)
    assert profile.reader_diagnostics

    for threshold in (0.5, float("nan")):
        profile = _profile(
            tmp_path,
            kind="strict_timer_glyphs",
            templates=assets,
            glyph_threshold=threshold,
            glyph_margin=0.04,
        )
        assert isinstance(profile.build_readers()["round_timer"], UnavailableStrictTimerGlyphReader)
        assert any("fixed at 0.90" in x for x in profile.reader_diagnostics)

    margin = _profile(
        tmp_path,
        kind="strict_timer_glyphs",
        templates=assets,
        glyph_threshold=0.90,
        glyph_margin=0.0,
    )
    assert isinstance(margin.build_readers()["round_timer"], UnavailableStrictTimerGlyphReader)
    assert any("fixed at 0.04" in x for x in margin.reader_diagnostics)


def test_invalid_opt_in_timer_profile_fails_closed_instead_of_using_ocr(tmp_path: Path) -> None:
    assets = _save_profile_assets(tmp_path)
    assets.pop("8")
    profile = _profile(
        tmp_path,
        kind="strict_timer_glyphs",
        templates=assets,
        glyph_threshold=0.90,
        glyph_margin=0.04,
    )

    class StubReader:
        calls = 0

        def read(self, image: np.ndarray, roi: np.ndarray):
            self.calls += 1
            return ReaderResult("1:40", 0.99, ("fallback_stub",))

    fallback = StubReader()
    analyzer = RealHudAnalyzer(
        resource_path("config/hud_layout_1080p_v3.json"),
        ocr_reader=fallback,
        template_profile_path=profile.path,
        readers={
            "ally_score": StrictTimerGlyphReader(_templates()),
            "enemy_score": StrictTimerGlyphReader(_templates()),
        },
    )
    assert isinstance(analyzer.readers["round_timer"], UnavailableStrictTimerGlyphReader)
    values = empty_hud_values()
    analyzer._read_values(
        np.zeros((1080, 1920, 3), np.uint8),
        values,
        {},
        CalibrationResult(True, (), 0, None, None),
        [],
    )
    assert fallback.calls == 0
    assert values["round_time_remaining_sec"] is None
    assert any("exactly digits" in item for item in analyzer.profile_diagnostics)
