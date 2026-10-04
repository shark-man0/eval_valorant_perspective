# HUD context safety follow-up

## Reproducibility

Starting shared HEAD: `e2c53305571e6b9c3e747cb0cf0b6885cdcdbc06`. The immutable review tool is committed separately at `ab8155af4d3b25347254cd29e0c5e5488f337470`. Production analyzer source remains `3e9df3dab16d6dce83f3973f0386638d11286c0c`; no detector, value-reader, identity gate, threshold, fact or event implementation changed in this phase.

Video SHA256: `71d58558559d6f578433ce9f234bf176f76fd5a86657dbfe3eba1e7d36136b06`. Active profile sidecar SHA256: `8e764d6eb2b7a6a8ce6a5f144300bdf809f16f9dcf2b689ac659333c2265b615`. Layout SHA256: `a3678bcd9df35d0932ae0e69495eb5b87a3ab40e9c988560d502a9507d59eef1`. Settings fingerprint: `5f73d89e69cc283cefdd28b68524e0ce2e81985b6605842de5bbb6725edc70f8`.

The 4,081-row classifier replay initially used a saved raw run recording analyzer commit `4f142acd50eebf6d956893fe3f9c47b4b9bbda7b`, executed with current source. Direct comparison against the committed-source Clean E2E at `3e9df3d` confirms all 4,081 frame indices, times, states, flags, contexts and player-HUD-validity fields agree. All 4,361 extracted JPEG relative paths and bytes agree. The only quality leaf difference is the added `quality.roi_confidence.hp_value`, absent/null versus 0.0 on all raw rows. This is state/pixel parity, not a claim that both run metadata commits or all quality objects are identical.

Private images, source paths, timestamps, individual annotations and prediction dumps remain local. Shared evidence is aggregate. Source selection uses pixels and diagnostic signal/context strata, not GT, expected states or event labels. Same-video, previously inspected blocks are development evidence, not independent recording holdouts.

## Ammo endpoint cue

The canonical ledger contains 317 unique crops, including 178 clear complete pairs. Measuring every foreground connected component in the frozen current field, without digit prediction or component pruning, gives 22 complete one-component current words across six source blocks. Their normalized gap to the right edge is 0–0.03846. These include both visually one-digit and two-digit words; component count is not digit count.

A diagnostic-only endpoint guard was frozen before evaluation: an already accepted one-component current word must have right gap <=0.05. This is a proposed calibrated-field placement constraint, not a partial-glyph detector. No reserve guard is justified because the reviewed set lacks clear one-digit reserve examples.

| Evaluation set | Crops | Current accepted before/after | Joint accepted before/after | Guard triggered |
| --- | ---: | ---: | ---: | ---: |
| Reused odd evaluation | 69 | 14 / 14 | 6 / 6 | 0 |
| Owned-live score-selected audit | 31 | 31 / 31 | 31 / 31 | 0 |
| Immutable positive audit | 24 | 24 / 24 | 3 / 3 | 0 |
| Native numeric-absent controls | 24 | 0 / 0 | 0 / 0 | 0 |
| Synthetic stress variants | 254 | 174 / 166 | 17 / 15 | 8 |

All eight removed current outputs follow complete erasure of the rightmost glyph. Pixel adjudication found no residual visible glyph fragment in the altered words. Five accepted attempted-border-shift cases also left the words visibly complete; they are not proven partial-glyph errors. Comparing altered outputs with the original value would be an expected-value oracle. The guard instead exploits recurring complete-word placement. It cannot detect complete erasure of a left glyph and has no natural positive triggered-case validation in those reused evaluation sets.

The separate natural challenge excluded canonical and previously reviewed exact pixel hashes. From 2,023 unique cached crops, 1,768 remained eligible. Exactly-one-component populations contain 27 high-gap candidates and 158 low-gap controls. Twelve per group were selected using low-level geometry/image features before loading numeric predictions. Both groups cover eight source blocks.

Root image-only review found all 24 crops contain decorative HUD lines over world/hand/transient texture, with no readable current numeral word. Frozen parser replay subsequently accepted 0/24 current words and 0/24 complete pairs, before and after the endpoint guard. These are useful natural hard negatives but provide no new evidence about complete-word endpoint generalization. The guard remains a development cue; it is not deployed.

