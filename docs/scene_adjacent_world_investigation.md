# Adjacent source-world photometry investigation

## Problem

Target `GT-R1-ROUND-START` remains blocked by qualified scene/UI input. Prior dense world tracking compares every entire background crop against the first seed. It stops at 3.969336 seconds although the source investigation suggests adjacent images are visually continuous. Hypothesis: cumulative seed appearance/model difference is unnecessarily terminating an otherwise consistent adjacent scene chain.

## Evidence and competing hypotheses

Started from main `03bfcbf945fbf3d7b04c54d80b3c5ff103475db0`. Source SHA256 remains `71d58558559d6f578433ce9f234bf176f76fd5a86657dbfe3eba1e7d36136b06`. A method declaration was saved before predictions. All tested images are previously exposed development populations, not new holdout. Alternatives include genuinely changed appearance, weak world texture, inadequate affine motion and source discontinuity. Neither a nonmatch nor a high similarity alone settles source time continuity.

## Independent image evidence

The explicit diagnostic mode `adjacent_dense_world` keeps only original reviewed world feature IDs. Reciprocal crop-local flow, adjacent patch NCC ≥0.90, original-seed patch NCC ≥0.90, original-seed affine coherence and at least three seed regions remain required. No reseeding follows an abstention.

An additional previous→current affine is fitted exclusively to retained, original-seed-qualified world tracks. It requires ≥90% inliers and at least three seed regions. Whole background crops then compare previous and current images with that model, using crop-local interpolation, original footprint protection, texture floor1, NCC0.90 and common distributed photometric regions in both links. These regions still span at least three witness cells, two rows and two columns. This is an alternative diagnostic contract, not a fallback or production policy change. It can use distributed adjacent background appearance even when surviving point witnesses occupy one row; qualification of that distinction remains necessary.

On the same30-frame stable archive, support changes **3/29 → 5/29**. At3.969336 the upper-region adjacent NCC is0.948021, versus the prior original-seed comparison0.871570. At3.986003 adjacent NCC is0.939976 and86original-world-qualified features remain. These two extra links support the cumulative-difference hypothesis locally.

At **4.002669**, support still fails before the phase/timer transitions. Region0 adjacent warped NCC is **0.833926**, below the fixed floor; another upper region remains texture-unknown. All valid warp fractions are1.0. The82retained points in seed regions1,2,5 occupy one row. The pre-existing independent raw-image measurement on the exact same pair gives region0NCC0.896447, also below0.90, so the failure is not exclusively introduced by warping.

The texture-unknown upper region has raw interior standard deviations **0.550076** and **0.562826** on that pair, below the floor1. It has stronger variation in the full crop, but using those border pixels is an untested interpolation-footprint hypothesis, not an authorized fallback. The present method preserves the original interior margin. No spatial, variance, NCC or flow threshold is reduced.

The36-frame prefix remains0/35: its first pair lacks three source-world regions. It is never restarted at a convenient later frame. The stable archive is a separately declared input.

## Controls

The already exposed pair `phase-evidence/dense-r1-end/frame_04.png → frame_06.png` fails with `seed_model_incoherent`, without injecting a discontinuity flag. An exact duplicate fails with `duplicate_image`. These are hypothetical-seed stress checks: the end-view seed is not independently qualified as world-only, and a single known cut plus duplicate is not a blind negative-control population or a whole-video false-positive estimate. No boundary is emitted.

Synthetic regressions reject a replaced upper-background appearance even if lower original-world tracks survive. Other cases preserve explicit discontinuity/duplicate vetoes, excluded-pixel invariance and no reacquisition. Synthetic success does not qualify the source method.

## Continuity decision

Cumulative original-seed comparison explains two early abstentions, but replacing only the whole-crop comparison does not provide the required R1 transition continuity. The candidate remains unqualified; missing support stays unknown, not a cut label. Earlier descriptive scene continuity evidence at the timer transition is neither disproved nor promoted to uninterrupted gameplay proof.

## Contract change

No production code, threshold, geometry, identity, ownership, OCR, GT, assertion or sampler is changed. Default `world_features` and existing `dense_world` output dictionaries exactly match their preserved prior implementation on116links across canonical/native stable inputs. The new mode is explicit and emits no runtime proof or event. No profile or qualification is adopted.

## Tests

15focused unit tests PASS in3.50seconds. Ruff for source/tests/E2E/diagnostics PASS; fresh mypy on102production files PASS; diff check PASS. All82historical assertion rows are preserved. Windows execution remains unverified.

## Previous / Current / Delta

| Same stable input | Previous original-seed dense | Current adjacent dense | Delta |
| --- | ---: | ---: | ---: |
| Native frames / adjacent links | 30 / 29 | 30 / 29 | 0 / 0 |
| Supported links | 3 | 5 | +2 (+66.67%) |
| First unsupported PTS, seconds | 3.969336 | 4.002669 | +0.033333 |
| Runtime, seconds | 8.015978 | 8.066642 | +0.050664 (+0.63%) |

Support is descriptive, not recognition accuracy or PASS gain. Prefix support stays0/35; its runtime is8.424014seconds. The two-control stress run takes0.431911seconds; no previous same-method runtime exists. Canonical historical baseline is23PASS/55FAIL/4NE; Current and Delta are unmeasured. No targeted, sampled or full E2E is justified by this failed qualification gate. New real events and qualification reports remain0.

## Remaining blocker

Distributed upper-world photometric support remains absent at4.002669. The next evidence question is whether the conservative whole-crop interior margin excludes usable reviewed background signal, and whether a strictly validated interpolation footprint could use it safely. That must be tested as a separately declared method with independent negatives; it must not silently replace the current margin or fill unknown. Trusted scene/UI producers, independent qualification, R2 transfer and separate R1-end result/continuity evidence remain incomplete. Additional video is not declared mandatory by these experiments.

Artifacts: [method declaration](../e2e_reports/match_001/scene_adjacent_world_declaration.json), [stable development](../e2e_reports/match_001/scene_adjacent_world_stable_development.json), [prefix development](../e2e_reports/match_001/scene_adjacent_world_prefix_development.json), [control stress](../e2e_reports/match_001/scene_adjacent_world_controls.json), [verification](../e2e_reports/match_001/scene_adjacent_world_verification.json).
