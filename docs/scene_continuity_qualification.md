# Scene continuity qualification: withheld native intervals

## Problem

R1's critical timer-transition links have strong scene correspondence, but that finding does not qualify a general production continuity producer. Fixed crops must remain usable through ordinary camera motion, foreground animation and occlusion. The current opt-in producer still requires physically consistent accepted timers and rejects R1's abnormal display sequence; no runtime qualification is installed.

Target remains source-qualified round lifecycle evidence for R1 start/end and R2 start, upstream of the33round-related failures. No assertion is newly passed in this investigation.

## Evidence

Starting HEAD: `0a606a0a3edb19ba4cd10d8007c2d045c39b2006`, with previously documented worktree changes. Source video SHA256: `71d58558559d6f578433ce9f234bf176f76fd5a86657dbfe3eba1e7d36136b06`.

Before decode/scoring, three scene-only holdout spans were frozen:3.30–3.80,4.65–5.15and30.10–30.60sec. They are explicit offline diagnostic ranges, not GT acceptance windows or runtime constants. The reservation binds the current HUD code fingerprint, diagnostic script SHA and60previous scene-development frame hashes. Every new frame hash is disjoint from that development set. These are correlated intervals of the same video, not independent lifecycle episodes or a complete cross-component training/holdout qualification.

Existing shared extraction verifies ffprobe coverage on both sides of each range, every interior native PTS against ffmpeg showinfo, frame count and ordering. All90frames are kept, yielding87adjacent links at60fps, time base1/15360. No N-frame sampling, FPS reduction, profile changes or full-sampler changes. Source video, PNG/pixel hashes and code binding are checked terminally. Runtime63.483sec includes extraction, hashing and both scene and production-camera measurements; no directly comparable previous runtime exists.

Artifacts:

- [Frozen reservation](../e2e_reports/match_001/scene_holdout_reservation.json)
- [Raw native measurements](../e2e_reports/match_001/scene_holdout_diagnostics.json)
- [Review provenance and qualification decision](../e2e_reports/match_001/scene_holdout_review.json)

Images stay Pi-local. No expected timer, score, round ID or acceptance window is used to score/select the methods.

## Competing hypotheses

1. Fixed raw-NCC camera cells generalize sufficiently beyond the short R1 development window.
2. Camera/foreground motion causes substantial safe abstention even within visually continuous scenes.
3. High LK feature coverage means the fixed crops contain independent background evidence.

The withheld intervals contradict hypotheses1and3as sufficient qualification claims. They support hypothesis2. Missing camera quorum is not a content-cut label.

## Independent image evidence

All30source-indexed panels of each span were reviewed in contact sheets. Timer/top HUD and phase/result panel are masked in those review renderings; measurement source images remain unchanged. Midpoint full-resolution context was also viewed, with numeric HUD values unused in the decision.

The pre-transition span shows a wall/doorway, knife inspection and moving teammates. The post-transition span shows camera motion past the wall/doorway with teammates and knife foreground. The later span shows a doorway/courtyard pan and knife inspection. None shows an obvious whole-scene replacement in the reviewed panels. This supports ordinary scene motion, not uninterrupted gameplay-time certification or hidden-edit rejection.

The same fixed six R1 crops can contain hands/knife, teammate bodies or teammate overlays in these views. Consequently, tracking points in three regions is not by itself proof that those regions are world background. The static crop layout is not a universal HUD/foreground exclusion policy.

## Continuity decision

| Frozen span (sec) | Native frames | Adjacent links | Production phase-excluded camera quorum | Camera abstentions | All-six raw NCC≥0.90 | LK support in≥3regions |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| 3.30–3.80 | 30 | 29 | 5 | 24 | 0 | 29 |
| 4.65–5.15 | 30 | 29 | 1 | 28 | 0 | 29 |
| 30.10–30.60 | 30 | 29 | 17 | 12 | 0 | 29 |
| Total | 90 | 87 | 23 | 64 | 0 | 87 |

