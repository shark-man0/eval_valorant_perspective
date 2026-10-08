# Security / Privacy Review

## Review metadata

- Repository: `shark-man0/eval_valorant_perspective`
- Review branch: `external/security-review`
- Latest-main baseline at resumed review: `9bb50abd463ab0ef41fb35c59dbe0d7679a64082`
- Original security-review branch base: `deaf3c8ed34a571f38a46e947ade5beea187d930`
- Review date: 2026-10-08
- Scope: security/privacy audit and narrowly scoped security fixes only
- Explicitly out of scope: recognition thresholds, Analyzer accuracy, event/evaluation semantics, schema redesign, installer redesign

## Executive summary

No Critical or High security finding was identified under the stated threat model: a personal-use Windows desktop application operated by a trusted local user, with an uncompromised OS.

The existing design already has several strong controls:

- OpenAI credentials are stored in the OS credential backend via `keyring`; the JSON settings file does not persist the API key.
- `OPENAI_API_KEY` is only a fallback when no stored credential exists.
- OpenAI requests use `store=False`.
- Round Package paths are normalized before remote AI submission so local absolute video/frame paths are not transmitted.
- logging and diagnostic artifacts use centralized redaction.
- diagnostic bundles are allowlist-based and do not recursively archive runtime directories.
- FFmpeg/ffprobe execution uses argument vectors, not `shell=True`, with cancellation/timeouts.
- clip IDs and output paths are contained and publication is create-only.
- SQLite value inputs are parameterized; dynamic SQL is limited to internally generated clauses/placeholders.
- no unsafe `pickle`, `eval`, `exec`, unsafe YAML loading, or external archive extraction path was identified.
- repository `.gitignore` already excludes common credentials, local video, databases, logs, generated output, and local calibration artifacts.

This review fixed security issues in diagnostic path handling, source ZIP privacy, error/traceback privacy, prompt-injection boundaries, and POSIX private-file permissions.

Two material privacy risks remain intentionally unresolved because they cross other owners' contracts:

1. PyInstaller currently packages the local `config/` directory wholesale, so an ignored/private local configuration file can be included in a distributable.
2. selected gameplay/evidence frames sent to OpenAI may contain player names, chat, minimap, or other on-screen private content because the current contract sends the selected frame image, not a privacy-redacted crop.

## Threat model

### Assumptions

- personal-use Windows desktop application
- trusted local user
- local VALORANT recordings
- local SQLite database and generated clips/evidence
- optional OpenAI API usage
- FFmpeg/ffprobe child processes
- user-selected local paths
- diagnostic bundles/logs that may be shared for support
- GitHub-shared E2E reports
- packaged Windows application
- OS compromise is out of scope

### Assets

- OpenAI API key
- raw video
- screenshots/evidence frames/HUD crops
- local paths and usernames
- player-related private data
- SQLite contents
- logs
- analysis results
- diagnostic/performance output
- local calibration/profile artifacts

### Primary abuse cases

- credential or local-path leakage into logs, diagnostics, UI errors, Git, source ZIPs, or packaged binaries
- path traversal or destructive overwrite through generated output paths
- unsafe subprocess command construction
- arbitrary file deletion outside application-owned roots
- SQL injection
- malicious/oversized archive or local input
- prompt injection from OCR/video-visible text
- accidental remote upload of data not required by the feature

## Reviewed surfaces

- `src/valorant_ai_coach/settings.py`
- `src/valorant_ai_coach/logging_setup.py`
- `src/valorant_ai_coach/observability/*`
- `src/valorant_ai_coach/ai/*`
- `src/valorant_ai_coach/visual/semantic.py`
- `src/valorant_ai_coach/video/*`
- `src/valorant_ai_coach/clips/*`
- `src/valorant_ai_coach/storage/*`
- `src/valorant_ai_coach/application/pipeline.py`
- desktop UI error surfaces
- `scripts/diagnostics/*`
- `scripts/e2e/*` and committed E2E reports
- `scripts/package_source.py`
- `.gitignore`
- `VALORANT-AI-Coach.spec`
- `pyproject.toml`, Windows/E2E constraints
- recent repository history (latest 15 `main` commits, secret-like additions only)

## Findings

### SEC-01: diagnostic run ID traversal and destructive bundle overwrite

- Severity: **Medium**
- Status: **Fixed**
- Affected files:
  - `scripts/diagnostics/create_bundle.py`
  - `src/valorant_ai_coach/observability/bundle.py`
