"""Independent evaluation path: the only route that analyses opened hold-out recordings.

Development commands admit recordings for ``development_analysis`` only. This module
is the separate path for ``qualification`` and ``final_evaluation``. It runs the
same common timeline (acquisition, camera panel, export) with options frozen in
advance, and nothing else:

1. ``prepare`` freezes a plan before anything is analysed: the catalog recordings,
   the evaluation purpose, the analysis options, the references, the reader
   configuration and a digest of the analysis code. The catalog must already show
   every recording opened for that purpose and never exposed otherwise. ``prepare``
   reads the catalog and writes only the new plan file.
2. ``execute`` runs a prepared plan. It needs a recorded approval note, refuses a
   plan whose code, references, reader configuration or catalog admission changed,
   and writes new private outputs with a receipt.

Opening hold-out material (``recordings open``) and formal qualification are
separate decisions; this module performs neither. Its outputs carry
``formal_qualification: NOT_GRANTED`` and ``formal_outputs: 0``. No supplement,
override or tuning input is accepted: the options are fixed in this file and bound
by the plan.

Usage::

    python -m valorant_ai_coach.temporal.independent_evaluation prepare \\
        --catalog CATALOG --purpose qualification --recording REC_ID [...] \\
        --reader-config screen_PRIVATE.json --label-reference label.png \\
        --remote-hint hint.png --remote-duration bat.png --camera-hint camera.png \\
        --plan plan_PRIVATE.json
    python -m valorant_ai_coach.temporal.independent_evaluation execute \\
        --plan plan_PRIVATE.json --approval-note "who approved, when" --output OUT
"""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import UTC, datetime
from fractions import Fraction
from pathlib import Path
from typing import Any

from .replay import file_sha, read_json, write_private

VERSION = "independent_evaluation_v1"
EVALUATION_PURPOSES: tuple[str, ...] = ("qualification", "final_evaluation")
OBSERVER = "valorant_ai_coach.temporal.screen_cues:ScreenCueObserver"
# The options of the approved common timeline (#150 and #151), frozen.
FROZEN_OPTIONS: dict[str, Any] = {
    "coarse_seconds": "1",
    "dense_seconds": "1/5",
    "max_refinement_windows": 0,
    "max_refinement_seconds": "0",
    "refinement_selection_policy": "evidence",
    "report_view_bridge": True,
    "buy_clock_expiry": True,
    "provisional_map_roles": True,
    "active_clock_bridge": True,
    "return_display_tail": True,
    "buy_clock_tail": True,
    "current_hp_return_candidate": True,
    "current_menu_return_candidate": True,
    "practical_visual_state": True,
    "evidence_continuity": True,
    "measured_view_precedence": True,
}
REFERENCE_NAMES: tuple[str, ...] = (
    "label_reference", "remote_hint", "remote_duration", "camera_hint",
)


