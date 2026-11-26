from __future__ import annotations

import json
from pathlib import Path

from valorant_ai_coach.facts import FactBuilder
from valorant_ai_coach.rules import RuleSelector

ROOT = Path(__file__).resolve().parents[2]
REGISTRY = ROOT / "config" / "rule_trigger_registry_v2.json"


def package(case_id: str) -> dict:
    path = ROOT / "tests" / "cases" / case_id / "input.json"
    raw = json.loads(path.read_text(encoding="utf-8"))
    return FactBuilder().enrich(raw)


def test_missing_policy_allow_unscored_keeps_candidate() -> None:
    selected = {
        candidate.rule_id: candidate
        for candidate in RuleSelector(REGISTRY).select(package("TC-038"))
    }
    assert "POS-01" in selected
    assert selected["POS-01"].missing_fact_keys == ("spatial_context_available",)


def test_missing_policy_exclude_and_role_gate() -> None:
    selector = RuleSelector(REGISTRY)
    assert "ROLE-06" in selector.select_ids(package("TC-030"))
    assert "ROLE-06" not in selector.select_ids(package("TC-031"))
    assert "ROLE-02" in selector.select_ids(package("TC-035"))
    assert "ROLE-02" not in selector.select_ids(package("TC-036"))


def test_evaluable_candidates_first_then_priority_order() -> None:
    candidates = RuleSelector(REGISTRY).select(package("TC-029"))
    ranks = {"mvp_required": 0, "important": 1, "additional": 2}
    keys = [(bool(item.missing_fact_keys), ranks[item.priority]) for item in candidates]
    assert keys == sorted(keys)
    assert {"AIM-02", "DEC-01"}.issubset({item.rule_id for item in candidates})


def _rule(priority: str, gate: str | None = None) -> dict:
    predicates = (
        [{"fact_key": gate, "op": "exists", "missing_policy": "allow_unscored"}] if gate else []
    )
    return {
        "trigger_event_types": ["shot"],
        "required_state_predicates": predicates,
        "supporting_fact_keys": [],
        "priority": priority,
        "temporal_level": "micro",
        "label_mode": "llm_contextual",
    }


def test_candidates_are_not_capped_and_missing_facts_do_not_push_out_evaluable_ones() -> None:
    # 14 mvp rules that miss a fact and 3 lower-priority rules that can be judged.
    rules = {f"M-{n:02d}": _rule("mvp_required", gate="absent_fact") for n in range(14)}
    rules |= {f"E-{n:02d}": _rule("additional") for n in range(3)}
    selector = RuleSelector({"display": {"max_rules_per_round": 12}, "rules": rules})
    candidates = selector.select(
        {"events": [{"type": "shot"}], "deterministic_facts": []}
    )
    assert len(candidates) == 17  # the display limit does not cut candidates
    assert [c.rule_id for c in candidates[:3]] == ["E-00", "E-01", "E-02"]
    assert all(c.missing_fact_keys == ("absent_fact",) for c in candidates[3:])
    assert selector.display_limit == 12


def test_normal_round_has_no_trigger_fallback_noise() -> None:
    # round_start/state_snapshot are deliberately non-action events.
    assert RuleSelector(REGISTRY).select_ids(package("TC-037")) == []


def test_unmatched_action_does_not_receive_arbitrary_mvp_fallback() -> None:
    selector = RuleSelector(
        {
            "rules": {
                "AIM-02": {
                    "trigger_event_types": ["shot"],
                    "required_state_predicates": [],
                    "supporting_fact_keys": [],
                    "priority": "mvp_required",
                    "temporal_level": "micro",
                    "label_mode": "deterministic_if_confident_else_llm",
                }
            },
        }
    )

    assert selector.select_ids(
        {"events": [{"type": "movement_state"}], "deterministic_facts": []}
    ) == []
