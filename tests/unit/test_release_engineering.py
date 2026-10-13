from __future__ import annotations

import importlib.util
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MODULE_PATH = ROOT / "scripts" / "release" / "release_tools.py"
SPEC = ROOT / "VALORANT-AI-Coach.spec"
INSTALLER = ROOT / "installer" / "VALORANT-AI-Coach.iss"
WORKFLOW = ROOT / ".github" / "workflows" / "release-windows.yml"


def _load_release_tools():
    spec = importlib.util.spec_from_file_location("release_tools", MODULE_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_version_and_artifact_names_come_from_pyproject() -> None:
    tools = _load_release_tools()
    version = tools.project_version()
    assert re.fullmatch(r"\d+\.\d+\.\d+(?:[A-Za-z0-9.+-]*)?", version)
    names = tools.artifact_names(version)
    assert names.portable_zip == f"VALORANT-AI-Coach-{version}-windows-x64.zip"
    assert names.installer == f"VALORANT-AI-Coach-Setup-{version}-x64.exe"


def test_checksum_generation_is_sha256_and_stable(tmp_path: Path) -> None:
    tools = _load_release_tools()
    first = tmp_path / "b.zip"
    second = tmp_path / "a.exe"
    first.write_bytes(b"portable")
    second.write_bytes(b"installer")
    output = tmp_path / "SHA256SUMS.txt"

    tools.write_checksums([first, second], output)

    lines = output.read_text(encoding="utf-8").splitlines()
    assert [line.split("  ", 1)[1] for line in lines] == ["a.exe", "b.zip"]
    assert all(re.fullmatch(r"[0-9a-f]{64}  .+", line) for line in lines)


def test_pyinstaller_bundle_excludes_test_tree_and_remaps_default_mock_case() -> None:
    text = SPEC.read_text(encoding="utf-8")
    assert '"tests/cases/TC-029/input.json"' in text
    assert '"runtime/mock_cases/TC-029"' in text
    assert '(str(project / "tests"), "tests")' not in text
    assert 'str(project / "tests" / "cases")' not in text
    assert 'binaries=[]' in text


def test_installer_is_per_user_and_does_not_delete_user_data() -> None:
    text = INSTALLER.read_text(encoding="utf-8")
    assert "PrivilegesRequired=lowest" in text
    assert "DefaultDirName={localappdata}\\Programs\\VALORANT-AI-Coach" in text
    assert "AppId={{9E6020A8-1C44-4C70-9CB7-78E694AA1B41}" in text
    assert "[UninstallDelete]" not in text
    assert "ValorantAICoach\\app.db" not in text


def test_release_workflow_is_release_only() -> None:
    text = WORKFLOW.read_text(encoding="utf-8")
    assert "workflow_dispatch:" in text
    assert "tags:" in text
    assert '- "v*"' in text
    assert re.search(r"(?m)^\s{2}push:\s*$", text)
    assert "branches:" not in text
    assert "release create" not in text.lower()


def test_build_info_records_resolved_dependency_and_tool_versions(tmp_path: Path) -> None:
    tools = _load_release_tools()
    dependencies = tmp_path / "DEPENDENCIES.txt"
    dependencies.write_text("numpy==2.5.4\n", encoding="utf-8")
    output = tmp_path / "BUILD-INFO.json"
    tools.write_build_info(
        output, commit="a" * 40, python_version="Python 3.12.10",
        dependency_file=dependencies, build_command="test",
    )
    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["commit"] == "a" * 40
    assert payload["resolved_dependencies"]["sha256"] == tools.sha256_file(dependencies)
    assert payload["build_tools"]["pip"] is not None
    assert set(payload["build_tools"]) == {"pip", "setuptools", "wheel", "pyinstaller"}


def test_release_script_requires_pip_check_and_isolated_dependency_audit() -> None:
    script = (ROOT / "scripts/release/build_release.ps1").read_text(encoding="utf-8")
    assert 'Invoke-Checked $PythonExe @("-m", "pip", "check")' in script
    assert "work\\dependency-audit-venv" in script
    assert '"pip-audit==2.10.1"' in script
    assert '"--no-deps"' in script and '"DEPENDENCY-AUDIT.json"' in script
    assert 'Where-Object { $_ -notmatch "(?i)^valorant-ai-coach==" }' in script
