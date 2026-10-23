# Private multi-video HUD failure corpus

`scripts/diagnostics/hud_failure_corpus.py` indexes existing native observations
without decoding video, fitting a model or changing any reader. The CLI reuses
the Private registry's DEVELOPMENT gate and Exposure journal. Register new
recordings with the existing Source-only intake and freeze their allocation
before using them. E2E registration and independent qualification remain separate.

```sh
python scripts/diagnostics/hud_failure_corpus.py \
  --review-session /private/dataset/review_session \
  --input /private/study/source_a_normalized.json \
  --input /private/study/source_b_normalized.json \
  --output /private/study/new_failure_corpus.json
```

Inputs use the existing native Round evidence rows, including complete native
coverage ledgers with `analysed: false` for frames without reader observations.
The existing transition validator checks source identity, PTS/timebase, repeated
PTS and acquisition boundaries. Optional `geometry_diagnostic` preserves the
existing anchor failure reasons/positions. `scope_diagnostic` is explanatory
metadata only. Neither field can override `geometry_consistent`.

Cases retain the source SHA, native integer PTS, rational timebase, pixel hash,
channel, epoch witnesses, reader output and rejection reasons. Case IDs exclude
epoch to find repeated pixels again; occurrences retain their acquisition
identity and are not joined into continuous evidence. Separate input corpora
remain separate acquisitions. Result ROI proposal failures are distinguished
from an unreadable OCR result with a proposed region. Text accepted while
geometry is unknown is explicitly categorized, not counted as a valid event.

The deterministic review queue is capped at 24 cases, rotates across sources,
and selects representatives by channel/reason strata. It is targeted development
triage, not independent discovery, a complete temporal review, or qualification
GT. Missing image paths are not queued. The corpus hashes the input documents;
it does not certify image bytes or a decoder. Asset verification remains with
the existing Native acquisition/review tools before viewing or confirming a case.
All labels start UNKNOWN; raw predictions never become human labels. Unobserved
rows and undetected purchase displays are not negative examples.

Outputs must be private and new; overwrites, unregistered/evaluation sources,
mixed declared identities, changed inputs and duplicate input paths are rejected.
Existing GT, allocations and previous evidence files are not rewritten. Keep the
corpus, queue, profile, images and individual PTS outside Git and Git LFS.

## Top-region diagnostic experiment

`hud_scope_structure.top_scope` reuses the existing oriented edge measure on
three disjoint tiles of a frozen top-bar reference at the expected location.
Each tile must retain at least 32 reference edges and score at least 0.90; the
parent must pass the existing non-generic structure guard. It performs no
alignment, scale search, template fitting, OCR, player/state inference or reader
fallback. Missing structure stays UNKNOWN.

The result may explain why a top region is visible while bottom HUD anchors are
absent. It cannot authorize full calibration, certify a Result/Score/Timer value,
or feed Lifecycle promotion. Real development samples show that it also rejects
many previously supported frames. It is a triage diagnostic only; it is not a
replacement Matcher, Profile, ownership check or production calibration policy.

## Opt-in Round component recognition

`outline_mask` selects long straight reference strokes with fixed Hough
parameters (length 6% of reference width, vote threshold 4%, gap 0.5%, five-pixel
band intersected with the frozen mask). It never uses the observed image or
predicted Score/Result to choose the reference pixels. This removes dynamic
glyph interiors from the structure comparison while keeping the existing
three-tile, 32-edge and 0.90 acceptance conditions.

The new `component_geometry` producer checks actual native BGR pixel hashes,
the reference-set fingerprint, profile/layout/bank identities and reference
resolution. It reruns the existing Result title-region selector and verifies
the selected crop hash before supporting the Result ROI. Score, Timer and
Result receive separate support flags. A supported top outline alone cannot
authorize a Result region or supply an unread OCR value.
The reader-profile digest must bind the effective configuration, including
explicit preprocessing overrides and asset fingerprints, not just its parent
configuration file. Reader outputs are also hashed into each frame receipt.

The offline Round transition/lifecycle assemblers may opt in through the
explicit `component_geometry` receipt. They validate its frame/epoch hashes,
asset bindings, digest, tile evidence and role consistency. Profile changes
inside an acquisition are rejected. The legacy `scope_diagnostic` field cannot
opt in. Existing global-only evidence retains its original behavior; its
`geometry_consistent` flag is never rewritten. Component support does not
authorize player ownership, full HUD geometry, internal event timing or any
Production End/Start. The current-frame readers, confidence thresholds, native
continuity, Score persistence, word-direction and multiple-evidence gates still
apply. Receipts are reproducible diagnostic provenance, not signed GT or
qualification; the caller must retain the actual source and frozen assets.

For each change freeze sources, sample-selection policy, reference/profile and
input hashes before comparison. Report the four existing lifecycle regressions
on identical observations separately from newly acquired samples. New fixed-grid
samples without an End candidate are unlabelled, not proven natural negatives.
Compare semantic correctness only where independently reviewed. Source visual
continuity, internal End/Start and qualification remain unverified.
