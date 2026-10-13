"""Conservative static inventory of Python text I/O; never auto-convert encodings."""

from __future__ import annotations

import argparse
import ast
import json
import tokenize
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SCOPES = ("src", "scripts", "tests", "config", "ValorantData")
UTF8 = {"utf-8", "utf8", "utf-8-sig"}


def _literal(node: ast.expr | None) -> Any:
    if node is None:
        return None
    try:
        return ast.literal_eval(node)
    except (ValueError, TypeError, SyntaxError, MemoryError, RecursionError):
        return None


def _keyword(call: ast.Call, name: str) -> ast.expr | None:
    return next((item.value for item in call.keywords if item.arg == name), None)


def scan_source(source: str, path: str) -> list[dict[str, Any]]:
    """Enumerate I/O boundaries without assuming they are UTF-8."""
    tree = ast.parse(source, filename=path)
    findings: list[dict[str, Any]] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        fn = node.func
        if isinstance(fn, ast.Attribute):
            name = fn.attr
            parent = fn.value.id if isinstance(fn.value, ast.Name) else None
        elif isinstance(fn, ast.Name):
            name = fn.id
            parent = None
        else:
            continue

        if name in {"read_bytes", "write_bytes"} and isinstance(fn, ast.Attribute):
            kind, category = name, "Binary I/O"
        elif name in {"read_text", "write_text"} and isinstance(fn, ast.Attribute):
            kind, category = name, ""
        elif name == "open" and (parent in {None, "io"} or isinstance(fn, ast.Attribute)):
            kind, category = "open", ""
            mode = _literal(_keyword(node, "mode"))
            if mode is None:
                index = 0 if isinstance(fn, ast.Attribute) else 1
                mode = _literal(node.args[index]) if len(node.args) > index else "r"
            if isinstance(mode, str) and "b" in mode:
                category = "Binary I/O"
        elif name in {"run", "Popen", "check_output", "check_call"} and parent == "subprocess":
            kind, category = "subprocess", "要調査"
            if _keyword(node, "encoding") is None and (
                _literal(_keyword(node, "text")) is not True
                and _literal(_keyword(node, "universal_newlines")) is not True
            ):
                category = "Binary I/O"
        elif name in {"decode", "encode"} and isinstance(fn, ast.Attribute):
            kind, category = name, "要調査"
        else:
            continue

        encoding_node = _keyword(node, "encoding")
        if kind in {"decode", "encode"} and encoding_node is None and node.args:
            encoding_node = node.args[0]
        if kind == "open" and encoding_node is None:
            index = 1 if isinstance(fn, ast.Attribute) else 3
            if len(node.args) > index:
                encoding_node = node.args[index]
        encoding = _literal(encoding_node)
        if category != "Binary I/O":
            if isinstance(encoding, str) and encoding.lower().replace("_", "-") in UTF8:
                category = "UTF-8明示"
            elif encoding_node is not None:
                category = "その他の明示的encoding" if encoding is not None else "要調査"
            else:
                category = "要調査"
        findings.append({
            "path": path, "line": node.lineno, "operation": kind,
            "category": category, "encoding": encoding,
        })
    return sorted(findings, key=lambda item: (item["line"], item["operation"]))


def scan_repository(root: Path = ROOT) -> dict[str, Any]:
    findings: list[dict[str, Any]] = []
    files = sorted(
        file for scope in SCOPES for file in (root / scope).rglob("*.py")
        if file.is_file() and "__pycache__" not in file.parts
    )
    for file in files:
        relative = file.relative_to(root).as_posix()
        with tokenize.open(file) as stream:
            findings.extend(scan_source(stream.read(), relative))
    categories = Counter(item["category"] for item in findings)
    return {
        "python_files": len(files), "io_sites": len(findings),
        "categories": dict(sorted(categories.items())),
        "sites": findings,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--summary-json", action="store_true")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    result = scan_repository()
    if args.summary_json:
        result = {key: value for key, value in result.items() if key != "sites"}
    if args.summary_json or args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(f"{result['python_files']} Python files; {result['io_sites']} I/O call sites")
        for category, count in result["categories"].items():
            print(f"  {category}: {count}")
        print("Use --json for candidates; '要調査' is not an automatic UTF-8 fix.")


if __name__ == "__main__":
    main()
