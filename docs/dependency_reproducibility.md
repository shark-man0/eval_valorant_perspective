# Dependency reproducibility

## Dependency classes

The project requires Python `>=3.12,<3.13`.

| Class | Source | Purpose |
| --- | --- | --- |
| Core runtime | `pyproject.toml` `[project].dependencies` | NumPy, jsonschema, keyring, OpenAI SDK, OpenCV, Shapely, plus Windows-marked `pywin32-ctypes` |
| GUI only | `.[gui]` | PySide6 desktop UI |
| Development | `.[dev]` | mypy, pytest, pytest-cov, Ruff |
| Windows packaging | `.[build]` | PyInstaller |
| Shared E2E baseline | `constraints-e2e.txt` | Exact direct versions used for cross-platform E2E comparison |
| Windows test/build baseline | `constraints-windows.txt` | Exact GUI/dev/build direct versions on Windows |
| Optional diagnostics | none | Observability uses the Python standard library; no monitoring dependency is required |

`constraints-e2e.txt` is deliberately not a complete transitive lock. It pins the measured direct E2E set while pip resolves transitive packages. `constraints-windows.txt` similarly fixes the Windows direct GUI/dev/build baseline.

## Current direct pins used for comparison

The shared E2E constraints pin NumPy 2.5.3, jsonschema 4.26.0, keyring 25.7.0, OpenAI 2.54.0, OpenCV 4.14.0.94, and Shapely 2.1.2. Windows constraints additionally pin PySide6 6.11.2, pywin32-ctypes 0.2.3 on Windows, mypy 1.20.2, pytest 9.1.1, pytest-cov 7.1.0, Ruff 0.16.9, and PyInstaller 6.22.3.

## Windows

For the source E2E path, use Python 3.12 and the shared E2E constraints. For the desktop app, full tests, and packaging, install the GUI/dev/build extras against `constraints-windows.txt`. FFmpeg/ffprobe and Git remain external commands. The diagnostic snapshot records versions but does not record their resolved local paths.

## Linux and Raspberry Pi

The same source E2E entrypoint is used on Linux. Raspberry Pi OS ARM64 has already executed the real-video pipeline with Python 3.12, but detection parity remains a separate concern. The documented Pi setup uses `constraints-e2e.txt`, does not require PySide6 or PyInstaller for headless E2E, and deliberately avoids silently changing dependency pins or Analyzer quality for ARM64.

OpenCV/NumPy ARM64 wheel availability must still be validated on the target machine. The snapshot is observational: a mismatch is reported, not used to disable execution.

## Create a snapshot

```bash
python -m scripts.diagnostics.snapshot \
  --output outputs/diagnostics/local/dependency_snapshot.json \
  --pip-check
```

The machine-readable schema includes Python implementation/version, OS/architecture, relevant direct package versions, FFmpeg/ffprobe version strings, repository commit/dirty state, and optional `pip check` status. It excludes hostname, username, home path, MAC/IP addresses, environment dumps, and serial numbers.

Missing packages or external tools are represented as `null`/unavailable rather than causing snapshot generation to fail.

## Compare Windows and Pi snapshots

```bash
python -m scripts.diagnostics.compare_snapshots \
  windows/dependency_snapshot.json \
  pi/dependency_snapshot.json
```

The compact diff compares Python, OS/architecture, NumPy, OpenCV, FFmpeg, and ffprobe. Compare `performance.json` files separately for total/phase runtime and memory metrics; phase reports use the same schema across platforms, while individual resource fields may be unavailable where the standard library cannot provide equivalent data.

## Drift checks

Use both the project version ranges and the platform constraint file appropriate to the task. Recommended checks are:

```bash
python -m pip check
python -m scripts.diagnostics.doctor
```

A snapshot difference is not an Analyzer execution prohibition. The accepted ranges in `pyproject.toml` and the explicit constraints for a given workflow remain authoritative.

## Known limitations

- The snapshot is not a complete lockfile and does not capture every transitive wheel hash.
- Peak RSS uses POSIX `resource`; Windows reports it unavailable without adding a new dependency.
- Current RSS is collected only on Linux via `/proc`.
- External tool version parsing stores only the first version line.
- Git commit/dirty state is unavailable in packaged/non-repository execution.
- Raspberry Pi temperature/throttling fields are best-effort and never required for a successful run.
