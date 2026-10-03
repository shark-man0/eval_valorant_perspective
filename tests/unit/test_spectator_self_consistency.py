<<<<<<< HEAD
from __future__ import annotations

import json
from pathlib import Path
from typing import Any
=======
import copy
import json
>>>>>>> 4a5f013ee504d22dea6dac02ccf62b9b7d280de5

import cv2
import numpy as np
import pytest
<<<<<<< HEAD

from valorant_ai_coach.hud.spectator import (
    detect_panel,
    freeze_panel_reference,
    generate_panel_reference,
    local_component_scores,
    validate_panel_reference,
=======
from test_e2e_share_report import _inputs

from scripts.e2e.calibration_report import sanitize_calibration
from scripts.e2e.share_report import MAX_REPORT_BYTES, export_report
from valorant_ai_coach.hud.spectator import (
    PanelReference,
    component_match_diagnostics,
    detect_panel,
    generate_panel_reference,
    local_component_scores,
    panel_components,
>>>>>>> 4a5f013ee504d22dea6dac02ccf62b9b7d280de5
)
from valorant_ai_coach.hud.templates import HudTemplateProfile


<<<<<<< HEAD
def _fixture_scene() -> tuple[np.ndarray, np.ndarray]:
    """Small deterministic UI-like scene with three separated edge families."""
    gray = np.full((128, 176), 36, dtype=np.uint8)
    labels = np.zeros_like(gray)
    # Boundary fragments.
    cv2.line(gray, (12, 22), (61, 22), 220, 2)
    cv2.line(labels, (10, 20), (63, 24), 1, 1)
    # Portrait frame edges.
    cv2.rectangle(gray, (75, 20), (107, 67), 215, 2)
    cv2.rectangle(labels, (72, 17), (110, 70), 2, 1)
    # Three short aligned text rows.
    for y, width in ((30, 36), (42, 28), (54, 33)):
        cv2.line(gray, (119, y), (119 + width, y), 205, 2)
        cv2.line(labels, (116, y - 3), (158, y + 3), 3, 1)
    return gray, labels


def _shift(image: np.ndarray, dx: int, dy: int) -> Any:
    matrix = np.asarray([[1, 0, dx], [0, 1, dy]], dtype=np.float32)
    return cv2.warpAffine(image, matrix, (image.shape[1], image.shape[0]))


def _encode_png(path: Path, image: np.ndarray) -> None:
=======
def panel(panel_images, y=8, fragmented=False):
    image = cv2.cvtColor(panel_images(160, 126)[0], cv2.COLOR_BGR2GRAY)
    image[:20] = 60
    split = 45 if y == 96 else 72
    for left, right in ((5, split), (split + 8, 155)) if fragmented else ((5, 155),):
        cv2.line(image, (left, y), (right, y), 230, 2)
    return image


@pytest.mark.parametrize("y", [8, 40, 96])
@pytest.mark.parametrize("fragmented", [False, True])
@pytest.mark.parametrize("shift", [-2, -1, 0, 1, 2])
def test_component_contract_all_topologies_fragments_and_rigid_offsets(
    panel_images, y, fragmented, shift
):
    image = panel(panel_images, y, fragmented)
    reference = panel_components(image)
    assert isinstance(reference, PanelReference)
    shifted = cv2.warpAffine(
        image, np.float32([[1, 0, shift], [0, 1, -shift]]), (160, 126), borderValue=60
    )
    result = component_match_diagnostics(shifted, reference)
    assert result["passed"]
    assert result["dx"] == shift and result["dy"] == -shift
    assert min(local_component_scores(shifted.copy(), reference.copy())) == 1
    for component in result["components"]:
        assert component["matched_expected_count"] == component["expected_count"]
        assert component["matched_observed_count"] == component["observed_count"]


def test_old_neighbourhood_contract_can_reject_its_own_valid_source(panel_images):
    image = panel(panel_images)
    # Adjacent real decoration changes which structural frame is selected;
    # the legacy precision neighbourhood includes edges absent from its labels.
    cv2.line(image, (6, 3), (154, 3), 230, 1)
    diagnostics = {}
    reference = panel_components(image, diagnostics)
    assert reference is not None
    legacy = diagnostics["legacy_self_match"]
    assert legacy["passed"] is False
    assert legacy["limiting_component"] == "portrait"
    assert legacy["components"][1]["precision"] < 0.90
    assert min(local_component_scores(image.copy(), reference)) == 1


def test_outside_support_edges_do_not_corrupt_precision(panel_images):
    image = panel(panel_images)
    reference = panel_components(image)
    cv2.rectangle(image, (115, 105), (145, 120), 220, 2)
    assert min(local_component_scores(image, reference)) == 1


def test_inside_support_conflict_lowers_precision_and_blocks_presence(panel_images):
    image = panel(panel_images)
    reference = panel_components(image)
    cv2.line(image, (5, 32), (5, 83), 230, 1)
    result = component_match_diagnostics(image, reference)
    assert result["components"][1]["precision"] < 0.90
    assert result["components"][0]["score"] >= 0.90
    assert result["components"][2]["score"] >= 0.90
    assert detect_panel(image, reference)["checked"] is False
    assert detect_panel(image, reference)["panel_present"] is None


@pytest.mark.parametrize("kind", ["portrait", "text", "boundary", "partial", "independent"])
def test_single_or_incoherent_components_are_not_positive_or_clear(panel_images, kind):
    image = panel(panel_images)
    reference = panel_components(image)
    if kind == "portrait":
        image[:20] = 60
        image[:, 50:] = 60
    elif kind == "text":
        image[:20] = 60
        image[:, :50] = 60
    elif kind == "boundary":
        image[20:] = 60
    elif kind == "partial":
        image[35:90, 50:] = 60
    else:
        text = image[25:90, 50:].copy()
        image[25:90, 50:] = cv2.warpAffine(
            text, np.float32([[1, 0, 8], [0, 1, 0]]), (110, 65), borderValue=60
        )
    result = detect_panel(image, reference)
    assert result["checked"] is False
    assert result["panel_present"] is None


def test_reference_assets_roundtrip_and_missing_support_fail_closed(tmp_path, panel_images):
    image = panel(panel_images)
    reference = panel_components(image)
    assert isinstance(reference, PanelReference)
    for name, pixels in (
        ("template", reference),
        ("support_regions", reference.regions),
        ("orientation", reference.orientation),
    ):
        ok, encoded = cv2.imencode(".png", pixels)
        assert ok
        (tmp_path / f"{name}.png").write_bytes(encoded.tobytes())
    config = {
        "version": 2,
        **{k: f"{k}.png" for k in ("template", "support_regions", "orientation")},
    }
    raw = {"schema_version": "1.0", "spectator_panel_detector": config}
    profile = HudTemplateProfile(tmp_path / "profile.json", raw)
    assert isinstance(profile._panel_components, PanelReference)
    assert min(local_component_scores(image, profile._panel_components)) == 1
    assert {p.name for p in profile._find_asset_paths(profile.raw)} == {
        "template.png",
        "support_regions.png",
        "orientation.png",
    }
    config["support_regions"] = "missing.png"
    invalid = HudTemplateProfile(tmp_path / "bad.json", raw)
    assert invalid._panel_components is None
    assert invalid.reader_diagnostics


def test_failed_support_diagnostics_self_scores_private_bounded_and_local_unchanged(
    panel_images, tmp_path
):
    image = panel(panel_images)
    stats = {}
    assert generate_panel_reference([image, image, *[np.zeros_like(image)] * 6], stats) is None
    candidate = stats["candidate_support"][0]
    assert candidate["training_support"] == 1
    assert candidate["self_match"]["passed"] is True
    assert candidate["self_match"]["minimum_score"] == 1
    assert candidate["failed_support_scores"]["count"] == 3
    assert candidate["failed_support_scores"]["max"] == 0
    candidate["self_match"]["path"] = "PRIVATE"
    candidate["self_match"]["components"][0]["OCR"] = "PRIVATE"
    stats["candidate_support"] = [
        {**copy.deepcopy(candidate), "sample_index": i} for i in range(64)
    ]
    raw = {
        "schema_version": 1,
        "automatic_identity_generation": {"references": {"spectator_panel": stats}},
    }
    before = copy.deepcopy(raw)
    shared = sanitize_calibration(raw)
    gen = shared["automatic_identity_generation"]["references"]["spectator_panel"][
        "spectator_generation"
    ]
    assert gen["matcher"] == "oriented_component_regions_v2"
    assert len(gen["candidate_support"]) == 6
    assert gen["omitted_candidate_support_count"] == 58
    assert gen["self_match_summary"]["passed_count"] == 64
    assert gen["self_match_summary"]["min"] == 1
    assert gen["candidate_support"][0]["self_match"] == {
        k: v for k, v in candidate["self_match"].items() if k != "path"
    } | {
        "components": [
            {k: v for k, v in c.items() if k != "OCR"}
            for c in candidate["self_match"]["components"]
        ]
    }
    assert "PRIVATE" not in json.dumps(shared)
    assert len(json.dumps(shared, indent=2).encode()) < 128 * 1024
    inputs = _inputs(tmp_path)
    inputs["raw"]["hud_calibration_diagnostics"] = raw
    export_report(**inputs)
    for name in ("summary.json", "hud_calibration.json"):
        output = tmp_path / name
        assert output.stat().st_size <= MAX_REPORT_BYTES
        assert "PRIVATE" not in output.read_text()
    assert raw == before


def test_opposing_small_component_shifts_do_not_have_a_common_transform(panel_images):
    image = panel(panel_images)
    reference = panel_components(image)
    result = np.full_like(image, 60)
    for start, end, dy in ((0, 20, -2), (25, 90, 2)):
        region = image[start:end].copy()
        result[start:end] = cv2.warpAffine(
            region, np.float32([[1, 0, 0], [0, 1, dy]]), (160, end - start), borderValue=60
        )
    match = component_match_diagnostics(result, reference)
    assert match["passed"] is False
    assert detect_panel(result, reference)["panel_present"] is None


@pytest.mark.parametrize("seed", range(5))
def test_dense_texture_around_incomplete_panel_is_not_positive(panel_images, seed):
    image = panel(panel_images)
    reference = panel_components(image)
    image[20:, 50:] = np.random.default_rng(seed).integers(0, 256, (106, 110), np.uint8)
    result = detect_panel(image, reference)
    assert result["checked"] is False
    assert result["panel_present"] is None


def _write_png(path, image):
>>>>>>> 4a5f013ee504d22dea6dac02ccf62b9b7d280de5
    ok, encoded = cv2.imencode(".png", image)
    assert ok
    path.write_bytes(encoded.tobytes())


<<<<<<< HEAD
def _v2_profile(tmp_path: Path, labels: np.ndarray, reference: dict[str, np.ndarray]) -> Path:
    _encode_png(tmp_path / "components.png", labels)
    _encode_png(tmp_path / "support.png", reference["support"])
    _encode_png(tmp_path / "evidence.png", reference["evidence"])
    profile_path = tmp_path / "profile.json"
    profile_path.write_text(
        json.dumps(
            {
                "schema_version": "1.0",
                "spectator_panel_detector": {
                    "version": 2,
                    "template": "components.png",
                    "support": "support.png",
                    "evidence": "evidence.png",
                },
            }
        ),
        encoding="utf-8",
    )
    return profile_path


def test_frozen_reference_is_exclusive_and_self_consistent_with_nearby_edges() -> None:
    gray, labels = _fixture_scene()
    reference = freeze_panel_reference(gray, labels)

    assert set(reference) == {"support", "evidence"}
    assert validate_panel_reference(labels, reference)
    assert set(np.unique(reference["support"])).issubset({0, 1, 2, 3})
    assert np.all(reference["evidence"][reference["support"] == 0] == 0)
    for component in (1, 2, 3):
        assert np.count_nonzero(reference["support"] == component) > 0
        assert np.count_nonzero(
            (reference["support"] == component) & (reference["evidence"] > 0)
        ) >= 12

    detail: dict[str, object] = {}
    scores = local_component_scores(gray, labels, reference, detail)
    assert scores == pytest.approx([1.0, 1.0, 1.0])
    assert detail["best_shared_offset"] == [0, 0]
    assert detail["passed"] is True


def test_v2_allows_one_shared_translation_of_one_or_two_pixels() -> None:
    gray, labels = _fixture_scene()
    reference = freeze_panel_reference(gray, labels)

    for dx, dy in ((1, 0), (-1, 1), (2, 0), (0, -2)):
        scores = local_component_scores(_shift(gray, dx, dy), labels, reference)
        assert min(scores) >= 0.90, (dx, dy, scores)


def test_v2_rejects_inverted_polarity_and_contradictory_edges_inside_support() -> None:
    gray, labels = _fixture_scene()
    reference = freeze_panel_reference(gray, labels)

    inverted = 255 - gray
    assert min(local_component_scores(inverted, labels, reference)) < 0.90

    contradictory = gray.copy()
    mask = reference["support"] == 2
    contradictory[mask] = 255 - contradictory[mask]
    scores = local_component_scores(contradictory, labels, reference)
    assert scores[1] < 0.90


def test_edges_far_outside_frozen_support_do_not_reduce_precision() -> None:
    gray, labels = _fixture_scene()
    reference = freeze_panel_reference(gray, labels)
    with_outside_edges = gray.copy()
    cv2.rectangle(with_outside_edges, (3, 91), (46, 119), 240, 1)
    assert not np.any(reference["support"][88:123, 0:52])

    baseline = local_component_scores(gray, labels, reference)
    augmented = local_component_scores(with_outside_edges, labels, reference)
    assert augmented == pytest.approx(baseline)


def test_component_cannot_move_independently_beyond_shared_offset_contract() -> None:
    gray, labels = _fixture_scene()
    reference = freeze_panel_reference(gray, labels)
    moved = gray.copy()
    component_pixels = np.zeros_like(gray)
    component_pixels[20:69, 72:111] = gray[20:69, 72:111]
    moved[20:69, 72:111] = 36
    moved[30:79, 92:131] = component_pixels[20:69, 72:111]

    scores = local_component_scores(moved, labels, reference)
    assert scores[1] < 0.90


def test_blank_partial_and_noisy_crops_remain_unknown() -> None:
    gray, labels = _fixture_scene()
    reference = freeze_panel_reference(gray, labels)

    blank = detect_panel(np.zeros_like(gray), labels, reference)
    assert blank["checked"] is False
    assert blank["panel_present"] is None

    partial = np.full_like(gray, 36)
    cv2.line(partial, (12, 22), (61, 22), 220, 2)
    result = detect_panel(partial, labels, reference)
    assert result["panel_present"] is None
    assert result["reason"] in {"panel_structure_ambiguous", "panel_structure_mismatch"}

    noise = np.random.default_rng(7).integers(20, 230, gray.shape, dtype=np.uint8)
    result = detect_panel(noise, labels, reference)
    assert result["panel_present"] is None


def test_reference_validation_fails_closed_for_missing_or_corrupt_arrays() -> None:
    gray, labels = _fixture_scene()
    reference = freeze_panel_reference(gray, labels)

    assert not validate_panel_reference(labels, {"support": reference["support"]})
    corrupt = {key: value.copy() for key, value in reference.items()}
    corrupt["evidence"][corrupt["support"] == 0] = 8
    assert not validate_panel_reference(labels, corrupt)
    corrupt = {key: value.copy() for key, value in reference.items()}
    corrupt["support"][0, 0] = 4
    assert not validate_panel_reference(labels, corrupt)


def test_v2_profile_load_fails_closed_and_fingerprint_covers_support_and_evidence(
    tmp_path: Path,
) -> None:
    gray, labels = _fixture_scene()
    reference = freeze_panel_reference(gray, labels)
    profile_path = _v2_profile(tmp_path, labels, reference)
    profile = HudTemplateProfile.load(profile_path)
    assert profile._panel_reference is not None
    baseline = profile.fingerprint(profile_path)

    _encode_png(tmp_path / "support.png", np.zeros_like(labels))
    assert HudTemplateProfile.load(profile_path)._panel_reference is None
    assert HudTemplateProfile.load(profile_path).reader_diagnostics
    assert HudTemplateProfile.load(profile_path).fingerprint(profile_path) != baseline

    _encode_png(tmp_path / "support.png", reference["support"])
    _encode_png(tmp_path / "evidence.png", np.zeros_like(labels))
    invalid_evidence = HudTemplateProfile.load(profile_path)
    assert invalid_evidence._panel_reference is None
    assert invalid_evidence.reader_diagnostics
    assert invalid_evidence.fingerprint(profile_path) != baseline


def test_reference_generation_keeps_even_training_and_odd_holdout_independent(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    gray, labels = _fixture_scene()
    reference_out: dict[str, np.ndarray] = {}

    def fixed_components(
        frame: np.ndarray, diagnostics: dict[str, Any] | None = None
    ) -> np.ndarray:
        if diagnostics is not None:
            diagnostics.update(
                reason="candidate",
                final_rejections={
                    "text_alignment_insufficient": 0,
                    "boundary_span_insufficient": 0,
                    "relative_position_mismatch": 0,
                    "component_pixels_insufficient": 0,
                },
            )
        return labels

    monkeypatch.setattr("valorant_ai_coach.hud.spectator.panel_components", fixed_components)
    stats: dict[str, Any] = {}
    crops = [gray.copy() for _ in range(8)]
    result = generate_panel_reference(crops, stats, reference_out)

    assert result is not None
    assert stats["training_count"] == 4
    assert stats["holdout_count"] == 4
    assert stats["training_accept_count"] >= 3
    assert stats["holdout_accept_count"] == 4
    assert all(item["sample_index"] % 2 == 0 for item in stats["candidate_support"])
    assert all(item["sample_index"] % 2 == 1 for item in stats["holdout_matches"])
    assert validate_panel_reference(labels, reference_out)


def test_generation_requires_three_training_and_three_holdout_matches(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    gray, labels = _fixture_scene()

    def fixed_components(
        frame: np.ndarray, diagnostics: dict[str, Any] | None = None
    ) -> np.ndarray:
        if diagnostics is not None:
            diagnostics.update(
                reason="candidate",
                final_rejections={
                    "text_alignment_insufficient": 0,
                    "boundary_span_insufficient": 0,
                    "relative_position_mismatch": 0,
                    "component_pixels_insufficient": 0,
                },
            )
        return labels

    monkeypatch.setattr("valorant_ai_coach.hud.spectator.panel_components", fixed_components)
    stats: dict[str, Any] = {}
    assert generate_panel_reference([gray.copy() for _ in range(4)], stats) is None
    assert stats["training_count"] == 2
    assert stats["candidate_count"] == 2
    assert stats["support_rejected"] == 2

    crops = [gray.copy() for _ in range(8)]
    crops[1] = 255 - crops[1]
    crops[3] = 255 - crops[3]
    crops[5] = 255 - crops[5]
    holdout_stats: dict[str, Any] = {}
    assert generate_panel_reference(crops, holdout_stats) is None
    assert holdout_stats["training_accept_count"] >= 3
    assert holdout_stats["holdout_accept_count"] < 3
    assert holdout_stats["holdout_rejected"] == 1



def test_invalid_reference_cannot_prove_absence() -> None:
    gray, labels = _fixture_scene()
    reference = freeze_panel_reference(gray, labels)
    del reference["evidence"]
    result = detect_panel(gray, labels, reference)
    assert result["checked"] is False
    assert result["panel_present"] is None
    assert result["reason"] == "reference_invalid"


def test_absence_retains_broader_structural_candidate_veto(monkeypatch) -> None:
    gray, labels = _fixture_scene()
    reference = freeze_panel_reference(gray, labels)
    scene = np.tile(np.linspace(25, 120, 176, dtype=np.uint8), (128, 1))
    cv2.circle(scene, (30, 107), 8, 240, 2)
    called = []

    def ambiguous_candidate(frame, diagnostics=None, *, directed_portrait=True):
        called.append(directed_portrait)
        return labels

    monkeypatch.setattr("valorant_ai_coach.hud.spectator.panel_components", ambiguous_candidate)
    result = detect_panel(scene, labels, reference)
    assert called == [False]
=======
def _write_remote_v2_profile(tmp_path, labels):
    profile_path = tmp_path / "profile.json"
    config = {
        "version": 2,
        "template": "template.png",
        "support_regions": "support_regions.png",
        "orientation": "orientation.png",
    }
    raw = {"schema_version": "1.0", "spectator_panel_detector": config}
    profile_path.write_text(json.dumps(raw), encoding="utf-8")
    _write_png(tmp_path / "template.png", labels)
    _write_png(tmp_path / "support_regions.png", labels.regions)
    _write_png(tmp_path / "orientation.png", labels.orientation)
    return profile_path, raw, config


def test_v2_assets_fail_closed_and_all_are_fingerprinted(tmp_path, panel_images):
    image = panel(panel_images)
    reference = panel_components(image)
    assert isinstance(reference, PanelReference)
    profile_path, raw, config = _write_remote_v2_profile(tmp_path, reference)
    layout_path = tmp_path / "layout.json"
    layout_path.write_text("{}", encoding="utf-8")
    profile = HudTemplateProfile.load(profile_path)
    assert isinstance(profile._panel_components, PanelReference)
    baseline = profile.fingerprint(layout_path)

    for key in ("template", "support_regions", "orientation"):
        asset_path = tmp_path / config[key]
        original = asset_path.read_bytes()
        pixels = cv2.imdecode(np.frombuffer(original, np.uint8), cv2.IMREAD_GRAYSCALE)
        pixels[0, 0] = (int(pixels[0, 0]) + 1) % 256
        _write_png(asset_path, pixels)
        assert profile.fingerprint(layout_path) != baseline, key
        asset_path.write_bytes(original)

    for key in ("support_regions", "orientation"):
        config[key] = f"missing_{key}.png"
        profile_path.write_text(json.dumps(raw), encoding="utf-8")
        invalid = HudTemplateProfile.load(profile_path)
        assert invalid._panel_components is None
        assert invalid.reader_diagnostics
        assert detect_panel(image, invalid._panel_components)["panel_present"] is None
        config[key] = f"{key}.png"

    profile_path.write_text(json.dumps(raw), encoding="utf-8")
    _write_png(tmp_path / "orientation.png", np.zeros((2, 2), dtype=np.uint8))
    corrupt = HudTemplateProfile.load(profile_path)
    assert corrupt._panel_components is None
    assert corrupt.reader_diagnostics
    assert detect_panel(image, corrupt._panel_components)["panel_present"] is None


def test_structural_candidate_veto_prevents_clear_absence(monkeypatch, panel_images):
    image = panel(panel_images)
    reference = panel_components(image)
    scene = np.tile(np.linspace(25, 120, 160, dtype=np.uint8), (126, 1))
    cv2.circle(scene, (30, 107), 8, 240, 2)
    calls = []

    def candidate(frame, diagnostics=None, *, conservative_veto=False):
        calls.append(frame.shape)
        return reference

    monkeypatch.setattr("valorant_ai_coach.hud.spectator.panel_components", candidate)
    result = detect_panel(scene, reference)
    assert calls == [scene.shape]
>>>>>>> 4a5f013ee504d22dea6dac02ccf62b9b7d280de5
    assert result["checked"] is False
    assert result["panel_present"] is None
    assert result["reason"] == "panel_structure_mismatch"


<<<<<<< HEAD
def test_shared_self_match_diagnostics_remain_allowlisted() -> None:
    from scripts.e2e.calibration_report import sanitize_calibration

    gray, labels = _fixture_scene()
    reference = freeze_panel_reference(gray, labels)
    detail = {}
    local_component_scores(gray, labels, reference, detail)
    detail["private"] = "PRIVATE"
    report = sanitize_calibration({
        "schema_version": 1,
        "automatic_identity_generation": {"references": {"spectator_panel": {
            "matcher": "signed_support_v2",
            "candidate_support": [{
                "sample_index": 0, "training_support": 1, "minimum_required": 3,
                "self_match": detail, "legacy_self_match_scores": [0.8, 0.8, 0.8],
                "training_matches": [{"private": "PRIVATE"}],
            }],
        }}},
    })
    generation = report["automatic_identity_generation"]["references"]["spectator_panel"][
        "spectator_generation"
    ]
    assert generation["matcher"] == "signed_support_v2"
    assert generation["candidate_support"][0]["self_match"]["passed"] is True
    assert "PRIVATE" not in json.dumps(report)
    assert "training_matches" not in json.dumps(report)
    assert len(json.dumps(report).encode()) < 128 * 1024
=======
def test_generation_requires_three_training_and_holdout_and_eighty_percent(
    panel_images,
):
    positive = panel(panel_images)
    blank = np.full_like(positive, 60)

    two_training = {}
    assert generate_panel_reference([positive.copy() for _ in range(4)], two_training) is None
    assert two_training["training_count"] == 2
    assert two_training["candidate_count"] >= 1
    assert two_training["support_rejected"] >= 1

    three_training_and_holdout = {}
    accepted = generate_panel_reference(
        [positive.copy() for _ in range(6)], three_training_and_holdout
    )
    assert accepted is not None
    assert three_training_and_holdout["training_accept_count"] >= 3
    assert three_training_and_holdout["holdout_accept_count"] == 3

    below_three_holdout = [positive.copy() for _ in range(6)]
    below_three_holdout[5] = blank
    stats = {}
    assert generate_panel_reference(below_three_holdout, stats) is None
    assert stats["holdout_accept_count"] == 2
    assert stats["holdout_rejected"] == 1

    exactly_eighty_percent = [positive.copy() for _ in range(10)]
    exactly_eighty_percent[9] = blank
    stats = {}
    assert generate_panel_reference(exactly_eighty_percent, stats) is not None
    assert stats["training_accept_count"] >= 5
    assert stats["holdout_accept_count"] == 4

    below_eighty_percent = [positive.copy() for _ in range(10)]
    below_eighty_percent[7] = blank
    below_eighty_percent[9] = blank
    stats = {}
    assert generate_panel_reference(below_eighty_percent, stats) is None
    assert stats["holdout_accept_count"] == 3
    assert stats["holdout_rejected"] == 1


def test_contrast_polarity_inversion_remains_unknown(panel_images):
    image = panel(panel_images)
    reference = panel_components(image)
    inverted = 255 - image

    result = detect_panel(inverted, reference)
    assert result["checked"] is False
    assert result["panel_present"] is None


def test_absence_veto_uses_conservative_mode_when_strict_generation_rejects(
    monkeypatch, panel_images
):
    image = panel(panel_images)
    reference = panel_components(image)
    scene = np.tile(np.linspace(25, 120, 160, dtype=np.uint8), (126, 1))
    cv2.circle(scene, (30, 107), 8, 240, 2)
    calls = []

    def candidate(frame, diagnostics=None, *, conservative_veto=False):
        calls.append(conservative_veto)
        return reference if conservative_veto else None

    monkeypatch.setattr("valorant_ai_coach.hud.spectator.panel_components", candidate)
    result = detect_panel(scene, reference)

    assert calls == [True]
    assert result["checked"] is False
    assert result["panel_present"] is None
    assert result["reason"] == "panel_structure_mismatch"
>>>>>>> 4a5f013ee504d22dea6dac02ccf62b9b7d280de5
