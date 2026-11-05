"""Local development consumer; candidates never become deterministic facts/events."""

from __future__ import annotations

from typing import Any

from valorant_ai_coach.models import RuleCandidate

from .engine import DeterministicRuleEngine
from .temporal_scope import TemporalScopeResolver, scope_round_package


def evaluation_package(bundle: dict[str, Any], start: int, end: int) -> dict[str, Any]:
    if bundle.get("qualification") != "development_only" or bundle.get("formal_outputs") != 0:
        raise ValueError("Development application timeline required")
    if not 0 <= start < end <= len(bundle["seconds"]):
        raise ValueError("Nonempty recording-second range required")
    rows = bundle["seconds"][start:end]
    return {
        "round_window": {
            "start_sec": start,
            "end_sec": min(end, bundle["recording"]["end_timestamp"]),
        },
        "deterministic_facts": [],
        "events": [],
        "state_snapshots": [],
        "frames": [],
        "development_timeline": rows,
        "development_event_candidates": {
            ref: bundle["events"][ref] for row in rows for ref in row["event_candidates"]
        },
        "qualification": "development_only",
    }


def review_timeline(bundle: dict[str, Any]) -> dict[str, Any]:
    """Actual downstream review queue, plus existing rule-engine handoff smoke."""
    rows = bundle["seconds"]
    package = evaluation_package(bundle, 0, len(rows))
    candidate = RuleCandidate("AIM-02", "P2", "round", "deterministic")
    scope = TemporalScopeResolver().resolve(candidate, package)
    scoped, _ = scope_round_package(package, [scope])
    decision = DeterministicRuleEngine().evaluate(
        candidate.rule_id, scoped["deterministic_facts"], scoped["events"]
    )
    assert decision is None
    return {
        "version": "development_timeline_review_v1",
        "seconds_consumed": len(rows),
        "candidate_review_queue": [
            {
                "candidate_ref": ref,
                "kind": event["kind"],
                "lower_timestamp": event["lower_timestamp"],
                "upper_timestamp": event["upper_timestamp"],
            }
            for ref, event in bundle["events"].items()
        ],
        "UNKNOWN_seconds": {
            domain: sum(row[domain]["value"] == "UNKNOWN" for row in rows)
            for domain in ("round_state", "life_state", "camera_state")
        },
        "observed_seconds": sum(row["observation_present"] for row in rows),
        "hud_candidate_seconds": {
            key: sum(bool(row["hud_observations"][key]["candidates"]) for row in rows)
            for key in ("hp", "armor", "weapon", "timer", "score")
        },
        "map_candidate_seconds": sum(
            row["map_observations"]["status"] == "CANDIDATES" for row in rows
        ),
        "existing_scope_resolver_consumed": True,
        "deterministic_engine_decision": None,
        "formal_outputs": 0,
        "scope": "Coverage and candidate review, not coaching score or recognition accuracy",
    }
