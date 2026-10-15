"""Source-bound S-01 point smoke against the real match_001 Git LFS fixture.

This is *not* continuous round-boundary qualification or canonical full E2E.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from scripts.e2e import run_dataset_case  # noqa: E402
from scripts.e2e.frame_suite import load_suite  # noqa: E402

VIDEO_RELATIVE_PATH = Path("tests/e2e/fixtures/real/match_001.mp4")
VIDEO_PATH = ROOT / VIDEO_RELATIVE_PATH
SUITE_PATH = ROOT / "datasets/e2e_suites/match_001/targeted.json"
SOURCE_SHA256 = "71d58558559d6f578433ce9f234bf176f76fd5a86657dbfe3eba1e7d36136b06"
SOURCE_SIZE = 267056165


class SmokePreflightError(ValueError):
    """A required, independently identified test input is not usable."""


def source_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def check_source(path: Path = VIDEO_PATH) -> None:
    if path.is_symlink():
        raise SmokePreflightError("VIDEO_SYMLINK_REJECTED")
    if not path.is_file():
        raise SmokePreflightError(
            "LFS_VIDEO_MISSING: check out feat/s01-lfs-point-smoke and run "
            "git lfs pull --include=tests/e2e/fixtures/real/match_001.mp4"
        )
    with path.open("rb") as stream:
        prefix = stream.read(48)
    if prefix.startswith(b"version https://git-lfs.github.com/spec/v1"):
        raise SmokePreflightError(
            "LFS_POINTER_ONLY: run git lfs pull "
            "--include=tests/e2e/fixtures/real/match_001.mp4"
        )
    if path.stat().st_size != SOURCE_SIZE:
        raise SmokePreflightError("VIDEO_SIZE_MISMATCH")
    if source_sha256(path) != SOURCE_SHA256:
        raise SmokePreflightError("VIDEO_SHA256_MISMATCH")


def resolved_path(value: str) -> Path:
    path = Path(value).expanduser()
    return path if path.is_absolute() else ROOT / path


def check_inputs(pack: Path, layout: Path, categories: tuple[str, ...]) -> int:
    check_source()
    if not layout.is_file():
        raise SmokePreflightError("HUD_LAYOUT_MISSING")
    manifest = pack / "MANIFEST.json"
    if not manifest.is_file():
        raise SmokePreflightError("VALIDATION_PACK_MANIFEST_MISSING")
    try:
        info = json.loads(manifest.read_text(encoding="utf-8"))
    except (UnicodeError, json.JSONDecodeError) as error:
        raise SmokePreflightError("VALIDATION_PACK_MANIFEST_INVALID") from error
    if not isinstance(info, dict) or info.get("source_sha256") != SOURCE_SHA256:
        raise SmokePreflightError("VALIDATION_PACK_SOURCE_MISMATCH")
    try:
        suite = load_suite(SUITE_PATH, "targeted", SOURCE_SHA256, categories)
    except (OSError, ValueError) as error:
        raise SmokePreflightError(f"TARGETED_SUITE_INVALID: {error}") from error
    count = len(suite["frames"])
    if count == 0:
        raise SmokePreflightError("NO_SELECTED_FRAMES")
    return count


def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--validation-pack", required=True, help="Independent match_001 validation pack")
    p.add_argument("--hud-layout", required=True, help="Explicit existing production HUD profile")
    p.add_argument(
        "--include-regressions", action="store_true",
        help="Add regression_protection category to the seven round_boundary points",
    )
    p.add_argument("--preflight-only", action="store_true", help="Verify inputs, no recognition")
    p.add_argument("--previous", help="Previous compatible targeted run for comparison")
    p.add_argument("--output", help="Private output directory; leave empty for unique run path")
    p.add_argument("--cache-dir", help="Decoded frame cache; never recognition/qualification cache")
    return p


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    categories = ("round_boundary", "regression_protection") if args.include_regressions else (
        "round_boundary",
    )
    pack = resolved_path(args.validation_pack)
    layout = resolved_path(args.hud_layout)
    try:
        frame_count = check_inputs(pack, layout, categories)
    except SmokePreflightError as error:
        print(f"S-01 LFS preflight failed: {error}", file=sys.stderr)
        return 2
    print(
        f"S-01 LFS point smoke: verified {SOURCE_SHA256}, "
        f"{frame_count} fixed point(s), no temporal qualification",
        flush=True,
    )
    if args.preflight_only:
        return 0

    runner_args = [
        "--video", str(VIDEO_PATH),
        "--video-id", "match_001",
        "--validation-pack", str(pack),
        "--hud-layout", str(layout),
        "--mode", "targeted",
        "--frame-suite", str(SUITE_PATH),
    ]
    for category in categories:
        runner_args.extend(("--category", category))
    if args.previous:
        runner_args.extend(("--previous", str(resolved_path(args.previous))))
    if args.output:
        runner_args.extend(("--output", str(resolved_path(args.output))))
    if args.cache_dir:
        runner_args.extend(("--cache-dir", str(resolved_path(args.cache_dir))))
    return run_dataset_case.main(runner_args)


if __name__ == "__main__":
    raise SystemExit(main())
