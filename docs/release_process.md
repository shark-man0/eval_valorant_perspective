# Release process

This document describes how to create Windows release candidates without changing
Analyzer behavior or weakening the existing CI contract.

## 1. Prepare the version

The application version is defined only in `pyproject.toml`:

```toml
[project]
version = "X.Y.Z"
```

Update that value in the normal development process before creating a release.

Do not copy the version into `VALORANT-AI-Coach.spec` or the Inno Setup script.
`scripts/release/release_tools.py` supplies it to all artifact names and installer
metadata.

A release tag must match the version exactly:

`vX.Y.Z`

The release workflow rejects a mismatched tag.

## 2. Verify normal CI first

Basic CI and Windows verification remain separate from Release Engineering.

Do not weaken their test, coverage, Ruff, mypy, or packaged-smoke requirements merely to
publish a release.

Resolve or explicitly account for pre-existing failures before deciding to publish.

## 3. Build on Windows

Prerequisites for a local release build:

- Windows 10/11 x64
- Python 3.12
- Git
- Inno Setup 6.3+ or 7.x

Run:

```powershell
.\scripts\release\build_release.ps1
```

The script installs Python dependencies using `constraints-windows.txt`, so the
release uses the same pinned direct dependency set as the existing Windows build.

## 4. Release verification performed by the script

The release command performs the following release-specific checks:

1. release-engineering unit tests
2. clean PyInstaller `onedir` build
3. packaged `--smoke-test`
4. release-content denylist check
5. Portable ZIP creation
6. extraction and Portable smoke test
7. Inno Setup compilation
8. silent installer installation
9. installed application smoke test
10. reinstall/upgrade simulation
11. verification that `app.db` and a user-data sentinel survive upgrade
12. silent uninstall
13. verification that user data survives uninstall
14. resolved dependency capture
15. build metadata generation
16. SHA-256 generation

A failure in any step aborts the release build.

## 5. Expected output

For project version `X.Y.Z`, `release\` contains:

- `VALORANT-AI-Coach-X.Y.Z-windows-x64.zip`
- `VALORANT-AI-Coach-Setup-X.Y.Z-x64.exe`
- `SHA256SUMS.txt`
- `BUILD-INFO.json`
- `DEPENDENCIES.txt`
- `RELEASE_NOTES_TEMPLATE.md`

Only the ZIP and installer are required in the checksum file; the metadata files are
supporting release evidence.

## 6. GitHub Actions release candidate build

The dedicated workflow is:

`.github/workflows/release-windows.yml`

It is triggered only by:

- manual `workflow_dispatch`
- a tag matching `v*`

Ordinary branch pushes do not trigger release artifact creation.

The workflow uploads the `release\` directory as a GitHub Actions artifact. It does
**not** create or publish a GitHub Release.

## 7. Review the candidate

Before publishing, verify:

- `BUILD-INFO.json` points to the intended commit and version
- the tag, if used, equals `v<version>`
- both checksum values match the downloaded artifacts
- release smoke tests succeeded
- normal CI status is understood
- no raw videos, validation packs, private profiles, databases, logs, `.env`, or API
  credentials appear in the artifact
- FFmpeg/ffprobe are not unexpectedly bundled
- release notes state any storage migration or known limitation

If the storage schema changed, obtain the storage owner's migration decision before
publishing. Release Engineering must not invent or bypass migrations.

## 8. Publish only after explicit approval

A production GitHub Release is a deliberate manual action. The repository intentionally
does not auto-publish one from the release workflow.

After explicit owner approval, create a GitHub Release for `vX.Y.Z` and attach:

- portable ZIP
- installer EXE
- `SHA256SUMS.txt`
- optionally `BUILD-INFO.json` and `DEPENDENCIES.txt`

Use `.github/RELEASE_NOTES_TEMPLATE.md` as the starting point for release notes.

## 9. Post-release

Retain the workflow run and `BUILD-INFO.json` so an artifact can be traced back to:

- commit
- application version
- Python version
- direct constraint set
- resolved dependency set
- build command

Code signing, certificate custody, update-channel design, and automatic in-app updates
are separate future security/release tasks.