- Evidence:
  - the CLI composed `diagnostics_dir / run_id / diagnostic_bundle.zip` from an unrestricted `run_id`
  - bundle creation used ZIP mode `w`, allowing an existing file to be replaced
  - explicitly supplied JSON/log inputs could be symlinks
- Impact:
  - a crafted local invocation could escape the intended diagnostics directory or overwrite an existing bundle
  - a symlink could cause an unintended local file to be read into a shared diagnostic path
  - a pre-existing symlinked run directory could redirect bundle output outside the selected diagnostics root
- Exploitability:
  - local-only and requires control of CLI arguments/files; reduced by the trusted-local-user model, but still unsafe file handling
- Fix:
  - strict bounded run-ID syntax
  - reject `.` / `..`
  - validate before creating parent directories
  - create ZIP with mode `x` (create-only)
  - omit symlinked JSON/log inputs
  - resolve the selected diagnostics root and reject symlinked run directories that escape it
  - regression tests added

### SEC-02: raw traceback and remote exception details exposed through user-visible errors/logs

- Severity: **Medium**
- Status: **Fixed**
- Affected files:
  - `src/valorant_ai_coach/ui/main_window.py`
  - `src/valorant_ai_coach/ui/settings_dialog.py`
  - `src/valorant_ai_coach/ai/coach.py`
- Evidence:
  - analysis failure UI placed `traceback.format_exc()` into a QMessageBox detailed-text surface
  - several UI errors used raw exception strings
  - OpenAI transport/validation exception strings could be propagated/logged
- Impact:
  - local absolute paths, usernames, remote response details, or other private data embedded in exceptions could be shown to users or copied into support material
- Exploitability:
  - requires a failing code path whose exception contains sensitive context
- Fix:
  - full traceback stays only in the redacted log path
  - user dialogs receive sanitized short messages
  - OpenAI request errors/refusals/incomplete responses use generic user-visible messages
  - OpenAI logs keep exception class only, not raw remote error body
  - regression tests cover path/API-key suppression and absence of GUI traceback details

### SEC-03: source ZIP could include ignored/private runtime artifacts

- Severity: **Medium**
- Status: **Fixed**
- Affected files:
  - `scripts/package_source.py`
  - `tests/unit/test_package_source_security.py`
- Evidence:
  - source packaging recursively included allowed directories independently of Git tracking/ignore status
  - a private file placed under `src/`, `config/`, or `scripts/` could therefore enter a source ZIP
- Impact:
  - accidental sharing of credentials, settings, logs, SQLite, local HUD layout, private keys, or recordings
- Fix:
  - explicit private-name/private-suffix exclusions
  - excludes `.env` and `.env.*` anywhere
  - symlink exclusion retained
  - archive remains create-only
  - regression test verifies representative private artifacts are excluded

### SEC-04: private runtime files did not explicitly enforce owner-only POSIX mode

- Severity: **Low**
- Status: **Fixed**
- Affected files:
  - `src/valorant_ai_coach/settings.py`
  - `src/valorant_ai_coach/logging_setup.py`
  - `src/valorant_ai_coach/storage/repository.py`
  - `src/valorant_ai_coach/observability/bundle.py`
- Impact:
  - on Linux/Pi with a permissive umask/custom data directory, settings/log/DB/diagnostics could be more readable than intended
- Fix:
  - best-effort `0600` for settings, primary log, SQLite DB, and diagnostic bundle on POSIX
  - Windows ACL behavior is intentionally not replaced with POSIX emulation
  - regression tests verify POSIX permission bits

### SEC-05: remote observed text needed an explicit prompt-injection trust boundary

- Severity: **Low**
- Status: **Fixed**
- Affected file: `src/valorant_ai_coach/ai/coach.py`
- Evidence:
  - visual semantic flow already said image text is data, not instructions
  - the main AI Coach system instruction did not state the same boundary explicitly
- Impact:
  - OCR/video-visible text could attempt to masquerade as instructions
- Fix:
  - Round Package/image strings are explicitly declared untrusted observations and may not act as system/tool instructions or credential requests
  - local schema validation and deterministic rule authority remain unchanged

### SEC-06: PyInstaller packages the complete local config directory

- Severity: **Medium**
- Status: **Unresolved — handoff to Windows packaging / installer owner**
- Affected file: `VALORANT-AI-Coach.spec`
- Evidence:
  - `datas` contains `(str(project / "config"), "config")`
  - `.gitignore` excludes local `config/hud_layout.json`, but PyInstaller packages the working tree rather than Git-tracked files only
