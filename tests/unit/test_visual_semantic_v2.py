import json
import runpy

import pytest

from valorant_ai_coach.events import EventSourceContract
from valorant_ai_coach.resources import resource_path
from valorant_ai_coach.video import FrameSample
from valorant_ai_coach.visual.fusion import EvidenceFusion, resolve_value
from valorant_ai_coach.visual.sampling import micro_requests
from valorant_ai_coach.visual.semantic import FACT_FIELDS, SemanticBudget, SemanticVisualAdapter


def test_original_visual_patch_validator_unchanged():
    runpy.run_path(str(resource_path("config/visual_v2/tests/validate_visual_patch.py")))


def test_budget_persists_counts_failed_attempts_and_resumed_windows(tmp_path):
    path = tmp_path / "budget.sqlite"
    budget = SemanticBudget(path)
    for index in range(8):
        assert budget.reserve("match", "1", str(index), 8, 96)
    assert not SemanticBudget(path).reserve("match", "1", "next", 8, 96)
    for round_no in range(2, 13):
        for index in range(8):
            assert budget.reserve("match", str(round_no), f"{round_no}-{index}", 8, 96)
    assert not budget.reserve("match", "13", "last", 8, 96)
    assert budget.reserve("other", "1", "0", 8, 96)
    assert not budget.reserve("other", "1", "0", 8, 96)


@pytest.mark.parametrize("context,expected", [(False, 12), (True, 24)])
def test_semantic_keyframes_and_isolation(tmp_path, context, expected):
    path = tmp_path / "frame.jpg"
    path.write_bytes(b"test-image-bytes")
    requests = []

    def transport(content, schema):
        requests.append(content)
        assert "exposed_directions_count" not in schema["properties"]
        return {
            **{key: None for key in FACT_FIELDS},
            "confidence": 0.95,
            "affected_side": "unknown",
        }

    adapter = SemanticVisualAdapter(transport=transport)
    result = adapter.observe(
        [FrameSample(i / 15, path) for i in range(30)],
        match_id="m",
        round_id="r",
        context_pass=context,
    )
    assert result is not None
    assert sum(item["type"] == "input_image" for item in requests[0]) == expected
    assert "rule_id" not in json.dumps(requests)
    assert "GOOD" not in json.dumps(requests)


def test_semantic_invalid_fields_and_failures_abstain_without_retry(tmp_path):
    path = tmp_path / "x.jpg"
    path.write_bytes(b"test")
    calls = []

    def transport(*_):
        calls.append(1)
        return {"exposed_directions_count": 5, "confidence": 1.0}

    adapter = SemanticVisualAdapter(transport=transport)
    for _ in range(2):
        assert adapter.observe([FrameSample(1, path)], match_id="m", round_id="r") is None
    assert len(calls) == 1


def test_micro_sampling_clamps_unions_and_keeps_15fps():
    requests = micro_requests(3, [(0, "shot"), (0.1, "shot"), (2.8, "shot")])
    times = [request.time_sec for request in requests]
    assert times == sorted(set(times))
    assert times[0] == 0 and times[-1] == 3
    assert times[1] == pytest.approx(1 / 15, abs=1e-6)


def test_evidence_conflict_not_always_hud():
    contract = EventSourceContract.load(resource_path("config/event_source_contract_v1.json"))
    fusion = EvidenceFusion(contract)
    event = {
        "event_id": "h",
        "type": "spike_pickup",
        "actor": "player",
        "time_sec": 1,
        "confidence": 0.86,
        "attributes": {"visible": True},
    }
    other = {**event, "event_id": "v", "confidence": 0.98, "attributes": {"visible": False}}
    hud, visual, notes = fusion.events([event], [other])
    assert not hud and visual == (other,) and not notes
    other["confidence"] = 0.87
    hud, visual, notes = fusion.events([event], [other])
    assert not hud and not visual and notes
    assert resolve_value("A", 0.88, "B", 0.9) is None
    assert resolve_value("A", 0.7, "B", 0.95) == "B"
