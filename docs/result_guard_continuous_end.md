# Result guard on the continuous R1 end window

## Problem and target

`GT-R1-ROUND-END` and `event_count_constraints-002` need source-backed end
evidence. The optional glyph contrast guard rejects a demonstrated added-stroke
confusable, but static crops do not establish continuous boundary behavior.
Check whether the stronger result predicate delays corroboration beyond the
existing one-second association horizon. Do not extend that horizon or move the
boundary timestamp to fit an assertion.

## Evidence and method

Replay all 108 native frames in the existing 74.2–76.0-second window through
the actual shared `observe_native_system_frames` API, once per profile,
sequentially. Compare the original late-result profile and its opt-in contrast
guard variant under the same current production code. Preserve native cadence,
source PTS, time base, epoch and pixel hashes. Every archived PNG decodes to its
original recorded pixel hash; its encoded PNG bytes were reencoded losslessly.
Archive names start at `frame_01.png`, not `frame_00.png`. Earlier filename
probes were invalid; the verified mapping covers all 108 images.

Decode the source startup image separately for geometry-only calibration.
It supplies no timer, score, phase or temporal observation. Source video SHA,
input-contract assurance, archive hashes, profile fingerprints and code
fingerprint all verify again after processing. No retained-geometry policy or
recognition threshold changes.

Keep native measurements unqualified. A standalone `UneditedUiEndTracker`
collects a diagnostic pattern after source/cadence checks and resets on source
breaks. This diagnostic does **not** claim a preceding active round, authorize
an event, create a qualification or establish whole-match lifecycle/rearm.
The actual transport's `system_evidence` remains empty.

## Continuous result

| Metric | Previous profile | Guarded profile | Delta |
| --- | ---: | ---: | ---: |
| Processed native frames | 108 | 108 | 0 |
| Accepted timer readings | 17 | 17 | 0 |
| Accepted complete score pairs | 47 | 47 | 0 |
| Result matches | 29 | 29 | 0 |
| Unqualified end patterns | 1 | 1 | 0 |
| Pattern boundary time | 74.486003 | 74.486003 | 0 |
| First result support | 75.319336 | 75.319336 | 0 |
| Result confirmation time | 75.369336 | 75.369336 | 0 |
| Pattern confidence | 0.924868 | 0.919552 | -0.005316 |
| Detected source breaks | 0 | 0 | 0 |
| Released formal events | 0 | 0 | 0 |
| Player-owned facts | 0 | 0 | 0 |
| Analyzer runtime, seconds | 234.542 | 232.851 | -1.691 |

Runtime changes by -0.72% in this one sequential pair; this does not establish
a speed improvement. Native processing totals 467.394 seconds, excluding
source hashing, prefix decode and finalization. All timer displays, numeric
values and display provenance match between profiles, including unknowns.
All guarded result matches were also original-profile matches.

The observed clock changes from `0:29` to `0:06` at 74.452669 seconds. The
accepted score pair changes from `[0,1]` to `[0,2]` at 74.486003 and stabilizes
at 74.536003. Result support begins at 75.319336 and reaches the unchanged
0.05-second support duration at 75.369336, 0.916667 seconds after the clock
change. The boundary candidate retains the first observed score-change time;
the later confirmation does not replace it. Missing current score readings at
confirmation remain missing, with prior accepted evidence explicitly retained
as history rather than filled into current facts.

## Competing hypotheses and decision

The stronger glyph predicate could have delayed or interrupted the result run,
making this end pattern expire. It did neither on these 108 actual native
images: the same 29 result matches and same confirmation time survive. Static
JPEG holdout counts do not predict native temporal timing; preserve both
results without substituting one input for the other.

The other hypothesis is that a surviving pattern is already a qualified round
end. That claim is unsupported. Component and temporal qualification remain
incomplete, and this collector has no active-round claim. Keep the pattern
diagnostic and preserve the strict release gate.

## Contract and tests

No production code changed during this replay. The already completed
current-code regression remains 2740 passed, 6 skipped; Ruff and mypy passed.
Do not rerun the full suite solely for diagnostic/documentation changes.

Both recognition passes finished, but the initial final comparator indexed the
optional timer display field when it was absent on an unknown reading. Preserve
that failure log. A separate finalizer compares optional fields using `get`,
checks the saved source-bound rows and performs terminal input/video/profile/
code hash verification. Recognition was not repeated. The diagnostic script
was corrected for future use; no production behavior was changed.

## Canonical result and remaining blockers

Canonical full E2E was not run: release qualification and the whole continuous
R1-start → end → R2-start path have not passed. Last adopted canonical status
remains **23 PASS / 55 FAIL / 4 NE**; no new assertion is claimed PASS. Canonical
negative/discontinuity regression counts are unmeasured by this diagnostic.
Zero source breaks here is a local observation, not a whole-match safety result.

The first observed score change is 0.003003 seconds beyond the unchanged strict
R1-end acceptance window. Do not round, backdate to the earlier clock change,
or alter the validation pack. The separate ±0.1-second practical accuracy
criterion does not grant strict acceptance, and this replay does not establish
an independent point-GT accuracy qualification.

Next work is current-code component/temporal qualification with preserved
training/holdout/negative exposure and whole-lifecycle association. This existing
single-source reviewed window is not a new blind cohort. End controls and
R1-to-R2 rearm still need current guarded-profile verification. Current Windows
execution is unverified.

Machine-readable evidence: `e2e_reports/match_001/result_guard_continuous_end.json`.
Full local source-bound rows, plans, preserved failure log and final hash audit:
`outputs/recognition-investigation/result-guard-continuous-end-20261013/`.
