# Independent registered word prototype: normalization loses required negative space

## Problem and targets

The old additional AND guard cannot recover the early result nonmatch for
`GT-R1-ROUND-END` / `event_count_constraints-002`. Test a separate word
representation on the already frozen 14 training parents. Unlike the old
conjunction, it would require its own qualification before any runtime use.

## Frozen training-only design

Retain all 14 source images, original hashes and split. Use fixed white-210
connected components, area≥32, width≥3, height≥40%-of-ROI, exactly seven glyphs,
one-pixel border and 28×56 `INTER_AREA` registration. Non-seven-glyph frames
remain unknown. Require the gap between the two words to be uniquely widest.
Derive width, height, top and gap envelopes from all eligible training parents,
with one physical-pixel quantization allowance; no free pose search.

The independent prototype uses all seven glyph NCCs≥0.90 and the existing
foreground/negative-space contrast guard, preserving its minimum 32 pixels per
region, positive polarity and all selected background pixels. It does not
inherit a rejected old word match, discard a glyph, lower a threshold or use
held/early images for fitting. Freeze all criteria before scoring.

## Result and root cause

Seven of 14 training parents supply a complete seven-glyph word and valid
word-space structure. Their per-cell median canonical strip fails the existing
contrast constructor: **insufficient foreground/negative space**. No valid
independent model exists, so training support is zero. Stop before held,
natural-control, synthetic-control or early-frame scoring.

A source-only population audit identifies the loss:

| Glyph index | Canonical negative pixels, 28×56 | Median native-reference negative pixels | Required |
| --- | ---: | ---: | ---: |
| 0, T | 126 | 140 | ≥32 |
| 1, E | 200 | 174 | ≥32 |
| 2, A | **29** | 47 | ≥32 |
| 3, M | **26** | 80 | ≥32 |
| 4, A | 32 | 42 | ≥32 |
| 5, C | 127 | 169 | ≥32 |
| 6, E | 196 | 169 | ≥32 |

Native-reference dimensions are the median physical training glyph dimensions,
not an arbitrary enlargement chosen to reach a population gate. The audit
does not score new current native glyph candidates or prove their masks have
sufficient unique physical samples. Reference eligibility is distinct from
runtime eligibility.

## Previous / Current / Delta

Both experiments use the same 14 assigned training parents. The previous
additional AND guard has five combined supports; the current independent word
prototype has zero because its reference is invalid. Their predicates differ,
so this is not an accuracy regression comparison. Formal end events remain
0→0. Production and adopted canonical 23 PASS / 55 FAIL / 4 NE are unchanged.
The failed training prototype takes 1.739 seconds; no comparable pipeline
runtime delta is claimed.

## Decision and next hypothesis

Reject the 28×56 contrast-footprint premise. Do not reduce 32, omit A/M,
change segmentation after seeing a held result, or enlarge current-image pixels
and count interpolation as additional independent evidence.

Next training-only hypothesis: preserve native reference glyph dimensions and
transport the reference/masks onto each actual current source glyph patch.
Measure contrast on original current pixels, requiring at least 32 distinct
physical foreground/negative-space samples in every comparison. Keep complete
seven-glyph NCC, word geometry, original splits and minimum source support.
The native-reference population audit motivates this test but does not qualify
it or guarantee early detection.

## Tests and scope

Exact source/pixel hashes, complete glyph counts, deterministic reference
population calculation and terminal code/input hashes verify. No production
code, profile, safety policy, GT or assertion changed. Existing current-code
2740 passed / 6 skipped, Ruff PASS and mypy PASS remain applicable; JSON and
diff checks pass. No redundant E2E or regression run, no new qualification,
no event and no new blind cohort. Current Windows execution is unverified.

Machine-readable rejection and every glyph population:
`e2e_reports/match_001/result_independent_registration_training.json`.
Local frozen plan, training outputs and population audit:
`outputs/recognition-investigation/result-independent-registration-training-20261013/`.
