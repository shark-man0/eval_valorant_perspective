from __future__ import annotations

import sys
from pathlib import Path


class ResourceNotFoundError(FileNotFoundError):
    """Raised when an authoritative bundled resource cannot be located."""


def resource_root() -> Path:
    """Locate the project resources in editable and PyInstaller installations."""

    candidates: list[Path] = []
    bundle_root = getattr(sys, "_MEIPASS", None)
    if bundle_root:
        candidates.append(Path(bundle_root))
    module_path = Path(__file__).resolve()
    candidates.extend((module_path.parents[2], Path.cwd()))
    for candidate in candidates:
        if (candidate / "schemas" / "round_package_schema_v2.json").is_file() and (
            candidate / "config" / "valorant_evaluation_rules_v4.json"
        ).is_file():
            return candidate
    searched = ", ".join(str(path) for path in candidates)
    raise ResourceNotFoundError(f"正本リソースが見つかりません。検索先: {searched}")


def resource_path(relative_path: str | Path) -> Path:
    path = resource_root() / Path(relative_path)
    if not path.is_file():
        raise ResourceNotFoundError(f"リソースが見つかりません: {relative_path}")
    return path


def executable_path(configured: str, name: str) -> str:
    """Resolve an optionally bundled FFmpeg tool without overriding custom paths."""
    value = str(configured).strip() or name
    if value.lower() not in {name.lower(), f"{name.lower()}.exe"}:
        return value
    bundle_root = getattr(sys, "_MEIPASS", None)
    if bundle_root:
        candidates = (
            Path(bundle_root) / "bin" / f"{name}.exe",
            Path(bundle_root) / "bin" / name,
        )
        for candidate in candidates:
            if candidate.is_file():
                return str(candidate)
    return value
