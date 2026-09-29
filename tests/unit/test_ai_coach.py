from __future__ import annotations

import importlib
import json
from pathlib import Path
from threading import Event, Thread
from types import SimpleNamespace
from typing import Any

import pytest

from valorant_ai_coach.ai import (
    AiCoachCancelled,
    FileResultCache,
    OpenAICoach,
    OpenAIResponseError,
)
from valorant_ai_coach.schema_validation import SchemaValidator

ROOT = Path(__file__).resolve().parents[2]


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def package() -> dict[str, Any]:
    return load_json(ROOT / "tests" / "cases" / "TC-006" / "input.json")


def output() -> dict[str, Any]:
    return {
        "schema_version": "3.0",
        "analysis_id": "analysis-006",
        "match_id": "MOCK-TC-006",
        "round_no": 5,
        "evaluations": [
            {
                "evaluation_id": "eval-006",
                "clip_id": "clip-006",
                "primary_rule_id": "AIM-02",
                "related_rule_ids": [],
                "label": "good",
                "decision_source": "hybrid",
                "fact_refs": ["F008"],
                "concept_tags": ["preaim", "crosshair_placement"],
                "title": "プリエイムできています",
                "situation": "角へ出る前に照準を合わせました。",
                "reason": "0.7秒前から照準を置いた事実が基準を満たします。",
                "improvement": None,
                "confidence": 0.96,
                "evidence": [
                    {
                        "time_sec": 30.0,
                        "fact": "preaim_lead_sec は0.7秒",
                        "source": "deterministic_fact",
                    }
                ],
                "evidence_range": {"start_sec": 29.0, "end_sec": 31.0},
                "display_clip": {"start_sec": 26.0, "end_sec": 35.0},
                "missing_information": [],
                "unscored_reason_code": None,
            }
        ],
    }


class FakeResponses:
    def __init__(self, outputs: list[str | Exception]) -> None:
        self.outputs = outputs
        self.calls: list[dict[str, Any]] = []

    def create(self, **kwargs: Any) -> Any:
        self.calls.append(kwargs)
        value = self.outputs.pop(0)
        if isinstance(value, Exception):
            raise value
        return SimpleNamespace(status="completed", output_text=value)


class FakeClient:
    def __init__(self, outputs: list[str | Exception]) -> None:
        self.responses = FakeResponses(outputs)


def coach(
    client: FakeClient,
    repairs: int = 2,
    *,
    retry_delays: tuple[float, ...] = (),
    cache: FileResultCache | None = None,
) -> OpenAICoach:
    rules = load_json(ROOT / "config" / "valorant_evaluation_rules_v4.json")
    return OpenAICoach(
        api_key="test-key",
        model="test-model",
        rules_by_id={rule["id"]: rule for rule in rules["rules"]},
        validator=SchemaValidator(),
        client=client,
        max_repair_attempts=repairs,
        retry_delays=retry_delays,
        cache=cache,
    )


def test_only_selected_rules_are_sent_and_result_is_validated() -> None:
    client = FakeClient([json.dumps(output(), ensure_ascii=False)])
    result = coach(client).evaluate(package(), ["AIM-02"])
    assert result["evaluations"][0]["primary_rule_id"] == "AIM-02"
    call = client.responses.calls[0]
    prompt = json.loads(call["input"][0]["content"][0]["text"])
    assert [rule["id"] for rule in prompt["candidate_rules"]] == ["AIM-02"]
    assert prompt["round_package"]["source_video"]["path"] == "TC-006.mp4"
    assert call["text"]["format"]["schema"]["$id"] == "ai_coach_output_schema_v3.json"
    assert call["store"] is False


