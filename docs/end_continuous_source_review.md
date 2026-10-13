# Complete native source review of the R1 end window

## Problem and targets

`GT-R1-ROUND-END` and `event_count_constraints-002` need an end timestamp with
actual image meaning. Prior diagnostics record score change at 74.486003 and
result matcher support from 75.319336. Do not interpret matcher acceptance as
the first physical appearance of a result caption or backdate an event to GT.

## Independent image evidence

Review all 108 original native images in the existing 74.2–76.0-second window.
Six chronological source-only contact sheets show the original topbar and
bounded result ROI without recognizer predictions, expected values or GT
overlays. Verify every decoded pixel hash against original source metadata;
lossless PNG reencoding is retained as an explicit archive distinction.
Recorded PTS and cadence remain unchanged. No new video decode or recognition
run is needed: compare labels only to the unchanged current-code guarded
producer output after source review.

This is an independent source transcription, **not** a new blind cohort.
Earlier development and selected-frame reviews already exposed this episode.
The source-specific unedited assurance remains in force; no edit-only image
proof is repeated. Crops do not newly attest whole-scene continuity, phase
absence or the exact physical game-end time.

## Source observations and competing timestamp hypotheses

The reviewed topbar shows:

- 15 frames of `0:29`, then 53 of `0:06`, then 40 of `0:05`.
- Ally score remains 0 throughout.
- Enemy score is 1 for the first 17 frames, then 2 for the remaining 91.

Key native observations are distinct:

| Source observation | PTS seconds | Tick |
| --- | ---: | ---: |
| Brief complete `TEAM ACE` inside bounded ROI | 74.436003 | 1143337 |
| First `0:06` after `0:29` | 74.452669 | 1143593 |
| First enemy score 2 after 1 | 74.486003 | 1144105 |
| First `0:05` after `0:06` | 75.336003 | 1157161 |

The complete caption briefly appears before the clock and score transitions,
then its rendering moves/scales and becomes partial, clipped or obscured.
Later caption pixels settle enough for the current matcher. The full source
review contains 45 complete readable captions, 20 partial/ROI-clipped captions,
one obscured result ROI and 42 without a readable caption inside that bounded
ROI. The latter categories do not attest absence elsewhere in the image.

The current guarded matcher first supports a continuous result run at
75.319336, confirmed at 75.369336. Those times describe **recognizer support**,
not first source-visible result text. At confirmation the source timer is already
`0:05`; current OCR remains unknown and is not filled from that manual label.

Three possible end-time cues therefore exist: early caption, clock reset and
score increment. Their causal relationship is plausible but the exact physical
game-end semantics are not attested by this review. Do not select whichever
falls nearest GT, round 74.486003 into the strict window, or treat the later
matcher time as the boundary. Existing candidate time remains unchanged.

## Recognition accuracy against source labels

| Current field | Correct accepted | Unknown/nonmatch | Wrong accepted |
| --- | ---: | ---: | ---: |
| Timer literal display | 17 | 91 | 0 |
| Ally score | 53 | 55 | 0 |
| Enemy score | 61 | 47 | 0 |
| Complete score pair, physical frame unit | 47 | 61 | 0 |
| Result matcher | 29 | 79 nonmatches | 0 |

All 29 result matches occur on source-complete captions. Nonmatches retain
their original status; they do not become absence assertions. The early complete
caption remains a source-reviewed unknown for the current matcher. Preserve
the original `0:29`/enemy 1 prefix, including the previously documented GT/source
score disagreement. No source value is altered to match a pack expectation.

## Continuity decision and contract change

Retain SHA-specific source assurance, native PTS/cadence/image guards and all
existing fail-closed transitions. This review does not qualify a new end path,
change the one-second horizon, create an event, repair current values or change
the recognition/ownership/geometry policy. The only contract clarification is
diagnostic terminology: source appearance and matcher support are separate.

Do not multiply these 108 correlated images into independent end episodes.
One complete source episode still cannot be described as several independently
held temporal cases merely by truncation or overlapping windows.

## Previous / Current / Delta and tests

The new complete structured review covers 0→108 frames in this artifact;
earlier selected source reviews existed. Accepted timer/score/result wrong
counts are now source-verified zero, rather than assumed from confidence.
Predictions are unchanged, no formal end is generated, and adopted canonical
status remains 23 PASS / 55 FAIL / 4 NE. No new full run or full-match safety
delta is measured.

All 108 source pixels and six contact-sheet hashes verify at completion;
manual-label/source binding and current prediction comparisons pass. No
production code changed, so the prior 2740 passed / 6 skipped, Ruff PASS and
mypy PASS evidence remains applicable. JSON integrity and diff checks pass.
No redundant E2E or full regression is run. Windows runtime is unverified.

## Remaining blocker and next concrete hypothesis

The existing late-reference matcher safely recognizes late captions but does
not qualify the brief earlier complete rendering. Never feed the manual
74.436003 observation back into production as a timestamp override.

A previously frozen registered seven-glyph method failed eligibility on only
three training references with component counts 7/7/6. The training inventory
has since been explicitly expanded to 14 already assigned source images.
Test that existing fixed method once against the full frozen training inventory,
without a threshold/segmentation scan, discarding a required glyph or fitting
to the early/held source frame. Retain seven complete glyph correspondences,
NCC 0.90, distinct source support and the original holdout. If eligibility still
fails, reject the premise rather than converting the early review into a proof.

Machine-readable labels and evidence:
`e2e_reports/match_001/end_continuous_source_review.json`.
Local source-only sheets and complete source transcription:
`outputs/recognition-investigation/end-continuous-source-review-20261013/`.
