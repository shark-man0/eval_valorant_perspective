"""Temporal / aggregation policy contract (audit of the rules JSON vs. the runtime).

Everything here follows from the rules JSON and the existing runtime. Nothing assigns a
new meaning to a policy value: the tolerance table, ``event_window_seconds`` and the
clip strategy stay separate concepts.
"""

from __future__ import annotations

import importlib.util
import json
import math
import re
from copy import deepcopy
from pathlib import Path
from typing import Any

import pytest
from match_fixtures import REGISTRY_PATH, RULES_PATH, case_package, registry, rules_config

from valorant_ai_coach.models import RuleCandidate
from valorant_ai_coach.rules import TemporalScopeResolver
from valorant_ai_coach.rules.temporal_contract import (
    ROUND_TIMELINE_COMPLETE,
    ROUND_TIMELINE_PARTIAL,
    ROUND_TIMELINE_UNAVAILABLE,
    ROUND_TIMELINE_UNKNOWN,
    TIME_SCOPE_EVENT_WINDOWS,
    TIME_SCOPE_UNKNOWN,
    TIME_SCOPE_WHOLE_ROUND_BY_POLICY,
    TIME_SCOPE_WHOLE_ROUND_FALLBACK,
    WHOLE_ROUND_LEVELS,
    RuleTemporalPolicy,
    TemporalPolicyTable,
    assess_context,
    round_timeline_status,
)
from valorant_ai_coach.rules.temporal_scope import (
    AnalysisScope,
    previous_round_context_missing,
)
from valorant_ai_coach.schema_validation import ContractValidationError

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src" / "valorant_ai_coach"
AUDIT_DOC = ROOT / "docs" / "temporal_policy_contract_audit.md"


def rule_by_id(rule_id: str) -> dict[str, Any]:
    return next(rule for rule in rules_config()["rules"] if rule["id"] == rule_id)


def candidate(rule_id: str, level: str, matched: tuple[str, ...] = ()) -> RuleCandidate:
    return RuleCandidate(rule_id, "important", level, "deterministic", matched_event_types=matched)


# ------------------------------------------------------------------ the 44-rule table


def test_table_holds_all_44_rules_sorted_and_aligned_with_the_trigger_registry() -> None:
    table = TemporalPolicyTable.load()
    assert len(table) == 44
    assert list(table.rule_ids) == sorted(table.rule_ids)
    assert set(table.rule_ids) == {rule["id"] for rule in rules_config()["rules"]}
    table.validate_registry_alignment(registry()["rules"])  # no exception


def test_registry_alignment_detects_level_and_membership_drift() -> None:
    table = TemporalPolicyTable.load()
    drifted = deepcopy(registry()["rules"])
    drifted["AIM-01"]["temporal_level"] = "micro"
    with pytest.raises(ContractValidationError, match="AIM-01.*levelが不一致"):
        table.validate_registry_alignment(drifted)
    removed = deepcopy(registry()["rules"])
    del removed["MOV-02"]
    with pytest.raises(ContractValidationError, match="registryにないルール.*MOV-02"):
        table.validate_registry_alignment(removed)
    extra = deepcopy(registry()["rules"])
    extra["ZZZ-99"] = deepcopy(extra["AIM-01"])
    with pytest.raises(ContractValidationError, match="ルール設定にないregistryルール.*ZZZ-99"):
        table.validate_registry_alignment(extra)


def test_the_two_level_sources_agree_for_every_rule() -> None:
    """Resolver reads rules JSON, FramePlanner reads the registry: they must not differ."""
    registry_rules = json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))["rules"]
    for rule in rules_config()["rules"]:
        level = rule["temporal_context"]["level_code"]
        assert registry_rules[rule["id"]]["temporal_level"] == level, rule["id"]
        assert rule["trigger"]["temporal_level"] == level, rule["id"]


def test_final_label_mode_in_automation_policy_matches_the_registry_label_mode() -> None:
    """The registry's label_mode is what runtime reads; automation_policy must not diverge."""
    registry_rules = registry()["rules"]
    for policy in TemporalPolicyTable.load():
        assert registry_rules[policy.rule_id]["label_mode"] == policy.final_label_mode