def test_schema_failure_is_repaired_at_most_twice() -> None:
    client = FakeClient(["{}", json.dumps(output(), ensure_ascii=False)])
    result = coach(client).evaluate(package(), ["AIM-02"])
    assert result["schema_version"] == "3.0"
    assert len(client.responses.calls) == 2
    repair = client.responses.calls[1]["input"][0]["content"][-1]["text"]
    repair_payload = json.loads(repair)
    assert repair_payload["repair_request"]
    assert repair_payload["round_window"] == package()["round_window"]
    assert repair_payload["allowed_fact_ids"] == [
        fact["fact_id"] for fact in package()["deterministic_facts"]
    ]
    assert repair_payload["selected_rule_policies"][0]["id"] == "AIM-02"
    assert "human_policy" in repair_payload["selected_rule_policies"][0]
    assert "human_exceptions" in repair_payload["selected_rule_policies"][0]


def test_invalid_output_after_repairs_raises() -> None:
    client = FakeClient(["{}", "{}", "{}"])
    with pytest.raises(OpenAIResponseError, match="2回修復"):
        coach(client).evaluate(package(), ["AIM-02"])
    assert len(client.responses.calls) == 3


def test_no_candidates_returns_no_evaluations_without_api_call() -> None:
    client = FakeClient([])
    result = coach(client).evaluate(package(), [])
    assert result["evaluations"] == []
    assert client.responses.calls == []


def test_more_than_twelve_candidates_are_rejected() -> None:
    client = FakeClient([])
    with pytest.raises(ValueError, match="最大12件"):
        coach(client).evaluate(package(), [f"R-{index:02d}" for index in range(13)])


def test_binding_deterministic_decision_is_sent_and_enforced() -> None:
    deterministic = {
        "AIM-02": {
            "label": "good",
            "confidence": 0.98,
            "fact_refs": ["F008"],
            "reason": "約0.5秒前のプリエイム",
        }
    }
    client = FakeClient([json.dumps(output(), ensure_ascii=False)])
    coach(client).evaluate(package(), ["AIM-02"], deterministic_decisions=deterministic)
    prompt = json.loads(client.responses.calls[0]["input"][0]["content"][0]["text"])
    assert prompt["binding_deterministic_decisions"] == deterministic

    conflicting = output()
    conflicting["evaluations"][0]["label"] = "improve"
    conflicting["evaluations"][0]["improvement"] = "止まって照準を合わせる"
    client = FakeClient([json.dumps(conflicting, ensure_ascii=False)])
    result = coach(client, repairs=0).evaluate(
        package(), ["AIM-02"], deterministic_decisions=deterministic
    )
    assert result["evaluations"][0]["label"] == "good"
    assert result["evaluations"][0]["improvement"] is None
    assert result["evaluations"][0]["fact_refs"] == ["F008"]
    assert result["evaluations"][0]["decision_source"] == "hybrid"


def test_related_rule_can_satisfy_same_scene_deterministic_binding() -> None:
    value = output()
    evaluation = value["evaluations"][0]
    evaluation["primary_rule_id"] = "AIM-03"
    evaluation["related_rule_ids"] = ["MOV-02"]
    evaluation["fact_refs"] = ["F008", "F009"]
    decisions = {
        "AIM-03": {"label": "good", "fact_refs": ["F008"]},
        "MOV-02": {"label": "good", "fact_refs": ["F009"]},
    }

    OpenAICoach._validate_deterministic_alignment(value, decisions)


