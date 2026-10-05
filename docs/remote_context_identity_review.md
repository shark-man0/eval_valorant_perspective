# Remote context identity review

## Reproducibility and scope

Starting shared HEAD: `3fa26967b2c26f4ced5cbb355accfd7be65777c8`. Analyzer production source remains `3e9df3dab16d6dce83f3973f0386638d11286c0c`. Clean E2E source observations are the 4,081 rows of `20261004T130701Z-bb7e94b4`, with `git_is_dirty=false`.

Video SHA256: `71d58558559d6f578433ce9f234bf176f76fd5a86657dbfe3eba1e7d36136b06`; profile sidecar SHA256: `8e764d6eb2b7a6a8ce6a5f144300bdf809f16f9dcf2b689ac659333c2265b615`; layout SHA256: `a3678bcd9df35d0932ae0e69495eb5b87a3ab40e9c988560d502a9507d59eef1`.

This follows the Buy close-X diagnostic. Replacing the strict Hough anchor exposed one UNKNOWN-to-Remote decision on visible death/report world texture. No GT, expected timestamps, expected mode, Agent identity, or OCR values were passed to a detector. All image review, timestamps and individual frame mappings remain private; this document shares aggregates only.

## Actual runtime path

`RealHudAnalyzer.observe_frames` calls `OpenCvHudFeatureReader.observe`. Its `_astra_scores` measures the configured `center_crosshair_area` crop. In this profile the crop is 400 x 400 pixels. Three scalars are computed:

- Purple HSV coverage divided by 0.24, capped at 1.0.
- Hough circle count: score 0.92 if at least two circles are found, otherwise 0.0.
- Lower-crop Canny edge occupancy divided by 0.07, multiplied by normalized grayscale standard deviation; both factors are capped at 1.0.

Each scalar is converted to a boolean at 0.90. `HudStateClassifier` treats all three true as sufficient `astra_astral` Remote evidence. Its confidence is the minimum scalar. These are normalized image heuristics, not probabilities, reference similarity scores, or verified hand/control-interface matches. They share one crop; naming them three features does not prove independent UI support.

The actual sidecar configures HP, Ability and Weapon structure references, and no Remote subtype template. There is therefore no Remote reference hash, mask, support-group matcher, training/holdout validation or reference alignment in this active path.

`live_identity` separately blocks all-three heuristic flags. Keep that safety contract unchanged. The classifier also keeps contradictory mode candidates UNKNOWN. Deleting a weak candidate entirely can erase an existing conflict and expose another unsupported positive; weak exclusion evidence and sufficient positive identity evidence must be distinguished.

## Exact score evidence

The bounded audit recomputed the production function on all 33 saved Remote observations, the exposed report/world observation, and 32 score-near report-signal/non-Remote controls. The exposed observation is excluded from those 32 controls. Saved state and report flags describe strata; they are not semantic ground truth or negative labels. This bounded control set differs from an earlier broad all-frame diagnostic and must not be conflated with it.

| Cohort | Count | Geometry min/median/max | Palette min/median/max | Interface min/median/max | All three >=0.90 |
| --- | ---: | --- | --- | --- | ---: |
| Saved Remote observations | 33 | 0.92 / 0.92 / 0.92 | 0.906 / 1.0 / 1.0 | 0.9064 / 1.0 / 1.0 | 33 |
| Exposed report/world observation | 1 | 0.92 / 0.92 / 0.92 | 1.0 / 1.0 / 1.0 | 1.0 / 1.0 / 1.0 | 1 |
| Score-near report-signal/non-Remote controls | 32 | 0.92 / 0.92 / 0.92 | bounded diagnostic median 0.1609, max 0.5851 | bounded diagnostic median 0.8074, p90 1.0 | 0 |

The exposed world-texture observation saturates the palette and interface scores and equals every accepted geometry score. Raising these scalar gates cannot separate it from accepted observations while retaining those observations. No threshold change is proposed.

## Synthetic sufficiency counterexample

`scripts/diagnose_remote_texture_probe.py` creates two deterministic synthetic 400 x 400 textures, invokes the actual scorer and classifier, and writes aggregate JSON only. It uses no reference assets or gameplay labels. Run from the repository with its Python environment and `PYTHONPATH=src`; supply a new private output JSON path.

