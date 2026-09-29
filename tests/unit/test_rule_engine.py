from __future__ import annotations

from valorant_ai_coach.models import DeterministicFact
from valorant_ai_coach.rules import DeterministicRuleEngine, EvaluationAggregator


def fact(key: str, value: object, confidence: float = 0.98) -> DeterministicFact:
    return DeterministicFact("F1", key, value, confidence, "derived_code")  # type: ignore[arg-type]


def test_only_explicit_thresholds_receive_deterministic_labels() -> None:
    engine = DeterministicRuleEngine()
    assert engine.contract_version == "1.0"
    good = engine.evaluate("AIM-02", [fact("preaim_lead_sec", 0.7)], [])
    improve = engine.evaluate("AIM-02", [fact("preaim_lead_sec", 0.3)], [])
    exposure = engine.evaluate("PEEK-04", [fact("exposed_directions_count", 3)], [])
    assert good is not None and good.label == "good"
    assert improve is not None and improve.label == "improve"
    assert exposure is not None and exposure.label == "improve"
    assert engine.evaluate("DEC-04", [fact("rotation_delay_sec", 25)], []) is None


def test_low_confidence_and_exception_prevent_deterministic_label() -> None:
    engine = DeterministicRuleEngine()
    assert engine.evaluate("MOV-02", [fact("first_shot_stationary", True, 0.89)], []) is None
    smoke_shot = [
        {"event_id": "shot-1", "type": "shot", "attributes": {"purpose": "smoke penetration"}}
    ]
    linked_fact = {
        "fact_id": "F1",
        "key": "first_shot_stationary",
        "value": True,
        "confidence": 0.98,
        "provenance_event_ids": ["shot-1"],
    }
    assert engine.evaluate("MOV-02", [linked_fact], smoke_shot) is None
    assert engine.evaluate("AIM-03", [linked_fact], smoke_shot) is not None
    unrelated_smoke = [{**smoke_shot[0], "event_id": "other-shot"}]
    assert engine.evaluate("MOV-02", [linked_fact], unrelated_smoke) is not None


def test_deterministic_labels_require_confident_occurrences_to_agree() -> None:
    engine = DeterministicRuleEngine()
    conflicting = [
        {"fact_id": "F1", "key": "first_shot_stationary", "value": True, "confidence": 0.99},
        {"fact_id": "F2", "key": "first_shot_stationary", "value": False, "confidence": 0.90},
    ]
    assert engine.evaluate("AIM-03", conflicting, []) is None

    agreeing = [
        {"fact_id": "F1", "key": "preaim_lead_sec", "value": 0.7, "confidence": 0.98},
        {"fact_id": "F2", "key": "preaim_lead_sec", "value": 0.6, "confidence": 0.94},
    ]
    decision = engine.evaluate("AIM-02", agreeing, [])
    assert decision is not None
    assert decision.label == "good"
    assert decision.fact_refs == ("F1", "F2")
    assert decision.confidence == 0.94

    conflicting_threshold = [
        {"fact_id": "F1", "key": "preaim_lead_sec", "value": 0.7, "confidence": 0.99},
        {"fact_id": "F2", "key": "preaim_lead_sec", "value": 0.3, "confidence": 0.90},
    ]
    assert engine.evaluate("AIM-02", conflicting_threshold, []) is None


def test_aggregation_deduplicates_time_and_group_members() -> None:
    rule_config = {
        "rules": [
            {
                "id": "DEC-01",
                "aggregation_policy": {
                    "deduplicate_same_rule_within_seconds": 35,
                    "max_display_exemplars_per_match": 3,
                },
            },
            {
                "id": "INFO-03",
                "aggregation_policy": {
                    "deduplicate_same_rule_within_seconds": 10,
                    "max_display_exemplars_per_match": 3,
                },
            },
        ]
    }
    registry = {
        "dedup_groups": {
            "numbers": {"members": ["DEC-01", "INFO-03"], "primary_order": ["DEC-01", "INFO-03"]}
        }
    }
    base = {"label": "improve", "confidence": 0.8, "related_rule_ids": []}
    values = [
        base | {"primary_rule_id": "DEC-01", "evidence_range": {"start_sec": 10, "end_sec": 12}},
        base
        | {
            "primary_rule_id": "DEC-01",
            "confidence": 0.9,
            "evidence_range": {"start_sec": 20, "end_sec": 22},
        },
        base | {"primary_rule_id": "INFO-03", "evidence_range": {"start_sec": 21, "end_sec": 23}},
    ]
    result = EvaluationAggregator(rule_config, registry).aggregate(values)
    assert len(result) == 1
    assert result[0]["primary_rule_id"] == "DEC-01"
    assert result[0]["confidence"] == 0.9
    assert result[0]["related_rule_ids"] == ["INFO-03"]


