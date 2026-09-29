import json
import subprocess
from pathlib import Path
from unittest.mock import patch

import cv2
import numpy as np
import pytest

from valorant_ai_coach.hud.layout import HudLayout
from valorant_ai_coach.hud.readers import ReaderResult
from valorant_ai_coach.hud.templates import (
    HudTemplateProfile,
    NumericFieldsReader,
    SegmentedDigitsReader,
    SubregionReader,
    TemplateValueReader,
    TesseractDigitsReader,
    TesseractTextReader,
    load_profile_readers,
)
from valorant_ai_coach.resources import resource_path


def _asset(root: Path, name: str, seed: int = 1) -> np.ndarray:
    image = np.random.default_rng(seed).integers(0, 255, (24, 28, 3), dtype=np.uint8)
    assert cv2.imwrite(str(root / name), image)
    return image


def _profile(root: Path, **sections) -> HudTemplateProfile:
    path = root / "profile.json"
    path.write_text(json.dumps({"schema_version": "1.0", **sections}), encoding="utf-8")
    return HudTemplateProfile.load(path)


def test_profile_readers_match_values_weapon_abilities_and_signals(tmp_path):
    image = _asset(tmp_path, "yes.png")
    _asset(tmp_path, "no.png", 2)
    profile = _profile(
        tmp_path,
        readers={
            "spike_top_center": {"kind": "template_values", "values": {"planted": "yes.png"}},
            "weapon_inventory": {"kind": "weapon_templates", "values": {"Vandal": "yes.png"}},
            "abilities": {
                "kind": "ability_slots",
                "slots": [
                    {
                        "slot": 3,
                        "roi": [0, 0, 1, 1],
                        "available_template": "yes.png",
                        "unavailable_template": "no.png",
                    }
                ],
            },
        },
        signals={
            "spectated_player_panel": {"roi": "spectated_player_panel", "template": "yes.png"}
        },
    )
    readers = profile.build_readers()
    assert readers["spike_top_center"].read(image, image).value == "planted"
    assert readers["weapon_inventory"].read(image, image).value == {"weapon_text": "Vandal"}
    slot = readers["abilities"].read(image, image).value[0]
    assert slot["slot"] == 3 and slot["available"] is True
    assert slot["semantic_role"] == "ultimate"
    layout = HudLayout.load(resource_path("config/hud_layout_1080p_v3.json"))
    frame = np.full((1080, 1920, 3), 60, dtype=np.uint8)
    x1, y1, _, _ = layout.normalized_roi("spectated_player_panel").pixel_bounds(1920, 1080)
    frame[y1 : y1 + 24, x1 : x1 + 28] = image
    assert profile.detect_signals(frame, layout)["spectated_player_panel"] is True
    assert not profile.detect_signals(np.zeros_like(frame), layout)


def test_ambiguous_templates_do_not_choose_arbitrary_label(tmp_path):
    image = _asset(tmp_path, "same.png")
    profile = _profile(tmp_path)
    reader = TemplateValueReader(
        tuple(profile.load_template(name, "same.png") for name in ("a", "b"))
    )
    assert reader.read(image, image).value is None
    assert reader.read(image, np.zeros((3, 3, 3), dtype=np.uint8)).value is None


def test_profile_validation_missing_assets_and_fingerprint(tmp_path):
    with pytest.raises(ValueError, match="schema_version"):
        HudTemplateProfile(tmp_path / "bad.json", {})
    with pytest.raises(ValueError, match="object"):
        HudTemplateProfile(tmp_path / "bad.json", {"schema_version": "1.0", "readers": []})
    profile = _profile(
        tmp_path,
        readers={"bad": {"kind": "template_values", "values": {"a": "missing.png"}}},
        signals={"bad": {}},
    )
    assert not profile.build_readers()
    assert len(profile.reader_diagnostics) >= 2
    assert load_profile_readers(tmp_path / "missing.json") == (None, {})
    layout_path = resource_path("config/hud_layout_1080p_v3.json")
    first = profile.fingerprint(layout_path)
    _asset(tmp_path, "missing.png")
    assert first != profile.fingerprint(layout_path)
    with pytest.raises(ValueError, match="threshold"):
        profile.load_template("a", "missing.png", float("nan"))
    assert cv2.imwrite(str(tmp_path / "blank.png"), np.zeros((10, 10), dtype=np.uint8))
    with pytest.raises(ValueError, match="コントラスト"):
        profile.load_template("blank", "blank.png")


