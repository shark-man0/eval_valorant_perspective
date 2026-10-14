# Fresh source evidence after Strict storage integration

## Problem and method

Storage integration changes the recognizer fingerprint, invalidating previous
qualification. Re-run the frozen source-reviewed static and continuous cohorts
through current production readers, then build support from fresh outputs and
original labels. Preserve all training/holdout/negative splits and prior exposure.
No reference fitting, new blind-cohort claim, threshold or GT changes.

Fingerprint:
`96c79de983a298b1f849c742c9653728c527481d929e2991b6e6f918dfe95da5`.
Video SHA remains `71d58558…`; local manifests and terminal hashes bind full SHA,
profile, code, input images and source PTS.

## Component Previous / Current / Delta

| Source-reviewed metric | Previous | Current | Delta |
| --- | ---: | ---: | ---: |
| Timer correct / unknown / wrong | 25 / 7 / 0 | 25 / 7 / 0 | 0 / 0 / 0 |
| Score field correct / unknown / wrong | 36 / 18 / 0 | 36 / 18 / 0 | 0 / 0 / 0 |
| Result correct / unknown / wrong | 3 / 8 / 0 | 3 / 8 / 0 | 0 / 0 / 0 |
| Bounded negative-control false accepts | 0 | 0 | 0 |

Phase counts: 3 training matches, 8 holdout matches and 12 negative rejections.
Fresh 162-frame start/control, 108-frame end and 99-frame end-control production
replays retain the previous candidate times and bounded negative results. The
actual loader admits all six components in the newly reviewed offline audit.
End support still represents one exposed episode, not independent temporal
generalization or a default release. Start qualification is separately limited
to timer, purchase phase and UI transition.

## Real native → application → package → trace

Freshly decode the continuous physical source origin through 6 seconds (358
native frames). Run the actual qualified source-assured native producer with the
new start-only bundle: one system start at **4.102669**, confirmed at **4.202669**,
confidence **0.911719**. No end or duplicate start. All source images remain
unknown for player-owned validity; no HP, weapon, death or shot is attributed.

Pass only that unchanged fresh native output into the real HudVideoProcessor
alongside another fresh decode of **all 358 main frames** over the same interval.
Every main raster matches the native source pixel hash. Real HUD/visual analysis,
native merge, package builder, trace adapter and terminal verification execute.
One start reaches the trace with actor/time/type/confidence/attributes intact;
visual events remain zero. No native proof is reconstructed from diagnostic
measurements.

The unchanged canonical evaluator reports **GT-R1-ROUND-START PASS**. This is a
bounded source acceptance test, not a new standard full E2E result. The earlier
application run used only 39 main frames; this run uses a complete continuous
358-frame interval, so their timings are not comparable speed measurements.

| Stage | Frames | Processing time | Recorded wall-clock |
| --- | ---: | ---: | ---: |
| Qualified native producer | 358 | 622.277s | 816.856s |
| Real HUD/visual application | 358 | 533.342s | 727.848s |

The open package keeps timeline completeness 0 and no snapshots. Its upper
storage sentinel is source duration 171.019336, **not** observed coverage after
6 seconds or an inferred end. Initial context before 3.602669 still requires
separate practical unknown-fragment retention/association. Do not score a full
round from this incomplete package.

## Limits and next work

This real R1 test uses the existing **PNG-backed 0–6 source window**. It proves
current-code qualification and actual application merge, not whole-source Strict
raw replay collection on real video. That new storage entrance is currently
covered by synthetic qualified/provider/decoder tests. Do not conflate them.

R1-end/R2-start patterns in separately replayed windows do not prove a current
whole-source active/end/rearm path. Their six-component offline admission is not
independent temporal qualification. No default bundle is installed. No independent
point truth is supplied here for a separate ±0.1-second certificate; the strict
acceptance-window PASS and practical point-error metric remain distinct.

Adopted baseline remains **23 PASS / 55 FAIL / 4 NE**. Whole-source Strict replay
application, sampled/full eligibility, remaining context association, full
regression and Windows CI for the dirty storage change remain pending. The
goal is active; no git commit or push is performed in this phase.

Machine-readable record:
`e2e_reports/match_001/strict_replay_source_verification.json`.