def test_per_rule_test_tolerance_equals_the_global_policy_for_its_level() -> None:
    """A data-consistency check only: it does NOT make these the resolver's 0.05 s."""
    config = rules_config()
    table = config["temporal_tolerance_policy"]
    for rule in config["rules"]:
        level = rule["temporal_context"]["level_code"]
        assert rule["test_tolerance_seconds"] == table[level], rule["id"]
    assert set(table) == {"micro", "local", "phase", "round", "cross_round", "match"}


def test_whole_match_aggregation_flag_is_not_the_same_fact_as_match_level() -> None:
    table = TemporalPolicyTable.load()
    whole = {p.rule_id for p in table if p.uses_whole_match_aggregation}
    assert whole == {"AIM-01", "AIM-02", "AIM-03", "AIM-04", "MOV-01", "MOV-02"}
    assert {p.rule_id for p in table if p.level == "match"} == {"AIM-01"}
    for rule_id in whole - {"AIM-01"}:
        policy = table.get(rule_id)
        assert policy is not None and policy.level == "micro" and policy.event_window is not None
        assert policy.needs_match_context  # aggregated over the match, judged per event window
    assert {p.rule_id for p in table if p.needs_match_context} == whole


def test_rules_needing_previous_round_context_are_exactly_the_economy_rules() -> None:
    table = TemporalPolicyTable.load()
    needing = {p.rule_id for p in table if p.requires_previous_round_context}
    assert needing == {"ECO-01", "ECO-02", "ADV-07"}
    assert all(table.get(rule_id).level == "cross_round" for rule_id in needing)  # type: ignore[union-attr]


def test_whole_round_levels_have_no_event_window_and_windowed_rules_are_micro_or_local() -> None:
    table = TemporalPolicyTable.load()
    for policy in table:
        if policy.level in WHOLE_ROUND_LEVELS:
            assert policy.event_window is None, policy.rule_id
        if policy.event_window is not None:
            assert policy.level in {"micro", "local"}, policy.rule_id
            assert policy.event_window.before_sec + policy.event_window.after_sec > 0


def test_rows_are_json_safe_deterministic_and_keep_natural_language_verbatim() -> None:
    config = {rule["id"]: rule for rule in rules_config()["rules"]}
    first, second = TemporalPolicyTable.load().to_rows(), TemporalPolicyTable.load().to_rows()
    assert json.dumps(first, allow_nan=False) == json.dumps(second, allow_nan=False)
    for row in first:
        source = config[row["rule_id"]]["temporal_context"]
        assert row["display_clip_strategy"] == source["display_clip_strategy"]  # never seconds
        wanted = source["event_window_seconds"]
        assert row["event_window_seconds"] == wanted
        assert "tolerance" not in json.dumps(row)  # separate concept, not mixed in


# ------------------------------------------------------------- policy shape validation


def policy_from(mutate: Any) -> RuleTemporalPolicy:
    rule = deepcopy(rule_by_id("AIM-02"))
    mutate(rule)
    return RuleTemporalPolicy.from_rule(rule)


