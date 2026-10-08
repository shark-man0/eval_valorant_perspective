# Purchase-phase reference qualification

## Current follow-up: structural reference and phase contract

The sections below record the initial unmasked experiment. The current working-tree follow-up adds an opt-in `semantic_text_ncc_v1` profile matcher and an independent phase-confidence contract; the safe default profile remains unchanged. Training uses the same three R1 crops, excluding numeric fields. A frozen stable-foreground mask with a one-pixel contrast ring is split into three support groups. Every group must independently reach NCC 0.90. Invalid profiles fail closed, and this matcher cannot replace identity or spectator evidence.

After freezing the mask, 21 additional frames were selected and reviewed before prediction: eight purchase-phase positives and thirteen negatives. Production matching accepts all eight positives and none of the negatives. On these same frames, the previous unmasked reference accepted seven positives. The previously reviewed R2 cohort is a regression control rather than fresh holdout: seven of eight positives now match; PTS 103.002669 remains unknown. No threshold was relaxed to accept it.

The production phase tracker requires corroborating frames over at least 0.05 seconds and resets on missing evidence, invalid geometry, discontinuity markers or a gap exceeding one second. It preserves unknown player identity and unknown numeric values. Independent phase confidence travels through the existing ROI-confidence field to trace state intervals. It does not generate round events. Explicit discontinuity handling does not establish that real content jumps have been detected upstream.

On the same 18 native frames used below, the new continuous check produces eight confirmed purchase-phase flags (six in R1, two in R2), while timer and both scores remain unknown and round starts/ends remain zero. Runtime is 47.336 seconds; the initial experiment used a different OCR runtime environment, so these times are not a comparable performance measurement. Local evidence: `outputs/recognition-investigation/phase-evidence/structural-text/native-phase-contract.json`.

| Check | Previous | Current | Delta |
| --- | ---: | ---: | ---: |
| Targeted PASS / FAIL / NE | 0 / 5 / 2 | 0 / 5 / 2 | 0 / 0 / 0 |
| Targeted runtime (seconds) | 76.505 | 76.886 | +0.382 |
| Sampled PASS / FAIL / NE | 7 / 12 / 11 | 7 / 12 / 11 | 0 / 0 / 0 |
| Sampled runtime (seconds) | 285.415 | 285.123 | -0.292 |
| Confirmed phase flags on 18 native frames | 0 | 8 | +8 |

The sampled and targeted runs completed with their existing assertion failures and no changed failure set. These partial checks do not prove full negative-assertion or discontinuity safety. No new full E2E has run, and no new canonical PASS is claimed. The required complete boundary windows and all three genuine lifecycle boundaries remain acceptance blockers.

### Native pre-round package check

At HEAD `9bb50abd463ab0ef41fb35c59dbe0d7679a64082` plus the documented diagnostic/test changes, the 0–9 second replay processed all 224 archived native PTS in 460.752 seconds. Video SHA256, terminal archive SHA256 and profile fingerprint were verified before and after processing. Results: unknown 217, live 7, semantic purchase matches 69, confirmed phase flags 64, accepted timer/score pairs zero, native boundary events zero. Confirmed phase spans PTS 0.202669–4.086003; the first live observation is 7.369336.

The native builder preserves one partial fragment `[7.369336, 8.502669]` with timeline completeness zero, one snapshot, six derived state snapshots and no round boundaries. Preparation confidence can extend context around an actual detected start, but cannot create that start or turn this fragment into a completed round. The 3.283333-second difference between the last phase confirmation and first live observation is an evidence gap, not itself proof of an adjacent-frame continuity violation. The continuous input includes intermediate unknown observations. No missing boundary was injected to force association.

This rejects the hypothesis that phase confidence alone will resolve the native pre-round package scope. The immediate blocker remains a source-qualified round-start event. The package unit test separately verifies that qualified preparation associates with a supplied start and that the same preparation without a start leaves a partial fragment unchanged. Local terminal evidence: `outputs/recognition-investigation/phase-evidence/structural-text/native-pre-round-package.json`.

