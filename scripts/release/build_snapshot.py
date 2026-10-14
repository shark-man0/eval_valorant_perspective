"""Compare two independently built Windows PyInstaller payloads without hiding drift."""

from __future__ import annotations

import argparse
import csv
import hashlib
import importlib.metadata
import json
import re
import sys
from pathlib import Path

COMMIT_RE = re.compile(r"^[0-9a-f]{40}$")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _write_json(path: Path, document: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(document, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def _record_rows(path: Path) -> dict[str, str]:
    """Hash each RECORD CSV row separately; keep original bytes in the package."""
    with path.open("r", encoding="utf-8", newline="") as stream:
        rows = list(csv.reader(stream))
    result: dict[str, str] = {}
    for row in rows:
        if len(row) != 3:
            raise ValueError(f"malformed installed-package RECORD: {path.name}")
        name = row[0].replace("\\", "/")
        if name in result:
            raise ValueError(f"duplicate installed-package RECORD row: {name}")
        # Avoid exposing absolute runner paths in public audit artifacts.
        if name.startswith("/") or re.match(r"^[A-Za-z]:/", name):
            name = "absolute-path-sha256:" + hashlib.sha256(name.encode()).hexdigest()
        result[name] = hashlib.sha256(
            json.dumps(row, ensure_ascii=True, separators=(",", ":")).encode()
        ).hexdigest()
    return result


def _install_artifacts(report: Path) -> dict[str, list]:
    """Record pip distribution archive SHA-256 without exposing index URLs."""
    payload = json.loads(report.read_text(encoding="utf-8"))
    if not isinstance(payload.get("install"), list):
        raise ValueError("pip install report must contain an install list")
    hashed: list[dict[str, str]] = []
    unhashed: list[dict[str, str]] = []
    for entry in payload["install"]:
        metadata = entry["metadata"]
        name, version = str(metadata["name"]).lower(), str(metadata["version"])
        info = entry.get("download_info", {})
        archive = info.get("archive_info", {})
        hashes = archive.get("hashes", {})
        digest = hashes.get("sha256")
        if digest is None:
            legacy = archive.get("hash", "")
            if isinstance(legacy, str) and legacy.startswith("sha256="):
                digest = legacy.removeprefix("sha256=")
        if isinstance(digest, str) and re.fullmatch(r"[0-9a-fA-F]{64}", digest):
            hashed.append({"name": name, "version": version, "sha256": digest.lower()})
        else:
            # Local editable sources or archives without a supplied hash.
            unhashed.append({"name": name, "version": version})
    hashed.sort(key=lambda x: (x["name"], x["version"], x["sha256"]))
    unhashed.sort(key=lambda x: (x["name"], x["version"]))
    return {"hashed": hashed, "unhashed": unhashed}


def capture_snapshot(
    distribution: Path, dependencies: Path, commit: str, output: Path,
    install_report: Path | None = None,
) -> dict:
    """Capture content hashes, not mtimes, runner paths, or a claimed wheel lock."""
    if not COMMIT_RE.fullmatch(commit):
        raise ValueError("expected the full 40-character commit SHA")
    if not distribution.is_dir() or not dependencies.is_file():
        raise ValueError("distribution directory and dependency list are required")
    files = []
    record_rows = {}
    for path in distribution.rglob("*"):
        if not path.is_file() or path.is_symlink():
            continue
        files.append({
            "path": path.relative_to(distribution).as_posix(),
            "sha256": _sha256(path),
            "bytes": path.stat().st_size,
        })
        if path.name == "RECORD" and ".dist-info" in path.parent.name:
            record_rows[path.relative_to(distribution).as_posix()] = _record_rows(path)
    files.sort(key=lambda item: item["path"])
    if not files:
        raise ValueError("cannot fingerprint an empty distribution")
    resolved = sorted(
        line.strip() for line in dependencies.read_text(encoding="utf-8").splitlines()
        if line.strip()
    )
    if not resolved or any("==" not in line for line in resolved):
        raise ValueError("a pinned resolved dependency list is required")
    tools = {}
    for name in ("pip", "setuptools", "wheel", "pyinstaller"):
        try:
            tools[name] = importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:
            tools[name] = None
    result = {
        "schema": 1, "commit": commit, "platform": sys.platform,
        "python": ".".join(str(item) for item in sys.version_info[:3]),
        "build_tools": tools,
        "dependencies": resolved,
        "files": files,
        "record_rows": record_rows,
        "install_artifacts": _install_artifacts(install_report) if install_report else None,
    }
    _write_json(output, result)
    return result


def compare_snapshots(first: Path, second: Path, output: Path) -> dict:
    left = json.loads(first.read_text(encoding="utf-8"))
    right = json.loads(second.read_text(encoding="utf-8"))
    for document in (left, right):
        if document.get("schema") != 1 or not document.get("files"):
            raise ValueError("invalid build snapshot")
    left_files = {file["path"]: file["sha256"] for file in left["files"]}
    right_files = {file["path"]: file["sha256"] for file in right["files"]}
    common = left_files.keys() & right_files.keys()
    changed = sorted(p for p in common if left_files[p] != right_files[p])
    version_drift = {
        field: [left.get(field), right.get(field)]
        for field in (
            "commit", "platform", "python", "build_tools", "dependencies",
            "install_artifacts",
        )
        if left.get(field) != right.get(field)
    }
    result = {
        "schema": 1,
        "same_commit": left["commit"] == right["commit"],
        "first_file_count": len(left_files),
        "second_file_count": len(right_files),
        "only_first": sorted(left_files.keys() - right_files.keys()),
        "only_second": sorted(right_files.keys() - left_files.keys()),
        "changed_hashes": [
            {"path": p, "first_sha256": left_files[p], "second_sha256": right_files[p]}
            for p in changed
        ],
        "metadata_drift": version_drift,
    }
    # Diagnose which installed-package RECORD entries changed without re-writing
    # any hashes, stripping metadata, or publishing absolute runner paths.
    changed_records = {}
    for record in changed:
        if not record.endswith(".dist-info/RECORD"):
            continue
        lr = left.get("record_rows", {}).get(record, {})
        rr = right.get("record_rows", {}).get(record, {})
        changed_records[record] = {
            "only_first": sorted(lr.keys() - rr.keys()),
            "only_second": sorted(rr.keys() - lr.keys()),
            "changed_rows": sorted(
                name for name in lr.keys() & rr.keys() if lr[name] != rr[name]
            ),
            "parsed_csv_equivalent": lr == rr,
        }
    result["record_row_differences"] = changed_records
    result["bit_for_bit_equal"] = bool(
        result["same_commit"] and not result["only_first"]
        and not result["only_second"] and not changed
    )
    result["reproducible_environment"] = not version_drift
    _write_json(output, result)
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="action", required=True)
    capture = sub.add_parser("capture")
    capture.add_argument("--distribution", type=Path, required=True)
    capture.add_argument("--dependencies", type=Path, required=True)
    capture.add_argument("--commit", required=True)
    capture.add_argument("--install-report", type=Path)
    capture.add_argument("--output", type=Path, required=True)
    compare = sub.add_parser("compare")
    compare.add_argument("--first", type=Path, required=True)
    compare.add_argument("--second", type=Path, required=True)
    compare.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.action == "capture":
        result = capture_snapshot(
            args.distribution, args.dependencies, args.commit, args.output,
            args.install_report,
        )
        print(f"Recorded {len(result['files'])} hashed payload files.")
    else:
        result = compare_snapshots(args.first, args.second, args.output)
        print(json.dumps({
            "bit_for_bit_equal": result["bit_for_bit_equal"],
            "reproducible_environment": result["reproducible_environment"],
            "only_first": len(result["only_first"]),
            "only_second": len(result["only_second"]),
            "changed_hashes": len(result["changed_hashes"]),
            "metadata_drift": sorted(result["metadata_drift"]),
        }))
        # Deliberately observational: upload the complete mismatch report.


if __name__ == "__main__":
    main()
