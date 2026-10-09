# R1 scene continuity: search-range hypothesis rejected

## Problem

The frozen reviewed-world reference method failed positive holdout qualification:0of30adjacent links were supported. A plausible explanation was crop-local LK's restricted destination search. This follow-up tests whether searching across all existing non-UI crops resolves that limitation, before adding reference poses or changing production policy.

Target upstream assertions remain `GT-R1-ROUND-START`, `GT-R1-ROUND-END`, `GT-R2-ROUND-START` and related lifecycle/count/ordering assertions. No canonical status change is inferred from diagnostic image support. HEAD remains `0a606a0a3edb19ba4cd10d8007c2d045c39b2006`.

## Evidence

The comparison uses the same four reviewed image references and all96existing native frames:30R1,30R2 and36previously reserved images. Every adjacent link within each archive is retained:29+29+30=88. No video decode, source modification, FPS reduction or new ground truth is introduced. Source video/PNG/pixel/report/code hashes are bound and terminally verified. The previous36-frameholdout is **development for this redesign**, never its qualification set.

Image matching reads no timer, phase, PTS, expected values or round IDs. PTS is checked only by the orchestration for native ordering; the function receives grayscale arrays and explicit crops. Timer/top-clock band and padded phase/result region cannot be search crops. Results are [comparison measurements](../e2e_reports/match_001/scene_patch_search_development.json) and [rejection stages](../e2e_reports/match_001/scene_patch_search_rejections.json).

## Competing hypotheses

1. Search range alone explains poor transfer: reference features moved into another allowed background crop.
2. Repeated wall textures, changing scale/appearance and foreground/occlusion prevent unambiguous reference correspondence even with wider search.
3. Unsupported links are content discontinuities.

The comparison **rejects hypothesis1 as a sufficient remedy**. It supports ambiguity/appearance limitations in hypothesis2, without quantifying their individual causal shares. Hypothesis3 remains unproven: failure to find a unique patch is not cut evidence.

## Independent image evidence

Reference corners supply reviewed15×15world patches. Each patch is searched independently inside each allowed current-image crop at NCC≥0.90. A second distinct peak≥0.90, outside a2pxneighbourhood of the best position, or qualified peaks in multiple search crops causes abstention. Accepted matches require reciprocal search back to the reference with≤1pxerror. Matching patches then require the existing2pxpartial-affine RANSAC and≥90%inlier coherence for shared-link support. At least three reviewed regions and spatial cells spanning two rows/two columns are needed at both source endpoints. No threshold was lowered; these are exploratory descriptive checks, not a production policy.

For existing reference16,114patches are considered in four explanatory poses:

| Pose | Accepted patches | Forward no NCC-qualified peak | Forward ambiguous second peak | Other rejection |
| --- | ---: | ---: | ---: | ---: |
| Critical timer-transition image | 22 | 2 | 86 | 4 |
| Earlier R1 pose | 1 | 87 | 20 | 6 |
| Returning R1 pose | 3 | 27 | 76 | 8 |
| Later R1 pose | 4 | 39 | 63 | 8 |

The critical image still has distributed shared world evidence:22shared reference16features, minimum patch NCC0.901034. At the first subsequent stable display image,18shared features remain with minimum NCC0.910874. The displays themselves are not inputs to those matches.

A large fraction of the wall patches have multiple high-NCC locations. At the critical image,86/114(75.44%)are rejected for forward ambiguity despite the known visible scene continuity. In the early pose,87/114(76.32%)lack a qualifying peak. Thus wider crop search cannot by itself establish general world-reference coverage. Appearance/occlusion and repeated structure remain unresolved; weak uniqueness must not be overridden to force coverage.

## Continuity decision

The R1 critical-link conclusion remains: distributed image evidence favours a transient UI display change in a visibly continuous scene. This investigation does not establish uninterrupted gameplay time or exclude scene-preserving edits.

Reject the cross-crop search method as a production qualification remedy. R1development link coverage decreases26→19of29. R2remains0/29and all30former-holdout links remain unsupported. No reference/profile is adopted, no continuity token or lifecycle event is emitted, and unsupported images are not labelled cuts.

## Contract change

There is **no production contract change** in this follow-up. New diagnostic code exposes forward/reverse rejection stages. An optional rejection sink preserves all existing numeric match outputs; a test verifies exact equality with and without instrumentation. Pre-instrumentation helper/runner bytes are preserved in the private `scene-patch-search-20261009` archive with their SHA-derived filenames, so the comparison report's historical code binding remains reproducible.

The already implemented opt-in `transient_ui_transition` still requires genuine scene/UI qualification and trusted source producers. It retains every display, never special-cases2:25or1:39, and never exports player-owned facts without identity. Missing support, explicit content cuts, duplicate pixels and native PTS discontinuity remain vetoes. GT, thresholds, ownership, geometry, OCR, assertion/evaluator semantics and full sampler are untouched.

## Tests

**10new unit tests PASS(8.06sec)** cover cross-crop motion, exact excluded-pixel invariance, ambiguous repeated patches, unrelated views, duplicate similarity without authorization, invalid/protected crops, textureless references and unchanged outputs with rejection instrumentation. Ruff passes `src tests scripts/e2e` and all three new diagnostic scripts; `git diff --check` passes.

Production source hashes match the prior [holdout verification](../e2e_reports/match_001/scene_world_feature_holdout_verification.json), where204related tests and mypy102source files passed. These are selected/source verification results, not new canonical negative-assertion results. No full regression, sampled/full E2E or Windows runtime validation is claimed.

The96-framecomparison ran once to exit0 using a blocking completion wait; full measurement wall time157.137sec. Four rejection-stage poses use saved frames and add no source decoding. No qualified candidate exists to justify a canonical full run.

## Previous / Current / Delta

| Same input scope | Previous crop-local method | Current cross-crop search | Delta |
| --- | ---: | ---: | ---: |
| R1 descriptive supported links /29 | 26 | 19 | -7(-26.92%) |
| R2 descriptive supported links /29 | 0 | 0 | 0 |
| Former-holdout descriptive links /30 | 0 | 0 | 0 |
| Real new qualification / boundaries | 0/0 | 0/0 | 0/0 |
| Canonical PASS / FAIL / NE | Historical23/55/4 | Not rerun | Unmeasured |

The new ambiguity/reciprocal checks differ from crop-local LK, so a coverage delta is not an accuracy or safety comparison. Previous short method timing20.288sec covered60images; current157.137sec covers96images and wider matching. Their raw runtime subtraction is not a comparable speed delta. No E2E runtime result is introduced.

## Remaining blocker

Searching farther is insufficient; scene support needs distinctive image structure with qualified coverage under ordinary camera pose/appearance changes and foreground occlusion. The next design should use reviewed spatial feature structure or image-derived reference coverage, rather than relax ambiguity/NCC requirements or add GT-selected poses. New independently reserved positive/negative inputs are needed for any redesigned method; the consumed cohorts remain development.

Trusted positive UI disappearance and scene-only source producers are still missing. R2transfer and R1-end result-banner qualification remain separate blockers. Canonical round starts/ends, package separation and PASS gains are unproven. The82assertion matrix is unchanged; `NEG-R2-NO-ROUND-END` remains a historical PASS, not a newly validated result.
