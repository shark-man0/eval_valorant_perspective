# E2E shared reports

This directory is Git-trackable. No raw video or full analyzer trace belongs here.
`run_e2e_windows.ps1` creates `<video_id>/summary.json`, `<video_id>/history.json`
and a small README. Inspect them before committing. The runner never runs Git writes.

Evidence images are OFF by default. Explicit `-IncludeEvidence -EvidenceLimit 3`
exports at most 3 HUD crops (maximum allowed: 10) into `<video_id>/evidence/`.
Images cannot be guaranteed anonymous: inspect them manually before `git add`.
Previously exported evidence is not removed by a later run without that option.

See [Windows E2E instructions](../WINDOWS_E2E.md) for setup and report interpretation.
