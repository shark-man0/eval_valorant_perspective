# Current continuous native UI start replay

## Problem and source coverage

Static timer/phase tests do not qualify temporal boundaries. Replay the previously
frozen5native windows through the current shared analyzer and existing
UneditedUiStartTracker. Targets remainGT-R1-ROUND-START,GT-R2-ROUND-STARTand
related count/ordering constraints. All162suffixframes retain exact cadence
256ticks at1/15360, source epoch, SHA, pixel/encoded identities. No sampler,
threshold, reference, assertion or production code change.

## Cold-entry evidence

Starting a new analyzer directly at each short window yields only1accepted
initial anchor. Existing calibration policy rejects all5initializations, making
all162phase scans invalid and all timer valuesunknown. The tracker correctly
remainsunobservedand emits0candidates. This is a short-window initialization
failure, not evidence that geometry causes29or55full-runFAILs. The historical
full source had valid retained geometry after its startup frame.

## Source-initialized development replay

Use the actual decoder-owned startup image atPTS553/15360=0.036002604as the
first analyzer observation before each suffix. Existing anchor matching accepts
4anchors; no injected positions, confidence, fake CalibrationResult or geometry
policy changes. Current shared analyzer then processes every native suffix
frame with events disabled. The native system projection strips all player-owned
values and retains source PTS. Frame indices are rebased to suffix-relative
bookkeeping only; no timestamp/image/event is substituted.

The UI tracker is newly initialized for each suffix and receives no startup row
or cross-gap continuity proof. The analyzer itself sees the startup observation
and gap, so its contextual outputs can affect initial suffix observations. This
common initialization input is explicitly hash-bound into the input fingerprint
and reported as shared between windows. This is development replay, not an
independent joint holdout or a production qualified entrance. It cannot prove
R1end→R2rearmbecause windows are independently initialized.

All162suffix PTS/pixel hashes match cold-entry inputs exactly. Source and terminal
hashes verify. Diagnostic scripts retain raw measured phase flags/scans and
source-break markers rather than assumed valid scans.

## Evidence, candidates and controls

| Metric | Cold entry | Source-initialized | Delta |
| --- | ---: | ---: | ---: |
| Native suffix frames | 162 | 162 | 0 |
| Valid phase scans | 0 | 162 | +162 |
| Accepted timer observations | 0 | 133 | +133 |
| Start candidates in two start windows | 0 | 2 | +2 |
| Start candidates in3control windows | 0 | 0 | 0 |
| Formal HUD events | 0 | 0 | 0 |
| Projected owned facts | 0 | 0 | 0 |

| Window | Native frames | Accepted timers | Start candidate | Later confirmation |
| --- | ---: | ---: | --- | --- |
| R1development | 36 | 36 | 4.102669 | 4.202669 |
| R2development | 36 | 30 | 111.419336 | 111.486003 |
| Active control | 30 | 26 | none | none |
| Menu control | 30 | 30 | none | none |
| Spectator control | 30 | 11 | none | none |

Source review of16transition frames after predictions confirms phase disappears
at the recorded candidates. R1actually displays0:00→2:25→2:25→1:39;
2:25remains in clock-display provenance. Stable clock support begins4.152669and
confirms4.202669; the original phase-disappearance candidate4.102669is retained.
R2phase disappears111.419336, displays1:40then1:39, and confirms111.486003.
No GT timestamp or round ID enters tracker logic. These observations do not
qualify all133accepted timer values merely by their confidence.

No duplicate candidate occurs within either short positive suffix. These are
2source start episodes, not3independent boundary holdout cases. Controls retain
source menu/spectator context and yield no start. This start-only test does not
verify a full lifecycle end, R2endabsence, whole-video duplicates or canonical
negative/discontinuity assertions.

## Runtime and tests

Cold acquisition/analysis/integrity runtime306.288sversus421.970ssource-initialized,
+115.682s/+37.77%; the latter includes a startup source decode and extra analyzer
observations. Same-suffix analysis stages are recorded individually in JSON.
This is an initialization-context comparison, not recognizer speed optimization.
No production/test changes; preceding2690PASS/6SKIP,Ruff,mypyremain the last
code verification. No full E2E or Windows qualification is claimed.

## Remaining blocker and next implementation

A short native entrance needs explicit source-bound initialization support to
reproduce application startup geometry without inventing anchors or carrying
phase/timer/ownership facts across missing context. The default full sampler and
geometry policy must remain unchanged. Current ignored diagnostic callback code
is not a qualified production API and must not become a qualification sidecar
implicitly. Shared initialization and all temporal context must be included in
split/provenance review rather than hidden behind endpoint hashes.

Independent reader/UI joint qualification, valid negative scope, end semantics
and full R1→R2state management remain gates. Both start candidates lying within
historical assertion windows is not a PASS: no formal event or canonical run
exists. Historical82statuses remain23PASS/55FAIL/4NE, Current full/Delta unavailable.

Hash/PTS/measurements, candidate provenance and window comparisons:
[lifecycle_ui_current_native.json](../e2e_reports/match_001/lifecycle_ui_current_native.json).
