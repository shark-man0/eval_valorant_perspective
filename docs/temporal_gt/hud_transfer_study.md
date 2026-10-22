# Offline HUD transfer study

`scripts/diagnostics/diagnose_hud_transfer.py` compares training-frozen reference
banks with the unchanged pixel NCC matcher and a separate structural diagnostic.
It imports no runtime acquisition pipeline, identity rules or event publisher.
`geometry_consistent` is an experimental diagnostic; `semantic_label` remains
UNKNOWN and `production_qualified` is always false. It cannot replace runtime
calibration or release Round End / Self Death events.

Freeze a private plan before decoding or looking at new results. Bind accepted
DEVELOPMENT sources through the existing private registry/review plan and append
Exposure with existing APIs. Exclude evaluation candidates. Record source SHA,
native integer PTS/rational timebase, acquisition epoch and encoded/pixel hashes.
Keep previous evidence immutable and verify source/profile/configuration hashes.
Use existing bounded `VideoService.native_window`; no new decoder is required.

The five-source study fixed 16 interior duration fractions per source (80 new
witnesses), without predictions or semantic selection. Even ordinals from the
first four sources generated references (32 images). Odd ordinals and all 16
images from the fifth source formed the 48 development checks. The old 85
witnesses were a separate regression set, never new reference input. Source five
was already exposed development data, **not** an independent holdout. Each window
was <=0.1 seconds, retaining only one witness; continuity remained UNVERIFIED.

Call the diagnostic API with training images only:

```python
bank, reference_stats = freeze_bank(training_images, layout, existing_profile_raw,
                                    new_private_asset_directory)
frozen = bank_fingerprint(bank)
# Freeze source/frame roles and persist reference/input hashes before this loop.
rows = [observe(image, layout, bank, reference_stats=reference_stats)
        for image in development_check_images]
assert bank_fingerprint(bank) == frozen
```

Reuse `development_sources`, `append_exposure`, private output checks and
`write_private` around this API. This module is a diagnostic component rather
than another source/GT registry. Asset writes are exclusive and private. It does
not export a loadable runtime Profile; no production configuration is modified.

Reference generation reuses persistent-edge/orientation masks and the existing
training-only observed-reference proposal. At most three references per anchor
are selected by additional non-self raw NCC coverage, requiring at least three
supporting training images. Single and multiple NCC methods share the same
training cohort, masks, search regions and unchanged >=0.90 NCC threshold.

The structural branch proposes locations using normalized binary edge
correlation, then requires existing bidirectional unsigned-orientation soft
coverage >=0.90 (>=32 reference edges). This is a separately fixed experimental
cutoff; it is not an equivalent NCC confidence or accuracy claim. No rescaling
or post-result threshold tuning is allowed. Static support is defined by the
training persistence mask, not semantic annotation of static HUD elements.

Every method still needs existing capture/resolution checks and three fresh
geometric inliers. Multiple high scores at inconsistent positions cannot bypass
these checks. Blank, random noise, large shifts, missing structure and resolution
mismatches must not become events or verified negatives. Unmodified scene labels
(Menu, Spectator, Death, HUD hidden, overlay) remain UNKNOWN without evidence.

Compare the frozen previous Profiles separately from methods trained on the new
cohort: reference-data changes and matcher changes are different experiments.
Report per-source/per-anchor support, reference-structure failure, missing
non-self NCC training support, observed-edge shortage,
structure mismatch, structure-supported NCC rejection and geometry rejection.
Generic edges are not proof of HUD presence. Pass the frozen generation stats
to distinguish absent reference structure from a structured proposal rejected
by training NCC support. Without those stats, a missing reference is UNKNOWN
(`reference_unavailable`), never an assertion that structure was absent. Record fit/replay time and process
peak RSS, source-five regressions and known-invalid transform challenges.

In the fixed study, frozen previous Profiles reproduced 18/85 and 19/85 but both
only reached 4/80 on the new uniform samples. New single/multiple NCC references
reached 12/85 and 12/85, with 9/48 each on development checks: multiple NCC helped
training only and did not establish more stable transfer. The structural
candidate reached 35/85 and 21/48; on source five it reached 6/17 old and 7/16 new,
versus previous observed-reference NCC 3/17 and 2/16. These are structural
consistency counts, not recognition accuracy or verified correct calibrations.

