# Current-code lifecycle component revalidation

## Problem

The completed-end history correction changed the production recognizer fingerprint.
Earlier qualification bundles and qualified native/application results therefore
remain historical. Updating their fingerprint without new recognition would
reuse stale evidence.

## Evidence and change

Replay the original fixed, source-reviewed rasters using current production
readers and `observe_native_system_frames`. Preserve training/holdout/negative
splits, original source labels, PTS, pixel hashes and previous exposure. Verify
76 timer-training parents and 10 unchanged glyph assets again. Source-video,
input, profile and recognizer hashes are checked at completion. No thresholds,
GT, validation assertions, ownership or full sampler change.

Current recognizer fingerprint:
`fd8b8ff3da3c1c9775604141f61062d39656f59e492610ed482e8530db691817`.

## Tests and Previous / Current / Delta

| Fixed-source measurement | Previous | Current | Delta |
| --- | ---: | ---: | ---: |
| Timer correct / unknown / wrong | 25 / 7 / 0 | 25 / 7 / 0 | 0 / 0 / 0 |
| Score field correct / unknown / wrong | 36 / 18 / 0 | 36 / 18 / 0 | 0 / 0 / 0 |
| Result correct / unknown / wrong | 3 / 8 / 0 | 3 / 8 / 0 | 0 / 0 / 0 |
| Start patterns in two reviewed windows | 2 | 2 | 0 |
| End patterns in reviewed end window | 1 | 1 | 0 |
| Start patterns in active/menu/spectator controls | 0 | 0 | 0 |
| End patterns in menu/active controls | 0 | 0 | 0 |
| Formal source events released by this verification | 0 | 0 | 0 |

Static phase: 3 training matches, 8 holdout matches, 12 negative rejections.
Eight timer type controls, 54 score negative-field calls and three natural
result negatives produce no false accepts. These bounded controls do not
establish full-video negative assertion results.

Fresh continuous producer outputs preserve the following distinct times:

| Pattern | Boundary time | Confirmation time |
| --- | ---: | ---: |
| R1 start | 4.102669 | 4.202669 |
| R1 end | 74.486003 | 75.369336 |
| R2 start | 111.419336 | 111.486003 |

R1's observed `0:00 → 2:25 → 1:39` sequence remains in provenance; no display
is discarded. End timing remains the first observed score change, with later
clock/score/result corroboration. Do not backdate it to match GT. The strict
R1-end window ends at 74.483 seconds, so this candidate remains outside that
window by approximately 0.003003 seconds. No new strict PASS is claimed.

Elapsed times: static phase/timer 24.120 seconds; score 8.932 seconds; result
2.948 seconds. Continuous start/control replay: 162 frames, 303.024 seconds.
Continuous end: 108 frames, 249.094 seconds including source checks, with
233.863 seconds in the producer. End controls: 99 frames, 182.318 seconds.
These are fixed diagnostics, not targeted/sampled/full E2E runtimes. Replayed
windows remain separate source contexts and are never spliced into a match.

## Qualification admission and remaining blocker

Build new offline support bundles from the fresh outputs and source labels.
The actual unchanged loader admits timer, purchase_phase, ui_transition,
score, round_result and ui_end_transition. Cross-component physical and pixel
splits remain disjoint. The end prefix has 71 frames, six source-correct
corroborating support images and one known end episode; its two negative
windows contain 99 images. Six supports are not six independent ends.

This is an admission audit, not final qualification, new blind data or default
runtime release. Independent temporal generalization and the complete
source-owned active-start→end→preparation path remain unverified. Previous
qualified native/application R1-start reports are still historical until
their real entrance is exercised under current code. Do not reuse those old
recognition outputs.

No full E2E or new full regression was run here. The latest correction has
108 related unit tests PASS, Ruff PASS and mypy PASS; earlier full-suite
2740 PASS / 6 SKIP predates that correction. Adopted canonical status stays
23 PASS / 55 FAIL / 4 NE. Windows remains unverified for the dirty worktree.

Next: validate the real qualified native entrance on continuous source,
preserving the observed duplicate-frame breaks before R2 preparation. Do not
promote raw UI diagnostic measurements into runtime proofs or assume that
loader admission proves full lifecycle/package coverage.

Machine-readable results: `e2e_reports/match_001/current_code_lifecycle_revalidation.json`.
Local replay outputs and admission audit:
`outputs/recognition-investigation/current-code-components-20261013/`.
