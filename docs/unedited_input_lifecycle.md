# Unedited input contract and R1 UI transition

## Verification checkpoint — 2026-10-10

The source-assurance/start and native assured-pipeline suites were checked again:
93 tests PASS in65.95seconds. This is a contract regression check, not a new
source-image qualification or canonical E2E run.

The user's no-edit assurance is accepted as an explicit input condition for the
listed SHA256, without another image-based edit investigation. Existing code
already separates this route from videos without assurance. Edit-only mandatory
continuity/world-reference qualification is removed from this route; timer,
purchase-phase and joint temporal UI qualification remain required.

Verified 157 related unit tests PASS in71.67seconds; focused RuffPASS and
mypy121source filesPASS. Coverage includes another-video rejection, unchanged
legacy qualification, weak reader rejection, source gaps/epoch changes,
occlusion/menu vetoes, duplicate suppression and preservation of transient
displays. These tests verify contracts, not independent real-image qualification.
No additional production change or video decode was needed for this checkpoint.

The existing actual30frame R1 replay retains `0:00 → 2:25 → 2:25 → 1:39`.
Phase disappearance proposes4.102669270833333sec; coherent later clock support
confirms4.202669270833334sec. Neither clock value nor an acceptance window is
hard-coded. The transient readings remain evidence and restart the stable-clock
interval when inconsistent. They are not discarded or labeled edits.

| Metric | Previous | Current | Delta |
| --- | ---: | ---: | ---: |
| Existing actual R1 start candidates | 1 | 1 | 0 |
| Released diagnostic events | 0 | 0 | 0 |
| Canonical PASS / FAIL / NE | 23 / 55 / 4 | Not rerun | Unavailable |

Remaining blocker: independent reader and complete temporal UI qualification.
Previously exposed R1 development frames cannot become independent holdout.
No new canonical E2E was started because its qualification gate is not met.
The assurance removes the edit hypothesis; it does not certify a timer reading,
player identity, ownership, a negative assertion or capture continuity.

## Current acceptance boundary

### Qualification support scope clarified

The loader requires at least three distinct reviewed physical frame hashes per
component/split, not three independent round episodes or three videos. Timer,
phase and joint UI transition may share physical frames **within the same split**;
this permits corroborating different measurements on the same current input.
The union of training, holdout and negative hashes remains disjoint across all
components. A frame used for timer training cannot become UI-transition holdout.
Source assurance changes none of these split/count/error requirements.

Four focused regression tests PASS in1.03seconds, with RuffPASS, covering shared
same-split evidence and all three cross-split leakage pairs. These are synthetic
loader contract tests and create no real qualification. No production change or
new canonical run was made. Previously reviewed full temporal R1/R2 development
sequences remain exposed; simply choosing three frames from them does not create
independent UI holdout. Additional video is not imposed as a prerequisite.

The immediate acceptance targets remain `GT-R1-ROUND-START`,
`GT-R2-ROUND-START`, `event_count_constraints-000` and
`event_count_constraints-004`. All four retain their existing FAIL status until
real qualified lifecycle events reach the canonical evaluator. Their count is
neither a guaranteed PASS gain nor permission to reinterpret count constraints.

For the explicitly assured source only, intentional editing is excluded by input
contract rather than re-established by image matching. The assured route retains
native cadence/PTS/epoch checks and qualified timer, purchase-phase and temporal
UI evidence. It does not extend the assurance to another video or to player-owned
facts. The actual R1 sequence produces a start **candidate** at
4.102669270833333 seconds, confirmed at4.202669270833334 seconds; both observed
2:25 frames remain in its evidence. No special clock value or GT acceptance time
is used in detection. A separate qualified release is still required: the current
development reports release zero events, and canonical PASS improvement remains
unmeasured. The end/rearm implementation described below does not establish an
actual R1 end. Reader and joint temporal holdout qualification remain the next
start-release gate; scene-preserving-edit proof is no longer that gate.

Explicit producer `content_jump`/`discontinuity` markers now reach the assured
tracker. A timer anomaly never creates either marker. Native continuity segment
IDs are integers, matching the package builder's contract; source epoch remains
separately recorded. Common orchestration now carries replay-verified source
breaks to HUD/Visual state resets and package fragments, with terminal event/cut
revalidation. Unsupported consumers stop before processing. Standalone receivers
still reject post-start breaks unless the exact replayed cut list is supplied
for segmented downstream processing. No break manufactures a round end.

## Problem

R1's observed clock changes from0:00to2:25to1:39. Background correspondence
was supported, but foreground presentation changes were previously held pending
proof against a scene-preserving edit. The user now guarantees no editing,
intentional frame deletion/join/reordering or speed change for the current video.
That guarantee is an input condition, not an image-recognition hypothesis.

## Explicit input contract

`datasets/input_contracts/match_001.unedited.json` records the user's assurance
against source SHA256 `71d58558559d6f578433ce9f234bf176f76fd5a86657dbfe3eba1e7d36136b06`.
`UneditedInputContract.load` requires exact matching source hash, explicit true
claims and provenance. It does not infer a guarantee from file naming, application
platform, smooth camera motion, video metadata or the absence of cut markers.
No guarantee is automatically applied to other videos. The document contains no
GT time, reader value, round ID or acceptance window.

## Qualification conditions to remove or retain

| Existing condition | Assured-source decision | Reason |
| --- | --- | --- |
| Prove foreground change is normal animation rather than a scene-preserving edit | Remove | Edit alternative is excluded by the user |
| Independently qualify hidden edited time/source-jump exclusion | Remove | Intentional editing/speed modification is excluded |
| Require paired scene/UI world-reference qualification solely to establish no edit | Replace with explicit contract plus decoder continuity | Background matching is no longer an edit attestation |
| Fail acquisition at an accumulated world-reference model mismatch | Do not use as an edit-only start veto in the assured route | It remains relevant to recognition geometry; it does not prove a recording gap |
| Require a low-contrast wall template to prove phase absence before proposing a start | Replace as a **candidate** prerequisite | Proposal uses a valid phase scan and later accepted coherent clock; nonmatch alone never confirms absence |
| Timer, purchase-phase and joint UI-transition qualification | Retain | No-edit assurance does not prove reader correctness or safe boundary semantics |
| Holdout/training separation, minimum support, wrong=0/negativeFP=0 | Retain unchanged | Recognition errors remain possible |
| Native frame cadence, monotonicPTS, source epoch, pixel/source integrity | Retain | Capture losses and PTS problems remain possible |
| Geometry, occlusion, state/menu/spectator conflicts and explicit discontinuities | Retain | Game transitions and unavailable evidence remain possible |
| Identity/ownership and player facts | Retain unchanged | System start evidence cannot establish HP/weapon/death/shot ownership |

The qualification loader now exposes an explicitly contracted branch requiring
`timer`, `purchase_phase`, and `ui_transition` components. It removes the mandatory
edit-oriented `continuity` and paired `scene_continuity` components **only when
an explicit unedited contract is passed**. All component support/count/review,
profile/code hash and split checks remain unchanged. Without that argument,
legacy requirements are unchanged. No real qualification report was fabricated.
The joint UI component must qualify the complete temporal proposal/confirmation
method, including occlusion, menu/spectator, phase jitter and recording-gap controls.

## State machine / contract change

`UneditedUiStartTracker` proposes system-only start candidates:

1. Observe repeated accepted purchase-phase evidence with the existing minimum
   preparation duration, and retain the accepted original phase timer display.
2. A valid current phase ROI scan no longer supporting the phase proposes
   `transient_ui_transition` at its first PTS. Nonmatch is not certified absence.
3. Retain every display/value/provenance in the transient sequence. Reuse the
   existing `PendingUiStart` clock consistency rule and0.05sconfirmation minimum.
4. An inconsistent clock change restarts the stable-clock interval; it does not
   delete the sample, alter its value or independently label an edit.
5. Subsequent coherent accepted clocks corroborate a `round_active_candidate`.
   Keep the proposal PTS and separately record confirmation PTS.
6. Cadence/epoch changes, explicit discontinuities, invalid/occluded phase scan,
   conflicting states, duplicate source pixels or timeout reset the candidate.
   Once proposed/confirmed, phase jitter cannot produce duplicate starts.

This module produces **candidates**, not native/evaluator events. Its source
continuity multiplier1represents intact measured transport under the input
assurance, not image confidence; reader/phase confidence remains the minimum of
accepted original measurements. `reader_qualification_required=true` is retained.
It never rewrites source observations, player identity or ownership, and cannot
produce an end event. Repeated source pixels do not count as new corroboration.
Uniform recordedPTS cannot prove no hidden capture loss; stalled/repeated pixels
are handled conservatively and undetectable recorder loss is not claimed absent.

## Fresh actual-image evidence

`e2e_reports/match_001/r1_unedited_native_start.json` is a fresh current-reader
native decode/analysis from source origin through4.3s. It processes256frames in
one epoch at256ticks/15360, with checked source/pixel/profile/code/terminal
bindings and all256phase ROI scans geometrically available. No GT or expected
clock input is read. Existing timer/geometry/reference thresholds are unchanged.
A valid scan means the calibrated ROI was measured at the correct shape; it
**does not** turn a contrast-unavailable glyph nonmatch into positive absence.

| Actual PTS | Observed phase | Original timer display |
| --- | --- | --- |
| 4.086002604166667 | Present | 0:00 |
| 4.102669270833333 | No accepted phase match; proposal | 0:00 |
| 4.1193359375 | No accepted phase match | 2:25 |
| 4.136002604166666 | No accepted phase match | 2:25 |
| 4.152669270833333 | No accepted phase match; stable clock begins | 1:39 |
| 4.202669270833334 | Stable clock confirmation | 1:39 |

There is one candidate at4.102669270833333, confirmed at4.202669270833334,
with four coherent1:39observations. Its seven display samples include both2:25
frames. This is generic consistency handling; there is no special2:25rule or
GT/round ID hard-code. The no-edit contract excludes intentional editing as an
explanation; the exact cause of the transient display (UI state or recognition
error) is not proved by assurance. No numeric observation is corrected.

A separate archived replay verifies78saved native image overlaps against actual
pixel/encoded hashes. It agrees with the fresh candidate but is not independent
holdout and does not inherit old reader/code qualification.

## Tests

112related tests PASS in50.94s, including source-hash opt-in, transient retention,
stability restart, duplicate suppression, epoch/gap/marker/occlusion/menu/scan
resets, rejected low reader confidence, contracted qualification requirements,
and unchanged legacy qualification/native merge contracts. Ruff PASS; mypy PASS
across118source files. Fresh native diagnostic exits0in499.209010s; it releases0
native events and generates no qualification. Windows execution is unverified.

## Previous / Current / Delta

| Metric | Previous | Current | Delta |
| --- | ---: | ---: | ---: |
| Edit-exclusion input contract | 0 | 1 source-specific | +1 |
| Fresh diagnostic start candidates under this contract | Unmeasured | 1 | Unmeasured |
| Released qualified start/end events in this diagnostic | 0 | 0 / 0 | 0 |
| Archived canonical PASS / FAIL / NE | 23 / 55 / 4 | Not rerun | Unmeasured |
| Native reader prefix frames | 256 | 256 | 0 |
| Native reader prefix runtime | 500.588115s | 499.209010s | -1.379105s (-0.28%) |

The runtime comparison covers differing diagnostic instrumentation and versions;
it is descriptive, not a demonstrated E2E acceleration. Canonical negative and
discontinuity failures have no new measurement; archived0/0is not a fresh claim.

## Remaining blocker / next implementation

Edit-exclusion evidence is no longer a blocker for this explicitly assured source.
Next integrate this contracted tracker with analyzer-owned scan guards and the
native event/package/trace receiver, preserving qualification/replay and source
hash checks. Qualify timer/phase and the complete temporal UI method on disjoint
holdout/negative controls before releasing production starts or running canonical
full E2E. The existing shared native CLI/provider still selects the original
paired-scene route; it has not yet been switched to the assured branch. Full E2E
was not run because no real reader/UI qualification has been adopted. R1result
banner and R2start acceptance remain subsequent tasks, with no threshold tuning.

## Qualified native production connection

The assured branch now connects analyzer-owned measurements to the shared
processor/package/trace receiver. `NativeLifecycleOptions` accepts an explicit
`unedited_input_contract_path`. It hashes the actual video, loads the matching
contract and current timer/phase/UI qualification **before decode**, then invokes
one analyzer-owned native producer for source origin throughEOF. Scene reference
assets are not required in this explicitly assured branch. Missing qualification
rejects before both native and sampled decoding; there is no fallback.

The phase template matcher exposes successful ROI shape/scan availability as a
separate boolean. The native analyzer additionally requires calibrated geometry.
The measurement is never called positive phase absence and does not alter NCC or
text acceptance. Complete projected global observations and actual scan results
enter the tracker once. Decoded source/pixel checks, profile/code/qualification
and input contract checks run again before output release. Injected readers
cannot inherit the profile's assured qualification.

The native result retains the contract/path only for local terminal validation.
Events carry contract/qualification/profile/code hashes and exact source pixel/
PTS/epoch provenance, with system actor. The receiver reloads the contract,
checks global-only fields and actual cadence/index, replays the tracker and
requires identical event output. Changed phase scans, events or contracts,
foreign source/epoch/PTS, and HP=0as well as other owned fields are rejected.
Native preparation provenance enters the existing package association rule;
sampled observations and their timestamps/frame counts are not replaced.

This is a start-only implementation: it does not invent an end, reopen an active
round from phase jitter, or claim R1/R2 splitting without a separately evidenced
end lifecycle. The qualified result uses the existing schema/event contract and
keeps original transient clock samples in public event provenance.

Shared CLI activation uses **one** source basis: either the previous scene profile
or the explicit unedited contract, together with a positive PNG budget. Bounded
isolated inputs and raw adaptation cannot opt in. Dataset start/end settings
fingerprints include the contract fingerprint; the runtime mode records which
source basis was selected. No guarantee is inferred for default commands.

