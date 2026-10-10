# R1 scene-camera model and final membership investigation

## Problem

On main `03bfcbf945fbf3d7b04c54d80b3c5ff103475db0`, the full-valid reviewed-world diagnostic stopped at purchase-phase disappearance despite strong adjacent crop photometry. Its original-seed similarity consensus removed every remaining point in region 1. Target assertions remain `GT-R1-ROUND-START`, `GT-R1-ROUND-END`, `GT-R2-ROUND-START` and the existing boundary-count/order assertions. This investigation addresses R1 source continuity only; it does not solve package scope or count an assertion as passed.

## Evidence

The same 30 native images span 3.902669–4.386003 seconds, with 256-tick adjacent increments in time base 1/15360. Video SHA256 is `71d58558559d6f578433ce9f234bf176f76fd5a86657dbfe3eba1e7d36136b06`. The six reviewed background footprints exclude timer and purchase-phase pixels; crop-local flow and warping cannot import excluded pixels. Original feature identities are immutable, with no new features or reacquisition after a failed link.

The original diagnostic supports 11/29 links. At 4.102669 there are 68 candidate correspondences: region 1 has 5, region 2 has 36 and region 5 has 27. The returned similarity RANSAC mask includes 63, excluding all five in region 1. Applying the final returned matrix with the same 2-pixel forward error includes 66: three region-1 points have errors within the floor. Region-1 median error is 1.83549 pixels, maximum 2.05383. This is a distinction between consensus-mask membership and refined-model error membership, not evidence of an OpenCV bug.

[Declared shadow-model comparison](../e2e_reports/match_001/scene_camera_model_declaration.json) and [bound results](../e2e_reports/match_001/scene_camera_model_stable_development.json) preserve the original population. Shadow fits execute after the original replay, avoiding interference with its random state. Its image-result dictionaries match the preceding full-footprint replay. Historical routine bytes are preserved locally under `outputs/recognition-investigation/scene-camera-model-20261009/`; their hashes match the report's original code bindings.

## Competing hypotheses

1. The camera projection requires a more flexible transform. Full affine and homography each include 68/68 points at this link and reduce regional residuals. These are geometric fits, without independent image qualification, and are not adopted.
2. The original returned mask is being treated as though it were final-model error membership. The same similarity transform already includes three additional region-1 candidates within the fixed error floor. This narrower contract hypothesis is tested before introducing a more flexible transform.
3. The scene actually changes at the timer transient. Distributed source-world identity and independently warped non-UI crop appearance now support visible scene continuity across the critical frames. They cannot exclude an edit that preserves the visible scene while advancing hidden game time.

## Independent image evidence

The declared `symmetric_final` diagnostic retains the original similarity estimator, its original consensus ratio of at least 0.90, and additionally requires at least 0.90 bidirectional final-model membership. Each point must lie within 2 canonical pixels in both seed→current and current→seed spaces. Original-seed and adjacent patch NCC remain at least 0.90. At least three retained seed regions and distributed full-valid crop support remain necessary. No timer value, phase value, expected timestamp or round ID enters this calculation.

[Declaration](../e2e_reports/match_001/scene_final_membership_declaration.json) preceded [the development replay](../e2e_reports/match_001/scene_final_membership_stable_development.json). All six full-valid crop regions support the following links; the values below are the minimum across those independent crop measurements:

| Current native PTS | Separately observed UI | Minimum background crop NCC |
| --- | --- | ---: |
| 4.102669 | Phase disappears; clock remains 0:00 | 0.993730 |
| 4.119336 | First 2:25 display | 0.996453 |
| 4.136003 | Second 2:25 display | 0.940422 |
| 4.152669 | First 1:39 display | 0.952430 |
| 4.169336 | Continued active display | 0.958853 |

At phase disappearance, the original mask includes 63, bidirectional membership includes 66 and original-seed photometry retains 65; one added candidate fails seed NCC and is rejected. Minimum accepted seed-patch NCC is 0.900535. Retained original identities span regions 1, 2 and 5. These independent geometric and photometric conditions jointly support the link; no single crop or NCC establishes continuity.

