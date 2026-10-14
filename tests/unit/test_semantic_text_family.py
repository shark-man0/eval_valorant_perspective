"""Synthetic safety controls; these tests never qualify real source captions."""
import json

import numpy as np
import pytest

from tests.unit.test_glyph_contrast_guard import semantic_reference, write_profile
from tests.unit.test_result_structure_diagnostic import text_image
from valorant_ai_coach.hud.glyph_contrast import GlyphContrastGuard
from valorant_ai_coach.hud.layout import HudLayout, NormalizedRoi
from valorant_ai_coach.hud.semantic_text import SemanticTextFamily
from valorant_ai_coach.hud.templates import HudTemplateProfile


def references():
    return {
        label: semantic_reference(text_image(label), GlyphContrastGuard(text_image(label)))
        for label in ("TEAM ACE", "GAME ACT")
    }


def test_family_requires_one_complete_caption_not_a_mix_of_good_groups():
    refs = references()
    family = SemanticTextFamily(refs)
    for label in refs:
        image = text_image(label)
        assert family.score(image) >= .9
        measurement = family.measure(image)
        assert measurement["score"] == family.score(image)
        assert measurement["matched_caption"] == label
        assert measurement["absence_checked"] is False
        assert measurement["runtime_transition_authorized"] is False
    mixed = text_image("TEAM ACE")
    mixed[:, 180:] = text_image("GAME ACT")[:, 180:]
    assert all(ref.score(mixed) < .9 for ref in refs.values())
    assert family.measure(mixed)["presence"] is None
    assert family.score(np.full_like(mixed, 25)) == 0
    assert family.score(mixed[:3, :2]) == 0


@pytest.mark.parametrize("case", ["one", "many", "empty", "unguarded", "threshold"])
def test_family_rejects_unsafe_definitions(case):
    refs = references()
    if case == "one":
        refs.pop("GAME ACT")
    elif case == "many":
        refs = {str(i): next(iter(refs.values())) for i in range(9)}
    elif case == "empty":
        refs[""] = refs.pop("GAME ACT")
    elif case == "unguarded":
        refs["GAME ACT"] = semantic_reference(text_image("GAME ACT"))
    else:
        refs["GAME ACT"].threshold = .95
    with pytest.raises(ValueError):
        SemanticTextFamily(refs)


def family_profile(tmp_path):
    write_profile(tmp_path)
    path = tmp_path / "profile.json"
    data = json.loads(path.read_text())
    base = data["signals"]["round_end_template"]
    variant = {key: base[key] for key in (
        "template", "mask", "support_regions", "training", "contrast_guard",
    )}
    variant["label"] = "additional"
    base["variants"] = [variant]
    path.write_text(json.dumps(data))
    return path


def test_profile_family_is_opt_in_and_preserves_unknown_and_measurement(tmp_path):
    path = family_profile(tmp_path)
    profile = HudTemplateProfile.load(path)
    assert not profile.reader_diagnostics
    assert isinstance(profile._semantic_text["round_end_template"], SemanticTextFamily)
    layout = HudLayout("1.0", True, (360, 90), {
        "round_end_banner": NormalizedRoi(0, 0, 1, 1),
    })
    assert profile.detect_signals(text_image(), layout)["round_end_template"] is True
    records = {}
    signals = profile.detect_signals(text_image("TEAM AGE"), layout,
                                     semantic_diagnostics=records)
    assert "round_end_template" not in signals
    assert records["round_end_template"]["presence"] is None
    assert records["round_end_template"]["absence_checked"] is False


def test_variant_only_asset_changes_invalidate_profile_fingerprint(tmp_path):
    path = family_profile(tmp_path)
    data = json.loads(path.read_text())
    variant = data["signals"]["round_end_template"]["variants"][0]
    asset = tmp_path / "variant-only.png"
    asset.write_bytes((tmp_path / "word.png").read_bytes())
    variant["template"] = asset.name
    path.write_text(json.dumps(data))
    profile = HudTemplateProfile.load(path)
    assert not profile.reader_diagnostics
    layout = tmp_path / "layout.json"
    layout.write_text("{}")
    before = profile.fingerprint(layout)
    asset.write_bytes(asset.read_bytes() + b"changed")
    assert profile.fingerprint(layout) != before


@pytest.mark.parametrize("case", [
    "role", "matcher", "empty", "duplicate", "bad_training", "missing_guard",
    "missing_primary_guard", "threshold_override", "bad_asset",
])
def test_malformed_variant_disables_signal_without_primary_fallback(tmp_path, case):
    path = family_profile(tmp_path)
    data = json.loads(path.read_text())
    spec = data["signals"]["round_end_template"]
    variant = spec["variants"][0]
    if case == "role":
        spec["roi"] = "center_phase_banner"
    elif case == "matcher":
        spec["matcher"] = "plain_pixels"
    elif case == "empty":
        spec["variants"] = []
    elif case == "duplicate":
        variant["label"] = "primary"
    elif case == "bad_training":
        variant["training"] = []
    elif case == "missing_guard":
        variant.pop("contrast_guard")
    elif case == "missing_primary_guard":
        spec.pop("contrast_guard")
    elif case == "threshold_override":
        variant["threshold"] = .1
    else:
        variant["template"] = "missing.png"
    path.write_text(json.dumps(data))
    profile = HudTemplateProfile.load(path)
    assert "round_end_template" not in profile._signal_templates
    assert "round_end_template" not in profile._semantic_text
    assert profile.reader_diagnostics