```bash
python3 scripts/e2e/run_dataset_case.py \
  --video-id match_001 --video /path/to/source.mp4 \
  --validation-pack /path/to/unchanged-validation-pack \
  --hud-layout /path/to/reader-and-ui-qualified-hud-layout.json \
  --mode full --native-png-budget 12000000000 \
  --unedited-input-contract datasets/input_contracts/match_001.unedited.json
```

This is an interface example, not authorization to run an unqualified candidate.
The illustrative byte budget is not a whole-video capacity assurance. No actual
reader/UI qualification is installed and no new full E2E was started.

161related tests PASS,1Windows-host test skipped in74.03s; Ruff PASS; mypy PASS on
119source files. Synthetic qualification demonstrates one schema-valid system
start in a package and canonical trace, actor/time/contract provenance unchanged,
and no end event. Synthetic results are not actual-image qualification or new
canonical assertion PASSes. The prior499.209snative diagnostic remains a
historical source/code-bound result; it was not resigned after integration.

| Metric | Previous | Current | Delta |
| --- | --- | --- | --- |
| Assured native candidate→qualified event/package/trace path | Missing | Implemented behind qualification | Added |
| Assured shared full CLI | Missing | Explicit opt-in | Added |
| Actual adopted reader/UI qualification | 0 | 0 | 0 |
| Canonical PASS/FAIL/NE | 23/55/4 archived | Not rerun | Unmeasured |

Next qualify actual timer, phase and the complete UI temporal producer on
separated training/holdout/negative controls. Then continuous validation and
sampled regression must precede canonical full E2E. Do not require proof against
user-excluded edits or use synthetic qualification for the actual video.

Actual source/profile preflight is recorded in
`e2e_reports/match_001/assured_pipeline_preflight.json`. The normal decoder entry
points were instrumented to fail if called. The current source's matching contract
loads, but its missing reader/UI qualification stops processing: native decode0,
sampled decode0, released events0. Metadata probing occurs normally. This verifies
the pre-decode gate and absence of fallback; it does not evaluate image recognition.


## Current-code component holdout replay

`e2e_reports/match_001/unedited_component_holdout_replay.json` binds the current
profile, recognizer code and existing reviewed manifests by SHA256. No new labels,
Validation Pack inputs, candidate selection or threshold changes were used.
The timer uses the configured outer ROI before its configured SubregionReader;
phase uses the production template matcher on the saved source image.

| Diagnostic metric | Previous | Current | Delta |
| --- | ---: | ---: | ---: |
| Timer correct | 25 | 25 | 0 |
| Timer unknown | 7 | 7 | 0 |
| Timer wrong | 0 | 0 | 0 |
| Timer alternate-field false accepts | 0 | 0 | 0 |
| Phase positive correct | 8 | 8 | 0 |
| Phase positive unknown | 0 | 0 | 0 |
| Phase negative false accepts | 0 | 0 | 0 |

The combined initial replay took 14.333 seconds. An initial diagnostic invocation
incorrectly supplied an already-cropped timer field to SubregionReader, causing a
second crop. Those timer predictions are excluded; the corrected timer/control
replay took 1.375 seconds. This is diagnostic runtime, not E2E runtime.

### Qualification boundary and remaining blocker

The no-edit contract removes the need to qualify evidence whose sole purpose is
to exclude intentional editing or scene-preserving edits. It does not certify
reader outputs or phase absence. Existing timer controls are alternate field-type
controls, not natural timer-absent ROI controls. The replay uses saved JPEG images
and reference coordinates, rather than native calibrated full-analyzer input.
Phase nonmatch remains unknown rather than independently verified absence.

Most importantly, isolated reviewed reader images do not qualify the joint temporal
producer. The R1 prefix was used for development and cannot become an independent
UI-transition holdout by relabeling it. The next task is to inventory disjoint,
reviewed continuous episodes in this same source for the frozen start producer,
including negative transitions, and evaluate them without tuning on their labels.
Frame/PTS gaps, recording loss and explicit discontinuity markers must still reset
pending evidence. Other sources retain the default continuity qualification path.

No qualification sidecar was created, no production event was released by this
replay, and no canonical E2E was run. Canonical Current/Delta remain unmeasured;
the archived baseline remains 23 PASS / 55 FAIL / 4 NE. These component results
must not be represented as a new canonical result or a completed round lifecycle.


## Frozen R2 temporal application under the source assurance

### Problem / competing hypotheses

The R1 contract must also handle a different transient timer sequence without
special-casing either display or boundary time. The already exposed R2 development
window provides an application test, not independent qualification.

### Evidence

Thirty saved lossless native images spanning 111.202669–111.686003 seconds were
replayed using the unchanged configured timer and phase readers. Each encoded
image and decoded pixel hash matches the earlier source-bound manifest. All
adjacent PTS differ by 256 ticks at time base 1/15360. Current code, profile and
input manifests are checked again at terminal. No Validation Pack was loaded.

Timer results are unchanged: 24 correct / 6 unknown / 0 wrong (delta 0/0/0).
The first six abstentions remain unknown. The observed transition is retained as
`0:00 → 1:40 → 1:39`. The frozen tracker proposes one start at
111.4193359375 seconds and corroborates it at 111.48600260416667 seconds,
confidence 0.931477963924408. No duplicate or end candidate is produced.
Runtime is 22.567 seconds; a comparable previous combined-tracker runtime is
unavailable. This is reader/temporal diagnostic runtime, not full E2E runtime.

### Continuity decision / contract change

No new contract or recognition behavior changed. The video-specific no-edit
assurance applies; native PTS/pixel continuity is checked, while no scene edit
qualification is attempted. This replay deliberately assumes reference-coordinate
geometry, unoccluded ROIs and an eligible unknown global state. It therefore proves
application of the frozen candidate tracker under these stated conditions, not
full-analyzer acceptance, production lifecycle segmentation, or canonical PASS.
A fresh tracker models this separate diagnostic window; it does not establish
R1-to-R2 state progression or allow a missing R1 end to be inferred.

### Tests / Previous / Current / Delta

| Metric | Previous | Current | Delta |
| --- | ---: | ---: | ---: |
| Timer correct | 24 | 24 | 0 |
| Timer unknown | 6 | 6 | 0 |
| Timer wrong | 0 | 0 | 0 |
| Qualified events released | 0 | 0 | 0 |

No production code was modified, so prior related unit/Ruff/mypy results are not
represented as newly run. `git diff --check` passes. Full/targeted/sampled E2E
were not run because the joint producer qualification remains absent. Canonical
Current/Delta are unmeasured, and the archived 23/55/4 baseline is unchanged as a
comparison reference rather than a new run.

### Remaining blocker

Both available start episodes are previously exposed development data. Do not
count R2 as independent holdout simply because it follows R1 chronologically, and
do not count adjacent images as independent events. Existing component holdout
supports the readers but not the joint temporal producer. The next task remains
reviewed disjoint continuous negative/application controls and a justified joint
qualification design. R1 end and native R1/R2 package separation are still pending.

Machine-readable evidence: `e2e_reports/match_001/r2_unedited_reader_temporal_replay.json`.


## Fixed native negative controls and qualification-support audit

### Problem / evidence / competing hypotheses

The current GlobalLifecycleQualification loader requires at least three distinct
hashes in each component training/holdout/negative split, at least three reviewed
correct holdout cases, no holdout wrong or negative false positives, and disjoint
aggregate splits across components. It does **not** encode a requirement for three
independent round-start episodes. Do not invent that requirement, or represent
three adjacent images as three independent events. Frame-support compliance and
independent temporal validation remain separate evidence claims.

The current native-PTS exposure inventory records 509 distinct known ticks from
284 saved reports/manifests, with no size-skipped files. It is conservative and
non-exhaustive: rounded JPEG review times and all historical code-development
exposure are not fully represented. It cannot alone certify a clean holdout.

Three continuous control intervals were fixed before new predictions by source
metadata duration * 0.25, 0.50 and 0.75, each 0.2 seconds. All native frames were
retained: 36 frames, cadence 256 ticks at 1/15360, source hash verified at terminal.
Intervals are [42.754834,42.954834], [85.509668,85.709668] and
[128.264502,128.464502]. Their decoded source images remain Pi-local.
Manual all-frame timer/phase crop review and labels were frozen before predictions,
without Validation Pack input. The wider contact sheet shows ordinary world view,
buy menu and a world view with smoke/killfeed respectively. No identity/ownership
claim is derived from these visual descriptions.

### Continuity decision / contract change

No contract, thresholds or production behavior changed. The explicit source
assurance applies; recording/PTS/cadence checks remain. Reference-coordinate reader
replay with an eligible unknown-state projection and fresh tracker per window is
an optimistic diagnostic, not calibrated full-analyzer qualification. All three
intervals lack purchase-phase text and a start transition on the reviewed images.
Their timers are present, so they are **not** natural timer-absence controls.

### Tests / Previous / Current / Delta

| Metric | Previous comparable run | Current | Delta |
| --- | ---: | ---: | ---: |
| Processed native frames | unavailable | 36 | unavailable |
| Timer correct / unknown / wrong | unavailable | 33 / 3 / 0 | unavailable |
| Phase false accepts | unavailable | 0 | unavailable |
| Start candidate false positives | unavailable | 0 | unavailable |
| Valid phase scans | unavailable | 36 | unavailable |
| Decode/collection wall time (seconds) | unavailable | 53.533 | unavailable |
| Reader/temporal replay wall time (seconds) | unavailable | 23.450 | unavailable |

The zero start candidates demonstrate rejection with no prior preparation context,
not recovery from phase jitter, stale pre-round context or an end-to-start lifecycle.
Three intervals of one source are not independent videos. No qualification report
was installed, no event released, and no canonical E2E run or new assertion PASS
is claimed. Production code is unchanged; earlier checks are historical rather than
newly rerun. `git diff --check` passes.

### Remaining blocker / next action

The new controls supplement reader and candidate-bootstrap negatives. Qualification
still needs justified disjoint temporal holdout and negative transition cases for
the complete producer, and calibrated analyzer coverage. Existing R1/R2 development
replays must not be promoted to blind holdout. The next useful check is the frozen
actual analyzer on these controls, retaining its real menu/occlusion/state gates;
then investigate context-bearing transition controls without inserting labels into
runtime. R1 result/end qualification remains a separate blocker.

Evidence: `e2e_reports/match_001/unedited_ui_fixed_negative_controls.json`,
`e2e_reports/match_001/native_exposure_pts_inventory_unedited.json`, and local
`outputs/recognition-investigation/unedited-ui-fixed-controls/{selection,manifest,blind-labels}.json`.


## Actual analyzer control replay

Problem: the preceding controls assumed reference geometry, eligible unknown state
and no occlusion. Evidence now comes from the configured RealHudAnalyzer, without
injected anchors, signals or reader objects. Twelve original-source calibration
inputs (four repeated per batch) and 36 control inputs were processed.

The first diagnostic used separate calls for prefix and controls; geometry retention
is local to observe_frames, so every control was calibration_required (0 effective
geometry, 0 valid phase scans, 36 unknown timers). This attempt is preserved in
`unedited_ui_actual_analyzer_controls.json`. Its zero candidates is geometry-gated
rejection and must not be counted as meaningful reader/temporal qualification.

The corrected diagnostic uses one prefix+control call per batch. All input bytes,
source pixels, source SHA, profile/code and review labels are terminal-bound. Only
the control portion enters a fresh candidate tracker. Frame indices are rebased
for that projection; original PTS/pixels remain intact. The prefix gap is never
start corroboration. This remains an archived-source diagnostic, not the automatic
single-origin-to-EOF production provider.

| Metric | Prior reference-ROI replay | Actual analyzer controls | Delta |
| --- | ---: | ---: | ---: |
| Control frames | 36 | 36 | 0 |
| Timer correct | 33 | 33 | 0 |
| Timer unknown | 3 | 3 | 0 |
| Timer wrong | 0 | 0 | 0 |
| Valid phase scans | 36 | 36 | 0 |
| Start candidate false positives | 0 | 0 | 0 |

Actual control states: 2 live_first_person, 22 unknown, 12 buy_menu_open. Prior
states were assumed, so these counts have no comparable state Delta. Prefix+
control geometry across all batches: 3 fresh, 48 effective, 45 retained. Those
counts include repeated prefixes and do not measure whole-video geometry quality.
Raw analyzer player-valid facts occur in two live frames; none occur in unknown
frames. The independent global projection releases zero player-valid facts.
Normal analyzer identity decisions are not credited to global evidence.

Corrected runtime: 89.975 seconds, including decode/verification and 48 analyzer
inputs. The reference-ROI replay's 23.450 seconds omits calibration/identity/state
and processes only 36 reader inputs; it is not a comparable runtime benchmark.
No production behavior changed. No new unit/Ruff/mypy execution is claimed;
`git diff --check` passes. No canonical targeted/sampled/full was run, no sidecar
installed, and no new PASS/FAIL/NE or canonical negative-regression result exists.

Remaining blocker: joint temporal qualification on disjoint reviewed transitions
with preparation context. These short controls reject fabricated bootstrap starts
but do not exercise phase jitter or R1→R2 progression. R1 end/result qualification
and the eventual canonical full evaluation remain pending.

Evidence: `e2e_reports/match_001/unedited_ui_actual_analyzer_combined_controls.json`.


## Actual analyzer R2 start application

The previously exposed 30-frame R2 development interval was processed by the
configured RealHudAnalyzer with four real origin calibration images in the same
call. No reader/anchor/signal override, GT, time substitution or state override
was supplied. Only the R2 portion enters a fresh diagnostic tracker; control
indices are rebased for projection while source PTS/pixels remain unchanged.
The long calibration-prefix gap does not corroborate the boundary or R1→R2 state.
Source hash, PNG/pixel hashes and current profile/code/input bindings are checked.

All 30 R2 observations remain unknown; nine carry buy_phase_banner. All 30 phase
scans are valid. The unchanged tracker proposes exactly one start at
111.4193359375 seconds, confirmed at 111.48600260416667 seconds. The original
`0:00 → 1:40 → 1:39` display samples are preserved. No end is proposed.

