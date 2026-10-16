# Current-main application merge and remaining qualification gates

## Decision

**B: partial qualification remains.** Close the actual R1 application-merge
verification gap; do not release default/full lifecycle qualification. Original
main remains `c11ec6d333957cccb270417bc95a8a57f433e6ad`; this follow-up starts from
PR #42 commit `79b6eea5b8cc559498e3873366a85fe23f593cd8`. No production source,
profile, reader, GT, threshold, timestamps, sampler or qualification is changed.
See [prior bounded results](current_main_round_boundary_requalification.md).

## Actual R1 application path

First check the current source SHA, recognizer/profile fingerprint, explicit
Start-only qualification and unedited contract against the actual prior native
run. Reuse its complete 358-row output unchanged; this is offline integration
of current producer output, not new recognition or a recognition-cache feature.
Native artifact SHA:
`969794eb923d30104b8b0056b6d22710830c3f623d583effb0682a6a5a614975`.
The unchanged application independently replays/admit-checks native events at
entrance and completion. Old historical native predictions are not inputs.

Freshly decode 39 main images at 0–0.08 and 3.9–4.5 seconds. Each image must
match the current native pixel hash at its exact integer PTS. Main FrameSample
objects retain source SHA, ticks, original timebase and current encoded-image
hash. The disjoint main windows do not supply native temporal continuity; the
complete validated 0–6 second native producer output does.

Invoke real `HudVideoProcessor.process_frames`, `RealHudAnalyzer`,
`RealVisualAnalyzer`, event-source contract and `RoundPackageBuilder`; keep
Strict mode and the existing open-fragment option `require_detected_rounds=False`.
Actual stages exercised: native admission, main HUD, source-bound timer merge,
visual analysis, world-view gating, evidence fusion, Package schema and terminal
publication checks. Full Pass A/Pass B sampler is not exercised.

One system R1 Start reaches Trace, preserving type, actor, boundary timestamp,
confidence and every native attribute exactly. Boundary 4.102669270833333,
confirmation 4.202669270833334, confidence 0.9117099378029602. No End, duplicate,
visual event, snapshot or player-owned Fact. One partial Package retains
3.602669270833333–171.019336; the upper value is a duration sentinel, not End
or processed coverage. Quality/completeness remains zero with missing interval.

Only after production, run unchanged canonical evaluation and verify assertion,
evaluator and schema hashes before/after. `GT-R1-ROUND-START` PASS. Other fragment
outcomes stay private and cannot update the adopted 23/55/4 baseline.

Processing: 12.224 seconds; acquisition/application/terminal checks: 18.475
seconds, excluding initial input hashing. Retained PNGs 45,491,368 bytes;
process peak RSS 141,721,600 bytes (macOS ru_maxrss; decoder-child RSS not measured).
Temporary images removed on exit. The first measurement script incorrectly
referenced `hud_observations` instead of `observations` after processing/merge
checks. Preserve that failed log and use one bounded rerun after correcting the
exporter only; production is unchanged. No speed/accuracy improvement is inferred
against the historical application experiment under a different environment.

## R2 actual entrance: safe failure and identified cause

Freeze a separate fresh 111.0–111.8 second native window before running it.
Use the same current explicit Start-only qualification through
`observe_qualified_unedited_native_start_frames`. Do not inject a calibration
prefix, concatenate epochs, reuse R1 state or supply expected events.

48 frames produce **zero events**. All 48 are `insufficient_anchors` with invalid
geometry, zero fresh/effective geometry successes, zero retained geometry cases,
zero timer/score confidence and no player-owned Facts. The bundle is admitted
and source/native/terminal checks pass. This is an actual failed detection in
this declared entrance/window, not proof that R2 is absent. It differs from the
previous 36-frame diagnostic window that explicitly used a source-origin image
for geometry calibration. Do not promote that diagnostic pattern into a formal
R2 event or silently import its state.

Runtime 14.035 seconds; retained PNGs 70,650,570 bytes; process peak RSS
124,321,792 bytes. Temporary images removed. The current entrance API has no
calibration-prefix parameter, whereas diagnostic `observe_native_system_frames`
has an explicit source-checked, geometry-only prefix route. `observe_frames`
reinitializes geometry for the supplied sequence, so a prior unrelated analyzer
call is not a supported substitute. No anchor threshold is lowered.

A future implementation candidate is a separately declared, source-verified
geometry initialization mechanism that transports only geometry, never lifecycle,
ownership or continuity. Alternatively exercise one bounded-storage source-origin
native replay with existing production initialization. Either requires current
fingerprint requalification, fixed training/negative data, fresh source checks
and held review; neither is implemented or treated as passing here. Repeating
this isolated window without changing the missing initialization adds no value.

