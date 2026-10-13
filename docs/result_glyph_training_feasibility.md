# Result glyph discrimination: training rejection

## Problem and fixed targets

`GT-R1-ROUND-END`and`event_count_constraints-002`need independent result evidence
before qualified end/rearm can unblock package association. Earlier whole-word
maskedNCCcan accept a syntheticTEAM AGEconfusable at0.99229. Earlier per-glyph
binary3×3tiles reject that control but reject0/6real training examples too.
Do not retry that method, lowerNCC0.90or promote a word merely from confidence.

## Frozen hypotheses and source scope

Reuse three explicitly reviewed late-result development images75.402669,
75.802669,76.269336atcrop[842,178,1078,247]. They are already exposed training
data, not independent holdout. Four separate declarations precede their own
training predictions; no real holdout is evaluated after rejection:

| Fixed method | Training support | Synthetic confusable | Decision |
| --- | ---: | --- | --- |
| Full grayscale glyph cells,1pixel border,NCC0.90 | 1/3 | TEAM AGEbelow0.90 in synthetic font | reject support |
| Original wordNCC0.90plus glyph edge recall/precision0.90 | 2/3 | TEAM AGE0.955157accepted | reject support and control |
| Original wordNCCplus training-stable binary3×3tiles | ineligible | syntheticTEAM AGE0.65rejected | reject comparable population |
| Measured connected glyph cells normalized28×56,NCC0.90 | ineligible | syntheticTEAM AGE0.893541rejected | reject segmentation |

The conjunctive edge method retains original wordNCCrather than substituting a
weaker score. Existing structural_scorekeeps its one-pixel/20degree tolerance.
The stable tile method requires≥80%and≥32comparable pixels in every tile and
≥32stable foreground/background pixels per glyph; no unstable region is dropped
to satisfy the criterion. Several E/Aregions retain only31–77%comparable pixels.
Registration uses measured connected components, never a free best-match search;
source glyph counts7,7,6fail the declared seven-glyph requirement.

## Independent source inspection and encoding check

The third image has bright background/glare bridging E/Aat the fixed white210
segmentation level. Same physical native decoder frames are then acquired and
hash-verified before/after processing, using the unchanged crop and methods.
Native glyph counts remain7,7,6,so this is not solely JPEGencoding degradation.
Rebuilding the grayscale median from native counterparts still supports only1/3:
minimum cellNCC0.899847,0.907549,0.867660. No rounding or epsilon acceptance is
used at0.90. The native acquisition/check takes42.884s.

The source-derived Ccell also receives an offline synthetic39pixel horizontal
stroke in its aperture. Full-cellNCCis0.908383,so the cell matcher accepts it at
0.90. This is an added-stroke control, not a claim that it is the exact game's G
font, and not a natural video negative. The original video and references are
unchanged. It demonstrates that synthetic-font rejection alone cannot establish
exact semantics for the actual font. Full-cell area can still hide critical
negative-space changes.

## Previous / Current / Delta

| Release metric | Previous | Current | Delta |
| --- | ---: | ---: | ---: |
| Qualified exact result reader | 0 | 0 | 0 |
| Qualified end from these methods | 0 | 0 | 0 |
| Formal end events from these methods | 0 | 0 | 0 |

The4methods are distinct hypotheses, not comparable accuracy populations or
new independent source episodes. All train on the same3physical cases. Their
subsecond matcher timings are retained separately in JSON; native conversion
does not create extra support. No threshold scans, word repair, timing injection,
profile or production changes. Existing2707PASS/6SKIP,Ruff/mypyverification
remains applicable to unchanged code; no unnecessary full regression/E2E.

## Conclusion and remaining blocker

Reject all4methods. Exact glyph discrimination and tolerance of actual rendering/
background variation are not jointly supported by these training examples.
A whole-word or whole-cell confidence above0.90is insufficient. Additional
source training support and a defensible foreground/negative-space distinction
are needed before another frozen reference can reach independent holdout.
Do not fix the training failure by dropping characters or ignoring blank glyph
interiors. No additional video is made a prerequisite; use available current
source evidence first.

Global end still additionally requires qualified score/timer/temporal inputs and
correct original boundary semantics. Qualification files remain absent, and the
fixed expected-score discrepancy is retained. All82canonical statuses remain
historical23PASS/55FAIL/4NE; Current full/Delta are unavailable. Windows execution
is unverified.

Exact scores, native hashes and frozen method declarations:
[result_glyph_training_feasibility.json](../e2e_reports/match_001/result_glyph_training_feasibility.json).