def code_digest() -> str:
    """Digest of every module of the package (analysis, catalog and rules)."""
    root = Path(__file__).resolve().parent.parent
    entries = sorted(
        (path.relative_to(root).as_posix(), file_sha(path))
        for path in root.rglob("*.py")
        if "__pycache__" not in path.parts
    )
    return hashlib.sha256(
        json.dumps(entries, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


def _catalog(root: Path, path_map: dict[str, str] | None) -> Any:
    from valorant_ai_coach.recordings.catalog import RecordingCatalog

    return RecordingCatalog(root, path_map=path_map or {})


def _new_private_path(path: Path) -> Path:
    path = path.expanduser().resolve()
    if path.exists() or any((p / ".git").exists() for p in path.parents):
        raise ValueError("New private path outside Git required")
    return path


def prepare(
    *,
    catalog_root: Path,
    recording_ids: list[str],
    purpose: str,
    reader_config: Path,
    references: dict[str, Path],
    plan_path: Path,
    path_map: dict[str, str] | None = None,
) -> dict[str, Any]:
    """Freeze an evaluation plan; refuse recordings not opened for ``purpose``."""
    if purpose not in EVALUATION_PURPOSES:
        raise ValueError("Evaluation purpose must be qualification or final_evaluation")
    if not recording_ids or len(set(recording_ids)) != len(recording_ids):
        raise ValueError("Explicit distinct recording ids required")
    if set(references) != set(REFERENCE_NAMES):
        raise ValueError("All camera panel references required")
    plan_path = _new_private_path(plan_path)
    catalog = _catalog(catalog_root, path_map)
    catalog.guard(recording_ids, purpose)  # opened for purpose, otherwise unexposed
    plan = {
        "version": VERSION,
        "created_at": datetime.now(UTC).isoformat(),
        "purpose": purpose,
        "catalog": str(Path(catalog_root).resolve()),
        "path_map": dict(path_map or {}),
        "catalog_head_at_plan": catalog.head_anchor(),
        "recordings": [
            {
                "recording_id": rid,
                "source_sha256": catalog.state.recordings[rid].source_sha256,
                "split": catalog.state.recordings[rid].split,
            }
            for rid in recording_ids
        ],
        "options": FROZEN_OPTIONS,
        "observer": OBSERVER,
        "reader_config": {"path": str(reader_config.resolve()), "sha256": file_sha(reader_config)},
        "references": {
            name: {"path": str(path.resolve()), "sha256": file_sha(path)}
            for name, path in sorted(references.items())
        },
        "code_digest": code_digest(),
        "formal_qualification": "NOT_GRANTED",
        "formal_outputs": 0,
    }
    plan_path.parent.mkdir(parents=True, exist_ok=True)
    write_private(plan_path, plan)
    return plan


def _check_plan(plan: dict[str, Any]) -> Any:
    if plan.get("version") != VERSION or plan.get("purpose") not in EVALUATION_PURPOSES:
        raise ValueError("Independent evaluation plan required")
    if plan["options"] != FROZEN_OPTIONS or plan["observer"] != OBSERVER:
        raise ValueError("Plan options differ from the frozen evaluation options")
    if plan["code_digest"] != code_digest():
        raise ValueError("Analysis code changed after the plan was frozen")
    for binding in [plan["reader_config"], *plan["references"].values()]:
        if file_sha(Path(binding["path"])) != binding["sha256"]:
            raise ValueError("Frozen reference or reader configuration changed")
    catalog = _catalog(Path(plan["catalog"]), plan.get("path_map"))
    ids = [r["recording_id"] for r in plan["recordings"]]
    catalog.guard(ids, plan["purpose"])
    for row in plan["recordings"]:
        if catalog.state.recordings[row["recording_id"]].source_sha256 != row["source_sha256"]:
            raise ValueError("Catalog recording differs from the plan")
    return catalog


def execute(*, plan_path: Path, approval_note: str, output: Path) -> dict[str, Any]:
    """Run a frozen plan; the approval of this run is recorded, not granted here."""
    if not approval_note.strip():
        raise ValueError("Recorded approval of the evaluation run required")
    plan = read_json(plan_path)
    catalog = _check_plan(plan)
    output = _new_private_path(output)
    output.mkdir(parents=True)
    from . import camera_panel
    from .application import export_application
    from .match import run_match
    from .screen_cues import ScreenCueObserver

    options, purpose = plan["options"], plan["purpose"]
    refs = {name: Path(b["path"]) for name, b in plan["references"].items()}
    results = []
    for row in plan["recordings"]:
        rid = row["recording_id"]
        work = output / rid
        work.mkdir()
        policy_path = work / "policy_PRIVATE.json"
        write_private(policy_path, {
            "catalog": plan["catalog"], "path_map": plan.get("path_map") or {},
            "allowed_recording_ids": [rid], "purpose": purpose,
        })
        acquisition = work / "acquisition"
        run_match(
            policy_path=policy_path,
            source_id=rid,
            reader_config=Path(plan["reader_config"]["path"]),
            output=acquisition,
            observer_factory=ScreenCueObserver,
            coarse_seconds=Fraction(options["coarse_seconds"]),
            dense_seconds=Fraction(options["dense_seconds"]),
            max_refinement_windows=options["max_refinement_windows"],
            max_refinement_seconds=Fraction(options["max_refinement_seconds"]),
            refinement_selection_policy=options["refinement_selection_policy"],
            report_view_bridge=options["report_view_bridge"],
            buy_clock_expiry=options["buy_clock_expiry"],
            provisional_map_roles=options["provisional_map_roles"],
            active_clock_bridge=options["active_clock_bridge"],
            return_display_tail=options["return_display_tail"],
            buy_clock_tail=options["buy_clock_tail"],
            current_hp_return_candidate=options["current_hp_return_candidate"],
            current_menu_return_candidate=options["current_menu_return_candidate"],
            practical_visual_state=options["practical_visual_state"],
            evidence_continuity=options["evidence_continuity"],
            admission_purpose=purpose,
        )
        record = catalog.state.recordings[rid]
        location = record.locations.get("managed") or record.locations.get("original")
        video = catalog.local_path(location["path"])
        camera = work / "camera_panel_PRIVATE.json"
        status = camera_panel.main([
            "--video", str(video),
            "--timeline", str(acquisition / "timeline_PRIVATE.json"),
            "--label-reference", str(refs["label_reference"]),
            "--remote-hint", str(refs["remote_hint"]),
            "--remote-duration", str(refs["remote_duration"]),
            "--camera-hint", str(refs["camera_hint"]),
            "--output", str(camera),
        ])
        if status != 0:
            raise ValueError("Camera panel measurement failed")
        manifest = export_application(
            timeline_path=acquisition / "timeline_PRIVATE.json",
            receipt_path=acquisition / "completion_PRIVATE.json",
            policy_path=policy_path,
            output=work / "timeline",
            supplements=[camera],
            provisional_map_roles=options["provisional_map_roles"],
            active_clock_bridge=options["active_clock_bridge"],
            return_display_tail=options["return_display_tail"],
            buy_clock_tail=options["buy_clock_tail"],
            current_hp_return_candidate=options["current_hp_return_candidate"],
            current_menu_return_candidate=options["current_menu_return_candidate"],
            practical_visual_state=options["practical_visual_state"],
            evidence_continuity=options["evidence_continuity"],
            measured_view_precedence=options["measured_view_precedence"],
            admission_purpose=purpose,
        )
        results.append({
            "recording_id": rid,
            "source_sha256": row["source_sha256"],
            "output_sha256s": manifest["output_sha256s"],
        })
    receipt = {
        "version": VERSION,
        "finished_at": datetime.now(UTC).isoformat(),
        "plan_sha256": file_sha(plan_path),
        "purpose": purpose,
        "approval_note": approval_note,
        "catalog_head_at_plan": plan["catalog_head_at_plan"],
        "catalog_head_at_run": catalog.head_anchor(),
        "code_digest": plan["code_digest"],
        "results": results,
        "scoring": "NOT_PERFORMED",
        "formal_qualification": "NOT_GRANTED",
        "formal_outputs": 0,
    }
    write_private(output / "independent_evaluation_receipt_PRIVATE.json", receipt)
    return receipt


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="command", required=True)
    plan = sub.add_parser("prepare")
    plan.add_argument("--catalog", type=Path, required=True)
    plan.add_argument("--purpose", required=True, choices=EVALUATION_PURPOSES)
    plan.add_argument("--recording", action="append", required=True)
    plan.add_argument("--reader-config", type=Path, required=True)
    for name in REFERENCE_NAMES:
        plan.add_argument("--" + name.replace("_", "-"), type=Path, required=True)
    plan.add_argument("--path-map", help="JSON object mapping catalog path prefixes")
    plan.add_argument("--plan", type=Path, required=True)
    run = sub.add_parser("execute")
    run.add_argument("--plan", type=Path, required=True)
    run.add_argument("--approval-note", required=True)
    run.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    if args.command == "prepare":
        result = prepare(
            catalog_root=args.catalog,
            recording_ids=args.recording,
            purpose=args.purpose,
            reader_config=args.reader_config,
            references={name: getattr(args, name) for name in REFERENCE_NAMES},
            plan_path=args.plan,
            path_map=json.loads(args.path_map) if args.path_map else None,
        )
        print(json.dumps({"purpose": result["purpose"],
                          "recordings": len(result["recordings"]),
                          "code_digest": result["code_digest"]}))
    else:
        receipt = execute(plan_path=args.plan, approval_note=args.approval_note,
                          output=args.output)
        print(json.dumps({"recordings": len(receipt["results"]),
                          "formal_qualification": receipt["formal_qualification"]}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