@pytest.mark.parametrize(
    ("mutate", "message"),
    [
        (lambda r: r.pop("id"), "idがありません"),
        (lambda r: r.pop("temporal_context"), "temporal_context はobject"),
        (lambda r: r["temporal_context"].update(level_code="galaxy"), "level_code が不正"),
        (lambda r: r["temporal_context"].update(level_code=None), "level_code が不正"),
        (lambda r: r["temporal_context"].update(requires_round_timeline="yes"), "bool"),
        (lambda r: r["temporal_context"].update(uses_whole_match_aggregation=1), "bool"),
        (lambda r: r["temporal_context"].update(requires_previous_round_context=None), "bool"),
        (lambda r: r["temporal_context"].update(display_clip_strategy=""), "空でない文字列"),
        (lambda r: r["temporal_context"].update(display_clip_strategy=12), "空でない文字列"),
        (
            lambda r: r["temporal_context"].update(event_window_seconds={"before": -1, "after": 4}),
            "0以上",
        ),
        (
            lambda r: r["temporal_context"].update(event_window_seconds={"before": 0, "after": 0}),
            "幅が0",
        ),
        (
            lambda r: r["temporal_context"].update(
                event_window_seconds={"before": math.nan, "after": 4}
            ),
            "有限",
        ),
        (
            lambda r: r["temporal_context"].update(
                event_window_seconds={"before": math.inf, "after": 4}
            ),
            "有限",
        ),
        (
            lambda r: r["temporal_context"].update(
                event_window_seconds={"before": True, "after": 4}
            ),
            "有限",
        ),
        (lambda r: r["temporal_context"].update(event_window_seconds=[6, 4]), "nullまたはobject"),
        (lambda r: r.pop("automation_policy"), "automation_policy"),
        (lambda r: r["automation_policy"].pop("final_label_mode"), "final_label_mode"),
        (lambda r: r.pop("aggregation_policy"), "aggregation_policy"),
        (
            lambda r: r["aggregation_policy"].update(deduplicate_same_rule_within_seconds=-1),
            "0以上の有限値",
        ),
        (
            lambda r: r["aggregation_policy"].update(
                deduplicate_same_rule_within_seconds=math.nan
            ),
            "0以上の有限値",
        ),
        (
            lambda r: r["aggregation_policy"].update(max_display_exemplars_per_match=0),
            "1以上の整数",
        ),
        (
            lambda r: r["aggregation_policy"].update(max_display_exemplars_per_match=True),
            "1以上の整数",
        ),
        (
            lambda r: r["aggregation_policy"].update(summary_required_if_occurrences_at_least=0),
            "nullまたは1以上",
        ),
        (
            lambda r: r["aggregation_policy"].update(aggregate_repeated_occurrences="true"),
            "bool",
        ),
    ],
)
def test_malformed_policy_values_are_rejected_with_the_rule_id(mutate: Any, message: str) -> None:
    with pytest.raises(ContractValidationError, match=message) as caught:
        policy_from(mutate)
    if "idがありません" not in message:
        assert str(caught.value).startswith("AIM-02:")


@pytest.mark.parametrize("level", sorted(WHOLE_ROUND_LEVELS))
def test_whole_round_level_cannot_declare_an_event_window(level: str) -> None:
    def add(rule: dict[str, Any]) -> None:
        rule["temporal_context"].update(
            level_code=level, event_window_seconds={"before": 6, "after": 4}
        )

    with pytest.raises(ContractValidationError, match="ラウンド全体を見る"):
        policy_from(add)


def test_duplicate_rule_ids_are_rejected_and_unknown_ids_are_absent() -> None:
    one = policy_from(lambda rule: None)
    with pytest.raises(ContractValidationError, match="重複"):
        TemporalPolicyTable([one, one])
    table = TemporalPolicyTable([one])
    assert table.get("AIM-99") is None and "AIM-99" not in table and "AIM-02" in table


def test_table_from_config_requires_a_rules_array() -> None:
    with pytest.raises(ContractValidationError, match="rules配列"):
        TemporalPolicyTable.from_config({"rules": {}})


def test_every_rule_in_the_shipped_config_passes_shape_validation() -> None:
    for rule in rules_config()["rules"]:
        RuleTemporalPolicy.from_rule(rule)  # no exception


# -------------------------------------------------- previous_round_context: one meaning


