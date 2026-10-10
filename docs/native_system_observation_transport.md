# Native system observation transport

## Problem

Round lifecycle needs continuous source PTS, rather than retimestamped sampled
observations. Player identity may be unknown, but the global route must never
release HP, weapon, ammunition, death, shot or other player-owned facts. The
explicit scene entrance previously lacked a matching production reader entrance.

## Evidence and root cause

The sampled analyzer read objects with a `path` through ordinary `imread`, which
did not enforce `NativeSourceFrame` encoded/pixel hash checks on each read. Its
output also included player facts and event production. Reusing that complete
output as global evidence would conflate observation, ownership and qualification.

Target assertions remain `GT-R1-ROUND-START`, `GT-R1-ROUND-END`,
`GT-R2-ROUND-START` and lifecycle count/ordering constraints. This transport alone
cannot make those assertions PASS.

## Change and contract

`RealHudAnalyzer.observe_native_system_frames(frames, native_step_ticks=...)`
is an explicit native entrance using the same configured geometry, classifier,
semantic phase and numeric readers as ordinary HUD analysis. The default sampler
and default event path are unchanged.

- One nonempty contiguous decoder epoch, video hash, timebase, dimensions and
  exact native cadence are required before analysis. Gaps or mixed epochs reject
  the whole window rather than continuing state across them.
- Every native read uses `read_image()` to verify encoded and decoded pixels.
  Input files and profile/code fingerprints are checked again before releasing
  buffered observations. A profile changed since analyzer construction requires
  reloading the analyzer, so cached readers are not labelled with a newer profile.
- Each row keeps actual source ticks, seconds, timebase, epoch, video/pixel hash
  and input fingerprint. Observation timestamp/index must match each input.
- Original accepted timer text and reader provenance are copied, never formatted
  from seconds. Timer, scores, phase and their measured confidence remain subject
  to existing acceptance/calibration policies.
- Primary state and state flags retain spectator/menu/remote/transition guards.
  World-view trust and player ownership are false in the global projection.
  HP, armor, weapon, ammo, abilities, killfeed, location and map values are absent
  or schema defaults. Owned confidence fields are excluded.
- Event building is disabled for this explicit measurement entrance. Its
  `system_evidence` is empty: these observations do not attest scene continuity,
  UI disappearance, qualification or a boundary. No caller-supplied supplemental
  signals are accepted by this API.

The scene-only qualified proof entrance is separate. A future paired producer
must bind independent scene/UI proofs to these exact native inputs before the
global lifecycle can release system-level events. The new source fingerprint
invalidates older code-bound qualifications; historical reports are not resigned.

## Tests

81 related tests passed in 33.52 seconds, covering native input, replay trace,
scene evidence, global lifecycle and source binding. The new suite covers
owned-fact exclusion in five states, preserved OCR display/provenance and phase
confidence, mixed epoch/video/timebase and cadence rejection, timestamp/index/
coverage mismatch, terminal asset/config mutation, loader verification, stale
profile rejection, and the actual analyzer entrance without event building.
Positive display/projection fixtures are synthetic, not real-image qualification.
Ruff passed; mypy passed for 114 source files.

## Real-image transport check

`e2e_reports/match_001/native_system_observation_transport.json` records four
previously exposed contiguous R1 native frames at ticks
63017, 63273, 63529 and 63785 (timebase 1/15360). Saved PNG hashes and pixel hashes
are checked against the existing decoder report. The existing
`round-global-timer-glyph-20261008` development profile is used without a new
reference, threshold adjustment, GT input or supplied geometry anchors.

All four output notes contain `calibration_required`; original timer values and
display remain unknown. This is a genuine early-window input blocker under this
configured profile, not proof that geometry alone causes any canonical FAIL.
The check releases zero proofs/events and creates no qualification. It is a
development transport check, not blind holdout or canonical E2E.

## Previous / Current / Delta

| Metric | Previous | Current | Delta |
| --- | ---: | ---: | ---: |
| Canonical PASS / FAIL / NE | 23 / 55 / 4 | unmeasured | unmeasured |
| Canonical round start / end | 0 / 0 | unmeasured | unmeasured |
| Canonical packages | 1 partial | unmeasured | unmeasured |
| Negative failures / discontinuity violations | 0 / 0 | unmeasured | unmeasured |
| Native transport check frames | no comparable run | 4 | unmeasured |
| Native transport check runtime | no comparable run | 3.545511 s | unmeasured |
| Native transport check accepted timer displays | no comparable run | 0 | unmeasured |
| Native transport check proofs / events | no comparable run | 0 / 0 | unmeasured |

## Conclusion and remaining blockers

The production entrance now preserves native input identity and separates global
observations from owned facts and authorization. It does not complete lifecycle
delivery or improve canonical counts. R1 foreground/source continuity remains
unqualified; phase disappearance has no independently qualified producer. The
tested early-window profile also lacks accepted geometry, so its global readers
release no facts. Do not bypass geometry or inject retained transforms from later
frames. Establish eligible current-image inputs and paired qualification before
native lifecycle/event/package/trace activation. No targeted/sampled/full E2E was
run for this transport-only change; no qualified boundary candidate exists.

Windows behavior remains unverified on hardware. Native PNG decoding, FFmpeg PTS,
path handling and profile loading require the same cross-platform checks; no
platform-specific recognition logic was added.


## Follow-up: preserve acquisition context

[Continuous native prefix validation](native_system_prefix_validation.md) resolves
this report's isolated-window geometry blocker without policy changes:256native
frames from the actual first source PTS acquire geometry once and retain it;
the same four images now have4accepted original displays. Independent scene/UI
qualification and event integration remain unavailable. The original four-frame
report remains historical and is not rewritten.
