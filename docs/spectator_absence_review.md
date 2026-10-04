# Spectator sparse-edge absence review

Decision: `NEED MORE EVIDENCE` for a new Spectator absence crosscheck. No Spectator production change is made in this diagnostic commit. The next experiment is a newly reserved portrait holdout for a frozen two-phase orientation representation; this decision does not end work.

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

## Safety and next action

HP + Ability + Weapon + checked Spectator exclusion and threshold 0.90 are unchanged. Normalization can only withhold absence; it cannot establish live identity, clear Report evidence, prove self-HUD loss, use a timestamp/state/Agent oracle or carry state between frames. Buy close-X, buy grid, map and flash safeguards remain unchanged. Raw crops/video/reference assets and per-frame dumps stay private. Candidate support remains one-recording evidence.

Next: reserved two-phase holdout, current-frame runtime parity and synthetic damaged-icon regression. Only after these checks may an absence-only guard and narrowly localized scene-detail context handling be implemented; production changes must receive full/static checks and committed-source Clean E2E.

Verification for this diagnostic commit: pytest 755 passed / 2 existing skips; Ruff src/tests/scripts passes; mypy 84 source files passes; diff check passes. Six new diagnostic tests cover no positive promotion, sparse directional-world retention, geometry rejection, aggregate privacy, exact-pixel split leakage and oracle-field rejection.
