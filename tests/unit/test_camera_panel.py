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


def frame(label=False, icons=None, seed=0, health=True):
    image = np.random.default_rng(seed).integers(0, 256, (1080, 1920, 3)).astype(np.uint8)
    if health:
        x, y = cp.HEALTH_BOX[:2]
        for offset in (10, 40, 70):
            image[y + 12 : y + 45, x + offset : x + offset + 20] = 255
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
    assert result["counts"] == {"spectator_label": 10, "remote_control": 0, "astral_view": 0,
                                "own_ability_bar": 40, "undecided": 1}
    assert signals[0] == ["owner_hud"] and signals[400] == ["spectator"]
    assert 500 not in signals
    assert all(r["context"]["stream_kind"] == "camera_panel" for r in result["observations"])
    assert result["formal_outputs"] == 0 and result["qualified"] is False
    json.dumps(result)


def test_own_bar_without_health_digits_gives_no_row(reference):
    # e.g. the view that follows the planted spike after the recorder died
    images = [frame(icons=OWN, seed=i) for i in range(40)]
    images += [frame(icons=OWN, seed=99, health=False)]
    measured = [(sample(i), cp.measure_frame(img, reference)) for i, img in enumerate(images)]
    assert cp.health_digits(images[-1]) == 0 and cp.health_digits(images[0]) == 3
    result = cp.camera_rows(measured, reference)
    assert 400 not in {r["sample"]["native_pts_tick"] for r in result["observations"]}
    assert result["counts"]["own_ability_bar"] == 40


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


def test_own_hud_after_measured_result_stays_unresolved():
    # A dead recorder can see its own ability bar on the spike camera after the
    # Round ends; only the next Round's purchase phase respawns it.
    rows = [obs(0, ["owner_hud", "buy"]), obs(10, ["owner_hud", "active"]),
            obs(20, ["death"]), obs(30, ["spectator"]), obs(40, ["spectator", "result"]),
            obs(50, ["owner_hud"]), obs(60), obs(70, ["owner_hud"])]
    result = replay(rows, measured_view_precedence=True)
    assert [result["frames"][i]["life"]["value"] for i in (5, 7)] == ["UNKNOWN"] * 2
    assert result["measured_view_return_history"] == []


def test_result_inside_the_own_hud_run_blocks_the_next_round_buy():
    rows = [obs(0, ["owner_hud", "buy"]), obs(10, ["owner_hud", "active"]),
            obs(20, ["death"]), obs(30, ["owner_hud"]), obs(40, ["owner_hud", "result"]),
            obs(50, ["owner_hud", "buy"])]
    result = replay(rows, measured_view_precedence=True)
    # The next Round's BUY does not reach back across the result; the own HUD
    # with health inside the still running Round is alive on its own.
    assert result["frames"][3]["life"]["value"] == "ALIVE"
    assert result["frames"][3]["life"]["reason"] == "measured_own_hud_with_health_during_round"


def test_own_hud_during_a_running_round_is_alive_without_a_round_change():
    rows = [obs(0, ["owner_hud", "buy"]), obs(10, ["owner_hud", "active"]),
            obs(20, ["death"]), obs(30, ["owner_hud"]), obs(40, ["owner_hud"])]
    result = replay(rows, measured_view_precedence=True)
    frames = result["frames"]
    assert frames[3]["round"]["value"] == "ACTIVE"
    assert frames[3]["life"]["value"] == "ALIVE"
    history = result["measured_view_return_history"]
    assert [h["basis"] for h in history] == ["measured_own_hud_with_health_during_round"]
    assert history[0]["confirmation_sample"] is None
    # Outside a Round shown to be running (no later measured ACTIVE/BUY row of the
    # same Round), the own HUD stays unresolved.
    assert frames[4]["round"]["value"] == "UNKNOWN"
    assert frames[4]["life"]["value"] == "UNKNOWN"


def test_own_hud_before_a_result_without_a_running_round_stays_unresolved():
    rows = [obs(0, ["owner_hud", "buy"]), obs(10, ["owner_hud", "active"]), obs(20, ["death"])]
    rows += [obs(s) for s in range(30, 100, 10)] + [obs(100, ["owner_hud"]), obs(110, ["result"])]
    result = replay(rows, measured_view_precedence=True)
    assert result["frames"][-2]["round"]["value"] == "UNKNOWN"
    assert result["frames"][-2]["life"]["value"] == "UNKNOWN"


