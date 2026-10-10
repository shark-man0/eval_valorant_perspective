# Observed source seed to continuous joint scene links

## Problem

`GT-R1-ROUND-START` needs native source-safe independent scene evidence. Stateless reference reacquisition failed changed poses; reviewed per-frame world masks cannot provide runtime truth. Connect an image-supported actually observed first frame to the retained source-identity chain and joint appearance while keeping source time and reference assets distinct.

## Evidence

Main `80d0d460b8e3a76d3c181e035c72cd10026f4252`. One existing reviewed reference profile supplies an initial image-only proposal. The actual native input, not the reference asset, supplies first PTS and full-resolution pixel hash. Thirty native images/29links are frozen at3.902669–4.386003seconds with256tick gaps at1/15360. Source/profile/asset/code/PNG/pixels verify before and after replay. All are exposed development data; this is not independent holdout qualification.

## Competing hypotheses

The measured adjacent chain might require hand-written current-frame masks, or its original identities and complete joint domain appearance may suffice for descriptive visible-scene evidence from an observed seed. Reference assets might also incorrectly supply prior native time/confidence. Finally, unknown source gaps/cuts/duplicates could silently reacquire a reference unless termination is explicit.

## Independent image evidence

The observed first native image passes source-domain reference matching, then establishes the previous-source snapshot at its actual PTS and native pixel hash. It emits no temporal link and contributes no invented reference-to-native duration. Original reviewed source identities are retained; no new GFTTidentities are extracted from unreviewed current crops. Every next link requires complete native cadence, source epoch, distinct native pixels, unchanged original/adjacent model/NCCconsensus and distributed joint local appearance. Matching consumes no timer, phase, expected value, boundary window or per-frame current semantic annotations.

| Critical native PTS | Descriptive observed scene link |
| --- | --- |
| 4.102669 | True |
| 4.119336 | True |
| 4.136003 | True |
| 4.152669 | True |
| 4.169336 | True |

22/29links pass. They include phase disappearance, both2:25images, first1:39and the following native image. At4.286003the existing original camera-model consensus fails; all later images remain `episode_terminated` without rejoining. No timer display is skipped, corrected or used by the scene observer. This has the same descriptive count as earlier manually reviewed replay, but the actual observed source chain now needs no current-frame manual mask input.

## Continuity decision

The continuous observed-image evidence supports visible scene continuity with a transient UI display sequence on these exposed frames. It does not certify uninterrupted hidden game time, full camera-model uniqueness, semantic absence of small foreground or temporal clock qualification. Source-domain bootstrapping still only passes the self-reference pose in the stateless eight-image development check; broad independent acquisition coverage is unproven. Runtime scene/UI qualification remains absent and production fail-closed behavior is unchanged.

## Contract change

`ObservedSceneChain` is a diagnostic integration outside production. A static asset may supply reviewed source identity structure but never previously observed native PTS/pixels. Initialization establishes only an actual source observation. Non-identical initialization additionally requires original reference-identity binding; failures terminate. Subsequent proposals carry actual previous/current native hashes/PTS and source epoch, plus limited-scope joint appearance. Native spacing is an explicit metadata input, not an OS or GT rule. A cut/epoch/gap/duplicate/invalid input or image evidence failure clears prior state and permanently terminates the object; there is no hidden reseeding. Results always have `runtime_proof_authorized=false`, `world_mask_authorized=false` and `qualification_created=false`. No player facts, round events, packages or trace evaluations are emitted.

## Tests

13related unit cases pass in15.31seconds: five initializer and eight observed-chain cases, including real native previous-pixel/PTS binding under synthetic camera motion, no reference-as-prior-frame, gap/epoch/cut/duplicate/invalid-image termination, no reacquisition and unknown initial image refusal. Ruff passes `src tests scripts/e2e` and the observer; `git diff --check`passes. Production source is unchanged from the preceding104file mypy PASS.

Four real-image protocol controls (gap, duplicate, explicit cut, changed epoch) produce0scene links and stay terminated. Two additional **image-only synthetic negative timelines** (different actual camera scene and distributed occlusion) also produce0links and no rejoin without supplying an explicit cut flag. They preserve original image provenance but assign a counterfactual contiguous test timeline; original video, GT and runtime timestamps are not modified. These are exposed controls and cannot establish independent false-positive rates.

## Previous / Current / Delta

| Metric | Previous | Current | Delta |
| --- | ---: | ---: | ---: |
| Same-input manually reviewed / image-derived descriptive source links | 22/29 | 22/29 | Count0; input contracts differ |
| Critical exposed source links | 5/5 | 5/5 | 0 |
| Native continuity links emitted at initialization | 0 | 0 | 0 |
| Four protocol-control links | Not measured for integration | 0/4 | Not comparable |
| Two image-only synthetic negative links | Not measured for integration | 0/2 | Not comparable |
| Runtime scene/UI qualifications | 0 | 0 | 0 |
| Canonical PASS / FAIL / NE | Historical23/55/4 | Not rerun | Unmeasured |
| Canonical negative / discontinuity violations | Historical0/0 | Not rerun | Unmeasured |

