# Native prefix validation for R1 global inputs

## Problem

The native system entrance initially returned four unknown timer displays around
R1 start with `calibration_required`. This could be a current-image geometry
problem or the consequence of starting analysis after the acquisition context.
The canonical 55 FAIL classification must not be changed without causal evidence.

## Evidence and competing hypotheses

The unchanged detector accepts only `top_match_bar` on all four exposed native
images. Timer NCC is 0.796730–0.849364, HP 0.606296–0.642275 and ability
0.438861–0.726619, below 0.90. There is no letterbox; rejection is
`insufficient_anchors`, not a measured geometry mismatch.

The accepted full baseline uses one fresh acquisition and retained geometry.
The development global profile uses the same anchor specifications. Therefore
test native input from source acquisition through R1, rather than reducing the
anchor count, changing masks/thresholds or injecting a later transform.

## Change and source contract

`scripts/diagnostics/validate_native_system_prefix.py` accepts explicit video,
source SHA256, layout, native cadence and bounded start/end arguments. It invokes
the production native decoder and native system analyzer. No Validation Pack,
expected display, round ID, GT window or supplied anchor geometry enters runtime.
Video integrity is checked through decoder context exit before report release.

An initial request starting at 0.02 seconds was correctly rejected: the first
source frame is later, so the decoder's probe cannot cover that request. FFprobe
identifies first video PTS 553 at timebase 1/15360. The completed run starts at
that actual source PTS, 0.03600260416666667 seconds, and ends at 4.3 seconds.
These are diagnostic CLI input bounds, not production boundary constants.
All 256 native frames are processed in one decoder-owned epoch with exact
256-tick cadence. No images or observations from distinct epochs are joined.

## Results

The run completes in 500.588115 seconds (about 8 minutes 21 seconds). Existing
geometry policy acquires once and retains on 255 later frames: effective geometry
is available for all 256. Player identity remains unknown for all frames; global
inputs are observed without releasing owned facts, scene/UI proofs or events.
There are 234 accepted original timer displays and 22 unknown displays. This
acceptance count does not establish accuracy for all 234 images.

The R1 source sequence is preserved as `0:00` through tick63017, `2:25` at
ticks63273/63529, and `1:39` from tick63785. Phase flags are present through
tick62761 and absent at tick63017. Absence of a phase flag is not positive proof
of phase disappearance or scene continuity.

The four images from the previous isolated entrance have identical pixel hashes
and now retain all four displays. Another 24 shared native images exactly match
the earlier source-reviewed display predictions and pixel hashes. This comparison
is after prediction, uses previously exposed development material and is not
independent holdout qualification. Earlier reference-geometry simulation is still
historical; this run uses actual production acquisition/retention without injected
geometry or projected primary state.

## Continuity decision and contract change

The input/calibration hypothesis is resolved: starting the native window after
acquisition caused its geometry rejection. Geometry thresholds, minimum support,
retention and identity policies need no change for this continuous prefix.
Keep native acquisition context within the same source epoch; do not borrow
geometry backward from a later frame or bridge independent decoder windows.

The foreground/UI continuity decision remains unqualified. Observing the real
timer transient and phase timing does not authorize a lifecycle boundary. Matching
backgrounds also do not prove that foreground animation is unedited. Preserve
fail-closed event behavior until independent scene/UI qualification is established.

## Tests

18 native system input tests pass in 0.83 seconds, including a new synthetic
prefix test: first-frame acquisition plus later insufficient anchors retains
geometry under the existing policy and preserves original timer text. It does
not represent real image qualification. Ruff passes for src/tests/scripts/e2e
and the new diagnostic runner. Production source is unchanged since the preceding
114-file mypy PASS; its fingerprint matches the completed native report.

## Previous / Current / Delta

| Metric | Previous | Current | Delta |
| --- | ---: | ---: | ---: |
| Same four source images: accepted displays | 0 | 4 | +4 |
| Same four source images: unknown displays | 4 | 0 | -4 |
| Same four source images: calibration required | 4 | 0 | -4 |
| Same four source images: proofs/events | 0 / 0 | 0 / 0 | 0 / 0 |
| Native run processed frames | 4 | 256 | +252; different context |
| Native run wall time | 3.545511 s | 500.588115 s | +497.042604 s; different context |
| Canonical PASS / FAIL / NE | 23 / 55 / 4 | unmeasured | unmeasured |
| Canonical negative failures / discontinuity violations | 0 / 0 | unmeasured | unmeasured |

The different-context wall time is not a speed regression claim. The shared-four
comparison measures input availability; it is not a canonical assertion gain.

## Artifacts and remaining blocker

- `e2e_reports/match_001/native_system_geometry_rejection.json`
- `e2e_reports/match_001/native_system_prefix_validation.json`
- `e2e_reports/match_001/native_system_prefix_comparison.json`

Production-native global inputs now reach R1 without reference-geometry injection.
Next qualify source/foreground continuity and positive UI transitions, then bind
native system events through lifecycle/package/trace. Do not prioritize R2/end
threshold tuning or infer a round merely because timer text is available.
No targeted/sampled/full canonical E2E was run: no qualified boundary candidate
exists. All 82 assertion records remain unchanged. Windows hardware remains
unverified, including decoder PTS/PNG behavior and profile loading.
