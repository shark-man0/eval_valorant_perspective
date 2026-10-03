from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import cv2
import numpy as np
import pytest

from valorant_ai_coach.hud.spectator import (
    detect_panel,
    freeze_panel_reference,
    generate_panel_reference,
    local_component_scores,
    validate_panel_reference,
)
from valorant_ai_coach.hud.templates import HudTemplateProfile


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
    ok, encoded = cv2.imencode(".png", image)
    assert ok
    path.write_bytes(encoded.tobytes())


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
    assert result["checked"] is False
    assert result["panel_present"] is None
    assert result["reason"] == "panel_structure_mismatch"


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
