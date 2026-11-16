"""Measure which of the 44 rules can fire on DEVELOPMENT recordings.

Reads private HUD crop archives, runs the knowledge-based readers (ability HUD,
top match bar), derives development-only candidate facts/events and counts rule
occurrences. Writes a private JSON report; prints a public summary.

    PYTHONPATH=src python3 scripts/rules/rule_readiness_real_video.py \
        --cache ~/valorant_knowledge_cache --out private/rule_readiness.json CROPS/*.zip
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np

from valorant_ai_coach.knowledge import load_game_knowledge
from valorant_ai_coach.knowledge.assets import ReferenceAssets
from valorant_ai_coach.knowledge.hud_abilities import AbilityHudReader, identify_agent
from valorant_ai_coach.knowledge.top_bar import read_top_bar
from valorant_ai_coach.learning.archives import CropArchive
from valorant_ai_coach.rules.coverage import coverage, load_rules, summarize
from valorant_ai_coach.rules.development_readiness import (
    Observation,
    derive,
    rule_occurrences,
)


def observe(archive: Path, reader: AbilityHudReader) -> tuple[list[Observation], dict[str, object]]:
    crops = CropArchive(archive)
    readings, series = [], []
    names = {agent.uuid: agent.name for agent in reader.knowledge.agents}
    for sample in crops.iter_samples(("abilities", "top_bar")):
        hud = reader.read(sample.crops["abilities"]) if "abilities" in sample.crops else None
        bar = read_top_bar(sample.crops["top_bar"]) if "top_bar" in sample.crops else None
        if hud is not None:
            readings.append(hud)
        best = int(np.argmax(hud.agent_scores)) if hud is not None else -1
        series.append(Observation(
            sec=sample.sec,
            hud_present=bool(hud and hud.hud_present),
            viewed_agent=names[hud.agent_uuids[best]] if hud is not None else None,
            viewed_score=float(hud.agent_scores[best]) if hud is not None else 0.0,
            charges=tuple(s.charge_fraction for s in hud.slots) if hud is not None
            else (0.0, 0.0, 0.0, 0.0),  # type: ignore[arg-type]
            ally_alive=bar.ally.alive if bar is not None and bar.consistent else None,
            enemy_alive=bar.enemy.alive if bar is not None and bar.consistent else None,
        ))
    ident = identify_agent(readings)
    meta = {"video_id": crops.video_id, "samples": len(series), "status": ident.status,
            "agent": names.get(ident.agent_uuid or ""),
            "vote_share": round(ident.vote_share, 4), "margin": round(ident.margin, 4)}
    crops.close()
    return series, meta


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--cache", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("archives", type=Path, nargs="+")
    args = parser.parse_args()
    knowledge = load_game_knowledge()
    reader = AbilityHudReader(knowledge, ReferenceAssets.load(args.cache))
    rules = load_rules()
    per_match = []
    totals = {rule["id"]: 0 for rule in rules}
    matches_with = {rule["id"]: 0 for rule in rules}
    for archive in sorted(args.archives):
        series, meta = observe(archive, reader)
        agent = knowledge.agent(meta["agent"]) if meta["agent"] else None  # type: ignore[arg-type]
        derived = derive(series, agent.name if agent else None,
                         agent.role if agent else "unknown")
        counts = rule_occurrences(rules, derived)
        for rule_id, count in counts.items():
            totals[rule_id] += count
            matches_with[rule_id] += count > 0
        events: dict[str, int] = {}
        for sample in derived:
            for event in sample.events:
                events[event] = events.get(event, 0) + 1
        per_match.append({**meta, "role": agent.role if agent else "unknown",
                          "events": events, "rule_occurrences": counts})
        print(meta["video_id"], meta["agent"], meta["status"],
              sum(c > 0 for c in counts.values()), flush=True)
    fired = sorted(r for r, n in matches_with.items() if n > 0)
    report = {
        "development_only": True,
        "formal_outputs": 0,
        "matches": len(per_match),
        "readiness_before": summarize(coverage("before", rules)),
        "readiness_after": summarize(coverage("after", rules)),
        "rules_with_real_video_candidates": fired,
        "rule_candidate_totals": totals,
        "rule_matches_with_candidates": matches_with,
        "per_match": per_match,
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps({k: report[k] for k in ("matches", "readiness_before", "readiness_after",
                                             "rules_with_real_video_candidates")},
                     ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