| Metric | Previous ROI/projected-state diagnostic | Actual analyzer | Delta |
| --- | ---: | ---: | ---: |
| Boundary frames | 30 | 30 | 0 |
| Timer correct | 24 | 24 | 0 |
| Timer unknown | 6 | 6 | 0 |
| Timer wrong | 0 | 0 | 0 |
| Start candidates | 1 | 1 | 0 |
| Qualified events released | 0 | 0 | 0 |

Runtime 62.405 seconds includes 34 analyzer inputs and origin decode. Previous
22.567-second ROI replay omits calibration/state/identity and is not comparable.
This verifies availability of candidate inputs through the actual analyzer;
it does not qualify the previously exposed case as an independent holdout, prove
single-epoch full-source lifecycle progression, or change canonical PASS counts.
Qualification reports for the complete frozen producer remain absent. R1 result/
end evidence remains a separate blocker. No production code or policy changed;
`git diff --check` passes, and no new unit/Ruff/mypy execution is claimed.

Evidence: `e2e_reports/match_001/r2_unedited_actual_analyzer_temporal_replay.json`.


## Separate R1-end reference/occlusion diagnosis

The actual TEAM ACE image at native PTS 1143337 (74.43600260416666 seconds)
was checked against the previously frozen three-image reference/mask. Full-group
NCC remains 0.387553 / 0.419838 / 0.526164, below the unchanged 0.90 requirement.
A descriptive HSV red-overlay mask overlaps 6.96% / 21.79% / 5.43% of each
reference support group. The visible damage indicator contaminates the text,
but is not proved to be the only mismatch cause.

Four predeclared descriptive upper-height bands (25/50/75/100%) were measured;
none reaches 0.90 in all three groups. The top quarter scores
0.871391 / 0.913201 / 0.904624. Thus simply discarding the lower damaged area
is not supported as a fix. No mask, reference, OCR candidate or threshold changed;
these post-inspection measurements are not training or independent holdout.
Actual input/reference hashes are verified again at terminal. Production events,
new qualification and canonical results remain absent.

The assured producer is explicitly start-only: replay_assured_starts releases
round_start and the tracker latches after its first start. It cannot currently
produce an end or rearm for R2 within one full-source epoch. The older global
end path requires qualified score and round_result components plus accepted score
transition/current result evidence; the current timer/phase profile lacks those
qualified end inputs. Source no-edit assurance does not supply them. This is both
an input qualification blocker and missing end/rearm integration, not a failure
of actor rewriting or package labels. Do not count the local fresh R2 tracker
as evidence that this missing full lifecycle progression is completed.

Next: qualify source-supported result visibility variants with distinct training
and heldout support, then implement end/rearm under that qualified contract.
The failed upper-band hypothesis must not be retried by lowering NCC or selecting
support on the early regression frame. No new full E2E is warranted yet.

Evidence: `e2e_reports/match_001/round_result_occlusion_diagnostics.json`.


## Started-latch display-transition regression repair

Problem/root cause: the start-only assured tracker called reset on invalid phase
scan, occlusion, menu/spectator/remote state or unqualified result flags before
checking its already-started latch. Subsequent preparation could therefore produce
a second start without any qualified end. Six synthetic transition cases reproduce
two candidates before the fix, at 0.12 and 0.46 seconds. Three source-break cases
already pass. These times are unit fixtures, not production constants or GT.

Change: source binding, cadence/epoch/duplicate-pixel and explicit content-jump/
discontinuity checks still run first and clear state as before. After those checks,
a started tracker remains latched before UI rejection checks. Rejected UI evidence
still clears pre-start preparation. No current state, player fact or end is inferred.
End/rearm integration remains pending and cannot be replaced by display jitter.

Tests: all nine new cases pass (previous 6 FAIL / 3 PASS, current 0 FAIL / 9 PASS).
Related tracker/qualified native/receiver/provider/global lifecycle tests:
126 PASS in 30.69 seconds. Ruff `src tests scripts/e2e` PASS; mypy 119 source
files PASS; `git diff --check` PASS. Saved actual analyzer output replay covers
322 frames across R1, R2 and three fixed controls. Both start candidate contents
and all control candidate counts remain exactly unchanged; replay runtime 0.067
seconds is cached-output replay, not fresh recognition or E2E runtime.

The production code fingerprint changes. Earlier image/reader reports retain their
historical code binding; none was resigned into qualification. No global sidecar
is installed and no full/targeted/sampled E2E was launched. Canonical Previous is
23/55/4; Current and Delta remain unmeasured, including canonical negative and
discontinuity metrics. No threshold, identity/ownership, geometry, source sampler,
Validation Pack or assertion was changed. Windows remains unverified.

Evidence: `e2e_reports/match_001/unedited_start_latch_regression.json`.
Next: qualified result/score input and end/rearm integration, with a justified
independent temporal holdout before canonical evaluation.


## Qualified assured end and next-round preparation

Problem: the assured route was start-only; it could not close a round or rearm
within one full native epoch. Added UneditedRoundLifecycle around the existing
start tracker. Existing entry-point names remain compatible.

The producer transports calibrated semantic round-result match/confidence only
when the current qualification includes both score and round_result. The receiver
validates the evidence shape/types and rejects result evidence under a start-only
qualification. End requires an already-started lifecycle, adjacent source-bound
frames, valid scans/unoccluded compatible states, all four accepted score readings
at the existing 0.90 guard, exactly one point changing on one side, and current
qualified semantic result at 0.90. This preserves the existing global end predicate
and additionally rejects invalid prior-frame UI context. No score or timestamp is
inferred and no earlier banner time is substituted.

A confirmed end clears preparation and the start latch while retaining the actual
source position. Subsequent confirmed purchase-phase evidence enters
next_round_preparation; the unchanged transient UI/clock policy confirms a new
start. No second end can fire while ended/preparing. Source gap/epoch/marker guards
still clear pending state. These events remain system actor through the native
receiver, RoundPackage builder and trace adapter; no player fact is released.

| Synthetic contract metric | Previous start-only fixture | Current | Delta |
| --- | ---: | ---: | ---: |
| Start events | 1 | 2 | +1 |
| End events | 0 | 1 | +1 |
| Native packages | 1 | 2 | +1 |

This table is **synthetic unit evidence**, not real-video E2E. The two-start/
one-end sequence, pre-round association, exact system actor/time/type trace,
low/unknown/bool scores, two-point jumps, absent/low result, menu, current/prior
occlusion, invalid prior scan, start-only qualification rejection and receiver
result-tampering checks pass. Related184 tests PASS79.73sec; Ruff PASS; mypy120
files PASS; git diff --check PASS. A subsequent documentation-only module-header
edit changes the code fingerprint; historical fixture/test bindings are not real
qualification and no real sidecar is resigned.

No result reference, score reader, threshold, ownership/identity/geometry policy,
Validation Pack, assertion or sampler changed. Runtime still requires a freshly
qualified complete producer. Actual result/score qualification is absent and the
early TEAM ACE reference still fails; no actual end, package split, canonical PASS
gain or negative-regression result is claimed. Full E2E was not run because its
actual-image acceptance gates remain unmet. Windows is unverified.

Remaining blocker: qualified current-frame result/score input plus independent
whole-producer temporal qualification and canonical evaluation. Existing end logic
needs result present on the score-transition frame; current reviewed early banner
and later score transition do not satisfy that simultaneity, so this connection
alone must not be presented as a solved R1 end or guaranteed 30 PASS.

Evidence: `e2e_reports/match_001/assured_end_rearm_contract.json`.


## R1-end small-translation hypothesis rejected

A descriptive fixed integer dx/dy grid [-4,4] was evaluated on the already
reviewed early TEAM ACE image against the frozen existing reference. All source/
asset bindings are checked again at terminal. Full-mask and top-quarter diagnostics
each evaluate 81 translations, without image repair, scale change or runtime
geometry override. In both cases the maximum minimum-group NCC occurs at dx=0,
dy=0: full 0.387553; top quarter 0.871391. Neither has any all-three-group
0.90 acceptance. Small ROI translation therefore does not explain or fix the
observed transfer failure. Scale and other appearance variation are not excluded
by this measurement. The hypothesis is rejected, not retried with lower thresholds.
Runtime0.205sec; no prior comparable alignment run. This is post-inspection
source diagnosis, not training, independent holdout or canonical E2E. No production
code/reference/profile changed, no qualification installed, and no canonical
Current/Delta is measured. Earlier184test/Ruff/mypy results remain historical;
git diff --check passes. Actual end qualification remains the blocker.
Evidence: `e2e_reports/match_001/round_result_alignment_diagnostics.json`.


## Four-image common-structure training hypothesis rejected

Target: GT-R1-ROUND-END, specifically the early result appearance that the later
reference does not cover. The previously exposed early regression image was
explicitly moved into a diagnostic training pool with the three existing later
training images; it is not holdout. A single fixed training-only hypothesis used
the unchanged median reference, all-four bright foreground intersection (>210),
one-pixel contrast ring and three separate groups. No holdout predictions or
Validation Pack input were used. Selection and assets were frozen before scoring.

The constructor succeeds because three later examples meet all-group NCC0.90.
The early training example remains rejected: minimum0.692134 (previous old
reference0.387553; delta+0.304581). Its three group scores are
0.692134/0.811248/0.801471. This numerical increase is not successful target
coverage. Minimum support is preserved at three accepted source examples; simply
listing four training hashes does not establish four accepted supports or an early
appearance model. Training/constructor eligibility is not qualification.

The target-specific hypothesis is rejected before holdout evaluation or adoption.
No retry, threshold lowering, recognition code/profile change, qualification or
canonical run occurred. Local generated images remain diagnostic artifacts only.
Training diagnostic runtime0.398sec; no comparable previous generation runtime.
Source/frame/asset bindings are recorded and existing input bytes verified again.
Earlier184test/Ruff/mypy results remain historical; git diff --check passes.

Evidence: `e2e_reports/match_001/round_result_common_structure_training.json`;
local artifacts: `outputs/recognition-investigation/result-common-structure-training/`.
Actual end appearance qualification and complete-producer holdout remain unmet.

## R1 actual continuous validation through six seconds

Problem / target: `GT-R1-ROUND-START` requires a real temporal boundary, with no
duplicate start through subsequent UI changes. The earlier actual-image check
ended at4.3seconds. Extend the same fixed profile and explicit source assurance
to6seconds; do not change readers, references, thresholds or acceptance logic.

Evidence / change: one fresh native decode from source origin to6seconds,
256tick cadence, actual analyzer, every decoded frame retained. First actual PTS
is0.036002604166667 and last5.986002604166667. Source/pixel, contract, profile and
code bindings are checked through decoder completion. All358 phase scans are
geometrically available; this is not a claim of positively certified phase
absence. All358 primary states remain unknown; global projection supplies no
player-owned facts.

| Development diagnostic metric | Previous (0–4.3sec) | Current (0–6sec) | Delta |
| --- | ---: | ---: | ---: |
| Native frames | 256 | 358 | +102 |
| Geometrically available phase scans | 256 | 358 | +102 |
| Start candidates | 1 | 1 | 0 |
| Released events | 0 | 0 | 0 |
| Wall time (sec) | 499.209 | 723.760 | +224.551 |

Runtime comparison changes input duration, so it does not establish a speed
regression. The only candidate remains4.102669270833333, confirmation remains
4.202669270833334 (both deltas0). The complete original sequence remains
0:00,2:25,2:25,1:39,1:39,1:39,1:39. No second candidate appears through the end
of the interval. No display correction, GT injection or scene-edit proof is
used. This development interval is not independent holdout or canonical E2E.

Tests: diagnostic exit0; the preceding current unit check85PASS24.71sec, Ruff
PASS and mypy120source files PASS. No production code changed in this extension.
Canonical Current/Delta, negative assertion regression and full package gains
are unmeasured. Adopted full baseline remains23PASS/55FAIL/4NE as historical
evidence; it is not a post-change full result. Full E2E was not run because actual
reader/joint temporal qualification and R1 end acceptance are still unmet.

Conclusion / remaining blocker: the longer actual interval supports stable
candidate timing and duplicate suppression. Next qualify the complete global
start producer on disjoint reviewed holdout and negative temporal controls;
retain wrong=0 and negativeFP=0. The user-assured no-edit input is already
established and must not be re-proved. Windows execution remains unverified.
Evidence: `e2e_reports/match_001/r1_unedited_native_start_through6.json`.

## Reproducible qualification-evidence binding audit

Problem / target: `GT-R1-ROUND-START` remains blocked at actual qualification.
Saved component, R2 and negative diagnostics must not silently acquire the
current producer fingerprint after lifecycle code changes. The new diagnostic
`scripts/diagnostics/audit_assured_start_evidence.py` records source/contract,
profile/code matches and all explicitly listed input-file hash checks, then
rechecks its inputs before publication. It creates no qualification or event,
reads no Validation Pack, and changes no production behavior.

The audit of four saved reports finds one current-code match (the fresh R1
through-six-second run) and three historical-code reports. All listed dependency
hashes match, with zero mismatches. Historical fingerprints remain intact; they
cannot be repaired by resigning the reports. Matching bindings alone do not
establish independently reviewed labels, split separation or temporal coverage.
The current loader requires three distinct hashes per training/holdout/control
split and at least three correct holdout cases per component; it does not require
three independent round-start episodes. Correlated source frames must still be
described honestly rather than presented as independent events.

Run from the repository root (repeat `--report` for additional saved evidence):

```bash
PYTHONPATH=.:src python3 scripts/diagnostics/audit_assured_start_evidence.py \
  --video ValorantData/videos/Valorant_09-25-2026_0-37-29-379.mp4 \
  --layout outputs/hud_profiles/round-global-timer-glyph-20261008/hud_layout.json \
  --input-contract datasets/input_contracts/match_001.unedited.json \
  --report e2e_reports/match_001/r1_unedited_native_start_through6.json \
  --output /tmp/assured-start-evidence-audit.json
```

