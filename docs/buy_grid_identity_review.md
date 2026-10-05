# Buy grid identity review

## Starting checkpoint

The fixed Replay infrastructure checkpoint is complete at `697b5dd`, with
unchanged production detector behavior. Clean analyzer `5b7a7e2` remains
22 passed / 56 failed / 4 not evaluated, negative 20/0 and 4,038 observations.
The worktree was clean and origin/main synchronized before this diagnostic.
No Buy, Spectator, identity, threshold, ownership or temporal code changes here.

## Source, selection and frozen candidate

Source SHA-256:
`71d58558559d6f578433ce9f234bf176f76fd5a86657dbfe3eba1e7d36136b06`.
The secondary challenge draws 34 rows from each of the two fixed populations,
using fixed 1.25/3.75-second offsets in odd five-second blocks and excluding
previously reviewed samples. Selection precedes score inspection and uses no
GT/event/current-state/detector-score criterion. The official immutable sets
remain 1,026 and 4,038 frames; this challenge does not replace or refit them.
The prior-review exclusion and single recording limit independent generalization.

There are 68 rows but 66 unique native images: two cross-cohort duplicate
locators are both appearance-negative. All original JPEG and decoded BGR hashes
were recovered exactly through production VideoService quality-92/no-resize
extraction, including images absent from older E2E artifact directories.

The candidate is frozen max-of-three grayscale NCC on the existing 39x39 center
patch of the configured close-anchor crop, at 0.90, with no alignment search.
References come from the three earlier frozen training examples, not this
challenge. Candidate asset hash:
`cccadc393cd82fe7215c713b8a211432f21265c426583aa0f2d25a00d197fa60`.

Actual clean layout hash:
`a3678bcd9df35d0932ae0e69495eb5b87a3ab40e9c988560d502a9507d59eef1`.
The earlier source-layout hash is
`d74d3c38f23905e56a2c7eaea336aa1ab87f4cc7b77a1e9bcf2f35494fef2529`;
grid and close-anchor pixel bounds were verified identical, not assumed.
Grid bounds are [360,90,1510,960], close-anchor [1825,0,1918,95], and the
intervention patch [1852,27,1891,66] lies entirely outside the grid.

## Appearance-only held-out evaluation

Root reviewed full source-context pages with opaque captions before opening
per-image scores or locators. Aggregate scores had previously been disclosed,
so this is not described as pristine blind review. One caption transcription
error was corrected against the original page before joining; the old ledger
remains private and the corrected ledger hash is
`a53a89daf870d89a05ebf5f0c0023e1cdd9eca211c0c35484b44b300088153a1`.
Receipt checks prove every sample/category ID matches, with disjoint categories.

The six unique visibly open Buy-menu images all pass frozen NCC (.9957–.9982).
None of 60 unique non-Buy appearance controls pass; row counts are 6 positives
and 62 negatives. Controls include purple angular map UI, purple world fields,
Buy-phase banner without menu, scoreboard/report, death/body/report,
Spectator-portrait/report and ordinary world views. These are image appearances,
not expected production states or Agent knowledge. The same continuous menu
occurrences are close to training blocks, so dynamic-state invariance and
independent occurrence/recording qualification are still unproven.

## Independent pixel-contract stress

All 68 inputs were tested without selecting by appearance, score or replay
state. The original NCC was recomputed and equals the frozen score table on
every row. Grid evidence calls the unchanged production primitive
`_region_candidate(measure_roi(configured_crop), min_edge=0.055)`, whose existing
0.72 candidate threshold is retained. It combines edge density and contrast;
it does not establish Buy-specific grid identity.

Only the center patch is changed: insert each of the three frozen references,
or replace it with black or the original patch's mean BGR. No classifier is
called, and no production detector or threshold is changed. Grid scores are
exactly invariant under every intervention because that ROI is disjoint.

| Variant | NCC-positive unique images | Grid-positive unique images | Raw conjunction | Flips from original |
| --- | ---: | ---: | ---: | ---: |
| original | 6 | 17 | 6 | 0 |
| insert frozen reference 1 | 66 | 17 | 17 | 11 rejects to accepts |
| insert frozen reference 2 | 66 | 17 | 17 | 11 rejects to accepts |
| insert frozen reference 3 | 66 | 17 | 17 | 11 rejects to accepts |
| black patch | 0 | 17 | 0 | 6 accepts to rejects |
| mean-BGR patch | 0 | 17 | 0 | 6 accepts to rejects |

This measures counterfactual predicate sensitivity, **not** an observed
real-world false-positive rate. The remaining full-context pixels are unchanged.
It demonstrates that the coarse grid conjunct supplies insufficient independent
menu evidence when the generic close-X patch is supplied. Strong original
appearance-control scores alone therefore cannot qualify this representation.

Private stress aggregate hash:
`d47f8cfcd46b5cd7c697f91c389351c55f16436c57099e595a1568e78312f72b`.
Private per-image detail hash:
`f89b9a4ee049eded761fb12740024bce331b60a487d75f0e563c010c99d8d9d1`.
Shared `buy_grid_contract_stress_v1.json` contains only aggregate results, hashes
and geometry. No original/intervened frames, crops, references or per-image
score/label records are committed.

## Decision and next evidence

**NEED MORE EVIDENCE**. Do not adopt the close-X plus coarse-grid candidate.
The next experiment is already selected: learn only persistent long border/line
lattice from the three frozen training grid crops, discover two to four
separated support groups, exclude local icon/text/value evidence, and freeze
candidate masks/scoring before held-out evaluation. Test the same originals and
X-only interventions, requiring independent groups to reject the 11 additional
predicate accepts while retaining genuine menu controls. Record training and
holdout recurrence, support population, contradictions and insufficient evidence.
No threshold search or holdout refit will substitute for structural proof.

This diagnostic follows the verified infrastructure checkpoint (920 pytest
passed / 2 existing optional-fixture skips, Ruff/mypy/diff checks pass).
It adds aggregate/docs only; production code is unchanged, so no new adaptive
E2E is required. The clean 5b7 E2E and fixed baselines remain authoritative.
This evidence gap triggers the next diagnostic rather than stopping autonomy.
