# Windows distribution

This document defines the supported Windows distribution contract for VALORANT AI Coach.

## Supported platform

Official release artifacts target:

- Windows 10 and Windows 11
- x86_64 / x64-compatible systems
- a packaged PyInstaller runtime; end users do not install Python

The source-development workflow still uses Python 3.12.

## Distribution formats

The release build produces two user-facing formats from the same PyInstaller `onedir`
output.

### Portable package

`VALORANT-AI-Coach-<version>-windows-x64.zip`

Extract the archive and run `VALORANT-AI-Coach.exe`. The archive root is versioned,
but the executable name stays stable.

The portable archive contains only packaged runtime files plus
`README-Windows.md`. It must not contain repository tests, Git metadata, validation
packs, recordings, local databases, logs, `.env` files, API credentials, or developer
outputs.

### Installer

`VALORANT-AI-Coach-Setup-<version>-x64.exe`

The installer uses Inno Setup because the application is an x64 desktop application
with a single onedir payload and does not require an MSI-specific deployment model.

The installer is intentionally per-user:

- `PrivilegesRequired=lowest`
- default install directory:
  `%LOCALAPPDATA%\Programs\VALORANT-AI-Coach`
- Start Menu shortcut is created
- desktop shortcut is optional and unchecked by default
- a stable Inno Setup `AppId` identifies upgrades
- uninstall support is enabled

Administrator rights are not required for the normal installation path.

## User data is separate from application files

Application binaries live under the install directory or the extracted portable folder.

Persistent user data remains under:

`%LOCALAPPDATA%\ValorantAICoach`

The current application contract stores data such as:

- `settings.json`
- `app.db`
- `clips\`
- `matches\`
- `cache\`
- `logs\`
- `temp\`

The OpenAI API key is not stored in `settings.json`. The existing Windows Credential
Manager / keyring contract remains unchanged.

Release artifacts must not contain an existing settings file, database, logs, generated
clips, analysis output, API key, or local credential material.

## Upgrade behavior

Installing a newer version with the same `AppId` updates application files in the
per-user install directory.

The installer does not own `%LOCALAPPDATA%\ValorantAICoach`, so an upgrade must not
remove settings, SQLite data, generated clips, saved analysis results, or the keyring
credential.

Database schema migration remains the responsibility of the existing storage contract.
Release Engineering must not invent a migration when the storage schema changes.

The release build performs an install/reinstall smoke test and verifies that a user-data
sentinel and `app.db` survive the second installation.

## Uninstall behavior

The Inno Setup uninstaller removes installed application files and shortcuts.

It does not declare `[UninstallDelete]` entries for
`%LOCALAPPDATA%\ValorantAICoach`. User-generated analysis data and clips therefore
remain by default.

Removing retained user data is a separate explicit user action and is not performed
silently by the installer.

## FFmpeg and ffprobe

Official release artifacts do **not** bundle `ffmpeg.exe` or `ffprobe.exe`.

The user must either:

1. install FFmpeg/ffprobe so both commands are available on `PATH`, or
2. select explicit executable paths in the application settings.

This policy avoids redistributing an arbitrary third-party binary whose effective
license depends on how that particular FFmpeg build was configured. Do not commit or
embed FFmpeg binaries into an official release without a separate provenance and
license review.

The application can launch in Mock mode without FFmpeg being invoked immediately, but
video probing and clip generation require FFmpeg/ffprobe before real video work can
complete.

## Packaged resources

`VALORANT-AI-Coach.spec` remains a PyInstaller `onedir` build.

The release bundle includes only runtime resources required by the packaged application:

- canonical top-level config JSON used at runtime
- canonical JSON schemas
- runtime Visual v2 config/schema JSON
- production Map/Zone v3 config/schema JSON and the production minimap reference
- the default Mock HUD runtime input, remapped to
  `runtime/mock_cases/TC-029/input.json`

Repository test trees and Map/Zone fixtures are not packaged.

PyInstaller's standard hooks provide the Python runtime, PySide6/Qt runtime and plugins,
OpenCV runtime, SQLite standard-library support, and imported Python dependencies.
The explicit hidden imports retain the Windows keyring backend.

## Version and artifact naming

The single source of truth for the application version is:

`pyproject.toml -> [project].version`

Release scripts derive all artifact names from that value. Do not manually copy the
version into the installer script.

Expected names for version `0.1.0` are:

- `VALORANT-AI-Coach-0.1.0-windows-x64.zip`
- `VALORANT-AI-Coach-Setup-0.1.0-x64.exe`

A release tag must be exactly `v<project-version>`, for example `v0.1.0`.

## Building a release

On Windows, install Inno Setup 6.3+ or 7.x and run:

```powershell
.\scripts\release\build_release.ps1
```

The script creates/reuses `.venv`, installs the pinned Windows dependency set, runs
release-engineering tests, builds PyInstaller, performs packaged smoke tests, builds and
tests the installer, and writes final artifacts under `release\`.

A GitHub-hosted build can be started with the dedicated
`Windows release build` workflow. That workflow is separate from basic CI and only
runs on manual dispatch or a `v*` tag.

## Smoke-test coverage

The release build verifies:

- PyInstaller executable startup with `--smoke-test`
- Qt GUI construction in offscreen mode
- canonical config and schema loading through the real composition root
- production Map/Zone resource loading
- writable per-user data directory
- SQLite initialization
- log directory initialization
- portable ZIP extraction and launch
- silent installer installation
- reinstall/upgrade preservation of user data
- silent uninstallation while retaining user data

OpenAI network calls and raw-video analysis are intentionally excluded from release
smoke tests.

## Checksums

`SHA256SUMS.txt` contains SHA-256 digests for the portable ZIP and installer.

PowerShell verification example:

```powershell
Get-FileHash .\VALORANT-AI-Coach-0.1.0-windows-x64.zip -Algorithm SHA256
Get-FileHash .\VALORANT-AI-Coach-Setup-0.1.0-x64.exe -Algorithm SHA256
```

Compare the values with `SHA256SUMS.txt` from the same release.

## Build traceability

Each release build also writes:

- `BUILD-INFO.json`
- `DEPENDENCIES.txt`
- `RELEASE_NOTES_TEMPLATE.md`

`BUILD-INFO.json` records the application version, commit, Python version, platform,
architecture, Windows constraints digest, resolved dependency-set digest, and the build
command.

This is traceability, not a claim of bit-for-bit reproducibility.

## Known limitations

- FFmpeg/ffprobe are external dependencies and are not bundled.
- Windows code signing is not configured by this repository.
- SmartScreen reputation therefore depends on future signing/publisher setup.
- The packaged Mock runtime includes only the default `TC-029` demonstration case;
  the repository's test dataset is not distributed.
- Windows ARM is not an official target. x64 emulation may work where Windows supports
  it, but ARM-native packaging is outside this release contract.
