# Report identity representation review

## Decision and pipeline priority

`NEED MORE EVIDENCE`. No production behavior or threshold changed. The Ability followup identified extractor contamination but did not establish dynamic-value invariance; the next Spectator diagnostic exposed a stronger safety blocker: at least nine pixel-reviewed Report overlays already pass the baseline live gates. Report detection therefore takes priority over increasing live recall. This decision starts a new experiment rather than ending the work.

## Reproducibility

Starting commit: `a0d844e4b881c854726486145f92db69c6d8ef78`. Video SHA256: `71d58558559d6f578433ce9f234bf176f76fd5a86657dbfe3eba1e7d36136b06`. Loaded HUD profile fingerprint: `372bf43ab9c443e3d54bd46b3b5d51626aa1ebf0f8d8a68edeb76e5aff826453`. It has HP, Ability and Weapon references, but no Report reference. The existing clean E2E evaluated analyzer `2650d09b90df50d6a004dbe5d849fc60432af33b`, with `git_is_dirty=false`. This diagnostic adds offline scripts/tests/docs; no new clean E2E is required for unchanged production.

Images, crops, model assets, sample IDs and timestamps remain private. Shared measurements are aggregates. No GT event/state/expected value enters extraction. Calibration candidates were independently reviewed from pixels. Frozen training contains 22 Report crops and 13 non-Report crops; holdout contains 16 Report and 16 non-Report crops. Exact image hashes are disjoint from each other and prior controls. Training/holdout use distinct capture blocks, but this single recording includes correlated episodes across blocks; this is not recording-separated validation.

## Current detector failure

The native reader uses a panel proxy: 55% outer-margin brightness difference plus 45% content contrast/edge density, accepted at 0.78. Its flag/score replay agrees across all 4,730 native observations. One actual Report scores 0.5099 despite content score 1.0: its outer-margin signal is only 0.1088. Changing only the exterior 6.16% margin can raise the same unchanged UI to score 1.0. A shopping panel without Report also scores 0.7974. Neither recall threshold lowering nor this boundary proxy provides reliable Report identity.

## Candidate progression

Early weak-score seeds produced long horizontal line groups and shopping false accepts. Manual pixel review found that high-score seeds include non-Report panels; lower-boundary actual Reports were underrepresented. The corrected training cohort removes that seed-label assumption.

| Frozen candidate | Training Report | Holdout Report | Non-Report controls | Interpretation |
|---|---:|---:|---:|---|
| Panel-scale persistent separator groups | insufficient, 0 groups | not evaluated | not evaluated | No recurrent panel-scale pairs; never claim zero false accepts |
| Smaller geometric corner groups | 0/22 | unqualified shape probe only | unqualified shape probe only | Majority illustration edges were selected; not invariant UI |
| Static header, three raw NCC groups | 7/22 | not evaluated | not evaluated | Training fails |
| Static header, three masked NCC groups | 9/22 | not evaluated | not evaluated | Left group fails 13 training crops |
| Static header, two masked groups | 22/22 | 16/16 | 0/16 holdout, 0/8 world, 0/7 shop | Diagnostic only; full-native audit and excluded-group interpretation pending |

Two-group candidate detects 29/30 frozen Report-visible controls. Those controls are positives for Report detection even though they are negatives for live identity. The 13 training non-Report controls are excluded from training and not counted as independent holdout performance.

Header localization searches vertically inside the configured Report ROI and horizontally within two pixels, with one shared pose and no scaling/rotation. It is specific to this Report experiment, not the Ability alignment experiment. Observed header positions differ by 16 pixels. Support uses Canny edges dilated one pixel, masked grayscale NCC, and unchanged 0.90 per-group acceptance. This is a static UI-texture template; it is neither OCR nor a value-invariant separator-only representation, and locale/capture-family dependence remains.

## Left group failure and observability

The 13 failing left-group crops have median brightness std 19.28, 230 observed Canny edges and 18.5% local contrast occupancy. Oriented edge recall median is 0.883, precision median 0.968; all 13 have precision at least 0.90. About 84.7% of reference edge pixels recur in at least 60% of failing crops. Left-only ±1-pixel shifts recover zero crops. Mismatch occurs inside glyph-edge geometry; darkness or a simple horizontal alignment error does not explain it.

This is observable disagreement with a particular raster reference, not proof that the Report family is absent. Conversely, the two-group result cannot silently relabel that disagreement as unobservable. Inverting either selected group rejects; changing outside their support is exactly invariant, including inversion of the excluded left group. Whether that ignored variation is nonidentity raster variation or relevant contradictory evidence needs further audit before adoption.

## Reproducible offline contract and checks

`scripts/diagnose_report_scaffold.py` accepts a private NPZ with exactly three uint8 grayscale stacks: `training`, `holdout`, `negative`. It emits only aggregate model diagnostics and support hashes. No production module imports this helper. The panel-scale model must pass independent group recurrence and joint training sufficiency before holdout or negative scoring. For this real cohort (22/16/44), training rejects with no persistent segments/pairs; downstream results explicitly remain not evaluated.

Six tests cover synthetic recurring groups with holdout glyph variation, exact outside-support invariance, missing/contradictory supports, stripe-only insufficient training, invalid-model not-evaluated reporting, and strict input geometry/nonfeature keys. Full pytest: 730 passed, 2 skipped. Ruff across source/tests/scripts, mypy existing 83-source-file contract, and diff checks pass. No production E2E rerun or claim of metric improvement is made.

## Next evidence

Freeze the two-group model and audit native acceptance across all 4,730 observations, especially baseline live and the proposed Spectator ablation. Inspect diverse new accepted frames independently from pixels. Any adoption must preserve legacy negative evidence, reject insufficient selected supports and test temporal death-event consequences. Map ownership diagnosis proceeds independently; a bright minimap component alone cannot become a confident self marker.