Replay plus four protocol controls took 55.721315seconds. It includes initialization/joint-lattice instrumentation and is not comparable as a speed benchmark to the previous single-tracker replay. No full E2E was started.

## Remaining blocker

Freeze this complete observed source route for independent continuous acquisition/holdout/negative assessment, not isolated reference self-matches. The qualifying producer must address current foreground/occlusion eligibility with its explicit limited footprint scope, full hypothesis scope and paired positive UI-transition evidence. Add score/confidence/source/profile/code provenance before any native production evidence contract is installed; no diagnostic report is runtime truth. No static reference or annotation lookup may supply temporal duration. R2start and result-banner qualification remain separate, and canonical lifecycle/package/evaluator acceptance is still unverified. All82historical assertion statuses are unchanged. Windows execution remains unverified.


## Decoder-boundary fail-closed followup

Problem / evidence: `_prepare` accesses `.shape` on non-array input. A list, mapping, scalar or decoder error string raised `AttributeError` while retaining the prior native observation. Also false-like, non-boolean discontinuity values were accepted as continuity. These are decoder/metadata contract defects, not evidence that the real video contains a cut.

Change: the diagnostic observer requires an ndarray before image preparation and an explicit boolean discontinuity value. Malformed image or source binding clears both tracker and previous observation and terminates the episode permanently. Valid native image matching, NCC floors, source spacing and production behavior are unchanged.

Tests: 22 observed-chain/initializer tests PASS in 27.03s, including nine new malformed-frame/unknown-cut cases after an established seed; Ruff PASS; mypy PASS (104 production source files); diff whitespace check PASS.

Previous / Current / Delta: malformed input regression coverage 0 / 9 / +9 cases. Canonical results remain historical 23 PASS / 55 FAIL / 4 NE; current and delta are unmeasured. Prior exposed 22/29 image links are historical measurements of the earlier observer revision, not a rerun of this change. No targeted, sampled or full E2E was launched because this diagnostic input guard does not enable a qualified production boundary producer.

Remaining blocker: independently qualified source/UI evidence, measured confidence and source/profile/code provenance before production activation. This fix provides no new round event or assertion PASS. Windows execution remains unverified.


## Measured witness provenance replay

Problem: earlier observed native links retained source hashes/PTS and witness IDs but discarded the actual appearance measurements and fixed camera transform. This prevented checking which pixel-domain evidence produced a proposal.

Change: every successful diagnostic link now retains the profile byte SHA256, reviewed reference ID, previous-to-current 2x3 affine transform in 640x360 coordinates, and each fixed-projection witness's source box and measured NCC. `minimum_witness_ncc` is the minimum of exactly those supporting witnesses; it is explicitly an appearance score, never a calibrated confidence for hidden game time or semantic absence of foreground. Joint acceptance and all thresholds are unchanged. The surrounding frozen replay manifest binds source video SHA256, native time base, input PNG/native hashes and observer/dependency code; terminal verification confirms these inputs did not change. This external manifest remains offline evidence and is not runtime authorization.

Tests: 30 observed-chain/initializer/joint cases PASS in 27.88seconds. Motion assertions verify that the reported transform maps the actual previous source image, that profile/ROI values match the declared reference, and that output JSON contains no NaN. Ruff PASS. Production code unchanged; preceding mypy PASS covers104source files. All82historical assertion rows retain their original digest.

Evidence: a new frozen replay of30already-exposed native R1frames takes 47.621045seconds. Links remain22/29, critical source links remain5/5, all22successful links now include measured witness provenance. The minimum supporting NCC across those links is 0.909788072. No old report is overwritten. Source/profile/assets/code/PNG terminal hashes match the declaration. No current-frame manual masks, timer/phase values or validation assertions are observer inputs.

Previous / Current / Delta: descriptive links22/29 /22/29 /0; links retaining witness measurements0 /22 /+22. Runtime47.621seconds versus the earlier55.721seconds is not a speed comparison because the earlier run included four extra protocol controls. Canonical PASS/FAIL/NE remain historical23/55/4; Current and Delta are unmeasured. No full E2E was started and no new round events or packages are claimed.

Remaining blocker: the source route is still exposed, unqualified and diagnostic. Independent continuous acquisition/negative/holdout assessment, foreground scope, paired current UI transition evidence and trusted runtime producer binding remain required before activation. This report does not solve static initialization coverage or R2/end qualification. Windows execution is unverified.
