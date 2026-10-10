# Displaced reference acquisition hypothesis

## Problem

The frozen source/current crop optical-flow matcher loses all136source features before NCC on the new13-second context. Test whether separating reviewed source support from declared current search destinations solves acquisition without threshold reductions. This is upstream source evidence research for GT-R1-ROUND-START/END and GT-R2-ROUND-START; no GT/clock/phase values are input.

## Contract change

The existing diagnostic unique reciprocal patch search now accepts optional `current_boxes` distinct from the reviewed source boxes. Source GFTT/15pxpatches remain entirely inside the reviewed asset crops. Current candidates must lie entirely within declared non-UI search crops; NCC>=0.90, second distinct qualifying peak rejection and reciprocal<=1px remain unchanged. Reverse search stays restricted to reviewed source support. The original same-crop behavior and result format are unchanged by default.

The domain-bootstrap diagnostic can opt into this route via `current_search_boxes`. It retains the unchanged2pxcamera model,>=90%original correspondence consensus,>=3source regions, complete fixed-projection domain appearance and distributed joint local-lattice support. The domain audit additionally requires **every interpolation tap** to lie in the allowed current search footprint; outside samples are unknown, not trimmed/zero-filled correlation evidence. No current semantic world mask, hidden-time proof or runtime qualification is emitted. Optional reports explicitly name the acquisition method/current footprint; production observer/cohort still uses its original path.

## Independent image evidence and tests

Synthetic exact80pxmotion is recovered outside original source crops with unique reciprocal support across3regions. Synthetic40pxmotion completes the bootstrap and joint appearance stages. A crop missing one column, or a fractional projection requiring one outside interpolation tap, cannot contribute fixed-projection appearance. Protected clock/phase destinations remain invalid. Related55tests PASS in52.03seconds; after adding method/footprint report fields, six bootstrap tests PASS. Ruff/diff checks PASS. Two actual default bootstrap dictionaries remain byte-equivalent as parsed values to their frozen previous measurements. Production source unchanged; preceding104-source-file mypy PASS remains applicable.

## Real-image experiment

Three exposed images are frozen with source/profile/assets/code/image SHA256 before prediction: source13.002669, evaluation13.202669 and a different6.002669camera context control. Current search boxes exclude top clock, central phase/result area, minimap/team UI and right statistics/bottom HUD margins using conservative image geometry. They are candidate appearance domains containing potentially unreviewed foreground, **not** current world labels.

| Image / reference | Fixed-crop accepted tracks | Displaced-search tracks | Model consensus / final proposal |
| --- | ---: | ---: | --- |
|13.002669self / arch source|78|9|9/9; self proposal only|
|13.202669evaluation / arch source|0|0|No model / no proposal|
|6.002669different context / arch source|Not measured here|1|No3-region model / no proposal|
|6.002669different context / old wall|Not measured here|2|No3-region model / no proposal|

The two-image source/evaluation rejection audit partitions all78reviewed source patches. Self-search has69ambiguous distinct peaks and9accepted; evaluation has40no-qualified-NCC-peak,33forward ambiguity and5reverse ambiguity, with0accepted. Thus moving the search beyond the original crop is mechanically possible but does not solve this real-image acquisition failure. Weak/repeated texture and absence of qualified photometric correspondence remain decisive; unique matching is not weakened to reclaim self-match counts. Source/self success is never a holdout positive. The different-camera control produces no final proposal despite1/2isolated patch matches.

## Competing hypotheses / continuity decision

A destination-clipping-only explanation is insufficient: removing the same-crop restriction still leaves0unique reciprocal correspondences. That hypothesis is rejected as a complete acquisition remedy. Actual motion/scale/appearance and repeated world texture require an explicitly tested correspondence representation/model before installation. No threshold or source box tuning is performed on these evaluation images. No content cut is inferred from unknown. The exposed R1scene-continuity diagnosis remains supported by earlier continuous measurements; this experiment does not add a system round event.

## Previous / Current / Delta

| Metric | Previous | Current | Delta |
| --- | ---: | ---: | ---: |
|13.202669accepted correspondences|0|0|0|
|13.202669final acquisition proposals|0|0|0|
|13.002669self correspondences, different uniqueness scopes|78|9|-69; methods differ|
| Extra-profile runtime deployment |0|0|0|
| Runtime qualification/events |0/0|0/0|0|
| Canonical PASS/FAIL/NE |Historical23/55/4|Not rerun|Unmeasured|

The prototype is opt-in diagnostic only and is rejected as an adequate real acquisition solution. No fresh holdout/standard targeted/sampled/full E2E is started because the development evidence already shows no improvement. Frozen terminal inputs match; image files/profile assets remain private/local. Report runtime is recorded in `displaced_world_acquisition_development.json`, not compared against different workloads.

## Remaining blocker

Current acquisition needs a displacement/appearance representation that proposes a model from independently observable structure, followed by the existing high-NCC complete-domain/current-eligibility verification and explicit alternative rejection. Do not mistake low-quality or ambiguous patch counts for independent evidence, select a preferred match from competing candidates, enlarge the reference bank, reduce NCC or use expected timing as a model selector. Any future representation must be frozen and independently qualified with acquisition-plus-continuous positives/negatives before production source/UI integration. Windows execution remains unverified.
