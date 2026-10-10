# Stateless reviewed-domain bootstrap contract

## Problem

`GT-R1-ROUND-START` needs an image-derived source-world initializer before continuous scene/UI qualification. Fixed coordinates cannot label arbitrary new scenes as background. A reference asset must also never be represented as an actually observed previous native frame.

## Evidence

Main `80d0d460b8e3a76d3c181e035c72cd10026f4252`. One existing reviewed native reference is declared in a profile-relative hashed image asset. The new profile explicitly declares `diagnostic_reviewed_domains`; a landmark-only declaration is rejected rather than silently promoted. Eight already exposed source images, native PNG/pixels, profile/code/video hashes are frozen before measurement and verified afterward. No new reference bank/model/threshold tuning occurs.

## Competing hypotheses

Full reviewed-domain joint appearance might provide an image-only source initialization proposal where unique point matching lacked coverage. Alternatively, fixed-reference camera correspondence may itself be incoherent over the changed pose before joint appearance can be measured. Even a passing reference pose is not temporal continuity or a foreground-free semantic mask.

## Independent image evidence

| PTS | Reference tracks | Model inliers | Model consensus | Initialization proposal |
| --- | ---: | ---: | --- | --- |
| 3.902669 | 180 | 180 | 100.00% | True |
| 4.086003 | 112 | 93 | 83.04% | False |
| 4.102669 | 110 | 92 | 83.64% | False |
| 4.119336 | 112 | 93 | 83.04% | False |
| 4.152669 | 113 | 87 | 76.99% | False |
| 3.002669 | 0 | 0 | Unavailable | False |
| 5.202669 | 0 | 0 | Unavailable | False |
| 6.002669 | 0 | 0 | Unavailable | False |

Only the reference self-image proposes initialization. This is a mechanics control, not independent accuracy evidence. All four actual R1transition images fail unchanged>=0.90global reference-model consensus and never enter the joint stage. Other camera poses have no sufficient reference tracks. This does not invalidate the adjacent22/29continuous source-chain evidence; it shows stateless reacquisition from this fixed reference is insufficient.

## Continuity decision

The reference is an asset, never the previous runtime frame. Matching it does not start a continuity segment, count temporal corroboration, establish pre-phase duration or create a lifecycle event. Incoherent matching remains unknown, not a content-cut classification. The earlier exposed transient scene evidence and production fail-closed behavior remain unchanged.

## Contract change

`WorldDomainBootstrap` composes the existing reference correspondence matcher and joint fixed-projection domain audit. It consumes only current canonical pixels and the strict reviewed reference profile; it accepts no PTS/video-ID/GT/current review lookup. Source correspondence retains NCC0.90, reciprocal1pixel, three-region support, partial-affine2pixel RANSAC and>=0.90consensus. Joint support preserves complete footprints, distributed source/current witnesses and explicit local alternatives. Multiple supported references are withheld rather than selected by best score. Output explicitly authorizes no semantic world mask, runtime proof, qualification or previous-frame assertion. Shared loader defaults preserve the old landmark format; the new domain scope is opt-in. No production code is changed.

## Tests

22related tests pass in12.97seconds (five new domain initializer cases plus nine landmark and eight joint cases). They verify no previous-native-frame/mask/runtime authority, unrelated scene rejection, protected UI invariance, competing-reference abstention, and refusal to promote a landmark-only profile. Ruff passes `src tests scripts/e2e` and both initializer modules. Production source is unchanged from the preceding104file mypy PASS.

## Previous / Current / Delta

| Metric | Previous | Current | Delta |
| --- | --- | --- | --- |
| Common exposed seven-frame reference self-matches | 1/7 (landmark method) | 1/7 (domain method) | Count0; methods differ |
| Extra exposed corridor image proposal | Unmeasured | 0/1 | Unmeasured |
| Qualified runtime initializer | 0 | 0 | 0 |
| Canonical PASS / FAIL / NE | Historical23/55/4 | Not rerun | Unmeasured |
| Canonical negative / discontinuity violations | Historical0/0 | Not rerun | Unmeasured |

Eight stateless queries took 5.024159seconds; this differs in model and instrumentation from prior experiments and is not a speed-improvement claim.

## Remaining blocker

This fixed-reference stateless route is rejected as a sufficient source initializer/reacquisition remedy. Do not expand banks or tune consensus thresholds to force these images through. The viable measured evidence is the continuous source-world identity chain; next connect an image-supported initial observation to it while retaining strict termination, current occlusion and source/PTS scope. Qualification still needs a frozen continuous producer and independent holdout/negative controls. A reference match cannot stand in for an observed prior frame or a current semantic mask. R1remains first priority; R2/result gates stay separate. No new canonical PASS, event, package or full E2E is claimed. Validation Pack/GT/assertions/full sampler remain unchanged; Windows execution is unverified.