| Synthetic content | Geometry / palette / interface | Classifier result | Player HUD valid |
| --- | --- | --- | --- |
| Solid purple | 0.0 / 1.0 / 0.0 | UNKNOWN | false |
| Purple with two circles and lower checker texture | 0.92 / 1.0 / 1.0 | Starting source: Remote, subtype astra_astral; qualified reader source: UNKNOWN | false |

Measured with OpenCV 4.14.0. This proves that the three features alone are insufficient evidence of a particular gameplay control UI. It is not a real-data false-positive rate or independent holdout. The diagnostic does not require this undesirable classifier result to remain a future production contract.

## Image-only context audit

A separate sealed bundle includes all saved Remote 33 observations, the exposed observation, and eight report-signal/non-Remote score-near controls from distinct source blocks. Opaque IDs, full context and the uncut center crop were reviewed after expected-manifest verification. Scores, selection groups and state mappings were withheld during root labeling. Twenty-three rows have no prior indexed review in their source block; this does not prove untouched recording evidence. All are correlated same-video samples.

All 42 show no distinct remote-operation interface identifiable from the supplied pixels. The first 33 reviewed observations comprise 24 normal first-person world scenes with held weapon/hand and purple dome/effect appearance, and nine death/report character-mesh textures. The exposed observation is another death/report mesh texture. The eight controls include normal world/scoreboard/report scenes and death/report character textures. These are appearance descriptions, not Agent expectations, GT mode labels or a claim that missing remote UI alone authorizes live identity.

The purple dome, character mesh, outlines and world geometry explain why color/circle/edge proxies can pass while their names imply stronger structural evidence than is measured. The first-person scenes expose observable world and hand/weapon structure; they should not be relabeled as insufficient image visibility solely because the Remote score is high.

Sealed review manifest SHA256: `823262f2f22fe5bf74fde6ce62133b5251bd2c12897185b7d9da029d0e92bcfd`. Root annotation SHA256: `7df73cff23b8240afe9c78c2831aaddd243d639b3d85c0ceb4ec428cc9f39b96`. Annotations bind opaque ID, decoded composite hash and shape. Original full-frame provenance must also agree with prediction inputs before a downstream join.

## Downstream risk and next experiment

Visual remote classification trusts a HUD Remote state and suppresses player mechanics. Round-window construction can treat Remote observations with sufficient HUD confidence as active-play time, absent buy/round-end flags. Thus invalid player ownership does not eliminate every consequence of a false Remote state.

`NEED MORE EVIDENCE` for a new positive Remote representation. The current three-proxy path has no tested structure support and cannot distinguish the saturated report/world counterexample. Do not fit new color or edge thresholds to this recording.

The next diagnostic tests quarantining unconfirmed heuristic evidence: retain it as a mode-conflict candidate and current-frame live exclusion, but prevent it from being the sole positive Remote source. Preserve configured confirmed/template paths and the existing conflicting-mode-to-UNKNOWN rule. A simple deletion is unsafe: it can turn an old conflict into Buy or live. Replay all 4,081 rows and verify ownership, state transitions and round-window effects before any production change. Independently seek actual observable remote-operation UI examples; do not treat the saved 33 labels as positive training truth.

## Verification

The reproducible texture probe is diagnostic-only. Production files are unchanged. Ruff passes for `src tests scripts`, mypy passes for the existing `src` contract (86 files), and diff check passes. Full pytest after the final review-tool width check and this diagnostic addition is 849 passed / 2 skipped (267.25 seconds). The two skips concern the fixed sibling-pack lookup and the dedicated legacy real-video anchor setting.

No new Clean E2E was run in this diagnostic-only phase. The last production Clean E2E remains 22 passed / 56 failed / 4 not evaluated, negative assertions 20/0, and 166 live observations. No diagnostic counterfactual is reported as production improvement. Private images, source crops and identity assets are excluded from Git.

## Evidence qualification change

