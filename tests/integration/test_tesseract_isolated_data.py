"""Exercise the real TSV renderer with language data but no config directory."""

import re
import shutil
import subprocess

import cv2
import numpy as np
import pytest

from valorant_ai_coach.hud.templates import TesseractTextReader


def test_isolated_language_directory_produces_same_tsv_result_as_default(tmp_path):
    executable = shutil.which("tesseract")
    if executable is None:
        pytest.skip("local Tesseract executable unavailable")
    query = subprocess.run([executable, "--list-langs"], capture_output=True, text=True,
                           check=True, timeout=5)
    match = re.search(r'List of available languages in "([^"]+)"', query.stdout + query.stderr)
    if match is None:
        pytest.skip("local language data directory not reported")
    from pathlib import Path

    model = Path(match[1]) / "eng.traineddata"
    if not model.is_file():
        pytest.skip("local English model unavailable")
    isolated = tmp_path / "tessdata"
    isolated.mkdir()
    shutil.copy2(model, isolated / "eng.traineddata")
    assert not (isolated / "configs").exists()
    image = np.full((100, 400, 3), 255, np.uint8)
    cv2.putText(image, "HELLO", (20, 70), cv2.FONT_HERSHEY_SIMPLEX, 2, (0, 0, 0), 3,
                cv2.LINE_AA)
    default = TesseractTextReader(language="eng").read(image, image)
    assert default.value == "HELLO"
    custom_reader = TesseractTextReader(language="eng", tessdata_dir=str(isolated))
    assert not custom_reader.diagnostics
    assert custom_reader.read(image, image) == default