def test_tesseract_tsv_success_invalid_text_and_timeout():
    image = np.full((15, 30, 3), 128, dtype=np.uint8)
    with patch("valorant_ai_coach.hud.templates.shutil.which", return_value="tesseract"):
        reader = TesseractDigitsReader()
    row = "5\t1\t1\t1\t1\t1\t0\t0\t20\t20\t94\t1:40\n"
    with patch(
        "valorant_ai_coach.hud.templates.subprocess.run",
        return_value=subprocess.CompletedProcess([], 0, ("header\n" + row).encode(), b""),
    ) as run:
        result = reader.read(image, image)
        assert result.value == "1:40" and result.confidence == pytest.approx(0.94)
        assert run.call_args.args[0][-1] == "tsv"
    with patch(
        "valorant_ai_coach.hud.templates.subprocess.run",
        return_value=subprocess.CompletedProcess(
            [], 0, ("header\n" + row.replace("1:40", "WORD")).encode(), b""
        ),
    ):
        assert reader.read(image, image).value is None
    with patch(
        "valorant_ai_coach.hud.templates.subprocess.run",
        side_effect=subprocess.TimeoutExpired("tesseract", 2),
    ):
        assert reader.read(image, image).value is None
    reader.executable = None
    assert reader.read(image, image).value is None


def _tsv_row(text: str, confidence: str = "94") -> str:
    return f"5\t1\t1\t1\t1\t1\t0\t0\t20\t20\t{confidence}\t{text}\n"


def _languages(*names: str) -> subprocess.CompletedProcess[bytes]:
    body = "List of available languages (test):\n" + "\n".join(names) + "\n"
    return subprocess.CompletedProcess([], 0, body.encode("utf-8"), b"")


def test_text_ocr_missing_executable_or_language_stays_unknown_with_diagnostics() -> None:
    image = np.zeros((24, 80, 3), dtype=np.uint8)
    with patch("valorant_ai_coach.hud.templates.shutil.which", return_value=None):
        no_executable = TesseractTextReader(language="jpn+eng")
    result = no_executable.read(image, image)
    assert result.value is None
    assert "tesseract_unavailable" in result.sources

    with (
        patch("valorant_ai_coach.hud.templates.shutil.which", return_value="/test/tesseract"),
        patch("valorant_ai_coach.hud.templates.subprocess.run", return_value=_languages("eng")),
    ):
        missing_language = TesseractTextReader(language="jpn+eng")
    result = missing_language.read(image, image)
    assert result.value is None and result.confidence == 0
    assert "tesseract_language_missing:jpn" in result.sources


