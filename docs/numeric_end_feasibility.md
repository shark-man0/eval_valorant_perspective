# Numeric round-end feasibility

## Problem / target

`GT-R1-ROUND-END` remains blocked: the accepted late result reference appears
after the end window, and translation does not recover the occluded early word.
Investigate existing independent timer/score observations without changing OCR,
recovering the word, choosing an event timestamp from GT or releasing an event.

## Frozen diagnostic hypothesis

An abnormal accepted clock decrease must occur while prior scores are stable.
An adjacent one-point, one-side score increase must then stabilize. Subsequent
accepted coherent clock observations must span the existing 0.05-second support
minimum within one second of the clock change. Every intervening native frame
must satisfy source, cadence, epoch and context checks. Contradictory scores or
another abnormal clock change reject the pending pattern. Missing clock readings
remain missing and contribute no support; this hypothesis does not certify their
unobserved display values. It describes temporal correlation, not end semantics.

This separate diagnostic was defined before replaying its saved input reports.
It does not modify the earlier frozen banner-based diagnostic or production.
Its thresholds/time budget reuse the existing diagnostic contract. Synthetic
tests use values unrelated to the validation video's expected values.

## Evidence / competing hypotheses

The saved 108-native-frame R1 end report supplies one pattern:

- Accepted clock reset: tick 1143593, 74.452669 seconds, original `0:06`.
- Score change: tick 1144105, 74.486003 seconds, observed `[0,1] → [0,2]`.
- Score support reaches the duration minimum at tick 1144873.
- Clock corroboration reaches the duration minimum at tick 1149481,
  using accepted observations at 1143593, 1143849 and 1149481.

The sparse accepted clocks are not consecutive accepted OCR. All native input
frames remain present, but unknown clock frames must not be called stable timer
evidence. Existing timer source review covers accepted readings; this diagnostic
does not create a new independent score correctness review.

Alternatives remain: UI reset followed by a genuine score update; delayed UI
presentation of an earlier end; or unrelated/misrecognized numeric evidence.
The correlation alone cannot decide which observed instant is the semantic end.
No boundary timestamp, actor or round ID is generated or backdated.

## Controls / contract limits

R1 start, R2 start, menu entry and a fixed active interval each produce zero
numeric end patterns. They are already exposed same-video controls, not new
blind holdout. Raw R2 observations are paired with their saved native measurements
without reconstructing values from the system-filtered observation.

The historical end report lacks the later `phase_present` raw measurement on all
108 frames. Its valid scan/debounced context cannot prove parity with the current
raw-phase guard. The diagnostic counts missing markers explicitly and cannot
serve as current-producer qualification. The same limitation is reported for
older controls. Source assurance excludes intentional edits, not recording loss.

## Tests / Previous / Current / Delta

19 related diagnostic tests passed in 0.65 seconds; Ruff passed. Production source
is unchanged; the preceding mypy check passed on 121 source files. Tests cover
unknown clocks, score/clock contradictions, source breaks, phase/spectator veto
and missing native frames. They do not qualify the actual lifecycle.

The previous banner-based and current numeric patterns each find one conditional
R1 correlation, but use different predicates; their counts are not an accuracy
comparison. Released events: Previous 0 / Current 0 / Delta 0. Canonical baseline
23 PASS / 55 FAIL / 4 NE; Current/Delta unavailable. No canonical targeted,
sampled or full run was started and no negative regression claim is made.

Four-report offline replay took 0.054051 seconds, excluding image production;
Previous/Delta runtime is unavailable. This is not an E2E speed measurement.

Artifacts: `e2e_reports/match_001/numeric_end_feasibility.json` and
`numeric_end_r2_negative.json`. The exact initial replay program is preserved at
`outputs/recognition-investigation/numeric-end-feasibility/diagnostic-at-run.py`
with its recorded SHA; subsequent line wrapping changes no logic. Saved inputs
and original code/profile fingerprints are preserved, never re-signed as current
qualification.

## Remaining blocker / next action

Replay the current actual producer over the existing 108 continuous source frames
to obtain raw phase presence; keep source pixels and OCR observations intact.
Then independently review numeric evidence and semantic end timing before any
qualified production promotion. A numeric pattern cannot replace independent
temporal qualification or proof of an active round. Failure analysis remains
33 round-lifecycle/package-related FAIL; no assertion is marked resolved here.
## Current actual producer replay

The current actual analyzer has now reprocessed the unchanged 108-frame source
archive, with four origin frames solely for geometry context. Encoded/pixel hashes
and native PTS are identical to the earlier run. Terminal profile/code bindings
pass; all 108 observations are unchanged. Every frame now has raw phase presence
and confidence: zero positive phase matches. This removes the missing current
producer measurement limitation for this interval, not the qualification gate.

| Metric | Previous | Current | Delta |
| --- | ---: | ---: | ---: |
| Native interval frames | 108 | 108 | 0 |
| Accepted timer displays | 17 | 17 | 0 |
| Accepted score pairs | 47 | 47 | 0 |
| Valid phase scans | 108 | 108 | 0 |
| Result reference matches | 29 | 29 | 0 |
| Raw phase fields available | 0 | 108 | +108 |
| Released events | 0 | 0 | 0 |
| Producer runtime seconds | 297.784433 | 229.458303 | -68.326130 |

Runtime decreased 22.94%, but the old run freshly decoded the interval and this
one reused the source PNG archive. This is a workload difference, not proof of a
recognizer speedup. Both numeric and delayed-banner diagnostics retain one pattern.

A post-prediction contact-sheet review covers the source score crops on all108
frames. All114 accepted individual score fields agree with readable source values;
0 wrong,102 unknown. Unknown/obscured crops are not promoted to observations.
The enemy score changes visibly between source images17and18. This supports
correctness of this development example, not independent holdout or semantic
proof of a round-end timestamp. Existing timer review remains applicable because
source pixels and all observations are identical.

Artifacts: `r1_end_current_phase_inputs.json`,
`r1_end_current_phase_comparison.json`, `r1_end_current_score_review.json`, and
the source-bound `r1_end_current_phase_archive_manifest.json` under the report
directory. No production code, reference, threshold or assertion changed in
this replay. Prior19diagnostic tests/Ruff and121-file mypy results remain relevant;
no new test was needed for these source/report-only additions. Canonical
Current/Delta remains unavailable; no full E2E or new qualification was created.

The next blocker is independent temporal/end-time semantics and qualification,
not missing raw phase measurements on this R1 end interval. Source assurance
removes edit-proof requirements but does not resolve this remaining requirement.
