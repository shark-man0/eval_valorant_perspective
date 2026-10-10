# R1 native UI and foreground change localization

## Problem

R1's abnormal clock sequence cannot be treated as a timer-only UI transition
merely because several background crops match. The phase matcher proves text
presence only; missing glyph contrast does not qualify disappearance. Determine
where independent native image changes occur before installing a scene/UI proof
producer for `GT-R1-ROUND-START` and its lifecycle/package dependencies.

HEAD remains `e9ecaf8f2f0f0dfa1f9433d40a598ec8909e9ce3`. This checkpoint changes
diagnostics and documentation only.

## Evidence

The audit uses the 30 previously exposed native R1 images, not new holdout. Each
PNG and decoded native pixel hash is checked against the archived source report;
actual integer ticks increase by 256 in timebase 1/15360. Source profile/assets,
report, measurement code and PNG hashes are checked again at completion. No
Validation Pack or expected timer/score/boundary value is loaded.

Explicit native pixel bounds are purchase panel `[738,135,1183,281]` and excluded
timer `[860,20,1060,90]`. The six previously reviewed source-domain boxes supply
separate background measurements. Every background box excludes both timer and
panel. Measurements include unwarped background NCC, full-image NCC outside the
panel/timer, change-component positions and phase crop variance. No camera model
is refitted and no metric creates a confidence or acceptance decision.

## Competing hypotheses

1. Purchase-panel removal and a normal view-model animation transition within
   the same recording scene.
2. Purchase-panel removal followed by a content jump that preserves the visible
   background but changes the foreground temporal state.
3. A camera scene cut. Background evidence does not establish this hypothesis.

The stronger statement "only the timer changes" is unsupported: the native
source visibly changes the hand/knife presentation at the first transient frame.
No player ownership, weapon-action event or physical motion fact is inferred.

## Independent image evidence

All numbers below are computed from actual native pixels. The displayed UI
descriptions come from the existing exposed source review; those clock labels
are not inputs to the independent image calculations.

| Current actual PTS | Separately observed UI | Minimum NCC across six backgrounds | NCC outside panel/timer |
| --- | --- | ---: | ---: |
| 4.102669 | Panel disappears; prior clock persists | 0.992527 | 0.964486 |
| 4.119336 | First transient display | 0.995074 | 0.345489 |
| 4.136003 | Second transient display | 0.921992 | 0.888551 |
| 4.152669 | First subsequent active display | 0.942158 | 0.891113 |
| 4.169336 | Subsequent active display persists | 0.937822 | 0.908690 |

The descriptive change bin is max-channel absolute difference >=8, **not** a
recognition or cut threshold. At panel disappearance, 64,970 panel pixels change;
the largest connected component is `[736,128,448,156]` with 66,002 pixels, matching
the visible panel's location. Changes outside panel/timer also occur, including
the right-side foreground.

At the first transient frame, zero panel pixels enter that change bin while
389,399 pixels outside panel/timer do. The two largest components are
`[850,562,1070,518]` (315,717 pixels) and `[30,806,580,274]` (70,592 pixels).
Original native images 12–15 were inspected after measurement. These large lower
screen changes include the hand/knife presentation; they are not a replacement
of the reviewed wall background. This explains why a full-image score and
background-only scores disagree. Neither score should be used alone as a cut
classifier.

The whole former panel has grayscale std about1.2 after disappearance. Its NCC
with the preceding panel is -0.030002; adjacent later blank-background crops have
NCC about0.977–0.998. Matching blank/low-texture content does not prove a semantic
absence class. The existing glyph masks have still lower contrast, as measured
in [the phase rejection evidence](r1_phase_rejection_evidence.md).

## Continuity decision

The measured background appearance remains compatible with the same camera
scene. A timer-only transition is not established, and foreground animation
continuity versus a scene-preserving content jump remains unresolved. Maintain
fail-closed runtime qualification and discontinuity behavior. Do not declare
the foreground change a cut solely from low whole-image NCC; do not declare
uninterrupted content solely from high background NCC. Every observed clock
display must remain in any eventual temporal evidence chain.

## Contract change

None. No phase-disappearance proof, scene proof, new boundary, ownership fact,
qualification, reference candidate or production threshold is created. The
diagnostic explicitly reports authorization false. The next verification should
compare native foreground correspondence and normal animation transitions in
the current recording, independently of timer/phase values, before releasing the
paired UI path. Do not prioritize R2 or result-banner threshold changes first.

## Tests

Six unit tests and Ruff pass. Controls cover timer exclusion, blank phase NCC
unavailability, random background changes, invalid/overlapping bounds and a large
foreground change while every background remains an exact match. Authorization
stays false in every case. Production code is unchanged, so the preceding
112-file mypy and 178-related-test production results remain historical evidence;
they are not claimed newly rerun here. No full/targeted/sampled canonical E2E is
justified by these descriptive measurements. Windows execution is unverified.

## Previous / Current / Delta

| Metric | Previous | Current | Delta |
| --- | ---: | ---: | ---: |
| Saved R1 source images examined | 30 | 30 | 0 |
| Whole native non-UI change localization | not recorded in this form | 29 adjacent pairs | new diagnostics |
| Real phase/scene qualification created | 0 | 0 | 0 |
| Canonical PASS / FAIL / NE | 23 / 55 / 4 | unmeasured | unmeasured |

No new assertion PASS or negative/discontinuity result is claimed. All 82 stored
assertion entries remain unchanged. Runtime was not instrumented in this saved
image localization diagnostic; it is not a tiered E2E runtime comparison.

## Remaining blocker

The native producer entrance exists, but independent current phase-absence
qualification and foreground temporal interpretation remain missing. Background
correspondence alone cannot authorize treating the abnormal clock sequence as a
pure UI transient. Resolve this concrete ambiguity with same-video animation
controls and native source provenance; do not copy diagnostic scores into
`background_checked`/`phase_disappearance` proof fields.

Machine-readable evidence:
[native_ui_localization.json](../e2e_reports/match_001/native_ui_localization.json).