@pytest.mark.parametrize(
    ("value", "missing"),
    [
        ("absent", True),
        (None, True),
        ({}, True),
        ([], True),
        ({"previous_round_result": "loss"}, False),
    ],
)
def test_previous_round_context_missing_is_one_definition_for_every_consumer(
    value: Any, missing: bool
) -> None:
    package = case_package("TC-012", round_no=1)
    if value == "absent":
        package.pop("previous_round_context", None)
    else:
        package["previous_round_context"] = value
    assert previous_round_context_missing(package) is missing
    resolver = TemporalScopeResolver()
    scope = resolver.resolve(candidate("ECO-01", "cross_round"), package)
    assert (scope.missing_context == ("previous_round_context",)) is missing
    policy = TemporalPolicyTable.load().get("ECO-01")
    assert policy is not None
    assessment = assess_context(policy, package, scope)
    assert assessment.missing_context == scope.missing_context


def test_rule_that_does_not_need_previous_round_context_never_reports_it_missing() -> None:
    package = case_package("TC-006", round_no=1)
    package["previous_round_context"] = None
    policy = TemporalPolicyTable.load().get("AIM-02")
    assert policy is not None
    assert assess_context(policy, package).missing_context == ()
    scope = TemporalScopeResolver().resolve(candidate("AIM-02", "micro"), package)
    assert scope.missing_context == ()


# ----------------------------------------------------------------- scope invariants


def test_pivot_events_outside_the_round_window_never_create_a_window() -> None:
    package = case_package("TC-006", round_no=1)
    start, end = package["round_window"]["start_sec"], package["round_window"]["end_sec"]
    for event in package["events"]:
        event["time_sec"] = end + 500.0 if event["type"] == "peek" else event["time_sec"]
    scope = TemporalScopeResolver().resolve(candidate("AIM-02", "micro", ("peek",)), package)
    for low, high in scope.windows:
        assert start <= low < high <= end
    assert scope.whole_round  # only out-of-round pivots matched: nothing to pin the time to


def test_windows_never_leave_the_round_even_when_the_pivot_sits_on_the_boundary() -> None:
    package = case_package("TC-006", round_no=1)
    start, end = package["round_window"]["start_sec"], package["round_window"]["end_sec"]
    package["events"].append(
        {
            "event_id": "EDGE-1",
            "time_sec": start,
            "type": "peek",
            "actor": "player",
            "attributes": {},
            "confidence": 0.9,
        }
    )
    scope = TemporalScopeResolver().resolve(candidate("AIM-02", "micro", ("peek",)), package)
    assert all(start <= low and high <= end for low, high in scope.windows)


def test_scope_does_not_depend_on_event_order_and_never_mutates_the_package() -> None:
    package = case_package("TC-006", round_no=1)
    before = deepcopy(package)
    resolver = TemporalScopeResolver()
    forward = resolver.resolve(candidate("AIM-02", "micro", ("preaim_started", "peek")), package)
    shuffled = deepcopy(package)
    shuffled["events"] = list(reversed(shuffled["events"]))
    backward = resolver.resolve(candidate("AIM-02", "micro", ("preaim_started", "peek")), shuffled)
    assert forward == backward
    assert package == before


def test_a_rule_unknown_to_the_config_gets_the_whole_round_and_no_invented_window() -> None:
    package = case_package("TC-006", round_no=1)
    scope = TemporalScopeResolver({}).resolve(candidate("ZZZ-99", "micro", ("peek",)), package)
    assert scope.whole_round and scope.windows == () and scope.level == "micro"
    assert scope.missing_context == ()


def test_the_configured_level_wins_over_the_candidates_level() -> None:
    package = case_package("TC-006", round_no=1)
    scope = TemporalScopeResolver().resolve(candidate("AIM-02", "round", ("peek",)), package)
    assert scope.level == "micro"  # level_code from the rules JSON


def test_scope_containment_uses_the_existing_0_05_second_slack_and_nothing_wider() -> None:
    scope = AnalysisScope("X", "micro", windows=((10.0, 20.0),), whole_round=False)
    assert scope.contains(10.0, 20.0)
    assert scope.contains(9.95, 20.05)
    assert not scope.contains(9.94, 20.0)
    assert not scope.contains(10.0, 20.06)
    # temporal_tolerance_policy.micro.evidence_sec (0.75) is a different concept
    assert not scope.contains(9.3, 20.0)


# ------------------------------------------------------------ assess_context contract


