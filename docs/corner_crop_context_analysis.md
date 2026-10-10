# Same-image corner crop context analysis

## Problem / competing hypotheses

Target: source continuity upstream of GT-R1-ROUND-START/END and GT-R2-ROUND-START. R1 self calibration fails distributed descriptor correspondence. Separate absent current candidates from descriptor mismatch, without interpreting acquisition failure as a content discontinuity. HEAD: e9ecaf8f2f0f0dfa1f9433d40a598ec8909e9ce3.

## Independent image evidence

`audit_corner_crop_context.py` uses only the previously exposed reference images and declared non-clock/phase search regions. The source and current inputs are the **same pixels**. For each existing source corner descriptor, it records nearest current candidate distance, current crop relative minimum-eigenvalue response, and the descriptor distance when computing at the exact same physical point. It does not propose an affine model or authorize a continuity link. Position identity is valid solely for this self calibration, never supplied to actual displaced recognition.

| Measurement | R1 wall | Arch |
| --- | ---: | ---: |
| Source corner descriptor candidates |295|74|
| Inside a current descriptor context |264|74|
| Below existing 0.01 relative quality in all eligible contexts |249|36|
| Current candidate within 1 pixel of source location |15|16|

R1 region counts of nearby current candidates are 0,0,15,0,0,0; all six source regions have candidates. Thus current crop-relative feature selection discards distributed R1 support even with identical pixels. The changed crop maximum affects the existing relative-quality criterion. This establishes candidate-selection loss independently of camera motion, timer, phase, content cuts or descriptor ambiguity. It does not prove this is the sole cause of actual displaced acquisition failure.

Forced same-point descriptor distances range 0–131.351 for R1 and 0–80.932 for arch. Crop context also changes representation despite identical physical points; this is a separate measured concern. These distances are descriptor units, not confidence/NCC. Border preprocessing supplies no real witness outside the declared crop.

## Continuity decision / contract change

No runtime continuity decision or contract is changed. Unknown remains unknown. No threshold, source profile, geometry or production logic changes. The next justified experiment is explicitly spatially balanced candidate selection using the existing per-local-domain detector parameters, with crop-context consistency assessed separately. Retain reciprocal uniqueness, distinct physical witnesses, three-region support, 90% original model/photometric consensus, NCC 0.90, full current footprint and joint ambiguity rejection. Do not tune those gates to rescue these exposed images. Successful development would still require independent acquisition/continuous/negative and paired UI qualification.

## Tests / provenance

The read-only diagnostic records input/script hashes before measurement and verifies them after measurement; full per-point statistics are in `e2e_reports/match_001/corner_crop_context_diagnostics.json`. Ruff passes for the new script and src/tests/scripts/e2e. No production implementation changed; no broad regression or E2E was warranted for this calibration. Windows execution remains unverified. Source/current same-image use is intentional calibration and cannot qualify independent holdout.

## Previous / Current / Delta

| Metric | Previous | Current | Delta |
| --- | --- | --- | --- |
| Cause of lost same-image R1 candidates |Suspected crop selection|249/264 below current relative quality floor|New measured evidence|
| Canonical PASS/FAIL/NE |Historical 23/55/4|Not rerun|Unmeasured|
| Runtime qualification |0|0|0|
| Production policy changes |0|0|0|

All 82 assertion entries are unchanged. Standard targeted/sampled/full E2E was not run. Calibration runtime is recorded in the machine-readable report; it is not an E2E runtime comparison.

## Remaining blocker

Current actual-view acquisition still fails distributed support. Image-only candidate coverage and descriptor context require a coherent design, then fresh independent qualification before lifecycle activation. No new PASS, scene continuity verdict or hidden-time proof is claimed.