- Impact:
  - a private/generated local calibration/config file can be unintentionally embedded in a distributable even though it is not committed
- Exploitability:
  - accidental leakage during packaging from a developer machine
- Recommended fix:
  - package an explicit allowlist of canonical config assets, or explicitly exclude local/generated/private filenames from the PyInstaller data collection
  - add a packaging test that fails when private runtime artifacts occur in `dist/`
- Why not fixed here:
  - installer/PyInstaller ownership is explicitly assigned to another worker; changing the data manifest may alter packaging behavior

### SEC-07: selected remote-AI frames may contain incidental private HUD/on-screen content

- Severity: **Medium**
- Status: **Unresolved — accepted feature/privacy risk; handoff to Vision/UI owner**
- Affected files:
  - `src/valorant_ai_coach/ai/coach.py`
  - `src/valorant_ai_coach/visual/semantic.py`
- Evidence:
  - AI Coach and semantic vision upload selected frame images as base64 inputs
  - raw source video is not uploaded
  - local absolute paths are removed from the text payload
  - the selected frame itself can still visually contain player names, chat, minimap, overlays, or other gameplay identifiers
- Impact:
  - incidental gameplay/private information can leave the local machine when real API mode/semantic vision is enabled
- Existing mitigation:
  - explicit UI notice
  - Mock AI mode avoids API upload
  - bounded frame selection; no raw video upload
  - `store=False`
- Recommended follow-up:
  - evaluate privacy-safe cropping/masking as a separate Vision contract change
  - make the specific image-upload surface explicit in user consent/help text
- Why not fixed here:
  - frame selection/cropping changes recognition behavior and are outside this review's allowed scope

### SEC-08: dependency/build tool locking is incomplete

- Severity: **Low**
- Status: **Unresolved / documented**
- Affected files:
  - `pyproject.toml`
  - `constraints-windows.txt`
  - build environment
- Evidence:
  - application dependency ranges are intentionally broad in `pyproject.toml`
  - Windows constraints pin most direct dependencies but do not pin `numpy`; E2E constraints do pin `numpy==2.5.3`
  - transitive packages remain pip-resolved by design
  - pip itself is a build tool and is not pinned by project constraints
- Public advisory review (2026-10-08):
  - PyInstaller GHSA-9fxf-4qw3-ghmr (published 2026-08-15) affects versions before 6.22.1; Windows baseline 6.22.3 is patched
  - PyInstaller CVE-2025-59042 / GHSA-p2xp-xx3r-mffc affects versions before 6.0.0; Windows baseline is 6.22.3
  - opencv-python PYSEC-2023-183 affects versions before 4.8.1.78; baseline is 4.14.0.94
  - historical keyring advisory PYSEC-2019-182 was fixed in 0.10.1; baseline is 25.7.0
  - historical NumPy advisories found in the targeted review affect old 1.x ranges; E2E baseline is 2.5.3
  - current pip advisories include fixes in 26.1 and 26.2; build environments should use pip >=26.2
  - malicious typo-squat packages named similarly to `openai` and `jsonschema` exist; the repository uses the legitimate package names
- Recommendation:
  - in a throwaway build environment, run `python -m pip_audit` after installing the exact build/runtime set
  - pin/update pip in the build owner/CI policy to >=26.2
  - consider a complete hash-locked dependency artifact for releases
- Boundary:
  - no CI workflow change was made in this review

### SEC-09: FFmpeg/ffprobe executable resolution trusts the local user/environment

- Severity: **Informational**
- Status: **Accepted by threat model**
- Evidence:
  - default names resolve via PATH
  - explicit user-provided binary path is supported
  - execution is argument-vector based with no shell
- Impact:
  - a compromised PATH or intentionally malicious executable can run code
- Assessment:
  - this is inherent to the explicit external-binary contract and an already-compromised/untrusted local environment is outside the threat model

## Credential handling

Assessment: **Good after review; no plaintext config storage observed.**

- OS credential backend via `keyring`
- stored key wins over environment fallback
- `OPENAI_API_KEY` is fallback only
- API key is not serialized into settings JSON
- API input field is password-masked
- diagnostic/log sanitization recognizes API-key/authorization/token/password/secret fields
- source packager excludes common credential file forms
- no API key is intentionally included in PyInstaller datas
- OpenAI errors no longer echo raw transport details through application error messages

