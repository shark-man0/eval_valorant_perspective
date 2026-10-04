from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import cv2
import numpy as np
import pytest

import valorant_ai_coach.hud.analyzers as analyzers_module
from valorant_ai_coach.hud.analyzers import RealHudAnalyzer
from valorant_ai_coach.hud.classifier import StateClassification
from valorant_ai_coach.hud.hp_glyphs import (
    StrictHpGlyphReader,
    UnavailableStrictHpGlyphReader,
)
from valorant_ai_coach.hud.identity import IdentityEvidence
from valorant_ai_coach.hud.layout import CalibrationResult, HudLayout
from valorant_ai_coach.hud.readers import FrameFeatureObservation, ReaderResult
from valorant_ai_coach.hud.templates import (
    HudTemplateProfile,
    SubregionReader,
)
from valorant_ai_coach.resources import resource_path

FONT = cv2.FONT_HERSHEY_SIMPLEX
FONT_SCALE = 1.0
THICKNESS = 2
GEOMETRY = {
    "center_offset_norm": [-3 / 156, 2 / 156],
    "gap_ratio_bounds": [0.09, 0.299],
    "tolerance_norm": 2 / 156,
}
SUBREGION = [0.1, 0.2, 0.88, 0.68]


def _otsu(image: np.ndarray) -> np.ndarray:
    enlarged = cv2.resize(image, None, fx=2, fy=2, interpolation=cv2.INTER_CUBIC)
    return cv2.threshold(enlarged, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)[1]


def _components(mask: np.ndarray) -> list[tuple[int, int, int, int]]:
    count, _, stats, _ = cv2.connectedComponentsWithStats(mask, connectivity=8)
    return sorted(
        [(int(x), int(y), int(w), int(h)) for x, y, w, h, area in stats[1:count] if area],
        key=lambda item: item[0],
    )


def _normalize(glyph: np.ndarray) -> np.ndarray:
    return StrictHpGlyphReader._normalize_known_white(glyph)


def _draw_digit(canvas: np.ndarray, digit: str, x: int, baseline: int = 38) -> None:
    cv2.putText(canvas, digit, (x, baseline), FONT, FONT_SCALE, 255, THICKNESS, cv2.LINE_8)


def _render(value: str, *, gap: int = 2) -> np.ndarray:
    glyphs: list[np.ndarray] = []
    widths: list[int] = []
    for char in value:
        glyph = np.zeros((48, 32), np.uint8)
        _draw_digit(glyph, char, 0)
        ys, xs = np.where(glyph > 0)
        glyph = glyph[ys.min() : ys.max() + 1, xs.min() : xs.max() + 1]
        glyphs.append(glyph)
        widths.append(glyph.shape[1])
    total = sum(widths) + gap * (len(widths) - 1)
    canvas_width = max(78, total + 10)
    x = (canvas_width - total) // 2
    field = np.zeros((48, canvas_width), np.uint8)
    for glyph, width in zip(glyphs, widths, strict=True):
        field[38 - glyph.shape[0] : 38, x : x + width] = glyph
        x += width + gap
    return field


def _templates() -> dict[str, list[np.ndarray]]:
    result: dict[str, list[np.ndarray]] = {}
    for digit in "0123456789":
        field = np.zeros((48, 78), np.uint8)
        _draw_digit(field, digit, 24)
        components = _components(_otsu(field))
        assert len(components) == 1
        x, y, width, height = components[0]
        result[digit] = [_normalize(_otsu(field)[y : y + height, x : x + width])]
    return result


def _reader(templates: dict[str, list[np.ndarray]] | None = None) -> StrictHpGlyphReader:
    return StrictHpGlyphReader(
        templates or _templates(),
        center_offset_norm=GEOMETRY["center_offset_norm"],
        gap_ratio_bounds=GEOMETRY["gap_ratio_bounds"],
        tolerance_norm=GEOMETRY["tolerance_norm"],
    )