def test_own_hud_until_next_round_buy_resolves_the_return():
    rows = [obs(0, ["owner_hud", "buy"]), obs(10, ["owner_hud", "active"]),
            obs(20, ["death"]), obs(30, ["owner_hud"]), obs(40),
            obs(50, ["owner_hud", "buy"])]
    result = replay(rows, measured_view_precedence=True)
    assert [f["life"]["value"] for f in result["frames"][3:]] == ["ALIVE"] * 3
    assert result["frames"][4]["life"]["reason"] == (
        "bracketed_by_measured_own_hud_after_round_change"
    )


def test_measured_spectator_view_means_the_recorder_is_not_alive():
    rows = [obs(0, ["owner_hud", "active"]), obs(10, ["spectator"]),
            obs(20, ["spectator", "result"])]
    frames = replay(rows, measured_view_precedence=True)["frames"]
    assert [f["life"]["value"] for f in frames] == ["ALIVE", "DEAD", "DEAD"]
    assert {f["life"]["reason"] for f in frames[1:]} == {"measured_spectator_view"}
    # Without the option, or from a learned view, it stays a competing hypothesis.
    assert replay(rows)["frames"][1]["life"]["value"] == "UNKNOWN"
    learned = [obs(0, ["owner_hud", "active"]), obs(10, ["spectator"], context=WEAK)]
    assert replay(learned, measured_view_precedence=True)["frames"][1]["life"]["value"] == "UNKNOWN"
    # A spectator view shown with the purchase phase is not used.
    buy = [obs(0, ["owner_hud", "active"]), obs(10, ["spectator", "buy"])]
    assert replay(buy, measured_view_precedence=True)["frames"][1]["life"]["value"] != "DEAD"


def test_carried_alive_before_a_measured_spectator_view_is_withdrawn():
    rows = [obs(0, ["owner_hud", "active"]), obs(10, ["owner_hud"]), obs(20, ["report"]),
            obs(30, ["spectator"])]
    result = replay(rows, measured_view_precedence=True)
    frames = result["frames"]
    assert [f["life"]["value"] for f in frames] == ["ALIVE", "ALIVE", "UNKNOWN", "DEAD"]
    assert frames[2]["life"]["reason"] == "carried_alive_before_measured_spectator_view"
    assert frames[2]["camera"]["value"] == "SELF"
    assert [h["basis"] for h in result["measured_view_return_history"]] == [
        "carried_alive_before_measured_spectator_view"]


def hsv_frame(hsv_fill, stripes=None, health=True):
    """A 1080p frame of one HSV colour, optionally with bright HSV stripes."""
    hsv = np.zeros((1080, 1920, 3), np.uint8)
    hsv[:] = hsv_fill
    if stripes is not None:
        for x in range(0, 1920, 160):
            hsv[:, x : x + 50] = stripes
    image = cv2.cvtColor(hsv, cv2.COLOR_HSV2BGR)
    if health:
        x, y = cp.HEALTH_BOX[:2]
        for offset in (10, 40, 70):
            image[y + 12 : y + 45, x + offset : x + offset + 20] = 255
    return image


def test_astral_form_is_a_remote_view_and_purple_smoke_or_a_pink_wall_is_not(reference):
    astral = hsv_frame((145, 200, 150), stripes=(155, 180, 250))
    smoke = hsv_frame((145, 200, 120))
    wall = hsv_frame((155, 180, 245))
    measured = cp.measure_astral(astral)
    assert measured["present"] is True
    assert measured["bright_magenta_share"] >= cp.ASTRAL_BRIGHT
    assert cp.measure_astral(smoke)["present"] is False  # no bright floor plan
    assert cp.measure_astral(wall)["present"] is False  # bright, but no spread
    assert cp.measure_astral(np.zeros((1080, 1440, 3), np.uint8))["checked"] is False
    images = [frame(icons=OWN, seed=i) for i in range(40)]
    images += [astral, astral, hsv_frame((145, 200, 150), stripes=(155, 180, 250), health=False)]
    images += [frame(icons=OWN, seed=300 + i) for i in range(5)] + [astral]

    def tick_sample(i):
        return obs(i * 15360)["sample"]  # one sample per second

    rows = cp.camera_rows(
        [(tick_sample(i), cp.measure_frame(img, reference)) for i, img in enumerate(images)],
        reference,
    )
    signals = {r["sample"]["native_pts_tick"] // 15360: r["signals"] for r in rows["observations"]}
    assert signals[40] == signals[41] == ["remote"]
    assert 42 not in signals  # no living HUD: undecided
    assert 48 not in signals  # a single astral frame is not a held form: undecided
    assert rows["counts"]["astral_view"] == 2
    assert rows["bindings"]["thresholds"]["astral_purple"] == cp.ASTRAL_PURPLE
