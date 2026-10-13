# Guarded end detector: existing continuous negative controls

## Problem, root cause and target

`GT-R1-ROUND-END` and `event_count_constraints-002` require trustworthy end
evidence without false boundaries during menu or ordinary play transitions.
The guarded result reference preserves the R1 end pattern, but that positive
window alone cannot demonstrate rejection of unrelated UI. Replay the existing
reviewed menu-entry and later active-play windows under the guarded profile and
current shared producer code before considering lifecycle qualification.

## Evidence and change

No production change. Use all 27 native frames in the 83.2–83.65-second menu
window and all 72 frames in the 130.0–131.2-second active window. Every image
decodes to its original recorded pixel hash, with original native PTS, time
base, epoch and cadence. Lossless archive PNG reencoding is recorded explicitly.
Use an actual newly decoded startup image for geometry-only calibration. Its
observations do not enter the control sequence or numeric/temporal evidence.

Run the actual `observe_native_system_frames` API with UI measurements enabled.
Preserve the unqualified measurement namespace and empty production
`system_evidence`. The diagnostic end collector uses the measured signals only
after source/cadence checks; reset on discontinuity. It makes no active-round,
formal-event or ownership claim. Retain NCC 0.90, minimum temporal support
0.05 seconds and the one-second association horizon.

## Previous / Current / Delta

Previous values come from the original-profile historical control diagnostic;
current values come from fresh guarded-profile production recognition of the
same decoded images. Code/profile and acquisition paths differ, so runtime
differences are observations rather than speed claims.

| Metric | Menu previous | Menu current | Delta | Active previous | Active current | Delta |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Native frames | 27 | 27 | 0 | 72 | 72 | 0 |
| Accepted timers | 26 | 26 | 0 | 64 | 64 | 0 |
| Complete score pairs | 27 | 27 | 0 | 27 | 27 | 0 |
| Result matches | 0 | 0 | 0 | 0 | 0 | 0 |
| Unqualified end patterns | 0 | 0 | 0 | 0 | 0 | 0 |
| Released events | 0 | 0 | 0 | 0 | 0 | 0 |
| Producer runtime, seconds | 66.943 | 55.743 | -11.200 | 156.645 | 110.209 | -46.436 |

Menu state remains 13 unknown / 14 buy-menu-open; active state remains 72
unknown. Current pending-end frames, source breaks and player-owned facts are
all zero in both windows. Current complete diagnostic wall time is 181.176
seconds, including prefix decode and terminal verification after the initial
source preparation. No unknown values were filled, and no menu observations
were promoted to live or owned facts.

## Conclusion and tests

These two existing controls show no result false positive or end-pattern
regression under the guarded profile. Terminal archive/input/profile/code and
source-video hashes verify. Recognition ran once per window, sequentially,
with output redirected to a log and silent blocking completion.

No source code changed. Existing current-code regression evidence remains
2740 passed / 6 skipped, Ruff PASS and mypy PASS. Do not repeat that long suite
for documentation and diagnostic artifacts alone. JSON integrity and
`git diff --check` are checked for this addition.

## Remaining blockers and next action

Neither these controls nor the positive end replay supplies a qualified
whole-match lifecycle. These are previously reviewed source windows, not new
blind negatives. The 130-second window does not prove absence of a false R2
end throughout the remaining video. Zero local source breaks does not prove
canonical discontinuity safety. Whole R1-start → R1-end → preparation → R2-start
association remains unverified under the current guarded profile.

Existing `UneditedRoundLifecycle` already resets pending end evidence on
confirmed/candidate starts and source breaks, resets the start latch after a
qualified end, and represents subsequent preparation as
`next_round_preparation`. Strict mode requires qualification and a preceding
active start. Practical mode may collect an independently evidenced end from
a mid-round recording without inventing a start. Reuse these paths; do not
create a second state machine or splice isolated windows into one epoch.

Next release work is component/temporal qualification on the same current
profile/code, followed by genuine continuous lifecycle verification. Formal
event count remains zero. No canonical E2E was run; last adopted status remains
23 PASS / 55 FAIL / 4 NE, with no new assertion claimed PASS. Current Windows
execution remains unverified.

Machine-readable comparison:
`e2e_reports/match_001/result_guard_end_controls.json`.
Source-bound rows and terminal hashes:
`outputs/recognition-investigation/result-guard-end-controls-20261013/`.
