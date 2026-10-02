"""Persist sanitized, hash-bound export inputs before attempting shared export."""

import json
import re
from pathlib import Path

from scripts.e2e.run_dataset_case import sha256_file
from scripts.e2e.share_report import sanitize_run_metadata

INPUT_FILES = ("raw_processing.json", "e2e_trace.json", "evaluation_report.json")


def save_context(run_dir: Path, metadata: dict, *, assertions_sha256=None, exit_code=None):
    context = {
        "schema_version": 1,
        "metadata": sanitize_run_metadata(metadata),
        "assertions_sha256": assertions_sha256,
        "input_hashes": {
            name: sha256_file(run_dir / name) for name in INPUT_FILES if (run_dir / name).is_file()
        },
        "exit_code": exit_code,
        "hud_layout_sha256": metadata.get("hud_layout_sha256")
        if isinstance(metadata.get("hud_layout_sha256"), str)
        and re.fullmatch(r"[a-f0-9]{64}", metadata["hud_layout_sha256"])
        else None,
    }
    temporary = run_dir / ".run_metadata.json.tmp"
    temporary.write_text(json.dumps(context, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    temporary.replace(run_dir / "run_metadata.json")
