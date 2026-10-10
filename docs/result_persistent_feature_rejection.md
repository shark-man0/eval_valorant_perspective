# Frozen result representation: independent source check and rejection

## Problem

The late result reference misses visible TEAM ACE text at NCC0.90. This blocks
qualified result corroboration for `GT-R1-ROUND-END` and downstream lifecycle
count/package assertions. Fixing it would not itself settle end timestamp
semantics or guarantee any canonical PASS increase.

## Evidence and training hypotheses

Only the original three distinct RGB training frames were used to freeze the
alternative assets. Grayscale stable trimming removes contrast: group reference
standard deviations3.55/4.40/4.77fail the existing5minimum. Fixed Canny12/24 also
fails training with minimumNCC0.5222. Neither is adopted.

Min-BGR>=200 separates white text from colored brightness. Keeping only original
mask pixels whose binary values agree across all three training images retains
foreground and negative contrast pixels in three groups. Training NCC1is true
by construction; it is not accuracy evidence. The method, pixel cutoff, ROI,
reference and masks were frozen before the new validation predictions. No
threshold search, registration search, heldout fitting or GT input was used.

## Independent source evidence

The explicit76.55–76.75sec window contains12native frames. All12are decoded and
evaluated, with source SHA256, exact ticks, original pixel hashes and terminal
input hash checks. Eight ticks are reserved before prediction after excluding
known saved native/decimal source exposures, including historical full reports.
The inventory does not prove exhaustive absence of prior exposure. Frames are
from the same result episode and are correlated; they are not independent
lifecycle episodes or sufficient event qualification.
The selection-time failure-analysis preimage is saved locally as
`failure-analysis-at-selection.json` in the validation image directory. Its
hash matches the frozen reservation input even after this analysis is updated.

Post-prediction review of the original unannotated images finds TEAM ACE readable
in all12. Existing three source-reviewed negatives are preserved. Scoring uses
the existing semantic matcher with NCC0.90and all three required spatial groups.
Both representations use the same crop and original physical training hashes.
All12saved images' encoded and decoded-pixel hashes are rechecked after review.

| Reserved source metric | Previous grayscale | Current binary | Delta |
| --- | ---: | ---: | ---: |
| Correct | 2 | 2 | 0 |
| Unknown | 6 | 6 | 0 |
| Wrong | 0 | 0 | 0 |
| Existing negative false positives | 0 | 0 | 0 |

Across all12frames both representations accept the same3frames. Correct/unknown
transitions are unchanged. Binary NCC improves on some images and worsens on
others; score changes do not establish an accuracy gain. Background contrast
still prevents generalization despite text readability.

## Decision and contract

Reject this representation for adoption: no acceptance improvement and only two
reserved correct cases, below the existing three-case qualification support.
No production preprocessing/profile/threshold/qualification change is made.
The cohort is now exposed development evidence and must not be relabeled a fresh
holdout. No round event is emitted. The user's source-specific no-edit assurance
remains accepted; this investigation concerns recognition, not editing.

## Tests and runtime

Four relevant unit tests PASS; focused RuffPASS. Tests cover unchanged training
pixels, colored versus white support, incomplete training rejection and source
grid exposure exclusion. Native decode/comparison takes27.557677seconds. Previous
comparable runtime is unavailable; this is not a speed comparison or an E2E run.
Production was unchanged; no new mypy run is needed for these diagnostic files.

Canonical Previous23PASS/55FAIL/4NE; Current/Delta unavailable. All82assertion
states remain unchanged. No new targeted/sampled/full canonical run was justified
by this rejected representation. Negative assertion/discontinuity outcomes are
not newly claimed from three image controls. Windows hardware is unverified.

## Remaining blocker and next action

Stop tuning this representation. Return to source-assured start temporal
qualification and upstream source-backed contracts. Result evidence availability
and end timestamp semantics remain separate unresolved gates; do not backdate a
late score/result observation into a fixed acceptance window.

Reports: `result_training_mask_audit.json`,
`result_persistent_minchannel_training.json`,
`result_persistent_feature_reserved_cohort.json`,
`result_persistent_feature_validation.json`, and
`result_persistent_feature_review.json` under `e2e_reports/match_001`.
Images remain local under `outputs/recognition-investigation`.
