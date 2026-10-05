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

## Frozen long-line scaffold follow-up

The three previously frozen training images supplied persistent horizontal and
vertical long-line masks, split into H1/V1/H2/V2 groups. Canny (60/150, L2) was
followed by 80-pixel oriented morphological opening. All four groups supported
all three training images. Candidate configuration was frozen before challenge
inspection; its SHA is
`0bf5ba57f9a098e96cf324b2259098a6c6a1e460a875307007e397a6ffa59487`.
The diagnostic rule required three of four groups, both orientations and the
unchanged 0.90 close-anchor NCC. It was never installed in production.

On the same secondary challenge (68 rows, 66 unique images), the locked
appearance-only ledger identifies six visible menus and 60 other appearances.
Only **2/6** menus survive scaffold plus NCC; **0/60** other appearances accept.
All 11 additional synthetic X-insertion accepts are rejected by the scaffold.
This is a useful counterfactual improvement but an unacceptable loss of four
existing menu controls. Exactly two unique images support three groups; none
supports all four. The original per-image predicates and corrected aggregate
join agree. Images, references, masks and per-frame dumps remain private.

| Representation | Visible menus retained | Other appearances accepted | Synthetic X-only additional accepts |
| --- | ---: | ---: | ---: |
| Coarse grid + frozen NCC | 6/6 | 0/60 | 11 |
| Long-line scaffold + frozen NCC | 2/6 | 0/60 | 0 |

For unique images, H1/H2/V1/V2 pass in 2/2/4/3 cases respectively. Five V1
failures and one H2 failure have extracted long-line responses elsewhere inside
their group bounds. Low response counts elsewhere are **extractor insufficiency**,
not proof that visible UI structure is absent or unobservable.

The interior ablation replaced 85.348% of grid pixels outside a 41-pixel support
halo. It left all training metrics unchanged, but held-out group metrics remain
unchanged only on H1 67/68, H2 68/68, V1 63/68 and V2 60/68 rows. These are
measured interventions, **not a proved dynamic-pixel exclusion contract**.
An 80-pixel opening composes erosion and dilation, and Canny hysteresis links
edges beyond a local derivative footprint. The chosen 41-pixel halo has not been
proved to bound these dependencies. An explicit dependency audit is the next
experiment; ablation changes must not be attributed to glyphs or visual states
until that mechanism is separated.

**NEED MORE EVIDENCE**: reject adoption of this frozen candidate. Preserve its
results, investigate the extraction contract, and test a finite local alternative
with verified footprints. Any revised candidate evaluated on these now-inspected
images is a development experiment, not fresh holdout qualification. Single
recording and nearby menu occurrences still limit generalization. No threshold,
identity safety gate or production behavior changed. Aggregate evidence is in
`buy_grid_scaffold_evidence_v1.json`; prior clean tests and E2E remain applicable
to the unchanged production code.

### Dependency audit result

Synthetic metamorphic tests establish that the 41-pixel halo is insufficient.
For OpenCV's default even 80-pixel kernel, anchor 40 gives single-stage
source-to-output influence offsets [-39,+40], composing to [-78,+80] for
erosion followed by dilation. Removing one pixel from an 80-pixel line changes
opened output 80 pixels away. This is asymmetric; the usual symmetric 79-pixel
bound would be incorrect for this implementation's default even anchor.
The vertical case reproduces the same influence. In the actual grayscale ->
Canny -> opening sequence a one-pixel change alters output 58 pixels away.
Removing a strong Canny seed 250 pixels away also removes a weak response.

These counterexamples invalidate the proposed exclusion guarantee; they do
not prove the mechanism of any individual real-image miss. Perimeter trimming
does not bound dependencies of internal support pixels. Frozen v1 configuration,
pixel scores and prior private audit are preserved. The corrected private audit
hash is `b3242fea386fecda3134743fcc6ebc86d6a1bc4c8fa77a5a6b524ebca4f775b2`.
Shared aggregate proof is `buy_kernel_dependency_evidence_v2.json`; reproducible
synthetic tests are `tests/unit/test_diagnostic_buy_kernel_contract.py`.

