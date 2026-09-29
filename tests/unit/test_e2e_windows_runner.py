import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "run_e2e_windows.ps1"


def test_windows_runner_uses_script_root_and_argument_array() -> None:
    source = SCRIPT.read_text(encoding="utf-8")

    assert "$RepoRoot = $PSScriptRoot" in source
    assert "Push-Location $RepoRoot" in source
    assert "Build-E2EArguments" in source
    assert "$PythonArgArray = Build-E2EArguments" in source
    assert "& $VenvPython @PythonArgArray" in source
    assert "Invoke-Expression" not in source
    assert "--video-id" in source
    assert "--validation-pack" in source
    assert "--hud-layout" in source
    assert "--visual-profile" in source
    assert "--manual-map-id" in source
    assert "--map-client-build" in source
    assert "--include-evidence" in source
    assert "--evidence-limit" in source


def test_windows_runner_does_not_resolve_implicit_video_or_pack_itself() -> None:
    source = SCRIPT.read_text(encoding="utf-8")

    assert "VALORANT_E2E_VIDEO" not in source
    assert "VALORANT_E2E_PACK" not in source
    assert ".env.local" not in source


def test_windows_runner_propagates_pipeline_failure_and_checks_toolchain() -> None:
    source = SCRIPT.read_text(encoding="utf-8")

    assert "function Assert-E2ESuccess([int] $ExitCode)" in source
    assert "if ($ExitCode -ne 0)" in source
    assert "Stop-Runner \"E2E pipeline failed" in source
    assert "Python 3.12 is required" in source
    assert "existing project virtual environment must use Python 3.12" in source
    assert "e2e-dependencies.sha256" in source
    assert "pip check" in source
    assert 'foreach ($ToolName in @("ffmpeg", "ffprobe"))' in source
    assert "Test-Path -LiteralPath $Video -PathType Leaf" in source


@pytest.mark.skipif(shutil.which("pwsh") is None, reason="PowerShell Core is unavailable")
def test_windows_runner_rejects_missing_required_video_id(tmp_path: Path) -> None:
    result = subprocess.run(
        ["pwsh", "-NoProfile", "-NonInteractive", "-File", str(SCRIPT)],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode != 0
    assert "VideoId" in result.stderr


@pytest.mark.skipif(shutil.which("pwsh") is None, reason="PowerShell Core is unavailable")
def test_windows_runner_power_shell_behavior_harness(tmp_path: Path) -> None:
    result = subprocess.run(
        [
            "pwsh",
            "-NoProfile",
            "-NonInteractive",
            "-File",
            str(ROOT / "tests/e2e/windows_runner_tests.ps1"),
            "-RunnerPath",
            str(SCRIPT),
        ],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert "behavior tests passed" in result.stdout
