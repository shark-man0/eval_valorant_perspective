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


## SEC-08 incremental audit (2026-10-13, Issue #34)

The Windows main verification run 38382176853 resolved CPython 3.12.10,
PySide6 6.11.2 (including Addons, Essentials, shiboken6), NumPy 2.5.4,
OpenCV 4.14.0.94, OpenAI SDK 2.54.0, PyInstaller 6.22.3, Ruff 0.16.9,
setuptools 84.0.0, and the direct versions already constrained. These
are observed Windows versions, **not** a Linux, ARM64 or future guarantee.
The validated NumPy 2.5.4 Windows x64 CPython 3.12 wheel is listed on PyPI
with SHA-256 a7b1b6353e36a7e50de2973a38d705c88ee93adcf120673cee7f45a4a3fa223a.
The Windows constraint now pins this *observed* NumPy version; the shared
E2E baseline remains 2.5.3 and is intentionally unchanged.

The official Windows release script now fails closed on pip check and,
after capturing all resolved packages into DEPENDENCIES.txt, runs the
2.10.1 version of pip-audit **from a separate virtual environment** using
--no-deps on pinned freeze requirements (excluding only the editable
first-party project, which has no PyPI vulnerability record). It writes
DEPENDENCY-AUDIT.json with dependency vulnerability evidence. A detected
vulnerability, unavailable advisory service or install failure causes the
release build to stop, not bypass the audit. The audit environment is
created under work/, outside the PyInstaller allowlisted payload.
Release BUILD-INFO.json also records installed pip/setuptools/wheel/
PyInstaller versions; output ZIP and EXE still receive SHA-256 checksums.

### Strategy decisions

| Method | Decision | Rationale |
| --- | --- | --- |
| Pin verified direct NumPy on Windows | Adopt | Closes actual Windows version drift without a speculative upgrade. |
| Snapshot all transitive versions and audit | Adopt | Existing DEPENDENCIES.txt plus new audit JSON; low impact on Qt. |
| Full hash-locked Windows wheelhouse | Defer | Requires collecting and verifying every platform-specific transitive wheel on an isolated Windows runner; source build dependencies are also not locked. |
| Cross-OS shared lock | Reject | Python/ABI/platform-specific wheels make Linux and Windows resolutions differ. |
| SBOM / attestation / bit-for-bit PyInstaller output | Future | Candidate for additional CI jobs and multi-build validation, not yet verified. |
| Broad PySide6/OpenCV/NumPy/PyInstaller upgrades | Reject here | Would confound Issue #18 Qt shutdown investigation and regression baselines. |

The PyInstaller GHSA-9fxf-4qw3-ghmr affects versions before 6.22.1;
the observed Windows 6.22.3 is above that patched threshold. This is
a **targeted advisory check**, not a complete clean bill from pip-audit.
Full release vulnerability audit has not been executed in this session:
the release workflow is manual/tag triggered and requires Windows/Inno Setup.
The standalone environment available to this review is not the project's
Python 3.12 Windows interpreter, and its pip check is not representative.

For an official release, run on Windows x64 with network access to the
advisory service. Verify DEPENDENCY-AUDIT.json, DEPENDENCIES.txt, BUILD-INFO.json,
artifact checksums, packaged smoke test and absence of secrets/videos/logs.
Maintain a separate OS-native wheel-hash lock only after independent
download/installation validation. Never claim a release is bit-for-bit
reproducible solely from freeze lists or artifact hashes.


## Independent Windows PyInstaller comparison (Issue #34)

The `.github/workflows/release-reproducibility.yml` workflow builds the
**same immutable PR-head commit** on two distinct GitHub-hosted Windows
runners, each with a new Python 3.12 environment. Both jobs install the
constrained dependencies, require `pip check`, build a fresh PyInstaller
onedir payload, and run the packaged smoke test. Each saves the exact
resolved pip version list, Python/build-tool versions and content SHA-256
of every regular file in the packaged tree. The comparison job records
missing, extra and byte-different relative paths, as well as Python,
package and tool-version drift; it retains a JSON report. It does **not**
claim that a green workflow means bit-for-bit reproducibility: compare the
explicit `bit_for_bit_equal` and `reproducible_environment` JSON fields.

This is an **independent onedir build probe**, not two complete release
builds: Inno Setup installer/ZIP reproducibility, FFmpeg/Inno Setup
checksums, provenance signatures and transitive wheel hash locks still
require separate official release evidence. If the content hashes differ,
review the named differing files before deciding whether an acceptable
nondeterminism (timestamps, bytecode, embedding) explains the delta; never
suppress the mismatch by filtering files from the inventory.

## Confirmed 2-run baseline and deterministic PyInstaller inputs

The initial independent rebuild workflow #38501514340 (commit `a72a702`)
created 425 files on each of two distinct Windows runners with the same
resolved Python and build-tool versions. **Five byte hashes differed**:
`VALORANT-AI-Coach.exe`, `_internal/base_library.zip`, and the three
`_internal/{jsonschema-4.26.0,keyring-25.7.0,numpy-2.5.4}.dist-info/RECORD`
files. The comparison was a failure of bit-for-bit identity despite green
build and smoke-test steps, not a successful reproducibility certification.

PyInstaller 6.22.3 documents both `PYTHONHASHSEED` (hashed collection and
bytecode stability) and `SOURCE_DATE_EPOCH` (Windows executable PE build
timestamp). The official release script and independent comparison jobs
now set hash seed 1 and the actual source commit's Unix timestamp before
the PyInstaller build. The comparison is rerun without ignoring or deleting
any of the five differing files; an identical result must be observed
before reporting byte reproducibility. Remaining differences may arise
from package RECORD data or build tools and require further investigation.

## Isolated remaining RECORD nondeterminism (2026-10-14)

In the independent rerun #38502011265 at commit `1288066`, both
425-file payloads had identical environment metadata, and the EXE and
`base_library.zip` became byte-identical after the reproducible-build
settings. The only remaining mismatches were the `RECORD` files for
jsonschema 4.26.0, keyring 25.7.0, and NumPy 2.5.4.
A new evidence-only CSV-row hashing field now allows the next independent
run to distinguish changed filenames/record entries from differences
in CSV formatting or row order. No `RECORD` content is omitted from
bundle hashing or normalized inside the distributed application. Absolute
runner paths are hashed rather than emitted to public artifacts.
