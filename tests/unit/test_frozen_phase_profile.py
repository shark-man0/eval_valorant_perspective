import hashlib
import json
import shutil
import sys
from pathlib import Path

import cv2
import numpy as np
import pytest

from valorant_ai_coach.hud.layout import HudLayout
from valorant_ai_coach.hud.templates import HudTemplateProfile

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.diagnostics.build_frozen_phase_profile import build_profile  # noqa: E402


def inputs(tmp_path):
    archive = tmp_path / "archive"
    reference_dir = tmp_path / "reference"
    base = tmp_path / "base"
    for directory in (archive, reference_dir, base):
        directory.mkdir()
    image = np.random.default_rng(123).integers(20, 235, (40, 120), dtype=np.uint8)
    regions = np.zeros(image.shape, np.uint8)
    for group in (1, 2, 3):
        regions[5:35, (group - 1) * 40 + 5:group * 40 - 5] = group
    mask = np.asarray(regions > 0, dtype=np.uint8) * 255
    hashes = {}
    for name, value in [("reference.png", image), ("mask.png", mask), ("groups.png", regions)]:
        assert cv2.imwrite(str(reference_dir / name), value)
        hashes[name] = hashlib.sha256((reference_dir / name).read_bytes()).hexdigest()
    training = []
    for index in range(3):
        pixels = image.copy()
        pixels[0, 0] = index
        path = archive / f"source-{index}.png"
        assert cv2.imwrite(str(path), pixels)
        training.append({"frame": path.name,
                         "frame_sha256": hashlib.sha256(path.read_bytes()).hexdigest()})
    manifest = {"crop_xyxy": [0, 0, 120, 40], "threshold": 0.9,
                "asset_hashes": hashes, "training_frames": training}
    (reference_dir / "frozen-manifest.json").write_text(json.dumps(manifest))
    layout_path = base / "base.json"
    layout_path.write_text(json.dumps({
        "schema_version": "1.0", "roi_coordinate_system": "normalized_0_to_1",
        "calibrated": True, "reference_resolution": {"width": 120, "height": 40},
        "regions": {"center_phase_banner": {"x": 0, "y": 0, "width": 1, "height": 1}},
    }))
    shutil.copy2(reference_dir / "reference.png", base / "anchor.png")
    layout_path.with_suffix(".templates.json").write_text(json.dumps({
        "schema_version": "1.0", "ocr_fallback_rois": [],
        "anchors": {"round_timer": {"template": "anchor.png", "threshold": 0.9,
                                    "search_region": "center_phase_banner"}},
    }))
    return layout_path, reference_dir, archive, image


def test_frozen_profile_preserves_base_and_moves_as_one_directory(tmp_path):
    layout, reference, archive, image = inputs(tmp_path)
    before = layout.with_suffix(".templates.json").read_bytes()
    generated = build_profile(layout, reference, archive, tmp_path / "generated")
    assert layout.with_suffix(".templates.json").read_bytes() == before
    assert generated.read_bytes() == layout.read_bytes()
    profile = HudTemplateProfile.load(generated.with_suffix(".templates.json"))
    assert profile.reader_diagnostics == []
    assert profile.raw["anchors"]["round_timer"]["threshold"] == 0.9
    assert profile.raw["signals"]["buy_phase_template"]["threshold"] == 0.9
    assert all(not path.is_absolute() for path in profile.asset_paths)
    moved = tmp_path / "moved"
    shutil.move(str(generated.parent), moved)
    loaded = HudTemplateProfile.load(moved / "hud_layout.templates.json")
    signals = loaded.detect_signals(image, HudLayout.load(moved / "hud_layout.json"))
    assert signals["buy_phase_template"] is True
    assert signals["buy_phase_template_matcher"] == "semantic_text_ncc_v1"
    assert signals.get("self_hud_identity_trustworthy") is not True
    assert "buy_phase_template" not in loaded.detect_signals(
        np.zeros_like(image), HudLayout.load(moved / "hud_layout.json")
    )


@pytest.mark.parametrize("mutation", ["asset", "training", "threshold", "crop", "escape"])
def test_invalid_frozen_inputs_leave_no_published_profile(tmp_path, mutation):
    layout, reference, archive, _ = inputs(tmp_path)
    manifest_path = reference / "frozen-manifest.json"
    manifest = json.loads(manifest_path.read_text())
    if mutation == "asset":
        (reference / "mask.png").write_bytes(b"corrupt")
    elif mutation == "training":
        (archive / "source-0.png").write_bytes(b"corrupt")
    elif mutation == "threshold":
        manifest["threshold"] = 0.89
    elif mutation == "crop":
        manifest["crop_xyxy"] = [-1, 0, 120, 40]
    else:
        manifest["training_frames"][0]["frame"] = "../outside.png"
    manifest_path.write_text(json.dumps(manifest))
    output = tmp_path / "invalid"
    with pytest.raises(ValueError):
        build_profile(layout, reference, archive, output)
    assert not output.exists()


