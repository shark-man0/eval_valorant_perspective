# Image-derived world landmark bootstrap investigation

## Problem

The projected R1 chain currently needs frame-bound manual world-only reviews. Such annotations cannot be copied into production runtime. This experiment tests whether an existing reviewed image reference can provide an image-only landmark entrance without current-frame time/round/GT lookup. Target assertion remains `GT-R1-ROUND-START`; no start event is claimed.

## Evidence

Main at measurement: `80d0d460b8e3a76d3c181e035c72cd10026f4252`. The seven inputs and profile/source/code hashes were declared before measurement. All inputs are already exposed development data, from one recording. The reference self-match is a parser/matcher control, not independent accuracy evidence. Local image assets are not Git artifacts.

## Competing hypotheses

An image-only reference bootstrap might replace manual current-frame lookup. Alternatively, the old unique reciprocal reference matcher may lack distinctive distributed witnesses after camera movement. No new matching model, reference bank, or threshold variant was introduced; the prior wider-search failure is not being reclassified as successful.

## Independent image evidence

| PTS (seconds) | Reference tracks | Model inliers | Distributed quorum |
| --- | ---: | ---: | --- |
| 3.902669 | 62 | 62 | True |
| 4.086003 | 3 | 3 | False |
| 4.102669 | 3 | 0 | False |
| 4.119336 | 2 | 0 | False |
| 4.152669 | 5 | 0 | False |
| 3.002669 | 0 | 0 | False |
| 5.202669 | 0 | 0 | False |

Total: 7 frames in 7.015737 seconds. Only the self-reference passes. The actual last-phase/phase-disappearance/first-2:25/first-1:39 images do not pass. Their timer/phase pixels are excluded, and the recognizer receives only canonical current pixels. Native PTS, video SHA and original pixels are bound in the measurement report outside recognition.

## Continuity decision

A single-frame landmark quorum does not decide temporal continuity. Failed landmark matching remains unknown, not a content-cut label. The earlier 30-native-image projected replay supported 22/29 links across the transient timer displays; that exposed continuous-image evidence still supports a visible UI transition, while uninterrupted hidden game time and independent runtime qualification remain unproven. This bootstrap provides no reason to override fail-closed production continuity.

## Contract change

`WorldLandmarkBootstrap` accepts only a strict diagnostic JSON reference profile, profile-relative hashed assets, reviewed non-UI reference boxes, and provenance. Unknown qualification/expected-time fields are rejected. Existing NCC >= 0.90, reciprocal error <= 1 pixel, RANSAC 2 pixels and distributed spatial quorum are unchanged. Output attests only matched reference patches: it explicitly does not authorize whole-ROI background masks, runtime continuity, events, player ownership or qualification. It is diagnostic code outside `src` and is not installed into `RealHudAnalyzer`.

## Tests

Nine focused tests pass (6.09 seconds): reference binding and schema rejection, unrelated-image rejection, and exact invariance under timer/phase pixel changes. Initial two failures were caused by the synthetic fixture using 640x360 assets against the existing native 1920x1080 contract; the fixture now generates native assets, with no relaxation of the input contract. Broader related-test/Ruff/mypy results are recorded in the verification artifact.

## Previous / Current / Delta

| Metric | Previous | Current | Delta |
| --- | --- | --- | --- |
| Diagnostic bootstrap quorum, exposed 7-frame set | Not measured | 1/7 (self-reference only) | Not comparable |
| Production scene/UI qualification | Absent | Absent | 0 |
| Accepted historical canonical PASS / FAIL / NE | 23 / 55 / 4 | Not rerun | Unmeasured |
| Fresh canonical negative / discontinuity failures | Historical 0 / 0 | Not rerun | Unmeasured |

## Remaining blocker

The image-only reference entrance is insufficient at the actual R1 start transition and is rejected as a qualification remedy. Do not enlarge reference banks or reduce ambiguity/spatial floors to make this set pass. The next implementation must preserve source-world feature identities from an image-qualified seed and reject current occlusion using image-derived footprint evidence, without manual per-frame masks or a whole-ROI semantic claim derived from mean NCC. Then freeze that producer and test disjoint holdout/negative controls/continuous sequences before runtime activation. R2 and TEAM ACE remain separate blockers. No full E2E was run because runtime evidence and qualification are still absent. Production, Validation Pack, GT, assertion semantics and full sampler remain unchanged. Windows execution is unverified.