## Actual source-break guard

Fresh separate native 81.70–81.90 second window, same explicit qualification,
12 frames. Real native replay/source-break extraction returns cuts at
81.78600260416667 and 81.83600260416667. Final continuity segment is 2; zero
Start/End/owned Facts. The failed geometry does not prevent source-raster break
tracking. This verifies these two actual duplicate-raster resets; it does not
prove every kind of scene continuity or an active-round lifecycle across them.
No earlier R1 event or later R2 event is joined to this epoch.

Runtime 5.232 seconds; retained PNGs 25,748,283 bytes; process peak RSS
120,946,688 bytes. Source/profile/code/qualification checks pass at completion.

## End annotation and data acquisition contract

match_001 has one already exposed End episode. Its neighboring native images,
reencodings or new annotations cannot become new independent event-level holdout.
The known score-update boundary remains 74.48600260416667, approximately
3.002604 ms beyond the fixed GT endpoint. No new earlier physical evidence has
been independently qualified. No early-caption method is retried or timestamp
shifted. The current data can support fixed regression and provenance review,
not independent End generalization.

For additional data, obtain a private source **other than match_002** and record:

- Source bytes SHA, source/recording origin, permission/access location and decoder
  version/settings; native integer PTS/timebase and pixel/encoded hashes.
- Original labels, annotator/review origin, prior development exposures, immutable
  event-level training/held/negative allocation before algorithm changes. Keep all
  supports from one physical episode in its assigned temporal cohort; report both
  image and episode units. No overlapping physical ticks or pixel hashes between
  training/held/control across components.
- Reviewed source sequence covering accepted old clock/score, clock change, first
  score update, consecutive score stability, first complete semantic result and
  confirmation; include unknown, occlusion and contradictory observations.
- Preparation and active Start in the same producer-owned decoder epoch before
  the target End. Record all intervening PTS gaps, duplicate rasters and visual
  breaks; never declare a receipt contract to be proof of visual continuity.
- Separate natural negatives: active play, menu/report/scoreboard, spectator view,
  timer-only change, unmatched result, score-only change, partial UI conflicts,
  and post-break/EOF fragments. Independently review actual declared coverage.
- Independent held event review after training/method freeze, preserving literal
  timer displays and distinct boundary/confirmation semantics. If changing the
  timestamp rule, use source evidence independent of the known GT miss.

At least one unexposed End episode is needed to test event-level transfer; that
minimum is **not** a statistical sufficiency guarantee. The loader's three-image
minimum per split and three held-correct supports is admission schema, not an
independent event sample-size rule. Extra supports from the exposed episode do
not resolve this requirement. No new private source has been supplied yet.

## Gates and handoff

| Requirement | Current authoritative evidence | Remaining limit |
| --- | --- | --- |
| Latest main / separate branch | fetched main c11ec6d; PR #42 branch | no main merge |
| Current-code qualification | real Start-only loader and producer | no independent full End/lifecycle |
| Source/profile/code/assets | immutable recovered manifests and current terminal checks | no new held End source |
| Stale bundle rejection | actual old-bundle rejection retained | no fingerprint-only signing |
| Positive/negative separation | original episode exposure and bounded cohorts explicit | no whole-video false-positive claim |
| Source timing | exact source PTS, literal displays, boundary/confirmation separated | known End GT miss retained |
| Safety | prior relevant regressions; actual R1 merge and two duplicate-raster cuts | R2 formal entrance fails geometry |
| Package/Trace | exact real application transfer of one R1 Start; schema PASS | full Start→End→next preparation unverified |
| CI | all four Linux/Windows jobs PASS on 79b6eea | this follow-up changes documentation only |
| Scope | B, private candidate/default disabled, completeness zero | Issue #16 remains open / PR draft |

No production fix or expanded test suite is justified by this documentation-only
follow-up. Fixed sampled/full E2E remain gated by independent End evidence and
current source-owned full path. Do not run another full native analysis merely
to recreate a historical exposed pattern. Issue #20 needs fixed qualified source,
comparable decoder/sampler/pack, negatives and resource estimates first. Issue #18,
#19 and #21 remain separate. New video is needed for unexposed End transfer;
match_001 alone still suffices for limited fixed regression and an eventual
geometry/continuous-path implementation check.

Sanitized evidence: `e2e_reports/match_001/current_main_round_application_followup.json`.
All source frames, profiles, bundles, raw rows and failed/successful logs remain
Git-ignored. Reproduce the fixed path from source decode → exact source-bound
FrameSamples → real process_frames with the unchanged current NativeLifecycleAnalysis
and explicit contract → Trace; always rerun integrity/admission and consult GT
only after processing. Never substitute diagnostic events or historical outputs.
