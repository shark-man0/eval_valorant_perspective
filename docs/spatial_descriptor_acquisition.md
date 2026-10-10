# Spatial candidate and descriptor context development

## Problem / hypothesis / target assertions

Same-image calibration showed loss of current features under larger-crop relative quality normalization and descriptor context changes. Test a coherent spatial candidate/context representation upstream of GT-R1-ROUND-START/END and GT-R2-ROUND-START. No clock/phase/GT input is used. HEAD e9ecaf8f2f0f0dfa1f9433d40a598ec8909e9ce3.

## Contract change

Explicit diagnostic-only `feature_source=spatial_corners` uses 64px tiles with stride32 inside each declared domain. Existing GFTT100/quality0.01/minDistance5 applies per tile. This increases total candidate budget and changes spatial selection, rather than preserving a global 100-feature cap. Duplicate physical coordinates are described once. Each size3/orientation0 descriptor uses the same fully observed19×19input centered at its candidate, independent of source/current crop boundaries. No implicit fallback or production/observer activation is added.

The final reciprocal ratio0.75, distinct physical association, three-region support, original-correspondence90%camera consensus, original-correspondence90%projected photometric support, NCC0.90/full interpolation footprint and complete joint ambiguity gates remain unchanged. Overlapping candidates are proposals, not independent world evidence. Library descriptor preprocessing is not additional observed support. Source/current corner margins remain9px. This is a coverage redesign, not an accepted lifecycle candidate.

## Evidence / competing hypotheses

Five previously exposed pairs, code, profiles/assets/source hashes are frozen before measurement and verified at termination. Prior `reviewed_corners` results compare exactly on all five pairs.

| Pair | Previous matches/regions | Current matches/regions | Model inliers | Outcome |
| --- | --- | --- | ---: | --- |
|Arch self|16/3|151/3|148/151|Self-only proposal;142photometric|
|Arch displaced13.202669|2/2|21/3|7/21|Camera incoherent, withheld|
|Arch other6.002669|0/0|1/1|Not evaluated|Insufficient support|
|R1self|16/2|286/6|286/286|170photometric; withheld|
|R1phasegone4.102669|16/2|52/4|26/52|Camera incoherent, withheld|

The R1self model is near identity; none of its evaluated NCC scores is below0.90.116tracks have unavailable projected photometry (the existing routine combines footprint and texture/NCC availability), so the original 90%gate correctly withholds the proposal. Do not discard those tracks after fitting or promote286matches to accepted image support. A further source-eligibility audit must separate known source texture from current footprint; it must precede matching rather than trim failed photometry afterward.

Actual R1/arch queries now have distributed descriptor proposals but original camera consensus is only50%/33.33%. Thus crop loss was real, but recovering candidates alone is insufficient. Repeated structure or incorrect correspondence remains a competing explanation. No model refit on a favorable subset and no threshold tuning is performed. Unknown is not labelled a content cut; no UI-transient continuity verdict or hidden-time proof follows.

## Tests

28descriptor/domain/joint tests PASS in31.65seconds, including the explicit new representation on synthetic translation/rotation-scale, constant/unrelated scenes and protected UI exclusion. An additional test checks exact same-location descriptor equivalence across crop contexts and physical deduplication. Final descriptor suite:16tests PASS in33.17seconds, including that additional regression; synthetic success is not independent actual-view qualification. Ruff passes. Production mypy PASS on104source files at current main. Native/window orchestration is not switched to this diagnostic representation.

## Previous / Current / Delta

| Metric | Previous | Current | Delta |
| --- | ---: | ---: | ---: |
| Actual R1phasegone distributed matches |16/2regions|52/4regions|+36matches/+2regions; not accepted|
| Actual R1/arch acquisition proposals |0/0|0/0|0/0|
| Five-pair proposals |1self|1self|0|
| Runtime qualification/events |0/0|0/0|0/0|
| Canonical PASS/FAIL/NE |Historical23/55/4|Not rerun|Unmeasured|

Real diagnostic runtime is in `spatial_descriptor_development.json`; it includes baseline equivalence checks and is not directly comparable with an E2E run. All82assertion entries are unchanged. No targeted/sampled/full E2E is warranted because real acquisition gates still fail. Windows/OpenCV execution remains unverified.

## Remaining blocker / next task

Audit source texture eligibility before matching and partition unavailable photometry. Then test whether coherent, unambiguous distributed correspondence can be supported at unchanged final conditions. Do not start another matcher or reduce original model consensus based on these exposed pairs. Independent acquisition-plus-continuous/negative and paired UI qualification still precedes activation, followed by native lifecycle/package/trace and canonical acceptance. No new PASS is claimed.
