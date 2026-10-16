# Explicit geometry initialization for the qualified native entrance

The bounded R2 source window cannot calibrate from a cold start: only the top-match-bar anchor matches, while three anchors are required. Diagnostic measurement already had a guarded geometry-reference route, but the qualified native entrance did not. Add optional `calibration_prefix` to `observe_qualified_unedited_native_start_frames`. The default remains prefix-free.

The reference must be an earlier real `NativeSourceFrame` with the same source SHA, timebase and dimensions and an explicit current unedited-input contract. The existing full anchor calibration runs on the reference; current geometry contradictions still veto use. This does not lower the required anchor count, template thresholds or tolerances. Retention is the existing insufficient-anchor-only rule. The separate reference epoch is recorded as geometry provenance, never a continuity segment or active Round state.

Only current-window images enter value readers, phase scans, the source-row stream and the lifecycle tracker. The reference cannot provide a timer, phase, result, score, player identity, Start, End or continuity observation. A boundary still needs its own current-window evidence. No default profile, qualification or automatic full-video sampler option is enabled.

`NativeGeometryInitialization` stores the source-owned reference and first-window frame plus an immutable JSON context. It binds reference encoded/pixel hashes and source epoch, window-first identity, source contract, profile/code/qualification fingerprints and producer fingerprint. Current rows carry its SHA. Qualified event provenance includes the complete geometry-only context. The producer rechecks it at completion; `validated_native_boundaries` reconstructs the normal lifecycle, re-reads the reference, verifies row bindings and enriches the expected events before comparing them with the transported output. Missing initialization, altered context or changed images withhold output even when there are no events. Removing only the initializer cannot turn an initialized artifact into a default artifact.

The reference image must remain readable through application/Package/Trace publication. Keep its decoder context alive around the consuming call, or retain its exact source-owned asset with the same hashes. Saved JSON predictions alone do not reconstruct a qualified initialized result. Profile/code/bundle and source-contract validation remain separate requirements.

```python
# Both contexts hold genuine decoder-owned frames; the reference carries no
# lifecycle state across their different epochs.
with decode_native_window(video, start_sec=0, end_sec=0.08, **source_options) as origin:
    with decode_native_window(video, start_sec=111, end_sec=111.8,
                              **source_options) as current:
        analysis = analyzer.observe_qualified_unedited_native_start_frames(
            current, native_step_ticks=256, input_contract_path=contract_path,
            video_metadata=metadata, calibration_prefix=origin[0],
        )
        # Validate/consume while origin[0] remains readable. This does not
        # assert that the two windows form one continuous temporal segment.
```

## Qualification and source evidence

This is a bounded pipeline change, not an independent new recognizer-accuracy cohort. Original training/held/negative physical assignments and exposure are retained. Fresh code/profile/source checks, static reader calls and eight-window native comparisons precede rebuilding the private Start-only admission; its fingerprint is never merely re-signed. The preceding bundle and original six-component bundle are actually rejected on the changed code. No End components are admitted and no sidecar is installed by default.

Fresh R1 Start, explicit R2 initialization, prefix-free R2, fixed negatives and duplicate-raster windows are measured separately. A local R2 fragment Package has local numbering; it does not establish match-wide Round2 ownership or a continuous R1→R2 path. The known R1 End approximately3.003ms miss and original canonical23/55/4 baseline remain unchanged. Source-bounded code/profile/bundle identities and complete measured results are in `e2e_reports/match_001/qualified_geometry_initialization.json`.

## Application boundary and safety

The first real R2 integration attempt reaches native Start/Package/Trace, then the ordinary application HUD pass raises `HUD calibration_required: insufficient_anchors`. Keep that rejection. The new native reference does not override the independent sampled HUD calibration or certify player facts. The initial harness saved native artifacts only after application success, so its native timing/outputs were not retained. Preserve that failed attempt; a declared fresh replay saves native artifacts before attempting application integration and records the application failure separately. It is not new independent evidence or a hidden exporter-only recovery.

Synthetic transport tests demonstrate exact provenance through Package/Trace when the receiving analyzer is otherwise valid. They do not establish success of the real R2 application pass. Native-only schema-valid partial Package/Trace, formal-loader admission, independent timing accuracy, complete match-wide membership and full application success are distinct claims.

