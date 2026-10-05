# Cross-platform E2E migration

Migration starts at clean `530c47d9303a8a06ceb0d17f24588ad0b4d468fa` after the
blind Buy-header diagnostic checkpoint was committed and pushed. No candidate
Buy/Ability representation was adopted. Analyzer feature work is paused for Pi validation.

## Actual call graph and scope

Before migration, the source path already was:
`run_e2e_windows.ps1` → `scripts/e2e/run_dataset_case.py` →
`tests/e2e/run_real_video.py` → `bootstrap.build_services` / production processor →
trace adapter → `tests/e2e/evaluate_saved_trace.py` → Validation Pack evaluator →
sanitized `e2e_reports/<id>/`. `diagnose_hud_video.py` is separate diagnostics.
The PowerShell wrapper additionally created a venv, installed/stamped dependencies,
required `py -3.12`, imported GUI dependencies and performed tool/input checks.

After migration, **both** `run_e2e_windows.ps1` and `run_e2e_pi.sh` call the same
existing `scripts/e2e/run_dataset_case.py`. No second orchestration wrapper was
introduced. `scripts/e2e/runtime.py` holds shared path/config/tool/environment
resolution. The validation, manifest registration, source SHA/pack fingerprints,
production invocation, evaluator, allowlisted metadata/report generation and
exit policy remain in the common runner. Process isolation is retained: all three
Python children use `sys.executable`, not a separately discovered interpreter.

Analyzer execution was already source Python, never a packaged `.exe`. Detector
code/configuration, thresholds, live identity contracts, UNKNOWN policy, sampling,
map/visual/event semantics and fixed-regression policies were not edited.

## OS-specific code audit

| Class | Actual location / assumption | Action |
|---|---|---|
| A: Windows packaging | `build_windows.ps1`, app spec, bundled `bin/*.exe`, PyInstaller; `resources.executable_path` handles `.exe` / `_MEIPASS` | Retained; build installs `.[gui,dev,build]` explicitly |
| B: launcher | `.venv\\Scripts\\python.exe`, PowerShell syntax, optional `py -3.12`; POSIX `.venv/bin/python` | Confined to thin launchers |
| C: E2E core fixes | PowerShell required py/absolute video paths, duplicated preflight, auto pip/hash stamp | Removed from invocation; explicit setup documented; native relative paths accepted |
| D: shared logic | Manifest/schema/source/pack validation, metadata/sanitization, subprocess argument lists, output/report policy | Kept in common Python; shared tool/config resolver added |
| E: intentional platform behavior | `settings.default_data_dir`: LOCALAPPDATA versus XDG; Windows `pywin32-ctypes` marker; GUI startup/UI files | Retained; source E2E sets private output data_dir and does not initialize GUI |
| E: portability guard | Dataset IDs reject Windows reserved names on every OS | Retained so shared artifacts stay cloneable on Windows |
| E: machine-local inputs | Docs/test fixtures demonstrate drive paths; private profiles/config can contain native absolute paths | Not production constants; local config must be rewritten on each host |

Audit covered launchers, common runner, video/evidence, trace/evaluator/report paths,
bootstrap/resources/settings, dependency metadata, Windows build/CI and fixed replay.
Backslash/drive examples in Windows docs and fixtures do not define the common path
contract. No Pi-specific hardware branch was added. Fixed replay already uses
production Python factories; no new sampling shortcut or parallel evaluator was added.

## Runtime, paths and precedence

Windows launcher: script root → repo venv → `python` → `py -3.12` fallback → shared
entrypoint → exact child exit. Existing named parameters remain, with Output,
Manifest/tool overrides and CheckEnvironment added. Missing VideoId is now checked
by common argparse (exit 2); environment check needs no fake VideoId.
POSIX launcher: physical script directory → repo venv → `python3` → same entrypoint
via `exec "$PYTHON_RUNTIME" ... "$@"`. It is tracked executable and LF-only.

All common Python paths use `Path`; relative inputs resolve from repo root even
when invoked elsewhere. Spaces/Unicode survive argument arrays. Linux rejects
copied Windows drive/UNC paths rather than treating them as relative filenames.
Source/pack/profile/manifest/output overrides use native paths, not slash replacement.
`--output` must name a new private directory, with the prior unique default retained.

