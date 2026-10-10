# Source acquisition fixed-crop failure investigation

## Problem

The actual observed observer cannot initialize the new13-second camera context from the original wall reference. Test the bounded hypothesis that one independently reviewed source-background reference for this context permits image-derived acquisition on a different, pre-reserved continuous native interval. The target remains upstream evidence for GT-R1-ROUND-START/END and GT-R2-ROUND-START; no boundary, timer or round ID enters this experiment.

## Evidence

A separate private diagnostic profile retains the original wall reference and adds the already-reviewed13.002669source image. Three integral640x360background boxes identify left upper arch trim `[170,45,214,117]`, left wall below minimap `[70,170,160,235]`, and right upper arch/wall `[440,40,580,100]`. Full native context review excludes timer/phase protected pixels, players and weapon in the **source asset**. It does not authorize unreviewed current pixels as a semantic world mask. Profile assets/code/source SHA256 are frozen before the new13.2–13.4interval is decoded.

All12new native images have0known PNG/native-pixel overlaps against the pre-decode inventory. The interval never initializes, terminates at the first image and never rejoins;0/11links are supported and0joint links are evaluated. Measurement takes13.920095seconds. The new profile self-matches with78tracks/78inliers and a joint proposal; the old wall still has0tracks. The held first image has0accepted tracks even against its new source context. Thus adding another static pose is not sufficient; the new profile is not adopted or installed in production.

## Competing hypotheses

1. Missing reference for the camera scene: explains old reference0tracks, but cannot alone explain the new reference's0tracks on nearby unseen input.
2. NCC acceptance too strict: contradicted as the cause of this measured failure because no current correspondence reaches the NCC stage.
3. Fixed source/current crop correspondence cannot accommodate the changed viewpoint: supported by the flow-stage counts and independent full-image comparison of arch/wall displacement. This does not prove a content discontinuity or establish exact camera motion.
4. Lack of source texture: not the immediate cause;136source features are detected and78pass on self-match. Large portions are nevertheless unsuitable/near crop edges, so this is not broad world eligibility proof.

## Independent image evidence

The13.002669training and13.202669evaluation full native images show similar architectural context with displaced arch/wall structure and changed foreground positions/weapon. This review occurs after fixed predictions and does not change profile boxes or acceptance. Only the first evaluation image has been reviewed; do not infer continuity ground truth for the whole12-frame interval. Neither displayed timer, phase, score nor GT is used in source matching or template selection.

## Failure stage diagnostics

A passive optional `rejection_sink` in the existing offline reference matcher partitions each source feature by its first rejection stage. It changes neither feature selection, matcher bounds, thresholds nor result schema when absent. All original two-image bootstrap dictionaries compare exactly with the frozen earlier outputs after instrumentation.

| Stage | Source self-match | First evaluation image |
| --- | ---: | ---: |
| Source features |136|136|
| Invalid flow/status/nonfinite |1|107|
| Forward/backward error rejection |0|29|
| Patch outside crop |57|0|
| Texture rejection |0|0|
| NCC rejection |0|0|
| Accepted |78|0|

Rejected+accepted counts sum exactly to136in both cases. The fixed-crop optical-flow acquisition stage fails before photometric/model/joint qualification. Do not reduce NCC, increase tolerated forward/backward error or add more reference poses to conceal this failure.

## Continuity decision / contract change

The held interval remains unknown at acquisition; it is not classified as a cut and is not counted as11wrong links. Production remains fail-closed. The proposed extra profile is a failed, private diagnostic hypothesis. The only code change is passive rejection instrumentation; no production behavior or boundary contract changes. Previously exposed R1visible-continuity evidence remains descriptive; no scene/UI qualification is emitted.

## Tests

45reference/initializer/observer/cohort cases PASS in32.59seconds. Three new cases cover motion, unrelated replacement and no-texture input, verifying exhaustive first-rejection accounting and exact unchanged default result dictionaries. Ruff/diff checks PASS. Two real source/evaluation bootstrap outputs remain exactly identical after instrumentation; declaration/terminal profile/image/instrumented-code hashes match. No standard targeted/sampled/full E2E was run because no qualified production candidate exists. Production source unchanged; preceding104-source-file mypy PASS applies.

## Previous / Current / Delta

| Metric | Previous | Current | Delta |
| --- | ---: | ---: | ---: |
| Old reference on original13.0context |0proposals|Not rerun as a cohort|Not comparable|
| Extra source reference self-match |Not measured|1proposal/78tracks|Not comparable|
| New interval image-derived acquisition |Not measured|0/1episode|Not comparable|
| New interval joint links actually evaluated |Not measured|0|Not comparable|
| Code changes affecting acceptance |0|0|0|
| Runtime qualifications/events |0/0|0/0|0|
| Canonical PASS/FAIL/NE |Historical23/55/4|Not rerun|Unmeasured|

No new assertion passes are claimed. The new interval and source are now exposed and cannot be reused as an independent holdout after redesign. Windows execution remains unverified; assets stay local with relative paths and shared Python profile format.

## Remaining blocker / next implementation

Reassess **source-world acquisition under displacement** before qualifying this observer. The fixed reviewed reference crop is a source identity support domain; it must not automatically constrain a moving background to the same current crop. A redesigned acquisition proposal would need independently supported current search/projection, exclusion of protected UI, explicit multiple-hypothesis ambiguity rejection, complete appearance witnesses, and disjoint acquisition-plus-continuous/negative qualification at the existing safety floors. It must neither transfer source world labels to arbitrary current foreground nor supply reference assets as prior native observations. Do not silently deploy a wider search as a qualified producer. This is an acquisition mechanism problem, not justification to tune R2/end/geometry/OCR thresholds. Round start/end and canonical package improvements remain incomplete.