def _profile(
    tmp_path: Path,
    roi_name: str = "player_hp_armor",
    *,
    template_paths: dict[str, str | list[str]] | None = None,
    **overrides: Any,
) -> HudTemplateProfile:
    spec: dict[str, Any] = {
        "kind": "strict_hp_glyphs",
        "templates": template_paths or {digit: f"{digit}.png" for digit in "0123456789"},
        "glyph_threshold": 0.90,
        "glyph_margin": 0.04,
        "subregion_norm": SUBREGION,
        "geometry": GEOMETRY,
    }
    spec.update(overrides)
    profile_path = tmp_path / "hp.templates.json"
    profile_path.write_text(
        json.dumps(
            {"schema_version": "1.0", "anchors": {}, "signals": {}, "readers": {roi_name: spec}}
        ),
        encoding="utf-8",
    )
    for digit in "0123456789":
        mask = _templates()[digit][0]
        paths = spec["templates"].get(digit, []) if isinstance(spec["templates"], dict) else []
        path_values = [paths] if isinstance(paths, str) else paths
        for path in path_values:
            cv2.imwrite(str(tmp_path / path), mask)
    return HudTemplateProfile.load(profile_path)


def test_reader_accepts_two_and_three_digits_but_never_one() -> None:
    reader = _reader()
    for text in ("80", "100"):
        result = reader.read(np.zeros((1, 1), np.uint8), _render(text))
        assert result.value == {"hp": int(text)}
        assert result.confidence >= 0.90
    single = reader.read(np.zeros((1, 1), np.uint8), _render("8"))
    assert single.value is None
    assert "two_or_three" in single.sources[0]
    assert reader.read(np.zeros((1, 1), np.uint8), _render("000")).value is None
    assert reader.read(np.zeros((1, 1), np.uint8), _render("101")).value is None


def test_missing_leading_middle_or_trailing_digit_is_unknown() -> None:
    reader = _reader()
    field = _render("100")
    mask = _otsu(field)
    parts = _components(mask)
    assert len(parts) == 3
    for index, (x, y, width, height) in enumerate(parts):
        mutated = mask.copy()
        mutated[y : y + height, x : x + width] = 0
        # Convert the binary mask back to a 1x gray input with the same foreground.
        raw = cv2.resize(mutated, (78, 48), interpolation=cv2.INTER_NEAREST)
        assert reader.read(np.zeros((1, 1), np.uint8), raw).value is None, index


def test_partial_occlusion_clutter_world_texture_and_flat_fields_are_unknown() -> None:
    reader = _reader()
    field = _render("100")
    for side in ("top", "bottom", "left", "right"):
        clipped = field.copy()
        if side == "top":
            clipped[0, :] = 255
        elif side == "bottom":
            clipped[-1, :] = 255
        elif side == "left":
            clipped[:, 0] = 255
        else:
            clipped[:, -1] = 255
        result = reader.read(np.zeros((1, 1), np.uint8), clipped)
        assert result.value is None
        assert "border" in result.sources[0]

        clipped = field.copy()
        ys, xs = np.where(clipped > 0)
        shifts = {
            "left": (-(int(xs.min())), 0),
            "right": (clipped.shape[1] - 1 - int(xs.max()), 0),
            "top": (0, -(int(ys.min()))),
            "bottom": (0, clipped.shape[0] - 1 - int(ys.max())),
        }
        dx, dy = shifts[side]
        clipped = cv2.warpAffine(
            clipped,
            np.float32([[1, 0, dx], [0, 1, dy]]),
            (clipped.shape[1], clipped.shape[0]),
            flags=cv2.INTER_NEAREST,
            borderMode=cv2.BORDER_CONSTANT,
        )
        touched = {
            "left": np.any(clipped[:, 0]),
            "right": np.any(clipped[:, -1]),
            "top": np.any(clipped[0, :]),
            "bottom": np.any(clipped[-1, :]),
        }
        assert touched[side]
        clipped_result = reader.read(np.zeros((1, 1), np.uint8), clipped)
        assert clipped_result.value is None
        assert "border" in clipped_result.sources[0]

    partial = field.copy()
    partial[14:31, 24:28] = 0
    assert reader.read(np.zeros((1, 1), np.uint8), partial).value is None

    extra = _render("1008")
    assert reader.read(np.zeros((1, 1), np.uint8), extra).value is None
    noisy = np.random.default_rng(9).integers(0, 256, (48, 78), dtype=np.uint8)
    assert reader.read(np.zeros((1, 1), np.uint8), noisy).value is None
    extra_component = field.copy()
    extra_component[2, 2] = 255
    extra_result = reader.read(np.zeros((1, 1), np.uint8), extra_component)
    assert extra_result.value is None
    assert "two_or_three_components" in extra_result.sources[0]
    assert reader.read(np.zeros((1, 1), np.uint8), np.zeros((48, 78), np.uint8)).value is None


