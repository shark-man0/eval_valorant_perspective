from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import tomllib
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Sequence

ROOT = Path(__file__).resolve().parents[2]
VERSION_PATTERN = re.compile(r"^[0-9]+\.[0-9]+\.[0-9]+(?:[A-Za-z0-9.+-]*)?$")


@dataclass(frozen=True, slots=True)
class ArtifactNames:
    portable_root: str
    portable_zip: str
    installer: str


def project_version(pyproject: Path | None = None) -> str:
    path = pyproject or ROOT / "pyproject.toml"
    with path.open("rb") as stream:
        value = tomllib.load(stream)["project"]["version"]
    if not isinstance(value, str) or not VERSION_PATTERN.fullmatch(value):
        raise ValueError(f"Unsupported project version: {value!r}")
    return value


def artifact_names(version: str) -> ArtifactNames:
    if not VERSION_PATTERN.fullmatch(version):
        raise ValueError(f"Unsupported project version: {version!r}")
    portable_root = f"VALORANT-AI-Coach-{version}-windows-x64"
    return ArtifactNames(
        portable_root=portable_root,
        portable_zip=f"{portable_root}.zip",
        installer=f"VALORANT-AI-Coach-Setup-{version}-x64.exe",
    )


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def write_checksums(paths: Sequence[Path], output: Path) -> None:
    entries = sorted((Path(path) for path in paths), key=lambda item: item.name.casefold())
    if not entries:
        raise ValueError("At least one artifact is required")
    for path in entries:
        if not path.is_file():
            raise FileNotFoundError(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        "".join(f"{sha256_file(path)}  {path.name}\n" for path in entries),
        encoding="utf-8",
        newline="\n",
    )


def validate_release_tag(tag: str, version: str) -> None:
    expected = f"v{version}"
    if tag != expected:
        raise ValueError(f"Release tag {tag!r} does not match project version {expected!r}")


def write_build_info(
    output: Path,
    *,
    commit: str,
    python_version: str,
    dependency_file: Path,
    build_command: str,
) -> None:
    version = project_version()
    if not re.fullmatch(r"[0-9a-fA-F]{7,64}", commit):
        raise ValueError("commit must be a hexadecimal Git commit id")
    if not dependency_file.is_file():
        raise FileNotFoundError(dependency_file)
    payload = {
        "schema_version": 1,
        "application": "VALORANT AI Coach",
        "version": version,
        "platform": "windows",
        "architecture": "x64",
        "commit": commit.lower(),
        "python": python_version.strip(),
        "constraints": {
            "file": "constraints-windows.txt",
            "sha256": sha256_file(ROOT / "constraints-windows.txt"),
        },
        "resolved_dependencies": {
            "file": dependency_file.name,
            "sha256": sha256_file(dependency_file),
        },
        "build_command": build_command,
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Windows release helper")
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("version")

    names = subparsers.add_parser("names")
    names.add_argument("--json", action="store_true")

    tag = subparsers.add_parser("validate-tag")
    tag.add_argument("--tag", required=True)

    checksums = subparsers.add_parser("checksums")
    checksums.add_argument("--output", type=Path, required=True)
    checksums.add_argument("artifacts", nargs="+", type=Path)

    build_info = subparsers.add_parser("build-info")
    build_info.add_argument("--output", type=Path, required=True)
    build_info.add_argument("--commit", required=True)
    build_info.add_argument("--python", required=True)
    build_info.add_argument("--dependencies", type=Path, required=True)
    build_info.add_argument("--build-command", required=True)

    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    version = project_version()

    if args.command == "version":
        print(version)
        return 0
    if args.command == "names":
        names = artifact_names(version)
        if args.json:
            print(json.dumps(asdict(names), separators=(",", ":")))
        else:
            print(names.portable_zip)
            print(names.installer)
        return 0
    if args.command == "validate-tag":
        validate_release_tag(args.tag, version)
        return 0
    if args.command == "checksums":
        write_checksums(args.artifacts, args.output)
        return 0
    if args.command == "build-info":
        write_build_info(
            args.output,
            commit=args.commit,
            python_version=args.python,
            dependency_file=args.dependencies,
            build_command=args.build_command,
        )
        return 0
    raise AssertionError(args.command)


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, KeyError, TypeError, ValueError) as exc:
        print(f"release helper error: {exc}", file=sys.stderr)
        raise SystemExit(2) from exc
