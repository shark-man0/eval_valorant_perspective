import subprocess

import numpy as np
import pytest

from valorant_ai_coach.temporal.killfeed_evidence import matching_alias_words, observe_slot


def tsv(name="Recorder", confidence="95"):
    return (
        f"level\tleft\ttop\twidth\theight\tconf\ttext\n5\t20\t30\t100\t25\t{confidence}\t{name}\n"
    )


@pytest.mark.parametrize(
    "name,confidence",
    [
        ("Other", "99"),
        ("RecorderExtra", "99"),
        ("Recorder", "89.9"),
        ("Recorder", "nan"),
        ("Recorder", "inf"),
        ("Recorder", "101"),
    ],
)
def test_bad_or_partial_alias_is_not_a_victim_match(name, confidence):
    assert matching_alias_words(tsv(name, confidence), "Recorder") == []


def test_exact_alias_casefold_preserves_uncalibrated_ocr_measurement():
    result = matching_alias_words(tsv("RECORDER", "91.5"), "Recorder")
    assert result[0]["confidence"] == 0.915
    assert result[0]["bbox"] == [20, 30, 100, 25]


def test_both_pixel_renderings_must_support_the_same_alias(monkeypatch, tmp_path):
    outputs = iter([tsv(), tsv("Other")])

    def run(*args, **kwargs):
        return subprocess.CompletedProcess(args[0], 0, next(outputs).encode("utf-8"), b"")

    monkeypatch.setattr(subprocess, "run", run)
    result = observe_slot(
        np.zeros((24, 90, 3), dtype=np.uint8),
        "Recorder",
        executable=tmp_path / "reader",
        tessdata=tmp_path,
    )
    assert result["status"] == "UNKNOWN"
    assert result["normal_kill_confirmed"] is False
    assert result["formal_outputs"] == 0


def test_ocr_agreement_is_still_not_normal_death_qualification(monkeypatch, tmp_path):
    monkeypatch.setattr(
        subprocess,
        "run",
        lambda *a, **k: subprocess.CompletedProcess(a[0], 0, tsv().encode("utf-8"), b""),
    )
    result = observe_slot(
        np.zeros((24, 90, 3), dtype=np.uint8),
        "Recorder",
        executable=tmp_path / "reader",
        tessdata=tmp_path,
    )
    assert result["status"] == "supported"
    assert result["death_kind"] == "UNKNOWN"
    assert result["normal_kill_confirmed"] is False