Retain the structural branch for further offline investigation only. Do not
adopt new NCC Profiles (old regressions remain), or connect the new Matcher to
production. Real false-calibration/crop/HUD-scale evidence and independent
semantic geometry validation remain missing. Round End additionally needs
compatible Score preprocessing, verified source continuity and qualified
lifecycle evidence; geometry counts alone cannot satisfy those contracts.

## Separating reference selection from matching

`freeze_bank(..., selection="structure", training_groups=source_groups)` is an
explicit offline alternative to the default NCC selector. It uses the same
training cohort and persistent mask, without calling the NCC medoid proposal or
raw NCC scoring. `persistent_structure` exposes only the existing mask-building
step; the default NCC branch retains its previous reference selection.

Structural candidates need at least 32 masked edges, at least three unsigned
orientation bins with eight pixels each, and four occupied cells in a 4x4 grid.
This rejects sparse, localized, and simple one/two-direction contours; it does
not establish that a complex contour is a HUD. Candidates require non-self
bidirectional structural support >=0.90 from at least three training frames
spanning at least two source groups. Selection greedily adds at least three
newly covered frames, then ranks by total support, non-self median similarity,
and earliest training index. At most three references are retained. Groups must
identify actual training sources, never arbitrarily split frames from one source.

Freeze thresholds, training membership, source groups, sampling, controls, and
implementation hashes before fitting. The structural selector and structural
matcher have separate roles; NCC >=0.90, the structural matcher, search regions,
capture checks, and geometry tolerances remain unchanged. Compare:

| Condition | Frozen reference selection | Matching |
|---|---|---|
| A | Previous NCC | NCC |
| B | Previous NCC | Structural diagnostic |
| C | Structural support | NCC |
| D | Structural support | Structural diagnostic |

Reuse the previous 32 training images; keep the known old85 and previous48
checks out of reference generation. A predeclared additional cohort uses eight
odd interior fractions `(2*i+1)/16` of each of five DEVELOPMENT sources, with no
replacement or prediction-based selection. These 40 witnesses are development
checks, not an independent holdout. Retain actual bounded native-frame
provenance and source continuity UNKNOWN/UNVERIFIED. Evaluation candidates are
excluded, and all private reference assets, frames, paths, timestamps, answers,
and detailed source identifiers remain outside Git.

Report reference-generation failure separately from observation failure. A
persistent mask is evidence of repeated edges, not proof of HUD presence.
Distinguish missing structure, inadequate NCC reference support, nonspecific
structure, inadequate cross-source structural support, matching rejection, and
geometry inconsistency. Record per-source/anchor outcomes, regressions, fit and
matching time, process peak RSS, and invalid-input controls. Deliberately copied
reference-shaped graphics are a semantic-risk probe: even matching coordinates
and high structure scores cannot qualify them as HUD. Automatic consistency
never becomes GT, a natural negative, a formal event, or production ownership.

The fixed comparison produced these geometry-consistency counts:

| Cohort | Images | A | B | C | D |
|---|---:|---:|---:|---:|---:|
| Known old regression | 85 | 12 | 35 | 11 | 52 |
| Known previous checks | 48 | 9 | 21 | 9 | 33 |
| Additional uniform checks | 40 | 4 | 10 | 6 | 19 |

The missing top-bar reference had persistent structure but at most one non-self
NCC supporter among 32 candidates, below the required three. Structural
selection retained two references with counterfactual NCC support of one and
zero; matching then supported that anchor in 132/173 checks (41 still failed).
Reference counts changed from timer/top-bar/HP/ability 1/0/1/3 to 1/2/1/2.
With structural matching fixed, B→D gained 17/12/9 cases with zero lost cases in
the three cohorts. On source five the counts were 6→10, 7→10, and 3→3. Source
five is exposed DEVELOPMENT, not independent qualification. With NCC matching
fixed, A→C lost one old-regression case, unchanged previous checks, and gained
two additional cases: structural selection is not a safe NCC-only replacement.

Nine invalid-input challenge families across ten inputs and four conditions
were all rejected (360 comparisons). These include simple/repeated background
contours, blank/noise, resolution changes, erasure, shifts, and inconsistent
anchor positions. A separate copied-reference graphics probe was accepted in
all 40 comparisons. This demonstrates a semantic limitation shared by all four
conditions, not a natural-negative accuracy measurement. No real
Menu/Spectator/Death state, HUD scale, crop variation, or true HUD coordinates
were independently qualified. Retain the structural selector only as a next
offline semantic-validation candidate; do not tune reference selection further
on these samples or adopt it in production.
