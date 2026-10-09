# Reviewed-world feature continuity: development result

## Problem

Fixed camera ROIs can contain hands, weapons and teammates. Conversely, whole-crop NCC can reject a visible world surface after camera motion. R1's independently supported UI transition cannot enter production merely by declaring every fixed crop to be background. The immediate target remains source evidence for R1 start, upstream of the round lifecycle/package failures; no canonical assertion is changed here.

Base HEAD: `0a606a0a3edb19ba4cd10d8007c2d045c39b2006`. Source SHA256: `71d58558559d6f578433ce9f234bf176f76fd5a86657dbfe3eba1e7d36136b06`.

## Evidence

The reference study uses all150previously decoded development frames. A single reviewed world view supports4/30R1frames with a global partial affine and6/30with regional affine; these frame counts include the source reference itself and are not continuity counts. The other120development frames have no distributed reference support. Existing source hashes, every native PTS, exact PNG/pixel hashes and terminal code/video hashes are checked. One reference is insufficient qualification and supplies no new holdout.

Four training images from the30-frame R1 archive were reviewed at full context: images1,2,8and16. The first two and middle image represent observed camera poses. Image8 is the middle pose of an image-only support gap. No expected timer, score, timestamp, round ID or acceptance window selects these assets or scores correspondence. Known world wall/crack regions0–4are used; region5is conservatively excluded. Each reference contains the same reviewed world context, but it does not label all future ROI pixels as world.

## Competing hypotheses

1. A single world reference generalizes sufficiently through the camera motion. Rejected on development inputs.
2. Whole-crop affine reference matching plus several poses supplies a complete preparation span. It supports the critical UI links, but leaves an earlier gap; the last supported phase span is33.333ms, below the unchanged50msconfirmation requirement.
3. Reference-attested **feature identities**, rather than all pixels in a crop, preserve world correspondence through perspective/motion changes. This is supported on the current development images and still needs independent qualification.

An exploratory projective fit improves some adjacent reference poses but does not establish a complete whole-region contract; no homography route is adopted. The default partial-affine measurement outputs remain exactly equal to the earlier single-reference report. Original module/runner versions are retained in the private scene-reference development archive; older reports bind their historical code bytes, not subsequently changed scripts.

## Independent image evidence

Local pyramids see only reviewed reference boxes. Accepted reference points require15×15patch NCC≥0.90, forward/backward error≤1px, and finite source coordinates inside the crop margin. Reference-to-current partial-affine RANSAC retains2pxscale. Only model inliers are used and both frames require≥90%model inliers among accepted reference tracks.

An adjacent link must match the **same reference point identities** at both ends. At least three reviewed regions and three spatial witness cells spanning two rows/two columns are required at **both** source endpoints. Unmatched pixels remain unknown. Foreground cannot inherit a whole region's background label merely because other pixels match. These checks are descriptive and do not certify uninterrupted gameplay time or scene-preserving-edit absence.

At the first `2:25` link, reference8supports72shared world features (minimum patch NCC0.9124) and reference16supports88(minimum0.9017), distributed at both endpoints. At the first `1:39`, reference16supports90(minimum0.9050). Neither timer nor phase ROI enters these image measurements. No source frame is skipped.

The actual different-view/discontinuity control images have no supported world-reference IDs and no shared previous-reference support under this feature method. They remain development negatives, not independent qualification. Duplicate images would still match the reference; duplicate-pixel/PTS/content vetoes remain mandatory.

## Continuity decision

The successful development result narrows the earlier blocker: background eligibility can be attached to **matched reviewed world patches**, while full-ROI eligibility is unnecessarily broad and brittle. It supports R1 visible scene continuity through the transient display sequence, not a claim of uninterrupted gameplay time. R2 stays unknown through its different/occluded view; the same frozen rule adds no supported link there.

No production qualification, source proof, profile installation or event is generated. The real analyzer still lacks the qualified scene/UI producer. The remaining requirement is independently reviewed holdout/negative validity and then the trusted producer integration; successful development matches alone cannot satisfy that gate.