Repository history scan:
- latest 15 `main` commits were scanned for common OpenAI/GitHub/AWS/private-key signatures in added patch lines
- three matches were found, all in `tests/unit/test_observability.py`
- patch context confirmed they are synthetic redaction-test tokens, not live credentials
- no live credential was identified in that scan
- this is a bounded recent-history review, not a substitute for GitHub Secret Scanning across the full repository history

## Logging and diagnostic privacy

Assessment: **Good with fixes.**

- bounded rotating logs
- rendered records are sanitized after formatting, including tracebacks
- absolute Windows/POSIX paths and home paths are redacted
- secret-like field values are redacted
- diagnostic snapshots use allowlisted environment information rather than dumping the full environment
- bundle inputs are allowlisted, bounded, sanitized, and now reject direct symlinks
- bundle excludes raw video, screenshots/HUD crops, DB, raw environment, credentials, raw API response, and arbitrary user files by policy
- bundle creation is now create-only

Residual risk:
- regex redaction is defense-in-depth and cannot mathematically identify every secret format
- private files outside the explicit bundle allowlist remain safer than relying on redaction alone

## File/path handling

Assessment: **Strong containment in security-sensitive output paths.**

- clip IDs use a restricted identifier pattern
- clip output resolves under the configured clip directory
- existing clip targets are never overwritten
- frame/evidence persistence uses random staging paths and containment checks
- match deletion validates IDs and uses a contained safe-tree removal
- repository clip cleanup verifies ownership root before unlink
- diagnostic run IDs now cannot traverse directories
- diagnostic CLI rejects a symlinked run directory that resolves outside the selected diagnostics root
- valid absolute source-video and explicit FFmpeg paths remain allowed as required by contract

## Temporary files

Assessment: **Good.**

- clip partial filenames include UUIDs
- clip publication is create-only and partials are cleaned on cancellation/failure
- frame extraction uses a UUID staging directory and rollback/cleanup
- persisted evidence has a staging/backup publish pattern
- private durable evidence is retained by design for resume/review and is not treated as accidental temporary output

Residual:
- evidence/frame files themselves do not receive explicit `0600` file modes; normal user-private data directories are relied on. If Linux/Pi uses a shared/permissive custom data directory, directory permissions should be reviewed separately.

## Subprocess review

Assessment: **Good.**

- no `shell=True` path identified in reviewed runtime subprocess calls
- commands are argument vectors
- FFmpeg/ffprobe receive source/output paths as distinct arguments
- timeout and cancellation behavior exists
- child stdin is disabled for video/clip subprocess paths
- stderr is bounded before being surfaced, and centralized log/UI redaction now limits privacy leakage
- explicit binary override remains supported by contract

## SQLite review

Assessment: **Good.**

- values are parameterized
- dynamic SQL identified in the repository is limited to internal placeholder counts/static clauses rather than user-controlled identifiers
- migrations use explicit transactions
- foreign keys and busy timeout are enabled
- clip deletion is contained to the configured clip directory
- primary DB receives owner-only mode on POSIX after review

Residual:
- WAL/SHM files are created by SQLite and inherit platform/directory policy; use a user-private data directory on Linux/Pi.

## Archive handling

Assessment: **No external archive extraction path identified.**

- source packaging creates ZIPs; it does not extract them
- validation-pack checking reads archive members for comparison; it does not write/extract member paths
- therefore Zip Slip/symlink-entry extraction controls are not applicable to current application behavior
- source ZIP generation is create-only and now excludes additional private runtime artifacts

## JSON/config and deserialization review

- no `pickle`, arbitrary object deserialization, unsafe YAML loader, `eval`, or `exec` path identified
- canonical AI/event/round data uses schema validation
- settings parsing validates/coerces known fields instead of executing data
- some trusted/local JSON reads are not globally byte-bounded; with a trusted local user this is a Low/Informational local-DoS residual rather than an Internet-facing security boundary

## OpenAI data exposure

### AI Coach

Sent:
- sanitized Round Package object shape
- gameplay events/facts/state/selected rules needed for evaluation
- selected evidence-frame images
- deterministic decision bindings

Not sent intentionally:
- raw video file
- absolute source-video path
- absolute local frame paths
- API key in prompt
- arbitrary local files

Controls:
- `store=False`
- bounded candidate count and evidence-image count
- schema validation
- prompt-injection trust-boundary instruction
- transport error body not logged/user-displayed after this review

### Visual semantic adapter

