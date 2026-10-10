# Verified native source entrance

## Problem

The sampled final HUD observations do not contain all native R1 transition
frames. A proof for a native preceding frame cannot be transferred to a sampled
preceding frame by changing its PTS or pixel identity. The actual source decoder
must deliver pixels and ticks to the common scene episode through its own path.

## Evidence

Starting HEAD: `e9ecaf8f2f0f0dfa1f9433d40a598ec8909e9ce3`, main.
[The prior audit](scene_source_binding.md) measured 2,253/4,633 sampled observation
pairs beyond one native step and omission of the R1 phase-disappearance/transient
frames. These sampling gaps do not imply a content cut.

Target assertions remain `GT-R1-ROUND-START`, `GT-R1-ROUND-END`,
`GT-R2-ROUND-START` and their boundary count/ordering dependencies. The maximum
failure cluster remains round-package scope; none is marked resolved here.

## Root cause and hypothesis

The common scene engine could consume saved frames, but the production video
service and analyzer had no native source entrance. An explicitly bounded native
decoder can preserve every source PTS and its full decoded pixel identity while
leaving existing HUD sampling untouched. This is necessary for subsequent native
system lifecycle delivery; it is insufficient to qualify scene/world/UI evidence.

## Change

`VideoService.native_window()` now provides a blocking context for explicit
**interior** source windows. Before delivering frames it:

- verifies the caller-provided source video SHA256;
- probes the actual stream timebase/geometry and all native source ticks in the
  interval, requiring probe coverage before and after its bounds;
- decodes with one FFmpeg worker, original timestamps, passthrough cadence and
  lossless PNGs, without resizing or FPS conversion;
- matches all decoded `showinfo` integer ticks and frame counts to the probe;
- verifies the source SHA256 again and records encoded/decoded pixel hashes.

The decode is not capped by the probed frame count. A temporal trim after the
explicit interval bounds decoding while preserving all frames inside it. A
synthetic negative test removes the last interior tick from the probe; the
independent decoder still emits that frame and rejects the mismatch before
delivery. A probe-derived frame-count cap could incorrectly make both truncated
prefixes agree, so that cap is absent from this production entrance.

`NativeSourceFrame` retains actual integer ticks, exact rational timebase,
fresh decoder-owned epoch, video hash and native dimensions. `read_image()`
rejects changed encoded bytes or decoded pixels. Frames are not assigned
timestamps from frame index or FPS. The temporary files are cleaned on normal
completion or error, and source integrity is rechecked when consumption exits.
The command blocks without a process/log polling loop. This implementation is
for bounded verification windows; it does not yet implement a bounded-memory,
whole-video native streaming route or automatically decode the full recording.

`RealHudAnalyzer.inspect_native_source_window()` forwards these verified source
images/ticks to the existing common `ObservedSceneEpisode`, with its unchanged
acquisition, no-rejoin and native-gap rules. Mixed source hashes, timebases or
epochs are rejected before an episode is created. The source profile/assets are
checked before and after measurement. Returned rows include source provenance
and descriptive scene measurements only. They do not release player facts,
system events or trusted scene/UI proof tokens.

The global recognizer fingerprint now includes native decoder/service code as
well as all shared HUD modules. A decoder change invalidates old qualification,
just as changing source reference assets already does. No qualification schema,
recognition threshold or acceptance condition was relaxed.

## Tests

178 related unit/integration tests pass in 60.92 seconds; Ruff passes for
`src tests scripts/e2e`, and mypy passes for 112 source files. Coverage includes
real FFmpeg decoding of a source with nonzero PTS origin and varying frame
intervals, exact native tick preservation, temporary cleanup, new epoch per
decode, mutated source/PNG rejection, invalid decoder logs, code-fingerprint
invalidation, mixed-epoch withholding, lifecycle jitter/discontinuity and existing
HUD video processor behavior.

The actual target video was decoded once for the explicit development window
3.9–4.39 seconds. This is the already-exposed R1 material, **not holdout or
qualification**. All 30 ticks and full native pixel hashes match the archived
30-frame source diagnostic. All scene measurement dictionaries match the prior
common-only replay exactly, excluding the newly owned decoder epoch. Production
epoch fields were not rewritten for comparison. The source, selected profile,
reference assets and recognition code were checked at completion; temporary
native assets were removed.

See [the machine-readable verification](../e2e_reports/match_001/native_source_entrance_verification.json).

## Previous / Current / Delta

| Metric | Previous | Current | Delta |
| --- | ---: | ---: | ---: |
| Exposed R1 native frames measured | 30 | 30 | 0 |
| Descriptive scene links | 22 | 22 | 0 |
| Real source/world/UI qualification created | 0 | 0 | 0 |
| Installed qualified scene/UI producer | 0 | 0 | 0 |
| Canonical PASS / FAIL / NE | 23 / 55 / 4 | unmeasured | unmeasured |

The new decode-and-measure verification took 70.662816 seconds. The preceding
saved-image-only replay took 48.918016 seconds; these scopes differ because the
new route also probes, decodes and checks source integrity. This is not a speed
regression comparison or a recognition gain. No standard targeted/sampled/full
E2E was run because independently qualified adoption evidence is still absent.
Canonical negative failures/discontinuity violations remain the archived 0/0;
they have not been remeasured in a new canonical run.

## Conclusion and remaining blockers

Actual decoder-owned native input now reaches the common scene episode through
the production video service and analyzer APIs without diagnostic imports. It
does not yet reach global lifecycle decisions, native package boundaries or
canonical evaluation. Independent source/world continuity and current-frame phase
absence qualification are still missing; appearance-only correspondence cannot
substitute for them. The next implementation must connect qualified global
current-frame readers/proofs to a native system lifecycle stream and preserve
native candidate timestamps when merging its events into the sampled package
pipeline. Player-owned evidence must retain its existing identity requirements.

No GT, Validation Pack, assertion, full sampler, geometry policy or ownership
policy changed. No Git commit/push was performed. Windows execution remains
unverified, including FFmpeg seek/PTS behavior, OpenCV pixels and temporary-file
lifetime; all runtime logic remains shared Python with portable relative assets.
