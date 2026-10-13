# Neutral-white colour assumption fails before result glyph qualification

## Problem and fixed target

`GT-R1-ROUND-END`and`event_count_constraints-002`still need qualified result
semantics. Prior grayscale glyph methods fail actual background variation and
confusable controls. Check whether a neutral-white foreground condition separates
the source E/Aglare bridge without changing source pixels orNCC0.90.

## Frozen hypothesis and input

Reuse the same three native training rasters75.402669,75.802669,76.269336and
crop[842,178,1078,247],with verified encoded hashes. Before predictions fix
all channels≥210and channel spread≤12. Declare seven measured tall glyphs,
Gaussian3×3whole-glyphNCC0.90plus eroded negative-space purity0.90,minimum32
foreground/background pixels and three supported training sources. No threshold
scan, pose search, word repair or holdout tuning.

## Evidence and rejection

Original grayscale white210produces connected-component counts7,7,6; the fixed
neutral-colour subset produces7,7,5. Even the first count7is not correct seven
character correspondence: the Tshrinks to a narrow vertical fragment, the M
splits and the Cis omitted. The third source also loses real letter components.
The stricter colour condition therefore cannot safely isolate the actual font.
Its rendered foreground is not consistently neutral white under the capture/
compositing conditions. Exact cause of colour tint is not inferred from these
three images.

Reject at segmentation eligibility, before glyph scores, synthetic added-stroke
control or any holdout. Training support0; qualification0; production change0.
Keep all inputs and the fixed method. Do not loosen the colour gate or reinterpret
component count7as correct text. Runtime0.016seconds excludes input loading.

## Previous / Current / Delta

| Release metric | Previous | Current | Delta |
| --- | ---: | ---: | ---: |
| Qualified exact result reader | 0 | 0 | 0 |
| Qualified end from this route | 0 | 0 | 0 |
| Formal end from this route | 0 | 0 | 0 |

This is a distinct training-only hypothesis, not a new independent source cohort
or an accuracy comparison across dissimilar methods. No shared code changed;
preceding303relatedtests,Ruff/mypyremain applicable. No full regression/E2E or
Windows execution. All82canonical statuses retain historical23PASS/55FAIL/4NE.

## Remaining requirement

Foreground/negative-space discrimination must survive the actual nonneutral or
translucent-looking letter pixels. Relative local contrast is a defensible next
hypothesis; a constant white-font gate is rejected. Do not repeat whole grayscale
cell/tile methods or mask away uncertain glyph interiors simply to pass training.

[Fixed declaration, source hashes and measured component boxes](../e2e_reports/match_001/result_neutral_colour_training.json).