## Contract change

Changes here are diagnostic-only. Optional world-track export preserves every previous reference measurement. A separate helper tests shared world identities without exporting a runtime continuity token. Native background scoring precedes joining archived observed phase/display annotations; those annotations do not select references or score the image method.

The diagnostic temporal prototype also had a concrete defect: its first unqualified image could contribute a phase observation because there was no previous PTS. It now clears context whenever image support is absent, including the first frame. Missing support is not labelled a cut. A regression test requires a new positively supported phase span after that first abstention. The earlier script is preserved byte-for-byte with SHA`f934cb25c27d277b671369f18738a1aa2a3240e0545eca2b6f57b911b3bec9de`.

## Tests

New cases cover translation/reference matching, exact excluded-pixel invariance, foreground replacement, weak texture, duplicate-match limitations, invalid crops, shared regions at both ends, unchanged outputs with feature export, crop-local projective validity, exact world-feature identity, NCC/FB/inlier vetoes and two-endpoint spatial spread. The initial-unsupported-phase regression closes the prototype defect.

Final selected scope: **219 related unit tests PASS (26.05sec), Ruff PASS**. Production source is unchanged in this follow-up; the earlier mypy102file PASS remains applicable and is fingerprint checked in the verification metadata. No full regression, fresh canonical E2E or Windows runtime validation is claimed.

## Previous / Current / Delta

| Same native inputs | Previous | Current | Delta |
| --- | ---: | ---: | ---: |
| R1 descriptive supported links /29 | 21 whole-region bank | 26 world-feature bank | +5 (+23.81%) |
| R2 descriptive supported links /29 | 0 | 0 | 0 |
| R1 `pre_round` prototype outputs | 0 | 5 | +5 |
| R1 `transient_ui_transition` outputs | 0 | 15 | +15 |
| Actual new runtime qualification / events | 0 /0 | 0 /0 | 0 /0 |
| Canonical PASS / FAIL / NE | Historical23 /55 /4 | Not rerun | Unmeasured |

The evidence unit changes from whole regions to linked world patches; +5is developmental coverage, not demonstrated accuracy gain or threshold equivalence. R1current prototype outputs are7unobserved/3phase_candidate/5pre_round/15transient; R2is30unobserved. Every raw `0:00`, `2:25` and `1:39` display remains in history. No round event is authorized.

Whole-region four-reference wall time20.004sec and verified-control world-feature wall time20.288sec: +0.283sec(+1.42%). These short runs compare different descriptive checks on the same native inputs; they are not an E2E speed or correctness result. All benchmark processes completed with blocking waits; no full E2E ran.

## Remaining blocker

The candidate is frozen before a newly reserved same-video cohort is decoded. [Reservation](../e2e_reports/match_001/scene_world_feature_holdout_reservation.json) binds code, references,152known development/control image hashes and six explicit prospective native intervals. Review labels are deliberately unassigned. The cohort is correlated same-video evidence, not independent lifecycle episodes. It must not be reused as holdout if it informs a redesign.

Next: decode/review that cohort, evaluate foreground/alternate-view negatives and world correspondence, then implement the trusted source producer only if qualification is justified. Positive phase disappearance and current-frame original timer/display qualification remain separate producer requirements. R1-end result qualification remains separate. Default production behavior, NCC0.90, identity/ownership/geometry/OCR/discontinuity policies, GT/assertions and full sampler are unchanged. No package FAIL or canonical PASS gain is claimed.

Current authoritative development artifacts:

- [Single reference,150frames](../e2e_reports/match_001/scene_reference_support_diagnostics.json)
- [Whole-region pose bank](../e2e_reports/match_001/scene_reference_bank_motion_bridge_diagnostics.json)
- [World-feature bank with matching control method](../e2e_reports/match_001/scene_world_feature_bank_verified_controls.json)
- [Continuous descriptive replay](../e2e_reports/match_001/scene_world_feature_verified_temporal_replay.json)
- [Initial unsupported-phase correction replay](../e2e_reports/match_001/transient_ui_initial_support_fix_replay.json)
