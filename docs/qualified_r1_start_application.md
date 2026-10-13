# R1 start through the actual application merge

## Problem and target

The current qualified source entrance emits a real R1 start, and a direct
builder/adapter replay passes `GT-R1-ROUND-START`. That does not yet prove
`HudVideoProcessor` admission, source validation, event merge, HUD/visual fusion
and terminal publication. Exercise these actual application stages with the
same unchanged qualification, source and production code.

## Exact native output reuse

Use the published 358-frame qualified native producer result, originally
generated from freshly decoded source 0–6 seconds. Retain every source row,
observation, event and diagnostic unchanged. It is formal source-owned producer
output, not a newly constructed diagnostic proof or inferred event.

Before use, verify its complete recorded input hashes, exact recognition-code
and profile fingerprints, original qualification SHA and current source-video
SHA. Load the original three-component start bundle under the matching explicit
unedited contract. No newer five-component bundle is substituted for its
qualification. The existing application boundary validator independently
replays and checks the native lifecycle at entrance and completion.

This is an offline integration check using an unchanged producer result, not
fresh native recognition or a production recognition-cache feature. Do not
reuse it after any source, code, profile, qualification or input mismatch. No
GT or external replacement evidence is injected.

## Fresh main inputs and actual application path

Decode all native frames in the explicitly selected main windows 0–0.08 and
3.9–4.5 seconds: 39 images. Verify each current decoded pixel hash against its
matching native source row. Each `FrameSample` keeps actual ticks, time base,
source video hash and current encoded image hash. The startup images are ordinary
main observations in this test; no special geometry acceptance or synthetic
timestamp is supplied.

Call the real `HudVideoProcessor.process_frames` with `RealHudAnalyzer`,
`RealVisualAnalyzer`, actual event-source contract and `RoundPackageBuilder`.
Keep strict boundary mode and explicitly allow the existing open fragment via
`require_detected_rounds=False`. No fake analyzer, fake visual result or reduced
recognition threshold is used.

The application performs native boundary/source admission, actual main HUD
recognition, exact-source timer-display merge, actual visual analysis, world-view
gating, evidence fusion, package schema validation and terminal native/input
revalidation. These declared main windows do not pretend to be one continuous
native temporal sequence. Boundary continuity comes from the complete validated
358-row native result, not the gap between selected main windows. Full sampler
and two-pass behavior remain unchanged and are not exercised here.

## Result and comparison

One system `round_start`, at 4.102669 seconds with confirmation 4.202669,
survives the full application merge into the trace. Actor, type, timestamp,
confidence and every event attribute exactly match native producer output.
No duplicate start, end or visual event appears. The unchanged canonical
evaluator again reports `GT-R1-ROUND-START` PASS on the local fragment.

| Metric | Previous direct-builder verification | Current application merge | Delta |
| --- | ---: | ---: | ---: |
| Native starts reaching trace | 1 | 1 | 0 |
| Native ends reaching trace | 0 | 0 | 0 |
| Targeted canonical R1-start assertion | PASS | PASS | 0 |
| Application admission/fusion/terminal merge checked | no | yes | verified |

Current main analysis processes 39 images in 59.582 seconds; the local run
takes 97.773 seconds including fresh acquisition and verification after initial
hash preparation. Native recognition was not repeated. Prior native-only or
direct-builder runtimes have different workloads, so no speed delta is claimed.

All main states remain unknown: 39 unknown, zero live/spectator/menu. Player-owned
facts remain absent. Fresh geometry succeeds once; effective geometry is valid
on all 39 images, with 38 retained cases. Missing identity evidence remains
explicit: weapon/ammo structure 39, ability structure 16, HP structure 1.
No ownership or geometry policy was relaxed to obtain the system event.

One partial package remains, starting at preparation 3.602669 and ending at
the actual video-duration sentinel 171.019336. That upper bound is not observed
coverage: only declared main windows and native 0–6 seconds were processed.
HUD/visual confidence and timeline completeness remain zero with the missing
interval explicit. There are zero state snapshots, so this test does not claim
resolution of snapshot or owned-fact assertions.

The generic no-assurance constructor's qualification diagnostic is retained;
actual source-assured admission separately succeeds with the correct contract.
No source contract is automatically applied to another video.

## Tests and remaining blockers

No production code changed. Fresh actual HUD/visual processing, decoded pixel
identity, native event replay/admission, exact trace contract, package schema,
targeted canonical acceptance and terminal source/profile/code/qualification
checks pass. Validation assertions, schema and evaluator hashes remain unchanged.
Prior current-code regression remains 2740 passed / 6 skipped; Ruff and mypy PASS.

This is not canonical sampled/full E2E and does not update the adopted
23 PASS / 55 FAIL / 4 NE. Full-video negative assertions, discontinuity outcomes,
R2-end absence, Windows execution and continuous R1→R2 rearm are unverified.
Result/score component admission does not supply the missing `ui_end_transition`
qualification. Do not manufacture independent temporal end cases from one
known source episode or enable a default lifecycle bundle prematurely.

Machine-readable evidence:
`e2e_reports/match_001/qualified_r1_start_application.json`.
Actual local application result, trace, packages and evaluation:
`outputs/recognition-investigation/qualified-r1-start-application-20261013/`.
