# Raspberry Pi / Linux E2E setup

Status: the real-video pipeline was **verified through evaluation on a Raspberry
Pi 4 Model B, Linux ARM64, Python 3.12.3**. It completed with exit 1 (assertion
FAIL), 3869 analyzed frames, valid schema and no runtime error. Detection/Windows
parity is still unverified. See [runtime repair and measured results](docs/pi_e2e_runtime.md).
Target: Raspberry Pi OS 64-bit (Bookworm or newer), ARM64. Linux x86_64 uses the same entrypoint. Python must be **3.12.x**, matching
`pyproject.toml`; do not substitute a system Python 3.11 or 3.13.

## Install system tools

```sh
sudo apt update
sudo apt install git ffmpeg python3-venv python3-pip libgl1 libglib2.0-0
git clone https://github.com/shark-man0/eval_valorant_perspective.git
cd eval_valorant_perspective
uname -m
python3.12 --version
```

On Trixie, use `libglib2.0-0t64` if the old GLib package name is unavailable.
OpenCV remains `opencv-python`, matching the Windows baseline; its Linux import
may need GL/GLib libraries even though E2E does not initialize a GUI. Do not also
install `opencv-python-headless` into the same environment.

If `python3.12` is unavailable, install it separately; the OS default is not the
project contract. One source-build option follows. This leaves system Python intact:

```sh
sudo apt install build-essential curl ca-certificates libssl-dev zlib1g-dev \
  libbz2-dev libreadline-dev libsqlite3-dev libffi-dev liblzma-dev libncurses-dev uuid-dev
mkdir -p "$HOME/python-build"
cd "$HOME/python-build"
curl -fLO https://www.python.org/ftp/python/3.12.15/Python-3.12.15.tar.xz
# Verify the archive against the official release page before extracting.
tar -xf Python-3.12.15.tar.xz
cd Python-3.12.15
./configure --prefix="$HOME/.local/python3.12" --with-ensurepip=install
make -j2
make altinstall
export PATH="$HOME/.local/python3.12/bin:$PATH"
python3.12 --version
# Return to your cloned repository before continuing.
```

