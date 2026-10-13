# Current guarded result component: caption evidence, not end-time qualification

## Problem and targets

`GT-R1-ROUND-END` and `event_count_constraints-002` require trustworthy result
semantics and a correctly associated timestamp. After current timer, phase,
UI-start and score review, the result component still needed explicit source
parents and cross-component split verification. Complete that review without
changing the reference, threshold, training/holdout or expected assertions.

## Actual source and shared matcher verification

Load the unchanged opt-in guarded profile and shared semantic matcher under
the same current profile/code fingerprints as the prior production replay.
Review all 14 original training parents: three exact native source images and
11 archival JPEG images originally unassigned to holdout. Preserve their encoded
and decoded-pixel hashes. Native PTS comes from recorded decoder metadata;
historical JPEG review timestamps map uniquely to the known native tick grid.
Those mappings are not a fresh native decode.

Use actual BGR source crops at the original fixed caption bounds. Re-evaluate
the original 11 source-reviewed holdout and three natural non-result controls.
Scores exactly match the prior unchanged-code production replay. No pose,
threshold, mask, glyph selection, reference or semantic criterion is fitted.

| Same held source input metric | Previous | Current | Delta |
| --- | ---: | ---: | ---: |
| Correct result matches | 3 | 3 | 0 |
| Unknown result reads | 8 | 8 | 0 |
| Wrong result reads | 0 | 0 | 0 |
| Natural negative false positives | 0 | 0 | 0 |

All 28 training/held/control parents are checked in 3.019 seconds. Terminal
input, code and profile hashes verify. Original exposure and the single-source
result episode remain explicit; this is not new blind temporal qualification.

The configured grayscale training assets have six combined-predicate supports.
The actual full BGR source path accepts seven training parents after BGR-to-gray
conversion. Preserve both distinct measurements: direct JPEG grayscale decode
and BGR conversion can differ slightly. This is not a 6→7 accuracy gain, a
threshold adjustment, a relabelled holdout or a replacement of the constructor's
six-support measurement.

The earlier synthetic added-stroke rejection remains separate. It is not one
of the three natural negative source images and supplies no additional natural
qualification support.

## Candidate component admission

Create a local candidate `round_result` component with 14 training, 11 holdout
and three natural negative parent pixel hashes. Its reviewed counts are
3 correct / 8 unknown / 0 wrong, zero negative false positives. Review provenance
records encoding differences, original exposure and the restricted caption
scope. It does not attest score/timer values, geometry, continuity or an end time.

Actual source-assured qualification loader admits the candidate's five
components: `timer`, `purchase_phase`, `ui_transition`, `score`, `round_result`.
Cross-component pixel split checks pass. A separate physical-PTS audit over
all five components finds 102 training / 84 holdout / 137 negative parents with
zero pairwise cross-split intersections. JPEG/PNG encoding differences therefore
do not hide physical source overlap.

The bundle remains in ignored local outputs. It is not installed by default,
used to promote owned facts, or presented as full lifecycle adoption.
`ui_end_transition` remains absent. Existing legacy adjacent-score/current-result
end behavior is unchanged; this audit does not replace that path or claim its
behavior across the full video has passed.

## Temporal decision and remaining blocker

Caption recognition is a result observation, not the boundary timestamp.
The current continuous end diagnostic observes clock change at 74.452669,
score change at 74.486003 and result support at 75.319336, confirmed 75.369336.
Do not move the observed score-change time to the caption time, round it into
the strict acceptance window, or use GT to decide which timestamp is an end.

There is one known end episode in this source. Its training and held caption
images are distinct physical examples, but do not become independent complete
temporal end events. Temporal-end qualification still needs explicitly reviewed
support/context units and honest independence/exposure. A caption component
meeting the loader's three-image gate is not proof of that temporal contract.

Next work is that end-transition review and the actual continuous lifecycle/
application path. Reuse existing end/rearm machinery and preserve negative,
source-discontinuity and ownership guards. Do not manufacture independent
events from overlapping or truncated versions of this one known episode.

## Tests and canonical status

No production code, GT, assertion or recognition policy changes. Fresh shared
matcher scores, source/asset hashes, physical split audit, actual component
loader admission and terminal verification pass. Prior current-code regression
remains 2740 passed / 6 skipped, Ruff PASS and mypy PASS; no redundant full
suite is run for this diagnostic/documentation work.

No formal event was emitted or canonical full E2E executed here. The adopted
baseline remains 23 PASS / 55 FAIL / 4 NE; new full Current/Delta are unavailable.
The previous local R1-start canonical PASS remains a separate targeted result.
Current Windows execution, full-video negative/discontinuity outcomes and
R1-to-R2 package association remain unverified.

Machine-readable evidence:
`e2e_reports/match_001/guarded_result_component_verification.json`.
Full local parent review, actual scores and candidate bundle:
`outputs/recognition-investigation/guarded-result-component-review-20261013/`.