Phase disappearance precedes the first 2:25 frame by 16.667 ms. The first 1:39 frame follows the last phase-present frame by 66.667 ms. These timestamps describe observed source ordering and are not production acceptance constants.

## Continuity decision

On these development images, the combined evidence favours a visibly continuous camera scene with a transient UI display sequence. The diagnostic supports 22/29 links through 4.269336, including every critical transient frame. It terminates at 4.286003 with `seed_model_incoherent` under the original consensus requirement and never rejoins. Unsupported links stay unknown; they are not relabelled as cuts.

This does not prove uninterrupted game time, independent holdout accuracy or absence of a scene-preserving edit. The former failed holdout has already been exposed to development and cannot become fresh qualification merely by rerunning it.

## Contract change

Only the explicitly selected diagnostic mode changes: final geometric membership is checked in both pixel spaces while original consensus remains a separate prerequisite. The default `ransac_mask` behavior remains intact. More flexible shadow fits are never runtime proof. Production geometry, identity, ownership, NCC/OCR acceptance, discontinuity policy, sampler and evaluator are unchanged.

The existing `pre_round → transient_ui_transition → round_active` lifecycle proposal still requires a trusted, independently qualified scene producer and qualified positive UI-transition evidence. Every observed clock display, including 2:25, must remain in the evidence chain. No global scene evidence may establish player-owned HP, weapon, death or shot facts. No new qualification or runtime boundary is created here.

## Tests

The current focused world-chain/model-audit suite passes 26 tests in 5.10 seconds. Ruff passes over `src tests scripts/e2e scripts/diagnostics`; mypy passes on 102 production source files. Synthetic tests cover model ambiguity/degeneracy, exact historical model binding, fixed bidirectional error floors, explicit mode selection, original photometric rejection and cut vetoes. Exposed real cut and duplicate controls and default-equivalence replay are recorded in [verification](../e2e_reports/match_001/scene_final_membership_verification.json). These controls are not blind negative qualification.

## Previous / Current / Delta

| Development metric | Previous | Current | Delta |
| --- | ---: | ---: | ---: |
| Native input frames | 30 | 30 | 0 |
| Adjacent links | 29 | 29 | 0 |
| Supported links | 11 | 22 | +11 (+100%) |
| Shadow-audited replay wall time, seconds | 8.895033 | 9.854874 | +0.959841 (+10.79%) |
| Qualifications created | 0 | 0 | 0 |
| New runtime events | 0 | 0 | 0 |

These times include diagnostic instrumentation and are not a production speed comparison. Supported links measure source evidence coverage, not recognition accuracy or assertion PASS.

| Canonical metric | Historical accepted baseline | Current | Delta |
| --- | --- | --- | --- |
| PASS / FAIL / NE | 23 / 55 / 4 | Not measured | Not measured |
| Round start / end events | 0 / 0 | Not measured | Not measured |
| Native packages | 1 partial | Not measured | Not measured |
| Negative failures / discontinuity violations | 0 / 0 | Not measured | Not measured |

All 82 stored assertion statuses remain unchanged. No targeted/sample/full canonical run or fresh production recognition is claimed. Full E2E is not justified yet: qualified R1 source inputs, R2 start and R1 result evidence have not met the three-boundary gate.

## Remaining blocker

Freeze this method before reserving independent same-video holdout and negative-control cohorts, with source hashes, native continuity, reviewed world-only footprints and no validation-value input. Test disjoint camera poses and actual cuts/occlusions without refitting to their results. Passing training links do not authorize production activation. Then connect a qualified scene producer and qualified positive UI-transition producer to the existing fail-closed lifecycle contract. R2 starts and TEAM ACE result qualification remain separate later tasks; the result reference NCC 0.388 is not repaired by lowering its threshold. Windows execution is not verified; shared Python code retains the same spatial and acceptance policy on both platforms.
