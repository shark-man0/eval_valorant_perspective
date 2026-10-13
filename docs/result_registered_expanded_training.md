# Expanded training tests the registered-glyph premise without early-frame fitting

## Problem and targets

`GT-R1-ROUND-END` and `event_count_constraints-002` remain blocked by temporal
qualification and the early complete result rendering. A prior fixed glyph
registration experiment failed eligibility on three reference images with
component counts 7/7/6. Test its structural method on all 14 already assigned
training parents; do not fit to held or early source frames.

## Fixed experiment

Use the current source parents and exact hashes: three native images and
11 previously assigned archival JPEG training images. Preserve all 14 inputs.
Actual BGR→gray conversion matches runtime's input path. Extract connected
glyph components with the existing fixed white-210, area≥32, width≥3,
height≥40%-of-ROI rule. Require exactly seven complete components in each
accepted frame. Non-seven-component frames remain unknown; no component is
removed, repaired, merged or silently counted as support.

Normalize each complete glyph with its original one-pixel border to 28×56 using
`INTER_AREA`. If at least three distinct complete training parents exist,
derive a per-cell median from all complete parents. Keep all seven cell NCCs
at 0.90 and the current word/contrast predicate in conjunction. This applies
the existing minimum-support rule to the expanded inventory; it does not
require every supplied training frame to be recognized or accept invalid frames.
Freeze the procedure before predictions. No threshold/segmentation scan occurs.

## Result and Previous / Current / Delta

Seven of 14 parents have exactly seven usable components. The other seven
remain ineligible/unknown. Five distinct source parents meet the combined
word/contrast plus all-seven-cell predicate, above the unchanged minimum of
three. Exact source, code/profile and execution-plan hashes verify at completion.
The experiment takes 1.883 seconds.

| Training eligibility metric | Previous small inventory | Expanded inventory | Delta |
| --- | ---: | ---: | ---: |
| Training parents supplied | 3 | 14 | +11 |
| Combined registered support | 0 | 5 | +5 |
| Formal end events | 0 | 0 | 0 |

This is different source inventory and the current guarded predicate, so the
support change is eligibility evidence, not a held accuracy gain. No holdout,
early frame, natural negative or synthetic counterexample is scored in this
experiment. No qualification or new source reference is installed.

## Root-cause decision

The original registered method is an **additional AND guard** on the existing
word predicate. Mathematically, its combined score cannot exceed that predicate.
It therefore cannot recover the early image already rejected by the existing
word matcher, regardless of its new five-image training support.

Reject this candidate for the early-result objective. Training eligibility is
not proof that it fixes end timing. Do not waste held-frame/full-E2E execution,
integrate an unnecessary guard, or remove its original conjunct and claim that
the altered algorithm was already qualified.

## Next concrete hypothesis

Recognition of rendering/scale variation would require a separately defined
registered word comparator, with complete seven-glyph correspondence, each
glyph's NCC≥0.90, negative-space discrimination, and word geometry/space
constraints derived only from training. It would be a new matcher representation,
not a threshold reduction or the unchanged additional guard.

Freeze that independent prototype and source-support criteria before original
held/early challenge scoring. Keep all source frames/splits, minimum support,
identity/ownership/geometry safety and negative controls. It must obtain its own
qualification and cannot inherit the present fixed-word component proof.
If structural support fails, reject it instead of scanning thresholds or
discarding letters. No current production change follows from this experiment.

## Tests and canonical status

Training source hashes, full glyph counts, all seven per-cell scores, support
counts and terminal code/profile checks pass. JSON and diff checks pass. No
production code changed; prior 2740 passed / 6 skipped, Ruff PASS and mypy PASS
remain applicable. No redundant regression or full E2E runs. The adopted
canonical result remains 23 PASS / 55 FAIL / 4 NE; no new full Current/Delta
or end event is claimed. Windows runtime remains unverified.

Machine-readable eligibility and rejection:
`e2e_reports/match_001/result_registered_expanded_training.json`.
Local frozen plan and all source scores:
`outputs/recognition-investigation/result-registered-expanded-training-20261013/`.
