# End-transition source units and completed-end history correction

## Problem and fixed target

`GT-R1-ROUND-END`, end-count constraints and R1→R2 association need temporal
evidence, not another early-caption tuning loop. Review the existing correct
clock/score/late-result path and inspect actual lifecycle history handling.
No GT time, expected score or round ID enters the production detector.

## Pre-change source/admission audit

The known end pattern's 71-frame prefix ends at its own confirmation time,
75.369336. This entire prefix is disjoint from every component's training
pixel hashes and from the physical timer/phase/result/UI-start training PTS.
The result-training parents begin after this confirmation; later frames are
not required to complete the prefix decision.

Six independently source-transcribed support images identify roles:
clock-before/reset, score-update/stability, result-first/confirmation. Their
actual values/measurements agree with the complete source review. These are
six physical supports for **one known temporal end episode**, not six end
events. Training context contains the existing 14 post-confirmation result
parents; negative context contains 99 native images in two complete reviewed
menu/active windows. Cross-split physical/pixel overlaps are absent.

The unchanged production loader, before the code correction below, accepts
the admission-audit candidate's six components. This establishes schema/count/
source partition admission only. It does not prove independent temporal
generalization, create new blind data, install a default bundle or release a
formal source end. Historical development exposure and one-case scope remain
explicit. Candidate boundary 74.486003 and confirmation 75.369336 stay distinct;
no backdating to the manual early caption or GT occurs.

## Immutable whole-source metadata evidence

Verify the archived 10259-row source record against its recorded artifact hash.
Use only immutable source PTS/pixel identifiers, deliberately excluding its
old recognition outputs. Current source windows independently match 466
archival PTS/pixel identities; this is not a new decode of all 10259 frames.

There are no archived native cadence gaps. Repeated decoded rasters occur at
81.786003 and 81.836003 seconds, after the known end and before R2 preparation.
Retain existing duplicate/source-break guards; no source continuity guarantee
or old recognition is inferred from those two image repeats. Complete source
collection must handle both breaks and preserve their unknown context.

## Concrete lifecycle bug

`UneditedRoundLifecycle.advance` previously cleared `ended` whenever current
UI observation reset the start tracker to `unobserved`. A post-result banner,
combat report, menu or unavailable phase scan therefore erased a previously
completed end even though source identity/cadence remained continuous. Later
valid preparation appeared as `pre_round`, losing `next_round_preparation`.

Correct the history rule: uncertain current UI clears preparation evidence,
not the known completed end in the same source segment. Actual source breaks
and invalid source binding still clear the end history. This flag does not
enable an active round, improve player ownership or bypass any end predicate.
Existing start/end event gates, timestamps and duplicate suppression remain
unchanged; only the segment-history/state-label behavior changes.

## Tests and Previous / Current / Delta

Add four post-end uncertainty cases and four source-break cases. Verify a
completed end survives result/report/menu/unavailable-scan uncertainty,
progresses to next preparation, and emits the same start/end/start sequence
without a second inferred end. Verify epoch changes, PTS gaps, repeated pixels
and explicit content jumps erase history and do not inherit preparation across
segments.

| Regression metric | Before | After | Delta |
| --- | ---: | ---: | ---: |
| New history tests PASS | 4 | 8 | +4 |
| New history tests FAIL | 4 | 0 | -4 |

Related UI-end/native-assured tests: 108 PASS in 77.24 seconds. Ruff PASS;
mypy PASS on 129 source files. The earlier bare `pytest` entry point failed
collection because the repository `tests` package was absent from that launch
path; `python3 -m pytest` runs the intended tests. Preserve the collection log;
no implementation/test criterion changed to fix that invocation issue.

No full regression or E2E is run after this correction: fresh candidate
qualification/source/temporal gates are pending. Earlier 2740-pass full-suite
evidence predates this edit and is not a current full-regression claim.

## Qualification invalidation and remaining work

The code fingerprint changes from
`7bbb45ea27708c547a9ceb7c79b6f52e99f765675735ad0e247fd0528021cd2c`
to
`fd8b8ff3da3c1c9775604141f61062d39656f59e492610ed482e8530db691817`.
Actual loader rejects the old pre-change candidate as
`Invalid or mismatched global lifecycle qualification`. Preserve that guard;
do not re-sign old counts or treat pre-change admission as current permission.

Next work is fresh current-code component/source verification, followed by
source-owned continuous start→end→preparation collection. Never splice the
isolated windows into a fictitious continuous epoch or promote raw diagnostic
measurements into runtime proofs. Native input guarantees, NCC/identity/OCR/
ownership/geometry/negative/source-break policies remain unchanged.

No new source-qualified end, no current canonical full run or new adopted PASS
is claimed. Last adopted status remains 23 PASS / 55 FAIL / 4 NE. Previous
targeted R1-start PASS evidence is historical under the prior code fingerprint.
Windows execution and full-video negative/discontinuity outcomes remain
unverified. The goal remains active.

Changed production file: `hud/unedited_lifecycle.py`; tests:
`tests/unit/test_unedited_ui_end.py`.
Machine-readable admission/history/source evidence:
`e2e_reports/match_001/ui_end_component_review.json`.
Local preserved logs/audits:
`outputs/recognition-investigation/ui-end-component-review-20261013/`.
