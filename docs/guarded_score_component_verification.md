# Current guarded-profile score component verification

## Problem, hypothesis and targets

R1 end requires independently reviewed current score inputs as well as result
and temporal qualification. `GT-R1-ROUND-END`, `GT-R1-SNAP-0415` and
`GT-R2-SNAP-11145` are downstream targets, not inputs to the recognizer or
source selection. Reuse the original source-only fixed holdout and type-control
cohort; do not create a new candidate or adjust acceptance to match GT.

## Frozen source and actual reader replay

Use the original six native source windows: three holdout and three spatial
negative windows, each with nine frames. Original labels were transcribed from
source before the old frozen score predictions. Preserve that provenance and
exposure; these are not new blind data. Verify all encoded/pixel hashes and
the original label-to-manifest hash binding.

Process 27 positive parents through the current ally/enemy outer-ROI wrappers
at the nominal layout. Process 27 negative parents through the original
44×45 score-sized fields and core readers. Do not apply the enclosing subregion
twice. Both paths use the current profile unchanged: NCC 0.90, margin 0.04,
Gaussian comparison and rowcontrast foreground preprocessing. No GT values,
acceptance times, round IDs, ownership or player identity enter the reader.

54 physical images produce 108 reader calls in 12.110 seconds. Terminal
input, profile and recognition-code hashes verify.

## Current / Previous / Delta

| Field-level metric, same holdout | Previous | Current | Delta |
| --- | ---: | ---: | ---: |
| Correct | 36 | 36 | 0 |
| Unknown | 18 | 18 | 0 |
| Wrong | 0 | 0 | 0 |
| Negative field false positives | 0 | 0 | 0 |

Direct per-input comparison finds 36 correct→correct and 18 unknown→unknown.
All wrong-increasing and other classification transitions are zero. The
original reference profile differs from the current profile; this is a fixed
source comparison, not evidence of a new accuracy gain or speed improvement.

The **joint score-pair** unit is a physical source frame: both ally and enemy
must be accepted and source-correct to count it correct. Current holdout is
9 correct / 18 unknown / 0 wrong across 27 parent images. Do not count the two
fields as independent images or put 36 correct into a 27-hash qualification
component. The nine correct pairs occur in one of the three source windows;
the other two windows retain nine unknown pairs each. All 27 negative parents
reject both fields, zero false-positive parents or fields.

## Training provenance and candidate admission

The current score and timer readers share the same ten digit asset paths.
Reverify the current 76-parent training/10-asset audit and its input hashes.
The provenance describes shared-font glyph training, not new score-location
training predictions. Actual score field holdout checks transfer without fitting.
Limited class/background coverage remains explicit.

Add a `score` component to the current local start-only candidate bundle:
76 training parent hashes, 27 holdout parent hashes, 27 negative parent hashes;
holdout counts 9 correct / 18 unknown / 0 wrong and zero negative false
positives. Review provenance explicitly records the pair unit, exposed source
cohort, original labels and restricted spatial-negative scope.

Actual source-assured qualification loader admits `timer`, `purchase_phase`,
`ui_transition`, `score`. Cross-component pixel splits pass its unchanged
checks. A separate physical-PTS audit of every start/timer/phase/score component
finds 88 training / 73 holdout / 134 negative parents, with zero pairwise
cross-split intersections. Sharing a parent inside the same split is permitted;
sharing it across splits is not.

This candidate bundle stays in ignored local outputs. No default installation,
score snapshot admission, player-owned fact or formal round end is enabled by
this audit. Qualification admission is distinct from adoption of the full
source/producer/temporal/package/trace pipeline.

## Tests and remaining blockers

No production code, template, threshold, GT or assertion changed. Fresh shared
reader predictions, exact source/label/asset hashes, physical split audit,
actual loader admission and terminal verification pass. Existing current-code
regression remains 2740 passed / 6 skipped, Ruff PASS and mypy PASS; no redundant
long suite is run for this diagnostic/documentation addition.

The negative fields test spatial type rejection, not natural score absence at
the nominal HUD location, accepted geometry, menu/spectator transitions or
temporal end detection. Unknown pair fields stay unknown and are not repaired
from neighboring scores. No canonical full E2E is run; last adopted status is
23 PASS / 55 FAIL / 4 NE, with Current/Delta unavailable for a new full run.
Windows runtime remains unverified.

Next work is current round-result and UI end-transition qualification, then
the actual continuous lifecycle/application path. Preserve the observed score
change timestamp rather than backdating it to fit the strict R1-end window.
Do not use score component admission alone as an end-event attestation.

Machine-readable evidence:
`e2e_reports/match_001/guarded_score_component_verification.json`.
Local actual predictions, split audit and candidate bundle:
`outputs/recognition-investigation/guarded-score-source-replay-20261013/`.