Video: CLI → environment → `.env.local`. Pack originally CLI → environment →
sibling pack; the new literal `.env.local` fallback is inserted below environment,
leaving existing explicit choices unchanged. Optional HUD/visual/map settings gain
the same local/environment fallbacks. Manifest/output remain explicit CLI or prior
defaults. The local file is an ignored allowlist, not a shell; values are never evaluated.

Tools: CLI → environment (`FFMPEG_BIN`, `FFPROBE_BIN`, `GIT_BIN`) → local file →
`shutil.which` → controlled preflight error. Chosen FF tools are propagated into
source Analyzer settings and evidence video probing; custom executable names work.
Git discovery is shared, and runtime Git commands are read-only identity operations.
Python child environments force `PYTHONUTF8=1`, including descendants of the
unaltered Validation Pack, avoiding CP932 decode failures.

Full E2E exits retain 0 PASS / 1 completed assertion FAIL / 2 preflight/runtime
failure. `--check-environment` exits 0 only for environment readiness; it runs no
Analyzer and does not claim accuracy. Launchers neither install dependencies nor
mutate Git. Setup is now an explicit operation, not repeated per-run bootstrap.

## Dependencies and Windows compatibility

`pyproject.toml` keeps Python >=3.12,<3.13. NumPy is now explicit. PySide6 moved
to optional `gui`; source E2E imports the production factory without importing Qt.
OpenCV remains `opencv-python`, preserving the package/version baseline. Linux
GL/GLib runtime libraries may still be necessary; do not install competing cv2 packages.
`constraints-e2e.txt` pins measured direct core versions; transitive dependencies
are resolved by pip and are not presented as a full lock. Windows constraints remain
for GUI/build tooling; Windows README/build/CI now install `.[gui,dev,build]`.
Windows packaged application behavior is unchanged; a new EXE was not built here.

Existing `.\\run_e2e_windows.ps1 -Video ... -VideoId ... -ValidationPack ...`
continues to work. First-time users must explicitly create/install `.venv`; the
former automatic pip/bootstrap/stamp behavior was intentionally removed to keep
OS launchers thin. See `WINDOWS_E2E.md` and `RASPBERRY_PI_E2E.md`.

## Verification and remaining boundary

Verification results are recorded after the final checks below. Tests cover root
resolution independent of CWD, Unicode/spaces, native/foreign path handling,
CLI/env/local/default precedence, missing pack/tools, interpreter propagation,
headless imports, literal config, explicit output/manifest, 0/1/2 exits, runtime
errors, no shell strings/Git mutation and shared thin entrypoint. Windows launcher
connectivity is exercised against real Python. Git Bash checks POSIX syntax and
stub argument/exit passthrough; **Git Bash is not Linux/Pi runtime verification**.

Actual Linux native absolute-path test remains skipped on Windows. No claim is
made that Linux/Pi installation or full Analyzer execution passed. ARM package
availability, native library imports, decoder/crop hashes, numeric/fixed replay
parity, runtime memory and source-profile portability require actual Pi evidence. The measured baseline profile
has 25 image references, four absolute Windows paths and 21 relative POSIX-style
paths. The existing loader is unchanged; copying referenced external assets and
rebasing those four private paths is a Pi preparation requirement, not evidence
of profile/detector parity.
See the setup guide for reproducible commands. New Analyzer improvements must wait
for that result; sampling and safety contracts may not be relaxed for Pi performance.

### Final verification

Final source suite: **966 passed / 3 skipped** in 272.76 seconds. Skips are the
existing optional sibling-pack fixture, optional real-HUD anchor video fixture and
host-native Linux absolute-path test on Windows. The raw video used for the separate
clean E2E remains available; these fixture skips do not establish real accuracy.
Ruff across src/tests/scripts passes; mypy passes the existing src contract across
86 files; diff checks pass. Common Python and actual PowerShell environment smoke
both exit 0. POSIX syntax and Unicode/0/1/2 launcher stub checks pass on Git Bash.

The single post-commit Windows real-video parity result will be recorded separately
under `e2e_reports/match_001/` and `docs/cross_platform_e2e_windows_parity_v1.json`.
It is not a Pi execution claim. No further Analyzer feature work is authorized until
the first Pi result is reviewed.