def test_frozen_profile_refuses_to_overwrite_previous_candidate(tmp_path):
    layout, reference, archive, _ = inputs(tmp_path)
    output = tmp_path / "previous"
    output.mkdir()
    with pytest.raises(FileExistsError):
        build_profile(layout, reference, archive, output)


def test_generation_rejects_source_change_without_publishing(tmp_path, monkeypatch):
    import scripts.diagnostics.build_frozen_phase_profile as module

    layout, reference, archive, _ = inputs(tmp_path)
    bundle = module._bundle_assets

    def mutate(raw, stage):
        result = bundle(raw, stage)
        image = cv2.imread(str(reference / "reference.png"), cv2.IMREAD_GRAYSCALE)
        image[0, 0] = 0
        assert cv2.imwrite(str(reference / "reference.png"), image)
        return result

    monkeypatch.setattr(module, "_bundle_assets", mutate)
    output = tmp_path / "mutated"
    with pytest.raises(ValueError, match="changed during generation"):
        build_profile(layout, reference, archive, output)
    assert not output.exists()


def test_reader_audit_preserves_original_return_and_input_objects():
    from scripts.diagnostics.diagnose_round_lifecycle import AuditedReader
    from valorant_ai_coach.hud.readers import ReaderResult

    image = np.zeros((4, 5), np.uint8)
    roi = image[:2]
    result = ReaderResult(None, 0.0, ("strict_timer_glyph_below_0_90",))

    class Reader:
        def read(self, actual_image, actual_roi):
            assert actual_image is image
            assert actual_roi is roi
            return result

    pending = []
    audit = AuditedReader("round_timer", Reader(), pending)
    assert audit.read(image, roi) is result
    assert pending == [{
        "role": "round_timer", "value": None, "confidence": 0.0,
        "sources": ["strict_timer_glyph_below_0_90"], "cross_checked": False,
    }]


def test_diagnostic_gaussian_timer_keeps_gates_and_original_assets():
    from scripts.diagnostics.diagnose_round_lifecycle import (
        FixedGaussianTimerComparison,
        diagnostic_timer_comparison,
    )
    from tests.unit.test_timer_glyphs import _templates
    from valorant_ai_coach.hud.templates import SubregionReader
    from valorant_ai_coach.hud.timer_glyphs import StrictTimerGlyphReader

    original = StrictTimerGlyphReader(_templates())
    original_assets = {digit: refs[0].copy() for digit, refs in original.templates.items()}
    wrapped = diagnostic_timer_comparison(SubregionReader(original, (0.1, 0.2, 0.8, 0.9)))
    assert wrapped.bounds == (0.1, 0.2, 0.8, 0.9)
    assert isinstance(wrapped.reader, FixedGaussianTimerComparison)
    assert wrapped.reader.THRESHOLD == original.THRESHOLD == 0.90
    assert wrapped.reader.CLASS_MARGIN == original.CLASS_MARGIN == 0.04
    for digit, ref in original_assets.items():
        np.testing.assert_array_equal(original.templates[digit][0], ref)
        np.testing.assert_array_equal(wrapped.reader.templates[digit][0],
                                      cv2.GaussianBlur(ref, (3, 3), 0))
    blank = np.zeros((48, 69), np.uint8)
    assert wrapped.reader.read(blank, blank) == original.read(blank, blank)
    with pytest.raises(ValueError, match="configured strict timer"):
        diagnostic_timer_comparison(None)


@pytest.mark.parametrize("malformation", ["missing_colon", "double_colon", "dot", "slash"])
def test_diagnostic_gaussian_does_not_relax_timer_structure(malformation):
    from scripts.diagnostics.diagnose_round_lifecycle import FixedGaussianTimerComparison
    from tests.unit.test_timer_glyphs import _render_timer, _templates
    from valorant_ai_coach.hud.timer_glyphs import StrictTimerGlyphReader

    original = StrictTimerGlyphReader(_templates())
    candidate = FixedGaussianTimerComparison(original)
    field = _render_timer("1:14", extra=malformation)
    assert original.read(field, field).value is None
    assert candidate.read(field, field).value is None
