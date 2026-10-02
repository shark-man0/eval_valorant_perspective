# Windows-local raw video / Git-shared E2E results

## One execution path

`run_e2e_windows.ps1` → `scripts/e2e/run_dataset_case.py` → existing
`tests/e2e/run_real_video.py` → existing trace adapter → existing
`tests/e2e/evaluate_saved_trace.py` / Validation Pack evaluator → sanitized report.
`diagnose_hud_video.py` remains a separate optional diagnostic, not a second Analyzer.
`run_windows.ps1` and `build_windows.ps1` remain application launch/build commands.
No runner invokes `git add`, `commit`, `push`, or `pull`.

## Requirements and input setup

- Windows 10/11; Python 3.12 and its `py` launcher; Git; FFmpeg/ffprobe on PATH.
- First execution creates/reuses `.venv` and installs the application dependencies with
  `constraints-windows.txt`. Later executions check the dependency stamp, imports and
  `pip check`; unchanged healthy environments need no reinstall.
- Unzip the separately provided **unaltered** `valorant_e2e_validation_pack_v3.zip`
  on Windows. The pack is required even if the source repository was cloned.
  It is not automatically fetched, uploaded, or silently replaced with mock GT.
- Keep the raw recording outside the repository. Renaming it to `match_001.mp4` is fine;
  identity is SHA-256, never the filename. The supplied `match_001` manifest identifies
  the original 171-second recording from the v3 pack, not an arbitrary match.
- For useful perception results configure your real HUD/Visual profiles using existing
  calibration instructions. `-HudLayout` / `-VisualProfile` / `-ManualMapId` /
  `-MapClientBuild` are optional passthroughs to the existing real pipeline.
  No profile means existing defaults; it does **not** mean validated HUD accuracy.
- The runner uses real analyzers but no paid Semantic Vision/AI Coach API calls.
  This is an Analyzer/GT validation workflow, not a complete AI Coach quality test.

## Path precedence (resolved in Python, once)

| Input | Priority |
| --- | --- |
| Video | `-Video` → `VALORANT_E2E_VIDEO` → repository `.env.local` |
| Validation Pack | `-ValidationPack` → `VALORANT_E2E_PACK` → sibling `../valorant_e2e_validation_pack_v3` |

Use absolute Windows paths. `.env.local` can contain
`VALORANT_E2E_VIDEO="D:\ValorantData\videos\match_001.mp4"`.
Only this key is read; there is no command/interpolation expansion or other environment loading.
The file stays ignored. CLI arguments override environment variables.

## Manifest and registration

`datasets/manifest.schema.json` validates `datasets/manifests/<video_id>.json`.
Fields: schema version, safe video ID, logical basename, SHA-256, duration, dimensions,
FPS, audio-track count, Validation Pack name/fingerprint and generated assertions hash.
No absolute paths, credentials or machine names are permitted.
The filename is logical (`<video_id>.<extension>`), deliberately not an identifying local filename.

SHA-256 is streamed from the local video. Before Analyzer execution it must match both
the dataset manifest **and** the pack's `MANIFEST.json.source_sha256`. Pack resource
fingerprints and metadata also must match. The existing pack validator runs as a preflight.
The fingerprint hashes the relative paths and bytes of JSON/Python files in the pack;
do not edit/reformat the canonical pack after registration.

For a NEW dataset ID, use explicit `-Register` with that video's matching Validation Pack.
This validates and writes a new manifest, then runs E2E. Existing manifests are never
overwritten, including when `-Register` is repeated. Do not register another recording
against this pack's GT; prepare a matching GT/pack first. Changing pack versions requires
an explicit reviewed manifest update, not an automatic rewrite.

## Local vs shared files

```text
outputs/e2e/<video_id>/<UTC-run-id>/     # ignored, Windows-only
  raw_processing.json
  e2e_trace.json
  evaluation_report.json
  processing_frames/                  # can be large
  analyzer.log / evaluation.log / validation_pack.log
  runtime_data/                       # existing pipeline data
  evidence-local/                     # optional original evidence frames

e2e_reports/<video_id>/                # Git-shareable after review
  summary.json
  history.json
  hud_calibration.json                # image-free anchor statistics, automatic
  README.md
  evidence/hud_00.jpg ...              # only with -IncludeEvidence
```

Each local execution has a fresh directory; an old PASS cannot be reused as current output.
Preflight/processing failures are nonzero and generate a sanitized failure report when
the Python runner has started with a valid VideoId. Earlier PowerShell/toolchain failures
return nonzero without a new report: check the exit code and `executed_at`, not an old file.
Exit 0 = evaluator PASS, 1 = evaluated FAIL, 2 = Python preflight/runtime failure.
Toolchain/bootstrap failures are also nonzero.

