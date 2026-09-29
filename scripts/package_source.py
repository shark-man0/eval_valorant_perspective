"""Package source/config/tests only; never include local recordings or credentials."""

from __future__ import annotations

import argparse
import hashlib
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile, ZipInfo

DIRECTORIES = {"src", "tests", "config", "schemas", ".github", "scripts"}
ROOT_EXTENSIONS = {".md", ".toml", ".ps1", ".spec", ".txt"}
EXCLUDED_PARTS = {"__pycache__", ".pytest_cache", ".mypy_cache", ".ruff_cache"}


def package(project: Path, destination: Path) -> tuple[int, str]:
    project = project.resolve()
    destination = destination.resolve()
    if destination.is_relative_to(project):
        raise ValueError("Choose an output ZIP outside the source project")
    members = []
    for path in sorted(project.rglob("*")):
        relative = path.relative_to(project)
        if path.is_symlink() or not path.is_file():
            continue
        if any(part in EXCLUDED_PARTS or part.endswith(".egg-info") for part in relative.parts):
            continue
        if relative.parts[0] in DIRECTORIES:
            if path.suffix in {".pyc", ".db", ".sqlite", ".mp4", ".mkv"}:
                continue
        elif len(relative.parts) != 1 or (
            path.suffix not in ROOT_EXTENSIONS and path.name != ".gitignore"
        ):
            continue
        members.append((path, relative))
    destination.parent.mkdir(parents=True, exist_ok=True)
    # Create-only: preserve any earlier deliverable rather than overwrite it.
    with ZipFile(destination, "x", compression=ZIP_DEFLATED, compresslevel=9) as archive:
        for path, relative in members:
            info = ZipInfo(f"{project.name}/{relative.as_posix()}", (2020, 1, 1, 0, 0, 0))
            info.compress_type = ZIP_DEFLATED
            info.external_attr = 0o644 << 16
            archive.writestr(info, path.read_bytes())
    with ZipFile(destination) as archive:
        if archive.testzip() is not None:
            raise RuntimeError("ZIP CRC verification failed")
    return len(members), hashlib.sha256(destination.read_bytes()).hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    count, digest = package(Path(__file__).resolve().parents[1], args.output)
    print(f"{args.output.resolve()}\nFiles: {count}\nSHA256: {digest}")


if __name__ == "__main__":
    main()
