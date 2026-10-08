# VALORANT AI Coach vX.Y.Z

## Highlights

- 

## Windows downloads

- `VALORANT-AI-Coach-X.Y.Z-windows-x64.zip` — portable package
- `VALORANT-AI-Coach-Setup-X.Y.Z-x64.exe` — per-user installer
- `SHA256SUMS.txt` — SHA-256 checksums

## Requirements

- Windows 10 or Windows 11, x86_64
- FFmpeg and ffprobe installed separately or configured from the application settings

Python does not need to be installed to run either packaged distribution.

## Upgrade notes

Installer upgrades preserve the per-user data directory at
`%LOCALAPPDATA%\ValorantAICoach`. Review storage migration notes before publishing
a release that changes database schema.

## Verification

Record the release commit, Windows release workflow run, packaged smoke-test result,
installer smoke-test result, and checksum verification here.

## Known limitations

- FFmpeg/ffprobe are not bundled with official release artifacts.
- Code signing is not configured unless a signing identity is supplied by the release owner.
