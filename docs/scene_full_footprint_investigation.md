# R1 complete interpolation-footprint investigation

## Problem

`GT-R1-ROUND-START` still lacks qualified scene/UI evidence. The previous adjacent dense method stops before the timer transition, partly because the upper-right crop's interior standard deviation is below1 even though the complete crop contains more background variation. Hypothesis: using every fully source-supported crop pixel, rather than discarding a fixed inner border, can supply distributed scene evidence without importing UI or artificial padding.

## Evidence and competing hypotheses

HEAD is `03bfcbf945fbf3d7b04c54d80b3c5ff103475db0`. Source SHA256 remains `71d58558559d6f578433ce9f234bf176f76fd5a86657dbfe3eba1e7d36136b06`. The same30native R1 images/29adjacent links are used; no skipping or restart occurs. All are development data, not independent holdout. The method and hashes were declared before predictions.

Before matching, both complete upper source footprints were reviewed across all30images:60panels. Canonical region0 maps to source `(501,159,639,351)` and region3 to `(1320,159,1701,351)`. Both show wall/background without timer, phase, arms or HUD in this population. The review is source-image provenance, not semantic GT. The competing explanations remain missing usable texture, cumulative reference difference, inadequate camera-motion model and actual discontinuity. Similarity or missing support alone cannot decide uninterrupted game time.

## Independent image evidence

The new explicit `full_valid` footprint is permitted only with the separate `adjacent_dense_world` diagnostic mode. The source crop is warped locally. A float all-one coverage image follows the same interpolation; only output pixels with coverage exactly1 are scored. Padding and all pixels outside the reviewed source crop are excluded. The valid fraction must be≥0.90 of the **whole crop**, and the minimum pixel population, texture floor1 and NCC0.90 remain unchanged. No border-padding zeros are counted as shared evidence.

Original world feature IDs, adjacent/original-seed patch NCC, reciprocal flow, seed affine coherence and three seed regions remain required. Adjacent affine coherence and distributed photometric regions still require three cells across two rows/two columns. This broadens the explicitly declared diagnostic pixel population; it is not a silent fallback, a reduction of spatial/threshold requirements or a production policy change.

On the same archive, support extends **5/29 → 11/29**. At4.069336 all six crop scores are≥0.970800 with full-valid fractions≥0.962976. At4.086003, the last historically reviewed purchase-phase image, all six scores are≥0.995003 and69original-world tracks survive in three seed regions. Previously excluded border signal therefore explains a material part of early abstention.

At **4.102669**, the phase-disappearance image, the chain still fails. All5remaining tracks in seed region1 pass adjacent patch NCC but are outliers under the original-seed partial-affine model. The63original-world-supported tracks remain only in regions2and5. The mandatory three-region world criterion fails before the adjacent dense stage is run; later timer displays are not bridged or ignored. This is an original-feature/model support failure, not the previously observed upper photometric shortage.

## Controls and tests

The already exposed known-cut pair fails with `seed_model_incoherent` without an injected cut flag. A duplicate fails with `duplicate_image`. Both remain stress tests with hypothetical, independently unqualified end-view seed labels; they are not blind negative controls or proof of whole-video false-positive safety.

18focused tests PASS in3.55seconds. New tests cover full valid footprint, all external-pixel invariance, missing/fractional padding, explicit mode selection, and discontinuity/no-reacquisition vetoes. A first draft test incorrectly expected a translated uint8 coverage corner to round to255; OpenCV returned239. The assertion was corrected to verify actual fractional-padding rejection. No claim of a demonstrated uint8 rounding bug is made.

Ruff for source/tests/E2E/diagnostics PASS; fresh mypy on102production files PASS; diff check PASS. Existing default result dictionaries exactly match the preserved previous implementation on174links across three modes and both resolutions. Windows execution remains unverified.

## Continuity decision

The complete source footprint supplies previously omitted independent background signal and preserves descriptive continuity to the last preparation image. It still does not carry a trustworthy chain through phase disappearance and the timer sequence. Missing original-world support stays unknown, not a content-cut declaration. No qualification report, production profile, source attestation, boundary or player fact is generated.

## Contract change

Only diagnostic code/tests and records changed. Existing interior processing remains default. Production recognition, geometry anchors/retention, identity, ownership, spectator, OCR, map, GT, assertions and full sampler are untouched. Runtime activation of the proposed scene/UI lifecycle route remains gated by missing trusted producers and independent qualification.

## Previous / Current / Delta

| Same native R1 population | Previous adjacent interior | Current full valid footprint | Delta |
| --- | ---: | ---: | ---: |
| Frames / adjacent links | 30 / 29 | 30 / 29 | 0 / 0 |
| Supported links | 5 | 11 | +6 (+120%) |
| First unsupported PTS, seconds | 4.002669 | 4.102669 | +0.100000 |
| Runtime, seconds | 8.066642 | 8.496191 | +0.429549 (+5.33%) |
| Known-cut stress support | 0 | 0 | 0 |
| Duplicate stress support | 0 | 0 | 0 |

Support counts are descriptive and do not establish accuracy or canonical PASS gain. Control runtime is0.448078seconds versus0.431911for the preceding method (+0.016167,+3.74%); tiny diagnostic timing differences are not E2E optimization. Historical canonical baseline remains23PASS/55FAIL/4NE; Current/Delta are unmeasured. All82assertion rows are preserved. No targeted, sampled or full E2E was run for this unqualified method.

## Remaining blocker and next action

The first unsupported image now identifies a precise source-camera model question: why the five region1 correspondences disagree with the original-seed partial-affine projection while their adjacent photometry survives. Before changing that model, compare source-based residuals against physically justified camera transformations, using fixed tolerances and known controls. This is background scene-motion diagnosis, separate from HUD geometry policy. Do not drop the third world region, fit an acceptance rule to GT time, reacquire across the failed link or weaken NCC. Qualified scene/UI producers, independent holdout, R2 transfer and separate R1-end evidence remain incomplete. This experiment does not establish that extra video is mandatory.

Artifacts: [declaration and review hashes](../e2e_reports/match_001/scene_full_footprint_declaration.json), [native development](../e2e_reports/match_001/scene_full_footprint_stable_development.json), [controls](../e2e_reports/match_001/scene_full_footprint_controls.json), [verification](../e2e_reports/match_001/scene_full_footprint_verification.json).
