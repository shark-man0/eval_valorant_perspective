# Qualified whole-source lifecycle provider

## Problem / Evidence

The shared processor previously accepted a validated in-memory native result,
without collecting that result from the source itself. The decoder now supports
source origin, verified EOF and an explicit aggregate PNG budget. Actual R1
continuity/UI qualification remains unavailable; this transport change does not
resolve that evidence blocker.

## Change / Contract

`HudVideoProcessor.process(native_lifecycle_options=NativeLifecycleOptions(...))`
opts into automatic collection. Existing calls retain their default behavior.
The option requires a positive integer PNG byte ceiling and supports `up` or
`none` lossless PNG prediction. It accepts no GT times, round IDs or expected
reader values. A supplied native result and automatic collection are mutually
exclusive. `process_frames` keeps its existing explicit-result interface.

Before decoding, collection reloads current code/profile qualification, requires
paired scene/UI components, and verifies the analyzer's scene source binding.
It requests one source-origin-to-EOF decoder context, then invokes the qualified
producer once over every decoded frame. Dimensions, cadence, timebase, epoch,
video hash and exact returned pixel/PTS coverage must agree. It verifies decoded
assets and scene binding again, exits the decoder's terminal source verification,
then revalidates/replays native events against current qualification and video.
Only a successful result enters the existing package/trace merger.

Decoder errors, budget overflow, cancellation at stage boundaries, missing
qualification, or partial/foreign results withhold output. There is no sampled
fallback, frame omission, chunk-state concatenation or invented boundary.
Cancellation is checked between stages, not an interruptible decoder guarantee.

`native_frame_decode` and `native_lifecycle` timing stages separate source
collection from recognition. The mandatory ceiling limits encoded PNG storage;
it does not guarantee whole-video completion, RAM limits or free disk capacity.
The existing decoder timeout remains applicable. CLI activation and incremental
processing are not supplied by this change.

## Target assertions

GT-R1-ROUND-START, GT-R1-ROUND-END, GT-R2-ROUND-START and their
count/ordering constraints remain the intended acceptance targets. This change
alone supplies no actual-image boundary acceptance.

## Tests

Synthetic contract fixtures exercise one origin-to-EOF epoch, required
qualification before decode, exact producer coverage/binding, cancellation,
mutually exclusive inputs, storage/terminal failure and no sampled fallback.
Their patched image reads and synthetic qualification are transport tests,
not real-image qualification. Final related checks: 34 tests PASS in 16.69 seconds,
Ruff PASS, mypy PASS across 116 source files, and `git diff --check` PASS.
The 82-assertion record hash remains unchanged. Existing native-event merge and processor tests
protect the supplied-result/default routes. Windows execution is unverified.

## Previous / Current / Delta

| Metric | Previous | Current | Delta |
| --- | --- | --- | --- |
| Automatic native source collection | absent | explicit processor option | added |
| Accepted real source/UI qualification | absent | absent | 0 |
| Canonical PASS / FAIL / NE | 23 / 55 / 4 baseline | unmeasured | unmeasured |

## Remaining blockers

Independent R1 foreground/source continuity and a positively qualified UI
absence reference remain missing. No full E2E candidate exists. Do not activate
this route using saved diagnostic proofs or synthetic qualification. Qualification
must bind the current production source; historical reports are not resigned.

## Shared runner opt-in

The shared dataset runner and native exporter now accept these paired options
for full source processing:

```bash
python3 scripts/e2e/run_dataset_case.py \
  --video-id match_001 --video /path/to/source.mp4 \
  --validation-pack /path/to/unchanged-validation-pack \
  --hud-layout /path/to/qualified-hud-layout.json \
  --mode full \
  --scene-reference-profile /path/to/qualified-scene-profile.json \
  --native-png-budget 12000000000
```

This is an interface example, **not a currently qualified candidate command**.
The illustrative 12GB ceiling is not measured capacity assurance; select a
ceiling below available disk space with metadata/log/free-space margin. The
qualification report remains the layout's existing `.global_qualification.json`
sidecar and must bind current production code/profile/assets.

Native mode is rejected for targeted/sampled isolated inputs, raw adaptation,
missing paired options and nonpositive budgets. Omission preserves legacy
commands. `AppSettings.scene_reference_profile_path` binds scene assets when
constructing the production analyzer. Dataset settings fingerprints include
scene profile/assets and the byte ceiling, and are checked at completion.
Producer qualification/assets receive their own pre-decode and terminal checks.
The raw runtime mode records origin-to-EOF scope, ceiling and PNG prediction.
Native decoding uses the configured/packaged FFmpeg executable through
`VideoService`, alongside configured ffprobe; no OS recognition branch exists.

CLI propagation/configuration tests are mocked orchestration evidence, not an
actual full-video acceptance result. Actual R1 qualification remains required;
therefore no new canonical full E2E was started for this integration.

Final shared-runner checks: 126 tests PASS, 1 Windows-host-only test skipped,
43.64 seconds. Ruff PASS; mypy PASS across 116 source files; diff check PASS.
The 82 assertion records retain their previous SHA256. Native decode tests use
small actual FFmpeg fixtures; runner forwarding tests mock orchestration.
Neither scope demonstrates real-image lifecycle qualification or full source
completion on the match video.
