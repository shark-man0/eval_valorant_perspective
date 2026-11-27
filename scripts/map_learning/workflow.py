"""Register or reuse a DEVELOPMENT recording and publish its desktop Map package."""

from __future__ import annotations

import argparse
import os
import re
import shutil
import subprocess
from contextlib import contextmanager
from pathlib import Path

from acquire_native import acquire
from checkpoints import pin
from run_batch import _FLAGS, _PATH_OPTIONS, _REQUIRED, _SHARED, record_map_exposure
from run_recording import _run

from valorant_ai_coach.application.map_job_control import PAUSE_ENV, PAUSE_EXIT, MapPaused, phase
from valorant_ai_coach.application.map_library import publish_map_package
from valorant_ai_coach.recordings.admission import resolve_catalog
from valorant_ai_coach.recordings.catalog import LeakageError, _lock_exclusive, _unlock
from valorant_ai_coach.temporal.evidence import digest
from valorant_ai_coach.temporal.replay import file_sha, read_json

_SCRIPT_ROOT = Path(__file__).resolve().parent
_MINIMUM_FREE = 12 * 2**30
_FRAME = re.compile(r"frame_[0-9]{6,}\.(png|webp)")


def _private(path):
    path = path.resolve()
    if any((p / ".git").exists() for p in (path, *path.parents)):
        raise ValueError("Map workflow output must stay outside Git checkouts")
    return path


@contextmanager
def _source_lock(path):
    with path.open("ab") as lock:
        if lock.tell() == 0:
            lock.write(b"\0")
        lock.flush()
        lock.seek(0)
        _lock_exclusive(lock.fileno())
        try:
            yield
        finally:
            _unlock(lock.fileno())


def import_packages(index, library):
    doc = read_json(index)
    if doc["schema"] != "development_map_catalog_viewer_v1" or doc["formal_outputs"] != 0:
        raise ValueError("A private development Map catalog is required")
    count = 0
    for row in doc["recordings"]:
        if row["status"] != "available":
            continue
        paths = {key: (index.parent / row[key]).absolute()
                 for key in ("bundle", "policy", "standard", "recovered", "evaluation")}
        for key in ("bundle", "standard", "recovered", "evaluation"):
            field = "timeline" if key == "bundle" else key
            if file_sha(paths[key]) != row[f"{field}_sha256"]:
                raise ValueError("An existing Map catalog artifact changed")
        publish_map_package(library, label=_label(paths["recovered"], prefix=row["index"]), **paths)
        count += 1
    return count


def _label(report, *, prefix=None):
    display = read_json(report.with_suffix(".display.json"))
    atlas = " / ".join(sorted({row["map_name"] for row in display["atlases"]})) or "Map UNKNOWN"
    return f"{prefix:02d} · {atlas}" if prefix is not None else atlas


def _options(setup):
    spec = read_json(setup)
    options = dict(spec["run_options"])
    flags = tuple(spec.get("run_flags", ()))
    if not _REQUIRED <= options.keys() <= _SHARED or set(flags) - _FLAGS:
        raise ValueError("Invalid development Map run options")
    for key in options.keys() & _PATH_OPTIONS:
        options[key] = (setup.parent / options[key]).resolve(strict=True)
    return options, flags


def _dependency_files(path):
    if path.is_file():
        return {str(path): file_sha(path)}
    return {str(file): file_sha(file) for file in sorted(path.rglob("*")) if file.is_file()}


def _run_fingerprint(options, flags):
    snapshots = {
        name: _dependency_files(path) for name, path in options.items() if isinstance(path, Path)
    }
    package = Path(__import__("valorant_ai_coach").__file__).resolve().parent
    code = {
        str(path.relative_to(root)): file_sha(path)
        for root, paths in (
            (_SCRIPT_ROOT, _SCRIPT_ROOT.glob("*.py")),
            (package, (package / "temporal").glob("map_*.py")),
        )
        for path in paths
    }
    return digest({
        "snapshots": snapshots, "options": {k: str(v) for k, v in options.items()},
        "flags": flags, "code": code,
    })