Existing evidence gaps: timer field-type negatives do not establish natural
timer-absence behavior; isolated phase tests do not establish joint start
semantics; fixed controls with fresh trackers and no prior preparation do not
test stale preparation. Current-code frozen whole-producer evidence is needed
before release. This audit does not add a new recognition or episode-count gate.
It establishes which archived evidence is historical, not that every historic
reader measurement is incorrect. R1-end score/result qualification remains
absent. No canonical delta, adopted qualification, new candidate or full E2E is
claimed. Previous/current audit counts are not comparable because this is the
first audit. Ruff passes for the new diagnostic; production checks85tests,
Ruff and120-file mypy remain the preceding results.

Evidence: `e2e_reports/match_001/assured_start_evidence_audit.json`.

## Actual R1 end inputs and global combat-report context

Problem / targets: `GT-R1-ROUND-END`, `event_count_constraints-002`. Manual
source review records an early result display and later clock/score changes,
but those reviewed values are not production input. Measure the configured
analyzer on all ten saved native frames74.369336–74.519336. Verify encoded image
hashes and native PTS against the saved source manifest; use four actual source
origin frames in the same analyzer call for geometric diagnostic context. The
prefix gap and separate epoch are explicitly not temporal corroboration.

Evidence: all ten frames remain unknown, all ten phase scans are geometrically
valid, no accepted purchase phase or result is present, and no score pair is
available. Timer has4correct/6unknown/0wrong against the prior manual source
review, compared only after inference. Its accepted original displays include
0:29and0:06. The current profile configures neither ally/enemy score reader nor
semantic round-result signal. Thus zero result matches here indicate unavailable
configured input, not a new measured NCC failure of the separate development
reference. Eight frames carry `combat_report_visible`. Wall33.355sec; no previous
comparable actual end-input run. No GT/expected input enters the analyzer.

Root cause / change: the assured end wrapper additionally vetoed the combat
report flag even when independently qualified global score/result would be
available. Allow that flag as global end context on both adjacent frames. This
is confined to the explicit assured global system end route; pre-start context,
legacy route, identity, ownership and player facts are unchanged. Current result
and both score readings still require confidence>=0.90, qualified components,
exact one-point change, native source continuity and non-occluded compatible
context. Spectator/remote/menu and other conflicting flags remain rejected.
This change does not turn a combat report into a death/HP/weapon fact or itself
constitute round-end evidence.

Tests:139relatedPASS55.93sec, Ruff PASS, mypy120files PASS. Three synthetic
current/prior/both combat-report contexts with unknown identity preserve system
end events and empty owned fields. Negative end cases run with and without a
combat report: missing/low/bool/two-point score, absent/low result, menu,
spectator, remote, conflicting flag, occlusion and invalid prior scan reject.
These tests do not qualify actual video evidence. All82canonical assertion
records remain unchanged. The actual input report predates the contract change;
its original code fingerprint is retained, without resigning.

Previous/current/delta: canonical values are unmeasured after this change;
adopted historical baseline23PASS/55FAIL/4NE is not a current run. Actual end
release remains0, no qualification is installed and no package gain is claimed.
Full E2E was not run because score/result input and independent whole-producer
qualification remain absent. The earlier single-banner and later score-update
frames still do not satisfy the current simultaneous end predicate. Next build
qualified score/result input rather than tuning thresholds or inventing an end.
Windows execution remains unverified.

Evidence: `e2e_reports/match_001/r1_end_actual_global_inputs.json`;
reproducible probe: `scripts/diagnostics/probe_native_end_inputs.py`.

## Score producer-to-boundary confidence contract corrected

Problem / targets: `GT-R1-ROUND-END`, `event_count_constraints-002`. Existing
score development must be reused before inventing a new recognizer. The frozen
`score-reader-white-pipeline.templates.json` adds only ally/enemy readers to the
current template profile; all other profile entries and existing readers match.
The probe now accepts optional `--templates`, passed to the normal analyzer
constructor, with no reader objects, geometry, signals, GT or qualification
injected. No runtime profile is adopted.

Evidence: on the same ten verified native end images, actual score output is
18correct/2unknown/0wrong (post-inference prior source review), with8complete
pairs. Default profile output had0pairs; delta+8. Timer availability remains4,
all10states stay unknown, result matches remain0, and owned facts remain absent.
Wall33.461699sec vs33.354574sec, delta+0.107125sec; this single short comparison
does not establish a performance trend. This is exposed development regression
evidence, not independent qualification. The existing earlier score holdout
36correct/18unknown/0wrong remains historical, not a freshly repeated holdout.

Root cause: the actual analyzer publishes accepted value confidence as
`score_ally_value`/`score_enemy_value`. Both global and assured end consumers
instead read `ally_score_value`/`enemy_score_value`. Thus every actual pair was
rejected even with accepted values. Synthetic fixtures used the same reversed
keys and concealed the integration failure.

Change: both consumers now read the exact producer keys. Update synthetic
fixtures to the actual contract; reject missing canonical value confidence even
when legacy or generic geometric confidence is high. No alias fallback, score
inference, threshold lowering, ownership/identity, sampler or GT change occurs.
The original measured report/code fingerprints remain historical after this
consumer fix; no sidecar is resigned or qualification installed.

Tests:187relatedPASS94.61sec, Ruff PASS, mypy120files PASS. A regression test uses
actual `RealHudAnalyzer` observation output with synthetic readers/qualification
to drive the global end consumer, rather than inserting confidence keys by hand.
Assured-end negative tests include missing canonical confidence and high legacy/
geometry confidence, with and without combat-report context. Synthetic tests
prove the contract only, not actual result detection or qualification.

Conclusion: one real vertical integration defect is fixed; actual end release,
canonical PASS gain and package splitting remain unmeasured/unqualified. No full
E2E was run. The separate result signal is absent, and early result/later score
still fail the existing same-frame end predicate. Next qualify the complete
score/result temporal producer using real evidence; do not backdate or invent
the missing end. All82assertion records are unchanged; Windows is unverified.
Evidence: `e2e_reports/match_001/r1_end_existing_score_analyzer.json`.

## Fixed binary-foreground result hypothesis rejected

Problem / target: `GT-R1-ROUND-END`; early TEAM ACE does not transfer to the
three-source later reference. Visual inspection confirms a red damage indicator
over the lower text, but earlier mask/translation diagnostics already failed to
establish occlusion alone as the cause. Test a separate luminance hypothesis:
raw grayscale transfer may depend on background or alpha appearance. Compare
the existing raw matcher to fixed white>210 binary foreground, using exactly
the same full mask, spatial groups and NCC0.90. This210level is the original
training foreground rule; no level sweep, new mask, geometric search or profile
candidate is generated. All images are already exposed development evidence.

| Same saved cases accepted | Previous raw | Fixed binary | Delta |
| --- | ---: | ---: | ---: |
| Training (3) | 3 | 0 | -3 |
| Previously exposed heldout frames (11) | 3 | 0 | -3 |
| Natural result-ROI controls (3) | 0 | 0 | 0 |
| Early reviewed result (1) | 0 | 0 | 0 |

Early minimum NCC0.387553→0.471950 (+0.084397) remains rejected. The fixed
foreground operation also loses minimum training support, so this hypothesis
is rejected without adoption or further threshold tuning. Binary foreground
does not isolate a supported transferable result model; raw/background versus
glyph/occlusion causes remain incompletely separated. Do not claim a font-size
diagnosis or successful result recognition from this result.

Source video, all used image hashes and unchanged reference/mask/region assets
are verified at terminal. This passive diagnostic changes no production code,
profile, qualification or events; all82assertion records are unchanged. Process
wall time was not retained by this quick diagnostic and is explicitly null,
rather than inferred from observation time. Previous187relatedtest/Ruff/mypy
results remain the latest production checks. No targeted/sampled/full E2E or
canonical delta is claimed; Windows remains unverified. The accepted score
consumer contract fix remains useful, but actual end evidence is still missing.
Next investigate a separately supported temporal global end hypothesis rather
than continuing to adjust the same weak early-banner reference.
Evidence: `e2e_reports/match_001/result_white210_structure_diagnostic.json`.

## Fresh extended R1-end numeric sequence

Problem / targets: `GT-R1-ROUND-END`, `event_count_constraints-002`. Test whether
the observed timer drop is followed by a stable score update, without relying
on the weak result reference. Extend only the explicit diagnostic native window
to74.36–74.75seconds. Use the existing frozen opt-in score sidecar and actual
analyzer, no new reader/candidate, GT input or qualification. The probe accepts
fresh-window options as an alternative to the existing archive inputs; it keeps
four real source-origin calibration frames in the same call, whose gap cannot
provide temporal evidence. All23end-window native frames are decoded and checked.

| Actual input metric | Previous ten frames | Extended23frames | Delta |
| --- | ---: | ---: | ---: |
| Accepted score pairs | 8 | 14 | +6 |
| Accepted original timer displays | 4 | 4 | 0 |
| Result matches | 0 | 0 | 0 |
| Released events | 0 | 0 | 0 |
| Wall seconds | 33.461699 | 84.426871 | +50.965172 |

Input duration differs; runtime delta does not establish a performance trend.
All ten overlapping actual observations are exactly equal to the previous
analyzer report. All23states remain unknown, with no player-owned facts supplied.
Extra score predictions are unreviewed and must not be counted as correct.

Independent numeric evidence: original accepted clock observations are0:29at
74.386003and74.419336, then0:06at74.452669and74.469336. Later timer values remain
unknown. Score changes0/1→0/2at74.486003; nine consecutive accepted updated pairs
extend through74.619336, duration0.133333seconds. The first exact native-tick
interval of0.05seconds is attained at74.536003. Later score abstentions terminate
the plateau. The two accepted reset clocks span only0.016667seconds; do not claim
0.05seconds of stable timer or fill the following unknowns.

`global_numeric_transitions.py` describes anomalies and current accepted score
plateaus using generic rules, original displays, native cadence, exact timebase
duration, canonical value confidence and existing0.90/0.05/1-second constants.
It reads no expected timer/score/round or GT time. Consecutive score plateaus
cannot join across abstentions, and source gaps reject. It reports one
conditional numeric pattern on this development interval, **not** a round-end
event. Active round state, safe temporal semantics and qualification remain
unproved; the geometric prefix is not lifecycle state. Three archived actual
analyzer score control windows (27frames, previously exposed/historical code)
produce0patterns; that is limited descriptive negative evidence, not fresh
reader/end qualification or comprehensive false-positive protection.

Tests:7diagnostic tests PASS0.45sec; Ruff PASS. Tests preserve source observations,
never release events/qualification and reject score gaps, low confidence,
two-point change, short plateau, missing clock and native frame loss. Production
code is unchanged;187relatedtests/Ruff/mypy remain its preceding checks. Original
measured-report bytes and descriptor input hashes are preserved; comparison is a
separate file. All82assertion records are unchanged. No targeted/sampled/full
E2E or canonical gain is claimed; Windows remains unverified.

Conclusion: actual numeric evidence exists for a separately testable end
hypothesis, but a clock anomaly plus score plateau does not by itself prove an
end. Next verify negative temporal contexts and independent labels/qualification
before designing a production release path; do not bypass the current result
predicate or backdate an event to satisfy GT. Evidence:
`r1_end_fresh_extended_inputs.json`, `r1_end_fresh_extended_comparison.json`,
`r1_end_numeric_temporal_pattern_validated.json`,
`global_numeric_archived_controls.json` under `e2e_reports/match_001/`.

## Fresh buy-menu-entry numeric negative control

Problem / target: `GT-R1-ROUND-END`. A clock-change/score-step hypothesis needs
negative UI transitions rather than only stable isolated crops. Select the
already located buy-menu onset83.419336 from the adopted full run's observed
state transitions, not GT/expected boundary data. Decode every native frame in
the explicit83.2–83.65development interval, using unchanged opt-in score/timer
readers and actual analyzer. The probe now optionally copies unchanged source
PNG bytes to a new Pi-local review directory, verifies copies through completion
and records original pixel hash, epoch and timebase. It does not claim blind
review or qualify a producer; existing archive/fresh commands remain supported.

Evidence:27native control frames,13unknown/14buy_menu_open. Classified menu
entry remains83.419336. Every frame has an accepted0/2score pair, and26have an
accepted clock. The descriptor finds0conditional numeric patterns and releases
0events. Runtime90.207540sec, no comparable preceding run. Calibration prefix
is separate geometry context and cannot corroborate a temporal boundary.

Post-prediction source-image review covers all27topbar crops plus full first,
last and transient frames. Score54correct/0unknown/0wrong; timer26correct/
1unknown/0wrong. Native83.302669 displays a composited0:15with a partially
visible menu overlay, while adjacent frames display0:28. The actual reader
abstains on that frame at confidence0; it is not converted to0:28or injected
as an accepted0:15clock. All original source images and measurements remain
intact. This is observed display/overlay evidence, not a diagnosis proving the
renderer cause or validating intentional-edit exclusion again. The explicit
user assurance already excludes edits for this video.

Previous/current/delta: archived descriptive controls27frames/0patterns and
this new control27frames/0patterns are distinct inputs, not comparable runs.
Canonical Current/Delta remain null; neither result proves canonical negative
assertion safety. No production recognition, end predicate, threshold, profile,
ownership, GT or full sampler changed. Ruff and git diff --check PASS; preceding
7diagnostic and187production-related tests remain the latest respective checks.
All82assertion records are unchanged. No full E2E or qualification is issued.

Conclusion / blocker: an observed UI clock transient without score change does
not become an end in this limited development control. It supports preserving
reader abstentions and separately checking score change. It does not establish
independent temporal holdout, active-round context, start/end semantics or safety
on other transitions. Further qualification remains necessary; Windows remains
unverified. Evidence under `e2e_reports/match_001/`:
`numeric_end_menu_entry_control.json`, `numeric_end_menu_entry_pattern.json`,
`numeric_end_menu_entry_review.json`. Images remain Pi-local in
`outputs/recognition-investigation/numeric-end-menu-entry-control/`.

