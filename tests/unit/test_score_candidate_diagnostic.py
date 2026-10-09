import hashlib
import json
import sys
from pathlib import Path

import cv2
import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.diagnostics.score_numeric import (  # noqa: E402
    DiagnosticScoreReader,
    load_score_candidate,
)
from tests.unit.test_timer_glyphs import _templates  # noqa: E402
from valorant_ai_coach.hud.timer_glyphs import StrictTimerGlyphReader  # noqa: E402


def field(text):
    templates = _templates()
    canvas = np.zeros((48, 100), np.uint8)
    cursor = 10
    for digit in text:
        ref = templates[digit][0]
        x, y, width, height = cv2.boundingRect(cv2.findNonZero(ref))
        canvas[10:10 + height, cursor:cursor + width] = ref[y:y + height, x:x + width]
        cursor += width + 6
    return canvas


def score_templates():
    # Synthetic training references use the frozen score foreground pipeline,
    # not timer Otsu references. This is a grammar test, not real qualification.
    refs = {}
    for digit in "0123456789":
        enlarged = cv2.resize(field(digit), None, fx=2, fy=2, interpolation=cv2.INTER_CUBIC)
        _, mask = cv2.threshold(enlarged, 200, 255, cv2.THRESH_BINARY)
        refs[digit] = [StrictTimerGlyphReader._normalize_known_white(mask)]
    return refs


@pytest.mark.parametrize("text", ["0", "1", "2", "12", "29"])
def test_frozen_score_grammar_recognizes_zero_and_one_or_two_digits(text):
    reader = DiagnosticScoreReader(score_templates())
    image = field(text)
    result = reader.read(image, image)
    assert result.value == text
    assert result.confidence >= .90
    assert reader.THRESHOLD == .90 and reader.CLASS_MARGIN == .04
    assert len(reader.templates) == 10


@pytest.mark.parametrize("text", ["00", "02", "123"])
def test_score_does_not_repair_leading_zero_or_three_digits(text):
    image = field(text)
    assert DiagnosticScoreReader(score_templates()).read(image, image).value is None


def test_blank_border_extra_component_and_missing_alphabet_fail_closed():
    reader = DiagnosticScoreReader(score_templates())
    image = field("1")
    for invalid in [np.zeros_like(image), np.empty((0, 0), np.uint8),
                    image.astype(np.float32)]:
        assert reader.read(invalid, invalid).value is None
    image[0, 0] = 255
    assert reader.read(image, image).sources == ("strict_score_foreground_touches_roi_border",)
    image = field("1")
    image[30:34, 65:69] = 255
    image[20:24, 80:84] = 255
    assert reader.read(image, image).value is None
    refs = score_templates()
    del refs["9"]
    with pytest.raises(ValueError):
        DiagnosticScoreReader(refs)


def candidate(tmp_path):
    specs = {}
    refs = score_templates()
    for digit, images in refs.items():
        assert cv2.imwrite(str(tmp_path / f"{digit}.png"), images[0])
    for role in ("ally_score", "enemy_score"):
        specs[role] = {
            "kind": "strict_score_glyphs", "glyph_threshold": .90, "glyph_margin": .04,
            "comparison_preprocessing": "gaussian3x3_v1", "foreground_preprocessing": "white200_v1",
            "subregion_norm": [0, 0, 1, 1],
            "templates": {digit: f"{digit}.png" for digit in refs},
        }
    path = tmp_path / "candidate.json"
    path.write_text(json.dumps({"readers": specs}))
    return path, specs


def test_candidate_hash_binds_assets_and_never_rewrites_input(tmp_path):
    path, _ = candidate(tmp_path)
    before = path.read_bytes()
    readers, initial = load_score_candidate(path)
    assert set(readers) == {"ally_score", "enemy_score"}
    assert path.read_bytes() == before
    pixels = cv2.imread(str(tmp_path / "0.png"), cv2.IMREAD_GRAYSCALE)
    pixels[0, 0] = 255
    assert cv2.imwrite(str(tmp_path / "0.png"), pixels)
    _, after = load_score_candidate(path)
    assert initial != after


@pytest.mark.parametrize("invalid", ["threshold", "bool", "margin", "escape", "bounds", "role"])
def test_unfrozen_candidate_declaration_rejected(tmp_path, invalid):
    path, specs = candidate(tmp_path)
    spec = specs["ally_score"]
    if invalid == "threshold":
        spec["glyph_threshold"] = .89
    elif invalid == "bool":
        spec["glyph_threshold"] = True
    elif invalid == "margin":
        spec["glyph_margin"] = .03
    elif invalid == "escape":
        spec["templates"]["0"] = "../0.png"
    elif invalid == "bounds":
        spec["subregion_norm"] = [0, 0, 2, 1]
    else:
        del specs["enemy_score"]
    path.write_text(json.dumps({"readers": specs}))
    with pytest.raises(ValueError):
        load_score_candidate(path)


def cohort(tmp_path):
    source = tmp_path / "source"
    source.mkdir()
    image = field("1")
    assert cv2.imwrite(str(source / "frame.png"), image)
    digest = hashlib.sha256((source / "frame.png").read_bytes()).hexdigest()
    layout = tmp_path / "layout.json"
    layout.write_text(json.dumps({
        "schema_version": "1.0", "roi_coordinate_system": "normalized_0_to_1",
        "calibrated": True, "reference_resolution": {"width": 100, "height": 48},
        "regions": {role: {"x": 0, "y": 0, "width": 1, "height": 1}
                    for role in ("ally_score", "enemy_score")},
    }))
    manifest = tmp_path / "manifest.json"
    data = {"source_video_sha256": "a" * 64, "windows": [{"split": "holdout", "rows": [{
        "frame_sha256": digest, "source_pts_ticks": 10, "time_base": "1/100", "pts_sec": .1,
    }]}]}
    manifest.write_text(json.dumps(data))
    return layout, manifest, source, data


def test_source_replay_uses_hash_bound_frames_without_claiming_calibration(tmp_path):
    from scripts.diagnostics.replay_score_cohort import replay

    path, _ = candidate(tmp_path)
    layout, manifest, source, _ = cohort(tmp_path)
    result = replay(layout, path, manifest, source)
    assert result["geometry_calibration_claimed"] is False
    assert [row["value"] for row in result["observations"]] == ["1", "1"]
    assert all("expected" not in row for row in result["observations"])
    assert all(not isinstance(value, Path) for row in result["observations"]
               for value in row.values())


@pytest.mark.parametrize("invalid", ["hash", "pts"])
def test_source_replay_rejects_wrong_image_and_pts_binding(tmp_path, invalid):
    from scripts.diagnostics.replay_score_cohort import replay

    path, _ = candidate(tmp_path)
    layout, manifest, source, data = cohort(tmp_path)
    if invalid == "hash":
        (source / "frame.png").write_bytes(b"changed")
    else:
        data["windows"][0]["rows"][0]["pts_sec"] = .2
        manifest.write_text(json.dumps(data))
    with pytest.raises(ValueError):
        replay(layout, path, manifest, source)
