from __future__ import annotations

import argparse
import re
from pathlib import Path

from valorant_ai_coach.observability import DiagnosticBundleRequest, create_diagnostic_bundle

_SAFE_RUN_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,127}$")


def _resolve_run_dir(diagnostics_dir: Path, run_id: str) -> Path:
    if not _SAFE_RUN_ID.fullmatch(run_id) or run_id in {".", ".."}:
        raise ValueError("diagnostic run_id contains unsafe characters")
    base = Path(diagnostics_dir).expanduser().resolve()
    candidate = base / run_id
    if candidate.is_symlink():
        raise ValueError("diagnostic run directory must not be a symlink")
    resolved = candidate.resolve()
    if not resolved.is_relative_to(base):
        raise ValueError("diagnostic run directory escapes diagnostics root")
    return resolved


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Create a sanitized, allowlist-only diagnostic bundle."
    )
    parser.add_argument("run_id")
    parser.add_argument("--diagnostics-dir", type=Path, default=Path("outputs/diagnostics"))
    parser.add_argument("--log", type=Path)
    args = parser.parse_args()

    run_dir = _resolve_run_dir(args.diagnostics_dir, args.run_id)
    destination = run_dir / "diagnostic_bundle.zip"
    request = DiagnosticBundleRequest(
        run_id=args.run_id,
        output_path=destination,
        performance_path=run_dir / "performance.json",
        dependency_snapshot_path=run_dir / "dependency_snapshot.json",
        log_path=args.log,
    )
    create_diagnostic_bundle(request)
    print(destination)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