Source-guard followup: the descriptive replay now rejects changed source epochs/
timebases when recorded, repeated source pixels and observation/PTS mismatch;
older reports without epoch metadata remain explicitly descriptive.11diagnostic
tests PASS0.46sec and Ruff PASS. Current guarded replay of all27menu-entry rows
still reports0patterns; no video or analyzer rerun was necessary. Production
code and qualification are unchanged. The original pre-guard descriptor report
is historical, not silently resigned as the newer implementation.

## Explicit break transport under the unedited contract

### Problem

The analyzer already observed explicit `content_jump` / `discontinuity` signals,
but its native UI measurements and assured producer discarded them. Direct
tracker tests reset correctly while the vertical producer path could not deliver
that evidence. Boundary provenance also used the string source epoch as
`continuity_segment`, whereas the package builder accepts nonnegative integers.

### Evidence and competing hypotheses

The existing R1 native replay retains both `2:25` frames, proposes the transition
at4.102669270833333 and confirms it at4.202669270833334. Under the user's explicit
source contract, intentional editing is excluded; UI transients, recording gaps,
PTS anomalies and reader errors remain possible. This change supplies no new
image-based no-edit claim and performs no new video decode. Timer changes alone
are not independent evidence of a source break.

### Continuity decision and contract change

The analyzer now preserves boolean break markers independently of geometry/phase
scan availability. The assured producer forwards true markers; replay accepts
only explicit boolean markers and resets before using boundary evidence. A
local integer segment increments on these markers or repeated source pixels;
epoch and all source hashes remain separate provenance. A break before a start
clears preparation and requires new evidence. A break after the first emitted
start stops native boundary publication at the receiver: without native break
positions in package transport, even a lone earlier start could extend a partial
package across the break. No synthetic end, GT timestamp or inferred score is
introduced. Segment-local fragment transport remains necessary to process such
inputs beyond the break safely. Cadence mismatches still fail before replay.

### Tests

100 related unit tests pass in71.71seconds, including actual analyzer marker
transport, producer/replay reset, invalid boolean markers, late breaks after a
single start, repeated pixels and receiver rejection. Ruff passes for
`src tests scripts/e2e`; mypy passes for120source files. Qualification fixtures
are synthetic and do not qualify the real video. No new targeted, sampled or
canonical full E2E was run: actual reader/joint temporal qualification is still
missing, so the production preflight cannot authorize release.

### Previous / Current / Delta

| Metric | Previous | Current | Delta |
| --- | --- | --- | --- |
| Explicit break markers delivered by assured producer | Discarded | Preserved | Contract repair |
| Boundary continuity segment type | String, ignored by builder | Nonnegative integer | Contract repair |
| Package publication after a post-start native break | No dedicated guard | Rejected pending fragment transport | Safety guard |
| R1 observed `2:25` samples retained | 2 | 2 | 0 |
| R1 diagnostic start candidates | 1 | No new run | Unmeasured |
| Canonical PASS / FAIL / NE | 23 / 55 / 4 | No new run | Unmeasured |
| Canonical negative failures / discontinuity violations | 0 / 0 | No new run | Unmeasured |

### Remaining blocker

Independent timer, phase and joint UI-transition qualification must authorize
real event release. The real R1 end remains unresolved: the existing qualified
end predicate lacks an accepted result banner coincident with the accepted score
transition. Numeric end patterns and menu controls remain descriptive development
evidence. Native break-to-package fragment transport is also incomplete; its
absence now fails closed instead of silently extending a package.

## Package fragments at explicit source breaks

### Problem and evidence

Native boundary replay now preserves breaks, but previously the package builder
could split only on game boundaries, boundary segment mismatches or sampled
observation gaps. A short native break may fall between adjacent sampled frames
and is not necessarily a sampled gap. Package range clipping alone also leaves
preparation/post-end association and derived event deduplication shared across
the source boundary. The Visual runtime currently resets its previous-frame
inputs on an unreadable image or a sampled gap over0.3seconds, but has no native
break-time input. Thus removing the receiver guard now would be unsafe.

### Change

`RoundPackageBuilder.build` accepts an optional `continuity_breaks` sequence of
strictly increasing, finite source times within the video. An empty sequence
keeps the existing path. For explicit breaks, observations and game boundaries
are partitioned into half-open source segments (the last includes video EOF).
The existing round/context logic runs independently in each segment; preparation
and post-end extension cannot read another segment. Window ranges are clipped
to that segment, and derivation starts with fresh temporal state per segment.
Packages retain global round numbering and original source-video duration. A
source break itself creates neither `round_start` nor `round_end`. A start and
end separated by a break are retained in separate partial fragments; they cannot
be paired into a complete round.

This is the builder contract, not yet the completed native runtime integration.
The application does not pass native breaks automatically. The receiver guard
remains active until HUD/Visual temporal resets and native source-time transport
are connected consistently. Direct HUD/Visual events still require their producer
to enforce source continuity before calling the builder; window clipping alone
cannot retroactively qualify event evidence.

### Tests and comparison

11new break tests cover splitting and boundary preservation, exact-cut snapshot
assignment, source metadata/round numbering, post-end context, preparation,
derived-state reset and invalid cut inputs. One initial test assumed all post-end
fragments would be merged; inspection showed the existing builder deliberately
retains a separate observed fragment. The test now checks the required no-crossing
invariant while preserving that existing behavior.105relatedtests pass in
83.44seconds, Ruff passes and mypy passes for120source files. No video decode,
new recognizer, threshold change, GT change or new canonical E2E run.

| Metric | Previous | Current | Delta |
| --- | --- | --- | --- |
| Builder explicit source-break API | Absent | Optional ordered source times | Added |
| Dedicated source-break unit cases | 0 | 11 | +11 |
| Native breaks connected automatically to builder | No | No | 0 |
| Receiver post-start break publication guard | Active | Active | 0 |
| Canonical PASS / FAIL / NE | 23 / 55 / 4 | No new run | Unmeasured |

### Remaining blocker

The next contract task is to propagate verified native source breaks through
sampled HUD and Visual temporal state before enabling segmented package
publication. Real timer/phase/UI qualification and R1 end recognition remain the
independent blockers to canonical boundary acceptance. No canonical assertion
has been relabeled or declared resolved by this fragment API.

## Visual source-break reset and semantic window isolation

### Problem and evidence

Native breaks can fall inside the Visual runtime's ordinary sampled gap limits.
Previously its pixel extractor, map timeline, enemy hysteresis and event state
would therefore retain history. A readable frame after an unreadable cut frame
must also retain the source-break notification; treating that unreadable frame as
having consumed the marker would leave the event engine's prior state alive.

### Change

Real Visual `analyze` and `trigger_windows` now accept optional ordered
`continuity_breaks`, with the same finite in-video time contract as the builder.
At the first readable frame after crossing a cut, pixel extraction and map
tracking restart, previous image/HUD inputs are cleared and a producer-owned
`source_discontinuity` proof resets the event engine's temporal state. A pre-cut
HUD sample cannot supply the post-cut view context. The notification remains
pending through unreadable frames. Trigger enemy presence latches reset at the
same source boundary. Semantic frame windows are restricted to the candidate's
source segment, so the optional semantic adapter cannot join images across a cut.
No source-break proof is emitted for unchanged default inputs, and a source break
itself creates no game event. Existing confidence/identity/ownership policies
remain unchanged.

Qualification's shared code fingerprint now includes Visual modules as consumers
of native source continuity. A changed consumer cannot inherit an old pipeline
qualification. The Visual implementation fingerprint advances from5to6. Existing
archived report fingerprints are preserved, not rewritten to claim qualification
of this implementation.

### Tests / Previous / Current / Delta

14new synthetic cases cover short-gap hysteresis reset without false enemy loss,
pixel/map reset, stale HUD rejection, unreadable cut frames, trigger latch reset
and invalid break inputs on both entrances. The focused Visual regression suite
passes72tests in48.85seconds. An earlier combined Visual/native suite passes105
in96.35seconds; these are different test sets, not a performance comparison.
Ruff and120-source-filemypy pass. No actual video decode, targeted/sample/full
canonical run or independent real-image qualification was performed.

| Metric | Previous | Current | Delta |
| --- | --- | --- | --- |
| Visual native source-break entrance | Absent | Analyze and trigger accept ordered cuts | Added |
| Pixel/map/event history at an explicit cut | Retained within ordinary gap limits | Reset independently of gap duration | Contract repair |
| Break notification after unreadable cut frame | Unavailable | Retained until a readable observation | Contract repair |
| Semantic window crossing an explicit cut | Possible | Restricted to one source segment | Contract repair |
| Native automatic runtime connection | Incomplete | Incomplete | 0 |
| Canonical PASS / FAIL / NE | 23 / 55 / 4 | No new run | Unmeasured |

### Remaining blocker

The application still needs one verified native cut sequence delivered to sampled
HUD stages, Visual trigger/final processing, and package association, with terminal
revalidation. The receiver's post-start break guard remains in place until that
integration is tested. Real timer/phase/joint UI qualification and actual R1 end
evidence remain unresolved; these synthetic reset tests do not authorize real
boundary release or prove canonical negative assertion outcomes.

Additional qualification/receiver regression:61tests pass in11.86seconds on the final source state. This verifies fixture qualification binding and native receiver compatibility; it does not qualify actual image recognition.

## Native source-break orchestration integration

### Problem / evidence

Builder and Visual cut entrances existed separately, but common orchestration
still called them without native source times. Merely removing the receiver's
post-start guard would have allowed stale HUD/Visual state and package extension
across a cut. A late marker can also change segmentation without changing the
already-produced round event list, so event-only terminal comparison is insufficient.

### Change

`native_source_breaks` reconstructs assured-source cuts by replaying the current
qualified lifecycle. It does not trust saved diagnostics or accept cut times from
GT. The receiver accepts an explicit downstream cut list only when it exactly
matches replay; its standalone default retains the fail-closed guard. Common
orchestration checks HUD, Visual and builder support before accepting cuts.
Actual source times reach Visual trigger/final processing and package building.
HUD Pass A and final processing receive a discontinuity on the first sampled
frame at or after each native cut, preserving frame order and native cut time.
No native frame, sampled timestamp or sampler policy changes. Multiple cuts
between two sampled frames still clear the next sampled frame's temporal state.

Events and cut lists are revalidated after final processing; the full runner also
compares them with the snapshot taken before Pass A. An added late break with
unchanged events is rejected. Qualification, profile/contract and source-video
terminal checks remain active. Unsupported consumers cannot silently ignore cuts.
Null Visual explicitly supports the contract because it emits no temporal events.
No system source-break evidence becomes player identity or ownership.

### Tests / Previous / Current / Delta

7new cases cover the three break forms (content marker, discontinuity marker,
repeated pixels) through common HUD/Visual/package/trace processing, unsupported
consumers, mismatched downstream cuts, mutation after Pass A and sampled cut
mapping. Synthetic qualification/reader fixtures test contracts, not actual
recognition accuracy. The final related suite passes108tests in89.75seconds;
an earlier82-test integration suite passes in66.72seconds (different scope).
Ruff and120-source-filemypy pass. All82canonical assertion records retain their
original digest. No new video decode, targeted/sample/full canonical E2E run,
threshold relaxation, GT change or actual image qualification was performed.

| Metric | Previous | Current | Delta |
| --- | --- | --- | --- |
| Native breaks automatically reach HUD/Visual/builder | No | Yes, for compatible assured-source pipeline | Connected |
| Post-start cut handling in common pipeline | Publication rejected | Independently reset consumers and split fragments | Supported |
| Standalone receiver without exact downstream cuts | Reject post-start breaks | Reject post-start breaks | 0 |
| Source-break-generated round ends | 0 | 0 in synthetic integration | 0 |
| Event-preserving late cut mutation | No Pass A snapshot comparison | Rejected against preflight snapshot | Contract repair |
| Canonical PASS / FAIL / NE | 23 / 55 / 4 | No new run | Unmeasured |
| Canonical negative / discontinuity failures | 0 / 0 | No new run | Unmeasured |

### Remaining blocker

Automatic source-break transport is now connected for the assured-input route.
This does not establish real reader or UI-transition qualification, actual R1 end
evidence, real negative-assertion safety or a canonical PASS gain. Next return to
frozen reader/temporal qualification and actual R1 end evidence rather than
repeating this completed transport work. Windows runtime remains unverified.

## Fresh frozen reader check at122.10–122.55seconds

### Problem / hypothesis / selection

Transport integration is tested, but actual independent reader and temporal
qualification remains missing. Before any new model change, freeze the existing
opt-in timer/score profile and current code and inspect a fixed late active-context
window. A conservative native-PTS inventory now contains585known source ticks;
none overlap122.10–122.55seconds. This does not prove exhaustive exposure or
independence from all prior JPEG/full-run review. The selection uses neither
expected timer/score values nor an assertion window. A pre-execution plan binds
profile/code and prior training/holdout/exposure reports. No qualification is
created from the inventory.

### Actual image evidence

Decode and analyze the27consecutive native frames exactly once, together with
four earlier calibration-prefix frames in the same analyzer call. The prefix
has a different epoch and large gap and is never temporal boundary evidence.
Actual source review occurs after predictions: all27show score0/2; frames1–18
show1:29, and19–27show1:28. These labels are diagnostic review data, never runtime
inputs or changes to canonical GT. All original PNG/pixel hashes, source PTS,
profile/code and frozen input hashes verify at terminal processing.

Timer:15correct/12unknown/0wrong of27. Score fields:10correct/44unknown/0wrong
of54. Only2frames contain an accepted pair, with approximately0.016667seconds
between them. All27phase scans are valid. Thus readable glyphs in the actual
image do not imply adequate score reader coverage; this active background is a
counterexample to treating the prior menu-control coverage as general coverage.
Do not fill unknowns or lower thresholds to repair it.

### Temporal control and ownership

