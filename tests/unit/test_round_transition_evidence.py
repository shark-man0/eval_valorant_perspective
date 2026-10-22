"""Offline association must preserve unknowns, native gaps and source bindings."""
from copy import deepcopy
from pathlib import Path

import cv2
import numpy as np
import pytest

from scripts.diagnostics.round_transition_evidence import integrate, score_readers


def read(text, confidence=.95):
    return {"value": text, "confidence": confidence}


def frame(tick, *, score=(1, 4), word=None, timer="0:06", epoch="a", geometry=True):
    return {"source_id": "dev", "source_sha256": "a" * 64, "tick": tick,
            "time_base": "1/60", "epoch": epoch, "expected_step_ticks": 1,
            "encoded_sha256": f"{tick + 1:064x}", "pixel_sha256": f"{tick + 2:064x}",
            "geometry_consistent": geometry,
            "ally_score": read(None if score is None else str(score[0])),
            "enemy_score": read(None if score is None else str(score[1])),
            "result": read(word), "timer": read(timer), "buy_phase": False}


def transition():
    return [frame(0), frame(1, score=(2, 4)),
            frame(2, score=(2, 4), word="THRIFTY"),
            frame(3, score=(2, 4)),  # reject/unknown stays unknown
            frame(4, score=(2, 4), word="THRIFTY")]


def test_native_score_result_timer_association_keeps_hole_and_no_formal_end():
    rows = transition()
    before = deepcopy(rows)
    report = integrate(rows)
    assert len(report["candidates"]) == 1
    c = report["candidates"][0]
    assert c["status"] == "DEVELOPMENT_TRANSITION_CANDIDATE"
    assert c["result_support_ticks"] == [2, 4]
    assert c["unread_result_ticks_between_support"] == [3]
    assert c["score_boundary"]["lower_tick"] == 0
    assert c["score_boundary"]["upper_tick"] == 1
    assert c["first_word_bracket"]["lower_tick"] == 1
    assert c["first_word_bracket"]["upper_tick"] == 2
    assert c["complete_display_status"] == "UNVERIFIED"
    assert c["internal_End_tick"] is None and report["formal_events"] == []
    assert rows == before


@pytest.mark.parametrize("change,reason", [
    (lambda r: r[4]["result"].update(value="LOST"), "conflicting_result_words"),
    (lambda r: r[4]["timer"].update(value="2:25"), "timer_contradiction"),
    (lambda r: r[1].update(geometry_consistent=False), "score_geometry_unknown"),
    (lambda r: r[2]["result"].update(confidence=.89), "insufficient_result_support"),
    (lambda r: [f["timer"].update(value=None) for f in r], "timer_unknown"),
    (lambda r: r[2].update(buy_phase=True), "preparation_overlaps_result"),
])
def test_evidence_contradiction_or_shortage_remains_unknown(change, reason):
    rows = transition()
    change(rows)
    c = integrate(rows)["candidates"][0]
    assert c["status"] == "UNKNOWN" and reason in c["reasons"]


def test_missing_native_frame_cannot_be_used_as_adjacent_score_boundary():
    rows = transition()
    rows[1:1] = []
    rows = [r for r in rows if r["tick"] != 1]
    report = integrate(rows)
    assert report["candidates"] == []
    assert report["source_gaps"] and report["orphan_result_groups"]


def test_cross_epoch_words_do_not_corroborate_score_change():
    rows = transition()
    for r in rows[2:]:
        r["epoch"] = "other"
    report = integrate(rows)
    assert report["candidates"][0]["status"] == "UNKNOWN"
    assert report["orphan_result_groups"]


def test_one_word_or_constant_score_is_not_a_transition():
    report = integrate([frame(0, word="WON"), frame(1, word="WON")])
    assert report["candidates"] == []
    assert report["orphan_result_groups"][0]["status"] == "UNKNOWN"


@pytest.mark.parametrize("field,value", [("tick", True), ("time_base", "1/0"),
                                        ("source_sha256", "bad"), ("epoch", ""),
                                        ("expected_step_ticks", 0)])
def test_invalid_native_binding_rejected(field, value):
    rows = transition()
    rows[0][field] = value
    with pytest.raises(ValueError):
        integrate(rows)


