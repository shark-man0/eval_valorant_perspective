"""Portable E2E boundary tests; synthetic IO is not real-video accuracy proof."""

import ast
import os
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest
import test_e2e_dataset_runner as existing

from scripts.e2e import run_dataset_case as runner
from scripts.e2e import runtime


@pytest.fixture
def case(tmp_path, monkeypatch):
    return existing.case.__wrapped__(tmp_path, monkeypatch)


def test_root_resolution_does_not_depend_on_cwd(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    assert runtime.repository_root(Path(runner.__file__)) == runner.APP_ROOT


def test_repo_relative_and_unicode_paths_do_not_depend_on_cwd(tmp_path, monkeypatch):
    root = tmp_path / "repo 空間"
    root.mkdir()
    monkeypatch.chdir(tmp_path)
    assert (
        runtime.native_path("資料/video with spaces.mp4", root)
        == (root / "資料" / "video with spaces.mp4").resolve()
    )
    absolute = root / "絶対.mp4"
    assert runtime.native_path(absolute, tmp_path) == absolute.resolve()


def test_foreign_windows_config_is_rejected_on_posix(tmp_path, monkeypatch):
    monkeypatch.setattr(runtime, "IS_WINDOWS", False)
    for value in (r"C:\data folder\clip.mp4", r"\\server\share\clip.mp4"):
        with pytest.raises(runtime.CaseError, match="FOREIGN_WINDOWS_PATH"):
            runtime.native_path(value, tmp_path)


@pytest.mark.skipif(os.name != "nt", reason="Host-native Windows path test")
def test_windows_path_preserves_drive_spaces_unicode(tmp_path):
    value = tmp_path / "録画 folder" / "video.mp4"
    assert runtime.native_path(str(value), tmp_path.parent) == value.resolve()


@pytest.mark.skipif(os.name == "nt", reason="Host-native POSIX path test")
def test_posix_absolute_path_preserved(tmp_path):
    assert runtime.native_path("/var/local/録画 folder/video.mp4", tmp_path) == Path(
        "/var/local/録画 folder/video.mp4"
    )


def test_video_and_pack_cli_env_local_default_precedence(tmp_path):
    (tmp_path / ".env.local").write_text(
        'VALORANT_E2E_VIDEO="local/video.mp4"\nVALORANT_E2E_PACK=local/pack\n',
        encoding="utf-8",
    )
    args = SimpleNamespace(video="cli/video.mp4", validation_pack="cli/pack")
    env = {"VALORANT_E2E_VIDEO": "env/video.mp4", "VALORANT_E2E_PACK": "env/pack"}
    assert runner.resolve_inputs(args, tmp_path, env) == (
        (tmp_path / args.video).resolve(),
        (tmp_path / args.validation_pack).resolve(),
    )
    args.video = args.validation_pack = None
    assert runner.resolve_inputs(args, tmp_path, env) == (
        (tmp_path / "env/video.mp4").resolve(),
        (tmp_path / "env/pack").resolve(),
    )
    assert runner.resolve_inputs(args, tmp_path, {}) == (
        (tmp_path / "local/video.mp4").resolve(),
        (tmp_path / "local/pack").resolve(),
    )
    (tmp_path / ".env.local").write_text("VALORANT_E2E_VIDEO=clip.mp4\n", encoding="utf-8")
    assert runner.resolve_inputs(args, tmp_path, {})[1] == (
        tmp_path.parent / "valorant_e2e_validation_pack_v3"
    )


def test_local_config_is_an_allowlist_and_never_executed(tmp_path):
    (tmp_path / ".env.local").write_text(
        "OTHER=secret\nVALORANT_E2E_VIDEO=$(touch forbidden).mp4\nVALORANT_E2E_VIDEO=second.mp4\n",
        encoding="utf-8",
    )
    assert runtime.local_settings(tmp_path) == {"VALORANT_E2E_VIDEO": "$(touch forbidden).mp4"}
    assert not (tmp_path / "forbidden").exists()


@pytest.mark.parametrize("name", ["ffmpeg", "ffprobe", "git"])
def test_tool_cli_env_path_precedence_and_missing(name, tmp_path, monkeypatch):
    seen = []

    def which(value):
        seen.append(value)
        return value if value != "missing" else None

    monkeypatch.setattr(runtime.shutil, "which", which)
    env = {name.upper() + "_BIN": "environment tool"}
    assert runtime.resolve_tool(name, explicit="cli tool", env=env) == "cli tool"
    assert runtime.resolve_tool(name, env=env) == "environment tool"
    assert runtime.resolve_tool(name, env={}) == name
    override = tmp_path / "tool 空間" / (name + ".exe")
    assert runtime.resolve_tool(name, explicit=str(override), env=env, root=tmp_path) == str(
        override.resolve()
    )
    with pytest.raises(runtime.CaseError, match=name.upper() + "_MISSING"):
        runtime.resolve_tool(name, explicit="missing", env=env)
    assert seen[-1] == "missing"  # Explicit invalid override never silently falls back.


@pytest.mark.parametrize("tool", ["ffmpeg", "ffprobe", "git"])
def test_missing_tool_prevents_analyzer_and_returns_2(case, monkeypatch, tool):
    monkeypatch.setattr(runtime.shutil, "which", lambda name: None if name == tool else name)
    assert existing.execute(case) == 2
    assert not any("run_real_video.py" in " ".join(c) for c in case.calls)


def test_unicode_paths_output_manifest_and_same_python_children(case):
    video = case.video.with_name("録画 with spaces.mp4")
    case.video.rename(video)
    case.args.video = str(video)
    case.args.output = "private run 空間"
    case.args.manifest = "manifests 空間/case.json"
    assert existing.execute(case) == 0
    assert (case.root / "private run 空間/e2e_trace.json").is_file()
    assert (case.root / "manifests 空間/case.json").is_file()
    python_calls = [c for c in case.calls if len(c) > 1 and c[1].endswith(".py")]
    assert len(python_calls) == 3
    assert all(c[0] == sys.executable for c in python_calls)
    analyzer = next(c for c in python_calls if c[1].endswith("run_real_video.py"))
    assert analyzer[analyzer.index("--source-video") + 1] == str(video.resolve())
    assert analyzer[analyzer.index("--ffprobe-bin") + 1] == "ffprobe"
    git_calls = [c for c in case.calls if c[0] == "git"]
    assert all(c[3] in {"rev-parse", "status", "diff", "ls-files"} for c in git_calls)


@pytest.mark.parametrize("code", [0, 1, 2])
def test_common_pipeline_exit_code_semantics(case, code):
    case.state["evaluation_code"] = code
    assert existing.execute(case) == code


def test_child_runtime_oserror_is_2_and_public_output_sanitized(case):
    def fail(cmd, **kwargs):
        raise OSError("private/secret runtime")

    case.command = fail
    assert existing.execute(case) == 2
    public = (case.root / "e2e_reports/match_001/summary.json").read_text()
    assert "secret" not in public


def test_headless_environment_never_imports_qt(monkeypatch, tmp_path):
    modules = []
    monkeypatch.setattr(runtime.importlib, "import_module", lambda name: modules.append(name))
    monkeypatch.setattr(runtime.shutil, "which", lambda name: name)
    assert set(runtime.check_environment(root=tmp_path)) == {"git", "ffmpeg", "ffprobe"}
    assert "cv2" in modules and all(not m.startswith("PySide6") for m in modules)


def test_source_factory_imports_without_gui_initialization():
    code = """import sys
class NoQt:
    def find_spec(self, fullname, path=None, target=None):
        if fullname.startswith('PySide6'):
            raise RuntimeError('Headless source factory imported Qt')
sys.meta_path.insert(0, NoQt())
from valorant_ai_coach.bootstrap import build_services
assert not any(x.startswith('PySide6') for x in sys.modules)
"""
    result = subprocess.run(
        [sys.executable, "-c", code],
        cwd=runner.APP_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr


def test_no_shell_strings_or_git_mutation_in_shared_runner():
    source = Path(runner.__file__).read_text(encoding="utf-8")
    tree = ast.parse(source)
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            assert not any(
                k.arg == "shell" and isinstance(k.value, ast.Constant) and k.value.value is True
                for k in node.keywords
            )
    assert all(
        'git("' + name + '"' not in source
        for name in ("add", "commit", "push", "pull", "reset", "checkout")
    )


def test_launchers_share_entrypoint_and_do_not_duplicate_validation():
    for name in ("run_e2e_windows.ps1", "run_e2e_pi.sh"):
        source = (runner.APP_ROOT / name).read_text(encoding="utf-8")
        assert "scripts/e2e/run_dataset_case.py" in source
        for forbidden in (
            "sha256",
            "validate_pack.py",
            "reference_evaluator",
            "pip install",
            "git commit",
            "ffprobe -version",
        ):
            assert forbidden not in source
    shell = (runner.APP_ROOT / "run_e2e_pi.sh").read_bytes()
    assert b"\r" not in shell and b'"$@"' in shell and b'exec "$PYTHON_RUNTIME"' in shell


def test_check_environment_cli_smoke():
    result = subprocess.run(
        [sys.executable, str(Path(runner.__file__)), "--check-environment"],
        cwd=runner.APP_ROOT.parent,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "Environment ready" in result.stdout


@pytest.mark.parametrize("failure", [ImportError, OSError])
def test_preflight_dependency_failure_is_controlled(failure, monkeypatch, tmp_path):
    def broken(name):
        raise failure("private library path")

    monkeypatch.setattr(runtime.importlib, "import_module", broken)
    with pytest.raises(runtime.CaseError, match="DEPENDENCY_UNAVAILABLE_NUMPY"):
        runtime.check_environment(root=tmp_path)


def test_preflight_rejects_wrong_python_version(monkeypatch, tmp_path):
    monkeypatch.setattr(runtime.sys, "version_info", (3, 13, 0))
    with pytest.raises(runtime.CaseError, match="PYTHON_312_REQUIRED"):
        runtime.check_environment(root=tmp_path)


def test_python_children_receive_utf8_even_on_legacy_windows_locale(case):
    original = case.command

    def command(argv, **kwargs):
        if len(argv) > 1 and argv[1].endswith(".py"):
            assert kwargs["env"]["PYTHONUTF8"] == "1"
        return original(argv, **kwargs)

    case.command = command
    assert existing.execute(case) == 0


@pytest.mark.parametrize("code", [0, 1, 2])
def test_posix_launcher_preserves_unicode_arguments_and_exit_code(tmp_path, code):
    # Git Bash verifies POSIX shell mechanics on Windows; it is not a Pi runtime.
    import shutil

    shell = (
        shutil.which("sh") if os.name != "nt" else str(Path("C:/Program Files/Git/bin/bash.exe"))
    )
    if not shell or not Path(shell).is_file():
        pytest.skip("POSIX shell unavailable")
    root = tmp_path / "launcher 空間"
    (root / ".venv/bin").mkdir(parents=True)
    (root / "scripts/e2e").mkdir(parents=True)
    launcher = root / "run_e2e_pi.sh"
    launcher.write_bytes((runner.APP_ROOT / "run_e2e_pi.sh").read_bytes())
    stub = root / ".venv/bin/python"
    stub.write_text(
        '#!/bin/sh\n[ "$1" = "$PWD/scripts/e2e/run_dataset_case.py" ] || exit 91\n'
        '[ "$2" = "--video" ] || exit 92\n[ "$3" = "録画 with spaces.mp4" ] || exit 93\n'
        "exit " + str(code) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    stub.chmod(0o755)
    syntax = subprocess.run([shell, "-n", str(launcher)], capture_output=True, check=False)
    assert syntax.returncode == 0, syntax.stderr
    result = subprocess.run(
        [shell, str(launcher), "--video", "録画 with spaces.mp4"],
        cwd=tmp_path,
        capture_output=True,
        check=False,
    )
    assert result.returncode == code, result.stderr


def test_optional_settings_local_env_cli_and_report_consistency(case, monkeypatch):
    import json

    (case.root / ".env.local").write_text(
        "VALORANT_E2E_MANUAL_MAP_ID=summit\nVALORANT_E2E_HUD_LAYOUT=profiles/hud.json\n",
        encoding="utf-8",
    )
    resolved = runner.resolve_options(case.args, case.root, {})
    assert resolved.manual_map_id == "summit"
    assert resolved.hud_layout == str((case.root / "profiles/hud.json").resolve())
    resolved = runner.resolve_options(
        case.args, case.root, {"VALORANT_E2E_MANUAL_MAP_ID": "env-map"}
    )
    assert resolved.manual_map_id == "env-map"
    case.args.manual_map_id = "cli-map"
    assert (
        runner.resolve_options(
            case.args, case.root, {"VALORANT_E2E_MANUAL_MAP_ID": "env-map"}
        ).manual_map_id
        == "cli-map"
    )
    # Run without the intentionally nonexistent diagnostic profile.
    (case.root / ".env.local").write_text(
        "VALORANT_E2E_MANUAL_MAP_ID=summit\n", encoding="utf-8"
    )
    case.args.manual_map_id = ""
    monkeypatch.delenv("VALORANT_E2E_MANUAL_MAP_ID", raising=False)
    assert existing.execute(case) == 0
    summary = json.loads((case.root / "e2e_reports/match_001/summary.json").read_text())
    assert summary["metadata"]["manual_map_id"] == "summit"


def test_existing_explicit_output_is_not_overwritten(case, monkeypatch):
    case.args.output = str(case.root / "already used")
    path = Path(case.args.output)
    path.mkdir()
    (path / "sentinel").write_text("original")
    monkeypatch.setattr(runner, "APP_ROOT", case.root)
    assert runner.main(["--video-id", "match_001", "--output", str(path)]) == 2
    assert (path / "sentinel").read_text() == "original"
    assert not case.calls
