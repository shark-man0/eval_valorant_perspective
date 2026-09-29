from __future__ import annotations

import json
from pathlib import Path

from jsonschema import Draft202012Validator

from valorant_ai_coach.rules import MockEvaluator

ROOT = Path(__file__).resolve().parents[2]


def test_mock_evaluator_reproduces_all_38_observation_driven_cases() -> None:
    evaluator = MockEvaluator()
    schema_path = ROOT / "schemas" / "ai_coach_output_schema_v3.json"
    output_schema = json.loads(schema_path.read_text(encoding="utf-8"))
    validator = Draft202012Validator(output_schema)
    case_dirs = sorted((ROOT / "tests" / "cases").glob("TC-*"))
    assert len(case_dirs) == 38
    for case_dir in case_dirs:
        package = json.loads((case_dir / "input.json").read_text(encoding="utf-8"))
        expected = json.loads((case_dir / "expected_assertions.json").read_text(encoding="utf-8"))
        output = evaluator.evaluate(package)
        errors = list(validator.iter_errors(output))
        assert not errors, f"{case_dir.name}: {[error.message for error in errors]}"
        actual = output["evaluations"]
        expected_items = expected["expected_evaluations"]
        assert [(item["primary_rule_id"], item["label"]) for item in actual] == [
            (item["primary_rule_id"], item["label"]) for item in expected_items
        ], case_dir.name
        for item, assertion in zip(actual, expected_items, strict=True):
            assert set(assertion["required_concept_tags"]).issubset(item["concept_tags"]), (
                case_dir.name
            )
            assert set(item["related_rule_ids"]).issubset(assertion["allowed_related_rule_ids"]), (
                case_dir.name
            )
            low, high = assertion["confidence_range"]
            assert low <= item["confidence"] <= high, case_dir.name
            assert (item["display_clip"] is not None) is assertion["expect_clip"], case_dir.name
            has_missing = bool(item["missing_information"])
            assert has_missing is assertion["expect_missing_information"], case_dir.name
            if codes := assertion.get("expected_unscored_reason_codes"):
                assert item["unscored_reason_code"] in codes, case_dir.name