def test_unknown_font_competing_class_and_malformed_rois_are_unknown() -> None:
    reader = _reader()
    different = np.zeros((48, 78), np.uint8)
    cv2.putText(different, "100", (6, 33), cv2.FONT_HERSHEY_COMPLEX, 0.7, 255, 2, cv2.LINE_8)
    assert reader.read(np.zeros((1, 1), np.uint8), different).value is None

    conflicting = _templates()
    conflicting["4"] = [conflicting["1"][0].copy()]
    assert _reader(conflicting).read(np.zeros((1, 1), np.uint8), _render("100")).value is None

    for roi in (
        np.zeros((48, 78), dtype=np.int64),
        np.zeros((48, 78, 4), dtype=np.uint8),
        np.zeros((0, 78), dtype=np.uint8),
    ):
        assert reader.read(np.zeros((1, 1), np.uint8), roi).value is None


def test_constructor_rejects_incomplete_and_invalid_references_or_geometry() -> None:
    refs = _templates()
    incomplete = dict(refs)
    incomplete.pop("7")
    with pytest.raises(ValueError, match="exactly digits"):
        _reader(incomplete)
    for bad_ref in (
        np.zeros((31, 24), np.uint8),
        np.zeros((32, 24), np.uint8),
        np.full((32, 24), 7, np.uint8),
    ):
        invalid = dict(refs)
        invalid["1"] = [bad_ref]
        with pytest.raises(ValueError):
            _reader(invalid)
    with pytest.raises(ValueError, match="center_offset_norm"):
        StrictHpGlyphReader(
            refs,
            center_offset_norm=[0.1, -0.1],
            gap_ratio_bounds=GEOMETRY["gap_ratio_bounds"],
            tolerance_norm=GEOMETRY["tolerance_norm"],
        )
    with pytest.raises(ValueError, match="tolerance_norm"):
        StrictHpGlyphReader(
            refs,
            center_offset_norm=GEOMETRY["center_offset_norm"],
            gap_ratio_bounds=GEOMETRY["gap_ratio_bounds"],
            tolerance_norm=float("nan"),
        )
    with pytest.raises(ValueError, match="gap_ratio_bounds"):
        StrictHpGlyphReader(
            refs,
            center_offset_norm=GEOMETRY["center_offset_norm"],
            gap_ratio_bounds=[0.0, 1.0],
            tolerance_norm=GEOMETRY["tolerance_norm"],
        )
    with pytest.raises(ValueError, match="center_offset_norm"):
        StrictHpGlyphReader(
            refs,
            center_offset_norm=[-0.08, 0.08],
            gap_ratio_bounds=GEOMETRY["gap_ratio_bounds"],
            tolerance_norm=GEOMETRY["tolerance_norm"],
        )
    with pytest.raises(ValueError, match="tolerance_norm"):
        StrictHpGlyphReader(
            refs,
            center_offset_norm=GEOMETRY["center_offset_norm"],
            gap_ratio_bounds=GEOMETRY["gap_ratio_bounds"],
            tolerance_norm=0.05,
        )


def test_factory_role_subregion_geometry_and_reference_list_fingerprint(tmp_path: Path) -> None:
    profile = _profile(
        tmp_path,
        template_paths={d: [f"{d}.png", f"{d}_alt.png"] for d in "0123456789"},
    )
    readers = profile.build_readers()
    assert isinstance(readers["player_hp_armor"], SubregionReader)
    assert len([p for p in profile.asset_paths if p.name in {"1.png", "1_alt.png"}]) == 2
    before = profile.fingerprint(resource_path("config/hud_layout_1080p_v3.json"))
    (tmp_path / "1_alt.png").write_bytes((tmp_path / "0.png").read_bytes())
    after = HudTemplateProfile.load(profile.path).fingerprint(
        resource_path("config/hud_layout_1080p_v3.json")
    )
    assert before != after

    wrong_role = _profile(tmp_path, "round_timer")
    assert isinstance(wrong_role.build_readers()["round_timer"], UnavailableStrictHpGlyphReader)
    assert any(
        "only supported for player_hp_armor" in item for item in wrong_role.reader_diagnostics
    )

    for overrides in (
        {"subregion_norm": None},
        {"subregion_norm": [True, 0.2, 0.88, 0.68]},
        {"glyph_threshold": 0.89},
        {"glyph_margin": 0.05},
        {"geometry": {"center_offset_norm": [-1, 1]}},
        {"templates": {digit: f"{digit}.png" for digit in "012345678"}},
    ):
        invalid = _profile(tmp_path, **overrides)
        assert isinstance(
            invalid.build_readers()["player_hp_armor"], UnavailableStrictHpGlyphReader
        )
        assert invalid.reader_diagnostics