def make_scope(rule_id: str, *, whole_round: bool, windows: tuple[Any, ...] = ()) -> AnalysisScope:
    return AnalysisScope(rule_id, "x", windows=windows, whole_round=whole_round)


def test_time_scope_distinguishes_pinned_policy_whole_round_and_fallback() -> None:
    package = case_package("TC-006", round_no=1)
    table = TemporalPolicyTable.load()
    windowed, whole = table.get("AIM-02"), table.get("DEC-01")
    assert windowed is not None and whole is not None and whole.event_window is None
    pinned_scope = make_scope("AIM-02", whole_round=False, windows=((1.0, 2.0),))
    pinned = assess_context(windowed, package, pinned_scope)
    assert pinned.time_scope == TIME_SCOPE_EVENT_WINDOWS
    fallback = assess_context(windowed, package, make_scope("AIM-02", whole_round=True))
    assert fallback.time_scope == TIME_SCOPE_WHOLE_ROUND_FALLBACK
    by_policy = assess_context(whole, package, make_scope("DEC-01", whole_round=True))
    assert by_policy.time_scope == TIME_SCOPE_WHOLE_ROUND_BY_POLICY
    assert assess_context(windowed, package).time_scope == TIME_SCOPE_UNKNOWN


@pytest.mark.parametrize(
    ("quality", "expected"),
    [
        (None, ROUND_TIMELINE_UNKNOWN),
        ("good", ROUND_TIMELINE_UNKNOWN),
        ({}, ROUND_TIMELINE_UNKNOWN),
        ({"timeline_completeness": 1.0}, ROUND_TIMELINE_UNKNOWN),
        ({"missing_intervals": []}, ROUND_TIMELINE_UNKNOWN),
        ({"timeline_completeness": 1.0, "missing_intervals": None}, ROUND_TIMELINE_UNKNOWN),
        ({"timeline_completeness": None, "missing_intervals": []}, ROUND_TIMELINE_UNKNOWN),
        ({"timeline_completeness": True, "missing_intervals": []}, ROUND_TIMELINE_UNKNOWN),
        ({"timeline_completeness": "1.0", "missing_intervals": []}, ROUND_TIMELINE_UNKNOWN),
        ({"timeline_completeness": math.nan, "missing_intervals": []}, ROUND_TIMELINE_UNKNOWN),
        ({"timeline_completeness": math.inf, "missing_intervals": []}, ROUND_TIMELINE_UNKNOWN),
        ({"timeline_completeness": 0.0, "missing_intervals": []}, ROUND_TIMELINE_UNAVAILABLE),
        ({"timeline_completeness": 0, "missing_intervals": []}, ROUND_TIMELINE_UNAVAILABLE),
        ({"timeline_completeness": 0.4, "missing_intervals": []}, ROUND_TIMELINE_PARTIAL),
        ({"timeline_completeness": 0.999, "missing_intervals": []}, ROUND_TIMELINE_PARTIAL),
        (
            {"timeline_completeness": 1.0, "missing_intervals": [{"start_sec": 1, "end_sec": 2}]},
            ROUND_TIMELINE_PARTIAL,
        ),
        ({"timeline_completeness": 1.0, "missing_intervals": []}, ROUND_TIMELINE_COMPLETE),
    ],
)
def test_round_timeline_status_never_guesses_from_missing_or_malformed_data(
    quality: Any, expected: str
) -> None:
    assert round_timeline_status({"observation_quality": quality}) == expected


def test_a_package_without_observation_quality_is_unknown_not_complete() -> None:
    assert round_timeline_status({}) == ROUND_TIMELINE_UNKNOWN


def test_timeline_shortfall_is_reported_only_for_rules_that_require_the_timeline() -> None:
    package = case_package("TC-006", round_no=1)
    package["observation_quality"]["timeline_completeness"] = 0.5
    table = TemporalPolicyTable.load()
    needing = next(p for p in table if p.requires_round_timeline)
    free = next(p for p in table if not p.requires_round_timeline)
    assert assess_context(needing, package).round_timeline_shortfall is True
    assert assess_context(free, package).round_timeline_shortfall is False
    package["observation_quality"]["timeline_completeness"] = 1.0
    package["observation_quality"]["missing_intervals"] = []
    assert assess_context(needing, package).round_timeline_shortfall is False


