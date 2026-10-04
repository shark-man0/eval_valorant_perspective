# Ability identity follow-up

## Reproducibility

Starting HEAD: `1c5c30bd92b10655f1e629c408f9c246e5b774d1`. Previous diagnostics remain the baseline; this phase does not repeat the 258-frame runtime reproduction. Production source/profile and threshold 0.90 are unchanged. Training is the same 32 even crops, holdout the 32 odd crops. Diagnostic cohorts are the same 183 positives, 75 misses and 27 verified contextual negatives. Private images, frame indices, timestamps and learned image assets remain local.

Video SHA256: `71d58558559d6f578433ce9f234bf176f76fd5a86657dbfe3eba1e7d36136b06`. Original profile/reference hashes are recorded in `ability_identity_review.md`. Revised diagnostic-only reference pixels: `f7cab7109cc82a4b3110e82399964b4e3e6a94693a3d0e6f1ccdaabb683b5c01`; mask: `32b02b86f68bfe8c44d7191572b68a87740357a5323804356874b91ffe50db57`; support labels: `6dad4ea4abbbb92d1f54c6815bae1b0ef7baca6f707175e3d114de0109a6a616`.

## Why the original scaffold lost 24 positives

Reference-edge recall medians were 1.0 across all four groups. Only 2/24 lost and 1/21 visible unresolved frames had any group recall below 0.90. Precision failures were concentrated in group 4 for lost positives (14/24) and group 3 for unresolved misses (16/21). Median additional nonreference edges there were 28 and 30. This establishes an extractor/clutter failure mode; it does not prove cooldown, charge, icon fill or animation semantics. Raw temporal std>20 covered every pixel in all four groups, making that proxy incapable of separating changing world background from dynamic HUD pixels. Low variance is not used to infer observability.

## Training-only revised candidate R

Freeze the existing four training-derived support groups. Fill outside each group before top-hat/contrast processing using existing `isolated_features`; learn the median training reference and oriented ridge mask from training only, retaining recurrent pixels at the already defined diagnostic 0.60 recurrence cutoff. Existing `feature_score` requires every group to satisfy oriented recall and nearby-edge precision >=0.90. Evaluation/negative cohorts do not choose masks, groups or thresholds. This is offline code, not a newly enabled production matcher.

| Representation | Existing positives retained /183 | Missing recovered /75 | Context negative raw accepts /27 | Train /32 | Holdout /32 |
|---|---:|---:|---:|---:|---:|
| Current fixed template |183|0|13|21|24|
| Previous raw-Canny scaffold |159|42|17|26|24|
| Masked fixed-template ablation |164|23|14|21|23|
| Training-only isolated oriented R |173|60|15|25|27|

R rescues 14/24 formerly lost positives and 18/21 formerly visible unresolved misses. It retains all previously retained 159 positives and recovers the prior 42 scaffold-supported misses. All 12 manually no-visible-HUD cases reject; eight score zero and four have low nonzero matches.

## Remaining observable discrepancies

The 10 remaining positive losses and 3 visible unresolved misses have nearby ridge evidence in all four groups. They are not whole-group absence. Lost positives fail group 4 in seven frames, group 3 in three, and group 2 in one (overlap). Visible unresolved frames fail groups 3 and 4 in two frames each (overlap). These are localized segment/endpoint/orientation differences and, sometimes, extra high-contrast ridges. Crops alone cannot determine whether the underlying cause is dynamic pedestal/fill behavior or background/foreground clutter; that semantic mechanism remains unproven. Observable mismatch is not relabelled as unobservable.

## Independent support and invariance evidence

The four reference populations are 120/119/116/136 bright ridge pixels. Training recurrence minima are .875/.875/.8125/.8125; medians .875/.90625/.90625/.875. All features have the same horizontal-ridge normal bin. Spatial separation exists, but four parallel contours do not establish the two-dimensional structural diversity expected by the HP matcher. Existing loader/matcher role constraints are left intact.

