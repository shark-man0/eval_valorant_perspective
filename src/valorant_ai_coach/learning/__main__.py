"""CLI for the continual-learning workspace (see ``pipeline`` module docstring)."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .pipeline import (
    TASK,
    Context,
    Workspace,
    evaluate_independent,
    intake,
    learning_curve,
    run_cycle,
    save_report,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m valorant_ai_coach.learning")
    sub = parser.add_subparsers(dest="command", required=True)
    for name in ("cycle", "curve", "status", "rollback", "independent"):
        command = sub.add_parser(name)
        command.add_argument("--workspace", type=Path, required=True)
        if name in ("cycle", "curve", "independent"):
            command.add_argument("--cache", type=Path)
            command.add_argument("--reviewed-labels", type=Path,
                                 help="private JSON list of reviewed portrait labels")
        if name == "cycle":
            command.add_argument("--manifest", type=Path,
                                 help="JSON: source_id -> {sha256, physical_match_id?, unexposed?}")
            command.add_argument("archives", type=Path, nargs="*")
        if name == "curve":
            command.add_argument("--sizes", default="1,2,4,8,16")
    args = parser.parse_args(argv)
    workspace = Workspace(args.workspace.expanduser())
    if args.command == "status":
        models = workspace.models
        payload = {"dataset": workspace.dataset.summary(), "active": models.active_id(TASK),
                   "versions": [{"id": v.version_id, "status": v.status, "metrics": v.metrics}
                                for v in models.versions.values()]}
    elif args.command == "rollback":
        payload = {"active": workspace.models.rollback(TASK)}
    else:
        context = Context(workspace, args.cache)
        labels = (json.loads(args.reviewed_labels.read_text(encoding="utf-8"))
                  if args.reviewed_labels else None)
        if args.command == "cycle":
            manifest = (json.loads(args.manifest.read_text(encoding="utf-8"))
                        if args.manifest else {})
            payload = {"intake": intake(workspace, args.archives, manifest),
                       "dataset": workspace.dataset.summary(),
                       "cycle": run_cycle(workspace, context, reviewed_labels=labels)}
            save_report(workspace, "last_cycle", payload)
        elif args.command == "independent":
            payload = evaluate_independent(workspace, context, labels)
            save_report(workspace, "independent", payload)
        else:
            sizes = [int(s) for s in args.sizes.split(",") if s]
            payload = {"curve": learning_curve(workspace, context, sizes, reviewed_labels=labels)}
            save_report(workspace, "learning_curve", payload)
    sys.stdout.write(json.dumps(payload, ensure_ascii=False, indent=1) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
