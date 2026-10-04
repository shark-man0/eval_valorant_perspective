# Spectator sparse-edge absence review

Decision: `CHANGE REPRESENTATION` for Spectator checked-absence evidence only, after a separate frozen reserved stress holdout and actual-runtime parity. Ability's representation decision remains `NEED MORE EVIDENCE`; no Ability implementation changes are included. The prior diagnostic commit rejected incomplete candidates before implementing the bounded contract below.

## Reproducibility

Starting HEAD: `d04eef714f172ec609d10d1bf59b9c6a53043410`. Source analyzer for current clean E2E: `5ed3b3d5f53e24c8cb9e902b30b6d5cfa958a3cf`. This phase starts clean; diagnosis adds scripts/tests/docs only. Controlled native comparisons use the earlier 4,730-observation population, not frame indices from the new 4,009-observation adaptive run.

Video SHA256: `71d58558559d6f578433ce9f234bf176f76fd5a86657dbfe3eba1e7d36136b06`. Private Report-enabled profile fingerprint: `2bdae7b5358f79ab8130e8c4a125ff3f5a6b83fe7ffe7b79c67bcf52d41c0383`. Layout SHA256: `a3678bcd9df35d0932ae0e69495eb5b87a3ab40e9c988560d502a9507d59eef1`. All prior HP/Ability/Weapon/Spectator sections and assets remain unchanged.

`python scripts/diagnose_spectator_absence.py PRIVATE_CROP_MANIFEST AGGREGATE_OUTPUT` reproduces the joint contrast/blur/compression candidate comparisons against this analyzer's actual detector. The private manifest has exactly portrait_training, portrait_holdout and ordinary_absence path arrays; decoded-pixel duplicates across portrait splits reject. Output contains aggregate counts and manifest hash, no paths, images, frame IDs or timestamps. Manual crop classifications are diagnostic annotations, never production evidence. The additional stress experiment applies edge strips covering 10%/25% of each side, bounded one/two-pixel shifts and resampling factors 0.75/0.5, each at contrast scales 1/0.5/0.25/0.2/0.15. Image mutations provide counterfactual safety tests, not evidence that these mutations actually occurred in the recording.

## Mechanism

The existing local detector can call a visibly faded portrait absent whenever fixed Canny 60/150 edges occupy at most 8% of the patch. Mean/variance/sharpness/acutance can still pass its observability checks. Thus sparse edges are not sufficient evidence of portrait absence. Brightness-preserving contrast changes are different from existing tests that darken the entire crop and fail mean checks. This diagnosis does not infer a portrait from past frames or recognize any Agent.

Twenty-four appearance-diverse actual portrait crops were independently pixel-reviewed. The initial 384 mutations produce 35 erroneous checked absences; a raw partial-topology veto fixes only seven. Joint contrast/blur/JPEG mutations produce 141 errors in 1,512 cases. A further 1,920 partial-occlusion/shift/resampling cases produce 536 errors. These counts share source crops and are not independent statistical trials.

## Candidate comparisons

Every candidate only vetoes an existing checked absence into UNKNOWN; none promotes normalized pixels to presence. Existing mean, clipping, sharpness and acutance guards precede it. Constants are inherited from existing presence/absence measurements, rather than fitted to GT or timestamps.

| Diagnostic candidate | Joint errors remaining / 1,512 | Stress errors remaining / 1,920 | Lost baseline live after Report / 137 | Lost scene-only opportunities / 18 |
|---|---:|---:|---:|---:|
| Existing sparse-edge absence | 141 | 536 | 0 | 0 |
| Require contrast 35 plus raw partial topology | 0 in initial 384-case check | Not evaluated | 131 | 17 |
| Normalize to std35; veto edge density >0.08 | 0 | 0 | 24 | 4 |
| Normalize; require 13 occupied cells, 10 components and 8 direction bins | 0 | 145 | 0 | 0 |
| Normalize; require density >0.08 and 8 direction bins | 0 | 0 | 0 | 0 |

