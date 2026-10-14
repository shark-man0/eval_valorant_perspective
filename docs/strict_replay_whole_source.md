# Whole-source Strict application replay entrance

## Problem and change being verified

Earlier whole-source experiments called the native analyzer directly. The shared
application collector rejected replay storage in Strict Mode. After permitting
explicit bounded replay without changing qualification, verify the actual
`HudVideoProcessor.collect_native_lifecycle(..., boundary_mode="strict")` entrance
on the entire physical source through EOF.

Use the freshly reverified experimental six-component admission bundle and the
explicit SHA-bound match001 input contract. Neither is installed by default.
No GT, external system proof, frame skipping, threshold change or sampled fallback
is supplied. One FullRunLock excludes another full workload. All code/profile/
input/source hashes remain unchanged through decode, collection and publication.

## Evidence

Source: 10259 native frames, first tick553, last2626601, cadence256 with timebase
1/15360. Read and verify every frame, including the two repeated raster breaks.
The existing decoder retains at most its bounded raw cache, configured with
64MiB; no whole-video PNG collection is created.

| Event | Boundary | Confirmation | Confidence | Segment |
| --- | ---: | ---: | ---: | ---: |
| R1 start | 4.102669 | 4.202669 | 0.911719 | 0 |
| R1 end | 74.486003 | 75.369336 | 0.919552 | 0 |
| R2 start | 111.419336 | 111.486003 | 0.900047 | 2 |

All actors are system. Source breaks at81.786003 and81.836003 remain resets,
not game-round boundaries. R2 is established from its own preparation after
these resets. R2 end is absent through EOF; duplicate boundaries are zero.
Owned-fact promotions remain zero. The global stream retains current context
states:8676 unknown,680 live,579 buy menu,324 spectator, without player attribution.

The application collector verifies current qualification before and after the
configured provider, every source row's exact binding and coverage, decoder
terminal checks and native event replay before returning. Only after successful
context exit are results published.

## Package, trace and evaluation

Feed the returned native-only observations/events to the current public builder
and trace adapter. Two schema-valid packages result: R1 context3.602669–81.769336
and open R2 context110.986003–171.019336. Actor/time/type/confidence/provenance
survive unchanged. The final endpoint is a duration sentinel, not an R2 end.

The unchanged canonical evaluator on this **native-only trace** returns27 PASS /
51 FAIL /4 NE; all20 negative assertions pass. This is not the standard full E2E
or an adopted baseline. Main sampled HUD/visual analysis, owned facts and their
merge were not run here. Keep the standard baseline23 PASS /55 FAIL /4 NE.

R1-end point remains FAIL because74.486003 is0.003003 seconds outside the fixed
window ending74.483. End-count PASS is distinct from point-window PASS. Ordering
remains NE and the native-only live snapshot705 remains absent. Neither the
point time nor snapshot is repaired to meet GT.

## Previous / Current / Delta

Compared with the pre-main direct-native experiment on the same physical source:

| Metric | Previous direct producer | Current application collector | Delta |
| --- | ---: | ---: | ---: |
| Frames | 10259 | 10259 | 0 |
| Starts | 2 | 2 | 0 |
| Ends | 1 | 1 | 0 |
| Packages | 2 | 2 | 0 |
| Native-only PASS / FAIL / NE | 27 / 51 / 4 | 27 / 51 / 4 | 0 / 0 / 0 |
| Wall-clock, seconds | 19703.275 | 19413.335 | -289.940 |

Entrances and code fingerprints differ, so the runtime arithmetic is **not a
speed-improvement benchmark**. The new evidence is the real Strict application
entrance successfully completing source-owned collection, not increased PASS.
Collector time19410.573s; recorded collection-stage wall-clock19413.335s
(5.393 hours). Package/trace/evaluator diagnostics run afterward.

## Remaining gates

Current fingerprint96c79de… is verified. The six-component audit still relies
on one exposed result episode; this run does not create independent training/
holdout temporal cases or final qualification. Do not promote it to default
release. Next run the fixed sampled main HUD/visual merge using only this exact
fresh native output under identical fingerprints, then eligible full regression
and standard full E2E. Preserve unknown initial/inter-round context separately;
do not label it R2 by adjacency. Windows CI for the dirty storage changes remains
pending. No parallel full E2E or new standard full E2E was launched here.

Full82-outcome machine record:
`e2e_reports/match_001/strict_replay_whole_source.json`.
Local complete producer/collector outputs:
`outputs/recognition-investigation/strict-replay-whole-collector-20261013/`.
