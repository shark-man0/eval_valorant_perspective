"""Recorder agent identification with and without parts of the game knowledge.

Variants on the same crops:
  no_knowledge   no names, roles or icons: the HUD can be clustered but not named,
                 so no agent (and no player_role) can be produced.
  icons_only     official ability icons, but without the slot-order rule: every
                 slot is matched against all ability icons of every agent.
  full           official icons + slot order (C, Q, E, X) + per-agent ability sets.

    PYTHONPATH=src python3 scripts/knowledge/agent_identification_experiment.py \
        --cache CACHE --truth fm1_1=Fade,... CROPS/*.zip
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path

import numpy as np

from valorant_ai_coach.knowledge import load_game_knowledge
from valorant_ai_coach.knowledge.assets import ReferenceAssets
from valorant_ai_coach.knowledge.catalog import HUD_ABILITY_KEYS
from valorant_ai_coach.knowledge.hud_abilities import AbilityHudReader, identify_agent
from valorant_ai_coach.learning.archives import CropArchive


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--cache", type=Path, required=True)
    parser.add_argument("--truth", default="", help="video_id=Agent,... (reviewed labels)")
    parser.add_argument("--out", type=Path)
    parser.add_argument("archives", type=Path, nargs="+")
    args = parser.parse_args()
    truth = dict(item.split("=", 1) for item in args.truth.split(",") if item)
    knowledge = load_game_knowledge()
    reader = AbilityHudReader(knowledge, ReferenceAssets.load(args.cache))
    names = [agent.name for agent in knowledge.agents]
    rows = []
    for path in sorted(args.archives):
        crops = CropArchive(path)
        full_frames, icon_frames, readings = [], [], []
        for sample in crops.iter_samples(("abilities",)):
            reading = reader.read(sample.crops["abilities"])
            if not reading.hud_present:
                continue
            readings.append(reading)
            full_frames.append(names[int(np.argmax(reading.agent_scores))])
            # icons_only: each slot is compared with every ability icon of every agent,
            # without the slot-order rule; the frame's agent is the majority owner.
            owners = []
            for window in reader.slot_windows(sample.crops["abilities"]).values():
                per_key = np.vstack([reader.match_window(window, key) for key in HUD_ABILITY_KEYS])
                owners.append(int(np.unravel_index(np.argmax(per_key), per_key.shape)[1]))
            icon_frames.append(names[Counter(owners).most_common(1)[0][0]])
        ident = identify_agent(readings)
        full_agent = names[[a.uuid for a in knowledge.agents].index(ident.agent_uuid)] \
            if ident.agent_uuid else None
        icon_agent = Counter(icon_frames).most_common(1)[0][0] if icon_frames else None
        expected = truth.get(crops.video_id)
        rows.append({
            "video_id": crops.video_id, "hud_frames": len(full_frames), "truth": expected,
            "no_knowledge": None,
            "icons_only": icon_agent, "full": full_agent, "full_status": ident.status,
            "full_vote_share": round(ident.vote_share, 4), "full_margin": round(ident.margin, 4),
            "frame_agreement_full": round(float(np.mean([f == expected for f in full_frames])), 4)
            if expected else None,
            "frame_agreement_icons_only": round(float(np.mean([f == expected
                                                                for f in icon_frames])), 4)
            if expected else None,
        })
        crops.close()
    labelled = [r for r in rows if r["truth"]]
    summary = {
        "matches": len(rows),
        "reviewed": len(labelled),
        "identified_full": sum(r["full"] is not None for r in rows),
        "correct_full": sum(r["full"] == r["truth"] for r in labelled),
        "correct_icons_only": sum(r["icons_only"] == r["truth"] for r in labelled),
        "correct_no_knowledge": 0,
        "mean_frame_agreement_full": round(float(np.mean([r["frame_agreement_full"]
                                                           for r in labelled])), 4)
        if labelled else None,
        "mean_frame_agreement_icons_only": round(float(np.mean(
            [r["frame_agreement_icons_only"] for r in labelled])), 4) if labelled else None,
    }
    payload = {"summary": summary, "matches": rows}
    if args.out:
        args.out.write_text(json.dumps(payload, ensure_ascii=False, indent=1), "utf-8")
    print(json.dumps(payload, ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
