import json

import cv2
import numpy as np
import pytest

from tests.unit.test_shared_game_timeline import obs, replay
from valorant_ai_coach.temporal import camera_panel as cp

RNG = np.random.default_rng(7)
# Coarse blocks, like text strokes, survive downscaling.
LABEL = cv2.resize(RNG.integers(0, 256, (7, 40)).astype(np.uint8),
                   (cp.LABEL_BOX[2], cp.LABEL_BOX[3]), interpolation=cv2.INTER_NEAREST)
OWN = [RNG.integers(0, 256, (cp.BAR_ROWS[1], 70)).astype(np.uint8) for _ in range(4)]
OTHER = [RNG.integers(0, 256, (cp.BAR_ROWS[1], 70)).astype(np.uint8) for _ in range(4)]


@pytest.fixture
def reference(tmp_path):
    path = tmp_path / "label.png"
    cv2.imwrite(str(path), LABEL)
    return cp.LabelReference.load(path)


def frame(label=False, icons=None, seed=0):
    image = np.random.default_rng(seed).integers(0, 256, (1080, 1920, 3)).astype(np.uint8)
    if label:
        x, y, w, h = cp.LABEL_BOX
        image[y : y + h, x : x + w] = LABEL[..., None]
    if icons is not None:
        x, y = cp.BAR_BOX[:2]
        for (a, _), icon in zip(cp.BAR_SLOTS, icons, strict=True):
            image[y : y + icon.shape[0], x + a : x + a + 70] = icon[..., None]
    return image


def sample(i):
    return obs(i * 10)["sample"]


def test_label_states_and_unsupported_geometry(reference):
    assert cp.measure_label(frame(label=True), reference)["state"] == "PRESENT"
    assert cp.measure_label(frame(), reference)["state"] == "ABSENT"
    half = cv2.resize(frame(label=True), (960, 540), interpolation=cv2.INTER_AREA)
    assert cp.measure_label(half, reference)["state"] == "PRESENT"
    narrow = np.zeros((1080, 1440, 3), np.uint8)
    assert cp.measure_label(narrow, reference) == {
        "checked": False, "score": None, "state": "UNCHECKED",
        "reason": "unsupported_aspect_ratio",
    }


def test_reference_geometry_is_required(tmp_path):
    path = tmp_path / "bad.png"
    cv2.imwrite(str(path), np.zeros((10, 10), np.uint8))
    with pytest.raises(ValueError):
        cp.LabelReference.load(path)


def test_rows_use_label_and_learned_own_ability_bar(reference):
    images = [frame(icons=OWN, seed=i) for i in range(40)]
    images += [frame(label=True, icons=OTHER, seed=100 + i) for i in range(10)]
    images += [frame(icons=OTHER, seed=200)]  # no label, someone else's HUD
    measured = [(sample(i), cp.measure_frame(img, reference)) for i, img in enumerate(images)]
    result = cp.camera_rows(measured, reference)
    signals = {r["sample"]["native_pts_tick"]: r["signals"] for r in result["observations"]}
    assert result["own_ability_bar"]["available"] is True
    assert result["counts"] == {"spectator_label": 10, "own_ability_bar": 40, "undecided": 1}
    assert signals[0] == ["owner_hud"] and signals[400] == ["spectator"]
    assert 500 not in signals
    assert all(r["context"]["stream_kind"] == "camera_panel" for r in result["observations"])
    assert result["formal_outputs"] == 0 and result["qualified"] is False
    json.dumps(result)


def test_own_bar_is_rejected_when_spectated_hud_matches(reference):
    images = [frame(icons=OWN, seed=i) for i in range(40)]
    images += [frame(label=True, icons=OWN, seed=100)]
    measured = [(sample(i), cp.measure_frame(img, reference)) for i, img in enumerate(images)]
    result = cp.camera_rows(measured, reference)
    assert result["own_ability_bar"] == {
        "available": False, "reason": "prototype_matches_spectated_hud", "spectator_matches": 1,
    }
    assert [r["signals"] for r in result["observations"]] == [["spectator"]]


def test_own_bar_needs_a_dominant_cluster(reference):
    images = [frame(icons=[RNG.integers(0, 256, (56, 70)).astype(np.uint8) for _ in range(4)],
                    seed=i) for i in range(40)]
    measured = [(sample(i), cp.measure_frame(img, reference)) for i, img in enumerate(images)]
    result = cp.camera_rows(measured, reference)
    assert result["own_ability_bar"]["reason"] == "no_dominant_ability_cluster"
    assert result["observations"] == []


WEAK = {"unqualified_view_model": True}


def test_measured_view_outranks_learned_view_only_when_enabled():
    rows = [obs(0, ["owner_hud"]), obs(0, ["spectator"], context=WEAK)]
    default = replay(rows)["frames"][0]
    assert default["camera"]["value"] == "UNKNOWN"
    precedence = replay(rows, measured_view_precedence=True)
    assert precedence["frames"][0]["camera"]["value"] == "SELF"
    assert precedence["configuration"]["measured_view_precedence"]
    weak_only = replay([obs(0, ["spectator"], context=WEAK)], measured_view_precedence=True)
    assert weak_only["frames"][0]["camera"]["hypotheses"] == ["SPECTATOR", "UNKNOWN"]
    with pytest.raises(ValueError):
        replay(rows, measured_view_precedence=1)


def test_own_hud_after_measured_result_resolves_the_return():
    rows = [obs(0, ["owner_hud", "buy"]), obs(10, ["owner_hud", "active"]),
            obs(20, ["death"]), obs(30, ["spectator"]), obs(40, ["spectator", "result"]),
            obs(50, ["owner_hud"]), obs(60), obs(70, ["owner_hud"])]
    default = replay(rows)["frames"]
    assert default[-1]["life"]["reason"] == "return_edge_unobserved"
    result = replay(rows, measured_view_precedence=True)
    frames = result["frames"]
    assert [f["life"]["value"] for f in frames[5:]] == ["ALIVE"] * 3
    assert frames[5]["life"]["reason"] == "measured_own_hud_after_round_change"
    assert frames[6]["life"]["reason"] == "bracketed_by_measured_own_hud_after_round_change"
    assert {h["basis"] for h in result["measured_view_return_history"]} == {
        "measured_result_before_own_hud"
    }


def test_own_hud_without_round_change_stays_unresolved():
    rows = [obs(0, ["owner_hud", "buy"]), obs(10, ["owner_hud", "active"]),
            obs(20, ["death"]), obs(30, ["owner_hud"]), obs(40, ["owner_hud"])]
    result = replay(rows, measured_view_precedence=True)
    assert result["frames"][-1]["life"]["value"] == "UNKNOWN"
    assert result["measured_view_return_history"] == []


def test_own_hud_until_next_round_buy_resolves_the_return():
    rows = [obs(0, ["owner_hud", "buy"]), obs(10, ["owner_hud", "active"]),
            obs(20, ["death"]), obs(30, ["owner_hud"]), obs(40, ["owner_hud"]),
            obs(50, ["owner_hud", "buy"])]
    result = replay(rows, measured_view_precedence=True)
    assert [f["life"]["value"] for f in result["frames"][3:]] == ["ALIVE"] * 3
    assert {h["basis"] for h in result["measured_view_return_history"]} == {
        "measured_buy_after_own_hud"
    }
