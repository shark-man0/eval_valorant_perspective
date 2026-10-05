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
    return p


def run_case(args, *, root=APP_ROOT, runner=subprocess.run, probe=None) -> int:
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

    def command(argv, name, allowed=(0,)):
        with (output / f"{name}.log").open("wb") as log:
            result = runner(
                argv,
                cwd=root,
                stdout=log,
                stderr=subprocess.STDOUT,
                check=False,
                env={**os.environ, "PYTHONUTF8": "1"},
            )
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
        settings = {}
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
        print("Running existing E2E pipeline; detailed logs stay in outputs/.", flush=True)
        save_context(output, metadata, assertions_sha256=assertions_hash)
        command(cmd, "analyzer")
        raw = read_json(output / "raw_processing.json")
        if raw.get("status") != "complete":
            raise CaseError("ANALYZER_INCOMPLETE")
        trace = read_json(output / "e2e_trace.json")
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
        if args.include_evidence and code:
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
    try:
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
