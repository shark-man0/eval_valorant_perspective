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

Keep using the same `-HudLayout` and its adjacent `.templates.json` profile locally.
The runner automatically exports fixed anchor names, thresholds, mask presence, image
dimensions and SHA-256, accepted/rejected/unscored counts, finite confidence min/median/max,
missing-anchor co-occurrence and geometry success rates. No extra flag or image upload
is required. `hud_calibration.json` and `summary.hud_calibration` contain the same metrics.
Fresh geometry and retained valid geometry are counted separately from state evidence.
These are sampled-frame rates, not time-weighted accuracy. Missing diagnostics from old
outputs are marked unavailable, never reconstructed. See
[HUD_DIAGNOSTICS_REVIEW.md](HUD_DIAGNOSTICS_REVIEW.md) for interpretation and the baseline.

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