def test_text_ocr_aggregates_unicode_tsv_words_and_keeps_min_confidence() -> None:
    image = np.zeros((24, 80, 3), dtype=np.uint8)
    with (
        patch("valorant_ai_coach.hud.templates.shutil.which", return_value="/test/tesseract"),
        patch(
            "valorant_ai_coach.hud.templates.subprocess.run",
            return_value=_languages("eng", "jpn"),
        ),
    ):
        reader = TesseractTextReader(language="jpn+eng")
    tsv = (
        "level\tpage_num\tblock_num\tpar_num\tline_num\tword_num\t"
        "left\ttop\twidth\theight\tconf\ttext\n"
    )
    tsv += _tsv_row("A", "96") + _tsv_row("メイン", "91")
    with patch(
        "valorant_ai_coach.hud.templates.subprocess.run",
        return_value=subprocess.CompletedProcess([], 0, tsv.encode("utf-8"), b""),
    ) as run:
        result = reader.read(image, image)
    assert result.value == "A メイン"
    assert result.confidence == pytest.approx(0.91)
    assert run.call_args.args[0][run.call_args.args[0].index("-l") + 1] == "jpn+eng"
    malformed = tsv.replace("\t91\tメイン", "\tnan\tメイン")
    with patch(
        "valorant_ai_coach.hud.templates.subprocess.run",
        return_value=subprocess.CompletedProcess([], 0, malformed.encode("utf-8"), b""),
    ):
        result = reader.read(image, image)
    assert result.value is None
    assert "tesseract_invalid_text_confidence" in result.sources


def test_text_reader_profile_config_uses_executable_language_and_tessdata(
    tmp_path: Path,
) -> None:
    image = np.zeros((24, 80, 3), dtype=np.uint8)
    profile = _profile(
        tmp_path,
        readers={"location_label": {
            "kind": "text", "language": "jpn+eng", "executable": "tesseract-test",
            "tessdata_dir": "tessdata", "psm": 7,
        }},
    )
    header = (
        "level\tpage_num\tblock_num\tpar_num\tline_num\tword_num\t"
        "left\ttop\twidth\theight\tconf\ttext\n"
    )
    calls = [
        _languages("eng", "jpn"),
        subprocess.CompletedProcess([], 0, (header + _tsv_row("A", "95")).encode(), b""),
    ]
    with (
        patch("valorant_ai_coach.hud.templates.shutil.which", return_value="/test/tesseract"),
        patch("valorant_ai_coach.hud.templates.subprocess.run", side_effect=calls) as run,
    ):
        readers = profile.build_readers()
        result = readers["location_label"].read(image, image)
    assert isinstance(readers["location_label"], TesseractTextReader)
    assert result.value == "A" and result.confidence == pytest.approx(0.95)
    for call in run.call_args_list:
        command = call.args[0]
        assert "--tessdata-dir" in command
        assert str(tmp_path / "tessdata") in command
    assert not profile.reader_diagnostics

    missing_language_dir = tmp_path / "missing-language"
    missing_language_dir.mkdir()
    missing_profile = _profile(
        missing_language_dir,
        readers={"location_label": {"kind": "text", "language": "jpn"}},
    )
    with (
        patch("valorant_ai_coach.hud.templates.shutil.which", return_value="/test/tesseract"),
        patch("valorant_ai_coach.hud.templates.subprocess.run", return_value=_languages("eng")),
    ):
        missing_profile.build_readers()
    assert any(
        "reader location_label: tesseract_language_missing:jpn" in message
        for message in missing_profile.reader_diagnostics
    )


@pytest.mark.parametrize("threshold", [-1, 256, True, 200.5, "200"])
def test_white_text_preprocessing_rejects_invalid_config(threshold):
    with pytest.raises(ValueError, match="white_text_threshold"):
        TesseractDigitsReader(white_text_threshold=threshold)


def test_white_text_preprocessing_is_opt_in_and_keeps_ocr_confidence():
    image = np.full((15, 30, 3), 128, dtype=np.uint8)
    image[5:10, 8:15] = 240
    reader = TesseractDigitsReader(white_text_threshold=200)
    reader.executable = "tesseract"
    row = "5\t1\t1\t1\t1\t1\t0\t0\t20\t20\t94\t1:40\n"
    with patch("valorant_ai_coach.hud.templates.subprocess.run",
               return_value=subprocess.CompletedProcess([], 0, ("header\n" + row).encode(), b"")):
        result = reader.read(image, image)
    assert result.value == "1:40"
    assert result.confidence == .94


