from __future__ import annotations

from copy import deepcopy
from typing import Any


class EvaluationAggregator:
    def __init__(self, rule_config: dict[str, Any], trigger_registry: dict[str, Any]):
        self.rules = {item["id"]: item for item in rule_config["rules"]}
        self.groups = trigger_registry.get("dedup_groups", {})

    def aggregate(self, evaluations: list[dict[str, Any]]) -> list[dict[str, Any]]:
        ordered = sorted(
            (deepcopy(item) for item in evaluations),
            key=lambda item: (self._time(item), -float(item.get("confidence", 0))),
        )
        kept: list[dict[str, Any]] = []
        for item in ordered:
            policy = self.rules.get(item["primary_rule_id"], {}).get("aggregation_policy", {})
            window = float(policy.get("deduplicate_same_rule_within_seconds", 0))
            duplicate = next(
                (
                    existing
                    for existing in kept
                    if existing["primary_rule_id"] == item["primary_rule_id"]
                    and existing.get("label") == item.get("label")
                    and existing.get("_aggregation_scope") == item.get("_aggregation_scope")
                    and abs(self._time(existing) - self._time(item)) <= window
                ),
                None,
            )
            if duplicate:
                self._merge_same_label(duplicate, item)
                if float(item["confidence"]) > float(duplicate["confidence"]):
                    replacement = item
                    self._merge_same_label(replacement, duplicate)
                    kept[kept.index(duplicate)] = replacement
                continue
            kept.append(item)
        for group in self.groups.values():
            members = set(group["members"])
            order = {rule_id: index for index, rule_id in enumerate(group["primary_order"])}
            merge_keys = list(
                dict.fromkeys(
                    (item.get("_aggregation_scope"), item.get("label"))
                    for item in kept
                    if item["primary_rule_id"] in members
                )
            )
            for scope, label in merge_keys:
                present = [
                    item
                    for item in kept
                    if item["primary_rule_id"] in members and item.get("label") == label
                    and item.get("_aggregation_scope") == scope
                ]
                removed_ids: set[int] = set()
                while present:
                    seed = present.pop(0)
                    if id(seed) in removed_ids:
                        continue
                    same_scene = [
                        item
                        for item in present
                        if id(item) not in removed_ids
                        and (
                            self._same_scene(seed, item)
                            or self._same_unscored_basis(seed, item)
                        )
                    ]
                    if not same_scene:
                        continue
                    cluster = [seed, *same_scene]
                    primary = min(
                        cluster,
                        key=lambda item: order.get(item["primary_rule_id"], len(order)),
                    )
                    for item in cluster:
                        if item is primary:
                            continue
                        self._merge_same_label(primary, item)
                        related = list(primary.get("related_rule_ids", []))
                        related_ids = [item["primary_rule_id"], *item.get("related_rule_ids", [])]
                        for related_id in related_ids:
                            if (
                                related_id != primary["primary_rule_id"]
                                and related_id not in related
                                and len(related) < 2
                            ):
                                related.append(related_id)
                        primary["related_rule_ids"] = related
                        removed_ids.add(id(item))
                if removed_ids:
                    kept = [item for item in kept if id(item) not in removed_ids]
        limits: dict[str, int] = {}
        result: list[dict[str, Any]] = []
        for item in kept:
            rule_id = item["primary_rule_id"]
            maximum = int(
                self.rules.get(rule_id, {})
                .get("aggregation_policy", {})
                .get("max_display_exemplars_per_match", 3)
            )
            if limits.get(rule_id, 0) >= maximum:
                continue
            limits[rule_id] = limits.get(rule_id, 0) + 1
            result.append(item)
        return result

    @staticmethod
    def _merge_same_label(target: dict[str, Any], source: dict[str, Any]) -> None:
        """Retain supporting references when two same-label examples are combined."""
        fact_refs = list(target.get("fact_refs", []))
        for fact_ref in source.get("fact_refs", []):
            if fact_ref not in fact_refs:
                fact_refs.append(fact_ref)
        if fact_refs:
            target["fact_refs"] = fact_refs

        evidence_range = target.get("evidence_range") or {}
        start = float(evidence_range.get("start_sec", float("-inf")))
        end = float(evidence_range.get("end_sec", float("inf")))
        evidence = list(target.get("evidence", []))
        for item in source.get("evidence", []):
            timestamp = float(item.get("time_sec", float("nan")))
            if start <= timestamp <= end and item not in evidence and len(evidence) < 8:
                evidence.append(item)
        if evidence:
            target["evidence"] = evidence

        missing = list(target.get("missing_information", []))
        for item in source.get("missing_information", []):
            if item not in missing:
                missing.append(item)
        if missing:
            target["missing_information"] = missing

    @staticmethod
    def _same_unscored_basis(first: dict[str, Any], second: dict[str, Any]) -> bool:
        if first.get("label") != "unscored" or second.get("label") != "unscored":
            return False
        reason = first.get("unscored_reason_code")
        if reason is None or reason != second.get("unscored_reason_code"):
            return False
        first_refs = tuple(sorted(str(value) for value in first.get("fact_refs", [])))
        second_refs = tuple(sorted(str(value) for value in second.get("fact_refs", [])))
        return bool(first_refs) and first_refs == second_refs

    @staticmethod
    def _time(item: dict[str, Any]) -> float:
        evidence_range = item.get("evidence_range") or {}
        return float(evidence_range.get("start_sec", 0))

    @staticmethod
    def _same_scene(first: dict[str, Any], second: dict[str, Any]) -> bool:
        first_range = first.get("evidence_range") or first.get("display_clip") or {}
        second_range = second.get("evidence_range") or second.get("display_clip") or {}
        if not first_range or not second_range:
            return False
        first_start = float(first_range.get("start_sec", 0))
        first_end = float(first_range.get("end_sec", first_start))
        second_start = float(second_range.get("start_sec", 0))
        second_end = float(second_range.get("end_sec", second_start))
        return max(first_start, second_start) <= min(first_end, second_end) + 0.5