## Shared result and privacy

The summary identifies commit SHA, dirty state, source SHA, execution time, pack identity,
and settings/dirty-code fingerprints. It contains layer counts and bounded assertion
details (expected/actual selected values, time range, controlled actor/state/owner/source,
confidence and diagnostic codes). Report data is allowlisted, not a copy of the raw JSON.
Paths, request headers, environment data, tokens, arbitrary diagnostics and player names
are not shared. Missing evidence remains null/unknown. Counts distinguish evaluator
failure messages from deduplicated negative assertions; consult the summary's labels.
An empty detection output satisfying all prohibitions is not proof of successful detection.

`summary.json` is latest. `history.json` retains at most 20 compact entries, replacing the
entry for the same source/commit/pack/dirty-code/settings identity. Execution timestamp
does not create duplicate history. Dirty-code fingerprints exclude generated reports and
dataset manifests, while `git_is_dirty` still describes the whole worktree.
Full reports are size-limited (128 KiB); detail truncation is explicit, not a silent PASS.

`-IncludeEvidence` exports only a bounded HP/Armor HUD crop around selected failures,
never an entire screen/chat/minimap/kill-feed by default. Default limit 3, maximum 10.
Images are **not guaranteed anonymous**, especially with custom UI/overlays: review manually.
Only reference-resolution video can use this crop export. Without this flag no new image
is copied. Existing evidence from a previous opt-in remains until manually removed.

This is not a fine-tuning dataset: raw video, dataset manifest, human ground truth,
analyzer output and E2E report have distinct roles.

### Image-free HUD profile diagnostics

Geometry anchors no longer establish live-player identity, masked or unmasked.
Use the single `python -m valorant_ai_coach.hud.calibrate_profile` command below; it generates
geometry masks and separate, unmasked HP/ability/weapon-ammo structure references from
unlabelled frames. Training-only modal clustering finds consistent structures even when other
HUD modes dominate. NCC remains >= .90. A chosen cluster needs at least three observations
per split and comparable prevalence in heldout frames; no holdout-driven ROI reselection.
It preserves existing readers and signals. No GT, validation pack, expected state, or API is
an input to generation. There is no intermediate image approval or JSON editing step.
The optional `calibrate_temporal` remains a geometry-only diagnostic tool, not the recommended
end-to-end workflow. Keep all generated assets in ignored `outputs/`.
The `identity_reasons`, sanitized `temporal_generation`, and `automatic_identity_generation`
statistics are automatically shared in the E2E calibration reports.
Use explicit `-ManualMapId summit` only when you know that is the actual map;
map selection does not bypass position/ownership/calibration requirements.

Keep using the same `-HudLayout` and its adjacent `.templates.json` profile locally.
The runner automatically exports fixed anchor names, thresholds, mask presence, image
dimensions and SHA-256, accepted/rejected/unscored counts, finite confidence min/median/max,
missing-anchor co-occurrence and geometry success rates. No extra flag or image upload
is required. `hud_calibration.json` and `summary.hud_calibration` contain the same metrics.
Fresh geometry and retained valid geometry are counted separately from state evidence.
These are sampled-frame rates, not time-weighted accuracy. Missing diagnostics from old
outputs are marked unavailable, never reconstructed. See
[HUD_DIAGNOSTICS_REVIEW.md](HUD_DIAGNOSTICS_REVIEW.md) for interpretation and the baseline.

### Automatic local profile → Windows E2E (PowerShell)

Run from the updated repository root. The example uses the default Desktop video filename;
set only the three input paths below to your actual local files. Use your existing calibrated
layout if available: its adjacent `.templates.json` is loaded automatically. Keep that base
profile's assets locally because inherited readers can still reference them.

```powershell
$ErrorActionPreference = 'Stop'
$video = Join-Path ([Environment]::GetFolderPath('Desktop')) 'Valorant_09-25-2026_0-37-29-379.mp4'
$baseLayout = (Resolve-Path (Read-Host 'Path to the previous Windows HUD layout JSON')).Path
$pack = (Resolve-Path '..\valorant_e2e_validation_pack_v3').Path

# Existing Windows E2E environments can reuse .venv; bootstrap when absent.
if (-not (Test-Path '.\.venv\Scripts\python.exe')) {
  py -3.12 -m venv .venv
  if ($LASTEXITCODE -ne 0) { throw 'venv creation failed' }
}
.\.venv\Scripts\python.exe -m pip install -c constraints-windows.txt -e .
if ($LASTEXITCODE -ne 0) { throw 'Dependency installation failed' }
Get-Command ffmpeg, ffprobe -ErrorAction Stop | Out-Null

# New directory on every run; no overwriting an earlier profile.
$out = Join-Path (Get-Location).Path ('outputs\hud_profiles\auto_' + [guid]::NewGuid().ToString('N'))
.\.venv\Scripts\python.exe -m valorant_ai_coach.hud.calibrate_profile `
  --video $video `
  --layout $baseLayout `
  --output $out `
  --samples 64
if ($LASTEXITCODE -ne 0) { throw 'Profile generation failed; E2E was not started' }
$hudLayout = Join-Path $out 'hud_layout.json'

# No image/JSON editing between these two commands.
.\run_e2e_windows.ps1 `
  -Video $video `
  -VideoId match_001 `
  -ValidationPack $pack `
  -HudLayout $hudLayout `
  -ManualMapId summit
