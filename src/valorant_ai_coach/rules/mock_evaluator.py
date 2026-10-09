from __future__ import annotations

import json
from collections import defaultdict
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from valorant_ai_coach.facts import FactBuilder
from valorant_ai_coach.models import RuleCandidate, RuleDecision
from valorant_ai_coach.resources import resource_path

from .aggregator import EvaluationAggregator
from .engine import DeterministicRuleEngine
from .selector import RuleSelector


class MockEvaluator:
    """Deterministic demo evaluator driven exclusively by Round Package observations."""

    def __init__(
        self,
        registry_path: Path | None = None,
        rules_path: Path | None = None,
        fact_builder: FactBuilder | None = None,
    ):
        registry_path = registry_path or resource_path("config/rule_trigger_registry_v2.json")
        rules_path = rules_path or resource_path("config/valorant_evaluation_rules_v4.json")
        self.registry = json.loads(registry_path.read_text(encoding="utf-8"))
        self.rule_config = json.loads(rules_path.read_text(encoding="utf-8"))
        self.rule_defs = {item["id"]: item for item in self.rule_config["rules"]}
        self.builder = fact_builder or FactBuilder()
        self.selector = RuleSelector(self.registry)
        self.engine = DeterministicRuleEngine()
        self.aggregator = EvaluationAggregator(self.rule_config, self.registry)

    def evaluate(
        self,
        round_package: dict[str, Any],
        candidates: Sequence[RuleCandidate | str] | None = None,
    ) -> dict[str, Any]:
        package = self.builder.enrich(round_package)
        selected = self.selector.select(package) if candidates is None else candidates
        candidate_ids = {
            candidate.rule_id if isinstance(candidate, RuleCandidate) else candidate
            for candidate in selected
        }
        events = package["events"]
        facts = package["deterministic_facts"]
        by_key: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for existing_fact in facts:
            by_key[existing_fact["key"]].append(existing_fact)
        evaluations: list[dict[str, Any]] = []

        def emit(
            rule_id: str,
            label: str,
            *,
            related: list[str] | None = None,
            event: dict[str, Any] | None = None,
            decision: RuleDecision | None = None,
            missing: list[str] | None = None,
            reason_code: str | None = None,
            reason: str = "観測事実をユーザー定義基準に照合しました",
        ) -> None:
            if rule_id not in candidate_ids:
                return
            evaluations.append(
                self._evaluation(
                    package,
                    rule_id,
                    label,
                    event=event,
                    decision=decision,
                    related=related or [],
                    missing=missing or [],
                    reason_code=reason_code,
                    reason=reason,
                )
            )

        event_map: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for event in events:
            event_map[event["type"]].append(event)

        def first(kind: str) -> dict[str, Any] | None:
            return event_map[kind][0] if event_map[kind] else None

        def fact(key: str) -> Any:
            return self._last_value(by_key, key)

        # Explicit human-authored thresholds/binary rules.
        if "AIM-02" in candidate_ids and by_key.get("preaim_lead_sec"):
            decision = self.engine.evaluate("AIM-02", facts, events)
            if decision:
                emit("AIM-02", decision.label, event=first("peek"), decision=decision)
        # One fact may drive several deterministic rules (MOV-02 and AIM-03 share
        # first_shot_stationary). Like the real coach, emit every rule that has a decision.
        for rule_id in ("MOV-02", "AIM-03"):
            if rule_id in candidate_ids and by_key.get("first_shot_stationary"):
                decision = self.engine.evaluate(rule_id, facts, events)
                if decision:
                    emit(rule_id, decision.label, event=first("shot"), decision=decision)
        if "PEEK-04" in candidate_ids:
            decision = self.engine.evaluate("PEEK-04", facts, events)
            if decision:
                emit("PEEK-04", decision.label, event=first("peek"), decision=decision)

        # Contextual mock decisions. These mimic the LLM using observations, without hidden labels.
        moving_shots = [
            event
            for event in event_map["shot"]
            if event.get("attributes", {}).get("moving") is True
            and event.get("attributes", {}).get("first_shot") is not True
        ]
        if moving_shots and "MOV-01" in candidate_ids:
            shot = moving_shots[0]
            attrs = shot["attributes"]
            good_exception = attrs.get("distance_class") == "close" or (
                attrs.get("distance_class") == "medium"
                and attrs.get("weapon") in {"Spectre", "Stinger"}
            )
            emit("MOV-01", "good" if good_exception else "improve", event=shot)

        offsets = [
            event
            for event in event_map["engagement_start"]
            if isinstance(
                event.get("attributes", {}).get("crosshair_vertical_offset_head_units"),
                (int, float),
            )
        ]
        if len(offsets) >= 3 and all(
            abs(event["attributes"]["crosshair_vertical_offset_head_units"]) >= 0.5
            for event in offsets
        ):
            emit("AIM-01", "improve", event=offsets[0])

        peek = first("peek")
        tradeable = fact("tradeable_ally_nearby")
        numbers = fact("numbers_state")
        if peek and numbers == "advantage" and tradeable is False:
            attrs = peek.get("attributes", {})
            related: list[str] = []
            kill = first("kill")
            if first("preaim_started"):
                related = ["INFO-03", "PEEK-01"]
            elif kill and "killer_side" not in kill.get("attributes", {}):
                related = ["INFO-03"]
            emit("DEC-01", "improve", related=related, event=peek)
        elif numbers == "disadvantage" and tradeable is True:
            emit("DEC-02", "good", event=first("engagement_start") or first("position_change"))
        elif peek and numbers == "even" and tradeable is False:
            emit("PEEK-01", "improve", event=peek)

        if peek and peek.get("attributes", {}).get("peek_style") == "body_width_unknown":
            emit(
                "PEEK-02",
                "unscored",
                event=peek,
                missing=["相手の保持方法とピーク幅を判別できません"],
                reason_code="ambiguous_exception",
            )

        reengage = first("enemy_reengage")
        if reengage and reengage["attributes"].get("same_angle") is True:
            emit("MOV-04", "improve", event=first("enemy_reengage"))

        if numbers == "disadvantage" and tradeable is False and first("position_change"):
            emit("INFO-03", "improve", event=first("position_change"))
        elif numbers is None and first("position_change"):
            emit(
                "INFO-03",
                "unscored",
                event=first("position_change"),
                missing=["生存人数を確認できません"],
                reason_code="insufficient_hud_evidence",
            )

        if first("status_effect"):
            withdrew = bool(first("engagement_end") and first("position_change"))
            emit("DEC-03", "good" if withdrew else "improve", event=first("status_effect"))
        elif fact("disadvantageous_effect_active") is True and first("position_hold"):
            emit("DEC-03", "improve", event=first("position_hold"))

        rotation = first("rotation_started")
        if rotation and fact("enemy_spotted_count") and fact("rotation_delay_sec") is not None:
            emit("DEC-04", "improve", event=rotation)

        objective = first("objective_state")
        engagement = first("engagement_start")
        movement = first("position_change")
        if objective and engagement and engagement["attributes"].get("far_from_site"):
            emit("DEC-05", "improve", event=objective)
        elif objective and movement and movement["attributes"].get("toward_objective"):
            emit("DEC-05", "good", related=["OBJ-02"], event=objective)

        utility_count = fact("utility_available_count")
        if (
            fact("player_died") is True
            and isinstance(utility_count, (int, float))
            and utility_count > 0
        ):
            emit("UTL-01", "improve", event=first("player_death"))

        if first("ally_entry_start") and peek and tradeable is True:
            emit("TEAM-02", "good", event=peek)

        site_state = first("site_state")
        if site_state and objective and objective["attributes"].get("plant_attempt_started"):
            risk = site_state["attributes"].get("incoming_damage_risk_observed")
            emit(
                "OBJ-02",
                "improve" if risk else "good",
                related=[] if risk else ["DEC-05"],
                event=objective,
            )

        position = first("position_change")
        if fact("spike_planted") is True and position:
            attrs = position.get("attributes", {})
            if attrs.get("cover_available") is True and attrs.get("line_of_sight_to_spike") is True:
                emit("POS-04", "good", event=position)
            if (
                attrs.get("line_of_sight_to_spike") is True
                and engagement
                and engagement["attributes"].get("enemy_defuse_pressure")
            ):
                emit("OBJ-03", "good", event=position)

        buy = first("buy_phase")
        purchase = first("purchase")
        if (
            buy
            and purchase
            and buy["attributes"].get("team_plan") == "full_buy"
            and purchase["attributes"].get("weapon") in {"Sheriff", "Classic", "Ghost"}
        ):
            emit("ECO-01", "improve", event=purchase)

        save = first("save_decision")
        if save and numbers == "disadvantage" and str(fact("weapon")).lower() == "operator":
            emit("ECO-02", "good", related=["ADV-07"], event=save)

        hold = first("hold_angle")
        if (
            hold
            and hold["attributes"].get("weapon") == "Operator"
            and hold["attributes"].get("angle_type") == "long"
            and hold["attributes"].get("cover_available") is True
        ):
            emit("WPN-01", "good", event=hold)

        role = package["round_meta"].get("player_role")
        if role == "duelist" and first("ally_enter_site") and position:
            emit("ROLE-06", "good", event=position)
        utility = first("utility_used")
        if (
            role == "controller"
            and utility
            and utility["attributes"].get("ability_effect") == "smoke"
            and first("ally_entry_start")
        ):
            emit("ROLE-02", "good", related=["TEAM-02"], event=utility)

        meaningful_types = {event["type"] for event in events}
        if (
            meaningful_types == {"engagement_start"}
            and len(events) == 1
            and "POS-01" in candidate_ids
            and fact("spatial_context_available") is None
        ):
            visual = float(package["observation_quality"]["visual_confidence"])
            reason_code = (
                "insufficient_visual_evidence" if visual < 0.55 else "missing_required_fact"
            )
            emit(
                "POS-01",
                "unscored",
                event=first("engagement_start"),
                missing=["遮蔽と退路の空間情報がありません"],
                reason_code=reason_code,
            )

        return {
            "schema_version": "3.0",
            "analysis_id": f"mock-{package['match_id']}-R{package['round_no']}",
            "match_id": package["match_id"],
            "round_no": package["round_no"],
            "evaluations": self.aggregator.aggregate(evaluations),
        }

    def _evaluation(
        self,
        package: dict[str, Any],
        rule_id: str,
        label: str,
        *,
        event: dict[str, Any] | None,
        decision: RuleDecision | None,
        related: list[str],
        missing: list[str],
        reason_code: str | None,
        reason: str,
    ) -> dict[str, Any]:
        rule = self.rule_defs[rule_id]
        timestamp = float(event["time_sec"] if event else package["round_window"]["start_sec"])
        start = max(float(package["round_window"]["start_sec"]), timestamp - 5)
        end = min(float(package["round_window"]["end_sec"]), timestamp + 5)
        # Evidence is the observed moment only (same as the real coach); the wider
        # window is just the display clip. Keeping them apart lets the rule's analysis
        # scope bound the evidence without constraining the clip.
        evidence_start = max(float(package["round_window"]["start_sec"]), timestamp - 0.75)
        evidence_end = min(float(package["round_window"]["end_sec"]), timestamp + 0.75)
        scored = label in {"good", "improve"}
        if decision is not None and decision.label == "unscored":
            missing = list(decision.missing_information) or missing
            reason_code = decision.unscored_reason_code or reason_code
        fact_refs = list(decision.fact_refs) if decision else self._fact_refs(package, rule_id)
        confidence = decision.confidence if decision else self._confidence(package, event)
        if fact_refs:
            facts_by_id = {
                str(fact["fact_id"]): fact for fact in package["deterministic_facts"]
            }
            confidence = min(
                confidence,
                *(float(facts_by_id[fact_id]["confidence"]) for fact_id in fact_refs),
            )
        if label == "unscored":
            confidence = min(confidence, 0.5)
        evidence = (
            []
            if not scored
            else [
                {
                    "time_sec": timestamp,
                    "fact": f"{event['type'] if event else 'state'} が観測されました",
                    "source": "event_log" if event else "deterministic_fact",
                }
            ]
        )
        return {
            "evaluation_id": f"mock-{package['match_id']}-R{package['round_no']}-{rule_id}",
            "clip_id": (
                f"clip-{package['match_id']}-R{package['round_no']}-{rule_id}" if scored else None
            ),
            "primary_rule_id": rule_id,
            "related_rule_ids": related[:2],
            "label": label,
            "decision_source": decision.decision_source if decision else "hybrid",
            "fact_refs": fact_refs,
            "concept_tags": list(rule.get("concept_tags", [])),
            "title": f"{rule['item']}の評価",
            "situation": "観測事実に基づくモック評価",
            "reason": decision.reason if decision else reason,
            "improvement": (
                f"次回は{rule['item']}の基準を行動前に確認してください"
                if label == "improve"
                else None
            ),
            "confidence": round(float(confidence), 3),
            "evidence": evidence,
            "evidence_range": (
                {"start_sec": evidence_start, "end_sec": evidence_end} if scored else None
            ),
            "display_clip": {"start_sec": start, "end_sec": end} if scored else None,
            "missing_information": missing,
            "unscored_reason_code": reason_code,
        }

    def _fact_refs(self, package: dict[str, Any], rule_id: str) -> list[str]:
        registry_rule = self.registry["rules"][rule_id]
        keys = {item["fact_key"] for item in registry_rule.get("required_state_predicates", [])}
        keys.update(registry_rule.get("supporting_fact_keys", []))
        return [fact["fact_id"] for fact in package["deterministic_facts"] if fact["key"] in keys][
            :8
        ]

    @staticmethod
    def _last_value(by_key: dict[str, list[dict[str, Any]]], key: str) -> Any:
        values = by_key.get(key, [])
        return values[-1].get("value") if values else None

    @staticmethod
    def _confidence(package: dict[str, Any], event: dict[str, Any] | None) -> float:
        quality = package["observation_quality"]
        base = min(
            float(quality["hud_confidence"]),
            float(quality["visual_confidence"]),
            float(quality["timeline_completeness"]),
        )
        if event:
            base = min(base, float(event.get("confidence", 0)))
        # Mock mode exercises the same evidence policy as the API path and must
        # never promote weak observations into a normally displayed score.
        return base
