# Basic CI

## Purpose

The repository uses two GitHub Actions workflows with deliberately different roles:

- `.github/workflows/basic-ci.yml` provides repository-contained basic validation on Linux.
- `.github/workflows/windows.yml` keeps the existing Windows verification and packaging path, including the PyInstaller build, packaged-application smoke test, and artifact upload.

Both workflows run on normal `push` and `pull_request` events. Superseded runs for the same workflow/ref are cancelled with `concurrency` so obsolete commits do not continue consuming CI time.

## Linux basic validation

`basic-ci.yml` runs on `ubuntu-latest` with Python 3.12, matching the project requirement `>=3.12,<3.13`.

The job:

1. checks out the repository with `actions/checkout@v4`;
2. configures Python 3.12 with `actions/setup-python@v5` and pip caching keyed from `pyproject.toml`;
3. ensures both `ffmpeg` and `ffprobe` are available;
4. installs the project with `python -m pip install -e ".[gui,dev]"`;
5. runs `python tests/validate_dataset.py`;
6. runs the repository-contained pytest suite with coverage and the existing 75% failure threshold;
7. runs `python -m ruff check src tests scripts/e2e`;
8. runs `python -m mypy src/valorant_ai_coach`.

`QT_QPA_PLATFORM=offscreen` is set for the Linux job so Qt smoke/unit tests can run headlessly without changing production GUI behavior. `PYTHONUTF8=1` keeps Python subprocess text handling deterministic.

The pytest command also prints the 25 slowest test durations. This does not skip or weaken any tests; it only makes long-running repository tests visible in CI logs.

## Coverage contract

The workflow preserves the repository coverage contract:

```text
--cov=valorant_ai_coach --cov-report=term-missing --cov-fail-under=75
```

The threshold is not reduced or bypassed. `pyproject.toml` also retains `fail_under = 75`.

## Real-video E2E boundary

Basic CI does **not** invoke:

- `run_e2e_windows.ps1`;
- `run_e2e_pi.sh`;
- `scripts/e2e/run_dataset_case.py` as an E2E run;
- `tests/e2e/run_real_video.py`;
- raw VALORANT video analysis;
- private HUD/profile files;
- machine-local validation packs or other private local resources.

The normal pytest collection may exercise repository-contained E2E **boundary/unit tests** that fake or mock the real-video subprocess path. `tests/e2e/run_real_video.py` is a CLI script rather than a `test_*.py` test module and is not invoked by the basic workflow. Tests that optionally use an external sibling validation pack keep their existing skip contract when that resource is absent.

## Windows verification and packaging

`.github/workflows/windows.yml` remains the Windows verification/packaging workflow. It continues to use Python 3.12 and `constraints-windows.txt`, and continues to perform:

- FFmpeg/ffprobe availability checks;
- dependency installation with `.[gui,dev,build]`;
- dataset validation;
- pytest with the existing 75% coverage gate;
- Ruff;
- mypy;
- PyInstaller build with `VALORANT-AI-Coach.spec`;
- packaged application smoke test with Qt offscreen;
- Windows onedir artifact upload.

The packaging behavior is intentionally not moved into Linux basic CI and is not replaced by a release, installer, signing, or deployment workflow.

## Security

Both workflows declare `permissions: contents: read`. They require no repository secrets, do not interpolate untrusted pull-request metadata into shell commands, and use the existing official GitHub Actions (`actions/checkout`, `actions/setup-python`, and `actions/upload-artifact`).
