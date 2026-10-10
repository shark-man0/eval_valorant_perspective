"""Local video -> existing E2E CLIs -> bounded share report. Never commits or pushes."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import re
import subprocess
import sys
import time
from contextlib import suppress
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

APP_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(APP_ROOT))
sys.path.insert(0, str(APP_ROOT / "src"))


from scripts.e2e.runtime import (  # noqa: E402
    CaseError,
    check_environment,
    local_settings,
    native_path,
    resolve_tool,
    setting,
)


def read_json(path: Path) -> dict:
    def reject(value):
        raise ValueError("Non-finite JSON")

    value = json.loads(path.read_text(encoding="utf-8"), parse_constant=reject)
    if not isinstance(value, dict):
        raise ValueError("JSON object required")
    return value


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def valid_id(value: str) -> str:
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,63}", value):
        raise CaseError("INVALID_VIDEO_ID")
    if value.upper() in {
        "CON",
        "PRN",
        "AUX",
        "NUL",
        *(f"COM{i}" for i in range(10)),
        *(f"LPT{i}" for i in range(10)),
    }:
        raise CaseError("INVALID_VIDEO_ID")
    return value


def local_video_setting(root: Path) -> str | None:
    return local_settings(root).get("VALORANT_E2E_VIDEO")


def resolve_inputs(args, root: Path, env=None) -> tuple[Path, Path]:
    env = os.environ if env is None else env
    local = local_settings(root)
    video = setting(args.video, "VALORANT_E2E_VIDEO", env, local)
    if not video:
        raise CaseError("VIDEO_NOT_CONFIGURED")
    pack = setting(args.validation_pack, "VALORANT_E2E_PACK", env, local)
    return native_path(video, root), (
        native_path(pack, root) if pack else root.parent / "valorant_e2e_validation_pack_v3"
    )


def resolve_options(args, root: Path, env=None):
    env = os.environ if env is None else env
    local = local_settings(root)
    args = argparse.Namespace(**vars(args))
    for name in ("hud_layout", "visual_profile", "manual_map_id", "map_client_build"):
        value = setting(getattr(args, name), "VALORANT_E2E_" + name.upper(), env, local)
        if value and name.endswith(("layout", "profile")):
            value = str(native_path(value, root))
        setattr(args, name, value or "")
    for name in ("ffmpeg", "ffprobe", "git"):
        field = name + "_bin"
        value = setting(getattr(args, field, None), name.upper() + "_BIN", env, local)
        setattr(args, field, resolve_tool(name, explicit=value, env={}, root=root))
    return args


def pack_identity(pack: Path) -> tuple[dict, str, str]:
    required = (
        "MANIFEST.json",
        "tests/validate_pack.py",
        "tests/reference_evaluator.py",
        "tests/generated/e2e_assertions_v3.json",
        "schemas/e2e_output_trace_schema_v1.json",
    )
    if not all((pack / item).is_file() for item in required):
        raise CaseError("VALIDATION_PACK_MISSING")
    manifest = read_json(pack / "MANIFEST.json")
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,95}", str(manifest.get("name", ""))):
        raise CaseError("VALIDATION_PACK_INVALID")
    if not re.fullmatch(r"[a-f0-9]{64}", str(manifest.get("source_sha256", ""))):
        raise CaseError("VALIDATION_PACK_SOURCE_HASH_MISSING")
    digest = hashlib.sha256()
    # Fingerprint GT, assertions, schemas and evaluator code, not cache/platform files.
    for path in sorted(
        pack.rglob("*"),
        key=lambda p: p.relative_to(pack).as_posix(),
    ):
        if path.is_file() and path.suffix in {".json", ".py"}:
            digest.update(path.relative_to(pack).as_posix().encode())
            digest.update(bytes.fromhex(sha256_file(path)))
    return manifest, digest.hexdigest(), sha256_file(pack / required[3])


def git_identity(root: Path, runner=subprocess.run, executable=None) -> dict:
    def git(*args):
        result = runner(
            [executable or resolve_tool("git", root=root), "-C", str(root), *args],
            capture_output=True,
            check=False,
        )
        if result.returncode:
            raise CaseError("GIT_IDENTITY_UNAVAILABLE")
        return result.stdout if isinstance(result.stdout, bytes) else result.stdout.encode()

    commit = git("rev-parse", "HEAD").decode().strip()
    if not re.fullmatch(r"[a-f0-9]{40,64}", commit):
        raise CaseError("GIT_IDENTITY_UNAVAILABLE")
    status = git("status", "--porcelain", "-z", "--untracked-files=all")
    # Diff and untracked file bytes are hashed locally, never emitted to the report.
    scope = ("--", ".", ":(exclude)e2e_reports", ":(exclude)datasets/manifests")
    digest = hashlib.sha256(git("diff", "HEAD", "--binary", *scope))
    # Generated reports changing do not create a new analyzer-code history key.
    untracked = git("ls-files", "--others", "--exclude-standard", "-z", *scope)
    for filename in untracked.split(b"\0"):
        if filename:
            path = root / os.fsdecode(filename)
            if path.is_file() and not path.is_symlink():
                digest.update(filename)
                digest.update(bytes.fromhex(sha256_file(path)))
    return {
        "analyzer_commit": commit,
        "git_is_dirty": bool(status),
        "git_dirty_fingerprint": digest.hexdigest(),
    }


def validate_manifest(value: dict, root=APP_ROOT) -> None:
    import jsonschema

    jsonschema.validate(value, read_json(root / "datasets/manifest.schema.json"))
    valid_id(value["video_id"])
    if not all(math.isfinite(value[k]) for k in ("duration_sec", "fps")):
        raise CaseError("MANIFEST_INVALID")


def make_manifest(video_id, video, digest, metadata, pack, pack_hash, assertions_hash):
    return {
        "schema_version": 1,
        "video_id": video_id,
        "filename": video_id + video.suffix.lower(),
        "sha256": digest,
        "duration_sec": metadata.duration_sec,
        "width": metadata.width,
        "height": metadata.height,
        "fps": metadata.fps,
        "audio_tracks": len(metadata.audio_tracks),
        "validation_pack": pack["name"],
        "validation_pack_sha256": pack_hash,
        "assertions_sha256": assertions_hash,
    }


def match_manifest(expected, actual):
    if expected["sha256"] != actual["sha256"]:
        raise CaseError("VIDEO_SHA256_MISMATCH")
    for key in (
        "video_id",
        "width",
        "height",
        "audio_tracks",
        "validation_pack",
        "validation_pack_sha256",
        "assertions_sha256",
    ):
        if expected[key] != actual[key]:
            raise CaseError("MANIFEST_METADATA_OR_PACK_MISMATCH")
    if (
        abs(expected["duration_sec"] - actual["duration_sec"]) > 0.05
        or abs(expected["fps"] - actual["fps"]) > 0.01
    ):
        raise CaseError("MANIFEST_METADATA_OR_PACK_MISMATCH")


def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--video")
    p.add_argument("--video-id")
    p.add_argument("--validation-pack")
    p.add_argument("--register", action="store_true")
    p.add_argument("--hud-layout")
    p.add_argument("--visual-profile")
    p.add_argument("--manual-map-id", default="")
    p.add_argument("--map-client-build", default="")
    p.add_argument("--include-evidence", action="store_true")
    p.add_argument("--evidence-limit", type=int, choices=range(1, 11), default=3)
    p.add_argument("--output", help="New private run directory; default is unique outputs/e2e run")
    p.add_argument(
        "--manifest", help="Dataset manifest; default datasets/manifests/<video-id>.json"
    )
    p.add_argument("--ffmpeg-bin")
    p.add_argument("--ffprobe-bin")
    p.add_argument("--git-bin")
    p.add_argument(
        "--check-environment",
        action="store_true",
        help="Check Python, headless imports and tools only; no analysis/evaluation",
    )
    p.add_argument("--mode", choices=("targeted", "sampled", "full"), default="full")
    p.add_argument("--frame-suite")
    p.add_argument("--native-png-budget", type=int)
    p.add_argument("--scene-reference-profile")
    p.add_argument("--unedited-input-contract")
    p.add_argument("--category", action="append", default=[])
    p.add_argument("--previous", help="Comparable previous run directory or runtime_summary.json")
    p.add_argument("--cache-dir", default="outputs/e2e_cache")
    return p


def run_case(args, *, root=APP_ROOT, runner=subprocess.run, probe=None) -> int:
    from scripts.e2e.run_metrics import FullRunLock

    budget = getattr(args, "native_png_budget", None)
    scene = getattr(args, "scene_reference_profile", None)
    assurance = getattr(args, "unedited_input_contract", None)
    if (budget is not None or scene or assurance) and (
        getattr(args, "mode", "full") != "full"
        or type(budget) is not int or budget <= 0 or not (scene or assurance)
        or bool(scene and assurance)
    ):
        raise CaseError("NATIVE_LIFECYCLE_REQUIRES_FULL_SOURCE_BUDGET_AND_SCENE_PROFILE")
    if getattr(args, "mode", "full") == "full":
        if getattr(args, "frame_suite", None) or getattr(args, "category", []):
            raise CaseError("BOUNDED_OPTIONS_REQUIRE_BOUNDED_MODE")
        with FullRunLock(root):
            return _run_case(args, root=root, runner=runner, probe=probe)
    return _run_case(args, root=root, runner=runner, probe=probe)


def _run_case(args, *, root=APP_ROOT, runner=subprocess.run, probe=None) -> int:
    from scripts.e2e.report_context import save_context
    from scripts.e2e.share_report import export_report
    from valorant_ai_coach.video import VideoService

    try:
        video_id = valid_id(args.video_id or "")
    except CaseError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    stamp = datetime.now(UTC).isoformat()
    output = (
        native_path(args.output, root)
        if getattr(args, "output", None)
        else (
            root
            / "outputs/e2e"
            / video_id
            / (datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ") + "-" + uuid4().hex[:8])
        )
    )
    output.mkdir(parents=True, exist_ok=False)
    shared = root / "e2e_reports" / video_id
    metadata = {
        "video_id": video_id,
        "source_sha256": None,
        "analyzer_commit": None,
        "git_is_dirty": None,
        "executed_at": stamp,
        "manual_map_id": args.manual_map_id,
    }
    raw, trace, assertions = {}, {}, {}
    evaluation = {"pass": False, "schema_valid": False, "failures": []}
    assertions_hash = None
    mode = getattr(args, "mode", "full")
    started = time.perf_counter()
    command_results = []
    orchestration_stages = {}
    suite = None
    from scripts.e2e.run_metrics import code_fingerprint

    initial_code = code_fingerprint(root)
    initial_settings = None

    def record_stage(name, seconds):
        row = orchestration_stages.setdefault(name, {"calls": 0, "total_sec": 0.0})
        row["calls"] += 1
        row["total_sec"] += seconds

    def command(argv, name, allowed=(0,)):
        command_started = time.perf_counter()
        with (output / f"{name}.log").open("wb") as log:
            result = runner(
                argv,
                cwd=root,
                stdout=log,
                stderr=subprocess.STDOUT,
                check=False,
                env={**os.environ, "PYTHONUTF8": "1"},
            )
        seconds = time.perf_counter() - command_started
        command_results.append(
            {"command": name, "exit_code": result.returncode, "wall_sec": seconds}
        )
        temporary = output / ".command_results.tmp"
        temporary.write_text(json.dumps(command_results, indent=2) + "\n", encoding="utf-8")
        temporary.replace(output / "command_results.json")
        if name == "evaluation":
            record_stage("evaluator", seconds)
        if result.returncode not in allowed:
            raise CaseError(name.upper() + "_FAILED")
        return result.returncode

    try:
        args = resolve_options(args, root)
        metadata["manual_map_id"] = args.manual_map_id
        metadata.update(git_identity(root, runner, args.git_bin))
        video, pack = resolve_inputs(args, root)
        if not video.is_file():
            raise CaseError("VIDEO_NOT_FOUND")
        try:
            digest = sha256_file(video)
        except OSError as exc:
            raise CaseError("VIDEO_UNREADABLE") from exc
        metadata["source_sha256"] = digest
        pack_manifest, pack_hash, assertions_hash = pack_identity(pack)
        metadata.update(validation_pack=pack_manifest["name"], validation_pack_sha256=pack_hash)
        if pack_manifest["source_sha256"] != digest:
            raise CaseError("VALIDATION_PACK_VIDEO_SHA256_MISMATCH")
        assertions = read_json(pack / "tests/generated/e2e_assertions_v3.json")
        manifest_path = (
            native_path(args.manifest, root)
            if getattr(args, "manifest", None)
            else root / "datasets/manifests" / f"{video_id}.json"
        )
        if args.register and manifest_path.exists():
            raise CaseError("MANIFEST_ALREADY_EXISTS")
        expected = None
        if not args.register:
            if not manifest_path.is_file():
                raise CaseError("MANIFEST_MISSING_USE_REGISTER")
            expected = read_json(manifest_path)
            validate_manifest(expected, root)
            if expected["sha256"] != digest:
                raise CaseError("VIDEO_SHA256_MISMATCH")
        for tool in ("ffmpeg", "ffprobe"):
            executable = getattr(args, tool + "_bin")
            command([executable, "-version"], tool)
        try:
            video_metadata = (probe or VideoService(args.ffprobe_bin).probe)(video)
        except Exception as exc:
            raise CaseError("FFPROBE_METADATA_FAILED") from exc
        actual = make_manifest(
            video_id, video, digest, video_metadata, pack_manifest, pack_hash, assertions_hash
        )
        validate_manifest(actual, root)
        if expected:
            match_manifest(expected, actual)
        command(
            [
                sys.executable,
                str(pack / "tests/validate_pack.py"),
                "--project-root",
                str(root / "src"),
            ],
            "validation_pack",
        )
        if args.register:
            manifest_path.parent.mkdir(parents=True, exist_ok=True)
            with manifest_path.open("x", encoding="utf-8") as stream:
                stream.write(json.dumps(actual, indent=2, allow_nan=False) + "\n")
            print(f"Registered dataset: datasets/manifests/{video_id}.json", flush=True)
        cmd = [
            sys.executable,
            str(root / "tests/e2e/run_real_video.py"),
            "--source-video",
            str(video),
            "--output",
            str(output),
            "--ffmpeg-bin",
            args.ffmpeg_bin,
            "--ffprobe-bin",
            args.ffprobe_bin,
        ]
        native_settings = {}
        if getattr(args, "native_png_budget", None) is not None:
            native_settings = {"native_png_budget": args.native_png_budget}
            cmd.extend(["--native-png-budget", str(args.native_png_budget)])
            if getattr(args, "unedited_input_contract", None):
                from valorant_ai_coach.hud.unedited_input import UneditedInputContract

                contract_path = native_path(args.unedited_input_contract, root)
                native_settings["unedited_input_contract"] = UneditedInputContract.load(
                    contract_path, source_video_sha256=digest,
                ).fingerprint
                cmd.extend(["--unedited-input-contract", str(contract_path)])
            else:
                from valorant_ai_coach.hud.scene_source_binding import SceneSourceBinding

                scene_path = native_path(args.scene_reference_profile, root)
                native_settings["scene_source_binding"] = SceneSourceBinding.load(
                    scene_path,
                ).fingerprint()
                cmd.extend(["--scene-reference-profile", str(scene_path)])
        settings = dict(native_settings)
        for option in ("hud_layout", "visual_profile", "manual_map_id", "map_client_build"):
            value = getattr(args, option)
            if value:
                cmd.extend(["--" + option.replace("_", "-"), value])
                settings[option] = (
                    sha256_file(Path(value)) if option.endswith(("layout", "profile")) else value
                )
        from valorant_ai_coach.hud.templates import HudTemplateProfile

        layout = (
            Path(args.hud_layout) if args.hud_layout else root / "config/hud_layout_1080p_v3.json"
        )
        sidecar = layout.with_suffix(".templates.json")
        metadata["hud_layout_sha256"] = sha256_file(layout) if layout.is_file() else None
        if sidecar.is_file():
            settings["hud_assets"] = HudTemplateProfile.load(sidecar).fingerprint(layout)
        metadata["settings_fingerprint"] = hashlib.sha256(
            json.dumps(settings, sort_keys=True).encode()
        ).hexdigest()
        initial_settings = metadata["settings_fingerprint"]
        if mode != "full":
            from scripts.e2e.frame_suite import load_suite, selected_frames

            suite_path = native_path(
                getattr(args, "frame_suite", None) or f"datasets/e2e_suites/{video_id}/{mode}.json",
                root,
            )
            suite = load_suite(
                suite_path,
                mode=mode,
                source_sha256=digest,
                categories=getattr(args, "category", []),
            )
            if suite["video_id"] != video_id:
                raise CaseError("SUITE_VIDEO_ID_MISMATCH")
            points = selected_frames(suite, getattr(args, "category", []))
            if not points:
                raise CaseError("EMPTY_FRAME_SELECTION")
            frame_input = {
                "schema_version": 1,
                "mode": mode,
                "input_scope": "isolated_points",
                "source_sha256": digest,
                "calibration_prefix": suite["calibration_prefix"],
                "pts_sec": [row["pts_sec"] for row in points],
            }
            (output / "frame_input.json").write_text(
                json.dumps(frame_input, indent=2) + "\n", encoding="utf-8"
            )
            cmd.extend(
                [
                    "--frame-input",
                    str(output / "frame_input.json"),
                    "--cache-dir",
                    str(native_path(getattr(args, "cache_dir", "outputs/e2e_cache"), root)),
                ]
            )
        print(f"Running {mode} E2E; detailed logs stay in outputs/.", flush=True)
        save_context(output, metadata, assertions_sha256=assertions_hash)
        command(cmd, "analyzer")
        raw = read_json(output / "raw_processing.json")
        if raw.get("status") != "complete":
            raise CaseError("ANALYZER_INCOMPLETE")
        trace = read_json(output / "e2e_trace.json")
        if mode == "full":
            code = command(
                [
                    sys.executable,
                    str(root / "tests/e2e/evaluate_saved_trace.py"),
                    "--pack",
                    str(pack),
                    "--trace",
                    str(output / "e2e_trace.json"),
                    "--output",
                    str(output / "evaluation_report.json"),
                ],
                "evaluation",
                allowed=(0, 1),
            )
            evaluation = read_json(output / "evaluation_report.json")
            if evaluation.get("pass") is not (code == 0):
                raise CaseError("EVALUATOR_RESULT_INCONSISTENT")
        else:
            from scripts.e2e.frame_suite import evaluate_frames

            evaluation_started = time.perf_counter()
            actual_pixels = raw.get("replay_metadata", {}).get("decoded_pixel_sha256", {})
            pixel_mismatches = [
                {
                    "pts_sec": row["pts_sec"],
                    "expected": row["decoded_pixel_sha256"],
                    "actual": actual_pixels.get(str(row["pts_sec"])),
                }
                for row in suite["frames"]
                if "decoded_pixel_sha256" in row
                and actual_pixels.get(str(row["pts_sec"])) != row["decoded_pixel_sha256"]
            ]
            (output / "pixel_witness_diagnostics.json").write_text(
                json.dumps(
                    {
                        "checked_frames": sum(
                            "decoded_pixel_sha256" in row for row in suite["frames"]
                        ),
                        "mismatches": pixel_mismatches,
                    },
                    indent=2,
                )
                + "\n",
                encoding="utf-8",
            )
            if pixel_mismatches:
                raise CaseError("REVIEWED_PIXEL_WITNESS_MISMATCH")
            evaluation = evaluate_frames(suite, raw["observations"])
            evaluation["full_validation_pack_evaluated"] = False
            evaluation["temporal_assertions_evaluated"] = False
            code = 1 if evaluation["counts"]["failed"] else 0
            evaluation["pass"] = code == 0
            (output / "evaluation_report.json").write_text(
                json.dumps(evaluation, indent=2) + "\n", encoding="utf-8"
            )
            record_stage("evaluator", time.perf_counter() - evaluation_started)
        if sha256_file(video) != digest or code_fingerprint(root) != initial_code:
            raise CaseError("INPUT_OR_CODE_CHANGED_DURING_RUN")
        if pack_identity(pack)[1] != pack_hash:
            raise CaseError("VALIDATION_PACK_CHANGED_DURING_RUN")
        current_settings = dict(native_settings)
        if "unedited_input_contract" in native_settings:
            current_settings["unedited_input_contract"] = UneditedInputContract.load(
                contract_path, source_video_sha256=digest,
            ).fingerprint
        if "scene_source_binding" in native_settings:
            current_settings["scene_source_binding"] = (
                SceneSourceBinding.load(scene_path).fingerprint()
            )
        for option in ("hud_layout", "visual_profile", "manual_map_id", "map_client_build"):
            value = getattr(args, option)
            if value:
                current_settings[option] = (
                    sha256_file(Path(value)) if option.endswith(("layout", "profile")) else value
                )
        if metadata["hud_layout_sha256"] != (sha256_file(layout) if layout.is_file() else None):
            raise CaseError("PROFILE_CHANGED_DURING_RUN")
        if sidecar.is_file():
            current_settings["hud_assets"] = HudTemplateProfile.load(sidecar).fingerprint(layout)
        if (
            hashlib.sha256(json.dumps(current_settings, sort_keys=True).encode()).hexdigest()
            != initial_settings
        ):
            raise CaseError("PROFILE_CHANGED_DURING_RUN")
        if mode == "full" and args.include_evidence and code:
            from scripts.e2e.evidence import export_evidence

            metadata["evidence_files"] = export_evidence(
                video=video,
                trace=trace,
                evaluation=evaluation,
                assertions=assertions,
                output=output,
                shared=shared,
                limit=args.evidence_limit,
                ffprobe_bin=args.ffprobe_bin,
            )
    except Exception as exc:
        if not raw and (output / "raw_processing.json").is_file():
            with suppress(OSError, ValueError):
                raw = read_json(output / "raw_processing.json")
        error = str(exc) if isinstance(exc, CaseError) else "PREFLIGHT_OR_RUNTIME_FAILED"
        metadata["error_code"] = error
        evaluation = {**evaluation, "pass": False}
        # Exception text and local paths are not suitable for Git reports.
        (output / "error_code.json").write_text(json.dumps({"error_code": error}) + "\n")
        print(error, file=sys.stderr)
        code = 2
    save_context(output, metadata, assertions_sha256=assertions_hash, exit_code=code)
    report_started = time.perf_counter()
    try:
        if mode == "full":
            export_report(
                raw=raw,
                trace=trace,
                evaluation=evaluation,
                assertions=assertions,
                metadata=metadata,
                output_dir=shared,
            )
    except (OSError, ValueError):
        print(
            "SHARED_EXPORT_FAILED: local run and metadata retained for re-export.", file=sys.stderr
        )
        return 2
    record_stage("report_generation", time.perf_counter() - report_started)
    from scripts.e2e.runtime_summary import export_runtime_summary

    export_runtime_summary(
        output=output,
        shared=shared,
        mode=mode,
        raw=raw,
        evaluation=evaluation,
        suite=suite,
        frame_input=locals().get("frame_input"),
        metadata=metadata,
        assertions_hash=assertions_hash,
        stages=orchestration_stages,
        started=started,
        initial_code=initial_code,
        initial_settings=initial_settings,
        previous_path=getattr(args, "previous", None),
        root=root,
    )
    print(f"Generated {mode} runtime summary: {output / 'runtime_summary.json'}")
    if mode == "full":
        print(f"Generated share report: e2e_reports/{video_id}/summary.json")
    return code


def main(argv=None) -> int:
    p = parser()
    args = p.parse_args(argv)
    try:
        if args.check_environment:
            local = local_settings(APP_ROOT)
            overrides = {
                name: setting(
                    getattr(args, name + "_bin"), name.upper() + "_BIN", os.environ, local
                )
                for name in ("git", "ffmpeg", "ffprobe")
            }
            check_environment(root=APP_ROOT, overrides=overrides)
            print("Environment ready: Python 3.12; headless imports; git/ffmpeg/ffprobe.")
            return 0
        if not args.video_id:
            p.error("--video-id is required unless --check-environment is used")
        if sys.version_info[:2] != (3, 12):
            raise CaseError("PYTHON_312_REQUIRED")
        return run_case(args)
    except Exception as exc:
        print(
            str(exc) if isinstance(exc, CaseError) else "PREFLIGHT_OR_RUNTIME_FAILED",
            file=sys.stderr,
        )
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
