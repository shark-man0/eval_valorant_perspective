from copy import deepcopy
from types import SimpleNamespace

import numpy as np
import pytest

from tests.e2e.trace_adapter import to_e2e_trace
from valorant_ai_coach.hud.analyzers import RealHudAnalyzer
from valorant_ai_coach.hud.models import HudObservationV2, empty_hud_values
from valorant_ai_coach.hud.readers import ReaderResult
from valorant_ai_coach.hud.templates import NumericFieldsReader
from valorant_ai_coach.resources import resource_path
from valorant_ai_coach.schema_validation import SchemaValidator


class FieldReader:
    def __init__(self, results):
        self.results = iter(results)
        self.calls = 0

    def read(self, image, roi):
        self.calls += 1
        return next(self.results)


def _reading():
    reader = NumericFieldsReader(
        {"damage_received": (0., 0., 1., 1.)},
        FieldReader([ReaderResult("0194", .95, ("source_ocr",))]),
    )
    return {
        "status": "candidate", "reader": "combat_report", "source_pts_sec": 1.,
        "source_pixel_sha256": "a" * 64, "profile_fingerprint": None,
        "fields": reader.read_candidates(np.zeros((20, 30, 3), dtype=np.uint8)),
    }


def test_independent_fields_preserve_source_display_and_unknown():
    reader = NumericFieldsReader(
        {"damage_given": (0., 0., .5, 1.), "damage_received": (.5, 0., 1., 1.)},
        FieldReader([ReaderResult(None, 0), ReaderResult("0194", .95, ("ocr",))]),
    )
    fields = reader.read_candidates(np.zeros((20, 30, 3), dtype=np.uint8))
    assert set(fields) == {"damage_received"}
    assert fields["damage_received"] == {
        "display": "0194", "value": 194, "confidence": .95, "sources": ["ocr"],
        "cross_checked": False, "roi_bounds_norm": [.5, 0., 1., 1.],
    }


@pytest.mark.parametrize("result", [
    ReaderResult("194", .89, ("ocr",), True),
    ReaderResult("194", float("nan"), ("ocr",)),
    ReaderResult("194", True, ("ocr",)),
    ReaderResult("194", .99, ()),
    ReaderResult("194", .99, (" ",)),
    ReaderResult("١٩٤", .99, ("ocr",)),
    ReaderResult("194 damage", .99, ("ocr",)),
    ReaderResult("1234567", .99, ("ocr",)),
    ReaderResult(194, .99, ("ocr",)),
])
def test_report_candidate_abstains_without_reliable_original_text(result):
    reader = NumericFieldsReader({"damage_received": (0., 0., 1., 1.)}, FieldReader([result]))
    assert reader.read_candidates(np.zeros((20, 30), dtype=np.uint8)) == {}


def test_empty_or_collapsed_crop_does_not_call_reader():
    raw = FieldReader([])
    reader = NumericFieldsReader({"damage_received": (0., 0., .01, .01)}, raw)
    assert reader.read_candidates(np.zeros((0, 0), dtype=np.uint8)) == {}
    assert reader.read_candidates(np.zeros((2, 2), dtype=np.uint8)) == {}
    assert raw.calls == 0


def test_existing_numeric_read_contract_unchanged():
    reader = NumericFieldsReader(
        {"hp": (0., 0., 1., 1.)}, FieldReader([ReaderResult("22", .85, ("ocr",))]),
    )
    assert reader.read(np.zeros((20, 30), dtype=np.uint8),
                       np.zeros((20, 30), dtype=np.uint8)).value == {"hp": 22}


def test_model_roundtrip_preserves_unowned_candidate():
    values = empty_hud_values()
    values.update(combat_report_visible=True, combat_report_readings=_reading())
    source = HudObservationV2(1., 0, values=values).to_dict()
    SchemaValidator().validate_hud_observation(source)
    assert HudObservationV2.from_dict(source).to_dict() == source
    assert source["values"]["player_specific_hud_valid"] is False
    assert source["values"]["hp"] is None


@pytest.mark.parametrize("mutation", [
    "confirmed", "stale_pts", "hidden_report", "wrong_value", "weak_confidence",
    "empty_sources", "invalid_bounds", "extra_owner", "missing_pixel_hash",
])
def test_persisted_candidate_rejects_malformed_or_promoted_readings(mutation):
    values = empty_hud_values()
    values.update(combat_report_visible=True, combat_report_readings=_reading())
    source = HudObservationV2(1., 0, values=values).to_dict()
    reading = source["values"]["combat_report_readings"]
    numeric = reading["fields"]["damage_received"]
    if mutation == "confirmed":
        reading["status"] = "confirmed"
    elif mutation == "stale_pts":
        reading["source_pts_sec"] = .5
    elif mutation == "hidden_report":
        source["values"]["combat_report_visible"] = False
    elif mutation == "wrong_value":
        numeric["value"] = 130
    elif mutation == "weak_confidence":
        numeric["confidence"] = .89
    elif mutation == "empty_sources":
        numeric["sources"] = []
    elif mutation == "invalid_bounds":
        numeric["roi_bounds_norm"] = [1., 0., 0., 1.]
    elif mutation == "extra_owner":
        reading["owner"] = "self"
    else:
        reading["source_pixel_sha256"] = ""
    with pytest.raises(ValueError):
        HudObservationV2.from_dict(source)
    with pytest.raises(ValueError):
        SchemaValidator().validate_hud_observation(source)


def test_actual_analyzer_records_only_current_visible_report_without_player_facts():
    raw = FieldReader([ReaderResult("194", .95, ("source_ocr",))])
    analyzer = RealHudAnalyzer(
        resource_path("config/hud_layout_1080p_v3.json"),
        readers={"combat_report": NumericFieldsReader(
            {"damage_received": (0., 0., 1., 1.)}, raw,
        )},
    )
    analyzer.ocr_fallback_rois = ()
    anchors = {
        name: analyzer.layout.normalized_roi(name)
        for name in ("round_timer", "top_match_bar", "player_hp_armor", "abilities")
    }
    frames = [np.zeros((1080, 1920, 3), dtype=np.uint8)] * 3
    signals = [{}, {"combat_report_visible": True, "combat_report_confidence": .95}, {}]
    result = analyzer.observe_frames(frames, anchor_detections=anchors, additional_signals=signals)
    assert raw.calls == 1
    assert "combat_report_readings" not in result.observations[0]["values"]
    assert "combat_report_readings" not in result.observations[2]["values"]
    reading = result.observations[1]["values"]["combat_report_readings"]
    assert reading["fields"]["damage_received"]["display"] == "194"
    assert reading["source_pts_sec"] == result.observations[1]["time_sec"]
    assert reading["status"] == "candidate"
    assert result.hud_events == ()
    for row in result.observations:
        assert row["primary_state"] == "unknown"
        assert row["values"]["player_specific_hud_valid"] is False
        assert row["values"]["hp"] is None
        SchemaValidator().validate_hud_observation(row)
    # No source observation is relabeled as a confirmed death attribute by trace.
    trace = to_e2e_trace(SimpleNamespace(
        round_packages=[{"round_window": {"start_sec": 0, "end_sec": 2},
                         "state_snapshots": [{"time_sec": 1}]}],
        observations=deepcopy(result.observations),
    ))
    assert not trace["events"]
    assert "combat_report_damage_received" not in trace["snapshots"][0]
