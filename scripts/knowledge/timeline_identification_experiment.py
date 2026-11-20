"""Recorder agent identification with and without the shared timeline.

For each crop archive with a shared-timeline export, compares the HUD-majority
vote with a vote restricted to the timeline's SELF + ALIVE frames, and reports
how often HUD frames inside timeline SPECTATOR intervals show the recorder.

    PYTHONPATH=src python3 scripts/knowledge/timeline_identification_experiment.py \
        --cache CACHE --pair fm1_1=CROPS/fm1_1.zip:TIMELINE/issue_oldfull001.json ...
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np

from valorant_ai_coach.knowledge import load_game_knowledge
from valorant_ai_coach.knowledge.assets import ReferenceAssets
from valorant_ai_coach.knowledge.hud_abilities import AbilityHudReader, identify_agent
from valorant_ai_coach.knowledge.timeline_view import TimelineView
from valorant_ai_coach.learning.archives import CropArchive


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--cache", type=Path, required=True)
    parser.add_argument("--pair", action="append", required=True,
                        help="ID=ARCHIVE.zip:TIMELINE.json")
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()
    knowledge = load_game_knowledge()
    reader = AbilityHudReader(knowledge, ReferenceAssets.load(args.cache))
    names = [agent.name for agent in knowledge.agents]
    results = {}
    for item in args.pair:
        video_id, paths = item.split("=", 1)
        archive, timeline_path = paths.rsplit(":", 1)
        timeline = TimelineView.load(Path(timeline_path))
        crops = CropArchive(Path(archive))
        readings, live, secs = [], [], []
        for sample in crops.iter_samples(("abilities",)):
            readings.append(reader.read(sample.crops["abilities"]))
            live.append(timeline.self_live(sample.sec))
            secs.append(sample.sec)
        crops.close()
        hud = identify_agent(readings)
        timed = identify_agent(readings, self_live=live)
        agent = knowledge.agent(timed.agent_uuid).name if timed.agent_uuid else None
        top = [names[int(np.argmax(r.agent_scores))] for r in readings]
        spectated = [t for t, s, r in zip(top, secs, readings, strict=True)
                     if timeline.spectating(s) and r.hud_present]
        results[video_id] = {
            "hud_majority": {"agent": knowledge.agent(hud.agent_uuid).name
                             if hud.agent_uuid else None,
                             "vote_share": round(hud.vote_share, 4),
                             "margin": round(hud.margin, 4), "frames": hud.frames_used},
            "timeline_self_live": {"agent": agent, "basis": timed.basis,
                                   "vote_share": round(timed.vote_share, 4),
                                   "margin": round(timed.margin, 4), "frames": timed.frames_used},
            "spectator_frames": len(spectated),
            "spectator_frames_showing_recorder": round(float(np.mean(
                [t == agent for t in spectated])), 4) if spectated else None,
        }
        print(video_id, json.dumps(results[video_id], ensure_ascii=False), flush=True)
    if args.out:
        args.out.write_text(json.dumps(results, ensure_ascii=False, indent=1), "utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