The blanket contrast floor is rejected for substantial positive loss. The full-topology condition is rejected because visible partially obscured portraits fail its spatial population criterion. All 54 density-veto native cases were independently reviewed in their full-frame context and configured icon ROI: none shows a flat portrait, all show rendered world/scene pixels, including some nearby 3D effects/characters. The 24 baseline losses are therefore real opportunity losses, not demonstrated safety corrections.

The single-phase direction candidate changes only one of 449 measured native absences to UNKNOWN, and loses neither 137 baseline post-Report live observations nor 18 scene-only opportunities. The latter opportunities remain counterfactual; the global scene-detail context veto is unchanged in production.

## Independent development holdout and falsification

Fifteen manually confirmed portrait crops from earlier source blocks have zero decoded-pixel hash overlap with the 24 late-block development crops. They are from the same recording and do not constitute cross-recording validation. Frozen single-phase orientation produces zero errors in 945 joint mutations, but one error in 1,200 stress mutations. The failure retains a visibly faint face under a bottom-quarter occlusion; it must not be called absent. This candidate is not adopted.

The failed normalized histogram has one bin at 4.98%, just under the unchanged 5% orientation-population requirement. Rotating the histogram bin origin by half its 45-degree width yields all eight populated bins, with minimum 5.55%. This is evidence of quantization-boundary instability, not grounds to lower 5% to the observed value. A two-phase histogram (origins 0 and 22.5 degrees) preserves the eight-bin/5% condition and uses either complete phase only to veto absence. It fixes the failure and retains all previously measured live opportunities, but the fifteen crops are now development evidence. A newly reserved, pixel-reviewed holdout is required before adoption; further failures must be investigated, not recast as unobservable.

## Report integration checkpoint

Clean E2E at analyzer `5ed3b3d5f53e24c8cb9e902b30b6d5cfa958a3cf` records git_is_dirty=false: 22 passed / 56 failed / 4 not evaluated; negative assertions 20 passed / 0 failed. HUD observations are 4,009: live 138, Spectator 336, remote 33, buy 1, unknown 3,501. Adaptive sample count differs from baseline 4,730, so raw state counts are not controlled recall comparisons.

An independent audit joins all 138 live observations to their actual current-run extracted frames in private diagnostics: zero missing frames; frozen production Report witness accepts 0/138 (all non-accepts emit present=None), scores 0.000–0.213, median 0.101. The highest-scoring representative of each of 21 time-contiguous runs was pixel-inspected; none contains visible Report UI. This bounded audit does not prove universal Report absence. Both old and current traces contain zero player_death events, so temporal death-event changes cannot be measured in this recording.

## Diagnostic phase safety and next action (completed)

HP + Ability + Weapon + checked Spectator exclusion and threshold 0.90 are unchanged. Normalization can only withhold absence; it cannot establish live identity, clear Report evidence, prove self-HUD loss, use a timestamp/state/Agent oracle or carry state between frames. Buy close-X, buy grid, map and flash safeguards remain unchanged. Raw crops/video/reference assets and per-frame dumps stay private. Candidate support remains one-recording evidence.

The diagnostic phase selected reserved two-phase holdout, current-frame runtime parity and synthetic damaged-icon regression as its next checks. These are completed in the adopted contract below. Production changes still require full/static checks and committed-source Clean E2E.

Verification for this diagnostic commit: pytest 755 passed / 2 existing skips; Ruff src/tests/scripts passes; mypy 84 source files passes; diff check passes. Six new diagnostic tests cover no positive promotion, sparse directional-world retention, geometry rejection, aggregate privacy, exact-pixel split leakage and oracle-field rejection.


## Adopted bounded contract

A newly reserved sixteen-portrait set was independently pixel-reviewed before evaluation. It has zero decoded-crop hash overlap with development twenty-four and the previous fifteen. It is still one-video, same-picture/shop-episode evidence, not an independent episode/recording holdout. The frozen two-phase direction veto leaves zero false absences among 1,008 joint mutations (legacy 119) and 1,280 stress mutations (legacy 449). No constants are adjusted after this evaluation.

