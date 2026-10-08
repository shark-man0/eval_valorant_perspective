# Purchase-phase reference qualification

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
