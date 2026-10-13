# Current guarded-profile lifecycle component verification

## Problem and fixed targets

`GT-R1-ROUND-START` and `GT-R2-ROUND-START` need qualified current-code
timer/purchase-phase/UI evidence. Older timer/phase diagnostics have different
profile/code fingerprints following the contrast-guard implementation. Do not
copy those fingerprints or counts into a release sidecar without current
verification. No production thresholds, GT, assertion semantics or sampler
changed in this work.

## Current static verification

Reprocess the original 23 phase cases, 32 manually reviewed native timer cases
and 8 native alternate-field timer controls using the actual guarded profile
and shared reader/signal code. Preserve original labels, selections and splits.
Exclude the already identified phase control that conflicts with timer training;
do not change the original diagnostic or silently relabel it.

| Same source metric | Previous | Current | Delta |
| --- | ---: | ---: | ---: |
| Phase training correct | 3 | 3 | 0 |
| Phase holdout correct | 8 | 8 | 0 |
| Phase negative rejections | 12 | 12 | 0 |
| Timer holdout correct | 25 | 25 | 0 |
| Timer holdout unknown | 7 | 7 | 0 |
| Timer holdout wrong | 0 | 0 | 0 |
| Native timer type-control false positives | 0 | 0 | 0 |

Static recognition processes 63 inputs in 24.306 seconds. The older phase/timer
runtime excluded the 8 type controls, so it is not a comparable combined run.
The type controls exercise actual alternate fields with the configured reader
wrapper; they do not qualify absence at the genuine timer location or geometry.

Independently reverify all 76 historical training parent pixel hashes and the
10 unchanged digit reference hashes. Keep NCC 0.90 and class margin 0.04. This
is a source/asset audit, not new current predictions on every training image.
Partial timer/phase pixel splits remain disjoint. The audit takes 8.292 seconds.

## Source-labelled continuous UI verification

Process all 162 existing native images from five separate continuous windows
through the current guarded-profile `observe_native_system_frames` API. Each
window gets a fresh tracker and geometry-only source prefix; windows are never
spliced into one source epoch. Preserve source cadence, source/image hashes,
unedited-input assurance and all terminal input/profile/code/source checks.

Original manual source labels are compared to the actual current observations:
133 correct timer displays, 29 unknown and 0 wrong. This includes the real
R1 `0:00 → 2:25 → 1:39` transition without deleting or repairing `2:25`.
All 25 literal purchase-phase matches are correct. The other 137 nonmatches
remain distinct from proven absence; 30 menu-obscured regions cannot attest
phase absence. Original observation and candidate comparisons also match.

| Continuous metric | Previous | Current | Delta |
| --- | ---: | ---: | ---: |
| Source frames | 162 | 162 | 0 |
| Timer correct | 133 | 133 | 0 |
| Timer unknown | 29 | 29 | 0 |
| Timer wrong | 0 | 0 | 0 |
| R1 start candidate time | 4.102669 | 4.102669 | 0 |
| R1 confirmation time | 4.202669 | 4.202669 | 0 |
| R2 start candidate time | 111.419336 | 111.419336 | 0 |
| R2 confirmation time | 111.486003 | 111.486003 | 0 |
| Candidates in three control windows | 0 | 0 | 0 |
| Formal events | 0 | 0 | 0 |
| Whole diagnostic runtime, seconds | 302.354 | 303.663 | +1.309 |

The observed runtime change is +0.43% in one comparable local replay, not an
E2E benchmark. These are previously reviewed source cases, not a new blind
cohort. Two separately initialized start candidates do not prove continuous
R1 → end → R2 lifecycle or duplicate suppression over the intervening source.

## Actual qualification gates

Write a current timer/phase-only partial bundle in ignored diagnostic outputs,
never runtime configuration. Test the actual production loader with the actual
source-specific unedited contract:

- The old profile/code bundle rejects as `Invalid or mismatched global lifecycle qualification`.
- The current incomplete bundle rejects as `Missing or unknown global lifecycle component`.

No qualification is installed or formal event emitted. The start route still
requires `ui_transition`; end additionally requires `score`, `round_result`
and `ui_end_transition`. Re-signing older reports does not supply those proofs.

The loader requires at least three distinct **source-image hashes** in each
component split and reviewed count consistency. It does not impose three videos
or three episodes. Review units must be explicit: correlated preparation,
boundary and corroborating images can support one temporal case, but must not
be reported as several independently detected events. The audit confirms all
five UI windows have no physical PTS intersection with the 76 timer training
parents. This clears that specific split concern; it does not itself qualify
the temporal predicate or turn exposed development into new blind holdout.

## Tests, conclusion and next work

No production code changed. Prior current-code regression remains 2740 passed,
6 skipped; Ruff and mypy PASS. Fresh shared-reader predictions, original source
labels, input/asset hashes, actual loader rejection and JSON/diff checks pass.
No redundant full regression or canonical full E2E was run. The last adopted
canonical result remains 23 PASS / 55 FAIL / 4 NE; no new assertion is claimed
PASS. Current Windows execution is unverified.

Next work is explicit physical support/context review for `ui_transition`
under this same current profile/code, with honest original split/exposure and
temporal scope. Retain the existing strict release gate until that proof is
complete. Then verify the existing lifecycle/package/trace path; do not create
another state machine or treat isolated start windows as whole-match continuity.

Machine-readable results and review provenance:
`e2e_reports/match_001/guarded_lifecycle_component_verification.json`.
Complete local rows and incomplete-bundle audit:
`outputs/recognition-investigation/guarded-start-components-20261013/` and
`outputs/recognition-investigation/guarded-ui-start-replay-20261013/`.