def _timeline_key(options, acquisition):
    inputs = {
        name: _dependency_files(options[name])
        for name in ("hud-config", "spectator-label", "camera-hint") if name in options
    }
    package = Path(__import__("valorant_ai_coach").__file__).resolve().parent
    code = {"prepare_native_timeline.py": file_sha(_SCRIPT_ROOT / "prepare_native_timeline.py")}
    for subtree in ("temporal", "hud", "rules"):
        code.update({
            str(path.relative_to(package)): file_sha(path)
            for path in (package / subtree).rglob("*.py") if not path.name.startswith("map_")
        })
    return digest([file_sha(acquisition), inputs, code])


def _clear_owned_cache(folder):
    if folder.resolve() != folder or folder.is_symlink():
        raise ValueError("Cannot release a redirected Map cache")
    metadata = {
        "decode_PRIVATE.log", "verified_acquisition_PRIVATE.json", "frame_hashes_PRIVATE.json",
    }
    frames = []
    for item in folder.iterdir():
        if (item.is_symlink() or not item.is_file() or item.stat().st_nlink != 1
                or (item.name not in metadata and not _FRAME.fullmatch(item.name))):
            raise ValueError("Cannot release unowned Map cache contents")
        frames.append(item)
    for item in frames:
        item.unlink()
    folder.rmdir()


def _acquisition(folder, policy, source, decode, minimum_free):
    receipt = folder / "verified_acquisition_PRIVATE.json"
    if not receipt.is_file():
        if folder.exists():
            _clear_owned_cache(folder)
        acquire(policy, source, folder, minimum_free_bytes=minimum_free, **decode)
    recorded = read_json(receipt)
    frames = recorded["frames"]
    if (recorded["sha256"] != source or recorded["native_pts_parity"] is not True
            or recorded["verified_source_before_after"] is not True or not frames
            or any(Path(name).parent != folder or not Path(name).is_file()
                   or Path(name).is_symlink() or not _FRAME.fullmatch(Path(name).name)
                   for _, name in frames)):
        raise ValueError("Invalid Map acquisition checkpoint")
    pin(folder / "frame_hashes_PRIVATE.json", {
        "acquisition_sha256": file_sha(receipt),
        "frames": [[tick, Path(name).name, file_sha(Path(name))] for tick, name in frames],
    })
    return receipt


def execute(catalog, workspace, library, setup, recording_id, *, release_cache=False,
            minimum_free=_MINIMUM_FREE, expected_run=None):
    record = catalog.state.recordings[recording_id]
    if record.split != "DEVELOPMENT":
        raise ValueError("Map workflow accepts only DEVELOPMENT recordings")
    catalog.guard([recording_id], "development_analysis")
    source = record.source_sha256
    options, flags = _options(setup)
    key = _run_fingerprint(options, flags)
    if expected_run is not None and expected_run != key:
        raise ValueError("Map analysis inputs changed; start a new version instead of resuming")
    print(f"Map workflow run: {key}", flush=True)
    home = _private(workspace) / source
    home.mkdir(mode=0o700, parents=True, exist_ok=True)
    with _source_lock(home / "workflow.lock"):
        policy = home / "source_policy_PRIVATE.json"
        pin(policy, {
            "catalog": str(catalog.root.resolve()), "allowed_recording_ids": [recording_id],
        })
        run = home / "runs" / key
        target = run / "run_PRIVATE.json"
        decode = {
            "hwaccel": options.pop("hwaccel", None), "lossless_webp": "lossless-webp" in flags,
            "png_compression": options.get("png-compression", 1),
        }
        cache = home / "native" / digest(decode)
        if not target.is_file():
            if not cache.is_dir() and shutil.disk_usage(home).free <= minimum_free:
                raise ValueError("Insufficient disk capacity for development acquisition")
            record_map_exposure(catalog, recording_id)
            phase("acquisition")
            receipt = _acquisition(cache, policy, source, decode, minimum_free)
            _run("run_recording.py", {
                **options, "source-sha256": source, "policy-path": policy,
                "output": run, "acquisition": receipt,
                "timeline-cache": home / "timelines" / _timeline_key(options, receipt),
            }, ("--resume", *(f"--{flag}" for flag in flags if flag != "lossless-webp")),
                cooperative_child=True)
        phase("publication")
        complete = read_json(target)
        exact_outputs = all(file_sha(run / name) == checksum
                            for name, checksum in complete["output_sha256s"].items())
        if (complete["schema"] != "development_map_recording_run_v1"
                or complete["formal_map_outputs"] != 0 or complete["source_sha256"] != source
                or not exact_outputs):
            raise ValueError("A completed Map run failed its receipt check")
        recovered = run / "map_recovered_PRIVATE.json"
        location = record.locations.get("original") or record.locations["managed"]
        title = f"{_label(recovered)} · {catalog.local_path(location['path']).name}"
        published = publish_map_package(
            library, label=title, bundle=run / "timeline/timeline_PRIVATE.json",
            policy=policy, standard=run / "map_standard_PRIVATE.json", recovered=recovered,
            evaluation=run / "analysis_recovered/match_evaluation_PRIVATE.json",
            variant=f"{setup.stem} · {key[:8]}",
        )
        if release_cache and cache.is_dir():
            _clear_owned_cache(cache)
        return published


