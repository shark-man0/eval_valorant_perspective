from __future__ import annotations

import zipfile
from pathlib import Path

from scripts.package_source import package


def test_source_package_excludes_private_runtime_artifacts(tmp_path: Path) -> None:
    project = tmp_path / "project"
    (project / "src").mkdir(parents=True)
    (project / "config").mkdir()
    (project / "scripts").mkdir()
    (project / "src" / "app.py").write_text("print('safe')\n", encoding="utf-8")
    (project / "config" / "canonical.json").write_text("{}\n", encoding="utf-8")

    private_files = [
        project / "src" / ".env",
        project / "src" / ".env.local",
        project / "config" / "hud_layout.json",
        project / "config" / "hud_layout.templates.json",
        project / "config" / "settings.json",
        project / "config" / "credentials.json",
        project / "config" / "secrets.json",
        project / "config" / "api_key.txt",
        project / "scripts" / "private.key",
        project / "scripts" / "runtime.log",
        project / "scripts" / "cache.sqlite3",
        project / "scripts" / "recording.mp4",
        project / "scripts" / "recording.avi",
    ]
    for path in private_files:
        path.write_text("private\n", encoding="utf-8")

    target = tmp_path / "source.zip"
    package(project, target)

    with zipfile.ZipFile(target) as archive:
        names = set(archive.namelist())

    prefix = f"{project.name}/"
    assert prefix + "src/app.py" in names
    assert prefix + "config/canonical.json" in names
    for private in private_files:
        assert prefix + private.relative_to(project).as_posix() not in names


def test_source_package_does_not_overwrite_existing_archive(tmp_path: Path) -> None:
    project = tmp_path / "project"
    (project / "src").mkdir(parents=True)
    (project / "src" / "app.py").write_text("pass\n", encoding="utf-8")
    target = tmp_path / "source.zip"
    target.write_bytes(b"original")

    try:
        package(project, target)
    except FileExistsError:
        pass
    else:
        raise AssertionError("package() must not overwrite an existing archive")

    assert target.read_bytes() == b"original"