Frozen guard SHA256: `8647ad7a01cb959cb51cbc3b9c6e8555eab72865d4d86c18868627e915c46feb`. Natural selection SHA256: `802bc8634edf9e60654b993a54fc56d571eae3594684be546ee81b147f30b562`. Sealed review manifest: `7d3a965c1dcd54aa6901a3ad2c30e8c62ac3acd2335849e9efc0ba302222a5c3`. Annotation SHA256: `4dcd2801f8a65e2a184243404a4018135ef94c8f8d557a74fa7228c369899b59`. Exact cache-pixel join SHA256: `e126bdbe2fc152a9d377f157b8c94442e2c99407553d4486afa3c5d5dfc854a9`.

## Buy close-X exact classifier replay

The existing strict close anchor is a Hough diagonal heuristic, not a learned reference. A frozen diagnostic candidate uses three fixed center-locked grayscale reference patches at threshold 0.90, with no displacement search or retuning. The original per-frame feature reader and original sequence post-processing were used, with cacheable independent feature extraction. Full baseline state/flag/player-validity parity is 4,081/4,081.

The candidate has 307 close-X hits, including 275 with the existing buy-grid condition. Replacing only the strict anchor while preserving existing identity gates, broad spectator-obscuration veto and classifier conflict policy yields:

- 275 UNKNOWN to Buy transitions;
- one old Buy to UNKNOWN transition;
- one UNKNOWN to Remote transition;
- no newly valid player-owned HUD or trustworthy-world observations on candidate hits.

The additive-OR variant preserves the two legacy states and adds 275 Buy transitions. Preserving an old heuristic is not evidence that its old positive is correct.

## Image-only context audit

A sealed 67-frame audit contains 24 sampled new Buy transitions (12 with a saved report-context signal, 12 without), all 32 candidate-positive/grid-detector-negative cases, and all 11 old strict-anchor hits. Selection and images were frozen before root labels; scores and mapping were withheld during labeling. Each join verified ID, decoded composite hash, shape and original full-frame bytes against prediction-cache inputs. All samples come from previously inspected source blocks, so this is correlated development review.

| Selected stratum | Count | Visible purchase grid + close X | World texture, no grid/X |
| --- | ---: | ---: | ---: |
| New Buy with report signal | 12 | 12 | 0 |
| New Buy without report signal | 12 | 12 | 0 |
| Candidate hit, grid detector misses | 32 | 32 | 0 |
| Old strict anchor hits | 11 | 0 | 11 |

The 11 world-texture cases comprise three death/report scenes, one first-person/report scene and seven first-person/world scenes. The old Buy removed by replacement is among the death/report world-texture cases, not a visibly open purchase menu. The new Remote exposed by replacement is also a death/report world-texture case. Appearance labels do not establish mode truth or ownership, but they reveal that retaining the Hough positive solely to preserve prior state is unjustified and that replacement exposes another classifier risk.

The 32 grid-detector misses visibly contain the complete menu, demonstrating a separate buy-grid recall mechanism. They do not justify removing the grid conjunction. Likewise, the saved report-context flag on sampled actual menu images must not be treated as independent evidence of a combat report.

Sealed review manifest SHA256: `4a510d9c689bb5e4b4693467a61df375a21b85f5f7796fbb55e669fcfc458f39`. Root annotation SHA256: `3a0b81268742f7d8468f4c2987adb518ebf67840ee7fa33543064d8f350f8636`.

## Decision and next blocker

`NEED MORE EVIDENCE` for production adoption of either candidate. No arbitrary threshold lowering, GT use, expected-value use, identity gate deletion or unsafe temporal persistence is introduced.

Do not repeat the endpoint stress test or the close-X threshold study. The next highest-information diagnostic traces the exposed Remote decision against the existing 33 Remote observations and observable death/report/world controls. This establishes whether a close-anchor improvement would safely classify menus or reveal unsupported Remote positives. Independent menu appearance validation and buy-grid structure remain subsequent requirements. Ammo deployment still requires complete-word safety evidence beyond score-selected positives and the tested same-video negatives.

## Verification and Git separation

The diagnostic review tool has 19 targeted synthetic regression cases passing after its final rendered-ID-width check. Full pytest before that small check was 848 passed / 2 skipped; the subsequent targeted tests cover the width change. Ruff passes for `src tests scripts`, mypy for the existing `src` contract (86 files), and staged diff check passes. The two skips concern a fixed sibling-pack lookup and a dedicated legacy real-video anchor setting.

No new Clean E2E was run for this diagnostic-only phase. The last committed-source Clean E2E remains 22 passed / 56 failed / 4 not evaluated, negative assertions 20 passed / 0 failed, `git_is_dirty=false`, 166 live observations. These unchanged results are not counterfactual production results. Diagnostic tools/tests/docs and this aggregate follow-up are separate commits; no image or generated private identity asset is committed.
