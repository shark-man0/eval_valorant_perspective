from __future__ import annotations

import argparse
from pathlib import Path

from valorant_ai_coach.observability import DiagnosticBundleRequest, create_diagnostic_bundle


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Create a sanitized, allowlist-only diagnostic bundle."
    )
    parser.add_argument("run_id")
    parser.add_argument("--diagnostics-dir", type=Path, default=Path("outputs/diagnostics"))
    parser.add_argument("--log", type=Path)
    args = parser.parse_args()

    run_dir = args.diagnostics_dir / args.run_id
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
