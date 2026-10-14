# Full E2E candidate after qualified lifecycle integration

## Problem, execution and evidence

After fixed targeted/continuous source verification, sampled improvement and
3646PASS/5SKIP full regression, run the shared Python full E2E once with an
isolated clone of the candidate profile and its explicit SHA-bound source
contract. The clone's layout/template/reference bytes and fingerprint remain
unchanged. Default profile/settings are not replaced.

Use privateTesseract5.3.4 for the entire process. Native collection is freshly
executed through Strict raw replay over the complete physical source; no
recognition cache from the missing-OCR environment is consumed. Existing adaptive
full sampler, Validation Pack, GT, assertion evaluator and safety thresholds stay
unchanged. Parent/native locks prevent concurrent full workloads. Wait silently
to process exit, then inspect terminal summaries once.

The analyzer finishes with `status: complete`, schema-valid output and verified
terminal source/code/profile/pack/artifact hashes. Exit1 is canonical evaluation
failure, not an analyzer crash. Raw/trace/evaluation/runtime artifacts are retained.

## Previous / Current / Delta

| Metric | Adopted baseline | Candidate | Delta |
| --- | ---: | ---: | ---: |
| Semantic assertion PASS | 23 | 28 | +5 |
| Semantic assertion FAIL | 55 | 50 | -5 |
| NE | 4 | 4 | 0 |
| Formal starts | 0 | 2 | +2 |
| Formal ends | 0 | 1 | +1 |
| Packages | 1 partial | 2 | +1 |
| Negative assertion failures | 0 | 0 | 0 |
| Source-break span violations | 0 | 0 | 0 |
| Processed main frames | 4634 | 6614 | +1980 |
| Unknown | 3715 | 5588 | +1873 |
| Live | 455 | 511 | +56 |
| Buy menu | 301 | 306 | +5 |
| Spectator | 163 | 209 | +46 |

The sampler algorithm is unchanged, but its inputs include newly detected native
boundaries and candidate numeric observations, increasing adaptive coverage.
State counts/unknown ratios therefore compare different frame populations and
are not evidence of improved or degraded classification by themselves.

Five FAIL→PASS IDs: `GT-R1-ROUND-START`, `GT-R2-ROUND-START`,
`event_count_constraints-000`, `event_count_constraints-002`,
`event_count_constraints-004`. No old PASS becomes FAIL/NE. All82records are saved;
this does not mean the29old package-scope failures are solved.

Starts retain4.102669/111.419336seconds; R1end retains74.486003, with its later
confirmation75.369336. Actors are system and all provenance survives. R2 end
and duplicate boundaries are absent. R1-end point stays FAIL because it is
approximately0.003003seconds outside the fixed window ending74.483. Ordering
remains NE; no time is rounded/backdated to meet GT.

Two package contexts: R1[3.602669,81.752669],307snapshots; open R2
[110.986003,171.019336],413snapshots. The upper sentinel is not an R2 end.
Initial and source-break/inter-round context remains unassigned in Strict mode;
Practical unknown fragments are a separate retention mechanism.

HUD produces three lifecycle events. One visual `movement_state` event at
140.052669 reports stationary with confidence0.86; no shot/death is invented.
Fresh geometry1/effective6614/retained6613. Live identity insufficient5473;
missing ability3603,weapon3653,HPstructure1201. Geometry is not automatically
declared the cause of these failures.

## New confidence contract blocker

Overall canonical `pass` is **false**. In addition to semantic FAIL, it reports
720`confidence:snapshots:N:source_confidence` errors. The diagnostic confirms
2636native per-field confidence leaves are valid, with zero invalid leaves;
all720maps are rejected because the canonical top-level `*_confidence` convention
expects scalars. Native package `source_confidence` is a typed per-field map,
which the current trace adapter copies verbatim into that reserved scalar name.

The82-status reporter intentionally separates these global confidence errors
from individual semantic predicates. **28PASS is not an overall evaluator PASS
or adoption approval.** Do not suppress evaluator checks, change the pack,
discard native provenance or install the Match002-specific confidence evaluator
for Match001. Next resolve the trace serialization contract while preserving
the native field map and unchanged canonical scalar validation.

## Runtime and bottlenecks

Recorded full wall37806.726seconds (10.502hours),main-frame rate0.17494/s.
Previous full was12995.97seconds (3.610hours). The new complete native source
pass, additional numeric readers and changed main-frame population make this
runtime comparison unlike a speed benchmark. This candidate is only for final
evaluation; fixed sampled comparison remains roughly3.5minutes per profile.

| Profiling stage | Total seconds | Calls | Average seconds | Wall share |
| --- | ---: | ---: | ---: | ---: |
| HUD geometry/features | 11837.996 | 35805 | 0.330624 | 31.31% |
| Spectator detection | 7159.858 | 17901 | 0.399970 | 18.94% |
| Numeric/OCR readers | 6975.328 | 17901 | 0.389661 | 18.45% |
| Native lifecycle residual | 5233.890 | 1 | 5233.890 | 13.84% |
| Identity detection | 1535.309 | 71604 | 0.021442 | 4.06% |

Stage accounting includes native and main visits and subtracts measured child
stages; native residual is not the total collection elapsed time. Geometry/features
is not a measurement of anchor search alone. No thresholds or frame rate are
lowered to reduce these costs.

## Adoption and next work

Keep the adopted baseline23/55/4. Candidate28/50/4 is a successful source/pipeline
experiment with five semantic gains, but confidence serialization and full numeric
evidence review remain open. Labelled sampled wrong0 does not prove every accepted
full OCR value correct. Independent temporal generalization and current branch
Windows CI are also incomplete.

Next: normalize the native-map→canonical-scalar trace contract without changing
recognition or assertions, re-adapt the hash-bound saved raw result where safe,
then investigate source-derived end-time semantics and classify the remaining50
semantic failures against current actual package membership. Avoid repeating
the10.5hour recognizer run for evaluator-only work.

Machine-readable full82outcomes and all terminal hashes:
`e2e_reports/match_001/strict_replay_full_candidate.json`.
Local complete artifacts:
`outputs/recognition-investigation/strict-replay-full-20261014/run/`.
