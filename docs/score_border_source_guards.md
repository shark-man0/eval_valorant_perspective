# Exact-code CI and qualified source guards after the score-reader checkpoint

The actual pushed code commit `16ff877d41e74c4dbd324d74c2f9360e797cc48c` passes its own Linux and Windows CI. Both full test steps and Ruff/mypy/dataset steps succeed; Windows also builds and smoke-tests the packaged application. Linux:3807 PASS/7 SKIP,897.82s,coverage86.63%. Windows:3803 PASS/11 SKIP,614.55s,coverage86.59%. Its Python text I/O gate also succeeds. The local macOS3801 PASS/4 existing FAIL/9 SKIP result remains separately recorded, rather than replaced by remote results.

Links: [Linux run](https://github.com/shark-man0/eval_valorant_perspective/actions/runs/38669572489), [Windows run](https://github.com/shark-man0/eval_valorant_perspective/actions/runs/38669572502), [text I/O run](https://github.com/shark-man0/eval_valorant_perspective/actions/runs/38669572532). These results apply to16ff877, not automatically to later commits. A live remote check still finds main `7e480c2f2f7f49aea73e1541d065d78881d2f11c`.

Fresh actual formal native calls use recognizer `ddc5e6c2…`, profile `fc3b8dfc…` and reviewed Start-only bundle `85caed7d…`. Source/contract/profile/code/bundle identities pass terminal checks. No prefix, expected boundary or foreign-epoch state is injected.

| Current qualified call | Result | Resource measurement |
| --- | --- | --- |
|81.70–81.90s,12 frames|Exact source cuts81.78600260416667 and81.83600260416667, final segment2; zero events/owned facts|5.365s,25,748,283 PNG bytes,process peak RSS121,700,352 bytes|
|111.0–111.8s,48 frames|Zero events/owned facts; all48 frames unknown due to insufficient anchors|14.043s,70,650,570 PNG bytes,process peak RSS122,290,176 bytes|

The R2 result is a real failure to detect the known Start through this declared entrance, not evidence that R2 does not exist. The top_match_bar matches all48 frames (confidence0.993399–0.997586). Round timer, player HP/armor and abilities anchors match zero frames: their maximum confidences are0.857025,0.663296 and0.604128 respectively, below the unchanged0.90 threshold. The layout requires3 accepted anchors; accepting just the top bar would relax the contract and is not done. The profile's old `temporal_generation.sample_count=64` is inherited generation metadata, not64 freshly observed or newly independent frames.

The earlier diagnostic R2 pattern used an explicitly supported geometry-only initialization image. The formal qualified entrance has no such parameter. Reusing an unrelated analyzer call or inserting R1 lifecycle state would not be a supported fix. The fresh source-break call confirms that failed geometry does not suppress duplicate-raster continuity cuts.

## Next implementation contract

A separately declared initialization API may reuse the already guarded geometry-only reference mechanism, subject to these requirements before formal adoption:

- Require a real earlier decoder-owned image, the same source SHA/timebase/dimensions and a current unedited source contract; re-read encoded and pixel identities. Never turn its separate decoder epoch into continuity proof.
- Require the existing full anchor calibration on that image. Keep minimum anchor count, scores, size/position tolerances and all contradictory-current-geometry vetoes. A merely missing current anchor is distinct from a contradictory geometry observation.
- Bind the exact reference identity, current profile/code/qualification and input contract to the native artifact and event provenance. Recheck reference and contract at production completion and again before Package/Trace publication; altered or missing assets withhold output.
- Send only current-window observations into phase/timer/score/result and the lifecycle tracker. Prefix purchase, numeric clock, result, score, player identity, active Start or continuity state must never enter the tracker or Package.
- Negatively test foreign source, later/equal PTS, mismatched timebase/dimensions, changed/missing images, stale code/profile/bundle, contradictory geometry, source breaks, repeated raster and prefix-only boundary evidence. Preserve the default prefix-free API behavior.
- Freeze before independent evaluation, rerun original fixed negative/continuity regressions and current source checks, and obtain fresh current-code qualification. A synthetic transport pass or recovery on the exposed R2 episode alone is insufficient for full lifecycle qualification.

This is the next candidate contract, **not an implemented or admitted capability**. Existing unqualified prefix support is not relabelled as formal admission. No production code, calibration threshold or qualification is changed by this report. Formal End, R2 entrance and complete lifecycle remain unqualified. Full E2E is not rerun. Aggregate, complete fingerprints and private-artifact hashes: `e2e_reports/match_001/score_border_source_guards.json`.
