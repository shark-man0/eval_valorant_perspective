from copy import deepcopy

import pytest

from scripts.diagnostics.ui_transition_contract import TransientUiDiagnostic


def prepared():
    model = TransientUiDiagnostic()
    model.advance(10, phase_confirmed=True, display="0:00", scene_supported=True)
    model.advance(10.1, phase_confirmed=True, display="0:00", scene_supported=True)
    assert model.state == "pre_round"
    return model


def point(model, pts, display, **kwargs):
    return model.advance(
        pts, phase_confirmed=False, display=display, scene_supported=True, **kwargs
    )


@pytest.mark.parametrize("transient,stable", [("2:17", "1:28"), ("3:09", "0:44")])
def test_all_display_values_retained_and_stable_display_does_not_authorize_round(transient, stable):
    model = prepared()
    displays = ["0:00", transient, transient, stable, stable]
    result = [point(model, 10.2 + i * 0.1, text) for i, text in enumerate(displays)]
    assert all(r["state"] == "transient_ui_transition" for r in result)
    assert result[-1]["display_stable"] is True
    assert all(r["round_event_authorized"] is False for r in result)
    assert [r["display"] for r in model.display_history][-5:] == displays
    assert result[-1]["clock_semantics"] == "unqualified"


@pytest.mark.parametrize("veto", ["content_jump", "duplicate_pixels"])
def test_explicit_source_veto_clears_context_without_discarding_raw_value(veto):
    model = prepared()
    point(model, 10.2, "1:28")
    result = point(model, 10.3, "1:27", **{veto: True})
    assert result["state"] == "unobserved"
    assert result["content_veto"] is True
    assert model.display_history[-1] == {"pts_sec": 10.3, "display": "1:27"}
    assert point(model, 10.4, "1:27")["state"] == "unobserved"


@pytest.mark.parametrize("pts", [10.1, 9.9, 12.0])
def test_duplicate_backward_or_long_gap_does_not_continue_preparation(pts):
    result = point(prepared(), pts, "1:28")
    assert result["content_veto"]
    assert result["state"] == "unobserved"


def test_inconclusive_scene_is_not_declared_cut_and_cannot_bridge_transition():
    model = prepared()
    result = model.advance(10.2, phase_confirmed=False, display="1:28", scene_supported=False)
    assert result["content_veto"] is False
    assert result["state"] == "unobserved"
    assert point(model, 10.3, "1:28")["state"] == "unobserved"


def test_phase_jitter_requires_a_new_confirmed_span():
    model = prepared()
    point(model, 10.2, "1:28")
    result = model.advance(10.3, phase_confirmed=True, display="0:00", scene_supported=True)
    assert result["state"] == "phase_candidate"
    assert point(model, 10.4, "1:28")["state"] == "unobserved"


def test_missing_display_never_becomes_stable_or_invented():
    model = prepared()
    point(model, 10.2, "1:28")
    result = point(model, 10.4, None)
    assert not result["display_stable"]
    assert result["raw_display"] is None
    assert not result["round_event_authorized"]


def test_returned_history_is_not_player_evidence():
    model = prepared()
    result = point(model, 10.2, "1:28")
    original = deepcopy(model.display_history)
    assert "actor" not in result
    assert "player_specific_hud_valid" not in result
    assert "global_continuity" not in result
    assert model.display_history == original


def test_initial_unattested_phase_cannot_supply_preparation_duration():
    model = TransientUiDiagnostic()
    first = model.advance(1, phase_confirmed=True, display="0:00", scene_supported=False)
    assert first["state"] == "unobserved"
    assert not first["content_veto"]
    second = model.advance(1.1, phase_confirmed=True, display="0:00", scene_supported=True)
    assert second["state"] == "phase_candidate"
    assert not model.armed
    third = model.advance(1.2, phase_confirmed=True, display="0:00", scene_supported=True)
    assert third["state"] == "pre_round"
    assert model.armed