Sent:
- selected timestamped frame images
- a fixed visible-fact extraction instruction and strict output schema

Controls:
- text in images explicitly treated as data, never instructions
- individual frame-size bound
- call budget
- `store=False`
- remote error body is not logged

## Shared output / Git hygiene

- committed E2E reports were checked for obvious home/absolute path, API-key, hostname/username, MAC/IP marker leakage; no such markers were found in the reviewed committed reports
- `.gitignore` covers common credential, video, DB, log, output, local data, and generated HUD-layout patterns
- source package privacy was hardened independently of `.gitignore`, because package creation works from the filesystem rather than the Git index

## Dependency review

The review used the pinned Windows/E2E baseline plus a targeted public OSV/PyPI advisory search on 2026-10-08.

Baseline reviewed:
- PySide6 6.11.2
- jsonschema 4.26.0
- keyring 25.7.0
- openai 2.54.0
- opencv-python 4.14.0.94
- shapely 2.1.2
- numpy 2.5.3 in E2E constraints
- PyInstaller 6.22.3

No targeted public advisory found in this review identified those exact pinned direct versions as affected. This is **not** equivalent to a complete transitive `pip-audit`, and transitive packages are not fully locked.

Notable supply-chain observation:
- similarly named malicious packages have recently appeared on PyPI, including `openaii` and `jsonschemavalidation`
- these are different package names from the legitimate `openai` and `jsonschema` dependencies used here
- exact dependency names and release provenance should be preserved

## Denial-of-service review

Reasonable desktop bounds exist for:
- AI candidate count
- selected image count
- semantic frame size
- diagnostic JSON/log bundle size
- rotating logs
- cache size/entry count
- frame extraction count
- subprocess timeouts

Residual:
- some local JSON/config files can be arbitrarily large if a trusted local user replaces them. No Internet-facing parsing endpoint exists, so no architecture-level change was made.

## PyInstaller / installer review

Positive:
- no API key, DB, logs, or environment dump is explicitly listed in `datas`
- application data directory is per-user writable; executable directory is not used as the runtime database/settings root
- current PyInstaller baseline 6.22.3 is newer than both the 6.0.0 fix for CVE-2025-59042 and the 6.22.1 fix for GHSA-9fxf-4qw3-ghmr

Unresolved:
- complete local `config/` directory is included. See SEC-06.

## Fixed findings

- SEC-01 diagnostic traversal/overwrite/symlink input
- SEC-02 UI traceback and raw remote error privacy
- SEC-03 source-package private artifact inclusion
- SEC-04 POSIX owner-only permissions for core private artifacts
- SEC-05 explicit prompt-injection trust boundary

## Unresolved findings / handoff

### Windows Packaging / Installer owner

1. Replace `VALORANT-AI-Coach.spec` whole-`config/` inclusion with an allowlisted/tracked canonical asset set, or explicitly exclude private/generated config.
2. Add a packaged-distribution privacy assertion that rejects `hud_layout.json`, settings, DB, logs, `.env`, credentials, and diagnostics.
3. Ensure release build tooling uses a non-vulnerable pip (>=26.2 as of this review).

### Vision / UI owner

1. Evaluate masking/cropping of player names, chat, or unrelated overlays before selected images are sent remotely.
2. Keep user consent/help text explicit that selected frame images—not the raw VOD—leave the machine in real API modes.

## Residual risks

- OS credential stores cannot protect secrets after full OS/user-session compromise; explicitly out of scope.
- user-selected external executable paths are trusted code by design.
- regex redaction is not a substitute for allowlisting; shared diagnostic collection should remain allowlist-only.
- raw/evidence frame privacy depends on the content visible in the selected game frame.
- complete transitive dependency vulnerability status requires a fresh environment-specific audit at release time.

## Verification plan

Required before merge:

- `python tests/validate_dataset.py`
- full repository pytest with coverage threshold unchanged at 75%
- `python -m ruff check src tests scripts/e2e`
- `python -m mypy src/valorant_ai_coach`
- Windows PyInstaller build
- packaged application smoke test
- Windows artifact upload

Security regression coverage added for:

- diagnostic traversal rejection
- diagnostic run-directory symlink escape rejection
- create-only diagnostic bundle
- symlinked diagnostic input omission
- source ZIP private-artifact exclusions
- source ZIP no-overwrite behavior
- OpenAI error redaction
- prompt-injection trust boundary
- GUI traceback/private-path suppression
- POSIX private permissions for settings/log/DB/bundle
