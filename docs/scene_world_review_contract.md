# Frame-bound source-world review contract

## Problem

The frozen R1-adjacent experiment exposed two separate failures: crop coverage under camera motion and unsafe generic world labels. A rectangle outside timer/phase can still contain arms, knife, teammates, nameplates or phase barriers at another camera pose. Geometry/NCC alone does not grant a world label. The priority remains qualified source evidence for `GT-R1-ROUND-START` and the upstream lifecycle/package pipeline. Main is `03bfcbf945fbf3d7b04c54d80b3c5ff103475db0`.

## Evidence

The previous36-native-frame cohort supported0/33links. The2.5second wall seed retained94original feature identities across6regions at the first link but all crop valid fractions were below0.90. The3.0and5.2second seeds visibly contained foreground/UI in fixed footprints. Those latter seeds must be rejected before their features are labelled world, regardless of matching scores.

For this gate replay, the2.502669and2.519336original1920×1080images were independently inspected at original resolution. All six source footprints show wall/markings outside timer, phase, minimap, arms and knife on that pair. Other seed annotations remain conservative: foreground/UI footprints are contaminated, and any unconfirmed footprint is unknown. This is a separate offline review record, not a change to Validation Pack ground truth.

## Competing hypotheses

- Every non-timer crop is world evidence: disproved by actual camera poses.
- World labels can be retained across an unknown frame and reacquired later: prohibited; missing review, occlusion, gap or cut terminates the reviewed chain.
- A frame review makes geometric failure pass: prohibited. It establishes label eligibility only. All existing geometric and photometric predicates still apply afterward.

## Independent image evidence

`FrameWorldReview` records source-video SHA256, the input pixel SHA256, native PTS ticks, source epoch, each footprint's world-only/contaminated/unknown status and review provenance. Here input pixels mean canonical640×360grayscale; the replay separately verifies original native PNG/pixel hashes against the source report before preprocessing. Preprocessing code is fingerprinted in the diagnostic report. A hash binds bytes; it cannot authenticate the truth or independence of a supplied annotation.

The record contains no timer/score/phase value, expected boundary time or round ID. A whole-input hash is provenance, not a timer feature. Invalid/duplicate boxes and timer/phase intersections are rejected. At least three explicitly world-only seed regions are required; the tracker separately retains its spatial-spread and NCC predicates. No region inherits eligibility merely from a different frame or pose.

## Continuity decision

In the three real seed examples, approved seed count changes3hypothetical→1reviewed. The two contaminated/unattested seeds are refused before tracker construction. The wall seed is accepted as eligible, but its next image still yields `original_world_support_insufficient` with exactly the previous tracker result: annotation cannot repair its valid-footprint deficit. No real link or boundary becomes qualified.

## Contract change

The new `ReviewedSceneDiagnostic` is an offline diagnostic wrapper. It leaves the existing tracker, production and recognition policies unchanged. Each next frame needs a matching review of every selected seed footprint, the same video and epoch, exact image binding and the next256-tick native frame. Missing/unreviewed/occluded evidence, explicit discontinuity, repeated/reversed/skipped PTS or invalid provenance terminates the chain and clears world tracks. It cannot reseed/rejoin. Duplicate pixels are still rejected by the underlying tracker even with valid review metadata.

This is deliberately not a production semantic recognizer, qualification, or trusted scene/UI producer. Per-frame offline annotations must not be installed as runtime truth or used to bypass the existing producer boundary. Production bootstrap will need image-matched reviewed references plus independently qualified current-frame world/occlusion evidence, without looking up acceptance times or frame IDs. Global scene evidence must never imply player ownership.

## Tests

The new gate tests include a successful synthetic translation with original identities/NCC>=0.90and no runtime authority; missing/changed source provenance; excluded/duplicate regions; current occlusion; stale/gapped/reversed source progression; epoch change; explicit cut; no reacquisition; and duplicate-image rejection. Existing diagnostic suites remain included. [Real seed replay](../e2e_reports/match_001/scene_world_review_gate_development.json) binds native source, preprocessing, tracker and gate bytes. [Verification](../e2e_reports/match_001/scene_world_review_gate_verification.json) records terminal test/static-check results. Windows execution is not verified; no OS-specific policy is added.

## Previous / Current / Delta

| Same three-seed diagnostic metric | Previous | Current | Delta |
| --- | ---: | ---: | ---: |
| Hypothetical/eligible tracker initializations | 3 | 1 | -2 (-66.67%) |
| Unsafe or unattested seeds refused before extraction | 0 | 2 | +2 |
| First-link descriptive support | 0 | 0 | 0 |
| Qualification created | 0 | 0 | 0 |
| New runtime events | 0 | 0 | 0 |

The counts measure diagnostic eligibility, not accuracy improvement. Earlier R1development22/29remains a stored observation; it is not rerun or reclassified. Canonical historical23PASS/55FAIL/4NEand negative/discontinuity0/0remain the accepted baseline; Current/Delta are unmeasured. All82stored assertion statuses stay unchanged. No targeted, sampled or full canonical evaluation is claimed.

## Remaining blocker

The next source-appearance task is to account for projected world footprints under camera motion while excluding unreviewed pixels and current foreground/UI. The wall pair's94distributed original correspondences are distinct evidence from its failed whole-crop coverage. The0.90valid-coverage and NCC floors stay fixed. Any new appearance domain or evidence combination must be declared before evaluation and qualified on disjoint data; newly exposed cohort images are development if used to design it. Missing runtime seed/occlusion qualification cannot be filled by copying these offline annotations into production. R2start/result-banner qualification remains separate. Full E2E is not justified before the real three-boundary gate, and the overall lifecycle goal is unfinished.