| Training-reference intervention | Old scaffold score | R score |
|---|---:|---:|
|reference|1.000000|1.000000|
|outside_support_noise|0.761745|1.000000|
|outside_support_inversion|0.804348|1.000000|
|global_affine_luminance|1.000000|1.000000|
|contrast_polarity_inversion|1.000000|0.508475|
|one_group_removed|0.000000|0.000000|
|one_group_only|0.000000|0.000000|
|dynamic_content_only_no_groups|0.013216|0.000000|
|flat_no_structure|0.000000|0.000000|
|arbitrary_texture|0.531469|0.625532|
|one_group_vertical_contradiction|0.752896|0.158333|

The old unsigned Canny representation changes score when excluded pixels change and accepts contrast-polarity inversion. R isolates excluded pixels and rejects inverted/contradictory structure, missing groups, one group only, flat/no-HUD evidence and random texture. These interventions establish feature isolation and selected failure contracts; they do not establish real dynamic-state invariance inside support groups.

## Cause breakdown for the original 75 misses

| Diagnostic primary category |Count|Percent|
|---|---:|---:|
|Fixed-reference disagreement with scaffold support|42|56.0%|
|Raw edge clutter resolved by isolation|18|24.0%|
|Localized oriented/partial contour mismatch|3|4.0%|
|No visible Ability HUD|12|16.0%|

These categories identify measured representation failure modes. They do not assign unobserved animation, Ability availability, agent identity or reference-generation semantics. The previous 21 unresolved are now split into 18 extractor/clutter cases and 3 observable contour discrepancies.

## Negative separation

Current/R raw acceptance is 13/27 versus 15/27. The frozen full-gate R replay is 0/27; every one is stopped by unverified Spectator exclusion. Therefore this replay establishes only preservation of those gates, not candidate-level negative separation. The added raw accepts are not automatically final false positives, but the candidate cannot claim improved separation. Additional current-run controls are being classified from pixels; unknown visible-HUD frames are reserved rather than labelled negative from state names alone.

## Decision and autonomous continuation

**NEED MORE EVIDENCE**. No production Ability change: 10 existing positives are still lost, dynamic-state invariance inside support is unproven, and intrinsic hard-negative separation is not established. Threshold relaxation is not considered. The next evidence steps are bounded temporal neighborhoods of the remaining 13 cases and verified expanded context controls.

The pipeline has a larger independently measurable blocker: among 4,730 current clean-E2E observations, 4,387 live-identity decisions stop at unchecked Spectator exclusion; 2,786 icon results are vetoed as obscured, versus only 182 structure insufficiencies once absence is checked. The exact pre-template feature path reproduces reason counts. Obscuration sources are 1,657 global-feature-only, 572 global-feature plus menu-close-X, and 557 menu-close-X-only. Next phase audits whether those hints actually obscure the local portrait ROI, with diagnostic-only counterfactual replay and image verification. It will not turn uncertainty into absence or bypass exclusion.

## Verification

Offline candidate CLI reproduces the private-probe aggregate counts and exposes no threshold override. Six contract tests pass. Ruff (`src tests scripts`), mypy (`src`, 83 files) and diff check pass. Initial full pytest used the wrong locale and omitted the external pack: 718 passed, two CP932 decode failures, five skipped. Reverification with the established UTF-8 and validation-pack environment: **723 passed /2 skipped**, 273.66 seconds. Existing HP/Weapon/Spectator tests are unchanged. Production is unchanged, so no new Clean E2E is run for this diagnostic-only phase.

## Bounded temporal follow-up

All 13 remaining cases have three preceding and three following canonical cached frames within 0.25 seconds; every center score matches exactly (zero error). Across their 15 failing support groups, five are center-only failures with all sampled neighbors passing that group, and ten have mixed neighboring scores; none has all sampled neighbors failing that group. The other 37 group-center checks pass. This establishes short-term feature instability; it does not prove Ability state semantics or authorize carrying a positive from another frame. Detailed timestamps and sequences remain private.

At the whole-frame level, 2/13 centers have all six neighbors passing, 11/13 have mixed neighbors, and none have all six failing. Across 78 neighbor observations, 59 pass R. Twelve of the 15 failing group instances have weak endpoints; matched displacement remains within 1 px rather than a coherent translated scaffold. Median pixel flow is 0.049 px in support versus 0.062 px nearby, and mean grayscale-difference medians are 4.66 versus 7.25 levels. These are feature-stability measurements, not permission for temporal positive persistence.
