# Seven training-derived slots expose the early renderer's appearance mismatch

## Problem and targets

The previous native-pixel comparator fails the early result image because
seven source letters form four thresholded components. For
`GT-R1-ROUND-END` / `event_count_constraints-002`, test whether segmentation
alone explains that failure, without hand-splitting the challenge or relaxing NCC.

## Frozen source-only representation

Use the same 14 assigned training parents and seven complete eligible words.
Median training component bounds define seven fixed source-native slots:

```
[x,y,width,height]
[7,8,25,56] [34,8,21,56] [57,8,30,56] [90,8,39,56]
[142,8,31,56] [174,8,29,56] [206,8,21,56]
```

Derive each slot's reference/core/negative space from actual training pixels
at those bounds, including the original one-pixel border. Keep full-cell and
all foreground/negative-group NCC≥0.90, polarity and at least 32 physical
pixels per region. Add an explicit inter-word space check, bounds
`[130,8,141,64]`, against the combined foreground/space mask at NCC≥0.90 and
positive foreground/space contrast.

Runtime comparison uses seven measured source slots; it no longer requires
seven separate current connected components. This neither invents seven
matched letters nor grants presence from a known word: every slot and the
space must actually pass. No source image resizing, held-frame position fitting,
threshold scan, free pose search or mask dropping occurs. ROI shape mismatch
rejects. Freeze method/reference hashes before original held/early scoring.

## Training and fixed held evaluation

Seven of 14 training parents pass all conditions, above the existing minimum
three. The known 39-white-pixel source-derived C-aperture addition scores
0.722216 and rejects; blank rejects. Do not count that synthetic change as a
natural negative or the game's exact G font.

Original 11 held source images yield 5 correct / 6 unknown / 0 wrong;
three natural negatives reject. These are the same outcomes as the previous
native-mask prototype, with no model/threshold change after scoring. Existing
exposure remains explicit; no new blind cohort is claimed.

| Same source metric | Previous native components | Fixed slots | Delta |
| --- | ---: | ---: | ---: |
| Held correct | 5 | 5 | 0 |
| Held unknown | 6 | 6 | 0 |
| Held wrong | 0 | 0 | 0 |
| Natural negative false positives | 0 | 0 | 0 |
| Early semantic slots actually compared | 0 | 7 | +7 |
| Early image accepted | no | no | 0 |

Training takes 1.894 seconds; fixed held/control evaluation 1.604 seconds.
These static workloads do not establish an E2E speed delta. A copied evaluation
hash routine initially expected three-element model tuples instead of the
four-element fixed-slot tuples; correct that bookkeeping before control/held
scoring, without changing the model, selection or predicate.

## Early appearance evidence

The exposed early image at 74.436003 now reaches every slot comparison:

| Glyph | Full-cell NCC | Lowest foreground/negative NCC |
| --- | ---: | ---: |
| T | 0.576988 | 0.775202 |
| E | 0.632631 | 0.563915 |
| A | 0.404418 | 0.391003 |
| M | 0.469581 | **0.214195** |
| A | 0.731679 | 0.513036 |
| C | 0.606660 | 0.354872 |
| E | 0.947583 | 0.982062 |

Word-space NCC is 0.650002. All polarity checks pass and the required physical
pixel populations are present, but six glyphs and the space fail the unchanged
NCC floor. Only the final E passes. The overall result is 0.214195, not a nearly
eligible match. Do not adjust parameters toward this exposed image or accept
one matching letter as evidence for the whole caption.

Thus component fusion was only the first blocker. Bypassing it does not solve
appearance compatibility between the early rendering and the available late
reference family. This experiment does not identify which alpha/scale/texture
mechanism caused the mismatch; do not overstate that diagnosis.

## Decision and next work

Reject this candidate as an early-renderer recovery and stop tuning comparator
variants against this one early image. No new reference, threshold waiver or
formal event follows. The late-caption source qualification and correct
clock/score transitions remain available for delayed corroboration.

Return to explicit `ui_end_transition` support/context review using the existing
five-component source evidence, with honest one-end-case scope and physical
splits. Preserve the observed score-change candidate time separately from the
later confirmation. Do not backdate to the manual early-caption timestamp or
claim that the existing strict acceptance window has improved. Practical timing
accuracy and strict canonical acceptance remain distinct.

## Tests and canonical status

Training/source hashes, frozen prototype/reference hashes, original labels,
counterexample/natural-negative rejection and terminal checks pass. No shared
production code, profile, GT or assertion changed. Prior current-code
2740 passed / 6 skipped, Ruff PASS and mypy PASS remain applicable; JSON/diff
checks pass. No redundant long regression or full E2E, no new qualification,
and no current Windows execution claim. Adopted baseline remains
23 PASS / 55 FAIL / 4 NE.

Machine-readable all-seven scores and comparison:
`e2e_reports/match_001/result_fixed_slot_training.json`.
Local fixed prototype, plans and full source outputs:
`outputs/recognition-investigation/result-fixed-slot-training-20261013/`.
