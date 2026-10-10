# Reviewed projected-world appearance investigation

## Problem

The frozen camera cohort abstained on its first wall link despite94original identities spanning6regions. All fixed-coordinate cropped warps had valid fractions0.728940–0.848885, below the existing0.90floor. Camera motion can project valid source world outside the same current crop. This investigation tests whether those projected pixels remain independently reviewed world. Priority remains R1source evidence for lifecycle/package; no clock, score or boundary semantics enter the appearance method. Main is `03bfcbf945fbf3d7b04c54d80b3c5ff103475db0`.

## Evidence

The development pair has native PTS2.502669270833333and2.5193359375, separated by256ticks in1/15360. Video SHA256 is `71d58558559d6f578433ce9f234bf176f76fd5a86657dbfe3eba1e7d36136b06`. Both original1920×1080images were reviewed at the preceding checkpoint. The source population stays each original complete wall footprint; larger current wall domains were declared before measurement, within visible wall and outside phase/minimap/FPS/arms/knife. Their coordinates and source/code hashes are frozen in [the declaration](../e2e_reports/match_001/scene_projected_world_declaration.json). This exposed pair is development, not a new holdout.

A passive `dense_model_sink` exports the exact existing adjacent partial-affine matrix and retained world correspondences before the fixed-crop photometry fails. It does not alter fitting, points, random state, thresholds or tracker state. The new appearance diagnostic reuses that matrix; it never optimizes a transform against appearance scores. The original result dictionary matches the previous frozen report after JSON normalization.

## Competing hypotheses

- Retained feature geometry is insufficient at this link: contradicted by94original photometrically supported world identities across6regions and the unchanged existing transform's predicates.
- Same-coordinate crop boundaries exclude otherwise valid world pixels under camera motion: supported by the projected test.
- Arbitrarily wider crops establish world evidence: rejected. Source labels, current reviewed masks, excluded-pixel independence and a fixed original population are prerequisites. Expanded wall labels on this pair do not authorize another pose.

## Independent image evidence

`projected_world_regions` samples the current image at coordinates obtained by applying the independent source-camera matrix to every source pixel. A source footprint must be100%reviewed world. Current interpolation is valid only when all bilinear taps belong to the current reviewed world mask. Padding, unreviewed pixels and foreground/UI holes do not become samples. Source population is not reduced to increase coverage: at least90%of the complete source crop and32pixels must remain. Texture standard deviation>=1and NCC>=0.90remain unchanged. Both masks reject protected timer/phase pixels.

[The development report](../e2e_reports/match_001/scene_projected_world_development.json) records:

| Source region | Previous fixed-crop valid fraction | Projected reviewed valid fraction | Projected NCC |
| --- | ---: | ---: | ---: |
| 0 | 0.728940 | 1.000000 | 0.993499 |
| 1 | 0.848885 | 1.000000 | 0.996149 |
| 2 | 0.831468 | 0.985798 | 0.995854 |
| 3 | 0.813484 | 1.000000 | 0.983046 |
| 4 | 0.831146 | 1.000000 | 0.974528 |
| 5 | 0.848480 | 0.957447 | 0.985730 |

All6regions satisfy the unchanged numerical floors and source/current center distribution across at least3cells,2rows and2columns. The minimum current NCC is0.974528. This adds independent appearance support to the already retained source identities and explains the original crop-coverage abstention; no single crop establishes continuity.

## Continuity decision

The measured pair supplies source-world geometry plus distributed reviewed projected appearance consistent with visible scene continuity. It is only one link. The original chain still abstains and terminates: the pure diagnostic is not a fallback that revives it. No complete temporal episode, uninterrupted hidden game time, qualification, UI evidence or lifecycle event follows from this measurement. The separate critical R1timer sequence remains its earlier development observation; this experiment does not manufacture additional timer or boundary facts.

## Contract change

Only passive matrix observability is added to the existing diagnostic tracker; its defaults and explicit final-membership decisions remain unchanged. The new projected appearance routine is separate and returns `runtime_proof_authorized=false`. No production file, geometry/identity/ownership/NCC/OCR/discontinuity policy, sampler, GT or evaluator changes.

Current world masks are offline reviewed development input. They cannot be copied into production as per-frame truth. Production still needs independently qualified image-derived seed eligibility/current occlusion evidence. Source-frame hashes and PTS bind provenance; they must not be used to select expected events or crop masks by GT time.

## Tests

Tests cover integer translation; independence from every excluded source/current pixel; fractional interpolation across unreviewed taps; occlusion/padding retaining the original denominator; incomplete source review; protected UI; unavailable/degenerate geometry; wrong appearance; textureless images; and no runtime authority. Passive-sink tests compare decisions and future state in all existing modes, including mutation of exported metadata. Real defaults compare exactly on203links against preserved historical code; exposed cut/duplicate controls still reject. [Verification](../e2e_reports/match_001/scene_projected_world_verification.json) records terminal unit/Ruff/mypy results and source bindings. Windows execution remains unverified; no OS-specific acceptance rule is introduced.

## Previous / Current / Delta

| Same development-pair metric | Previous fixed crop | Current projected diagnostic | Delta |
| --- | ---: | ---: | ---: |
| Supported appearance regions | 0 | 6 | +6 |
| Retained original correspondence population | 94 | 94same input | 0 |
| Original tracker supported links | 0 | 0 | 0 |
| Qualification created | 0 | 0 | 0 |
| New runtime events | 0 | 0 | 0 |

Appearance counts describe different declared measurement domains on the same source pair; they are not an accuracy or canonical PASS delta. The pure diagnostic's runtime is recorded in its JSON report, but no comparable production timing run exists. Canonical historical23PASS/55FAIL/4NEand negative/discontinuity0/0remain the accepted baseline. Current/Delta are unmeasured; all82stored assertion statuses remain unchanged.

## Remaining blocker

A continuous projected-world chain still needs independently verified source/current world eligibility, moving occlusion exclusion and correct population continuity at every native link. Each projected sample must remain within qualified world evidence; no new feature identity, reseeding or cut bridging may be introduced. Freeze that integrated contract before independent holdout/control evaluation. The new appearance method must not be selected from repeated holdout tuning; this formerly reserved pair is now explicitly development. R2start and result-banner qualification remain separate. No targeted/sample/full canonical E2E was run because the trusted scene/UI and three-boundary gates remain incomplete.