Camera quorum occurs on26.44%of measured links. This is descriptive coverage, **not a correctness/pass rate**. Correct/wrong full-content continuity counts are not assigned: visual scene review cannot exclude scene-preserving edits, and the producer requires additional timer/content evidence. The raw measurement report remains labelled unreviewed at generation; the separate review ledger supplies subsequent observations without rewriting that artifact.

**Reject qualification of the fixed six-ROI method as universal background evidence and the all-six raw-NCC temporal recipe.** Do not convert the64camera abstentions into cuts, reduce0.90, or treat the87distributed LK links as continuity proofs. No runtime qualification, source segment, round event or player fact is generated from this holdout.

## Contract change

No additional production change is made in this follow-up. The earlier phase/result pixel exclusion remains, with code-bound requalification required. The investigation supplies a missing qualification requirement: source correspondence must include explicit region eligibility/foreground/occlusion validity and motion-aware evidence, not merely fixed coordinates or feature counts.

Scene continuity, clock/display semantics and content-time vetoes remain separate. Unknown visibility does not authorize combining preparation and active evidence across a gap. Known content jumps, duplicate source pixels and nonmonotonic/gapped PTS remain vetoes. Player-owned evidence cannot reuse this system-scene path.

## Tests

Only source extraction/review artifacts and documentation change in this follow-up. Previously verified135related tests, Ruff and mypy101production files remain applicable because the frozen production and scene-code fingerprints match terminally. No redundant test rerun or new full E2E is performed. Existing native-extraction tests cover PTS/order/coverage rejection. Windows extraction, OpenCV outputs and file handling remain unverified on a Windows machine.

## Previous / Current / Delta

| Metric | Previous | Current | Delta |
| --- | ---: | ---: | ---: |
| Scene-method withheld native frames | 0 | 90 | +90 |
| Withheld adjacent links | 0 | 87 | +87 |
| Production camera-quorum coverage on these fixed inputs | Unmeasured | 23 /87 | — |
| Runtime qualification / new boundaries | 0 /0 | 0 /0 | 0 /0 |
| Canonical PASS | 23 | Not rerun | — |
| Canonical FAIL | 55 | Not rerun | — |
| Canonical NE | 4 | Not rerun | — |

The earlier development-window camera quorum49/58and this withheld coverage23/87have different inputs and must not be presented as a same-input regression delta. Historical negative failures/discontinuity violations are0; this source-only study does not establish fresh canonical safety. No additional PASS or29-package-failure resolution is claimed.

## Remaining blocker

The new withheld evidence sharpens the upstream failure: raw cell NCC abstains during normal motion, while distributed LK can track moving foreground. Independent current-frame **region eligibility plus motion-aware correspondence** is still missing. R1's anomalous clock semantics, R2's purple occlusion and R1-end banner transfer remain unresolved. Additional video is not made a prerequisite; these90frames and existing actual cut/occlusion controls provide concrete development cases, but once used to design another method they must cease being its qualification holdout. Reserve another disjoint cohort before evaluating the next frozen method.

The goal remains the source→lifecycle→package→trace→canonical pipeline, not merely a camera benchmark. The conditional30PASS/49FAIL/3NEgoal is unachieved. A full E2E remains unjustified until real qualified evidence establishes the three continuous boundaries and sampled/negative gates pass.

## Out-of-region motion consensus (development follow-up)

A diagnostic now tests each region's accepted LK patches against a motion model fitted **without that region**. This removes self-support: a moving foreground region cannot justify its own consistency by fitting its own points. Each model requires at least3tracks from at least2other regions; the existing partial-affine RANSAC2px scale is retained. Outputs contain model training regions/inliers, median/p90 predicted residual and number consistent within2px. Missing support yields unknown. The module never returns a continuity segment, authorization confidence or player fact.

