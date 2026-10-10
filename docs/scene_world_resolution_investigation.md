# Native-resolution R1 world tracking investigation

## Problem

R1 start remains blocked by independently qualified scene/UI evidence. The previous continuous reviewed-world chain loses distributed support before the `0:00 → 2:25 → 1:39` sequence. Hypothesis: canonical 640×360 INTER_AREA downscaling removes distinctive wall texture needed by the chain. Target assertion is `GT-R1-ROUND-START`, upstream of lifecycle/package scope; no assertion label enters image matching.

## Evidence and competing hypotheses

Started from latest main `03bfcbf945fbf3d7b04c54d80b3c5ff103475db0`. The newly merged qualification document also reports unresolved source/global evidence; its Mac source population and OCR experiments are historical, not new Pi results. Prior Pi world-chain diagnostics are the direct comparison for this experiment.

Source SHA256 remains `71d58558559d6f578433ce9f234bf176f76fd5a86657dbfe3eba1e7d36136b06`. The method declaration was saved before predictions. Inputs are the existing 36-frame native prefix and separate 30-frame stable archive, all development data. No holdout was newly labelled. The source frame set, PTS spacing and reviewed crop footprints are identical to the respective canonical-resolution trial. Scale every canonical crop coordinate by three; preserve the reviewed regions instead of searching for new favourable crops.

The alternative explanations are inadequate background spatial coverage, original-reference appearance change, affine-model mismatch and actual scene discontinuity. More accepted corners alone would not distinguish them. This experiment tests resolution loss as a sufficient remedy, not every possible scene matcher.

## Independent image evidence

New opt-in diagnostic resolution is 1920×1080 grayscale with no image resizing. Optical-flow window, corner separation, margins, patch radii, forward/backward tolerance and RANSAC pixel tolerance scale by three, preserving their normalized screen-space meaning. NCC remains ≥0.90; texture standard deviation remains ≥1; affine inlier fraction remains ≥90%; three reviewed regions and spatial witnesses across two rows/two columns remain mandatory. Dense minimum pixel population scales with area. No UI/clock/score values enter the chain. Only original reviewed world identities survive; no reseeding after abstention is introduced.

The native prefix seeds54features, just as the canonical prefix. Its first link at3.819336s retains only one candidate in region2 and terminates; canonical retained5candidates and likewise failed. Later images are not silently skipped or used to restart the chain.

The separate native stable archive seeds162features versus141at canonical resolution. Its first link at3.919336s has95original-world-supported tracks in regions1,2,5, but witnesses occupy only row1 and columns0,1. The spatial quorum therefore fails immediately. More source pixels improve neither distributed support nor the critical-link evidence under this fixed method.

## Continuity decision

Reject the hypothesis that removing downscaling alone repairs the chain. These missing supports remain unknown, never a content-cut label. Earlier independent regional evidence favouring visible camera continuity at R1's timer display change is not overturned, but it is also not upgraded into a qualified uninterrupted-gameplay history. No real boundary, scene attestation or qualification report is generated.

## Contract change

Only diagnostic scripts and tests changed. Canonical resolution remains the default, and all29per-frame result dictionaries on the original stable archive exactly match the preserved previous implementation. The native option enforces scaled protected timer/phase areas and expected shape. Production, geometry, ownership, OCR, validation pack, assertions and full sampler are untouched.

## Tests

Ten focused unit tests PASS in2.33seconds, including three new native-resolution tests for source-world identity, excluded-pixel invariance and protected-region/shape rejection. Ruff for source/tests/E2E/diagnostics PASS; fresh mypy on102production files PASS; diff check PASS. No full regression or canonical E2E is justified by this rejected diagnostic hypothesis. Windows execution remains unverified.

## Previous / Current / Delta

| Same-input diagnostic metric | Previous canonical | Current native | Delta |
| --- | ---: | ---: | ---: |
| Prefix frames / adjacent links | 36 / 35 | 36 / 35 | 0 / 0 |
| Prefix seed features | 54 | 54 | 0 |
| Prefix supported links | 0 | 0 | 0 |
| Prefix runtime seconds | 8.479058 | 8.787263 | +0.308205 (+3.63%) |
| Stable frames / adjacent links | 30 / 29 | 30 / 29 | 0 / 0 |
| Stable seed features | 141 | 162 | +21 (+14.89%) |
| Stable supported links | 4 | 0 | −4 (−100%) |
| Stable runtime seconds | 7.821179 | 7.776654 | −0.044525 (−0.57%) |

These are diagnostic-method comparisons, not measured recognition accuracy or E2E speed gains. Small timing changes are not claimed as optimization.

Canonical accepted history remains23PASS/55FAIL/4NE. Current and Delta are unmeasured, not unchanged fresh-run values. Existing82assertion rows are preserved. New qualification and new runtime events are both0. No full E2E was run.

## Remaining blocker

The required distributed source-world proof is missing under both tested resolutions. Current trusted scene/UI producers and their independent qualification are still required before activating the opt-in lifecycle path. R2 transfer and separate R1-end semantic-result/continuity qualification remain incomplete. Additional video is not asserted to be mandatory by this experiment; failure of this matcher cannot establish impossibility on the current source. Further work must address reviewed spatial/appearance support rather than repeatedly tune resolution or acceptance thresholds.

Artifacts: [pre-prediction declaration](../e2e_reports/match_001/scene_world_resolution_declaration.json), [prefix](../e2e_reports/match_001/scene_world_resolution_prefix.json), [stable](../e2e_reports/match_001/scene_world_resolution_stable.json), [verification](../e2e_reports/match_001/scene_world_resolution_verification.json).
