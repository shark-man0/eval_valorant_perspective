# Round lifecycle recording plan — 2026-10-09

## Dataset roles

- `match_001`: keep the existing video, manifest, Validation Pack and reports.
  **2026-10-16 clarification**: it was extracted from a longer recording using
  Outplayed, but the content **inside the selected clip is not edited**. The
  source interval is partial and does not include a complete match; neither
  cut boundaries nor unexpected frame changes may be promoted to game events.
  Preserve source-integrity checks, partial-round and negative-safety regression.
  Do not optimize OCR/thresholds to force missing boundaries. See
  `docs/match001_visual_review_100ms_20261016.md`.
- `match_002`: received on 2026-10-09; user confirms an unedited full match. Use it
  for main real-source lifecycle qualification only after independent dataset
  registration and validation preparation. Source intake is complete; matching
  Validation Pack and registered dataset manifest remain pending. No expected
  boundaries or lifecycle success claims have yet been generated.

Existing schemas, thresholds, assertions and negative safety contracts stay
unchanged. match_001 evaluator failures remain failures under its existing pack;
changing the task's acceptance scope does not rewrite evaluator outcomes.

## Source intake result

SHA-256: `55d909c2d6a5f38575d1cb6c249ddfa7e2a48b96535841317adcae704c6f63b6`.
Duration 2214.272 seconds (36:54.272), 1920x1080 at 60 FPS, H.264, three
48 kHz stereo AAC tracks, 3,461,781,210 bytes. Source hash was verified both
before and after the complete packet timestamp scan.

All 132,856 video packets have usable, nonduplicate presentation timestamps.
One final interval, 2214.233333 to 2214.266667, is about 33.334 ms instead of
16.667 ms. This is a descriptive timing observation, not evidence of editing.
Sparse visual inspection at 30, 1100 and 2200 seconds shows purchase phase,
a round-result screen and match victory respectively; this is not a full
boundary annotation or source-continuity qualification.

The user attestation and mechanical verification are separate. The intake CLI
accepts no GT, pack, labels, recognizer settings or expected timestamps. It writes
no registered manifest and runs no Analyzer/Evaluator. It preserves all audio
metadata and excludes source paths, tags, images and OCR from the report.
Local JSON and previews are under ignored `outputs/intake/match_002/`.

```bash
python -m scripts.diagnostics.intake_recording \
  --video /path/to/original.mp4 --video-id match_002 \
  --user-confirmed-unedited --output outputs/intake/match_002/new_intake.json
```

Outputs are exclusive-create; use a new output filename for a repeat intake.
The next dataset step is independent source-frame boundary/negative annotation,
then the matching pack and manifest registration, not reuse of match_001 GT.

## Safe work independent of annotation

Continue synthetic regressions for independently evidenced starts without a
previous end, source resets, unknown/low-confidence abstention, package/trace
association and opaque continuity tokens. A matching token permits pairing only
after existing start/end evidence gates; it is not independent boundary proof.
Conflicting tokens must split packages, and conflicting duplicate boundaries
or known/missing duplicate provenance must fail closed.

Real-source producer qualification, capture-specific OCR, calibration tuning,
full-match boundary counts and canonical match_002 E2E wait for independent
annotation/pack preparation. Synthetic
results do not prove detection in either recording.

## Capture and intake checklist

1. Record the full match continuously, ideally including pre-match preparation,
   all purchase/active/result transitions and post-match context. Do not use
   highlight export, pause recording, remove death/spectator segments or join
   multiple recordings. Preserve the original file and audio tracks.
2. Keep resolution, aspect ratio and HUD scale stable. Record map and capture
   settings independently of GT; provide these as explicit runtime settings.
   Recording artifacts still require source continuity checks, even when the
   file is described as unedited.
3. On receipt, hash the actual original bytes and probe metadata. Prepare a
   separate pack for this source using the existing pack schemas and validator.
   Its MANIFEST source_sha256 must match the actual video. Independently annotate
   observable boundaries and negative controls; unknown evidence stays unknown.
   Do not copy match_001 timestamps/assertions or manufacture missing evidence.
4. Keep expected states/timestamps, pack contents and GT out of production
   recognizers, templates, semantic prompts and calibration. Separate any
   development/training material from withheld qualification and negative
   controls; do not tune on holdout outcomes.
5. Register through the existing runner after the matching pack is ready.
   `datasets/manifest.schema.json` already binds source SHA, metadata, pack
   fingerprint and assertions hash. No new manifest format is needed. The
   runner refuses existing-manifest overwrite and source/pack mismatches.

## Windows commands after receipt and independent pack preparation

Run from the repository root. These commands prompt for actual local inputs;
they are not usable until the new video, matching pack and profile exist.

```powershell
$video = (Resolve-Path (Read-Host 'Unedited match_002 video path')).Path
$pack = (Resolve-Path (Read-Host 'Independent match_002 Validation Pack directory')).Path
$layout = (Resolve-Path (Read-Host 'Local HUD layout path')).Path
$mapId = Read-Host 'Explicit map ID from recording metadata (not GT)'
Get-FileHash -Algorithm SHA256 -LiteralPath $video

# First registration only: validates source/pack, writes the independent
# datasets/manifests/match_002.json, then runs full E2E.
.\run_e2e_windows.ps1 -Video $video -VideoId match_002 `
  -ValidationPack $pack -HudLayout $layout -ManualMapId $mapId -Register

# Subsequent runs: retain and verify the registered manifest.
.\run_e2e_windows.ps1 -Video $video -VideoId match_002 `
  -ValidationPack $pack -HudLayout $layout -ManualMapId $mapId
```

Registration is not proof of successful analysis. Preserve native PTS, boundary
source segments, incomplete packages, trace association and canonical evaluator
outputs. Compare boundary precision/recall and negative safety within the same
source/pack/settings; do not compare raw counts between different recordings as
an improvement claim. Share only sanitized reports and the manifest, never raw
videos, images, templates, OCR payloads or local profile assets.

See WINDOWS_E2E.md for tool/environment checks, output locations and recovery.

## Current verification

Mac unit/integration regression: 141 tests passed (global lifecycle, round
boundaries, existing lifecycle and E2E dataset runner). Ruff passed; mypy passed
for 102 source files; diff check passed. No recognizer, threshold, production
config, existing manifest or Validation Pack changed. Windows execution and
match_002 real-source behavior have not been verified.

After source receipt, intake plus global lifecycle/boundary/dataset runner
regressions: 95 tests passed. Ruff passed for src/tests/diagnostics/e2e scripts;
mypy passed for 102 source files. Source-only real-file probing is verified;
no full Analyzer/Evaluator run or real lifecycle improvement is claimed.