Related package and trace tests: **25 passed, zero skipped in 13.25 seconds**, with `VALORANT_E2E_VALIDATION_PACK` pointing to the existing local pack. The unchanged reference evaluator still rejects the synthetic spectator HUD leakage through `NEG-SPECTATOR-POISON-151`; this is a targeted contract regression check, not full-video negative acceptance. Ruff passes for src/tests/E2E/diagnostics, mypy passes for 98 source files, and `git diff --check` passes. Machine-readable current evidence and verification are in [semantic phase contract diagnostics](../e2e_reports/match_001/semantic_phase_contract_diagnostics.json).

## Problem and scope

At main `8e3cf32f1ac331c747e85fd1dcdcffcb4179e987`, the lifecycle pipeline has no qualified buy-phase input. This investigation tests that input using archived real frames and the existing production `HudTemplateProfile` matcher. It does not qualify a round boundary or adopt a new profile.

Targets: `GT-R1-ROUND-START`, `GT-R2-ROUND-START`, `event_count_constraints-000`, `event_count_constraints-004`, `ordering_constraints-001`, and `GT-R1-BUY-FLAG`. These require additional predicates; a template match alone is insufficient. R1 end remains a separate evidence problem.

## Reference and independent review

Three R1 frames at PTS 1.502669, 2.502669 and 3.902669 provide the median grayscale reference. The crop `[765,170,1155,240]` contains the Japanese purchase-phase text and excludes the changing round label, timer, scores and purchase hotkey. Background pixels remain in this unmasked reference, so background contamination is a known limitation.

The reference and training manifest were frozen before predictions on the separate R2 episode. NCC remains **0.90**. No threshold, crop or reference was retuned after holdout misses. Manual image review supplies diagnostic presence labels; these are not additions to validation ground truth and are not available to the runtime matcher.

The existing matcher accepts all three training examples. Of eight reviewed R2 positive holdout frames, five match and three remain unknown (PTS 99.002669, 103.002669, 105.002669). Thirteen reviewed non-purchase examples, including menus, remote-view backgrounds, combat/death imagery and a TEAM ACE banner, produce no false acceptance. A nonmatch means unknown, not verified absence. These small cohorts do not establish general false-positive safety.

Hashes, exact native PTS, scores and provenance are in [the qualification report](../e2e_reports/match_001/phase_reference_qualification.json). Images and the diagnostic profile remain local under `outputs/recognition-investigation/phase-evidence` and `outputs/hud_profiles/round-phase-text-20261008`.

## Native continuous check

The diagnostic profile copies the safe profile13 assets and adds only `buy_phase_template` in the existing JSON format. `RealHudAnalyzer` receives real archived frames, three genuine calibration prefix frames, and no injected anchors, signals, GT timestamps or round IDs. The existing diagnostic verifies source video SHA256, terminal raw hash and profile fingerprint. Every native PTS in the explicitly selected windows is processed; the full sampler is unchanged.

| Window | Frames excluding prefix | Phase matches | Both scores known | Timer known | State | Boundary events |
| --- | ---: | ---: | ---: | ---: | --- | ---: |
| 3.8–4.25 s | 12 | 9 | 0 | 0 | unknown: 12 | 0 |
| 111.25–111.6 s | 6 | 2 | 0 | 0 | unknown: 6 | 0 |

Runtime: **38.746 seconds**. The R1 window includes one training frame, so it is not independent R1 holdout qualification. No R2 frame was used in reference generation. These windows are shorter than the required complete lifecycle acceptance windows and do not replace that validation.

The semantic match is present at 4.086003 s and absent at 4.152669 s; it is present at 111.402669 s and absent at 111.436003 s. These are observed matcher transitions, **not emitted start events**. Production logic has no knowledge of these times. R2's earlier 111.269336 s frame is also a nonmatch, demonstrating why template disappearance alone cannot safely define a boundary.

## Previous / Current / Delta

The historical safe full contains the same 18 PTS, all unknown. The previous continuous input diagnostic had zero configured semantic phase matches.

