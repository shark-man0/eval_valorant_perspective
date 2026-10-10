# Existing corner to descriptor acquisition integration

## Problem / hypothesis

The current SIFT detector only describes1/2regions of the reviewed assets, although existing corner/self-patch eligibility spans6/3regions. Test describing the existing corner proposals instead of rebuilding references or reducing source support. Target remains source input upstream of GT-R1-ROUND-START/END and GT-R2-ROUND-START; no GT, timer/phase values, timestamps or round IDs enter the function.

## Contract change

The descriptor diagnostic accepts explicit `feature_source=reviewed_corners`. It reuses the existing per-crop GFTT100features/quality0.01/minDistance5detector, then computes fixed size3/orientation0SIFT descriptors from that crop input. No SIFT contrast threshold is reduced and no fallback is implicit. Descriptor input is crop-local; any library border extension is preprocessing, not independently observed support or NCC confidence. The separate actual projected15pxpatch and full-domain tests still require real current interpolation taps. The source proposals are **not** the180/78earlier LK-qualified self matches: candidate selection/context/status differ and counts must not be promoted between methods.

Default SIFT output remains exactly unchanged on all five frozen real pairs. The descriptor proposal ratio0.75, reciprocal/physical uniqueness,3regions,2pxmodel with90%original correspondence support,90%original projected-photometric support atNCC0.90, complete current-domain eligibility and distributed joint-lattice rejection are unchanged. No production observer/runner or profile is switched to this diagnostic variant.

## Evidence

Five preselected exposed source/query pairs are frozen with source/profile/assets/code/image hashes before measurement and checked at termination.

| Source/query | Previous matched regions / proposal | Current physical matches / regions | Model/photometric | Current proposal |
| --- | --- | --- | --- | --- |
|Arch self13.002669|2 /False|16 /3|16/16 /16/16|True, self only|
|Arch displaced13.202669|1 /False|2 /2|Not evaluated|False|
|Arch different6.002669|1 /False|0 /0|Not evaluated|False|
|R1self3.902669|1 /False|16 /2|Not evaluated|False|
|R1phasegone4.102669|1 /False|16 /2|Not evaluated|False|

The source corner descriptor pools include all reviewed regions: R1counts23,54,51,40,62,65(total295); arch22,44,8(total74). Current selection differs: R1self search-region counts3,43,46,27(total119), R1phasegone3,34,34,23(total94). Actual R1correspondences remain15fromregion2and1fromregion5. The new arch query's first current search strip supplies only2candidate descriptors and no source upper-arch correspondence. This points to current candidate selection/correspondence under changed crop context, not absent source corner structure. It does not prove that increasing feature budgets or changing normalization will solve actual correspondence; no such tuning is performed here.

The arch self-match reaches all existing model/projected-NCC/full-domain/joint gates with three distinct source regions. It is development calibration, not independent correct acquisition. The actual displaced image still cannot acquire three-domain support. Source clock or current semantic world masks are not inferred, and unknown is not labelled a cut.

## Tests

24descriptor/domain/joint cases PASS in17.41seconds, Ruff/diff checks PASS. Both explicit representations pass synthetic translation and2degree rotation/1.02scale with final photometric/joint support; constant/unrelated scenes, UI exclusion, protected destinations, physical duplicate/conflicting associations and unknown representation rejection remain covered. Frozen five default outputs compare exactly; terminal file hashes match. Source-only candidate distribution audit uses the same pinned code/assets. Production code unchanged; preceding104-source-file mypy PASS applies. Windows/OpenCV execution remains unverified.

## Previous / Current / Delta

| Metric | Previous | Current | Delta |
| --- | ---: | ---: | ---: |
| Exposed5-pair diagnostic proposals |0/5|1/5|+1; self calibration only|
| Actual arch displaced proposals |0|0|0|
| Actual R1phasegone proposals |0|0|0|
| R1phasegone physical matches, representations differ |4|16|+12; no accepted acquisition|
| Runtime qualification/events |0/0|0/0|0|
| Canonical PASS/FAIL/NE |Historical23/55/4|Not rerun|Unmeasured|

The real-pair runtime is recorded in `corner_descriptor_acquisition_development.json`; its default-equivalence checks add workload and prevent speed comparison to the earlier prototype. No independent holdout, standard targeted/sampled or full E2E was run because actual-query development gates still fail. No assertion PASS is claimed and no new reference/image bank is deployed.

## Remaining blocker / next task

Current corner candidate selection over larger search crops and correspondence uniqueness do not preserve the reviewed source region coverage. Before another recognition method, assess whether matching source/current candidate **spatial eligibility** can preserve existing detector conditions without reducing support, adopting an ambiguous match, exposing protected UI or trimming failed photometry. Source candidate295/74counts alone are not independent evidence. Freeze any redesign and disjoint acquisition-plus-continuous/negative/paired-UI qualification before runtime activation. R1start/result, R2start, lifecycle/package/trace/canonical acceptance remain incomplete.