Replay the same stored actual producer observations through the existing native
system projection and source-assured start tracker. Indices are rebased only for
this diagnostic replay; PTS/values/provenance remain actual. The primary states
remain16unknown/11live, but the system projection carries0player-owned facts.
The active-context replay produces0start candidates. This is a source-correlated
negative start context, not an independent positive lifecycle qualification or
canonical negative-assertion test. It contains no naturally timer/score-absent
control and does not release events.

### Tests / Previous / Current / Delta

No production or diagnostic source code changes in this step; no additional unit,
Ruff or mypy run was needed. Existing current-state checks remain those recorded
for native source-break integration. No targeted/sample/full canonical E2E run.

| Metric | Previous comparable context | Current | Delta |
| --- | --- | --- | --- |
| Processed native window frames | None | 27 | Unmeasured |
| Timer correct / unknown / wrong | None | 15 / 12 / 0 | Unmeasured |
| Score correct / unknown / wrong | None | 10 / 44 / 0 | Unmeasured |
| Accepted score-pair frames | None | 2 | Unmeasured |
| Active-context start candidates | None | 0 | Unmeasured |
| Diagnostic wall-clock | None | 77.194884seconds | Unmeasured |
| Real qualification created | 0 | 0 | 0 |
| Canonical PASS / FAIL / NE | 23 / 55 / 4 baseline | No new run | Unmeasured |

### Remaining blocker / next action

Preserve this frozen evidence and do not relabel it as whole-lifecycle qualification.
The score reader is safe here through abstention but cannot supply stable pairs
in most frames. Actual R1 end still lacks accepted result evidence at the
score-change point. Next distinguish the existing score reader's rejection
stage from missing geometry/identity, using saved source pixels without tuning
against this cohort; reader coverage improvements would require a new independent
holdout. Independent positive temporal/negative-absence qualification remains open.
Artifacts: `frozen_numeric_reader_holdout_plan.json`,
`frozen_numeric_reader_holdout_predictions.json` and
`frozen_numeric_reader_holdout_review.json` in `e2e_reports/match_001`.

## Frozen score rejection-stage diagnosis

### Problem / hypothesis

The late active-context check yielded44unknown score fields among54readings.
Determine whether these are unavailable geometry/identity, glyph NCC rejection,
class-margin ambiguity or segmentation failures before proposing any reader change.
No threshold, profile, ROI or preprocessing is adjusted in this diagnosis.

### Evidence and independent source inspection

Replay the production `StrictScoreGlyphReader` with its unchanged sidecar on all
27hash-bound source images. Nominal outer/inner ROI values and confidences exactly
reproduce all54actual analyzer field outputs. This does not independently attest
calibration, but demonstrates that the observed losses occur inside the configured
reader, rather than an identity gate dropping an otherwise accepted score.
All27phase scans were valid in the original actual analyzer run.

| Role | Accepted | ROI border foreground | Wrong component count | Digit layout | NCC/margin rejection |
| --- | ---: | ---: | ---: | ---: | ---: |
| Ally | 2 | 24 | 1 | 0 | 0 |
| Enemy | 8 | 16 | 2 | 1 | 0 |
| Total | 10 | 40 | 3 | 1 | 0 |

40/44unknowns (90.91%) stop at the existing border-foreground guard. The other
4stop at digit segmentation/layout. No unknown reaches the NCC0.90 or class
margin0.04 rejection stage. NCC/margin relaxation therefore does not address this
cohort's bottleneck and must not be attempted.

Direct source/mask inspection contrasts rejected frame1 and accepted frame26.
Both contain visually complete score glyphs inside the identical ROI. Fixed
white200segmentation also captures a bright background strip in frame1: detached
fragments appear around the ally0, while a broad strip is connected to the lower
part of enemy2 and touches the crop boundaries. Frame26produces isolated glyphs.
Simply deleting all border-connected components would also delete connected
parts of the actual2; it is not a justified repair. The blocker is background
separation before glyph comparison, not a proven missing score display.
Source/mask comparison images remain Pi-local.

### Tests / Previous / Current / Delta

The replay asserts equality with all54actual values and reader confidences and
verifies source encoded/pixel hashes, profile/code, prediction-report and video
SHA256 at terminal. Offline reader replay takes3.270809seconds; the original
77.194884seconds includes decode and full analyzer work and is not a comparable
runtime baseline. No production/diagnostic source changes, added candidate,
qualification, unit test rerun or new canonical E2E.

| Metric on identical27frames | Previous actual analyzer | Current frozen replay | Delta |
| --- | ---: | ---: | ---: |
| Accepted score fields | 10 | 10 | 0 |
| Unknown score fields | 44 | 44 | 0 |
| Wrong score fields (source review) | 0 | 0 | 0 |
| Unknown fields with identified reader rejection stage | 0 recorded | 44 | +44 diagnostic coverage |
| Canonical PASS / FAIL / NE | 23 / 55 / 4 baseline | No new run | Unmeasured |

### Remaining blocker / next action

A future score extraction change must separate value-invariant text structure
from background using training evidence, preserve NCC/margin/grammar safety and
qualify on a new held-out cohort and true negative controls. This exposed window
is now a rejection-analysis cohort and cannot be claimed as untouched holdout
for that future change. Its original frozen-reader assessment and hashes remain
unchanged. Independent UI-transition qualification and actual R1 result evidence
remain separate unresolved blockers. Do not substitute this score investigation
for proof of a real round boundary.
Artifact: `e2e_reports/match_001/frozen_score_rejection_stages.json`.

## Rejected local-opening foreground hypothesis

### Problem / hypothesis / fixed training plan

40of44unknown score fields in the exposed active-context diagnostic failed
border validation because bright background entered the white200mask. Test one
training-only, value-invariant local contrast hypothesis: estimate background by
elliptical9x9opening on the native inner-ROI grayscale, retain original intensity
only where gray-minus-opening is at least12, then call the unchanged production
strict white200/Gaussian reader. All ten classes, NCC0.90, margin0.04, border and
one/two-digit grammar guards remain unchanged. The wrapper sees only image/ROI,
not labels, timestamps, previous values or round IDs.

The declaration and source code/input hashes are frozen before replay. Use the
existing60development source frames/120score fields only. Do not load the exposed
27-frame active cohort or a fresh holdout. Prototype code remains exclusively in
`scripts/diagnostics/score_foreground_contrast.py`; the production profile and
reader implementation are unchanged.

### Evidence / decision

Baseline production replay exactly reproduces all120older development outputs.
It accepts114and rejects6at the foreground-border guard. The local-opening
prototype accepts53, rejects53at NCC,8at digit layout and6at the border guard.
Transitions:53accepted values remain identical,61accepted values become unknown,
6unknowns remain unknown,0unknowns become accepted,0accepted values change.
These are agreements with stored baseline outputs, not a new claim that all
baseline values are independently reviewed correct. The older development file's
`manual_source_review_complete` is false; preserve that provenance limitation.

Reject the hypothesis at training: it destroys usable glyph structure without
recovering the existing border failures. Do not adjust NCC/margin or sweep opening
kernel/contrast thresholds against the held-out cohort to conceal this result.
No profile adoption, new holdout extraction, boundary release or full E2E.

### Tests / Previous / Current / Delta

5diagnostic unit controls pass in0.46seconds, checking blank/bright/invalid input
abstention, source nonmutation and unchanged all-class/acceptance policy. Ruff
passes including the new diagnostic; mypy passes for120production source files.
The training replay verifies all input/script/profile/source-image bindings at
terminal and takes4.260661seconds for both methods. No comparable runtime exists.

| Training metric | Previous frozen reader | Local-opening hypothesis | Delta |
| --- | ---: | ---: | ---: |
| Accepted fields | 114 | 53 | -61 (-53.51%) |
| Unknown fields | 6 | 67 | +61 |
| Baseline accepted value disagreements | — | 0 | Unmeasured |
| Previously unknown fields recovered | — | 0 | Unmeasured |
| Canonical PASS / FAIL / NE | 23 / 55 / 4 baseline | No new run | Unmeasured |

### Remaining blocker / next action

A background estimator must preserve already usable digit strokes while separating
slowly varying/bright scene contribution. The9x9local opening does not satisfy
that condition. Next consider an estimator based on independently checked field
background support, with fail-closed rejection where support is inadequate, rather
than deleting connected components or weakening glyph acceptance. Use training
only until baseline preservation is demonstrated; a successful design still needs
new independent holdout and natural negative controls. R1 result/UI qualification
remain separate blockers.
Artifacts: `score_local_contrast_training_freeze.json` and
`score_local_contrast_training_results.json` in `e2e_reports/match_001`.
## Border-supported score background: fixed training rejection

Problem / target: score foreground segmentation is an input blocker for the
round lifecycle, including `GT-R1-ROUND-END`; it alone cannot guarantee a new
canonical PASS. The prior opening hypothesis damaged61accepted training reads.

Hypothesis / change: diagnostic-only `score_border_background.py` estimates each
native row from the maximum of left/right four-column medians and keeps original
grayscale pixels with contrast at least12. No erosion inside the digit, retry,
preferred value, time, Validation Pack input or temporal fill. The downstream
white200/Gaussian3x3 strict score reader retains all ten competitors, NCC0.90,
margin0.04, grammar and border rejection. Parameters and input/code hashes were
frozen in `score_border_background_training_freeze.json` before replay.

Evidence: all60saved source PNG byte hashes verify; unchanged baseline reproduces
the stored120values/confidences exactly. The older development file has no
complete manual score correctness review, so these comparisons measure baseline
agreement, not independently proven correct counts. The first invocation stopped
before reading because it compared a PNG byte hash with a decoded-pixel hash;
the corrected invocation verifies the documented PNG byte hash. No algorithm or
freeze parameters changed after that failure.

| Training metric | Previous | Current | Delta |
| --- | ---: | ---: | ---: |
| Accepted fields |114|86|-28 (-24.56%)|
| Unknown fields |6|34|+28 (+466.67%)|
| Previously unknown recovered |0|0|0|
| Accepted values changed |0|0|0|

Training comparison wall time4.283922seconds, with no comparable prior runtime
for this different hypothesis. Of120fields,86remain accepted with the same
display,28accepted becomeunknown,6unknown stayunknown. The28new rejections are
NCC failures; no threshold change is justified.

Independent mask diagnosis: all28regressed fields remove zero native pixels
above200, but each changes the enlarged white200 foreground. The86same-display
accepted fields also change their enlarged masks. Thus native bright-stroke
preservation is insufficient: suppressing dim surrounding pixels changes cubic
interpolation and antialiasing before template normalization. The6original
unknowns also lose native bright pixels and remainunknown. This localizes a
design failure; it does not prove geometry or new correctness.

Tests:6synthetic controls PASS (0.46seconds); Ruff onsrc/tests/scripts/e2e plus
the diagnostic PASS; mypy120source files PASS. Controls cover bright background,
supported stroke preservation, absent/invalid inputs and retained policy. They
are not real-video qualification. Reports:
`score_border_background_training_results.json` and
`score_border_background_mask_effect.json` under `e2e_reports/match_001`.

Conclusion / remaining blocker: reject before holdout, sampled or full E2E.
No production/profile adoption, qualification or event release. Archived
23PASS/55FAIL/4NE stays the baseline; canonical Current/Delta are unavailable.
No newly improved assertion is claimed. No source-code change means Windows
production behavior is unchanged; this diagnostic is untested on Windows.
Next investigate reference-compatible segmentation in the existing enlarged
comparison domain, freezing the hypothesis before training. The exposed27active
frames cannot be reused as untouched holdout. Real UI/start qualification and
R1 end result/score evidence remain separate unresolved gates.


## Enlarged-domain score foreground: limited positive evidence

Problem / target: `GT-R1-ROUND-END` needs accepted current-frame global score
inputs; this is one input blocker, not a guaranteed PASS fix. Native grayscale
background suppression changed interpolation and lost accepted glyphs.

Change / hypothesis: extract the production reader's original threshold stage
into `_foreground_mask` with the identical white200/Otsu OpenCV calls. The
training-only `EnlargedBackgroundScoreReader` estimates per-row background from
maximum left/right eight-column medians AFTER the unchanged cubic enlargement,
then keeps the original white200 mask where contrast is at least12. It inherits
all10class competition, NCC0.90, margin0.04, grammar and border safety. No retry,
expected value, Validation Pack input, temporal filling or production registration.

Evidence / comparisons:

| Cohort / score metric | Previous | Current | Delta |
| --- | ---: | ---: | ---: |
| Original60frame training accepted |114|114|0|
| Original60frame training unknown |6|6|0|
| Exposed27frame development correct |10|50|+40 (+400%)|
| Exposed27frame development unknown |44|4|-40 (-90.91%)|
| Exposed27frame development wrong |0|0|0|
| Fixed new27frame window correct |46|47|+1 (+2.17%)|
| Fixed new27frame window unknown |8|7|-1 (-12.5%)|
| Fixed new27frame window wrong |0|0|0|

All114original accepted training displays stay the same. Default production
reader values/confidences/sources reproduce all120stored fields. Stored training
acceptance is not independently reviewed correctness. The exposed active27frames
are explicitly development, never untouched holdout. Their40recoveries and10
preserved correct reads match earlier post-prediction source-pixel review.

Before new decoding, freeze125.10–125.55seconds outside the saved known native
ranges; no expected value/image selection. Decode all27native frames with exact
256tick cadence, retain source PNG/pixel hashes and verify terminal video SHA,
plan/code/inputs. Source topbar sheet review after predictions shows score0/2in
every frame. Previous46correct remain correct;1unknown becomes correct,7stay
unknown. Runtime29.589515seconds, no comparable runtime delta. This is a frozen
new-window check, but historical full JPEG exposure is not exhaustively excluded
and all27frames are correlated, with the same two score classes as development.
It does not establish broad independent qualification or geometry/lifecycle.

Tests:96related score/timer/template cases PASS (2.13seconds), Ruff PASS,
mypy120source files PASS. The first mypy check required a type-only cast of the
OpenCV ndarray; it changes no pixel operation. Initial training freeze/report
retain their historical pre-cast code fingerprint; a new development freeze
binds the corrected code. Production default behavior is unchanged, but its
source fingerprint changes and old qualification cannot be reused. Default mask
unit tests compare exact OpenCV output for both modes; synthetic dim-background
and uniform-bright controls do not substitute for natural negatives.