def test_mixed_sources_and_duplicate_pts_rejected():
    rows = transition()
    rows[-1]["source_sha256"] = "b" * 64
    with pytest.raises(ValueError):
        integrate(rows)
    rows = transition()
    with pytest.raises(ValueError):
        integrate(rows + [rows[-1]])


def test_explicit_discontinuity_cannot_be_stitched():
    rows = transition()
    rows[1]["discontinuity"] = True
    assert integrate(rows)["candidates"] == []


def test_exact_score_boundary_replay_is_deduplicated_without_joining_epochs():
    a = transition()
    b = deepcopy(a)
    for f in b:
        f["epoch"] = "b"
    report = integrate(a + b)
    assert len(report["candidates"]) == 1
    assert len(report["candidates"][0]["acquisitions"]) == 2


def score_profile(tmp_path: Path):
    import json
    spec = {"kind": "strict_score_glyphs", "glyph_threshold": .90,
            "glyph_margin": .04, "comparison_preprocessing": "gaussian3x3_v1",
            "foreground_preprocessing": "unsupported_old_experiment",
            "templates": {str(i): f"{i}.png" for i in range(10)}}
    for i in range(10):
        im = np.zeros((32, 24), np.uint8)
        cv2.putText(im, str(i), (1, 24), 0, .8, 255, 2)
        cv2.imwrite(str(tmp_path / f"{i}.png"), im)
    path = tmp_path / "profile.json"
    path.write_text(json.dumps({"schema_version": "1.0",
                               "readers": {n: spec for n in ["ally_score", "enemy_score"]}}))
    return path


def test_unsupported_score_configuration_is_a_preflight_error_not_image_failure(tmp_path):
    path = score_profile(tmp_path)
    with pytest.raises(ValueError, match="Score reader unavailable"):
        score_readers(path)


def test_supported_foreground_requires_explicit_declaration_preserves_parent(tmp_path):
    path = score_profile(tmp_path)
    before = path.read_bytes()
    readers, receipt = score_readers(path, foreground="white200_rowcontrast_v1")
    assert set(readers) == {"ally_score", "enemy_score"}
    assert receipt["explicit_foreground"] == "white200_rowcontrast_v1"
    assert receipt["production_changed"] is False
    assert path.read_bytes() == before


def test_two_valid_but_conflicting_replays_remain_unknown():
    first = transition()
    second = deepcopy(first)
    for f in second:
        f["epoch"] = "other"
        if f["result"]["value"]:
            f["result"]["value"] = "WON"
    c = integrate(first + second)["candidates"][0]
    assert c["status"] == "UNKNOWN" and "acquisition_replay_disagrees" in c["reasons"]


def test_cli_enforces_development_binding_and_exclusive_private_output(tmp_path, monkeypatch):
    import json

    from scripts.diagnostics import round_transition_evidence as module

    inp, out = tmp_path / "input.json", tmp_path / "output.json"
    inp.write_text(json.dumps({"source_id": "dev", "source_sha256": "a" * 64,
                               "rows": transition()}))
    calls = []
    monkeypatch.setattr(module, "development_sources", lambda _: [
        {"video_id": "dev", "source_sha256": "a" * 64}])
    monkeypatch.setattr(module, "append_exposure", lambda *a, **k: calls.append((a, k)))
    report = module.run(tmp_path, inp, out)
    assert report["formal_events"] == [] and len(calls) == 1
    assert out.stat().st_mode & 0o777 == 0o600
    with pytest.raises(FileExistsError):
        module.run(tmp_path, inp, out)
    assert len(calls) == 1
    monkeypatch.setattr(module, "development_sources", lambda _: [])
    with pytest.raises(ValueError, match="DEVELOPMENT"):
        module.run(tmp_path, inp, tmp_path / "forbidden.json")
    assert not (tmp_path / "forbidden.json").exists()


def test_later_conflicting_score_is_not_hidden_by_truncating_the_window():
    rows = transition() + [frame(5, score=(9, 9))]
    c = integrate(rows)["candidates"][0]
    assert c["status"] == "UNKNOWN"
    assert "conflicting_score_observation" in c["reasons"]
    assert c["score_conflicts"][0]["tick"] == 5
