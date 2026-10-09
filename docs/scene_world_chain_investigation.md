# R1 reviewed-world continuous tracking investigation

## Problem

R1 has a visible timer sequence `0:00 → 2:25 → 1:39`. Independent regional images favour visible camera-scene continuity, but the reference-bank method failed its reserved positive qualification. This bounded follow-up tests continuous tracking of reviewed world features rather than independent reference matches. It does not qualify a production detector or prove uninterrupted game time.

## Evidence

The source video SHA256 is `71d58558559d6f578433ce9f234bf176f76fd5a86657dbfe3eba1e7d36136b06`. Reports bind input PNG bytes, decoded pixels, source video and diagnostic code. Native adjacent frames are 256 ticks apart at time base 1/15360; no frames are skipped. The prefix comprises six images at 3.802669–3.886003 seconds followed by the original thirty at 3.902669–4.386003. The separate stable experiment explicitly starts at 3.902669; it does not resume the failed prefix chain.

## Competing hypotheses

A content cut, transient UI change, camera motion, weak/repeated wall texture and incomplete reference coverage remain distinct explanations. Missing distributed world support is an abstention, not proof of a cut. Earlier independent regional NCC and forward/backward motion support visible continuity across phase disappearance and anomalous clock displays; a scene-preserving edit remains unresolved.

## Independent image evidence

Only reviewed background crops outside the timer/phase and player arms are used. Initial world feature IDs persist; no new features are born after loss. Crop-local optical flow, forward/backward consistency, affine consensus, original-source patch NCC ≥0.90 and distributed support are required. An abstention clears the chain permanently. Duplicate images and explicit discontinuities veto continuation.

The 36-frame prefix supports **0/35** links: the first pair supplies only five tracks and fails the three-region requirement. The separately initialized 30-frame experiment supports **4/29** links. At 3.986003 seconds, 86 retained tracks in four regions still occupy only one witness-grid row, so they cannot satisfy the two-row spatial requirement. A high track count alone is insufficient.

An alternative diagnostic uses whole reviewed world crops with crop-local affine warping, valid interpolation coverage, NCC ≥0.90 and common distributed regions in both adjacent frames. It supports **3/29** links. At 3.969336 seconds, the upper crop NCC is **0.8715699315**, another upper crop has insufficient texture, and the remaining qualified crop centres occupy one row. Valid footprint fractions are 1.0: this failure is not excluded-pixel leakage or missing warp coverage.

A seventh lower-left background crop `(10,250,83,290)` in canonical 640×360 coordinates was manually reviewed across all thirty native images using a contextual contact sheet. It shows wall rather than arms/UI. Its NCC at the failing link is **0.8712360263**; support remains **3/29**. Adding an unoccluded reviewed region alone does not solve appearance support. These images and hypotheses are development data, not fresh holdout or semantic ground truth.

## Continuity decision

All continuous-chain variants abstain before the critical timer links. None authorizes a production scene-continuity proof. The earlier descriptive evidence for a transient UI display remains useful, but this follow-up does not establish the qualification needed to activate the production lifecycle route. Unknown must not be relabelled as either continuity or content cut.

## Contract change

No production contract or recognition behaviour changed in this follow-up. Two diagnostic support modes are explicit alternatives, never a fallback that bypasses spatial coverage. Both retain source-world identities and terminate after support loss. No threshold, geometry, ownership, GT, assertion or full-sampler policy is changed. Trusted positive scene/UI producers and paired qualification remain absent; no real round event is produced.

## Tests

Seven focused unit tests pass in 1.41 seconds, covering persistent identities, no reseeding, unrelated views, duplicates/discontinuities, excluded-pixel invariance, spatial abstention and crop-local dense warping. Ruff passes for source, tests, E2E scripts and the two new scripts. Production SHA256s match the earlier successful mypy check of 102 source files; mypy was not rerun for this diagnostic-only follow-up. The 82-assertion matrix SHA256 remains `6b192db1d045ae6c7022fc096dfdb22250d124221639b283472b45fa25f1e776`.

## Previous / Current / Delta

| Diagnostic | Frames / links | Supported links | Runtime |
| --- | ---: | ---: | ---: |
| Continuous world features, prefix | 36 / 35 | 0 | 8.479 sec |
| Continuous world features, separate stable input | 30 / 29 | 4 | 7.821 sec |
| Dense world, six reviewed regions | 30 / 29 | 3 | 8.016 sec |
| Dense world, seven reviewed regions | 30 / 29 | 3 | 7.968 sec |

For the same stable input, the seventh-region trial changes supported links **3 → 3 (0)** and initial features **141 → 148 (+7)**. Runtime changes by −0.048 seconds (−0.60%); this small diagnostic variation is not an E2E speed improvement. Point support versus dense support changes 4 → 3, but they use different contracts and this is not an accuracy comparison. Independent bank support of 26/29 is likewise not comparable qualification evidence for a continuous chain.

| Canonical metric | Historical accepted baseline | Current | Delta |
| --- | ---: | --- | --- |
| PASS | 23 | Not measured | Not measured |
| FAIL | 55 | Not measured | Not measured |
| NE | 4 | Not measured | Not measured |
| Round start / end events | 0 / 0 | Not measured | Not measured |
| Negative failures / discontinuity violations | 0 / 0 | Not measured | Not measured |

No targeted, sampled or full E2E was run for these rejected diagnostic methods. No new qualification or runtime boundary was created. Historical assertion results are preserved, not presented as a fresh recognition run.

## Remaining blocker

Reviewed background appearance and pose coverage do not yet provide persistent distributed proof. A trusted current-frame scene producer, positive UI-transition producer and independent qualification are required before real lifecycle activation. R2 transfer and the separate R1-end result-banner qualification remain unfinished. Windows execution is unverified. Work is paused at the user's requested checkpoint; the overall round-lifecycle goal is not complete.

Reports: [prefix](../e2e_reports/match_001/scene_world_chain_development.json), [stable features](../e2e_reports/match_001/scene_world_chain_stable_development.json), [dense spatial evidence](../e2e_reports/match_001/scene_world_chain_dense_spatial_diagnostics.json), [reviewed seventh region](../e2e_reports/match_001/scene_world_chain_reviewed_row2.json).