Files: `src/valorant_ai_coach/hud/score_glyphs.py`,
`scripts/diagnostics/score_enlarged_background.py`,
`scripts/diagnostics/probe_score_enlarged_background.py`,
`tests/unit/test_score_enlarged_background.py`; hash-bound freeze/results/review
JSONs prefixed `score_enlarged_background_` in `e2e_reports/match_001`.
Images remain Pi-local. The initial active replay stopped on an integer-vs-display
string assertion in diagnostic comparison; normalization of stored numeric
values corrected the comparison without changing reader pixels or predictions.

Conclusion / remaining blocker: promising segmentation evidence, no production
profile adoption, qualification or event release. No targeted/sampled/full
canonical run, new assertion PASS or negative/discontinuity guarantee is claimed;
archived23PASS/55FAIL/4NE remains the reference and canonical Current/Delta are
unavailable. Next validate this frozen method on source-reviewed natural
score-absent and difficult negatives. Do not tune against the new window.
Real UI/start qualification and R1 end result evidence remain independent gates.
Windows OpenCV/ROI/profile/runtime behavior remains unverified on hardware.


## Opt-in production foreground and actual producer check

Problem / hypothesis / target: background segmentation blocks global score
coverage relevant to `GT-R1-ROUND-END`. Keep the frozen enlarged-domain algorithm
and inspect real negative backgrounds before exposing an opt-in production mode.

Evidence: the existing64frame score-menu source review explicitly reports zero
natural timer-absent and zero score-absent frames. Do not relabel these positive
fields as absent negatives. Two fixed3x3grids on walls/architectural edges/smoke
in native frames1/14/27of the125.10–125.55archive supply54unmodified44x45crops.
Both contact sheets are manually reviewed before predictions; none shows a
numeric glyph. PNG and decoded-pixel hashes bind the original source. Both
readers reject all54crops: false numeric Previous0 / Current0 / Delta0;
unknown54 /54 /0. Offline comparison runtime6.750111seconds. These correlated
HUD-external controls test background rejection, not true nominal score-field
absence or lifecycle negative qualification. No arbitrary additional-video
requirement is imposed; unavailable evidence stays explicitly unproven.

Change: `StrictScoreGlyphReader` accepts explicit
`foreground_preprocessing="white200_rowcontrast_v1"`, requiringGaussian3x3.
The exact frozen enlarged-domain median support/contrast12mask is used once,
with all10classes, NCC0.90, margin0.04, grammar and border checks unchanged.
Successful reads record `foreground_white200_rowcontrast_v1` provenance.
Otsu/white200/default profiles retain their former behavior. The opt-in sidecar
`score-reader-rowcontrast-pipeline.templates.json` changes only the two score
preprocessing fields relative to the prior opt-in white pipeline; identity,
HP, timer, spectator, geometry and allother entries are unchanged. It is not
selected as the adopted profile and no real qualification is created.

Production parity:108actual score fields from exposed development/new-window
archives match the frozen diagnostic's values/confidences exactly. Accepted
reads retain the new preprocessing source tag. Runtime4.677465seconds. The
previous/current comparison is algorithm output parity, not canonical coverage.

Actual producer: `probe_native_end_inputs.py` processes the27saved native frames
with the opt-in sidecar plus4origin prefix frames for geometry context. The large
gap is explicitly not temporal evidence. All54produced score values/confidences
match the nominal reader replay:47correct/7unknown/0wrong. Nominal previous
baseline on the same source has46correct/8unknown/0wrong, giving+1/-1/0; that
baseline is not a previous actual-analyzer run.20frames have both score fields,
16have timer display,27have valid phase scans,0have matched round result.
Primary stateunknown27; HP/armor/ammo/weapon facts0 and player-specific validity
false27. No unknown identity is promoted to player ownership. Runtime52.234331
seconds; no comparable prior actual-analyzer runtime.0released events and no
qualification are deliberate; they do not prove canonical negative assertions.

Tests:82score/template/foreground cases PASS (1.87seconds); Ruff PASS;
mypy120source files PASS. Profile tests exercise both score roles and default
isolation. Exact production/diagnostic mask and all10synthetic display outputs
agree. An initial synthetic test assumed a renderer designed for Otsu would be
accepted under white200; it was corrected to check exact frozen-diagnostic
parity without relaxing acceptance. Actual accepted-source provenance is checked
on the108real-field replay. Code/profile fingerprints change, so historical
qualification cannot be reused; original diagnostic bindings remain unchanged.

Reports: `score_enlarged_background_controls_{complete_plan,review,results}.json`,
`score_rowcontrast_production_reader_parity.json`,
`score_rowcontrast_native_archive_manifest.json`,
`score_rowcontrast_actual_analyzer.json` in `e2e_reports/match_001`.
Images remain local. Production fingerprint
`44030c081c6d359c6fd618cfae128c5f339191f31942e0b623a06ae460f1073f`;
opt-in profile fingerprint
`8f075f9580c8e6e9980d5ab807e6ea7b8c4b0fda181b3a64b1c24546f9c7fa66`.

Conclusion / remaining blocker: the image→profile→production-reader→HUD-producer
path now carries the frozen foreground behavior correctly. Real current-profile
qualification, boundary/control replay and canonical targeted/sampled gates
remain. R1 result/UI qualification remains independent; this change cannot
claim33round/packageFAIL resolved. No full E2E or new canonical assertion
status; archived23PASS/55FAIL/4NE remains the reference, Current/Delta unknown.
Windows remains unverified on hardware. Next replay this fixed profile through
native lifecycle boundary/control intervals before any promotion/full run.


## R1 end score replay and result configuration correction

Problem / target: determine whether the frozen opt-in score preprocessing removes
an input blocker for `GT-R1-ROUND-END`. Replay the same10native frames at
74.3693359375–74.5193359375with identical4frame geometry prefix; do not use any
GT expected value/time in production. Actual stored PNG hashes/native cadence
and current code/profile bind the replay.

| Same10frame diagnostic | Previous | Current | Delta |
| --- | ---: | ---: | ---: |
| Score correct fields |18|19|+1 (+5.56%)|
| Score unknown fields |2|1|-1 (-50%)|
| Score wrong fields |0|0|0|
| Complete score pairs |8|9|+1 (+12.5%)|
| Timer accepted frames |4|4|0|
| Result matched frames |0|0|0|
| Wall seconds |33.461699|33.170153|-0.291545 (-0.87%)|

All18accepted score displays are preserved. The ally0at74.38600260416666becomes
accepted; the earlier ally field staysunknown. Source image review confirms0/1
until74.4693359375and0/2from74.48600260416667. Runtime change is observational
noise-scale difference, not demonstrated speedup. No boundary or qualification
is produced; allframeprimary states remainunknown.

Important correction to result interpretation: the score-only white/rowcontrast
pipeline sidecars contain NO `round_end_template` signal. In the actual producer,
`round_result_matched` requires that signal to be true and its matcher to be
`semantic_text_ncc_v1` (`hud/analyzers.py`). Therefore result0in these runs means
unavailable configuration; it does not measure the early banner's NCC. The
separate historical reference diagnostic rejects the early TEAM ACE at roughly
0.388; that trained late reference has never been configured in this score
sidecar. Both facts are blockers, but they are different measurements. Earlier
sections saying result0remain historical; this paragraph clarifies their cause.

Diagnostic change: `probe_native_end_inputs.py` now records `global_signal_setup`
for phase/result, with `not_configured`, `semantic_matcher_unavailable`, or
`loaded` status, configuration/loaded booleans and loader diagnostics. This
observes the actual loader, not merely a rawJSONkey. Loaded does not mean a
current-frame match or lifecycle qualification. Existing reports are not
rewritten/resigned. Threeunit cases cover missingprofile/omittedsignal,
invalidassets, and genuinely loaded syntheticreference. Tests3PASS; RuffPASS;
mypy120source filesPASS. This turn changes no production recognition behavior.

Reports: `r1_end_rowcontrast_archive_manifest.json`,
`r1_end_rowcontrast_actual_analyzer.json`, `r1_end_rowcontrast_comparison.json`.
The comparison supplies posthoc loader status bound to the exact profile hash,
separately from the immutable producer report. All82canonicalassertion statuses
retain their original digest; no new full E2E or claimed PASS. Archived baseline
23PASS/55FAIL/4NE; canonical Current/Delta unknown. Negative/discontinuity gates
are not newly verified by this input diagnostic. Windows remains unverified.

Next action: make an explicitly diagnostic sidecar using the existing hash-bound
late-result reference and its original training assets; inspect actualproducer
result evidence and temporal relation to score/timer. Do not silently promote
that reference, lowerNCC, or reinterpret score improvement as round-end success.


## Existing late result reference connected to actual producer

Problem / target: `GT-R1-ROUND-END` remains blocked; prior score-only profiles
omit the semantic result input. Test actual loader/producer transport with the
existing reference, without making a new reference or changing thresholds.

Change: diagnostic-only `score-rowcontrast-late-result-diagnostic.templates.json`
adds only`round_end_template`to the previous score-rowcontrast sidecar. Original
reference/mask/regions PNGs are copied byte-for-byte after verifying the original
freeze hashes. Three training crops are regenerated exactly from hash-verified
source JPEG pixels, with original frame hashes and crop842,178,1078,247. Bounds
are mapped into the existing round_end_banner ROI. Semantic loader confirms
3supported training frames, no profile diagnostics. No code, geometry, NCC,
identity, validation/assertion or default-profile change. No adoption or real
qualification. Profile binding hashes the copied assets and new crop assets.

Evidence: actual`RealHudAnalyzer.observe_frames(_build_events=False)`processes
3training,11existingholdout,3negative and10earlynativeframes, with4origin native
prefix frames for geometry. Input samples are ordered by their original stored
PTS; archived JPEG gaps are explicitly NOT continuous/native lifecycle evidence.
Source PNG/JPEG byte/pixel hashes and terminal source-video/profile/code hashes
verify. Direct nominal reference measurement matches producer counts in every
cohort; no loss is found between profile and producer.

| Result-input cohort | Previous omitted signal | Current diagnostic profile | Delta |
| --- | ---: | ---: | ---: |
| Training accepted /3 |0|3|+3|
| Existing holdout accepted /11 |0|3|+3|
| Negative false positive /3 |0|0|0|
| Early native accepted /10 |0|0|0|

Previous counts in this table follow the absent-signal contract, not a new
paired replay with the old profile. The11holdout frames were previously exposed
and belong to the same episode; they are not fresh independent qualification.
The early visible TEAM ACE remainsNCC0.3875529176, below0.90. No threshold is
lowered to force it through. Runtime68.830835seconds, no comparable prior run or
runtime delta. No event is released;`_build_events=False`and absent qualification
make this an input diagnostic, not evidence of end-to-end event safety.

Temporal observation: the accepted score step0/1→0/2occurs between native
74.4693359375and74.48600260416667, with no accepted result on that current frame.
Accepted result samples are75.402669,75.536003,75.602669,75.619336,75.802669,
76.269336. None coincides with an observed one-point score step. Thus the
observed same-frame result/score-step conjunction count is0. This distinguishes
configuration transport (now demonstrated) from appearance mismatch and temporal
contract. Gapped samples cannot authorize delayed corroboration/backdating.

Reports: `late_result_diagnostic_profile_binding.json`,
`late_result_actual_producer_replay.json`, `late_result_score_temporal_alignment.json`.
Assets remain Pi-local beneath the profile's`result-late-diagnostic`directory;
original reference freeze/reports are preserved. The production fingerprint is
unchanged44030c081c6d359c6fd618cfae128c5f339191f31942e0b623a06ae460f1073f;
diagnostic profile fingerprint is
10bfac00544e510ebf3f3e2c0072c9beba24938b2ff996c9012f7e4046d82c99.

Conclusion / remaining blocker: result evidence reaches the producer, but the
current same-frame end predicate still lacks the necessary conjunction. Do not
claim a round end, qualification, canonical improvement or33FAIL resolved.
All82assertion statuses remain bound to the original digest; archived baseline
23PASS/55FAIL/4NE, canonical Current/Delta unavailable. No full E2E. Windows
remains unverified. Next gather a continuous native interval through the clock/
score transition and later result support, then evaluate bounded temporal
corroboration and independent controls without GT timestamps or cross-gap joins.

Related verification:32signal-setup/semantic-text unit cases PASS (0.87seconds), RuffPASS, mypy120source filesPASS.


## Continuous native result/score timing measured

Problem / target: mixed archived samples cannot prove that score and delayed
semantic result belong to one continuous episode. Measure actual inputs relevant
to`GT-R1-ROUND-END`without changing the reference or end predicate.

Change / execution: freeze an explicit74.20–76.00native interval using the
existing diagnostic result/rowcontrast profile. Process all108native frames at
256ticks with4separateorigin prefix frames for geometry; the prefix gap is not
lifecycle evidence. This is input continuity inside the window, not a complete
R1start→end state-machine run. No production logic, threshold, GT, assertion,
sampler or adoptedprofile change.

The first attempt terminates before the analyzer: temporary lossless PNG output
exceeds the diagnostic200MBbudget. Its terminal error/log hash is preserved in
a new budgeted plan. Available disk17GB permits explicit500MBbounded storage.
Diagnostic CLI now accepts`--native-max-png-bytes`(default200MBretained; positive
value required). Retry only after actual terminal failure, with identical input
interval and no skips. Native decode and producer finish successfully. Images
remain local; no status/log polling occurs during either run.

Evidence / current counts:108native frames,17timer displays,47complete score
pairs,29accepted result frames,108valid phase scans and108unknown primary
states. One epoch, exact256tick cadence,0adjacent repeated pixel hashes,
0explicit content_jump/discontinuity markers. This does not attempt to reprove
no-edit assurance. Source/profile/code/input bindings remain verified; no
qualification or event is released. Runtime297.784433seconds; Previous comparable
continuous run and runtime Delta unavailable. The shorter10frame and gapped
archive runs are not runtime comparators.

