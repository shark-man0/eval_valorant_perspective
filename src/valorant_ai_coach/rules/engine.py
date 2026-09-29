from __future__ import annotations

import json
import math
from collections import defaultdict
from collections.abc import Iterable
from pathlib import Path
from typing import Any, Literal

from valorant_ai_coach.models import DeterministicFact, RuleDecision
from valorant_ai_coach.resources import resource_path


class DeterministicRuleEngine:
    """Final-label only the human-authored explicit binary/numeric policies."""

    minimum_confidence = 0.90

    def __init__(self, contract: Path | dict[str, Any] | None = None) -> None:
        source = (
            resource_path("config/deterministic_rule_engine_v1.json")
            if contract is None
            else contract
        )
        self.contract = (
            json.loads(source.read_text(encoding="utf-8")) if isinstance(source, Path) else source
        )
        if not isinstance(self.contract.get("fact_catalog"), dict):
            raise ValueError("Deterministic Rule Engine契約にfact_catalogがありません")
        if not isinstance(self.contract.get("deterministic_label_policy"), dict):
            raise ValueError("Deterministic Rule Engine契約にlabel policyがありません")
        self.contract_version = str(self.contract.get("version", "unknown"))
        self.fact_catalog = set(self.contract["fact_catalog"])

    def evaluate(
        self,
        rule_id: str,
        facts: Iterable[DeterministicFact | dict[str, Any]],
        events: list[dict[str, Any]],
    ) -> RuleDecision | None:
        by_key: dict[str, list[DeterministicFact | dict[str, Any]]] = defaultdict(list)
        for fact in facts:
            by_key[self._get(fact, "key")].append(fact)
        if rule_id == "AIM-02":
            self._require_catalog_key("preaim_lead_sec")
            return self._threshold(
                rule_id, by_key.get("preaim_lead_sec", []), 0.5, "gte", "約0.5秒前のプリエイム"
            )
        if rule_id == "AIM-03":
            self._require_catalog_key("first_shot_stationary")
            return self._boolean(
                rule_id, by_key.get("first_shot_stationary", []), "初弾時の完全停止"
            )
        if rule_id == "MOV-02":
            self._require_catalog_key("first_shot_stationary")
            facts_for_rule = by_key.get("first_shot_stationary", [])
            if self._smoke_suppression(events, facts_for_rule):
                return None
            return self._boolean(
                rule_id, facts_for_rule, "初弾時の完全停止"
            )
        if rule_id == "PEEK-04":
            self._require_catalog_key("exposed_directions_count")
            facts_for_rule = self._confident(by_key.get("exposed_directions_count", []))
            if not facts_for_rule:
                return None
            values = [self._number(self._get(item, "value")) for item in facts_for_rule]
            if any(value is None for value in values):
                return None
            crossed = [value >= 3 for value in values if value is not None]
            if not crossed or not all(crossed):
                return None
            confidence = min(float(self._get(item, "confidence")) for item in facts_for_rule)
            return RuleDecision(
                rule_id,
                "improve",
                "deterministic",
                confidence,
                self._fact_refs(facts_for_rule),
                "3方向以上への同時露出が観測されました",
            )
        return None

    def _require_catalog_key(self, key: str) -> None:
        if key not in self.fact_catalog:
            raise ValueError(f"正本Fact catalogに必要なkeyがありません: {key}")

    def _boolean(self, rule_id: str, facts: list[Any], reason: str) -> RuleDecision | None:
        confident = self._confident(facts)
        if not confident:
            return None
        values = [self._get(item, "value") for item in confident]
        if any(value is not True and value is not False for value in values):
            return None
        labels: list[Literal["good", "improve"]] = [
            "good" if value is True else "improve" for value in values
        ]
        if len(set(labels)) != 1:
            return None
        return RuleDecision(
            rule_id,
            labels[0],
            "deterministic",
            min(float(self._get(item, "confidence")) for item in confident),
            self._fact_refs(confident),
            reason,
        )

    def _threshold(
        self, rule_id: str, facts: list[Any], threshold: float, operator: str, reason: str
    ) -> RuleDecision | None:
        confident = self._confident(facts)
        if not confident:
            return None
        values = [self._number(self._get(item, "value")) for item in confident]
        if any(value is None for value in values):
            return None
        passed = [
            value >= threshold if operator == "gte" else value <= threshold
            for value in values
            if value is not None
        ]
        if len(set(passed)) != 1:
            return None
        label: Literal["good", "improve"] = "good" if passed[0] else "improve"
        return RuleDecision(
            rule_id,
            label,
            "deterministic",
            min(float(self._get(item, "confidence")) for item in confident),
            self._fact_refs(confident),
            reason,
        )

    def _confident(self, facts: list[Any]) -> list[Any]:
        return [
            fact
            for fact in facts
            if self._confidence(fact) >= self.minimum_confidence
        ]

    @staticmethod
    def _smoke_suppression(events: list[dict[str, Any]], facts: list[Any]) -> bool:
        linked_event_ids = {
            str(event_id)
            for fact in facts
            for event_id in DeterministicRuleEngine._get(fact, "provenance_event_ids") or ()
        }
        return any(
            event.get("type") == "shot"
            and str(event.get("event_id")) in linked_event_ids
            and "smoke" in str(event.get("attributes", {}).get("purpose", "")).lower()
            for event in events
        )

    @staticmethod
    def _number(value: Any) -> float | None:
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            return None
        number = float(value)
        return number if math.isfinite(number) else None

    @staticmethod
    def _confidence(fact: Any) -> float:
        try:
            value = float(DeterministicRuleEngine._get(fact, "confidence"))
        except (TypeError, ValueError):
            return float("-inf")
        return value if math.isfinite(value) else float("-inf")

    @staticmethod
    def _fact_refs(facts: list[Any]) -> tuple[str, ...]:
        refs: list[str] = []
        for fact in facts:
            fact_id = str(DeterministicRuleEngine._get(fact, "fact_id"))
            if fact_id not in refs:
                refs.append(fact_id)
        return tuple(refs)

    @staticmethod
    def _get(fact: DeterministicFact | dict[str, Any], key: str) -> Any:
        return fact.get(key) if isinstance(fact, dict) else getattr(fact, key)