def test_invalid_wrong_role_hp_config_blocks_timer_ocr_fallback(tmp_path: Path) -> None:
    profile = _profile(tmp_path, "round_timer", template_paths={"0": "0.png"})

    class StubOcr:
        calls = 0

        def read(self, image: np.ndarray, roi: np.ndarray) -> ReaderResult[str]:
            self.calls += 1
            return ReaderResult("1:40", 0.99, ("fallback_stub",))

    class StubScores:
        def read(self, image: np.ndarray, roi: np.ndarray) -> ReaderResult[None]:
            del image, roi
            return ReaderResult(None, 0.0, ("score_stub",))

    fallback = StubOcr()
    analyzer = RealHudAnalyzer(
        resource_path("config/hud_layout_1080p_v3.json"),
        ocr_reader=fallback,
        readers={"ally_score": StubScores(), "enemy_score": StubScores()},
        template_profile_path=profile.path,
    )
    assert isinstance(analyzer.readers["round_timer"], UnavailableStrictHpGlyphReader)
    values = {"round_time_remaining_sec": None, "score_ally": None, "score_enemy": None}
    from valorant_ai_coach.hud.models import empty_hud_values

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


def test_real_analyzer_clears_nonlive_and_never_carries_prior_hp(
    tmp_path: Path, monkeypatch
) -> None:
    layout_path = resource_path("config/hud_layout_1080p_v3.json")
    _, h, _, w = 0, 1080, 0, 1920
    analyzer_subregion = (76 / 220, 76 / 153, 154 / 220, 124 / 153)
    hp_reader = SubregionReader(_reader(), analyzer_subregion)

    class FakeFeatures:
        def observe_sequence(self, frames, **kwargs):
            return [
                FrameFeatureObservation(
                    time_sec=float(index),
                    metrics={},
                    signals={"frame_width": w, "frame_height": h},
                    roi_confidence={},
                    calibration_anchor_presence={},
                )
                for index, _ in enumerate(frames)
            ]

    class FixedClassifier:
        primary_state = "live_first_person"

        def classify(self, signals):
            live = self.primary_state == "live_first_person"
            return StateClassification(
                primary_state=self.primary_state,
                state_flags=(),
                remote_view_type="none",
                player_specific_hud_valid=live,
                is_player_world_view_trustworthy=live,
                confidence=0.95,
                flag_confidence={},
            )

    monkeypatch.setattr(
        analyzers_module, "live_identity", lambda *a, **k: IdentityEvidence(True, 3, "test")
    )
    monkeypatch.setattr(
        HudLayout, "validate_calibration", lambda *a, **k: CalibrationResult(True, (), 4, 0.0, 0.0)
    )
    analyzer = RealHudAnalyzer(
        layout_path,
        readers={"player_hp_armor": hp_reader},
        template_profile_path=tmp_path / "absent.json",
    )
    analyzer.feature_reader = FakeFeatures()
    classifier = FixedClassifier()
    analyzer.state_classifier = classifier

    def frame_with_hp(field: np.ndarray | None) -> np.ndarray:
        frame = np.zeros((h, w, 3), np.uint8)
        if field is not None:
            frame[925:1078, 500:720][76:124, 76:154] = cv2.cvtColor(field, cv2.COLOR_GRAY2BGR)
        return frame

    live_result = analyzer.observe_frames(
        [frame_with_hp(_render("100")), frame_with_hp(None)],
        anchor_detections={},
        letterboxed=False,
        crop_applied=False,
    )
    assert live_result.observations[0]["values"]["hp"] == 100
    assert live_result.observations[1]["values"]["hp"] is None

    classifier.primary_state = "spectator_first_person"
    nonlive = analyzer.observe_frames(
        [frame_with_hp(_render("100"))],
        anchor_detections={},
        letterboxed=False,
        crop_applied=False,
    )
    assert nonlive.observations[0]["values"]["player_specific_hud_valid"] is False
    assert nonlive.observations[0]["values"]["hp"] is None
