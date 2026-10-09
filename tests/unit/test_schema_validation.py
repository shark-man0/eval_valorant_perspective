from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from valorant_ai_coach.schema_validation import ContractValidationError, SchemaValidator

ROOT = Path(__file__).resolve().parents[2]


def load_case(case_id: str) -> dict[str, object]:
    path = ROOT / "tests" / "cases" / case_id / "input.json"
    return json.loads(path.read_text(encoding="utf-8"))


def valid_output() -> dict[str, object]:
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
                "title": "事前に照準を合わせられています",
                "situation": "角へ出る0.7秒前から頭の高さへ照準を置きました。",
                "reason": "約0.5秒前という基準を満たし、結果ではなく準備動作が良好です。",
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


def test_canonical_round_package_and_output_validate() -> None:
    validator = SchemaValidator()
    package = load_case("TC-006")
    validator.validate_round_package(package)
    validator.validate_ai_output(
        valid_output(), round_package=package, candidate_rule_ids={"AIM-02"}
    )


def test_candidate_membership_is_enforced_beyond_json_schema() -> None:
    validator = SchemaValidator()
    package = load_case("TC-006")
    output = valid_output()
    output["evaluations"][0]["primary_rule_id"] = "DEC-01"  # type: ignore[index]
    with pytest.raises(ContractValidationError, match="候補外"):
        validator.validate_ai_output(output, round_package=package, candidate_rule_ids={"AIM-02"})


def test_fact_reference_and_time_range_are_enforced() -> None:
    validator = SchemaValidator()
    package = load_case("TC-006")
    output = copy.deepcopy(valid_output())
    output["evaluations"][0]["fact_refs"] = ["UNKNOWN"]  # type: ignore[index]
    with pytest.raises(ContractValidationError, match="未知のfact_id"):
        validator.validate_ai_output(output, round_package=package, candidate_rule_ids={"AIM-02"})
    output = copy.deepcopy(valid_output())
    output["evaluations"][0]["display_clip"] = {  # type: ignore[index]
        "start_sec": 99,
        "end_sec": 110,
    }
    with pytest.raises(ContractValidationError, match="ラウンド範囲外"):
        validator.validate_ai_output(output, round_package=package, candidate_rule_ids={"AIM-02"})


def test_round_temporal_fields_are_finite_ordered_and_in_window() -> None:
    validator = SchemaValidator()

    package = load_case("TC-006")
    package["state_snapshots"][0]["time_sec"] = 101  # type: ignore[index]
    with pytest.raises(ContractValidationError, match="state_snapshots.*ラウンド範囲外"):
        validator.validate_round_package(package)

    package = load_case("TC-006")
    package["deterministic_facts"][2]["time_sec"] = 101  # type: ignore[index]
    with pytest.raises(ContractValidationError, match="time_sec がラウンド範囲外"):
        validator.validate_round_package(package)

    package = load_case("TC-006")
    package["deterministic_facts"][2]["time_range"] = {  # type: ignore[index]
        "start_sec": 98,
        "end_sec": 101,
    }
    with pytest.raises(ContractValidationError, match="time_range がラウンド範囲外"):
        validator.validate_round_package(package)

    package = load_case("TC-006")
    package["deterministic_facts"][2]["time_range"] = {  # type: ignore[index]
        "start_sec": 30,
        "end_sec": 29,
    }
    with pytest.raises(ContractValidationError, match="time_range の終了<=開始"):
        validator.validate_round_package(package)

    package = load_case("TC-006")
    package["deterministic_facts"][2]["time_sec"] = float("inf")  # type: ignore[index]
    with pytest.raises(ContractValidationError, match="time_sec は有限値"):
        validator.validate_round_package(package)

    package = load_case("TC-006")
    package["frames"].append(  # type: ignore[union-attr]
        {"time_sec": 101, "path": "frame.jpg", "purpose": "sparse_round_context"}
    )
    with pytest.raises(ContractValidationError, match="frames.*ラウンド範囲外"):
        validator.validate_round_package(package)


