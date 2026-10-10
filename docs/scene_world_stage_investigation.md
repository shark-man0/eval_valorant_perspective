# R1 reviewed-world rejection-stage investigation

## Problem

`GT-R1-ROUND-START` is blocked by qualified source scene/UI evidence. The native-resolution experiment rejected downscaling alone as a remedy. This follow-up separates weak image conditioning, reciprocal flow failure, seed photometry and spatial quorum loss before selecting another matcher or profile. It adds passive diagnostic counters, not a recognizer candidate.

## Evidence

HEAD is `03bfcbf945fbf3d7b04c54d80b3c5ff103475db0`. The original source SHA256 remains `71d58558559d6f578433ce9f234bf176f76fd5a86657dbfe3eba1e7d36136b06`. Existing development input sets are unchanged: 36 continuous native prefix frames and a separate 30-frame native stable archive, each measured at canonical and original resolution. Reports verify input bytes, decoded pixels, video and code before/after the completed process. No frames are skipped, no terminated track chain is restarted, and no GT/value label enters measurement.

## Competing hypotheses

A low track count could result from poor conditioning, moved features outside a crop, inconsistent flow, changed appearance or a content cut. A high track count could still fail spatial coverage. These outcomes must not be conflated. The new per-region counters identify the exact stage; they do not turn its failure into a semantic cut label.

## Independent image evidence

Each seed crop records raw corners, margin rejection, texture rejection and eligible source-world feature count. Each attempted link records flow status, reciprocal/out-of-crop rejection, adjacent NCC, affine inliers/outliers, valid original-source warp footprint and original-source NCC. Current-frame measurements remain restricted to reviewed non-UI crop-local images.

A shadow optical-flow call requests OpenCV's minimum-eigenvalue output using the same inputs and all existing parameters. Coordinates and status flags must exactly match the original call or the diagnostic aborts. The existing default minimum-eigenvalue threshold `1e-4` is unchanged. Failed forward/backward calls below that floor are distinguished from other failures. Forward and backward counts can overlap and must not be added as disjoint rejected-feature totals.

### Native stable input: conditioning causes the lost spatial row

At 3.919336 seconds, regions 0, 3 and 4 contain 4, 1 and 30 seed tracks. **All 35** fail forward and backward conditioning below the unchanged default eigenvalue floor. Their seed crop standard deviations are approximately 1.528, 1.174 and 2.267. These measurements identify numerical conditioning in the chosen weak-texture regions; they do not prove a physical scene replacement.

Regions 1, 2 and 5 retain 9, 60 and 26 tracks respectively: all **95** adjacent candidates are affine inliers and pass original-seed photometry. Their witnesses still occupy only row 1, columns 0 and 1. More pixels or more accepted points cannot supply the absent spatial row. No seed-warp or seed-NCC rejection occurs for these 95 points at that link.

### Canonical stable input: the last upper-row witness is lost

Region 0 begins with 6 eligible features. Four fail the default flow conditioning on the first link; two survive through the next links. At 3.969336, another fails backward conditioning. At 3.986003 the remaining point passes adjacent NCC but is an affine outlier against the other reviewed regions. Across all regions at that last link there are 91 adjacent candidates, 88 affine inliers and 86 original-seed-supported points. The last upper-row point is gone; the spatial quorum fails despite 86 surviving points. This is a measured model/conditioning limitation, not an NCC threshold shortage that warrants relaxation.

### Prefix input: a different immediate failure

At 3.819336 the canonical prefix retains 5 adjacent candidates, all in region 2. The native prefix retains 1 there. Other regions have flow status/reciprocity failures before a distributed model can be formed. These facts do not independently classify the prefix as a cut. Stronger real continuity evidence is required.

### Lower-row candidate is rejected before matching

Manual review of all 36 contextual source panels considered the proposed source ROI `(560,735,1000,885)`. Player hand/forearm/charm pixels enter it in multiple frames, including the timer-transition neighbourhood; faint fixed ability UI is also visible at its lower-centre edge. It cannot be declared a world-only source region. No matcher was executed with it and no new profile/mask or qualification was generated. Review hashes and representative source hashes are recorded in the review ledger; private images remain outside Git. This is development image review, not semantic ground truth or player ownership confirmation.

## Continuity decision

Missing source-world quorum stays unknown. The earlier independent evidence for visible scene continuity across the timer UI sequence is not invalidated, but this diagnostic still does not qualify uninterrupted gameplay or activate a boundary producer. An apparently useful lower-row patch cannot safely fill the missing row when it contains foreground/UI.

## Contract change

Only diagnostic instrumentation and its tests changed in this follow-up. Default and instrumented decisions/numeric outputs exactly match the preserved previous implementation on **128 adjacent links** across all four populations. The shadow flow call likewise checks exact coordinate/status invariance. Historical stage-only code bytes are reconstructed into a private snapshot and verified against their recorded SHA256; older reports are not rewritten as current-version proof.

Production thresholds, geometry, identity, ownership, OCR, GT, assertions, sampler and lifecycle behavior are untouched. Qualification and new runtime events remain zero.

## Tests

12 focused unit tests PASS in 2.58 seconds. The additional cases check seed-population accounting, rejection-stage conservation, exact decision invariance and no reseeding for empty/terminated chains. Ruff for source/tests/E2E/diagnostics PASS; fresh mypy on 102 production files PASS; diff check PASS. All 82 assertion rows and their hash remain unchanged. Windows execution remains unverified.

## Previous / Current / Delta

| Same-input metric | Previous stage-only run | Current eigenvalue diagnostic | Delta |
| --- | ---: | ---: | ---: |
| Canonical prefix supported links | 0 / 35 | 0 / 35 | 0 |
| Canonical stable supported links | 4 / 29 | 4 / 29 | 0 |
| Native prefix supported links | 0 / 35 | 0 / 35 | 0 |
| Native stable supported links | 0 / 29 | 0 / 29 | 0 |
| Canonical prefix runtime, seconds | 8.425243 | 8.405007 | −0.020236 (−0.24%) |
| Canonical stable runtime, seconds | 8.088257 | 8.082226 | −0.006031 (−0.07%) |
| Native prefix runtime, seconds | 8.744503 | 8.794743 | +0.050240 (+0.57%) |
| Native stable runtime, seconds | 7.809512 | 7.849903 | +0.040390 (+0.52%) |

Small timing changes are ordinary diagnostic variation, not E2E optimization or accuracy improvement. PASS/FAIL/NE historical baseline is 23/55/4; canonical Current/Delta remain unmeasured. No targeted, sampled or full E2E is justified by this unqualified source method. No new real round boundary is claimed.

## Remaining blocker and next action

The measured bottleneck is persistent distributed **reviewed world structure**, with weak upper-row conditioning and foreground/UI contamination in the proposed lower-row alternative. Do not lower eigenvalue, NCC or spatial quorum thresholds to manufacture support. Next source work should locate and verify distinctive world-only structures across relevant camera poses before another method qualification attempt. A failure of these fixed crops and models does not prove that additional video is mandatory or that all scene methods are impossible. Trusted positive scene/UI producers, independent qualification, R2 transfer and separate R1-end result/continuity evidence remain incomplete.

[Verification](../e2e_reports/match_001/scene_world_stage_verification.json) contains per-region statistics and all first-failure rows. [Candidate review ledger](../e2e_reports/match_001/scene_world_stage_candidate_review.json) records the rejected foreground/UI crop. The four `scene_world_eigen_*` JSON reports retain the complete native link populations.
