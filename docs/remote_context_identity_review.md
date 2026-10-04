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
| Purple with two circles and lower checker texture | 0.92 / 1.0 / 1.0 | Remote, subtype astra_astral | false |

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