def test_scored_evidence_and_display_ranges_are_cross_validated() -> None:
    validator = SchemaValidator()
    package = load_case("TC-006")

    output = copy.deepcopy(valid_output())
    output["evaluations"][0]["evidence"][0]["time_sec"] = 35  # type: ignore[index]
    with pytest.raises(ContractValidationError, match="evidence.time_sec がevidence_range外"):
        validator.validate_ai_output(output, round_package=package, candidate_rule_ids={"AIM-02"})

    output = copy.deepcopy(valid_output())
    output["evaluations"][0]["evidence_range"] = {  # type: ignore[index]
        "start_sec": 29,
        "end_sec": 35.03,
    }
    # A 0.05s rounding tolerance is allowed at the evidence/display boundary.
    validator.validate_ai_output(output, round_package=package, candidate_rule_ids={"AIM-02"})

    output["evaluations"][0]["evidence_range"]["end_sec"] = 35.06  # type: ignore[index]
    with pytest.raises(ContractValidationError, match="evidence_range がdisplay_clip"):
        validator.validate_ai_output(output, round_package=package, candidate_rule_ids={"AIM-02"})


def test_non_finite_numbers_are_rejected_at_each_validation_entry() -> None:
    validator = SchemaValidator()

    package = load_case("TC-006")
    package["events"][0]["confidence"] = float("nan")  # type: ignore[index]
    with pytest.raises(ContractValidationError, match="有限値"):
        validator.validate_round_package(package)

    package = load_case("TC-006")
    package["deterministic_facts"][0]["confidence"] = float("inf")  # type: ignore[index]
    with pytest.raises(ContractValidationError, match="有限値"):
        validator.validate_round_package(package)

    package = load_case("TC-006")
    output = valid_output()
    output["evaluations"][0]["confidence"] = float("nan")  # type: ignore[index]
    with pytest.raises(ContractValidationError, match="有限値"):
        validator.validate_ai_output(output, round_package=package)

    assertions = json.loads(
        (ROOT / "tests" / "cases" / "TC-006" / "expected_assertions.json").read_text(
            encoding="utf-8"
        )
    )
    assertions["expected_evaluations"][0]["confidence_range"][0] = float("inf")
    with pytest.raises(ContractValidationError, match="有限値"):
        validator.validate_assertions(assertions)


def test_unscored_cannot_have_display_clip() -> None:
    validator = SchemaValidator()
    output = valid_output()
    evaluation = output["evaluations"][0]  # type: ignore[index]
    evaluation.update(
        {
            "label": "unscored",
            "clip_id": None,
            "improvement": None,
            "missing_information": ["遮蔽情報"],
            "unscored_reason_code": "missing_required_fact",
        }
    )
    with pytest.raises(ContractValidationError, match="Schema"):
        validator.validate_ai_output(output)


def test_clip_id_must_be_safe_for_local_file_generation() -> None:
    validator = SchemaValidator()
    package = load_case("TC-006")
    output = valid_output()
    output["evaluations"][0]["clip_id"] = "../../outside"  # type: ignore[index]

    with pytest.raises(ContractValidationError, match="clip_id"):
        validator.validate_ai_output(output, round_package=package, candidate_rule_ids={"AIM-02"})


def test_fact_backed_evaluation_confidence_cannot_exceed_weakest_referenced_fact() -> None:
    validator = SchemaValidator()
    package = load_case("TC-006")
    package["deterministic_facts"][-1]["confidence"] = 0.61  # type: ignore[index]
    output = valid_output()
    output["evaluations"][0]["confidence"] = 0.62  # type: ignore[index]

    with pytest.raises(ContractValidationError, match="参照factの最小confidence"):
        validator.validate_ai_output(output, round_package=package, candidate_rule_ids={"AIM-02"})


def test_frame_only_evaluation_without_fact_refs_is_not_fact_confidence_capped() -> None:
    validator = SchemaValidator()
    package = load_case("TC-006")
    output = valid_output()
    evaluation = output["evaluations"][0]  # type: ignore[index]
    evaluation["fact_refs"] = []
    evaluation["confidence"] = 0.99

    validator.validate_ai_output(output, round_package=package, candidate_rule_ids={"AIM-02"})
