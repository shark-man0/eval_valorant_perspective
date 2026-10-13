# Complete native UI source review keeps image and event units separate

## Problem and fixed targets

`GT-R1-ROUND-START` and `GT-R2-ROUND-START` need independently reviewed global
phase/timer/UI evidence. Previously only16transition images and30spectator
clock images were manually reviewed.133accepted timers were not133verified
correct source values. Complete the source review without deriving labels from
tracker output, deleting the real2:25display or inventing a new blind cohort.

## Evidence and source labels

Review all162native source images in the original five windows. Contact sheets
show integer-frame-index/time labels and actual timer/phase pixels, hide reader
predictions and retain every source frame. Save labels before the new comparison,
while explicitly acknowledging earlier predictions were already exposed.
Original-display labels come from each image, not inferred elapsed time,
Validation Pack values or neighbour-frame completion. All162terminal encoded
image hashes match the original native archive; decoded source pixels verify.

| Window | Source timer observations | Literal purchase text |
| --- | --- | --- |
| R1,36frames | 13×0:00,2×2:25,21×1:39 | present first12frames,then disappears |
| R2,36frames | 14×0:00,2×1:40,20×1:39 | present first13frames,then disappears |
| Active,30frames | 5×1:36,25×1:35 | not visible in source region |
| Menu,30frames | 24×0:26,6×0:25 | region obscured by purchase menu |
| Spectator,30frames | 23×0:51,7×0:50 | not visible in source region |

Menu occlusion is not positive evidence that game purchase phase ended. Literal
nonmatch and actual underlying phase absence remain different concepts. No
underlying phase or ownership is inferred from these cropped observations.

## Current stored producer comparison

Compare labels to current source-bound native measurements, preserving the
original display strings rather than regenerating them from numeric seconds.
No new recognition pass, code/profile change or threshold adjustment.

| Window | Correct timer | Unknown | Wrong |
| --- | ---: | ---: | ---: |
| R1 | 36 | 0 | 0 |
| R2 | 30 | 6 | 0 |
| Active | 26 | 4 | 0 |
| Menu | 30 | 0 | 0 |
| Spectator | 11 | 19 | 0 |
| Total | 133 | 29 | 0 |

Literal purchase-phase matches are correct25/25.137other source images have no
literal text match;30are menu-obscured. None become checked game-phase absence
by this audit. Source phase-disappearance times4.102669and111.419336match the
existing candidates exactly, with confirmations4.202669and111.486003. The3
control windows still produce0candidates. This comparison is source UI evidence,
not additional canonical Round boundary ground truth or formal-event acceptance.

## Previous / Current / Delta

| Same input metric | Previous | Current | Delta |
| --- | ---: | ---: | ---: |
| Source frames | 162 | 162 | 0 |
| Accepted timer | 133 | 133 | 0 |
| Unknown timer | 29 | 29 | 0 |
| Correct against this complete review | unmeasured | 133 | unavailable |
| Wrong against this complete review | unmeasured | 0 | unavailable |
| Distinct source transition cases | 2 | 2 | 0 |
| Control candidates | 0 | 0 | 0 |
| Formal events from this replay | 0 | 0 | 0 |

No confidence-only correctness claim remains for the accepted values in these
five windows. This is a correlated, narrow source population; it is not a
whole-video error rate. Stored-measurement comparison takes0.292seconds, excluding
contact-sheet generation/manual review/decode/recognition, so no pipeline speed
comparison is claimed.

## Original splits and qualification units

Retain the original R1training,R2holdout_reviewand3negative_reviewwindow labels.
The frozen original plan explicitly calls these known source windows development
replay rather than new blind episodes. Do not erase that exposure history.

There are162physical images and two distinct source UI transitions. Repeated or
truncated replay of one transition does not create independent events. Minimum
three distinct component image hashes is likewise not a three-video/three-round
requirement. Frame-level component support, correlated temporal corroboration,
independent event cases and new blind holdout must be reported separately.
The full temporal context and geometry-only shared reference remain explicit.

## Tests and remaining blocker

No shared code or tests changed; preceding303relatedtests,Ruff/mypyremain
applicable. Original image/hash, source-label and current measurement alignment
checks pass. Qualification is not installed and formal events are not enabled.
No unnecessary full regression/E2E. All82canonical entries retain historical
23PASS/55FAIL/4NE; Current full/Delta unavailable. Windows runtime unverified.

The component evidence now includes complete source labels for accepted/rejected
clock readings and lexical phase visibility. Resolve UI support units and
original physical/context split provenance before a complete qualification
bundle. Also retain the separate unqualified result-reference/end/rearm blocker;
source start reproduction does not prove R1end→R2whole-stream lifecycle or
canonical package association.

Machine-readable source labels, original display comparisons, PTS, terminal
hashes and original split provenance:
[ui_continuous_source_review.json](../e2e_reports/match_001/ui_continuous_source_review.json).
