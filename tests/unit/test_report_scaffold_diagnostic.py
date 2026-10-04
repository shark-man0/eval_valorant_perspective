"""Synthetic diagnostic contract checks, independent of recording frames."""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import cv2
import numpy as np
import pytest


def load(name):
    path = Path(__file__).resolve().parents[2] / "scripts" / f"{name}.py"
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


engine = load("report_scaffold_diagnostic")
cli = load("diagnose_report_scaffold")


def motifs(count=4):
    frames = []
    for index in range(count):
        image = np.full((500, 520), 40, np.uint8)
        cv2.line(image, (25, 25), (325, 25), 220, 1)
        cv2.line(image, (25, 25), (25, 325), 220, 1)
        cv2.line(image, (195, 470), (495, 470), 220, 1)
        cv2.line(image, (495, 170), (495, 470), 220, 1)
        cv2.putText(image, str(index * 19), (180, 230), cv2.FONT_HERSHEY_SIMPLEX, 1, 200, 2)
        frames.append(image)
    return np.stack(frames)


def test_independent_motifs_recur_on_holdout_with_changed_glyphs():
    model = engine.learn_panel_separator_model(motifs())
    assert model.sufficient
    assert len(model.groups) >= 2
    assert engine.score_holdout(model, motifs(5))["accepted"]


def test_excluded_pixels_do_not_influence_features():
    frames = motifs()
    model = engine.learn_panel_separator_model(frames)
    assert model.sufficient
    allowed = np.zeros(frames.shape[1:], bool)
    for group in model.groups:
        allowed |= engine._localized(frames[0], group)[2]
    changed = frames[0].copy()
    changed[~allowed] = np.random.default_rng(7).integers(0, 256, (~allowed).sum(), dtype=np.uint8)
    baseline = engine._full_score(frames[0], model.groups)
    assert engine._full_score(changed, model.groups) == baseline


def test_missing_support_and_observable_wrong_geometry_reject():
    frames = motifs()
    model = engine.learn_panel_separator_model(frames)
    assert model.sufficient
    removed = frames[0].copy()
    removed[engine._dilate(model.groups[0].support, 8)] = 40
    assert not engine._full_score(removed, model.groups)["accepted"]
    shifted = np.roll(frames[0], 12, axis=0)
    assert not engine._full_score(shifted, model.groups)["accepted"]


def test_parallel_world_stripes_cannot_supply_independent_panel_structure():
    image = np.full((500, 520), 40, np.uint8)
    for y in (25, 45, 170, 190, 330, 350):
        cv2.line(image, (10, y), (510, y), 220, 1)
    samples = np.repeat(image[None, :, :], 4, axis=0)
    assert not engine.learn_panel_separator_model(samples).sufficient


def test_insufficient_training_is_not_reported_as_zero_false_accepts():
    flat = np.full((3, 64, 64), 40, np.uint8)
    report = cli.diagnose({"training": flat, "holdout": flat, "negative": flat})
    assert not report["training"]["sufficient"]
    assert report["negative"]["evaluated"] is False
    assert "accepted" not in report["negative"]
    encoded = json.dumps(report)
    assert "frame_path" not in encoded and "time_sec" not in encoded


def test_geometry_and_extra_fields_reject():
    flat = np.full((3, 64, 64), 40, np.uint8)
    with pytest.raises(ValueError):
        cli.diagnose({"training": flat, "holdout": flat[:, :32], "negative": flat})
    with pytest.raises(ValueError):
        cli.diagnose({"training": flat, "holdout": flat, "negative": flat, "expected_state": flat})
