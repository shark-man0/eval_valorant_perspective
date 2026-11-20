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
from valorant_ai_coach.knowledge.kill_feed import KillFeedReader
from valorant_ai_coach.knowledge.score_reader import ScoreReader, ScoreTemplatesUnavailable
from valorant_ai_coach.knowledge.spike_carrier import SpikeCarrierReader, SpikeTemplateUnavailable
from valorant_ai_coach.knowledge.timeline_view import TimelineView
from valorant_ai_coach.knowledge.top_bar import read_top_bar, spike_planted_indicator
from valorant_ai_coach.learning.archives import CropArchive
from valorant_ai_coach.rules.coverage import coverage, load_rules, summarize
from valorant_ai_coach.rules.development_readiness import (
    FeedKill,
    Observation,
    derive,
    rule_occurrences,
)
from valorant_ai_coach.rules.round_phases import PhaseRules


def observe(archive: Path, reader: AbilityHudReader, feed_reader: KillFeedReader,
            timeline: TimelineView | None, spike_reader: SpikeCarrierReader | None = None,
            score_reader: ScoreReader | None = None,
            ) -> tuple[list[Observation], dict[str, object]]:
    crops = CropArchive(archive)
    readings, series, live = [], [], []
    names = {agent.uuid: agent.name for agent in reader.knowledge.agents}
    for sample in crops.iter_samples(("abilities", "top_bar", "kill_feed", "weapon_inventory")):
        hud = reader.read(sample.crops["abilities"]) if "abilities" in sample.crops else None
        bar = read_top_bar(sample.crops["top_bar"]) if "top_bar" in sample.crops else None
        spike = spike_planted_indicator(sample.crops["top_bar"])[0] \
            if "top_bar" in sample.crops else None
        feed = None
        if "kill_feed" in sample.crops:
            feed = tuple(
                FeedKill(e.killer_team, e.victim_team,
                         e.victim if e.victim_score >= 0.6 else None,
                         e.recorder_killer, e.recorder_victim)
                for e in feed_reader.read(sample.crops["kill_feed"]))
        carried = None
        score = None
        timer = None
        if score_reader is not None and "top_bar" in sample.crops:
            reading = score_reader.read(sample.crops["top_bar"])
            score = (reading.ally, reading.enemy)
            timer = score_reader.read_timer(sample.crops["top_bar"])
        if spike_reader is not None and "weapon_inventory" in sample.crops:
            carried = spike_reader.read(sample.crops["weapon_inventory"]).carried
        if hud is not None:
            readings.append(hud)
            live.append(timeline.self_live(sample.sec) if timeline is not None else False)
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
            spike_planted=spike,
            feed=feed,
            spike_carried=carried,
            score=score,
            timer=timer,
        ))
    ident = identify_agent(readings, self_live=live if timeline is not None else None)
    meta = {"video_id": crops.video_id, "samples": len(series), "status": ident.status,
            "agent": names.get(ident.agent_uuid or ""),
            "vote_share": round(ident.vote_share, 4), "margin": round(ident.margin, 4),
            "agent_basis": ident.basis, "kill_feed_captured": any(o.feed is not None
                                                                  for o in series)}
    crops.close()
    return series, meta


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--cache", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--timeline-map", type=Path,
                        help="JSON: video_id -> shared-timeline export path")
    parser.add_argument("archives", type=Path, nargs="+")
    args = parser.parse_args()
    knowledge = load_game_knowledge()
    assets = ReferenceAssets.load(args.cache)
    reader = AbilityHudReader(knowledge, assets)
    feed_reader = KillFeedReader(knowledge, assets)
    try:
        spike_reader: SpikeCarrierReader | None = SpikeCarrierReader.load(args.cache)
    except SpikeTemplateUnavailable as exc:
        print(f"spike carrier disabled: {exc}")
        spike_reader = None
    try:
        score_reader: ScoreReader | None = ScoreReader.load(args.cache)
    except ScoreTemplatesUnavailable as exc:
        print(f"score reader disabled: {exc}")
        score_reader = None
    timelines = (json.loads(args.timeline_map.read_text(encoding="utf-8"))
                 if args.timeline_map else {})
    rules = load_rules()
    per_match = []
    totals = {rule["id"]: 0 for rule in rules}
    matches_with = {rule["id"]: 0 for rule in rules}
    for archive in sorted(args.archives):
        timeline_path = timelines.get(archive.stem)
        timeline = TimelineView.load(Path(timeline_path)) if timeline_path else None
        series, meta = observe(archive, reader, feed_reader, timeline, spike_reader,
                               score_reader)
        agent = knowledge.agent(meta["agent"]) if meta["agent"] else None  # type: ignore[arg-type]
        derivation = derive(series, agent.name if agent else None,
                            agent.role if agent else "unknown", timeline,
                            rounds_per_half=int(knowledge.rule("regulation_rounds_per_half")),
                            phase_rules=PhaseRules(
                                round_time_limit_sec=int(knowledge.rule("round_time_limit_sec")),
                                buy_phase_sec=int(knowledge.rule("buy_phase_sec")),
                                buy_phase_half_start_sec=int(
                                    knowledge.rule("buy_phase_half_start_sec")),
                                regulation_rounds_per_half=int(
                                    knowledge.rule("regulation_rounds_per_half"))))
        derived = derivation.samples
        counts = rule_occurrences(rules, derived)
        recon = derivation.reconciliation
        per_round: dict[int, int] = {}
        for death in recon.deaths:
            per_round[death.round_index] = per_round.get(death.round_index, 0) + 1
        meta["life"] = {
            "sources": derivation.sources, "rounds": recon.rounds,
            "deaths": len(recon.deaths),
            "revive_deaths": sum(d.after_revive for d in recon.deaths),
            "unsplit_round_deaths": [round(d.sec, 1) for d in recon.deaths
                                     if d.after_round_restart],
            "rounds_with_death": len(per_round),
            "max_deaths_in_round": max(per_round.values(), default=0),
            "dropped": recon.dropped,
            "by_sources": {"+".join(sorted(d.sources)): sum(
                1 for x in recon.deaths if x.sources == d.sources) for d in recon.deaths},
        }
        sides = derivation.sides
        meta["side"] = {
            "status": sides.status, "first_half_side": sides.first_half_side,
            "observed_attack_ordinals": list(sides.observed),
            "samples_with_side": sum("side" in d.facts for d in derivation.samples),
            "samples_with_score": sum(bool(o.score and None not in o.score) for o in series),
            "spike_carried_samples": sum(bool(o.spike_carried) for o in series),
        }
        meta["phases"] = [
            {"ordinal": p.ordinal, "score_update": p.score_update,
             "buy_phase_start": p.buy_phase_start, "combat_start": p.combat_start,
             "round_end": p.round_end, "bases": p.bases} for p in derivation.phases]
        meta["timer_samples"] = sum(o.timer is not None for o in series)
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