The implementation runs only in the existing sparse-edge checked-absence branch, after all original local observability/geometry/clipping/acutance guards. Raw partial topology (ten components and eight populated direction bins) or residual normalized edges with eight populated direction bins at either fixed origin 0/22.5 degrees withhold absence into UNKNOWN. The normalization floor remains the existing presence std35; Canny remains 60/150; density boundary remains 0.08; every orientation bin still needs five percent support. Positive presence thresholds and behavior are unchanged. The two bin origins address a measured 4.98%/5.55% boundary artifact without lowering the population threshold.

Actual production detector and frozen pre-change detector plus independent diagnostic candidate agree on every checked/present/reason decision across 8,833 cases: development training 3,432, first development holdout 2,145, reserved holdout 2,288, native absences 449 and native presences 519; zero mismatches. Across 7,865 portrait mutations, legacy errors are 1,799 and the guard leaves zero. These are correlated counterfactual tests, not a cross-recording false-positive estimate.

The center-scene scene_detail_collapse hint is removed only from the dedicated icon detector's obscuration context. It is still computed and consumed elsewhere in the scene/classifier pipeline. Direct local observability checks continue to reject low-information, clipped, blurred and ambiguous slots. Every buy-grid, close-X, map, flash, luminance-spike and visual-transition veto remains. Legacy non-dedicated panel detection is unchanged. The additional Report witness remains active; an actual runtime replay of the same twenty-one reviewed opportunities produces eighteen live and three rejected competing-evidence outcomes. The eighteen are evidence-backed opportunities rather than forced UNKNOWN promotions; full adaptive run effects require the committed-source Clean E2E.

Eleven synthetic regression cases use the existing abstract icon fixture, not a private image: mean-preserving fades with partial occlusion stay UNKNOWN and cannot release live_identity, world rectangles retain checked absence, full abstract presence remains unchanged, content outside the configured slot is irrelevant, and buy/map/flash/transition vetoes continue to reject. Existing HP/Ability/Weapon/Spectator/Report tests are unchanged. Full/static checks and Clean E2E results are recorded separately after the implementation commit.

Production verification before commit: pytest 766 passed / 2 existing skips; Ruff src/tests/scripts passes; mypy 84 source files passes; diff check passes. The 47 targeted Spectator/icon/diagnostic cases pass. Clean E2E is run only after this implementation commit with an empty worktree; its generated report is a separate commit.


## Completed committed-source Clean E2E

Analyzer `0972db4db955ba659bbcc9be3bdea9097c00ec76` was run with an empty `git status --porcelain`; metadata records `git_is_dirty=false`. Generated reports are isolated in commit `9d4309278e18a1af6a7827dbf70629f794d8f0cb`. Results: 22 passed / 56 failed / 4 not evaluated; negative assertions 20 passed / 0 failed. The 4,081 adaptive HUD observations comprise live 166, Spectator 335, remote 33, buy 1 and unknown 3,546. Visual eligibility is mechanics 166 / world 155. No numeric/text readers were configured; all thirteen audited value fields remain empty, so this identity improvement does not establish downstream facts/events completeness.

A controlled comparison shares 3,942 rounded-millisecond observations with the previous 4,009-observation Report-only run. All 138 earlier live observations remain live; eighteen shared non-live observations become live; zero shared live observations become non-live. All 156 paired live full-image hashes match exactly. Ten further live observations are newly sampled and have no paired counterpart; they are not counted as demonstrated recovery. These comparisons separate current-image behavior from changes in adaptive sampling.

All 166 live images are joined without missing frames and independently replayed against the frozen Report witness: accepts 0/166; score range 0 to 0.212728, median 0.106195. The maximum-Report-score representative of each of 31 contiguous live runs was visually reviewed: 31 self first-person HUD scenes, zero visible Report overlays, zero flat Spectator portraits. This bounded review is not universal ground truth. Private crops, frame identifiers and timestamps stay outside Git.

Decision remains CHANGE REPRESENTATION for the bounded Spectator absence veto only. Ability remains NEED MORE EVIDENCE. The next autonomous phase measures value-reader completeness and image-only glyph recognition while preserving all identity contracts.