| Input timing | Actual native PTS seconds |
| --- | ---: |
| Accepted clock decrease |74.45266927083334|
| Accepted0/1→0/2score step |74.48600260416667|
| New score plateau reaches0.05seconds |74.53600260416667|
| First accepted result |75.3193359375|
| First result run reaches0.05seconds |75.3693359375|

The first result run contains27consecutive native matches through75.75266927083334,
minimumNCC0.9248682987. A second2frame match at75.802669–75.819336does not reach
0.05seconds; it is not counted as stable. Score step→result onset delay0.833333s;
score step→result stability delay0.883333s. Same-frame result/score-step conjunction
remains0, as in the prior gapped observation; the native evidence now resolves
that specific continuity gap. Timer/score/result values are not imputed through
unknowns. All17accepted timer fields are manually reviewed after predictions:
17correct/0wrong,91abstentions remainunknown. No correctness label is claimed for
allscore/result outputs without a complete independent review.

Reports: `r1_end_continuous_result_{plan,budgeted_plan,inputs,alignment}.json`,
`r1_end_continuous_numeric_pattern.json`, `r1_end_continuous_timer_review.json`.
The existing numeric descriptor finds1conditional clock/score pattern and emits
0events. Native timing measurements use actual ticks; no event timestamp or
roundIDis copied from GT. The parser handles absent optional timer-display fields
as missing, without reconstructing text.

Tests:14signal-setup/numeric-transition unit casesPASS; RuffPASS;
mypy120source filesPASS. An initial unit invocation used a nonexistent filename,
ran0tests and was corrected; only the completed14case run counts as evidence.
No new canonical targeted/sampled/full run; all82assertion statuses retain their
original digest. Baseline23PASS/55FAIL/4NE, canonical Current/Delta unavailable.
Negative/discontinuity assertions are not newly verified by this input run.
Windows OpenCV/PNG/PTS/storage behavior remains unverified on hardware.

Conclusion / remaining blocker: temporal mismatch is established in continuous
native input. The existing same-frame predicate cannot consume these separately
accepted facts. Next specify an explicit pending-end corroboration contract with
bounded latency, qualified inputs, native source continuity, contradiction/gap/
discontinuity resets and negative controls. Do not choose a timeout by fitting GT,
force the earlyNCC0.388banner through, fill current unknowns or release events
from unqualified diagnostic evidence. Complete R1active lifecycle context and
independent qualification still remain gates.


## Pending-end contract: frozen diagnostic hypothesis

Problem / target: `GT-R1-ROUND-END`needs time-distributed global evidence; the
actual same-frame score-step/result conjunction is0. Prototype the temporal
relationship before changing production events or claiming qualification.

Change / hypothesis: `scripts/diagnostics/pending_end_contract.py`consumes
hash-bound producer rows and the existing numeric-pattern descriptor. It requires
native PTS/epoch/timebase/pixel provenance, prior accepted score stability,
accepted one-point score update/new score stability, and later consecutively
accepted result stability. Each stability uses existing0.05seconds; NCC remains
0.90and numeric acceptance remains unchanged. Freeze maximum correlation1second
from the observed clock change before replay. This is a conservative TRAINING
hypothesis chosen with observed input available, not an independently established
game guarantee. It is not a new production policy and is not selected with GT
expected timestamps/values. No timeout sweep or extension is performed.

Rejection contract: source PTS/cadence/epoch mismatch or repeated adjacent pixels
cannot corroborate; explicit content_jump/discontinuity, phase scan unavailable,
occlusion, menu/spectator/unsafe context or purchase phase prevents correlation.
An accepted conflicting score or additional clock transition invalidates pending
evidence; result nonmatches reset result stability. Timeout never extends.
Current unknown numeric fields remainunknown. Previously accepted score evidence
is stored as history, never substituted into current values/identity/ownership.
This conservative batch prototype rejects an entire inspected interval on unsafe
context/source markers; it is not yet the streaming lifecycle state machine.

Tests:15new synthetic contract cases plus11existing numeric cases,26PASS
(0.74seconds); RuffPASS; mypy120source filesPASS. Artificial values/times differ
from the video. Controls cover missing current score preservation, immutable
input, no event/qualification/active claim, discontinuity, spectator, phase,
score rollback, weak/brief/absent result, gap/epoch/repeatedpixels/missing source,
nonextending timeout, secondclock transition before score stability and result
jitter. No tests load Validation Pack or realqualification.

Evidence: freeze records code and3producer-report hashes. Fixed replay finds
1conditional R1pattern: clock1143593, score1144105, scorestable1144873,
resultfirst1156905, resultstable1157673ticks. Result minimumconfidence0.9248683;
prior/new score minimum0.9266304. At confirmation current score is[None,None],
and historical observed score is[0,2]; no missing field is filled. The
menu-entry report yields0patterns with conflicting-context rejection, and
active-context report0patterns. These are reused reports with different profiles,
not independently qualified negatives for the newly configured result profile.
Offline replay0.042859seconds; no comparable previous runtime/delta.

Previous same-frame conjunction0 and Current conditional pattern1 are DIFFERENT
metrics, not evidence of+1PASS or+1event. Released events Previous0 / Current0 /
Delta0. No active round is asserted, event timestamp chosen, roundIDassigned,
qualification minted or production/defaultprofile/safety behavior changed.

Artifacts: `pending_end_diagnostic_freeze.json`,
`pending_end_diagnostic_results.json`, `tests/unit/test_pending_end_contract.py`.
The original82assertion digest is preserved. No new canonical targeted/sampled/
full run; archived23PASS/55FAIL/4NE remains baseline and canonical Current/Delta
unavailable. Windows remains unverified. Next validate the FIXED hypothesis on
current-profile independent native controls and complete active lifecycle context,
then specify streaming pending-end qualification/event/provenance. No automatic
promotion from a descriptive training pattern to a boundary.


## Current-profile native controls for fixed pending-end hypothesis

Problem / target: reused control predictions used profiles without result input,
so they could not validate the newly configured semantic path relevant to
`GT-R1-ROUND-END`. Keep reader/reference/contract constants frozen.

Evidence / change: actual analyzer reprocesses all27saved83.20–83.65menu-entry
native frames under the current diagnostic result/rowcontrast sidecar. Result
matcher is loaded, result false matches0; primaryunknown13/menu14,26accepted
timer reads and27complete score pairs. All81timer-display/score output values
match the previous source-bound run, including the unaccepted ghosted timer;
unknown is not filled. Pending-end patterns Previous0 / Current0 / Delta0;
result false positives0 /0 /0, timer26 /26 /0, pairs27 /27 /0. Reused source,
not a fresh independent holdout. Current runtime66.943425seconds versus older
fresh decode90.207540; these input modes differ, so no speedup/runtime Delta
is claimed.

Before new decoding, freeze130.00–131.20seconds outside the saved known native
inventory. This1.2second interval exceeds the1second hypothesis horizon and is
selected without expected values or source-image inspection. All72native frames
are decoded/analyzed, exact cadence verified and unchanged PNGs archived.
Current loaded result profile yields0result matches,0pending patterns,
64accepted timer displays,27score pairs,72unknown primary states. All72result
ROI crops are reviewed AFTER prediction: no result text visible,0false matches.
No blanket numeric correctness claim is inferred from confidence; numeric
acceptance counts are kept separate. Player-specific validity remainsfalse and
owned HP/armor/ammo/weapon facts0. No sampling/threshold/identity/ownership change.

Runtime156.645030seconds; Previous comparable active run and runtime Delta
unavailable. Terminal source/profile/code/PNG bindings verify; fixed hypothesis
script hash is unchanged. Offline two-report replay0.064235seconds. These are
same-video correlated controls, and historical full JPEG exposure is not
exhaustively excluded. They are useful native negatives, not complete independent
positive/end qualification or a canonical negative-assertion run.

Reports: `pending_end_menu_current_{archive_manifest,inputs}.json`,
`pending_end_new_active_{plan,inputs}.json`,
`pending_end_current_profile_controls.json`. Contact sheet hash and review scope
are stored; images remain Pi-local. No production code changed this turn, so
prior26relatedunit/Ruff/mypy results apply to the identical implementation;
no redundant broad tests are rerun for new read-only diagnostic data.

Conclusion / remaining blocker: configured result/score changes introduce no
conditional-end pattern in these two controls. Released events stay0;
qualification/defaultprofile adoption/canonical Current/Delta remain absent.
Original82assertion status digest is preserved; archived23PASS/55FAIL/4NE remains
the baseline. Full E2E is not run because complete qualified lifecycle context
is still missing. Windows remains unverified. Next implement a streaming
pending-end collector behind an explicit separately qualified opt-in contract,
preserve the current default route, and test resets/duplicates/event provenance.
Independent positive temporal qualification and R1start→active→end source
context remain gates before production release or canonical adoption.

## Source assurance audit and separately qualified streaming end

Problem: assurance must remove edit-only proof obligations without turning raw
UI transitions into qualified events. The batch end diagnostic also could not
discard and rearm evidence one frame at a time. Targets remain
`GT-R1-ROUND-START`, `GT-R1-ROUND-END`, `GT-R2-ROUND-START` and their existing
count/ordering constraints. No assertion changes.

Input contract audit:

| Condition | Explicitly assured source | Other sources |
| --- | --- | --- |
| Image proof excluding scene-preserving edits | Not required | Existing route unchanged |
| Scene witness NCC / camera correspondence as edit exclusion | Not required | Existing qualified scene route unchanged |
| `continuity` / `scene_continuity` qualification as edit exclusion | Not required for assured start | Existing requirements unchanged |
| Exact source SHA256 and explicit assurance file | Required | Assurance path unavailable without matching contract |
| Native cadence / PTS / epoch / distinct pixels / source breaks | Required | Required |
| Qualified phase scan, timer and temporal UI transition | Required | Required |
| Identity / ownership / negative assertions / reader acceptance | Unchanged | Unchanged |

The guarantee is a user input contract, not an image-classification outcome.
It is explicitly selected and bound to the exact source hash. It never supplies
reader qualification or a player fact. Recording loss and PTS anomalies remain
failure cases. No new scene or edit proof was requested.

R1 evidence: replay `r1_unedited_native_start_through6.json` using all358native
rows and their actual source-bound phase scans, without assumed valid scans.
The tracker retains `0:00 → 2:25 → 2:25 → 1:39` unchanged, proposes at
4.102669270833333sec, begins coherent clock support at4.152669270833333 and
confirms at4.202669270833334. There is1candidate through6sec, not repeated starts.
This reuses historical reader predictions; it is not new recognition or
qualification. The path remains `pre_round → transient_ui_transition →
round_active_candidate`. Assurance resolves the edit hypothesis; UI transient
and reader error remain competing hypotheses for independent reader/UI review.

Contract change: `UneditedUiEndTracker` buffers bounded global evidence in an
already-started round. An accepted abnormal clock decrease proposes a candidate
only with stable prior scores. Adjacent accepted scores must change by one point
on one side and remain stable for0.05sec. A later result needs consecutive0.05sec
support within the frozen one-second clock-origin horizon. That horizon remains
a development hypothesis, not an established game invariant.

Activation requires a NEW `ui_end_transition` qualification, exact source
assurance and qualified timer/score/result. Old sidecars cannot enable this path;
their same-frame end predicate is preserved. No real qualification or default
profile is promoted. The code fingerprint changes; historical reports are not
re-signed or claimed as current-runtime evidence.

Source breaks, invalid binding, start and completed end clear pending evidence.
Unsafe phase/menu/spectator/occlusion contexts, accepted conflicting scores,
another abnormal clock transition or timeout discard it. Result nonmatches
restart consecutive support. OCR abstention cannot count as repetition. After
new scores are supported, current unknowns remain unknown while historical
scores can corroborate later result pixels. The collector is private to the
source-validating lifecycle owner, not a source-validation replacement.

Event contract: use first observed score-change PTS and retain separate clock,
score stability, result onset/confirmation, confidence and pixel hashes. Never
backdate from GT. The owner attaches assurance provenance; existing transport
attaches qualification/profile/code/source provenance and `system` actor. A
qualified end rearms preparation for the next package. Tests cover native→
package→trace transport, two packages and pre-round association.

Comparison of conditional offline patterns, not canonical events:

| Metric | Previous | Current | Delta |
| --- | ---: | ---: | ---: |
| R1 end conditional patterns | 1 | 1 | 0 |
| Menu-entry conditional patterns | 0 | 0 | 0 |
| Active-window conditional patterns | 0 | 0 | 0 |
| Diagnostic released events | 0 | 0 | 0 |

Replay uses frozen108R1,27menu and72active producer rows. R1 yields1pattern at
74.48600260416667sec, confirmation75.3693359375sec, confidence0.9248682987478553.
The observed score-change time is OUTSIDE the fixed R1 end acceptance window.
It is not a PASS improvement. The earlier clock transition's temporal meaning
still needs independent review. Menu/active give0patterns. Isolated end inputs
have `active_round_proven=false`; current unknowns and source files are unchanged.

Tests:191related unit tests PASS; RuffPASS; mypy121source filesPASS. Cases include
opt-in isolation, old route, duplicate suppression, source breaks, partial score
conflicts, weak readers, result jitter, timeout, rearm, no second end, actor/PTS/
provenance, package association and input immutability. Synthetic qualification
fixtures are not real qualification.

Report: `e2e_reports/match_001/streaming_end_contract_replay.json`. Separate offline
timings are recorded; no comparable previous runtime. Canonical Previous remains
23PASS/55FAIL/4NE; Current/Delta unavailable. Original82assertion digest unchanged.
No new targeted/sampled/full canonical run: qualification and complete actual
start→end context remain gates. Windows hardware remains unverified.

Next: qualify the source-assured start/UI path and independently settle end
timestamp semantics before enabling pending-end. Preserve fixed windows and
thresholds; never force a score timestamp into GT or promote conditional patterns
to released events.
