# Reviewed source structure eligibility audit

## Problem

The descriptor prototype finds real correspondence in only1or2source regions. Determine whether reviewed reference images lack background structure, whether canonical resize causes that loss, or whether the descriptor detector selects the wrong structure for these crops. Target remains source evidence upstream of GT-R1-ROUND-START/END and GT-R2-ROUND-START. No timer/phase/GT value or new matcher enters this audit.

## Frozen evidence

Both current private reference assets, their existing reviewed integral boxes, source byte/native pixel hashes and diagnostic code are frozen before source-only measurement. Compare SIFT at640x360and native1920x1080with the same descriptor parameters and proportionally scaled source boxes, then inspect the existing canonical corner/self-patch eligibility route. This is source structure/self evidence only, not temporal matching or independent qualification. Terminal hashes match in both reports.

| Source | Canonical SIFT descriptors / regions | Native SIFT descriptors / regions | Existing canonical eligible corners / regions |
| --- | --- | --- | --- |
|R1wall|8 /1(region2)|7 /1(region2)|180 /6|
|Arch context|8 /2(regions0,2)|35 /2(regions0,2)|78 /3|

Existing corner eligible counts by source region:

- R1:11,31,51,1,31,55 across regions0–5.
- Arch:23,46,9 across regions0–2.

These corner counts have complete source patch/texture/self-NCC/forward-backward eligibility at the unchanged floors. Self-camera consensus is180/180and78/78, respectively. They are **self matches**, not independent current correspondence, camera uniqueness, semantic current world masks or timing proof. Native descriptors cover a smaller physical detail scale despite normalized coordinates; do not present native/canonical counts as the same physical support footprint or multiply them into independent evidence.

## Competing hypotheses / conclusion

1. Missing reviewable background structure in all source areas: not supported by the existing corner measurements. All6/3source regions do contain eligible corner/self-patch structure.
2. Threefold canonical resize alone removes the required distributed descriptor support: contradicted for these same assets. Native extraction increases the arch descriptor count but still supports only2regions; R1remains1region.
3. Descriptor **detector/representation** eligibility selects too few of the reviewed source corner structures: supported by the contrast between method-specific region coverage. This does not prove that those corners can match the displaced actual query; raw-NCC/current-crop failures remain genuine.

The previous descriptor report is about that method's support, not proof that the references contain no usable world structures. Do not replace existing references or lower3-region/descriptor/NCC criteria based only on descriptor absence.

## Continuity decision / contract change

No code/profile/threshold or recognition behavior changes. No scene link, current-frame fact, boundary, package or trace result is emitted by this source-only audit. The already observed R1visible-continuity conclusion remains descriptive. Qualification remains0and all82historical assertion statuses are unchanged.

## Tests

Two frozen source surveys complete with exact terminal input/code hashes. Existing corner instrumentation accounts for every source feature by first rejection stage; eligible/self-inlier counts agree. No modified implementation needs a new unit run: preceding19descriptor/domain/joint tests and104-source-file mypy PASS cover unchanged code. No targeted/sampled/full E2E was run because no new production candidate exists. Windows execution remains unverified.

## Previous / Current / Delta

| Metric | Previous canonical | Current native | Delta |
| --- | ---: | ---: | ---: |
|R1descriptor eligible regions|1|1|0|
|Arch descriptor eligible regions|2|2|0|
|R1descriptor count|8|7|-1; physical footprint differs|
|Arch descriptor count|8|35|+27; physical footprint differs|
|Canonical PASS/FAIL/NE|Historical23/55/4|Not rerun|Unmeasured|

Corner/native descriptor methods are not aggregated as improvement scores. Source survey runtimes are stored separately and are not comparable workloads.

## Next implementation / remaining blocker

Reassess how to describe **existing reviewed eligible corners** for displaced/normalized correspondence, preserving full source context restrictions, reciprocal/physical uniqueness, all original-match model/photometric denominators,3independent world domains and complete current-domain/joint appearance. This is a detector-to-descriptor integration question before another matcher/reference-bank trial. Source eligibility alone cannot authorize current/background labels or replace independent acquisition-plus-continuous/negative/paired-UI qualification. Runtime lifecycle/package/canonical acceptance remains incomplete.