def test_aggregation_does_not_merge_dedup_group_across_distant_scenes() -> None:
    rule_config = {
        "rules": [
            {"id": "DEC-01", "aggregation_policy": {}},
            {"id": "INFO-03", "aggregation_policy": {}},
        ]
    }
    registry = {
        "dedup_groups": {
            "numbers": {
                "members": ["DEC-01", "INFO-03"],
                "primary_order": ["DEC-01", "INFO-03"],
            }
        }
    }
    values = [
        {
            "primary_rule_id": "DEC-01",
            "label": "improve",
            "confidence": 0.9,
            "related_rule_ids": [],
            "evidence_range": {"start_sec": 10, "end_sec": 12},
        },
        {
            "primary_rule_id": "INFO-03",
            "label": "improve",
            "confidence": 0.9,
            "related_rule_ids": [],
            "evidence_range": {"start_sec": 70, "end_sec": 72},
        },
    ]

    result = EvaluationAggregator(rule_config, registry).aggregate(values)

    assert [item["primary_rule_id"] for item in result] == ["DEC-01", "INFO-03"]


def test_aggregation_preserves_opposing_labels_in_same_scene() -> None:
    rule_config = {
        "rules": [
            {"id": "DEC-01", "aggregation_policy": {}},
            {"id": "INFO-03", "aggregation_policy": {}},
        ]
    }
    registry = {
        "dedup_groups": {
            "numbers": {
                "members": ["DEC-01", "INFO-03"],
                "primary_order": ["DEC-01", "INFO-03"],
            }
        }
    }
    common = {
        "confidence": 0.9,
        "related_rule_ids": [],
        "evidence_range": {"start_sec": 10, "end_sec": 12},
    }
    values = [
        common | {"primary_rule_id": "DEC-01", "label": "improve"},
        common | {"primary_rule_id": "INFO-03", "label": "good"},
    ]

    result = EvaluationAggregator(rule_config, registry).aggregate(values)

    assert [(item["primary_rule_id"], item["label"]) for item in result] == [
        ("DEC-01", "improve"),
        ("INFO-03", "good"),
    ]


def test_same_label_group_merge_unions_safe_references() -> None:
    rule_config = {
        "rules": [
            {"id": "DEC-01", "aggregation_policy": {}},
            {"id": "INFO-03", "aggregation_policy": {}},
        ]
    }
    registry = {
        "dedup_groups": {
            "numbers": {
                "members": ["DEC-01", "INFO-03"],
                "primary_order": ["DEC-01", "INFO-03"],
            }
        }
    }
    values = [
        {
            "primary_rule_id": "DEC-01",
            "label": "improve",
            "confidence": 0.9,
            "related_rule_ids": [],
            "fact_refs": ["F1"],
            "evidence": [{"time_sec": 11, "fact": "primary evidence", "source": "visual"}],
            "evidence_range": {"start_sec": 10, "end_sec": 12},
        },
        {
            "primary_rule_id": "INFO-03",
            "label": "improve",
            "confidence": 0.9,
            "related_rule_ids": [],
            "fact_refs": ["F2", "F1"],
            "evidence": [
                {"time_sec": 11.5, "fact": "overlapping evidence", "source": "event_log"},
                {"time_sec": 13, "fact": "out-of-range evidence", "source": "event_log"},
            ],
            "evidence_range": {"start_sec": 11, "end_sec": 14},
        },
    ]

    result = EvaluationAggregator(rule_config, registry).aggregate(values)

    assert len(result) == 1
    assert result[0]["fact_refs"] == ["F1", "F2"]
    assert [item["fact"] for item in result[0]["evidence"]] == [
        "primary evidence",
        "overlapping evidence",
    ]


def test_aggregation_never_merges_across_round_scopes() -> None:
    rule_config = {
        "rules": [
            {"id": "DEC-01", "aggregation_policy": {"deduplicate_same_rule_within_seconds": 35}},
            {"id": "INFO-03", "aggregation_policy": {}},
        ]
    }
    registry = {
        "dedup_groups": {
            "numbers": {
                "members": ["DEC-01", "INFO-03"],
                "primary_order": ["DEC-01", "INFO-03"],
            }
        }
    }
    values = [
        {
            "primary_rule_id": "DEC-01",
            "label": "improve",
            "confidence": 0.9,
            "related_rule_ids": [],
            "fact_refs": ["ROUND1"],
            "evidence_range": {"start_sec": 10, "end_sec": 12},
            "_aggregation_scope": 1,
        },
        {
            "primary_rule_id": "DEC-01",
            "label": "improve",
            "confidence": 0.9,
            "related_rule_ids": [],
            "fact_refs": ["ROUND2"],
            "evidence_range": {"start_sec": 20, "end_sec": 22},
            "_aggregation_scope": 2,
        },
        {
            "primary_rule_id": "INFO-03",
            "label": "improve",
            "confidence": 0.9,
            "related_rule_ids": [],
            "fact_refs": ["ROUND3"],
            "evidence_range": {"start_sec": 21, "end_sec": 23},
            "_aggregation_scope": 3,
        },
    ]

    result = EvaluationAggregator(rule_config, registry).aggregate(values)

    assert len(result) == 3
    assert [item["_aggregation_scope"] for item in result] == [1, 2, 3]
    assert [item["fact_refs"] for item in result] == [["ROUND1"], ["ROUND2"], ["ROUND3"]]
