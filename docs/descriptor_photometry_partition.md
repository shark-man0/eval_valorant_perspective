# Descriptor photometry and camera mismatch partition

## Problem / hypotheses / target assertions

R1source acquisition still blocks GT-R1-ROUND-START/END and GT-R2-ROUND-START. Prior spatial proposals fail camera consensus; even self calibration failed projected photometry. Separate source texture, current footprint/texture, NCC and camera correspondence without trimming tracks or refitting the saved model. HEAD e9ecaf8f2f0f0dfa1f9433d40a598ec8909e9ce3.

## Independent image evidence

`audit_descriptor_photometry.py` reuses all original saved matches and the frozen model, source/current image hashes and declared allowed regions. Exact15pxsource patch std, complete current interpolation taps, current std, NCC and camera residual are reported. First-rejection categories form an exact partition. No model/track filtering, hypothesis selection or detector decisions change. Image-time, timer, phase, score and GT values are not inputs.

| Pair | Tracks | Source std<1 | Current footprint missing | Current std<1 | NCC<0.90 | NCC>=0.90 | Model missing |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
|Arch self|151|6|0|0|0|145|0|
|Arch displaced|21|0|0|0|11|10|0|
|Other scene|1|0|0|0|0|0|1|
|R1self|286|116|0|0|0|170|0|
|R1phasegone|52|1|0|1|7|43|0|

Arch self has145appearance-supported points but142also satisfy the fixed final-model2pxresidual, matching the prior142photometric inliers. NCC alone does not grant a correspondence.

## Root cause / competing hypotheses

All116R1self unavailable points are source texture std<1. This is a source eligibility defect of the new proposal representation, not missing destination pixels or unexpected self photometry. Source eligibility should be assessed before matching, never applied after an unfavorable model to prune its denominator.

However, R1phasegone has26camera outliers and only1of these has unavailable source texture. Removing only that source-ineligible point without refitting gives26/51=50.98%, still far below90%. Arch displaced has no source texture failures. Therefore source texture filtering is **rejected as a sufficient actual acquisition remedy**, even though it can repair self calibration. Do not launch another full/cohort run on that premise.

R1phasegone26geometric inliers all have NCC>=0.90. Among26camera outliers,17also have NCC>=0.90at the saved camera projection,7failNCC,1lacks current texture and1lacks source texture. Thus appearance and the declared descriptor endpoint can disagree: repeated/weakly localized structure is a plausible explanation, not a proven content cut. High NCC must not override original correspondence consensus. Actual-scene continuity and hidden-time continuity remain unqualified.

The final-model residual partitions are diagnostic, not replacement RANSAC support or an acceptance rewrite. Arch displaced has8points within2pxof the final model, while the saved RANSAC support was7; those counts are not silently interchanged. All original candidate decisions remain unchanged.

## Contract change / tests

Read-only diagnostic only. Three tests PASS in0.27seconds: source/current/model/footprint distinctions, fractional missing-tap rejection, and unrelated photometry rejection. Ruff passes for src/tests/scripts/e2e and the new module. Production is unchanged; preceding mypy104filesPASS applies. No new standard targeted/sampled/full E2E: actual acquisition gates still fail. Windows execution unverified.

All inputs and diagnostic code are hashed before measurement and checked after measurement. `e2e_reports/match_001/descriptor_photometry_partition.json` holds per-point statistics and runtime. The original spatial declaration is verified before measurement; same exposed data cannot serve as independent holdout.

## Previous / Current / Delta

| Metric | Previous | Current | Delta |
| --- | --- | --- | --- |
| R1self unavailable photometry |116unclassified|116source texture|Cause resolved, count unchanged|
| R1phasegone camera support |26/52|26/52|0|
| Actual R1/arch proposals |0/0|0/0|0/0|
| Qualification/runtime events |0/0|0/0|0/0|
| Canonical PASS/FAIL/NE |Historical23/55/4|Not rerun|Unmeasured|

All82assertion entries remain unchanged. No new assertion PASS is claimed; negative/discontinuity historical0/0has not been remeasured in a canonical run.

## Remaining blocker / next task

The actual blocker is correspondence localization/coherence, rather than the self-only source texture defect. Investigate the17R1appearance-supported but endpoint-incoherent matches for repeated structure and full neighborhood ambiguity. Use frozen hypotheses and explicit competing locations; do not choose a favorable subset, relax90%original consensus, or accept a high NCC as localization proof. Keep the production route inactive until independent native acquisition/continuous/negative and paired UI qualification, then verify lifecycle/package/trace/canonical end to end.