The selected next experiment uses original-image local Sobel derivatives with
full 3x3 source-footprint validation, excluding hysteresis. Any subsequent
aggregation must validate its complete composed dependency footprint. Training
supports will be frozen before revised development scoring. The same 68 images
cannot supply fresh holdout qualification after their inspection. No production
detector, identity gate or threshold is modified.

### Verification of this diagnostic phase

Full pytest: 921 passed / 5 skipped in 267.54 seconds. The invocation omitted
the external-pack environment variable; the three pack-dependent skips were
then evaluated explicitly with the supplied `VALORANT_E2E_PACK`. The three pack
integration modules passed all five tests (including two already passed in the
full suite). Thus 924 distinct tests passed, with only the two existing optional
sibling-trace/source-anchor fixtures unevaluated. Four new synthetic dependency
tests also pass individually. Ruff (`src tests scripts`), mypy (`src`, 86 files),
JSON privacy/consistency checks and diff check pass.

No production change was made. The authoritative clean adaptive E2E remains
analyzer 5b7: 22 passed / 56 failed / 4 not evaluated, negative assertions
20 passed / 0 failed, `git_is_dirty=false`. No new E2E was run for this
diagnostic-only phase. Fixed manifests and baseline populations remain unchanged.

## Finite-local Sobel and topology diagnosis

A separate frozen diagnostic removes Canny and morphological opening. It
computes original-image 3x3 Sobel gradients, retaining only centers whose entire
source footprint is inside that group's mask, with no black-fill gradients.
Gradient magnitude 100 and orientation dominance 1.5 were frozen before development
scoring. Training-derived response/component minima and the three-of-four,
both-orientations diagnostic rule remained fixed. These are descriptive feature
tests, not production identity scores or a lowering of the 0.90 identity gate.

The source masks cover 11,876 of 1,000,500 ROI pixels (1.187%); 9,076 centers
have valid derivative footprints. Outside-mask randomization leaves every one
of the 12 training frame/group measurements exactly unchanged. The evaluation
scorer hash-binds the interval geometry and reproduces all training measurements;
68 development frame metrics and decisions remain identical after that binding
was made explicit. Candidate config SHA is
`7e94a91cadbfc88906a6f79406bff60ed58f0d8b706a6d3ea571c5fe8706ead9`.

| Frozen diagnostic representation | Visible menus retained | Other appearances accepted |
| --- | ---: | ---: |
| Canny plus long opening | 2/6 | 0/60 |
| Finite local Sobel, unshifted | 3/6 | 0/60 |
| Finite local Sobel, best common bounded offset | 6/6 | 0/60 |

The three unshifted misses fail response-pixel minima, not component minima.
H1 response counts are 337/347/342 against training minimum 348; one missed
V1 count is 354 against 398. All retain measured oriented responses, so this
does not prove physical border absence. Applying a single common translation
to all groups, not independent group search, evaluates all 25 offsets in the
[-2,2] window. Four offsets tie: (-2,-1), (-2,-2), (1,-1), (2,-1). Each retains
the original three supports and recovers the three misses with no other-image
accepts. Ties and boundary offsets establish alignment sensitivity, not a unique
correction. No production coordinate or acceptance threshold changes.

Count support still fails a topology contract. In synthetic constant-background
inputs, period-4 and period-6 normal stripes confined to the source bands pass
the unchanged rule, with H1/V1/H2/V2 patterns 1110 and 1101. They replace single
border structure with multiple parallel edges. Period-2 checker patterns,
tangential patterns, random texture and a single-edge scene reject. The period-2
case alone would miss the risk because central Sobel differences cancel that
alternation. These are synthetic predicate counterexamples, not an observed
real-world false-positive rate and not production classifier accepts.

**NEED MORE EVIDENCE**: do not adopt this representation, including the aligned
variant. Independent pixel footprints are established; border identity,
observable contradiction rejection and dynamic-state invariance are not. H2/V2
include green availability-like borders. All three training images are from one
recording/setup; mask-interior glyph or dynamic content remains possible. The
68 inspected challenge images are development data, not new holdout evidence.

