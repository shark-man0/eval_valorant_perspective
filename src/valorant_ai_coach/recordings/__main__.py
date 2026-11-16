"""Command line for the private recording catalog (#62).

Outputs that can be shown or committed are counts only; ids, hashes and paths stay in
the catalog directory.
"""

from __future__ import annotations

import argparse
import importlib
import json
import sys
from collections.abc import Sequence
from pathlib import Path

from .catalog import ARTIFACT_KINDS, EXPOSURE_KINDS, PURPOSES, CatalogError, RecordingCatalog


def _print(value: object) -> None:
    print(json.dumps(value, ensure_ascii=False, indent=2))


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m valorant_ai_coach.recordings")
    parser.add_argument("--catalog", type=Path, required=True, help="非公開カタログの場所")
    parser.add_argument(
        "--path-map", action="append", default=[], metavar="STORED=LOCAL",
        help="保存済みパスの先頭をこの環境の場所に読み替える（例: Macのパスを仮想環境へ）",
    )
    sub = parser.add_subparsers(dest="command", required=True)
    init = sub.add_parser("init")
    init.add_argument("--seed")
    init.add_argument("--ratios", help="例: DEVELOPMENT=0.6,QUALIFICATION=0.2,FINAL_HOLDOUT=0.2")
    register = sub.add_parser("register")
    register.add_argument("paths", nargs="+", type=Path)
    register.add_argument("--physical-match-id")
    register.add_argument("--split")
    register.add_argument("--role", default="original", choices=["original", "managed"])
    register.add_argument("--probe", action="store_true")
    register.add_argument("--workers", type=int, default=4)
    register.add_argument("--confirm-distinct", action="store_true")
    register.add_argument("--derived-from", help="派生動画の派生元recording_id")
    register.add_argument("--max-new-files", type=int, help="1回に新規登録する最大本数")
    legacy = sub.add_parser("import-legacy")
    legacy.add_argument("files", nargs="+", type=Path)
    exposure = sub.add_parser("expose")
    exposure.add_argument("recording_ids", nargs="*")
    exposure.add_argument("--location-prefix", type=Path, action="append", default=[],
                          help="この場所にある録画をすべて対象にする")
    exposure.add_argument("--kind", required=True, choices=EXPOSURE_KINDS)
    exposure.add_argument("--note", default="")
    opening = sub.add_parser("open")
    opening.add_argument("recording_ids", nargs="+")
    opening.add_argument("--purpose", required=True, choices=["qualification", "final_evaluation"])
    opening.add_argument("--note", required=True)
    artifact = sub.add_parser("artifact")
    artifact.add_argument("--kind", required=True, choices=ARTIFACT_KINDS)
    artifact.add_argument("--parent", action="append", required=True)
    artifact.add_argument("--producer", required=True)
    artifact.add_argument("--version", default="")
    artifact.add_argument("--config-sha256", default="")
    artifact.add_argument("--path", type=Path)
    artifact.add_argument("--sha256")
    artifact.add_argument("--artifact-id")
    guard = sub.add_parser("guard")
    guard.add_argument("nodes", nargs="+")
    guard.add_argument("--purpose", required=True, choices=PURPOSES)
    plan = sub.add_parser("plan")
    plan.add_argument("--producer", required=True)
    plan.add_argument("--version", default="")
    plan.add_argument("--config-sha256", default="")
    plan.add_argument("--purpose", default="development_analysis", choices=PURPOSES)
    lineage = sub.add_parser("lineage")
    lineage.add_argument("node")
    verify = sub.add_parser("verify")
    verify.add_argument("--quick", action="store_true", help="size/mtimeが同じなら再ハッシュしない")
    verify.add_argument("--recordings", nargs="+", help="照合する録画（分割実行用）")
    verify.add_argument("--trusted-head", help="カタログ外に保管したSEQ:SHA256")
    sub.add_parser("head")
    archives = sub.add_parser("learning-archives")
    archives.add_argument("--kind", default="frames")
    archives.add_argument("--include-authorised-exposed", action="store_true")
    sync = sub.add_parser("sync-learning", help="#154の継続学習登録簿へ反映")
    sync.add_argument("--workspace", type=Path, required=True)
    sync.add_argument("--kind", default="frames")
    sync.add_argument("--include-authorised-exposed", action="store_true")
    sub.add_parser("summary")
    sub.add_parser("learning-view")
    leak = sub.add_parser("leak-check")
    leak.add_argument("files", nargs="+", type=Path)
    args = parser.parse_args(argv)
    try:
        if args.command == "init":
            ratios = None
            if args.ratios:
                ratios = {
                    key: float(value)
                    for key, value in (item.split("=", 1) for item in args.ratios.split(","))
                }
            RecordingCatalog.create(args.catalog, seed=args.seed, ratios=ratios)
            _print(RecordingCatalog(args.catalog).public_summary())
            return 0
        path_map = dict(item.split("=", 1) for item in args.path_map)
        catalog = RecordingCatalog(args.catalog, path_map=path_map)
        if args.command == "register":
            results = []
            for path in args.paths:
                if path.is_dir():
                    results.extend(catalog.register_directory(
                        path, workers=args.workers, probe=args.probe,
                        confirm_distinct=args.confirm_distinct,
                        max_new_files=args.max_new_files, split=args.split,
                    ))
                else:
                    results.append(catalog.register(
                        path, physical_match_id=args.physical_match_id, split=args.split,
                        role=args.role, confirm_distinct=args.confirm_distinct,
                        derived_from=args.derived_from,
                    ))
            _print({"added": sum(r.added for r in results),
                    "already_registered": sum(not r.added for r in results),
                    "summary": catalog.public_summary()})
        elif args.command == "import-legacy":
            _print([catalog.import_legacy(path) for path in args.files])
        elif args.command == "expose":
            targets = list(args.recording_ids)
            for prefix in args.location_prefix:
                targets.extend(catalog.recordings_under(prefix))
            targets = list(dict.fromkeys(targets))
            if not targets:
                raise CatalogError("対象の録画がありません")
            recorded = 0
            for recording_id in targets:
                kinds = {e["kind"] for e in catalog.state.recordings[recording_id].exposures}
                if args.kind in kinds and args.kind == "user_authorized_development_use":
                    continue  # the same authorisation once is enough
                catalog.record_exposure(recording_id, args.kind, args.note)
                recorded += 1
            _print({"targets": len(targets), "recorded": recorded,
                    "summary": catalog.public_summary()})
        elif args.command == "open":
            catalog.open_for_evaluation(args.recording_ids, args.purpose, args.note)
            _print(catalog.public_summary())
        elif args.command == "artifact":
            identifier = catalog.register_artifact(
                kind=args.kind, parents=args.parent, path=args.path, sha256=args.sha256,
                artifact_id=args.artifact_id,
                producer={"name": args.producer, "version": args.version,
                          "config_sha256": args.config_sha256},
            )
            _print({"artifact_id": identifier})
        elif args.command == "guard":
            catalog.guard(args.nodes, args.purpose)
            _print({"allowed": True, "purpose": args.purpose})
        elif args.command == "plan":
            todo = catalog.plan(
                {"name": args.producer, "version": args.version,
                 "config_sha256": args.config_sha256},
                purpose=args.purpose,
            )
            _print({"pending": todo})
        elif args.command == "lineage":
            _print(catalog.lineage(args.node))
        elif args.command == "head":
            _print({"head": catalog.head_anchor()})
        elif args.command == "learning-archives":
            _print(catalog.learning_archives(
                artifact_kind=args.kind,
                include_authorised_exposed=args.include_authorised_exposed,
            ))
        elif args.command == "sync-learning":
            # Imported dynamically: the continual-learning package (#154) is optional.
            learning = importlib.import_module("valorant_ai_coach.learning.registry")
            DatasetRegistry = learning.DatasetRegistry  # noqa: N806

            rows = catalog.learning_archives(
                artifact_kind=args.kind,
                include_authorised_exposed=args.include_authorised_exposed,
            )
            registry = DatasetRegistry(args.workspace / "dataset_registry.json")
            _print({**catalog.sync_learning_registry(registry, rows),
                    "registry": registry.summary()})
        elif args.command == "verify":
            report = catalog.verify(
                full=not args.quick, recording_ids=args.recordings,
                trusted_head=args.trusted_head,
            )
            _print(report)
            return 1 if report["missing_locations"] or report["changed_sources"] or not report[
                "materialised_view_matches_journal"
            ] else 0
        elif args.command == "summary":
            _print(catalog.public_summary())
        elif args.command == "learning-view":
            _print(catalog.learning_view())
        elif args.command == "leak-check":
            findings = catalog.leak_check(args.files)
            _print({"findings": findings})
            return 1 if findings else 0
    except CatalogError as exc:
        print(f"拒否: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
