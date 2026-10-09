from __future__ import annotations

import numpy as np

from scripts.diagnostics.scene_constellation import coherent_translation, measure_constellation


def groups(alternatives=None):
    result = []
    for i, (x, y) in enumerate([(50, 60), (80, 180), (480, 150)]):
        positions = [[x + 10, y + 10]]
        if alternatives is not None:
            dx, dy = alternatives[i]
            positions.append([x + dx, y + dy])
        result.append(
            {"region": i, "reference_xy": [x, y], "candidates": [(0.99, pos) for pos in positions]}
        )
    return result


def test_joint_structure_resolves_individual_ambiguity():
    model, selected, reason = coherent_translation(groups([(40, 15), (80, 10), (20, 25)]))
    assert model == [10, 10]
    assert len(selected) == 3
    assert reason == "descriptive_constellation"


def test_second_complete_constellation_is_not_discarded():
    model, selected, reason = coherent_translation(groups([(40, 10)] * 3))
    assert model is None and not selected
    assert reason == "competing_distributed_constellations"


def test_fragmented_motion_does_not_form_constellation():
    values = groups()
    values[1]["candidates"] = [(0.99, [180, 180])]
    assert coherent_translation(values)[0] is None


def test_one_region_cannot_prove_scene():
    values = groups()
    for g in values:
        g["region"] = 0
    assert coherent_translation(values)[0] is None


def test_one_source_grid_cell_cannot_prove_scene():
    values = groups()
    for i, g in enumerate(values):
        g["reference_xy"] = [50 + i * 10, 50]
        g["candidates"] = [(0.99, [60 + i * 10, 60])]
    assert coherent_translation(values)[0] is None


def test_insufficient_feature_consensus_abstains():
    values = groups()
    values.append({"region": 3, "reference_xy": [500, 200], "candidates": [(0.99, [600, 200])]})
    assert coherent_translation(values)[0] is None


def test_image_correspondence_is_never_authorization_and_excluded_pixels_invariant():
    image = np.random.default_rng(62).integers(0, 256, (360, 640), dtype=np.uint8)
    boxes = ((20, 50, 80, 110), (20, 160, 80, 220), (480, 160, 540, 220))
    current = np.roll(image, 4, axis=0)
    before = measure_constellation(image, current, boxes)
    assert before[0]["runtime_proof_authorized"] is False
    assert before[0]["accepted_reference_tracks"] > 3
    mask = np.ones(image.shape, bool)
    for x1, y1, x2, y2 in boxes:
        mask[y1:y2, x1:x2] = False
    image[mask] = 0
    current[mask] = 255
    assert measure_constellation(image, current, boxes) == before


def test_empty_and_textureless_inputs_abstain():
    assert coherent_translation([])[0] is None
    image = np.zeros((360, 640), np.uint8)
    metrics, tracks = measure_constellation(image, image, [(20, 150, 80, 210)])
    assert tracks == []
    assert metrics["accepted_reference_tracks"] == 0
    assert metrics["runtime_proof_authorized"] is False


def test_candidate_budget_does_not_hide_remaining_peaks(monkeypatch):
    import cv2

    from scripts.diagnostics.scene_constellation import patch_peaks

    monkeypatch.setattr(cv2, "matchTemplate", lambda *a, **k: np.full((100, 100), 0.95, np.float32))
    image = np.zeros((360, 640), np.uint8)
    assert patch_peaks(np.zeros((15, 15), np.uint8), image, [(20, 150, 160, 290)]) is None