The initialization does not conceal current-epoch repeated rasters, gaps, source mismatches or contradictory geometry. It carries no player-owned facts and does not synthesize an End for a partial Package. Video duration as a Package upper bound remains a sentinel. Known source cuts81.78600260416667s and81.83600260416667s are preserved; source windows/epochs are not concatenated.

## Verification and remaining work

New synthetic tests cover cold-entry compatibility, reference-only geometry/value/phase separation, foreign source/timebase/dimensions/PTS, current-geometry contradiction, missing/changed images, mid-production mutation, stale code/profile/qualification/producer, altered row/context transport, prefix-only inputs, current PTS gaps, repeated rasters, Package/Trace provenance and terminal publication guards. Full regression, current source measurements and current-commit CI are reported with their own identities in the aggregate.

Formal End and the full lifecycle remain unqualified. Remaining gates include independent exact temporal End and negative annotations, delayed-caption/Spike/decimal paths, real R2 application HUD calibration, complete same-epoch active Start→End evidence, match-wide Package/preparation membership and R2-to-EOF no-false-End coverage. Full E2E is not rerun and main is not merged.

## Measured checkpoint

Recognizer fingerprint `d14e4b78b3e1fae4df0d154d21067b452796794a9c954992cf7f2ebb12a6d091`; source `71d58558…`; unchanged profile `fc3b8dfc…`; freshly measured/reviewed Start-only bundle `19a2ccedcafb8af48d14edcaf1e072fd0619eb9ed2f799874d033ab028948212`. The preceding `85caed7d…` bundle is actually rejected. Training/held/negative UI supports remain9/7/90 with original exposure, not a new blind cohort. Additional-source caption/score held results on prior fingerprints remain historical evidence, not current-code qualification.

| Actual current result | Evidence and scope |
| --- | --- |
|R1 native358 frames|Start4.102669270833333s, confirmation4.202669270833334s,confidence0.9117099378029602; partial Package1/Trace event1; owned facts0; canonical R1-start PASS|
|R1 actual application39 frames|Package1/Trace event1 with exact native attributes; canonical R1-start PASS|
|R2 explicit initialization48 frames|Start111.4193359375s, confirmation111.48600260416667s,confidence0.931477963924408; native partial Package1/Trace event1; owned facts0|
|R2 prefix-free48 frames|Still all unknown/insufficient anchors,zero events; default behavior preserved|
|R2 actual application attempt|Rejected with `HUD calibration_required: insufficient_anchors`; no successful application result or Trace is claimed|
|R2 canonical assertion|FAIL (`missing_point:GT-R2-ROUND-START`). Actual fragment event belongs to `sample_round_1`; canonical expects `sample_round_2`. No renumbering is performed|
|Source/negative guards162 frames|Both cold and initialized12-frame cut windows preserve exact cuts81.78600260416667/81.83600260416667s,segment2,zero events; three initialized Start-negative windows90 frames emit zero events/owned facts|
|Fixed static/native regressions|Original counts unchanged,369 native frames/eight windows; R1 End119 correct/97 unknown/0 wrong score fields, same unqualified74.48600260416667s End|

R2's native Package begins at preparation111.0693359375s, ends at the duration sentinel171.019336s, and has timeline completeness0 with an explicit missing interval. That upper bound is not a detected End. Local preparation inclusion is observed; correct match-wide Round2 membership remains unproven.

Native R2 replay: producer16.339s, application attempt5.573s,total28.693s,retained PNG76,624,131 bytes,process peak RSS147,193,856 bytes. Native R1: producer120.851s,total155.594s,PNG607,990,858 bytes,RSS134,234,112 bytes. R1 application: processing10.447s,total16.012s,RSS147,931,136 bytes. Six source-guard calls total82.277s,RSS127,729,664 bytes. Concurrent test activity and different PNG prediction settings prevent controlled runtime/storage improvement claims; child-decoder peak RSS is unmeasured.

New synthetic tests32 PASS. Dataset38 PASS, Ruff/mypy134 files/UTF-8 audit PASS. Full local regression **3833 PASS/4 existing spectator FAIL/9 SKIP**,460.16s,coverage86.6659%,exit1; no Qt shutdown abort observed. Current implementation CI must be checked after push; preceding16ff877 Linux/Windows success does not transfer automatically. Overall remains **B**, with real R2 native admission and partial transport improved but full application/membership/End qualification incomplete.
