# Shared original-identity scene tracking

## Problem / root cause / target

Native observed-source diagnostics still depended on a 604-line tracker under `scripts/diagnostics`. Production cannot import that source tree, and copying the tracker into an analyzer would create competing implementations and incomplete code fingerprints. Continue the preceding common domain-engine extraction by moving the original tracker and reviewed projected-footprint calculations into the common HUD package. Target assertions remain R1 start/end, R2 start and related count/ordering constraints. No new boundary or PASS is claimed.

HEAD: `e9ecaf8f2f0f0dfa1f9433d40a598ec8909e9ce3`.

## Change / contract

`src/valorant_ai_coach/hud/scene_tracking.py` contains the original source-identity tracker, symmetric affine membership, source-domain resolution validation, dense appearance calculation and reviewed projected appearance calculation. The two previous diagnostic modules re-export the same class/functions. There are no imports from diagnostic scripts. Existing callers keep their API and output dictionaries.

The tracker retains only original seed identities, reciprocal flow and independent seed/adjacent affine consensus. Missing support, duplicates and explicit cuts terminate without reseeding. NCC, feature/model consensus, footprint coverage and spatial support predicates are unchanged. Supplied review masks do not become image-derived semantic truth or qualification. All successful and unsuccessful outputs keep `runtime_proof_authorized=false`. Native PTS/epoch ownership remains the responsibility of the observed episode layer, which is not yet installed in production.

Strict typing uses only annotations and `typing.cast` at OpenCV/NumPy overloaded array calls; casts preserve the original runtime calls and shape normalization. Before/after normalized AST comparison verifies exact bodies for the tracker and five other functions after removing annotations, import relocation and typing-only casts. No detection thresholds or numeric operations are rewritten.

Frozen native observer/cohort and reviewed projected replay entrances now require both common source modules in their pre-execution bindings. Missing engine hashes are rejected; compatibility-module hashes alone cannot pin the calculation. The probe also binds both common modules through terminal verification. Historical declarations are not rewritten to pass new-code qualification.

## Evidence / tests

Before extraction, replay all 30 already exposed native R1 images with the existing reference profile and observed source episode. Verify original PNG and decoded pixel bindings, then verify bound input files at completion. This produces 22 descriptive links in 49.030276 seconds. After extraction the same inputs produce 22 links in 48.654446 seconds (delta −0.375830 seconds, a single-run fluctuation rather than a proven performance improvement). Complete serialized results and bindings, including termination and unrejoined tail, match exactly. Final results are saved in `e2e_reports/match_001/shared_scene_tracking_regression.json`.

155 related tests pass in 68.80 seconds. They exercise source identity retention, wrong/cut/duplicate termination, excluded-pixel independence, native/canonical resolutions, projected coverage, source/current review masks, unknown/competing appearance, bootstrap, observed episode protocol, frozen-code entrance and qualified lifecycle/UI consumers. Ruff passes on `src tests scripts/e2e` and changed diagnostic tools; mypy passes all 106 source files. During the first test invocation a source-binding guard correctly rejected a file edited while tests were running; the final clean invocation above passes with stable code.

## Previous / Current / Delta

| Metric | Previous | Current | Delta |
| --- | --- | --- | --- |
| Production-importable original-identity tracker |Absent|One shared module|+1 common implementation location|
| Real R1 descriptive links |22|22|0|
| Installed qualified scene/UI producer |0|0|0|
| Runtime source qualification |0|0|0|
| Canonical PASS / FAIL / NE |23 / 55 / 4|Not rerun|Unmeasured|

The complete 82-entry assertion matrix remains unchanged. Full/targeted/sampled canonical E2E is not justified by this extraction alone. Negative/discontinuity historical 0/0 is not a fresh full-run result. No Git commit/push is performed.

## Remaining blocker / next implementation

Extract source acquisition and the actual observed native episode owner into the common package. Preserve reference assets as assets, never previous observed source frames; retain exact native PTS/pixel/epoch/gap/duplicate bindings and permanent failure termination. Then establish independent source/world/phase-absence qualification before the analyzer can release paired scene/UI proofs. Appearance equality, NCC confidence and synthetic unit reports do not authorize `background_checked=true`. Windows OpenCV and packaged runtime execution remain unverified.
