"""Rule readiness on the per-second features (``extract_second_features.py``).

Same derivation as ``rule_readiness_real_video.py`` (5 s crops), but on one
keyframe per second, with the shot, movement and peek candidates added. Writes
a private JSON report and prints a public summary. Development only.

    PYTHONPATH=src python3 scripts/rules/rule_readiness_seconds.py \
        --features SEC_DIR --timeline-map TL.json --out private/rr_seconds.json
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any

from valorant_ai_coach.knowledge import load_game_knowledge
from valorant_ai_coach.knowledge.timeline_view import TimelineView
from valorant_ai_coach.rules.coverage import coverage, load_rules, summarize
from valorant_ai_coach.rules.development_readiness import derive, rule_occurrences
from valorant_ai_coach.rules.engagement_motion import engagement_motion, load_motion_frames
from valorant_ai_coach.rules.round_phases import PhaseRules
from valorant_ai_coach.rules.second_series import (
    WeaponLimits,
    ammo_events,
    detect_shots,
    load_second_records,
    movement_changes,
    second_additions,
)

AGENT_MIN_SCORE = 0.6
AGENT_MIN_SHARE = 0.4
AGENT_MIN_FRAMES = 60


def identify(records: list[Any], timeline: TimelineView | None) -> tuple[str | None, float]:
    votes: Counter[str] = Counter()
    for record in records:
        obs = record.observation
        if not obs.hud_present or obs.viewed_agent is None or obs.viewed_score < AGENT_MIN_SCORE:
            continue
        if timeline is not None:
            state = timeline.state_at(obs.sec)
            if state is not None and not timeline.self_live(obs.sec):
                continue
        votes[obs.viewed_agent] += 1
    total = sum(votes.values())
    if total < AGENT_MIN_FRAMES:
        return None, 0.0
    agent, count = votes.most_common(1)[0]
    share = count / total
    return (agent if share >= AGENT_MIN_SHARE else None), share


def own_live(records: list[Any], agent: str | None, timeline: TimelineView | None) -> list[bool]:
    out = []
    for record in records:
        obs = record.observation
        if timeline is not None and timeline.state_at(obs.sec) is not None:
            out.append(timeline.self_live(obs.sec))
        else:
            out.append(agent is not None and obs.viewed_agent == agent
                       and obs.viewed_score >= AGENT_MIN_SCORE)
    return out


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--features", type=Path, required=True)
    parser.add_argument("--timeline-map", type=Path)
    parser.add_argument("--ammo", type=Path,
                        help="directory of --ammo-only rows (adds the reserve count)")
    parser.add_argument("--motion", type=Path,
                        help="directory of extract_engagement_motion.py rows (60 fps)")
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    knowledge = load_game_knowledge()
    timelines = (json.loads(args.timeline_map.read_text(encoding="utf-8"))
                 if args.timeline_map else {})
    phase_rules = PhaseRules(
        round_time_limit_sec=int(knowledge.rule("round_time_limit_sec")),
        buy_phase_sec=int(knowledge.rule("buy_phase_sec")),
        buy_phase_half_start_sec=int(knowledge.rule("buy_phase_half_start_sec")),
        regulation_rounds_per_half=int(knowledge.rule("regulation_rounds_per_half")))
    limits = WeaponLimits.from_knowledge(knowledge.weapons)
    rules = load_rules()
    totals = {rule["id"]: 0 for rule in rules}
    matches_with = {rule["id"]: 0 for rule in rules}
    per_match = []
    for path in sorted(args.features.glob("*.jsonl")):
        video_id = path.stem
        records = load_second_records(
            path, args.ammo / path.name if args.ammo else None)
        timeline_path = timelines.get(video_id)
        timeline = TimelineView.load(Path(timeline_path)) if timeline_path else None
        agent_name, share = identify(records, timeline)
        agent = knowledge.agent(agent_name) if agent_name else None
        live = own_live(records, agent_name, timeline)
        series = [r.observation for r in records]
        role = agent.role if agent else "unknown"
        options = {"rounds_per_half": phase_rules.regulation_rounds_per_half,
                   "phase_rules": phase_rules,
                   "spike_detonation_sec": float(knowledge.rule("spike_detonation_sec"))}
        # Rounds first (they do not depend on shots), so shots never span a boundary.
        segments = [s.round_index for s in derive(series, agent_name, role, timeline,
                                                  **options).samples]
        additions = second_additions(records, live, limits, segments=segments)
        derivation = derive(series, agent_name, role, timeline, additions=additions, **options)
        counts = rule_occurrences(rules, derivation.samples)
        for rule_id, count in counts.items():
            totals[rule_id] += count
            matches_with[rule_id] += count > 0
        recon = derivation.reconciliation
        per_round: Counter[int] = Counter(d.round_index for d in recon.deaths)
        shots = detect_shots(records, live, limits=limits, segments=segments)
        ammo = ammo_events(records, live, limits, segments)
        motion: dict[str, int] = {}
        motion_path = args.motion / path.name if args.motion else None
        if motion_path is not None and motion_path.exists():
            frames = load_motion_frames(motion_path)
            previous = {e.sec: records[e.previous_index].observation.sec
                        for e in ammo if e.kind == "shot"}
            found = [engagement_motion(frames, previous[s.sec], s.sec)
                     for s in shots if s.first and s.sec in previous]
            motion = {"first_shots": len(found),
                      "first_shot_frames": sum(m is not None for m in found),
                      "moving_before_first_shot": sum(
                          bool(m and m.moving_before_shot) for m in found)}
        events: Counter[str] = Counter(e for s in derivation.samples for e in s.events)
        sides = derivation.sides
        per_match.append({
            "video_id": video_id, "agent": agent_name, "agent_share": round(share, 3),
            "role": agent.role if agent else "unknown", "seconds": len(records),
            "own_live_seconds": sum(live),
            "life": {"sources": derivation.sources, "rounds": recon.rounds,
                     "deaths": len(recon.deaths),
                     "revive_deaths": sum(d.after_revive for d in recon.deaths),
                     "unsplit_round_deaths": [round(d.sec, 1) for d in recon.deaths
                                              if d.after_round_restart],
                     "max_deaths_in_round": max(per_round.values(), default=0),
                     "multi_death_rounds": sum(c > 1 for c in per_round.values()),
                     "dropped": recon.dropped},
            "side": {"status": sides.status, "first_half_side": sides.first_half_side,
                     "observations": [[o.ordinal, o.side, o.source]
                                      for o in sides.observations],
                     "samples_with_side": sum("side" in d.facts for d in derivation.samples)},
            "phases": {"rounds": len(derivation.phases),
                       "with_combat_start": sum(p.combat_start is not None
                                                for p in derivation.phases),
                       "round_end_bases": dict(Counter(p.bases.get("round_end", "none")
                                                       for p in derivation.phases))},
            "shots": {"events": len(shots), "rounds_fired": sum(s.count for s in shots),
                      "first_shots": sum(s.first for s in shots),
                      "with_movement_state": sum(s.moving is not None for s in shots)},
            "ammo_events": dict(Counter(e.kind for e in ammo)),
            "engagement_motion": motion,
            "reserve_read_seconds": sum(r.reserve is not None for r in records),
            "movement_changes": len(movement_changes(records, live, segments)),
            "events": dict(events), "rule_occurrences": counts,
        })
        print(video_id, agent_name, sides.status, len(shots),
              sum(c > 0 for c in counts.values()), flush=True)
    fired = sorted(r for r, n in matches_with.items() if n > 0)
    report = {"development_only": True, "formal_outputs": 0, "sampling": "1 Hz keyframes",
              "matches": len(per_match),
              "readiness_after": summarize(coverage("after", rules)),
              "rules_with_real_video_candidates": fired, "rule_candidate_totals": totals,
              "rule_matches_with_candidates": matches_with, "per_match": per_match}
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps({k: report[k] for k in ("matches", "readiness_after",
                                             "rules_with_real_video_candidates")},
                     ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