@pytest.mark.parametrize("confidence", ["nan", "inf", "-1", "101", "invalid"])
def test_digit_ocr_rejects_invalid_confidence_without_partial_result(confidence):
    reader = TesseractDigitsReader()
    reader.executable = "tesseract"
    image = np.zeros((20, 40, 3), dtype=np.uint8)
    tsv = "header\n" + _tsv_row("1", "95") + _tsv_row("00", confidence)
    with patch("valorant_ai_coach.hud.templates.subprocess.run",
               return_value=subprocess.CompletedProcess([], 0, tsv.encode(), b"")):
        result = reader.read(image, image)
    assert result.value is None and result.confidence == 0
    assert "tesseract_invalid_digit_confidence" in result.sources


@pytest.mark.parametrize("text", ["1714", "13", "1:99", "1:4", "1:40:00"])
def test_timer_profile_rejects_ambiguous_ocr_format(tmp_path, text):
    reader = SegmentedDigitsReader(
        _profile(tmp_path), {"format": "timer_mmss"}, fallback=FixedReader(text, .99)
    )
    image = np.zeros((20, 60, 3), dtype=np.uint8)
    result = reader.read(image, image)
    assert result.value is None and result.confidence == 0
    assert "timer_ocr_format_invalid" in result.sources


class FixedReader:
    def __init__(self, value=None, confidence=0.95):
        self.result = ReaderResult(value, confidence)

    def read(self, image, roi):
        return self.result


def test_reader_subregion_is_configurable_without_changing_confidence():
    class ShapeReader:
        def read(self, image, roi):
            assert roi.shape == (30, 40, 3)
            return ReaderResult("100", .71)
    reader = SubregionReader(ShapeReader(), (.2, .1, .6, .4))
    image = np.zeros((100, 100, 3), dtype=np.uint8)
    result = reader.read(image, image)
    assert result.value == "100" and result.confidence == .71


def test_digit_templates_and_composite_field_crops(tmp_path):
    image = np.zeros((48, 40, 3), dtype=np.uint8)
    cv2.putText(image, "8", (6, 37), cv2.FONT_HERSHEY_SIMPLEX, 1.2, (255, 255, 255), 2)
    assert cv2.imwrite(str(tmp_path / "8.png"), image)
    profile = _profile(tmp_path)
    reader = SegmentedDigitsReader(
        profile, {"templates": {"8": "8.png"}, "glyph_threshold": 0.7}, fallback=FixedReader()
    )
    assert reader.read(image, image).value == "8"
    fields = NumericFieldsReader({"hp": (0, 0, 1, 1)}, reader)
    assert fields.read(image, image).value == {"hp": 8}
    reader.fallback = FixedReader("9")
    assert reader.read(image, image).value is None
    reader.fallback = FixedReader("8", 0.8)
    assert reader.read(image, image).cross_checked is True
    assert reader.read(image, np.empty((0, 0, 3), dtype=np.uint8)).value == "8"


def test_timer_format_and_reader_factory(tmp_path):
    profile = _profile(
        tmp_path,
        readers={
            "round_timer": {
                "kind": "digits",
                "format": "timer_mmss",
                "executable": "not-installed-test-ocr",
            },
            "player_hp_armor": {
                "kind": "fields",
                "fields": {"hp": [0, 0, 0.5, 1], "armor": [0.5, 0, 1, 1]},
                "executable": "not-installed-test-ocr",
            },
        },
    )
    loaded, readers = load_profile_readers(profile.path)
    assert loaded is not None and len(readers) == 2
    image = np.zeros((20, 60, 3), dtype=np.uint8)
    timer = readers["round_timer"]
    with patch.object(timer, "_read_templates", return_value=ReaderResult("140", 0.95)):
        assert timer.read(image, image).value == "1:40"
    with patch.object(timer, "_read_templates", return_value=ReaderResult("199", 0.95)):
        assert timer.read(image, image).value is None
    assert readers["player_hp_armor"].read(image, image).value is None
