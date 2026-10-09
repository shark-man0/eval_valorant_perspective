import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.diagnostics import diagnose_result_text as diagnostic  # noqa: E402
from tests.unit.test_native_scene_correspondence_diagnostic import inputs  # noqa: E402
from valorant_ai_coach.hud.readers import ReaderResult  # noqa: E402


def method():
    return {"version": "semantic_result_ocr_diagnostic_v1", "language": "eng", "psm": 7,
            "minimum_confidence": .90, "roi": "phase", "subregion_norm": [0, 0, 1, 1]}


@pytest.mark.parametrize("text,score,expected", [
    (" TEAM  ACE ", .95, "TEAM ACE"), ("victory", .90, "VICTORY"),
    ("TEAM ACF", .99, None), ("TEAM ACE!", .99, None), ("TEAM ACE", .899, None),
    ("TEAM AGE", .96, None),
    (None, 1.0, None), ("TEAM ACE", True, None), ("ACE", float("nan"), None),
    ("ACE", 1.1, None), ("this is a TEAM ACE", .99, None),
])
def test_result_grammar_never_repairs_text_or_relaxes_confidence(text, score, expected):
    assert diagnostic.accepted_result(text, score) == expected


@pytest.mark.parametrize("change", [{"minimum_confidence": .8}, {"psm": True},
                                   {"language": "jpn"}, {"preprocessing": "arbitrary"},
                                   {"subregion_norm": [0, 0, 1, float("nan")]}])
def test_changed_frozen_method_is_rejected(tmp_path, change):
    path = tmp_path / "method.json"
    path.write_text(json.dumps({**method(), **change}))
    with pytest.raises(ValueError):
        diagnostic.load_method(path)


@pytest.mark.parametrize("version,psm,valid", [
    ("semantic_result_rawline_ocr_diagnostic_v1", 13, True),
    ("semantic_result_rawline_ocr_diagnostic_v1", 7, False),
    ("semantic_result_ocr_diagnostic_v1", 13, False),
    ("semantic_result_rawline_ocr_diagnostic_v1", True, False),
])
def test_rawline_is_a_separate_frozen_method_not_an_override(tmp_path, version, psm, valid):
    path = tmp_path / "rawline.json"
    path.write_text(json.dumps({**method(), "version": version, "psm": psm}))
    if valid:
        assert diagnostic.load_method(path)["psm"] == 13
    else:
        with pytest.raises(ValueError):
            diagnostic.load_method(path)


def fixture(tmp_path, monkeypatch, *, mutate_model=False, language="eng", rawline=False):
    video, native, layout, declared = inputs(tmp_path)
    declaration = method()
    if rawline:
        declaration.update(version="semantic_result_rawline_ocr_diagnostic_v1", psm=13)
    if language == "jpn":
        declaration.update(version="combat_report_text_ocr_diagnostic_v1",
                           language="jpn", roi="combat_report")
        layout_data = json.loads(layout.read_text())
        layout_data["regions"]["combat_report"] = layout_data["regions"].pop("phase")
        layout.write_text(json.dumps(layout_data))
    declared.write_text(json.dumps(declaration))
    tessdata = tmp_path / "tessdata"
    tessdata.mkdir()
    model = tessdata / f"{language}.traineddata"
    model.write_bytes(b"synthetic language fixture, not qualified data")
    executable = tmp_path / "tesseract"
    executable.write_bytes(b"synthetic executable fixture")

    class Reader:
        diagnostics = []

        def __init__(self, **kwargs):
            assert kwargs == {"language": language, "psm": 13 if rawline else 7,
                              "tessdata_dir": str(tessdata)}
            self.executable = str(executable)

        def read(self, image, roi):
            assert roi.size > 0
            if mutate_model:
                model.write_bytes(b"changed")
            return ReaderResult("アビリティー" if language == "jpn" else "TEAM ACE",
                                .95, ("synthetic OCR",))

    monkeypatch.setattr(diagnostic, "TesseractTextReader", Reader)
    return video, native, layout, declared, tmp_path / "private-output", tessdata