def _refuse_protected_path(catalog, path):
    source = path.resolve()
    for record in catalog.state.recordings.values():
        if record.split != "DEVELOPMENT" and any(
            catalog.local_path(location["path"]).resolve() == source
            for location in record.locations.values()
        ):
            raise LeakageError("A protected recording cannot be registered as DEVELOPMENT")


def main():
    os.umask(0o077)
    parser = argparse.ArgumentParser(description=__doc__)
    target = parser.add_mutually_exclusive_group(required=True)
    target.add_argument("--video", type=Path)
    target.add_argument("--recording-id")
    target.add_argument("--import-index", type=Path)
    parser.add_argument("--catalog", type=Path)
    parser.add_argument("--setup", type=Path)
    parser.add_argument("--workspace", type=Path)
    parser.add_argument("--library", type=Path, required=True)
    parser.add_argument("--confirm-distinct", action="store_true")
    parser.add_argument("--release-cache", action="store_true")
    parser.add_argument("--minimum-free-gib", type=int, default=12)
    parser.add_argument("--pause-file", type=Path)
    parser.add_argument("--expected-run")
    args = parser.parse_args()
    if args.import_index:
        print("Map packages available:", import_packages(args.import_index.resolve(), args.library))
        return
    if args.setup is None or args.workspace is None or args.minimum_free_gib < 1:
        parser.error("Processing requires --setup, --workspace and at least 1 GiB reserve")
    catalog = resolve_catalog(args.catalog)
    if catalog is None:
        parser.error("A recording catalog is required")
    recording_id = args.recording_id
    if args.pause_file:
        os.environ[PAUSE_ENV] = str(args.pause_file.resolve())
    phase("registration")
    if args.video is not None:
        if not args.confirm_distinct:
            parser.error("Register a new physical match with --confirm-distinct")
        _refuse_protected_path(catalog, args.video)
        registration = catalog.register(args.video, split="DEVELOPMENT", confirm_distinct=True)
        recording_id = registration.recording_id
    print(f"Map registered recording: {recording_id}", flush=True)
    execute(catalog, args.workspace, args.library, args.setup.resolve(), recording_id,
            release_cache=args.release_cache, minimum_free=args.minimum_free_gib * 2**30,
            expected_run=args.expected_run)
    print("Development Map package available")


if __name__ == "__main__":
    try:
        main()
    except MapPaused:
        raise SystemExit(PAUSE_EXIT) from None
    except subprocess.CalledProcessError as exc:
        if exc.returncode == PAUSE_EXIT:
            raise SystemExit(PAUSE_EXIT) from None
        raise