The follow-up confidence-consistent counterfactual on the same 4,081 observations quarantines only all-three heuristic Remote promotions. Thirty-three Remote observations become UNKNOWN; the pre-existing uncertain-mode conflict remains UNKNOWN. Live 166, Spectator 335, Buy 1, player ownership 166 and trustworthy-world 155 remain unchanged on this fixed population. State and aggregate HUD confidence are capped at 0.45 on the 33 downgraded rows; accepted-reader ROI confidences and values remain unchanged.

The actual production fact helpers applied directly to raw observations retain 1,587 Timer point facts and 130 owned HP point facts, with identical fact hashes. These raw helper counts are not the final fused Clean E2E population of 1,477 Timer facts. Removing weak Remote from active-play evidence moves the inferred single window start by approximately 0.233 seconds; it does not establish a correct round boundary or make the window complete.

The implementation keeps the three heuristic flags in the existing mode-conflict calculation and leaves `live_identity` byte-for-byte unchanged. The image reader now explicitly marks its aggregate evidence as `remote_texture_candidate`. A sole unconfirmed heuristic candidate carrying that provenance returns UNKNOWN with confidence <=0.45 before any live fallback. Existing explicit `remote_control_candidate` and configured subtype-template signal paths retain their prior contracts. No new positive Remote recognition is introduced and no claim of dynamic UI invariance or genuine Remote recall is made.

This is a qualification correction for insufficient positive evidence, rather than adoption of a newly trained representation. The synthetic counterexample and image-only review establish that aggregate texture does not substantiate the asserted control interface. Quarantining its promotion preserves current-frame exclusions and avoids both unsupported Remote and accidental live promotion. An independent Remote UI matcher still requires actual observable positive examples, training/holdout recurrence and negative separation.

Targeted tests cover texture-only rejection, unchanged live exclusion, Buy/Map/Spectator conflicts, existing subtype template paths, the explicit candidate contract, confidence cap and no stale Remote carryover. Existing semantic-input HUD logic cases, including HL-004, and the temporal fixtures remain unchanged. The reader-provenance marker distinguishes measured texture candidates from existing confirmed semantic inputs. Weapon, HP and Spectator tests are unchanged. A clean committed-source E2E must validate the resulting pipeline before deployment claims.

Post-annotation evaluation-only cross-check: none of the 33 saved Remote observations overlaps any of the four GT-ASTRAL core intervals; one overlaps an outer transition bracket only. The four expected intervals already fail in the saved evaluator report. GT was consulted after image labels froze and did not enter production signals, masks, thresholds or timing logic. This corroborates the absence of validated positive retention in these 33 observations; it does not locate a new Remote interface or justify using GT for reference selection.

Final qualification verification: pytest 861 passed / 2 skipped (267.49 seconds); Ruff for src/tests/scripts, mypy for src (86 files), and git diff check pass. An initial classifier-wide qualification attempt failed the authoritative HL-004 semantic-input case; the final reader-provenance design preserves that unchanged case and all temporal fixtures. Clean E2E is pending the production commit. Source-equivalent cached replay recomputes the reader marker from measured flags and invokes the current classifier; its results match the confidence-consistent counterfactual above. No saved replay is claimed as fresh E2E.

## Fresh committed-source E2E

Clean run `20261004T234911Z-092d7437` analyzed commit `f291ded6140a802aec9098c22ea96ef6d7b29e2a`. Metadata records `git_is_dirty=false` and unchanged video, layout, settings, validation-pack and assertion hashes. The report-only commit is `32725d7`. Evaluation completed normally: 22 passed / 56 failed / 4 not evaluated; negative assertions 20 passed / 0 failed. E2E remains incomplete; this change corrects unsupported view identity rather than optimizing failed assertions.

Fresh population is 4,038 observations: live 165, Spectator 335, Buy 1, Remote 0, UNKNOWN 3,537. Compared by exact observation time to the earlier clean 4,081-observation run, all 4,038 fresh rows are common; 43 earlier rows are removed and none added. Removed rows comprised 35 UNKNOWN, seven Remote and one live. On common rows the only primary-state changes are 26 Remote-to-UNKNOWN. Thus the 33 earlier Remote positives disappear through 26 qualifications and seven sampling removals. The fixed-cache replay's 166 live count must not be claimed as fresh-run retention.

