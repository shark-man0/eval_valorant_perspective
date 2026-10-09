# Qualified transient UI lifecycle contract

## Problem

R1's visible `0:00 → 2:25 → 1:39` cannot be treated as either an ordinary clock reset or an OCR correction. The legacy timer-dependent continuity proof rejects it. The independent scene investigation supports continuity of the visible camera scene at these links, but cannot exclude a scene-preserving edit. See [source measurements and competing hypotheses](r1_scene_transition_investigation.md).

## Evidence

The native source shows phase disappearance at4.102669271sec, `2:25` at4.119335938and4.136002604, then `1:39` at4.152669271. These PTS and values are diagnostic observations, never production constants. Every raw display remains intact. No real start/end has been emitted by this follow-up.

## Competing hypotheses

Temporary UI transition is better supported than whole-camera replacement at the critical R1 links. An edit preserving the same scene remains unresolved. A low NCC during camera motion is not itself a cut; correspondence over a player/weapon overlay is not itself proof of world continuity.

## Independent image evidence

Six crop-local NCC and bidirectional patch tracks exclude timer/phase pixels. At the first `2:25`, minimum crop NCC is0.995436 with135accepted tracks in six regions. At `1:39`, minimum NCC is0.946006 with137tracks in five regions. Leave-one-region-out motion residuals are below0.56px in available groups at these two links. A saved real discontinuity retains55patch tracks but peer residual medians10.023/9.671/2.776px. Thus neither single NCC nor track count alone qualifies continuity. Detailed measurements, exact hashes, controls and code versions remain in the linked investigation reports.

## Continuity decision

Diagnostic decision: **visible scene continuity / temporary UI transition supported for R1's critical links; uninterrupted gameplay time unproven**. Fixed crops fail universal background qualification on the withheld same-video cohort, with foreground contamination and camera-motion abstention. R2's purple occlusion remains inconclusive. That cohort is now development data and cannot qualify a redesigned method as independent holdout.

Runtime decision: remain fail-closed until a trusted producer supplies qualified scene-only continuity and positive UI-transition evidence. The existing timer-dependent `global_continuity` proof cannot authorize this route. Explicit discontinuity, gap, duplicate pixels, epoch change or broken source-hash linkage cancels pending context. No threshold is reduced.

## Contract change

The shared Python lifecycle has an **opt-in** `pre_round → transient_ui_transition → round_active` route. A profile/code-bound qualification report must contain paired `scene_continuity` and `ui_transition` components in addition to existing core qualification. They require distinct reviewed training/holdout/negative hashes, no reviewed wrong/false-positive cases, and existing minimum support. Reports contain no expected clock values, acceptance windows or round IDs.

Opening a candidate requires confirmed preparation, an accepted source-preserved phase clock, positive current-frame `phase_disappearance` evidence bound to the current source pixel hash/PTS, and clock-independent scene evidence. Phase absence alone does not open it. Scene proof requires distinct linked source hashes, distributed high-NCC witnesses, background validity and matching profile/code fingerprints; declarative fields alone are not source qualification.

Every observed transient display/value is recorded. Changed clock values restart the coherent-clock confirmation window; they are not erased or reformatted. At least two accepted display observations across the existing0.05sec confirmation duration are required. The existing1sec maximum candidate duration applies. The event timestamp is the first positively evidenced UI transition; confirmation PTS and all intervening samples stay in provenance. These rules contain no `2:25`, `1:39`, source-video timing or GT constants. A stable but wrong UI display remains a producer qualification risk, not something these temporal tests prove safe.

Events remain system-level, independent of player identity. No HP/weapon/death/shot ownership is granted. The native builder, package association and trace retain actor/time/type/provenance and preparation context. Legacy qualified lifecycle uses its existing route; default recognition remains unchanged. Adding source modules changes the recognizer fingerprint, so old qualification cannot be reused.

**Integration status:** the real analyzer does not yet produce `global_scene_continuity` or `global_ui_transition`. Supplemental external `global_*` tokens are filtered. No real paired qualification/profile is installed. Consequently this new runtime route abstains, with an explicit diagnostic reason, on the current source pipeline. This is implemented downstream contract work, not completed real-source detection.

## Tests

Synthetic contract tests cover retained anomalous displays, confirmation, duplicates, missing/weak proof, current PTS/hash binding, explicit cuts, gaps, pixel duplication, epoch changes, menus, spectator state, phase jitter, identity isolation and native/package/trace preservation. A two-round fixture confirms separate package IDs, second-round preparation provenance and one end only. Existing analyzer security cases now explicitly reject externally forged scene/UI tokens.

Fixtures qualify only the contract within temporary unit directories; they are never real-source qualification assets. Related regression results are recorded in [verification metadata](../e2e_reports/match_001/transient_ui_contract_verification.json). Ruff and mypy apply to the shared production code. Windows runtime remains unverified.

## Previous / Current / Delta

| Metric | Previous | Current | Delta |
| --- | ---: | ---: | ---: |
| Production transient state contract | Absent | Opt-in implementation | Added |
| Qualified real scene/UI producer | 0 | 0 | 0 |
| Real-source boundaries newly accepted | 0 | 0 | 0 |
| Canonical PASS / FAIL / NE | Historical23 /55 /4 | Not rerun | Unmeasured |
| Canonical negative failures / discontinuity violations | Historical0 /0 | Not rerun | Unmeasured |

No canonical assertion changes are claimed. Unit fixtures do not supply Current canonical metrics. Targeted/sampled/full E2E is not rerun simply to exercise an inactive route; the three real-boundary acceptance gates are unmet.

## Remaining blocker

Next task: a trusted source producer with explicit visible-background/foreground validity and positive phase/UI transition evidence, qualified on reserved independent same-video holdout plus natural cuts, duplicates, occlusions and scene-preserving-edit limitations. Apply the frozen R1 contract to R2 only after its occlusion evidence is adequate. R1-end `TEAM ACE` reference qualification remains separate; NCC0.388 is not promoted by threshold tuning. GT, assertions, sampler, geometry, ownership and OCR acceptance are unchanged.

Current follow-up verification: **200 related unit tests PASS (24.97sec), Ruff PASS, mypy102source files PASS**. No fresh canonical E2E or real-source qualification is claimed.


### Reviewed-world feature development follow-up

Restricting background labels to actually linked reviewed reference features raises R1descriptive support21→26of29native links and establishes diagnostic pre_round→transient_ui_transition while retaining every display. Whole-crop matching and a three-reference bank had failed the existing preparation-duration gate. No qualification or runtime event follows from training data; R2remains unsupported and canonical Current/Delta unmeasured. The prototype also no longer counts an initially unattested image toward phase duration. All219related cases pass26.05sec, Ruff passes, and production fingerprint matches the earlier mypy102file check. A prospective same-video holdout is frozen before decode. [Evidence, alternative hypotheses, tests and next gate](scene_world_feature_development.md).