def test_related_deterministic_rule_does_not_relabel_non_deterministic_primary() -> None:
    value = output()
    evaluation = value["evaluations"][0]
    evaluation["primary_rule_id"] = "DEC-01"
    evaluation["related_rule_ids"] = ["AIM-02"]
    evaluation["label"] = "improve"
    evaluation["improvement"] = "味方と歩調を合わせて進行する"
    evaluation["decision_source"] = "llm"
    client = FakeClient([json.dumps(value, ensure_ascii=False)])

    result = coach(client, repairs=0).evaluate(
        package(),
        ["DEC-01", "AIM-02"],
        deterministic_decisions={
            "AIM-02": {
                "label": "good",
                "confidence": 0.98,
                "fact_refs": ["F008"],
                "reason": "約0.5秒前のプリエイム",
            }
        },
    )

    by_rule = {item["primary_rule_id"]: item for item in result["evaluations"]}
    assert by_rule["DEC-01"]["label"] == "improve"
    assert by_rule["DEC-01"]["improvement"] == "味方と歩調を合わせて進行する"
    assert by_rule["DEC-01"]["decision_source"] == "llm"
    assert "AIM-02" not in by_rule["DEC-01"]["related_rule_ids"]
    assert by_rule["AIM-02"]["label"] == "good"
    assert by_rule["AIM-02"]["decision_source"] == "deterministic"


def test_duplicate_deterministic_primary_evaluations_are_collapsed() -> None:
    value = output()
    duplicate = dict(value["evaluations"][0])
    duplicate.update(
        {
            "evaluation_id": "duplicate-model-eval",
            "clip_id": "duplicate-model-clip",
            "label": "improve",
            "improvement": "照準を修正する",
        }
    )
    value["evaluations"].append(duplicate)
    client = FakeClient([json.dumps(value, ensure_ascii=False)])

    result = coach(client, repairs=0).evaluate(
        package(),
        ["AIM-02"],
        deterministic_decisions={
            "AIM-02": {
                "label": "good",
                "confidence": 0.98,
                "fact_refs": ["F008"],
                "reason": "約0.5秒前のプリエイム",
            }
        },
    )

    assert len(result["evaluations"]) == 1
    assert result["evaluations"][0]["primary_rule_id"] == "AIM-02"
    assert result["evaluations"][0]["label"] == "good"


def test_missing_deterministic_evaluation_is_synthesized_locally() -> None:
    empty = {
        "schema_version": "3.0",
        "analysis_id": "analysis-empty",
        "match_id": "wrong-model-id",
        "round_no": 999,
        "evaluations": [],
    }
    decisions = {
        "AIM-02": {
            "label": "good",
            "confidence": 0.98,
            "fact_refs": ["F008"],
            "reason": "約0.5秒前のプリエイム",
        }
    }
    client = FakeClient([json.dumps(empty, ensure_ascii=False)])

    result = coach(client).evaluate(
        package(), ["AIM-02"], deterministic_decisions=decisions
    )

    assert result["match_id"] == "MOCK-TC-006"
    assert result["round_no"] == 5
    assert len(result["evaluations"]) == 1
    evaluation = result["evaluations"][0]
    assert evaluation["primary_rule_id"] == "AIM-02"
    assert evaluation["label"] == "good"
    assert evaluation["decision_source"] == "deterministic"
    assert evaluation["evidence"][0]["time_sec"] == 30


def test_model_ids_are_canonical_and_scoped_to_match_and_round() -> None:
    first_package = package()
    second_package = package()
    second_package["round_no"] += 1
    third_package = package()
    third_package["match_id"] = "MATCH-OTHER-006"

    results = []
    for round_package in (first_package, second_package, third_package, first_package):
        client = FakeClient([json.dumps(output(), ensure_ascii=False)])
        results.append(coach(client, repairs=0).evaluate(round_package, ["AIM-02"]))

    ids = [result["evaluations"][0] for result in results]
    assert ids[0]["evaluation_id"].startswith("eval-")
    assert ids[0]["clip_id"].startswith("clip-")
    assert ids[0]["evaluation_id"] != ids[1]["evaluation_id"]
    assert ids[0]["evaluation_id"] != ids[2]["evaluation_id"]
    assert ids[0]["clip_id"] != ids[1]["clip_id"]
    assert ids[0]["clip_id"] != ids[2]["clip_id"]
    assert ids[0]["evaluation_id"] == ids[3]["evaluation_id"]
    assert ids[0]["clip_id"] == ids[3]["clip_id"]