Python 3.12.15 is a source-only security release; source compilation and memory
requirements are unverified on this Pi. See the [official release](https://www.python.org/downloads/release/python-31215/).
Raspberry Pi OS requires a venv for normal pip installs on Bookworm onward; see
the [official Python guide](https://www.raspberrypi.com/documentation/computers/os.html#python-on-raspberry-pi).

## Create the headless environment

From the repository root:

```sh
python3.12 -m venv .venv
.venv/bin/python -m pip install --upgrade pip
.venv/bin/python -m pip install --only-binary=:all: -c constraints-e2e.txt -e .
.venv/bin/python -m pip check
./run_e2e_pi.sh --check-environment
```

The constraints pin the six direct dependencies measured on the Windows baseline:
NumPy 2.5.3, OpenCV 4.14.0.94, jsonschema 4.26.0, keyring 25.7.0,
openai 2.54.0 and Shapely 2.1.2. Transitive dependencies are pip-resolved, so this
is not a complete lock file. Save `pip freeze` locally when testing a machine.
No PySide6 or PyInstaller is needed for source E2E. `.[gui]` is for the desktop
app; `.[dev]` adds tests/static tools; full GUI tests additionally require `gui`.
Mock AI and disabled semantic processing remain the existing E2E behavior.

PyPI lists ARM64 wheels for the pinned [OpenCV](https://pypi.org/project/opencv-python/4.14.0.94/#files)
and [NumPy](https://pypi.org/project/numpy/2.5.3/#files) releases. Availability is
not proof of installation, native-library compatibility or numeric parity on Pi.
`--only-binary` deliberately fails instead of silently building large dependencies.
If a wheel is unavailable, preserve the failure log and investigate that package;
do not silently change a pin or the Analyzer's sampling/thresholds.

## Private inputs and profiles

Copy the original recording and **unaltered** Validation Pack v3 separately.
Neither is downloaded by the runner. Suggested private placement:

```text
/home/pi/ValorantData/videos/match_001.mp4
/home/pi/ValorantData/valorant_e2e_validation_pack_v3/
```

The registered `match_001` recording has SHA256
`71d58558559d6f578433ce9f234bf176f76fd5a86657dbfe3eba1e7d36136b06`.
Changing its name is allowed; replacing its bytes is rejected.
For behavior parity, copy the entire existing private calibrated profile directory,
including `.templates.json`, referenced anchors/identity masks and inherited assets.
Inspect profile asset paths: machine-specific absolute Windows paths must be
replaced with equivalent local relative/native paths without changing image bytes
or detector fields. Recheck profile/asset hashes and disclose any path-induced
profile hash change. Do not regenerate a profile merely to make an OS comparison pass.
The measured baseline sidecar contains 25 image references: 21 relative POSIX-style
paths and four absolute Windows paths. Copying just its directory is therefore
insufficient; transfer those four referenced files too and rebase their paths.
The loader is unchanged and does not guess mappings from Windows drives to Linux.
All private generated files remain in ignored `outputs/`.

Create a separate **ignored** `.env.local` in the repository root, using Pi paths:

```dotenv
VALORANT_E2E_VIDEO=/home/pi/ValorantData/videos/match_001.mp4
VALORANT_E2E_PACK=/home/pi/ValorantData/valorant_e2e_validation_pack_v3
VALORANT_E2E_HUD_LAYOUT=outputs/hud_profiles/existing/hud_layout.json
VALORANT_E2E_MANUAL_MAP_ID=summit
# Optional: VALORANT_E2E_VISUAL_PROFILE=path/to/existing/profile.json
# Optional executable overrides: FFMPEG_BIN=/usr/bin/ffmpeg
# FFPROBE_BIN=/usr/bin/ffprobe
# GIT_BIN=/usr/bin/git
```

Use a known map selection only when correct for the source. It does not bypass
HUD/ownership gates. Copying an entire Windows `.env.local` is unsafe: foreign
drive/UNC paths are rejected on Linux. Values are literal, not shell expressions;
quotes are allowed, but `$HOME`, `${VAR}` and inline comments are not expanded.
Relative paths are repository-relative, regardless of the caller's working directory.

Video precedence: CLI → environment → `.env.local` → missing-input error.
Pack precedence: CLI → environment → `.env.local` → sibling directory
`../valorant_e2e_validation_pack_v3`. The `.env.local` pack fallback is newly added
below the existing CLI/environment choices. Optional profiles/map settings follow
CLI → environment → `.env.local`. Tools follow CLI → environment → `.env.local`
→ PATH discovery → preflight error. Invalid explicit overrides never silently fall back.

## Run the same pipeline

After setup, the first machine check is:

```sh
./run_e2e_pi.sh --check-environment
```

Exit 0 here means environment ready, **not E2E PASS**. Then, with private inputs set:

```sh
git status --porcelain
./run_e2e_pi.sh --video-id match_001
code=$?
printf 'E2E exit code: %s\n' "$code"
```

Or pass paths explicitly (spaces/Unicode are supported with normal shell quoting):

```sh
./run_e2e_pi.sh --video-id match_001 \
  --video '/home/pi/ValorantData/videos/match_001.mp4' \
  --validation-pack '/home/pi/ValorantData/valorant_e2e_validation_pack_v3' \
  --hud-layout 'outputs/hud_profiles/existing/hud_layout.json' \
  --manual-map-id summit
```

The equivalent direct command is `.venv/bin/python scripts/e2e/run_dataset_case.py ...`.
`--manifest` selects a dataset manifest; default is `datasets/manifests/<id>.json`.
`--output` selects a **new** private run directory; default is
`outputs/e2e/<id>/<UTC+unique-id>/`. Existing directories are rejected to prevent
overwriting a prior run. Use `--register` only for an intentionally new dataset
manifest, not to conceal a source/pack mismatch.

Outputs: private raw processing, trace, evaluator results, logs and metadata in the
run directory; sanitized aggregates in `e2e_reports/<id>/` (`summary.json`, history,
HUD diagnostics and Markdown summary). Do not enable `--include-evidence` for an
image-free shared report. Exit **0 = assertions PASS; 1 = completed assertion FAIL;
2 = preflight/runtime/toolchain failure**. A nonzero assertion result is useful
evidence, not permission to loosen identity gates.

The runner only reads Git identity. It never stages, commits, pushes, pulls or
switches branches. Commit source before a clean E2E; initially require empty
`git status --porcelain`, then inspect `summary.json` for `git_is_dirty=false`.
Review and share sanitized reports separately; never force-add raw/private output.

## Troubleshooting and first Pi validation

- `PYTHON_312_REQUIRED`: recreate `.venv` with Python 3.12, not the OS default.
- `*_MISSING`: install Git/FFmpeg, fix PATH or the executable override. Both
  `ffmpeg` and `ffprobe` are required. Broken CLI overrides intentionally reject.
- `DEPENDENCY_UNAVAILABLE_*` / `libGL.so.1`: retain the import error, install the
  appropriate system library and verify the same pinned wheel. Do not add Qt to E2E.
- `FOREIGN_WINDOWS_PATH`: use Pi paths in local config and profile asset references.
- Missing/mismatched pack/video: copy the exact source and intact v3 pack; check hashes.
- Slow runs/OOM: capture elapsed time, RAM, temperature/throttling and private logs.
  Do not reduce sampling, disable detectors or change quality to obtain a result.
- `Permission denied`: Git should track launcher mode 100755. If a copy lost it,
  restore `chmod +x run_e2e_pi.sh`. Shell files must use LF.

ARM64 dependency installation/imports and the direct Python real-video E2E
entrypoint were verified. Still unverified: FFmpeg decode fidelity against Windows,
profile portability, fixed-frame image hashes, numeric detector parity, full E2E
output parity and the separate Pi shell launcher on the actual OS. Compare fixed-regression frame identities and per-frame results
before attributing differences to detectors. Existing fixed replay and comparison
contracts remain unchanged; see `docs/fixed_regression_replay.md`.

The first Pi runtime result is recorded in `docs/pi_e2e_runtime.md`. Runtime
completion does not imply that the remaining 57 detection assertions pass.
