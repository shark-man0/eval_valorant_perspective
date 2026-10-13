# Native-pixel registered word evidence: held improvement, early segmentation failure

## Problem and fixed targets

For `GT-R1-ROUND-END` / `event_count_constraints-002`, the independent 28×56
word representation lost the minimum negative-space population. Preserve real
current pixel coordinates while checking all seven glyphs and their geometry.
Do not use early/held data to refit training or relax a threshold.

## Frozen training design

Use the same 14 assigned source parents. Keep fixed white-210 connected
components, area≥32, width≥3, height≥40%-ROI, exactly seven components, a unique
widest gap between the words, and training-only width/height/top/gap envelopes
with one physical-pixel quantization allowance. Clipped glyphs fail closed.

Each glyph reference uses median physical training dimensions. Resize only
the reference and transport its masks onto the actual current glyph patch.
Actual current pixels are not resized or enlarged to create evidence. Require
at least 32 distinct current foreground and negative-space pixel coordinates.
Retain every mapped negative pixel in population-adaptive groups; require
positive foreground/background polarity, each full-cell NCC≥0.90 and every
foreground/negative-space NCC≥0.90. No old word match is inherited by this
independent prototype.

Seven training images provide complete word references and all seven meet
the combined predicate. Invalid training parents remain unknown. Source/code/
plan hashes verify. Training takes 2.030 seconds.

## Counterexample and original fixed evaluation

Freeze the model, reference/mask hashes and original held/negative/early
challenge list before scoring. Test the known 39-white-pixel source-derived
C-aperture addition first: score **0.709370**, rejected. Blank rejects. This is
a synthetic source-derived control, not the exact game's G font or a natural
negative. No mask/reference/threshold change follows from it.

Then score the original 11 held source images and three natural negatives once.
All earlier correct held images remain correct, and two previously unknown
images at 76.102669/76.119336 become source-correct matches. No wrong increase
or natural negative false positive is observed.

| Same original source metric | Previous fixed guarded word | Native-pixel prototype | Delta |
| --- | ---: | ---: | ---: |
| Held correct | 3 | 5 | +2 |
| Held unknown | 8 | 6 | -2 |
| Held wrong | 0 | 0 | 0 |
| Natural negative false positives | 0 | 0 | 0 |
| Early source challenge accepted | no | no | 0 |

This remains an exposed same-source cohort, not new blind qualification.
Fixed held/control evaluation takes 1.159 seconds. No pipeline speed claim or
full-E2E result is inferred from that static workload.

## Early failure before NCC

The reviewed early complete caption at 74.436003 fails with four retained
thresholded components:

```
[x,y,width,height]
[6,7,80,60]
[90,8,40,46]
[144,8,27,47]
[175,8,52,60]
```

The first component spans T/E/A and the last spans C/E. The source still
contains seven readable semantic letters. Connected components are segmentation
units, not proof that only four letters exist. This prototype's strict
seven-isolated-components precondition rejects before geometry or NCC; the
early sample does not provide a low NCC measurement for this model.

Do not lower 210, split those specific boxes by hand, discard letters, replace
unknown with the manual label, or claim that the held +2 fixes early boundary
timing. The early source remains an exposed challenge, not newly independent
holdout or training.

## Decision and next hypothesis

Keep the late-word training/held evidence as a recorded experimental result.
Do not integrate this model as a solution to the early-onset root cause and
do not run a costly full E2E for a candidate that still fails its key target.

Next training-only hypothesis is a seven-slot word layout derived from complete
training sources, checking every glyph's foreground/negative space and the
inter-word space without requiring one thresholded component per letter.
Retain all seven NCC floors, 32 distinct current pixels, clipping/ambiguity
guards, source splits and minimum support. The early challenge must not define
slot boundaries or select parameters. This is a representation test, not a
waiver of identity/ownership/geometry safety or qualification.

## Tests and canonical scope

Frozen training and held/source hashes, reference/mask hashes, physical current
pixel populations, counterexample/blank rejection and terminal checks pass.
No production code, profile, threshold, validation pack or assertion changed.
Prior 2740 passed / 6 skipped, Ruff PASS and mypy PASS remain applicable;
JSON/diff checks pass. No new qualification or formal end, no canonical full
E2E, and no current Windows execution claim. Adopted status remains
23 PASS / 55 FAIL / 4 NE, with full Current/Delta unavailable.

Machine-readable every-glyph scores and source counts:
`e2e_reports/match_001/result_native_mask_registration.json`.
Local frozen prototype, plans and complete outputs:
`outputs/recognition-investigation/result-native-mask-registration-20261013/`.