Final fused HP facts retain all 130 previous records exactly after ignoring generated fact IDs, with no additions/removals. Final fused Timer facts retain 1,470 previous records exactly, with seven removed and none added, compared with 1,477 earlier records. These are final package facts, not raw helper counts. The adaptive sampler uses state transitions to request dense frames; changing unsupported Remote evidence can change this population. All seven removed Timer records belong to removed sampled rows. Pass A retains the same 1,028 images in both runs; the 43 removed rows belong to the adaptive second pass. Saved JPEG and decoded BGR hashes match for all 4,038 common rows. Three ally-roster confidence leaves and one ally-alive value also differ on common rows; these limited secondary differences are recorded separately rather than claiming full JSON parity. Sampling must not be tuned to restore a count.

## Observable UI discovery after qualification

The next diagnostic found three distinct purple angular full-screen map-like/control-like interface examples among 24 image-reviewed two-of-three proxy near misses. Exact original-pixel scorer recomputation gives geometry 0.92 and palette 1.0 for all three, but interface scores only 0.0362--0.3857. The interface proxy can be low on observable geometric UI while being high on world/report textures. Labels describe visible pixels; they do not assert an Agent, expected mode or semantic Remote truth.

A frozen appearance-descriptor retrieval then selected a further 24 unique images, sealed against an expected manifest receipt and reviewed before private score/source mappings. Six show the purple angular full-screen interface; comparison images include four purchase grids, three gray expanded tactical maps, one death/report mesh and ten ordinary world/effect scenes. Three of those ten are opaque purple effects with insufficient evidence for an angular interface. No image, crop, timestamp or individual ID is shared in Git.

Retrieval used full-center-crop Lab cell moments and spatial HOG. It has no hand/weapon/icon exclusion mask; distributed cells do not establish semantic exclusion. It is discovery only, not an identity matcher. Six appearance-positive samples split into three development training and three development holdout; controls split eight and ten. All are same-video data, root has seen the review images, and adjacent source blocks may share an occurrence. This is not untouched or independent-video holdout evidence.

Next experiment: freeze a distributed geometric structure candidate from training only, ablate suspected dynamic/hand/weapon patches, measure recurrence across visible view variation and development holdout, and compare against gray-map, purchase-grid, smoke/world and report negatives. Keep the qualification correction active; do not promote this retrieval descriptor or lower thresholds. A new positive representation still requires independent support and contradiction/insufficient-evidence rejection.

Near-miss review manifest SHA256: `f8b0fa28fce0f3d7ecee3847b17c8b729266a448a4f3970d4e0ac83fd66dc3f6`; annotation SHA256: `c189176529c6ac0f1e6c17d197defaffb3c9f0c99439645f9bc6a6f0dd75865b`. Generic worker appearance hints were received before this review, so pristine blindness is not claimed.

Retrieval selector SHA256: `77943b31e55274faba9421a48e58c93740e1c80b21ee2ffc99c3eb0f6bc2b4d9`; review manifest SHA256: `5e701a8f089b44cdaba2425bfca950348cc7a391652c0f702222d225f9e10159`; annotation SHA256: `63fd62b6930af68906a3ca57a06c49483772f3fa269dada97d10386e28f93a28`.
Fresh comparison aggregate/provenance artifact SHA256: 5fd0832e10e3e0e11d8060afd5581b6c7110cfec04585f50e3feade369608c92. Earlier evaluator output contained 57 failure messages across 56 failed assertions; the fresh output has 56 failure messages across 56 failed assertions. This does not constitute an additional passed assertion.

Bounded attribution: all seven removed Timer facts lie inside both old and fresh round windows, so their loss is the removed sampling population, not the approximately 0.233-second start shift. The three ally-roster confidence differences occur on common UNKNOWN observations; two keep ally_alive=5, one changes 5 to null in a combat-report-visible observation. HP/Ability/Weapon/Spectator/Timer reader confidence and identity/state flags are identical on these rows. Existing roster debounce combines current and adjacent agreeing samples and can therefore be affected by changed neighboring samples; exact neighborhood reproduction remains a private diagnostic, not a proven root cause or a reason for an unrelated production edit.