def test_text_recognition_never_emits_events_or_installs_profile(tmp_path, monkeypatch):
    args = fixture(tmp_path, monkeypatch)
    result = diagnostic.run(*args)
    assert result["events_emitted"] == 0
    assert result["profile_adopted"] is False
    assert result["qualification_created"] is False
    assert result["trained_language_sha256"] == diagnostic.sha256_file(args[5] / "eng.traineddata")
    assert all(row["accepted_result_text"] == "TEAM ACE" and not row["round_end_emitted"]
               for window in result["windows"] for row in window["rows"])
    assert (args[4] / "selection.json").exists()
    assert (args[4] / "results.json").exists()


def test_rawline_mode_reaches_reader_without_promoting_result(tmp_path, monkeypatch):
    args = fixture(tmp_path, monkeypatch, rawline=True)
    result = diagnostic.run(*args)
    assert result["method"]["psm"] == 13
    assert result["text_role"] == "result"
    assert result["events_emitted"] == 0
    assert result["qualification_created"] is False
    assert result["profile_adopted"] is False


def test_model_mutation_cannot_produce_completed_diagnostic(tmp_path, monkeypatch):
    args = fixture(tmp_path, monkeypatch, mutate_model=True)
    with pytest.raises(ValueError, match="input changed"):
        diagnostic.run(*args)
    assert not (args[4] / "results.json").exists()


def test_changed_frame_cannot_be_ocr_evidence(tmp_path, monkeypatch):
    args = fixture(tmp_path, monkeypatch)
    (args[1] / "window-000/frame_000001.png").write_bytes(b"changed")
    with pytest.raises(ValueError, match="frame hash"):
        diagnostic.run(*args)
    assert not (args[4] / "results.json").exists()


@pytest.mark.parametrize("bad_pts", [True, float("nan"), "1.0", 0.5])
def test_unordered_or_invalid_pts_cannot_be_ocr_evidence(tmp_path, monkeypatch, bad_pts):
    args = fixture(tmp_path, monkeypatch)
    path = args[1] / "results.json"
    report = json.loads(path.read_text())
    report["windows"][0]["rows"][1]["pts_sec"] = bad_pts
    path.write_text(json.dumps(report))
    with pytest.raises(ValueError, match="source PTS"):
        diagnostic.run(*args)
    assert not (args[4] / "results.json").exists()


@pytest.mark.parametrize("preprocessing", ["gray_v1", "white210_v1", "white210_horizontal2_v1"])
def test_declared_preprocessing_preserves_no_event_contract(tmp_path, monkeypatch, preprocessing):
    args = fixture(tmp_path, monkeypatch)
    args[3].write_text(json.dumps({**method(), "preprocessing": preprocessing}))
    result = diagnostic.run(*args)
    assert result["method"]["preprocessing"] == preprocessing
    assert result["events_emitted"] == 0 and not result["qualification_created"]


@pytest.mark.parametrize("text,confidence,expected", [
    ("ラウンド が 進行 中", .95, "ラウンドが進行中"), ("アビリティー", .95, "アビリティー"),
    ("アビリティ一", .99, None), ("ラウンドが進行田", .99, None),
    ("アビリティー", .89, None), ("TEAM ACE", .99, None), (None, 1.0, None),
])
def test_report_text_does_not_repair_characters_or_infer_absent_state(text, confidence, expected):
    assert diagnostic.accepted_report_text(text, confidence) == expected


def test_ability_report_text_is_not_an_ended_round(tmp_path, monkeypatch):
    args = fixture(tmp_path, monkeypatch, language="jpn")
    result = diagnostic.run(*args)
    assert result["text_role"] == "combat_report"
    assert result["trained_language_sha256"] == diagnostic.sha256_file(args[5] / "jpn.traineddata")
    for window in result["windows"]:
        for row in window["rows"]:
            assert row["accepted_report_text"] == "アビリティー"
            assert row["accepted_result_text"] is None
            assert row["round_end_emitted"] is False
            assert "ended" not in row and "state" not in row