def test_unknown_timeline_counts_as_a_shortfall_for_a_rule_that_requires_it() -> None:
    needing = next(p for p in TemporalPolicyTable.load() if p.requires_round_timeline)
    assert assess_context(needing, {}).round_timeline_shortfall is True


def test_assessment_is_pure_json_safe_and_carries_no_judgement() -> None:
    package = case_package("TC-012", round_no=1)
    before = deepcopy(package)
    policy = TemporalPolicyTable.load().get("ECO-01")
    assert policy is not None
    first, second = assess_context(policy, package), assess_context(policy, package)
    assert first == second and package == before
    dumped = json.dumps(first.to_dict(), allow_nan=False)
    for judgement in ("label", "score", "confidence", "verdict", "good", "improve"):
        assert judgement not in set(json.loads(dumped))


def test_requires_round_timeline_is_reported_but_never_becomes_a_scoring_gate() -> None:
    """The rules JSON does not say a short timeline must block scoring, so nothing blocks it."""
    package = case_package("TC-006", round_no=1)
    package["observation_quality"]["timeline_completeness"] = 0.2
    scope = TemporalScopeResolver().resolve(candidate("AIM-01", "match"), package)
    assert scope.missing_context == ()  # the resolver gates on previous_round_context only


# ----------------------------------------------- audit document stays tied to the code

# field -> files under src/valorant_ai_coach that read it at runtime (None = nobody).
# If one of these changes, the audit document must be updated in the same change.
RUNTIME_USERS: dict[str, set[str]] = {
    "requires_round_timeline": {"ui/backend.py"},
    "requires_previous_round_context": {"rules/temporal_scope.py"},
    "event_window_seconds": {"rules/temporal_scope.py"},
    "uses_whole_match_aggregation": set(),
    "display_clip_strategy": set(),
    "temporal_tolerance_policy": set(),
    "test_tolerance_seconds": set(),
    "automation_policy": set(),
    "candidate_selection": set(),
    "final_label_mode": set(),
    "aggregate_repeated_occurrences": set(),
    "summary_required_if_occurrences_at_least": set(),
    "deduplicate_same_rule_within_seconds": {"rules/aggregator.py"},
    "max_display_exemplars_per_match": {"rules/aggregator.py"},
    "suggested_clip_window_seconds": {"ai/coach.py"},
}
# New read-only consumers added for the Match view; they report, they do not act.
REPORT_ONLY = {"rules/temporal_contract.py", "application/match_aggregation.py"}


def test_runtime_users_of_each_policy_field_match_the_audit() -> None:
    found: dict[str, set[str]] = {field: set() for field in RUNTIME_USERS}
    for path in SRC.rglob("*.py"):
        relative = path.relative_to(SRC).as_posix()
        if relative in REPORT_ONLY:
            continue
        text = path.read_text(encoding="utf-8")
        for field in RUNTIME_USERS:
            if re.search(rf"\b{field}\b", text):
                found[field].add(relative)
    assert found == RUNTIME_USERS, (
        "ランタイムのポリシー利用状況が変わりました。docs/temporal_policy_contract_audit.md の"
        "対応表とこのテストを同時に更新してください"
    )


def test_audit_document_contains_the_current_44_rule_table() -> None:
    script = ROOT / "scripts" / "audit_temporal_policy.py"
    spec = importlib.util.spec_from_file_location("audit_temporal_policy", script)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    table_text = module.render_rule_table()
    assert table_text.count("\n") == 45  # header + divider + 44 rules
    document = AUDIT_DOC.read_text(encoding="utf-8")
    assert table_text in document, "docs/temporal_policy_contract_audit.md の表が設定と一致しません"
    assert RULES_PATH.name in document
