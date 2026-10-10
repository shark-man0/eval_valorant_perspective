# Frozen joint scene cohort: exposure and upstream failure

## Problem

`GT-R1-ROUND-START` has joint appearance support on5exposed critical links, but that is not independent qualification. Freeze the unchanged source chain/joint audit and test other continuous camera poses, checking both encoded and decoded exposure before any qualification claim.

## Evidence

Main `80d0d460b8e3a76d3c181e035c72cd10026f4252`. The predecode inventory hashes2154existing PNGs and407native decoded images. It took78.897191seconds. A frozen reservation covers3.35–3.55,4.5–4.7and6.0–6.2seconds,12native images each. All gaps are256ticks at1/15360; source/code/PNG hashes verify at completion. Inputs are one recording and temporal neighbors, not independent videos.

## Competing hypotheses

Joint appearance might generalize to nearby camera poses, or source initialization/model eligibility might fail before the joint stage. Merely extracting a new filename may also hide prior exposure. These outcomes must be separated from precision/negative-control results. No adjustment follows this cohort.

## Independent image evidence

| Interval | Frames / links | PNG / decoded overlaps | Tracker support | Joint stage evaluated | First-link model inliers |
| --- | --- | --- | ---: | ---: | --- |
| [3.35, 3.55] | 12 / 11 | 12 / 12 | 0 | 0 | 29/39 (74.36%) |
| [4.5, 4.7] | 12 / 11 | 3 / 3 | 0 | 0 | 16/19 (84.21%) |
| [6.0, 6.2] | 12 / 11 | 0 / 0 | 0 | 0 | 46/55 (83.64%) |

15/36images overlap prior PNGbytes and decoded native pixels. The first interval is entirely exposed; the second has3overlaps and cannot be called an independent continuous holdout. The third has0stored-pixel overlaps but is still same-recording evidence. Every interval fails the unchanged >=0.90original model consensus on the first link, then terminates without rejoining. No joint camera transform is available for a subsequent link. Joint accuracy is therefore **not evaluated**, not0/33incorrect.

All36full-context source panels were inspected after prediction. Fixed footprints contain moving players, arms/knife, barrier or player UI in these views; seeds are not attested world-only. Images look visibly continuous within each episode, but this review does not certify hidden uninterrupted game time or provide runtime labels. These are now exposed diagnostic inputs and must not be reused as fresh holdout. No image-only seed producer selected valid world-only identities, so this cohort is not end-to-end qualification of that missing producer.

## Continuity decision

Missing source model remains unknown rather than a cut classification. No source segment is bridged after failure. The absence of positive outputs on contaminated/occluded scenes is useful rejection behavior, but upstream abstention cannot establish the joint stage's negative-control false-positive rate. Explicit cut/duplicate/occlusion controls for the complete producer still remain necessary.

## Contract change

The existing common Python cohort runner gains an opt-in joint audit. Both joint modules must be frozen before decoding. Default orchestration remains unchanged. The audit consumes exact measured adjacent transforms only when available; it cannot synthesize them, revive terminated tracks or install qualification. It records decoded-pixel overlap in addition to PNGbytes so recompression cannot silently create holdout. No production/frame sampler/GT/assertion changes were made.

## Tests

15focused tests pass in2.92seconds: native coverage/file binding, strict optional joint configuration/code freezing, and all prior joint/domain cases. Ruff passes `src tests scripts/e2e` and the cohort runner; `git diff --check`passes. Production source remains unchanged from the preceding mypy104file PASS. Windows execution is unverified; the runner remains shared pathlib/Python/FFmpeg/OpenCV.

## Previous / Current / Delta

| Metric | Previous | Current | Delta |
| --- | --- | --- | --- |
| Exposed R1joint local appearance | 5/5 | Not rerun | Unmeasured |
| Fresh reserved cohort tracker support | Unmeasured | 0/33 | Not comparable |
| New cohort joint-stage accuracy | Unmeasured | Not evaluated (no camera model) | Unmeasured |
| Qualified continuous holdout episodes | 0 | 0 | 0 |
| Runtime qualifications/events | 0 | 0 | 0 |
| Canonical PASS / FAIL / NE | Historical23/55/4 | Not rerun | Unmeasured |
| Canonical negative / discontinuity violations | Historical0/0 | Not rerun | Unmeasured |

The36-frame cohort finished in 35.289402seconds. The source inventory is a separate78.897191seconds. Neither is comparable to a full E2E runtime, and no full E2E was started.

## Remaining blocker

The limiting prerequisite is image-derived eligibility/initialization of reviewed source-world identities, not joint threshold selection. Fixed coordinates cannot declare every new camera pose to be world-only. Complete the portable image-only reference/seed producer before calling another arbitrary-pose cohort a positive qualification set. It must bind profile/reference pixels, current structural matches, ambiguity and limited witness scope without time/hash annotation lookup, player ownership or whole-ROI semantic claims from mean NCC. Current occlusion and independent scene/UI qualification still gate runtime activation. R1remains first priority; R2/end work remains separate. All82stored assertion statuses are unchanged.
