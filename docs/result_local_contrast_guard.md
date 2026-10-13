# Optional result glyph contrast guard

## Problem and targets

`GT-R1-ROUND-END`and`event_count_constraints-002`need trustworthy result
semantics. Whole-word NCC can accept altered text. A source-derived39pixel
added-stroke control scores0.927641with the current late-result reference,
above the unchanged0.90floor. Full grayscale cells and neutral-white colour
segmentation failed training. Current letter rendering is not uniformly opaque
white; relative foreground/background contrast is a better testable premise.

## Frozen training design

Use the same3native source reference frames and seven complete glyph boxes.
Median grayscale reference selects white210foreground, eroded1pixel to omit
ambiguous edges. Fill its foreground convex hull; erode internal background by
1pixel. Retain every selected negative-space pixel rather than masking out
uncertain letter interiors. Compare each region with foreground core using
Gaussian3×3grayscale maskedNCC≥0.90and positive foreground/background polarity.

Three fixed background groups were ineligible: Anegative regions have49/55
pixels and M94,insufficient for3×32. A separately frozen adaptive variant uses
`min(3, background_population // 32)`equal-population row-major partitions.
Each comparison still has≥32foreground/background pixels. No data discarded,
current-image white-colour assumption, pose search, word repair or threshold
scan. Original3source images support2/3;0.884630stays rejected at0.90.

Select all11old inventory cases unassigned to the original training/holdout,
before new predictions. Keep the3native reference and masks unchanged, and
preserve the original11holdout. Guard-only support becomes8/14; combined
production wordNCCplus guard support is6/14. Training support describes matched
physical images, not independently detected events or a claim that every
training image is readable. The original unknown remains unknown.

## Shared production integration

New `hud/glyph_contrast.py`derives all tall reference glyph boxes and checks
every glyph's foreground/negative-space partitions. Actual input remains
ordinary grayscale/BGR; shape/type mismatch, inadequate support, undefinedNCC
or reversed contrast fail closed.

`SemanticTextReference`optionally conjoins this guard with existing wordNCC.
The default is unchanged. Score and diagnostic presence use the same minimum;
no guard can promote a nonmatch. Constructor requires≥3distinct source-frame
hashes supporting the combined predicate. Profile support is opt-in and limited
to `round_end_template`:

```json
"contrast_guard": {
  "method": "glyph_local_contrast_v1",
  "template": "result-contrast/reference.png"
}
```

The ordinary semantic mask, groups, bounded ROI, source-backed training andNCC
requirements remain mandatory. Malformed guard or nonsemantic matcher cannot
fall back to unguarded matching. Its template asset enters the existing profile
fingerprint; the new module enters the existing global code fingerprint. No
Pi-specific branch, ownership evidence, formal event permission or qualification
is supplied by a guard match.

A local experimental sidecar and PNGassets live in ignoredoutputs; existing
profiles have not enabled the option. New production/source fingerprints require
fresh verification rather than silently re-signing older qualification counts.

## Source comparison

Actual shared loader/scorer reproduces the frozen guard on the original11
previously exposed holdout cases:3correct/8unknown/0wrong;3natural negatives
reject. All14source crops were reviewed before the new comparison. This is not
a new blind cohort or independent end-event qualification.

An initial parity script used direct JPEGgrayscale decode, causing small score
differences from runtime's BGR→grayconversion. Correct it to the actual runtime
input path; acceptance/reference/masks and parameters are unchanged. Production
scores and decisions then match the prototype.

| Same input metric | Previous | Current | Delta |
| --- | ---: | ---: | ---: |
| Holdout correct | 3 | 3 | 0 |
| Holdout unknown | 8 | 8 | 0 |
| Holdout wrong | 0 | 0 | 0 |
| Natural negative false positives | 0 | 0 | 0 |
| Added-stroke control accepted | yes,NCC0.927641 | no,score0.670662 | reject |
| Installed release qualifications | 0 | 0 | 0 |

The synthetic control is not a natural frame or the exact game's Gfont. Its
rejection fixes a demonstrated hole; it does not prove rejection of every
possible confusable word. Relative contrast is also tested under affine
lighting changes, with no currentpixel210white requirement.

## Tests

176relatedtestsPASS;fullpytest2740PASS/6SKIPin1937.64seconds;RuffPASS;mypyPASS
on129source files. Tests cover every negative-space pixel's partition coverage,
malformed shapes/types, confusable/blank rejection, lighting variation, copied
reference, score/measure agreement, combined source support, profile asset hash
binding and invalid-guard fallback prevention. Synthetic fixtures are not real
qualification support. Full regression runtime1918.35→1937.64seconds,+19.29
(+1.01%),with2707→2740tests;no pipeline speed inference from differing suites.

Skips are unavailable real-HUD accuracy fixture/system Tesseract and host-native
Windows/PowerShell tests. Windows runtime and current CI remain unverified.
Images stay local; shared report contains hashes, coordinates and statistics.

## Remaining blockers

No full E2E: independent current-fingerprint reader/UI/result qualification and
continuous lifecycle gates are incomplete. Native round events/packages and
canonical82statuses are not promoted. Historical23PASS/55FAIL/4NEremains the
last canonical full result, with no new full Current/Delta. Qualification units
must distinguish correlated image support from event-case counts. R1end timing,
current/retained score evidence and R1→R2rearm remain separate contracts.

Next, validate current native continuous end-context inputs using this strict
optional guard and the existing score/timer readers. Do not backdate events from
GT, fill unknown scores or treat this component test as a detected round end.

Machine-readable stage decisions, source hashes, Current/Previous/Delta and tests:
[result_local_contrast_guard.json](../e2e_reports/match_001/result_local_contrast_guard.json).
