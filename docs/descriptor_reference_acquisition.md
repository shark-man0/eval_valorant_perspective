# Descriptor-proposed source camera acquisition

## Problem and target

Raw15pxNCC patches and fixed source/current optical flow cannot acquire the displaced13-second scene. Test a motion/scale-normalized descriptor geometry proposal, followed by existing source support/NCC/current eligibility gates. Target remains independently observed source evidence for GT-R1-ROUND-START/END and GT-R2-ROUND-START; no expected values, timer/phase pixels or GT times enter the algorithm.

## Contract change

A separate pure diagnostic function creates SIFT pyramids from each declared source/current crop only. Source descriptor context never accesses pixels outside reviewed source crops. Current candidates remain inside declared non-UI search crops. Keypoints near crop edges are discarded. A fixed reciprocal nearest-neighbor ambiguity ratio0.75 proposes correspondences only; descriptor distance is not NCC confidence and never authorizes a fact. Source/current physical coordinate duplicates count once, and conflicting location associations are withheld entirely; multiple orientations cannot inflate evidence.

A proposal needs>=3independent source regions and>=3correspondences before the existing partial-affine2pxRANSAC/90%original-match support gate. It then verifies projected15pxpatches atNCC>=0.90, including every current interpolation tap, requiring>=90%original matches and3regions. The model is not repaired by deleting failed photometric witnesses. Complete domain NCC/current footprint eligibility/distributed joint local-lattice ambiguity must still pass. All outputs retain runtime/world-mask/qualification=False. This function is not called by production, the observed observer or cohort runner. It does not supply prior source PTS/pixels, events or ownership.

## Tests

19descriptor/domain/joint cases PASS in10.21seconds, Ruff/diff checks PASS. Actual matching recovers synthetic20pxtranslation and2degree rotation/1.02scale plus translation while requiring projected photometry and joint appearance. Constant/unrelated images and protected destinations abstain. Excluded timer/phase changes leave proposal output exactly unchanged. Duplicate orientations collapse to one physical witness, conflicting source/destination associations are unknown. Production source unchanged; preceding104-source-file mypy PASS remains applicable. The first18-case version also passed before the physical-support guard;19is the current tested implementation.

## Exposed real-image evidence

Five source/query pairs are frozen with profile/assets/source-video/dependency/current native image hashes before measurement and terminal verification. Both descriptor and final distinct-physical versions yield0proposals. Existing source box geometry, reader thresholds and qualification policy remain unchanged.

| Source/query | Descriptor matches | Distinct physical matches | Supported source regions | Result |
| --- | ---: | ---: | --- | --- |
|Arch / self13.002669|8|8|0:3,2:5|3-region support unavailable|
|Arch / displaced13.202669|1|1|0:1|3-region support unavailable|
|Arch / different6.002669|1|1|0:1|3-region support unavailable|
|Original R1wall / self3.902669|7|7|2:7|3-region support unavailable|
|Original R1wall / phasegone4.102669|4|4|2:4|3-region support unavailable|

Each reference has8eligible descriptors; the arch's source middle-wall region and most original wall regions supply no reciprocal descriptor correspondence, even on self-query. Matching descriptors cannot be treated as three independent background domains. No pair reaches model/photometric/joint evaluation, so these are source-support failures rather than low final NCC or wrong continuity classifications. The limited-source model is not fitted to one region then promoted to full-frame proof. All pairs are exposed development/controls, not independent holdout. The distinct-physical replay preserves the earlier proposal decisions and passes frozen terminal verification; runtimes are recorded in both machine reports.

## Competing hypotheses and decision

Motion-normalized appearance recovers the synthetic changes, but does not solve real reference support. The existing reviewed source profiles contain insufficient region-distributed eligible descriptor structure for this method. Do not call SIFT a production improvement or lower source region count/descriptor/NCC gates to obtain a result. This hypothesis is rejected for these references; no new reference bank, independent holdout, standard targeted/sampled/full E2E or recognition candidate follows from the synthetic result alone. Visible R1continuity remains the conclusion of previous native continuous image evidence, not this failed stateless experiment.

## Previous / Current / Delta

| Metric | Previous | Current | Delta |
| --- | ---: | ---: | ---: |
|13.202669correspondences (raw-patch / descriptor representations)|0|1|+1; not accepted evidence|
|13.202669final acquisition proposals|0|0|0|
|Real5-pair descriptor proposals|Not measured|0/5|Not comparable|
|Model/joint stages evaluated on those5pairs|Not measured|0|Not comparable|
|Runtime qualifications/events|0/0|0/0|0|
|Canonical PASS/FAIL/NE|Historical23/55/4|Not rerun|Unmeasured|

No new assertion PASS is claimed. Source profile13/16 historical E2E numbers remain historical; current canonical values are null/unmeasured. Windows/OpenCV SIFT execution remains unverified. Shared Python and relative profile assets remain portable, but no cross-platform validation is claimed.

## Remaining blocker

Current reference support is adequate for a narrowly initialized native tracker but not independently reacquired three-domain structure with this descriptor representation. Reassess which independently observable world structures/source-domain eligibility can constrain displaced camera hypotheses before generating another matcher. Preserve all three final background witnesses/current tap protections/ambiguity and disjoint qualification; do not replace independent evidence with synthetic/self-image success. Production scene/UI qualifications, R1/R2start/result boundary producer and canonical package/trace acceptance remain incomplete.
