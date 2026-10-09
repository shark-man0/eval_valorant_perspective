# R1 scene continuity: joint feature structure trial

## Problem

Single world patches on the R1 wall often have several NCC≥0.90destinations. Wider reciprocal search did not qualify the reference bank. This trial asks whether the **relative spatial arrangement** of those patches resolves their ambiguity without timer, phase, expected timestamps or round IDs.

The worktree base remains main `0a606a0a3edb19ba4cd10d8007c2d045c39b2006`. The previous goal turn produced image/rejection evidence; this is a new diagnostic hypothesis, not a status-only continuation or a production candidate.

## Evidence

The same reviewed image reference16and four existing native poses are used: the critical R1 display-transition pose, an earlier R1 pose, a returning pose and a later pose. PNG/pixel hashes, original report hashes, method code and source video SHA256 are checked before/after measurement. All four images are development, including previously heldout images consumed by the earlier redesign. No fresh holdout is claimed.

Two explicit runs are preserved: [all reference patches](../e2e_reports/match_001/scene_constellation_development.json) and [reference-only eligibility](../e2e_reports/match_001/scene_constellation_reference_eligibility.json). The second removes21of114source patches because their own reference image already exceeds the finite candidate-peak budget. This is static source eligibility, not discarding inconvenient current-frame mismatches.

Four isolated poses test image-method feasibility only. They are not continuous lifecycle validation, targeted/sample/full E2E, or proof of an event. The first run's exact helper/runner bytes are retained with SHA-derived filenames in the private `scene-constellation-20261009` archive.

## Competing hypotheses

1. Joint relative patch structure resolves the repeated-wall ambiguity and transfers to the nearby poses.
2. Weak/repeated image structure produces too many alternatives for the bounded matcher to assess, while changed appearance/pose prevents a coherent constellation elsewhere.
3. Unsupported images prove a content cut.

Synthetic joint-structure tests establish that the method can resolve individual ambiguity when exactly one distributed translation exists. The actual images do **not** qualify this implementation. Hypothesis2explains its explicit rejection stages; hypothesis3is unsupported. This is not proof that every spatial/affine/projective method must fail.

## Independent image evidence

Each15×15reviewed world patch supplies NCC≥0.90candidate peaks across the existing non-UI crops. Peaks outside a2pxneighbourhood are retained as alternatives. If more than32distinct qualified peaks remain in a crop, the pose is unknown: truncating the candidates and then declaring a unique motion is forbidden.

Every occupied2pxtranslation bin is assessed. A descriptive constellation must explain≥90%of features having qualified candidates, with at least three reviewed source regions and source/current witness cells spanning two rows/two columns. A distinct competing accepted translation more than2pxaway causes abstention. Reciprocal correspondence must retain≤1pxerror and≥90%feature support. The translation-only model does not certify rotation, depth/parallax, foreground eligibility or uninterrupted time. Quantized hypotheses are a bounded diagnostic model, not an exhaustive uniqueness proof over all possible camera transforms.

| Pose | All114reference patches | Static eligibility:93patches |
| --- | --- | --- |
| Critical R1 pose | Candidate peak budget exceeded | Candidate peak budget exceeded |
| Earlier pose | No coherent distributed constellation;27eligible current features | No coherent distributed constellation;16eligible current features |
| Returning pose | Candidate peak budget exceeded | Candidate peak budget exceeded |
| Later pose | Candidate peak budget exceeded | No coherent distributed constellation;54eligible current features |

Every pose yields0accepted tracks under this method. Candidate-budget rejection means **unassessed alternatives**, not an absent or contradicted scene correspondence. Removing source-intrinsically ambiguous patches does not establish qualification. Candidate limits and NCC are not relaxed to obtain a match.

## Continuity decision

Do not deploy this constellation trial. Its four-image result does not overturn the earlier distributed NCC/LK/world-feature evidence supporting visible R1 scene continuity through `0:00 → 2:25 → 1:39`. Nor does that earlier evidence prove uninterrupted gameplay time or exclude a scene-preserving edit.

No cut label, runtime continuity token, round event, qualification or profile is generated. R2thresholds and R1-end TEAM ACE acceptance are untouched. This bounded trial supplies no evidence to revisit their thresholds.

## Contract change

No production contract changes. The added diagnostic makes whole-model ambiguity explicit instead of selecting a convenient individual peak. Static reference eligibility is source-only; a selected feature exceeding the budget in the current image still vetoes the pose.

The existing opt-in transient-UI lifecycle keeps every timer display and requires independently qualified scene/UI producers. This trial cannot supply that qualification. Default runtime, identity/ownership, NCC0.90, geometry, OCR, discontinuity safeguards, GT, validation/assertions, full sampler and package/evaluator semantics are unchanged. The helper emits `runtime_proof_authorized=False` even for synthetic successful correspondences.

## Tests

New unit tests cover resolved individual ambiguity, a second complete constellation, fragmented motion, insufficient region/cell spread, insufficient90%feature consensus, exact excluded-pixel invariance, textureless inputs and candidate-budget overflow without hiding remaining peaks. Actual-image diagnostic runs exited0 with terminal input bindings intact. Verification is recorded in [current worktree checks](../e2e_reports/match_001/scene_constellation_verification.json).

Neither run measures a continuous boundary. No sampled/full E2E or full regression is justified by these rejected source inputs. The short four-pose CLI initially did not record wall-clock duration; runtime comparison is unavailable and is not reconstructed from tool observation timing. Windows numerical/runtime behaviour remains unverified.

## Previous / Current / Delta

| Metric on four corresponding poses | Previous reciprocal single-patch search | Current all-patch constellation | Delta |
| --- | ---: | ---: | ---: |
| Critical pose accepted reference16tracks | 22 | 0 | -22 |
| Earlier pose tracks | 1 | 0 | -1 |
| Returning pose tracks | 3 | 0 | -3 |
| Later pose tracks | 4 | 0 | -4 |
| Actual new qualification / boundaries | 0/0 | 0/0 | 0/0 |
| Canonical PASS / FAIL / NE | Historical23/55/4 | Not rerun | Unmeasured |

The methods have different correspondence/coherence contracts; track-count changes are not accuracy changes. Reference-only eligibility still returns0tracks in all four poses. Prior 96-framecomparison runtime157.137sec does not apply to this four-pose trial. All82assertion statuses remain unchanged; no negative/discontinuity regression result is newly claimed.

## Remaining blocker

Adding a joint translation test alone does not solve background reference eligibility/pose coverage. The next useful work is to review which **source background structures** remain distinguishable over normal camera changes and represent that coverage in a common reference/profile contract. Larger or spatial descriptors and additional reviewed poses need independent qualification; they must not be selected using expected clock values or GT boundaries. The consumed cohorts remain development.

Trusted scene-only and positive UI-transition producers remain missing. R1start qualification is the priority; R2transfer and R1-end result-banner qualification remain separate. Native package separation and canonical PASS gains are still unproven. A future implementation must not turn these failed diagnostic alternatives into an enabled producer by configuration alone.
