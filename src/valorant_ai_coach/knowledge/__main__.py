"""Command line for the game knowledge base.

    python -m valorant_ai_coach.knowledge summary
    python -m valorant_ai_coach.knowledge verify-assets [--cache DIR]
    python -m valorant_ai_coach.knowledge lookup agent クローヴ
    python -m valorant_ai_coach.knowledge read-archive --cache DIR CROPS.zip [...]
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .assets import ReferenceAssets, ReferenceAssetsUnavailable
from .catalog import load_game_knowledge


def _print(value: object) -> None:
    sys.stdout.write(json.dumps(value, ensure_ascii=False, indent=1) + "\n")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m valorant_ai_coach.knowledge")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("summary")
    verify = sub.add_parser("verify-assets")
    verify.add_argument("--cache", type=Path)
    lookup = sub.add_parser("lookup")
    lookup.add_argument("kind", choices=("agent", "weapon", "map", "ability"))
    lookup.add_argument("name")
    archive = sub.add_parser("read-archive", help="Agent and alive counts from crop archives")
    archive.add_argument("--cache", type=Path)
    archive.add_argument("archives", type=Path, nargs="+")
    args = parser.parse_args(argv)
    knowledge = load_game_knowledge()

    if args.command == "summary":
        _print(knowledge.summary())
        return 0
    if args.command == "verify-assets":
        try:
            assets = ReferenceAssets.load(args.cache)
        except ReferenceAssetsUnavailable as error:
            sys.stderr.write(f"{error}\n")
            return 2
        _print({"root": str(assets.root), "files": len(assets.records),
                "content_digest": assets.content_digest, "game_version": assets.game_version})
        return 0
    if args.command == "lookup":
        if args.kind == "agent":
            agent = knowledge.agent(args.name)
            _print(None if agent is None else {
                "name": agent.name, "names": agent.names, "role": agent.role,
                "abilities": {k: a.names for k, a in agent.abilities.items()}})
        elif args.kind == "weapon":
            weapon = knowledge.weapon(args.name)
            _print(None if weapon is None else {
                "name": weapon.name, "names": weapon.names, "cost": weapon.cost,
                "magazine_size": weapon.magazine_size, "category": weapon.category})
        elif args.kind == "map":
            game_map = knowledge.map(args.name)
            _print(None if game_map is None else {
                "name": game_map.name, "names": game_map.names, "sites": game_map.sites,
                "callouts": len(game_map.callouts)})
        else:
            _print([{"agent": a.agent_uuid, "key": a.key, "names": a.names}
                    for a in knowledge.abilities_named(args.name)])
        return 0

    from valorant_ai_coach.learning.archives import CropArchive

    from .hud_abilities import AbilityHudReader, identify_agent
    from .top_bar import read_top_bar

    reader = AbilityHudReader(knowledge, ReferenceAssets.load(args.cache))
    results = []
    for path in args.archives:
        crops = CropArchive(path)
        readings, counts = [], []
        for sample in crops.iter_samples(("abilities", "top_bar")):
            if "abilities" in sample.crops:
                readings.append(reader.read(sample.crops["abilities"]))
            if "top_bar" in sample.crops:
                bar = read_top_bar(sample.crops["top_bar"])
                counts.append([sample.sec, bar.ally.alive, bar.enemy.alive, bar.consistent])
        ident = identify_agent(readings)
        agent = knowledge.agent(ident.agent_uuid) if ident.agent_uuid else None
        results.append({
            "video_id": crops.video_id, "status": ident.status, "frames": ident.frames_used,
            "agent": agent.name if agent else None, "role": agent.role if agent else "unknown",
            "vote_share": round(ident.vote_share, 4), "margin": round(ident.margin, 4),
            "alive_counts": counts,
        })
        crops.close()
    _print(results)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