The source diagnostic exposes accepted tracks through an optional sink; all previous returned measurements remain exactly equal. The old version2script is preserved byte-for-byte in the private archive with SHA`f302d925836a1cc0627ff63b7b09fadf25eca633e66f312986afd61f2a2dbb19`. No production source changes in this follow-up. The former90-frame holdout is explicitly development data now, since its foreground/motion problem informed this instrumentation; it is not reused for qualification.

All150archived source frames and145native adjacent links from both development cohorts are measured, plus three controls. Terminal video/report/frame/code bindings are verified. The original90-frame scene measurements are exactly equal with the optional track sink. Runtime37.116sec; no same-input previous timing for this additional model diagnostic.

At the R1reset link4.119335938, out-of-region residual medians are approximately0.022/0.028/0.039/0.057/0.083/0.047px (thumbnail coordinates). At4.152669271they are0.337/0.142/0.374/unknown/0.559/0.222px. This reinforces the critical-link coherent-scene observation, without classifying uninterrupted game time or authorizing a clock transition.

| Control | Accepted LK patches | Out-of-region residual median | Interpretation |
| --- | ---: | --- | --- |
| Different actual scene | 0 | Unknown in all regions | No correspondence model |
| Previously reviewed discontinuity span | 55 | Regions3/4/5:10.023/9.671/2.776px | Surviving patches do not provide cross-region agreement |
| Identical source image | 138 | Near0px in all six regions | Duplicate-pixel veto remains mandatory |

The discontinuity span had31/19/5patches in regions3/4/5; only0/5/0fit their respective out-of-region models within2px. That is additional independent-of-timer image evidence against treating its55patches as continuity. It is not a general cut detector or a new validation label.

In the three ordinary-motion development spans, at least one modelled region has median residual above2px on27/29,29/29and14/29links:70/87total. This identifies heterogeneous motion/model disagreement, **not semantic foreground by itself**. Camera parallax, 3Dbackground and limited affine model validity can also cause large residuals. Conversely, rigid foreground or view-preserving edits can have low residual. Do not use either error direction alone as a background/cut classifier.

Six new unit cases cover common translation, independent moving-region rejection without self-fit, empty/single-region support, nonfinite coordinates and exact unchanged measurements with track export. Final141related tests pass9.27sec; Ruff passes and mypy101production files passes. No qualified producer, profile adoption, targeted/sampled/full or canonical gain is claimed. Historical23/55/4remains; current/delta unmeasured.

| Metric | Previous | Current | Delta |
| --- | ---: | ---: | ---: |
| Original scene-method returned metrics | Frozen | Exactly equal | 0 |
| Known-span surviving LK patches | 55 | 55 | 0 |
| Known-span peer-prediction residuals | Unmeasured | 10.023 /9.671 /2.776px | — |
| New diagnostic unit cases | 0 | 6 PASS | +6 |
| New qualification / runtime boundaries | 0 /0 | 0 /0 | 0 /0 |

[Source-bound model diagnostics](../e2e_reports/match_001/out_of_region_motion_diagnostics.json). The next production-source requirement remains explicit visibility/background validity and qualified motion/clock separation; this diagnostic supplies the cross-region model checks needed to reject self-supported correspondence. A fresh heldout cohort and real negative controls are still required before adopting an admission rule. No thresholds, GT, ownership, geometry or discontinuity policies are changed here.


### Reviewed-world feature development follow-up

Restricting background labels to actually linked reviewed reference features raises R1descriptive support21→26of29native links and establishes diagnostic pre_round→transient_ui_transition while retaining every display. Whole-crop matching and a three-reference bank had failed the existing preparation-duration gate. No qualification or runtime event follows from training data; R2remains unsupported and canonical Current/Delta unmeasured. The prototype also no longer counts an initially unattested image toward phase duration. All219related cases pass26.05sec, Ruff passes, and production fingerprint matches the earlier mypy102file check. A prospective same-video holdout is frozen before decode. [Evidence, alternative hypotheses, tests and next gate](scene_world_feature_development.md).
