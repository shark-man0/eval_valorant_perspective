# Fixed camera whole-domain audit

## Problem / hypotheses / target assertions

Small R1patches have many high-NCC alternative locations. Test whether all reviewed background domains jointly support the saved descriptor camera model, without selecting a favorable correspondence subset. Target remains source continuity upstream of GT-R1-ROUND-START/END and GT-R2-ROUND-START. HEAD e9ecaf8f2f0f0dfa1f9433d40a598ec8909e9ce3.

## Independent image evidence

`audit_fixed_camera_domains.py` evaluates the existing full-domain audit and joint17×17integer-translation lattice for every saved pair with a model, including previously rejected pairs. It never refits the camera, adjusts thresholds, edits source/current domains or overrides original acceptance. Full interpolation taps, source/current std>=1 and NCC>=0.90 remain required. Unknown competitors never act as vetoes. Profile/assets/query/code/source/declaration/result bindings match at termination. Existing measured arch-self domain/joint results compare exactly.

| Pair | Fixed projection witness regions | Distributed support | Competing / unresolved offsets | Joint result |
| --- | --- | --- | --- | --- |
|Arch self|0,1,2|Yes|0/0|Self-only local appearance|
|Arch displaced|None|No|0/264|Withheld|
|Other scene|Model unavailable|Not evaluated|Not evaluated|Not evaluated|
|R1self|1,2,3,4,5|Yes|0/0|Self-only local appearance|
|R1phasegone|1,2,5|No|5/0|Withheld|

R1phasegone full-domain NCC: region0=0.749053, region1=0.929518, region2=0.994791, region3=unavailable, region4=0.731892, region5=0.995152. All witnesses are left-side domains; their source/current cells fail the existing distributed support rule. Region3has no invalid offsets but its current projected texture std=0.919753(<1), while source std=1.164060, so unavailable is not a missing current footprint and must not be counted as a photometric contradiction.

Five retained competing offsets are(3,-1),(3,0),(3,1),(4,0),(4,1). They explain the same fixed witness regions atNCC>=0.90. This is a declared local translation lattice, not exhaustive alternative affine/perspective/3Dcamera model coverage.

## Competing hypotheses / continuity decision

R1self whole domains provide distributed unique-local appearance although the original source patch eligibility gate still rejects its286-track proposal. That calibration does not qualify the actual query. Actual R1phasegone lacks right-side/full-scene distributed support and retains competing projections. Therefore bypassing the failed point-camera gate with whole-domain NCC would also be unsupported. Both routes correctly withhold.

The lower-wall descriptors constrain one model that fails upper/right domain appearance; camera bias, correspondence ambiguity and scene depth/projection effects remain competing explanations. This audit proves neither a content cut nor hidden-time continuity. Do not refit a selected subset or tune full-domain acceptance to these exposed frames.

## Contract change / tests

Read-only orchestration only; original producer decisions, production, geometry/NCC policies, profiles and all82assertion entries remain unchanged.13existing full-domain/joint regression tests PASS in2.60seconds. Ruff/diff checks PASS. Prior production mypy104filesPASS applies. Windows execution unverified. Diagnostic runtime7.207687seconds includes four fixed-model audits, not E2E inference.

## Previous / Current / Delta

| Metric | Previous | Current | Delta |
| --- | --- | --- | --- |
| Actual R1whole-domain joint support |Not evaluated after early rejection|No;3left witnesses and5competitors|New diagnostic evidence|
| Actual R1/arch acquisition proposals |0/0|0/0|0/0|
| Runtime qualification/events |0/0|0/0|0/0|
| Canonical PASS/FAIL/NE |Historical23/55/4|Not rerun|Unmeasured|

No standard targeted/sampled/full E2E was run because actual acquisition qualification remains absent. No assertion PASS or fresh negative/discontinuity result is claimed.

## Remaining blocker / next task

The displaced-descriptor route is rejected as a sufficient scene acquisition remedy under unchanged full-domain gates. Stop refining its weak/repeated lower-wall proposals for this query. The existing observed-native chain already measures continuous critical R1links from a qualified appearance seed; next examine its real runtime acquisition/history contract and independently test that complete path, instead of another isolated matcher. An unknown initial observation cannot itself create prior history, a reference asset is not a native previous frame, and a failed established chain must not silently rejoin. Retain these boundaries while determining whether safe delayed initialization is possible before any history exists. Runtime source/UI qualification and canonical lifecycle acceptance remain incomplete.
