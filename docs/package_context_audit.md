# Strict and practical package context audit

## Problem and hypothesis

The pre-main-integration source run produces two real boundary-bearing packages,
but initial and inter-round observations remain outside their windows. Determine
whether context is lost, already retained by Practical Mode, or safely attributable
to an upcoming round. Target the package-scope cluster and initial/R2 buy-menu
snapshot coverage; do not change their predicates or manufacture membership.

## Evidence scope

At main `c11ec6d333957cccb270417bc95a8a57f433e6ad`, run the current public
RoundPackageBuilder on all 10259 immutable historical system observations and
three historical boundary events. Verify the input hash and current fingerprint
at completion. This is a **frozen upstream fixture replay for builder semantics**,
not current-code recognition, qualification or full E2E. Historical confirmed
events remain fixtures; their prior qualification is not re-signed or installed.

No video recognition, threshold, Validation Pack, GT or production code changes.
Use the two recorded source-break times: 81.786003 and 81.836003 seconds.

## Previous / Current / Delta: mode comparison on the same fixture

| Context metric | Strict | Practical | Delta |
| --- | ---: | ---: | ---: |
| Stored packages/fragments | 2 | 5 | +3 |
| Unassigned observed frames | 1966 | 0 | -1966 |
| Observations assigned to more than one window | 0 | 0 | 0 |
| Preserved formal boundary events | 3 | 3 | 0 |
| Newly generated boundary events | 0 | 0 | 0 |

This comparison changes only the explicit mode. It is not a before/after accuracy
claim. Strict leaves 19.16% of fixture observations unassigned:

- Initial context: 214 frames at 0.036003–3.586003 seconds.
- Inter-round context: 1752 frames at 81.786003–110.969336 seconds.

Unassigned states are 1387 unknown and 579 buy-menu frames. All 579 buy-menu
observations in this fixture fall outside Strict windows. Raw observations are
still present in the processing result; absence from a package is distinct from
deletion or absence of current-frame detection.

## Existing practical behavior

Reuse the existing `_retain_unassigned_observations` mechanism. Practical Mode
retains the context in three additional fragments, without source-cut overlap:

| Storage ordinal | Range | Observations | Boundary status |
| --- | --- | ---: | --- |
| 1 | 0.036003–3.602669 | 214 | start/end unknown |
| 2 | 3.602669–81.769336 | 4691 | historical fixture start/end confirmed |
| 3 | 81.786003–81.836003 | 3 | start/end unknown |
| 4 | 81.836003–110.986003 | 1749 | start/end unknown |
| 5 | 110.986003–171.019336 | 3602 | historical fixture start confirmed/end unknown |

All `observed_round_no` values remain null. Storage ordinals do not prove official
round numbers. Unknown fragments are incomplete, supply no formal start/end and
must not increase fact/AI confidence. The last endpoint is the source-duration
sentinel; it is not evidence of an R2 end. Unknown context is preserved rather
than forced across source breaks into the independently detected R2.

## Verification and conclusion

Public builder validates all observation/package schemas in both modes. Verify
each source observation belongs to at most one window, every observation is
retained in Practical Mode, and no window contains an interior source break.
All three boundary actor/time/type/confidence/attributes survive unchanged.
Runtime: 50.479 seconds, with zero decode/recognition work. No full E2E is run.

No production change is needed to retain these observations in Practical Mode.
This audit narrows the blocker to **safe round association and current-code
application/qualification integration**, rather than a missing retention engine.
The additional fragments are not three detected rounds and do not solve the
29 package-scope assertions. Strict behavior remains unchanged; no additional
adopted PASS is claimed (23 PASS / 55 FAIL / 4 NE).

Next: revalidate qualification under current code and inspect the real full
application merge. Evaluate source-local preparation independently of earlier
unknown/menu context. Do not use GT labels, nearby round times or package ordinals
to infer association.

Machine-readable report: `e2e_reports/match_001/package_context_audit.json`.
Local packages: `outputs/recognition-investigation/package-context-audit-20261013/`.