def test_unscored_result_always_has_null_clip_id() -> None:
    value = output()
    evaluation = value["evaluations"][0]
    evaluation.update(
        {
            "label": "unscored",
            "clip_id": "generic-model-clip",
            "display_clip": None,
            "improvement": None,
            "missing_information": ["照準位置を確認できる映像"],
            "unscored_reason_code": "insufficient_visual_evidence",
        }
    )

    result = coach(FakeClient([json.dumps(value, ensure_ascii=False)]), repairs=0).evaluate(
        package(), ["AIM-02"]
    )

    assert result["evaluations"][0]["clip_id"] is None


def test_transient_transport_retry_does_not_consume_schema_repair_budget() -> None:
    class RateLimitedError(RuntimeError):
        status_code = 429

    client = FakeClient([RateLimitedError("slow down"), json.dumps(output())])

    result = coach(client, repairs=0, retry_delays=(0.0,)).evaluate(package(), ["AIM-02"])

    assert result["evaluations"][0]["label"] == "good"
    assert len(client.responses.calls) == 2


def test_schema_repair_does_not_resend_evidence_images(tmp_path: Path) -> None:
    frame = tmp_path / "evidence.jpg"
    frame.write_bytes(b"jpeg evidence")
    client = FakeClient(["{}", json.dumps(output(), ensure_ascii=False)])

    coach(client).evaluate(package(), ["AIM-02"], frame_paths=[frame])

    first_content = client.responses.calls[0]["input"][0]["content"]
    repair_content = client.responses.calls[1]["input"][0]["content"]
    assert any(item["type"] == "input_image" for item in first_content)
    assert all(item["type"] != "input_image" for item in repair_content)


def test_validated_result_cache_avoids_second_api_call(tmp_path: Path) -> None:
    cache = FileResultCache(tmp_path / "cache")
    first_client = FakeClient([json.dumps(output(), ensure_ascii=False)])
    first = coach(first_client, cache=cache).evaluate(package(), ["AIM-02"])
    second_client = FakeClient([])

    second = coach(second_client, cache=cache).evaluate(package(), ["AIM-02"])

    assert second == first
    assert second_client.responses.calls == []
    assert list((tmp_path / "cache").rglob("*.json"))


def test_system_instructions_change_invalidates_cache(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    cache = FileResultCache(tmp_path / "cache")
    first_client = FakeClient([json.dumps(output(), ensure_ascii=False)])
    coach(first_client, cache=cache).evaluate(package(), ["AIM-02"])
    second_client = FakeClient([json.dumps(output(), ensure_ascii=False)])
    module = importlib.import_module("valorant_ai_coach.ai.coach")
    monkeypatch.setattr(module, "SYSTEM_INSTRUCTIONS", "changed prompt contract")

    coach(second_client, cache=cache).evaluate(package(), ["AIM-02"])

    assert len(second_client.responses.calls) == 1


def test_in_flight_api_request_can_be_cancelled() -> None:
    started = Event()
    released = Event()
    cancel = Event()

    class BlockingResponses:
        @staticmethod
        def create(**_kwargs: Any) -> Any:
            started.set()
            released.wait(5)
            return SimpleNamespace(status="completed", output_text=json.dumps(output()))

    class BlockingClient:
        responses = BlockingResponses()
        closed = False

        def close(self) -> None:
            self.closed = True
            released.set()

    client = BlockingClient()
    subject = coach(client)  # type: ignore[arg-type]
    # Exercise the production-owned client shutdown path with a controllable fake.
    subject._owns_client = True

    def request_cancel() -> None:
        assert started.wait(2)
        cancel.set()

    canceller = Thread(target=request_cancel)
    canceller.start()
    with pytest.raises(AiCoachCancelled):
        subject.evaluate(package(), ["AIM-02"], cancel_event=cancel)
    canceller.join(timeout=2)

    assert client.closed is True
