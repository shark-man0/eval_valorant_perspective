# R1 descriptor endpoint ambiguity

## Problem / hypotheses / target

The frozen R1phase-disappearance query contains17camera-outlier descriptor endpoints whose patches nevertheless support the saved camera projection at NCC>=0.90. Test repeated appearance versus uniquely localized correspondence. This is source continuity upstream of GT-R1-ROUND-START/END and GT-R2-ROUND-START, at HEAD e9ecaf8f2f0f0dfa1f9433d40a598ec8909e9ce3. No timer, phase, score, round ID or GT input enters measurement.

## Independent image evidence

`audit_descriptor_competitors.py` retains the saved affine model, all selected endpoint identities and the predeclared reviewed source/current domains. A15pxcurrent-oriented template is sampled from the source with the inverse fixed affine linear transform. Every source interpolation tap must remain in its reviewed domain; texture std>=1. Every integer current position whose entire15pxfootprint remains within a declared current search crop is measured, with texture std>=1 and NCC>=0.90. Endpoint/projection scores additionally use complete fractional current-tap masks. No crop trimming, model refit or preferred peak selection occurs.

All17source templates are available. All17camera projections have oriented NCC>=0.979912.16/17descriptor endpoints also have NCC>=0.90; the remaining endpoint is0.741757. Every template has competing qualified integer positions farther than2pxfrom the fixed camera projection:53–1441positions. Qualifying total positions range57–1454. These are lattice positions, **not** independent local maxima, unique structures or distinct camera hypotheses. The audit retains counts and example coordinates; it never selects a replacement location.

The17points belong to reviewed source regions2(7points)and5(10points). These are limited lower-wall appearance sources, not a full-scene current semantic world mask. The same exposed frames cannot serve as independent holdout.

## Competing hypotheses / continuity decision

Appearance is demonstrably nonunique within the declared search domain. Sixteen camera-incoherent descriptor endpoints and their model predictions both explain a high-NCC local appearance, with many additional positions. Therefore high NCC plus descriptor ratio cannot certify accurate point localization here. This explains a concrete source of correspondence ambiguity; it does not prove all endpoints wrong, hidden-time continuity, or content discontinuity.

The current90%original camera-consensus rejection remains correct. Do not repair it by picking the camera-favorable subset, using projection NCC as endpoint confirmation, or promoting these positions into independent witnesses. This query is still unknown; R1UI transition is not yet qualified for runtime.

## Contract change / tests

Read-only diagnostic only; production, source profiles, thresholds, observer and evaluator remain unchanged. Three tests PASS: retained competing repeated locations, oriented source/fractional current footprint rejection and constant texture rejection. JSON serialization is covered. Ruff PASS; prior104-file production mypy PASS remains applicable. Frozen declaration/result/partition/profile/source/assets/code hashes match at termination. Windows execution unverified.

## Previous / Current / Delta

| Metric | Previous | Current | Delta |
| --- | --- | --- | --- |
| High-NCC camera-outlier ambiguity |Suspected17points|17/17have competing positions|New measured cause|
| Original R1camera consensus |26/52|26/52|0|
| Actual acquisition / qualification |0/0|0/0|0/0|
| Canonical PASS/FAIL/NE |Historical23/55/4|Not rerun|Unmeasured|

No standard targeted/sampled/full E2E was run because acquisition qualification still fails. All82assertion entries remain unchanged; no new PASS is claimed. Historical negative/discontinuity0/0is not represented as a fresh run.

## Remaining blocker / next task

Small local appearance does not identify a unique location. Source acceptance needs a coupled distributed-domain camera hypothesis and explicit competitors, rather than counting tiny patch matches. Before any such redesign, audit all source-eligible correspondences at the frozen full-domain/complete-footprint gates; these17selected points alone cannot justify accepting the remaining subset. Existing joint-domain diagnostics do not grant runtime qualification. Independent actual native acquisition/continuity/negative and paired UI qualification must precede lifecycle/package/trace/canonical integration.
