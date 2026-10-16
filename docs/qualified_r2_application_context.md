# R2 application transport with actual source-origin context

The previous48-frame R2-only application call still rejects calibration with `HUD calibration_required: insufficient_anchors`. A distinct current-code execution includes actual source-origin images as ordinary sampled observations, using the same context condition as the earlier R1 application test. This51-frame ordinary application call succeeds without changing code, thresholds, calibration rules or the previous failing result.

## Fixed method and two separate inputs

Implementation commit `abeb0118f4700b91e939e9ee27b0e9c72a103593`; recognizer `d14e4b78b3e1fae4df0d154d21067b452796794a9c954992cf7f2ebb12a6d091`; profile `fc3b8dfc4c4e9c72e6bbbaf7c5a90762ad879ea695dff8784997123e1f56f51c`; freshly measured Start-only admission `19a2ccedcafb8af48d14edcaf1e072fd0619eb9ed2f799874d033ab028948212`. Original source and unedited-input contract are unchanged. This is an exposed source regression, not new independent accuracy qualification.

The qualified native producer reads48 consecutive current frames111–111.8s and uses only the first source-origin frame as its geometry reference. Its source rows do not include origin frames or carry lifecycle/continuity across epochs. It produces Start111.4193359375s, confirmation111.48600260416667s, confidence0.931477963924408.

The ordinary application is independently given51 real sampled observations: three decoder-owned source-origin frames from0–0.08s and all48 R2 frames. Their exact PTS/timebase/source/encoded hashes are supplied to FrameSample. Origin images participate in ordinary HUD analysis as actual observations; this differs from their geometry-only role in the native producer. They are not hidden inputs or invented prior state. The native producer output and complete geometry provenance are revalidated before and after application publication while reference images remain readable.

The first sampled PTS is0.03600260416666667s, last origin PTS0.0693359375s and first R2 PTS111.00266927083334s. There is an unsampled110.93333333333334s interval. It is **not** a native continuous stream or proof of R1→R2 lifecycle. Ordinary source continuity rejects an oversized inter-observation gap; this experiment does not measure the intervening source cuts or infer active-Round state across that gap. Earlier native duplicate-raster/cut checks remain separate evidence. No epochs or native observation rows are spliced.

## Result

The actual `HudVideoProcessor.process_frames` call completes ordinary HUD observation, native boundary validation/merge, Package construction, schema validation and Trace conversion. It emits one partial Package and one Start event with **exact native attributes**. Both native and application traces contain zero snapshots; every application observation remains primary-state unknown with player-specific HUD invalid, and no player-owned fact is released.

The Package starts at preparation111.0693359375s, which remains in the actual R2 window, and ends at171.019336s, the video-duration sentinel. Timeline completeness stays0 with the complete Package interval marked missing. A duration sentinel is not an End event. Adding source-origin observations does not pull preparation back across the sampling gap.

The event still belongs to local `sample_round_1`. Evaluating the saved application trace with unchanged assertions yields **GT-R2-ROUND-START FAIL**, `missing_point:GT-R2-ROUND-START`, because canonical expects match-wide Round2. No renumbering, GT adjustment or canonical baseline update is performed. Full E2E and the full default sampler are not run.

Measured native production14.526s, application processing14.601s,total35.417s; retained PNG76,624,131 bytes; process peak RSS146,636,800 bytes, decoder child peak unmeasured. Runtime differences from earlier runs are not controlled performance improvements. Source/code/profile/contract/admission and actual reference images pass terminal integrity checks. Full hashes and exact values are in `e2e_reports/match_001/qualified_r2_application_context.json`.

## Scope and remaining work

This proves fixed-frame application transport **when valid earlier source images are ordinary measured input**, using existing calibration retention. It does not fix cold R2 calibration, provide a public automatic initialization option, validate full default sampling, establish match-wide Round2 membership or qualify End. Keep the original cold-fragment rejection as a separate test condition.

Reproduction uses the private profile/admission/video with `PYTHONPATH=src:. .venv/bin/python work/qualified_geometry_r2_application_context.py`. The runner freezes its selection before prediction, holds both real decoder contexts live through publication, saves native and application artifacts and rechecks all identities. `work/qualified_geometry_evaluate_r2_application_context.py` evaluates only the saved application trace after production. GT is not a recognizer input; private artifacts remain outside Git. This report-only checkpoint changes no recognizer fingerprint, so a repeated full test run is unnecessary. Current implementation CI cannot be refreshed while automatic approval review rejects network actions due to its usage limit. Canonical23 PASS/55 FAIL/4 NOT_EVALUATED is unchanged; formal End and whole-lifecycle qualification remain incomplete.