```

Outputs: `hud_layout.json`, `hud_layout.templates.json`, `anchors/*.png` (including masks),
`identity/*.png` (available references), `profile_diagnostics.json`, and, when geometry is
generated, `temporal_stats.json`. No images are copied into `e2e_reports` by this workflow.
Do not add `-IncludeEvidence`. Only sanitized counts, status, dimensions and hashes are shared.

**Generation success means a loadable profile, not verified HUD accuracy.** Insufficient
identity references have status `insufficient_evidence` and remain disabled; the E2E can report
unknown or fail to form a round. It does not ask for hand editing. If stable geometry cannot
be generated, an existing local anchor profile is retained; with neither, generation fails
without publishing a partial directory. Existing thresholds are not lowered.

Old clear/background references are no longer generated or used as evidence. Regenerate
your profile, including when the previous CLI reported success. The new spectator detector
requires a long panel boundary, closed portrait-like box and aligned text components in the
layout's panel ROI. It learns positive component locations from supported training/holdout
observations, or extracts them from an existing configured positive full-panel template.
On regeneration, an existing valid component detector can also be inherited when no new
positive cluster is available. Its dimensions and assets are checked; this retains a reference,
not a previous frame's state. Source and new geometry asset paths/hashes are both excluded
from identity inheritance.
It never calls an arbitrary texture cluster "spectator". This shape prior is conservative;
UI variants that do not meet it are unsupported, not automatically labelled absent.

Runtime measures all three edge-component groups, not background pixel agreement. With an
observable ROI, all groups >= .90 prove presence; all <= .10 provide explicit structural
exclusion (`checked=true`, `panel_present=false`) only after a whole-ROI search finds neither
a panel candidate nor a displaced characteristic component. Position/structure mismatches
give `panel_structure_mismatch` and unknown. Partial/ambiguous structure, unreadable
ROI, size mismatch, or missing positive reference give `checked=false` and unknown. A legacy
pixel template's failure alone cannot establish absence. Current-frame HP/ability/ammo
structures and remote/spectator/menu/map blockers remain required; no live persistence.
There are no new dependencies or paid API calls.

Compare per-role candidate/rejection/support counts in `automatic_identity_generation.references`,
`identity_missing`, `spectator_checks`, `identity_reasons`, geometry success,
`geometry_valid_state_unknown`, Visual eligibility and Map unresolved counts against the
Windows baseline. Mac synthetic tests do not establish real-video improvement. PowerShell
execution itself must be checked on Windows. Map diagnostic counts now separate calibration
skipped due to HUD eligibility, attempted calibration failures, marker missing/not evaluated,
ownership rejection and location resolution. Downstream "not evaluated" is not a CV failure.

## Minimal workflow (PowerShell)

1. First setup (once):

   ```powershell
   git clone https://github.com/shark-man0/eval_valorant_perspective.git
   cd eval_valorant_perspective
   ```

2. Put the original recording at `D:\ValorantData\videos\match_001.mp4` and unzip the
   Validation Pack at `D:\ValorantData\valorant_e2e_validation_pack_v3`. Set its path:

   ```powershell
   $env:VALORANT_E2E_PACK = 'D:\ValorantData\valorant_e2e_validation_pack_v3'
   ```

3. On each validation run:

   ```powershell
   git pull
   .\run_e2e_windows.ps1 -Video 'D:\ValorantData\videos\match_001.mp4' -VideoId match_001
   $LASTEXITCODE
   ```

4. Inspect the result (a FAIL can still be valuable to share):

   ```powershell
   Get-Content .\e2e_reports\match_001\summary.json
   git diff --stat
   ```

5. After reviewing privacy and results, share only lightweight files:

   ```powershell
   git add datasets/manifests e2e_reports
   git diff --cached --stat
   git commit -m "Add E2E result for match_001"
   git push
   ```

On Mac, `git pull` provides the report without raw video. Private detailed logs and
recordings stay on Windows. Do not use `git add -f` on ignored outputs or recordings.