The next diagnostic is already selected: freeze training-only border topology
and normal-direction edge profiles, then test both real development images and
these synthetic contradictions. Observable shape contradictions cannot be
ignored by a three-of-four count vote. In parallel, the next pipeline blocker
audit covers the 234 unchecked/ambiguous Spectator exclusions among the 301
canonical snapshots with all three identity structures. These are opportunities
for further measurement, not live labels, and the exclusion gate remains intact.

This phase adds aggregate/docs only. Production and existing tests are unchanged;
the preceding full suite, external-pack rechecks, Ruff, mypy and clean 5b7 E2E
remain the applicable baseline. Shared numerical evidence is
`buy_finite_local_scaffold_evidence_v1.json`; private crops, masks, references,
per-image diagnostics and appearance ledgers remain local.

## Border profile topology and observability stress

Starting diagnostic HEAD: `c24ec31fc77cd0cdcdb53b192567455a5cf1c2e7`.
Production, profiles, thresholds and frozen replay manifests remain unchanged.
The preceding finite-local count probe accepted synthetic period-4/6 stripes;
the next diagnostic therefore compares normal-direction edge profiles rather
than just response populations. Eight segments use absolute original-image
Sobel profiles with valid derivative footprints. Three training images define
the normalized mean profile. A training-only common shift (+2,-1) increases
minimum pairwise cosine to .91636; all segments use that same frozen shift.
The cosine threshold stays .90. Any segment shape mismatch rejects the frame,
even when three other groups match. Signed profiles are forensic measurements,
not an additional acceptance path.

On the same previously inspected 68 development rows (66 unique), this shape
proxy retains 5/6 visible menu appearances and matches 0/60 other appearances.
It rejects all six synthetic scenes, including the stripe counterexamples.
This is improved topology sensitivity, not independent holdout qualification
or a safe detector. Its original observability predicate is only nonzero L2
profile norm and at least one valid center. That establishes a numerical
feature, not sufficient visible structure. Do not interpret the proxy's 60
other-image mismatches as 60 physically observable contradictions.

The separate frozen stress scales training contrast about gray128. At factors
.10 and .05, all 24 segment/frame cases at each factor (48 combined) still satisfy that nonzero predicate
and preserve cosine .956–1.000, while none retains oriented Sobel responses
at the frozen magnitude100/dominance1.5. Maximum mask-to-flank contrast is
only 7 and3 gray levels respectively. JPEG qualities95/70 do not establish
an observability safeguard. These are artificial counterexamples, not observed
UI alpha values or an estimate of real false-positive frequency. Shape
normalization must not conceal insufficient evidence.

The one visible-menu loss has a different mechanism. Its V1 segment retains
356 strong oriented responses; profile shape has additional later-bin energy.
Absolute/signed cosine at the frozen shift is .8988/.8769. A forensic common
bounded shift search reaches only .8992. Spatial phase/polarity mismatch is
supported; physical edge absence is not. Neither lowering .90 nor relabeling
this mismatch as unobservable is justified.

**NEED MORE EVIDENCE**. No production adoption. Training consists of three
frames from one recording, and H2/V2 still include availability-like green
borders. Agent independence, dynamic-state invariance and new holdout support
remain unproven. The next experiment freezes amplitude and spatial-support
qualification from training separately from normalized shape, then evaluates
the same development controls and weak/synthetic contradictions. This proceeds
in parallel with the higher-opportunity Spectator context audit; it does not
repeat the rejected count-only rule. Aggregate hashes and counts are in
`buy_border_profile_evidence_v1.json`; private profiles and crops remain local.

This aggregate/docs phase reran the full suite with the external validation pack:
**924 passed /2 skipped** in274.53 seconds. Ruff src/tests/scripts and mypy src
(86 files) pass. Existing optional trace-adapter/source-anchor fixtures account
for the two skips. No production change means no new adaptive Clean E2E is
required; the clean 5b7 result remains22/56/4 with negative20/0.