| Metric on these 18 PTS | Previous | Current | Delta |
| --- | ---: | ---: | ---: |
| Semantic purchase-phase matches | 0 | 11 | +11 |
| HUD unknown | 18 | 18 | 0 |
| Known score pairs | 0 | 0 | 0 |
| Known timer | 0 | 0 | 0 |
| Round starts | 0 | 0 | 0 |
| Round ends | 0 | 0 | 0 |

The last canonical result remains **23 PASS / 55 FAIL / 4 NE**. The diagnostic profile has not undergone a new canonical full run; its full PASS/FAIL/NE and deltas are unmeasured. No newly passing assertion is claimed. Negative and discontinuity assertions were not evaluated by this component check. Previous zero failures are not evidence of new acceptance safety.

## Conclusion and remaining blockers

R1 end has an additional continuity problem. Manual saved-image review shows score 0–1 and timer `0:29` at 74.402669 s, then 0–2 and `0:06` at 74.486003 s, on opposite sides of the known content jump. Neither image contains a semantic end banner. The reviewed 75.802669 s image does contain `TEAM ACE`. Joining that later banner back to the preceding score display across the cut would violate the continuity contract. This is not proof of a ground-truth error: elimination evidence before the cut or other independent evidence could still establish a boundary.

The existing five-slot roster heuristic also fails to provide a complete accepted ally count in the reviewed frames. At 74.319336 s its nominal-ROI candidates are `[unknown, unknown, unknown, unknown, alive]`; at 74.402669 s they are `[unknown, unknown, alive, unknown, unknown]`. Background pixels can resemble alive evidence, so these candidates must not be interpreted as a real elimination or forced to zero. The native accepted ally count is unknown throughout. The qualification JSON preserves these diagnostics separately from production accepted values.

The production profile mechanism can carry real semantic phase evidence without a new recognizer or policy change. The component is supported by multiple independent positive examples, but its coverage is incomplete and it is **not adopted**. `buy_phase_template` still needs accepted, stable score pairs before `_enrich_temporal_evidence` establishes pre-round context. The baseline profile has no configured score readers or accepted timer at these boundaries, and all boundary observations remain unknown under the unchanged independent identity policy.

Do not launch full E2E or claim lifecycle completion from this result. The next work must qualify the remaining boundary inputs and their provenance, including semantic end evidence and source discontinuity markers. Keep the existing restrictions on new numeric/spectator candidates for the Round Lifecycle task. This investigation made no OCR candidate, production source change, threshold change, validation change or sampler change.

Windows uses the same profile format, relative asset paths and matcher. These assets have not been tested on a Windows machine; OpenCV scores and image decoding still require verification there.

Verification on the current source: Ruff PASS; mypy PASS (97 files); 46 related template, runtime-semantics and lifecycle unit tests PASS in 4.59 s. No sampled/full run or full regression was executed for this unadopted input component.

## Dense R1 end source review (2026-10-08)

The earlier review compared archived full PTS 74.402669 and 74.486003, which contain no semantic end banner. A closer review found `TEAM ACE` at **74.436003**, already present in an older targeted frame archive but absent from full16 native observation PTS. A fresh source decode of **every frame in 74.36–74.52** confirms ten consecutive frames with 256-tick spacing at time base 1/15360. All ten were manually inspected. Exactly one in this range shows the banner, at tick1143337 (74.436002604...). Timer remains `0:29` there, switches to `0:06` at74.452669, and displayed score updates from0–1 to0–2 at74.486003. These are diagnostic visual observations, not accepted reader values or runtime labels.

This changes the next investigation: R1 end has real semantic evidence between archived full-native observations; it must not be described as absent throughout the source. It still does not qualify production end detection: a single banner frame lacks temporal corroboration and independent training/holdout support; archived score pairs and player HUD confidence are unknown/zero. The previously documented content discontinuity still prohibits treating later score/banner evidence as uninterrupted corroboration. No cut timestamp or GT value is injected, no sampler changes, template candidate or boundary events were made, and no new full E2E or canonical PASS is claimed. Next investigate independently corroborated end evidence within the same content segment and how its source timing can reach the existing production contract. [Source ticks, image hashes and detailed limits](../e2e_reports/match_001/r1_end_dense_source_diagnostics.json).
