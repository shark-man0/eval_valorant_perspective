# Native field confidence and canonical scalar trace contract

## Problem and evidence

The completed full candidate contains720snapshots with valid native
`source_confidence` maps. Canonical v3 checks top-level confidence-named fields
as finite scalar numbers, producing720shape errors despite all2636map leaves
being valid. This is an adapter representation mismatch, not a reason to change
validation rules, omit confidence or apply Match002's versioned evaluator to
Match001.

## Contract change

Keep native packages, SQLite, FactBuilder and production behavior unchanged.
In the shared E2E trace adapter:

- Preserve the complete original map in `source_confidence_by_field`.
- Encode the reserved scalar `source_confidence` as the minimum of its field
  confidences, or0for an empty/unknown support map.
- Reject non-map native support, empty/non-text field names and any nonnumeric,
  boolean, nonfinite or outside-[0,1] leaf. Relocation never hides invalid support.
- Do not raise any field's confidence, change observed values, modify ownership
  or mutate native input. Preserve map ordering/content in the copied structure.

The scalar is a conservative summary of recorded field support, not a new
probability or evidence gate. Native scoring still consumes its unchanged map.
Legacy snapshots without source confidence retain their previous representation.
The existing trace schema allows these additive fields; schema/pack/assertions
and canonical evaluator are unchanged. Reserved scalar validation still rejects
injected invalid trace scalars.

## Tests

Related trace/clock-fusion/source-membership/confidence tests: **50PASS in14.71s**.
Verify independent native-map copies, conservative minimum, unknown-empty0,
invalid leaves/names/types, unchanged source-clock and snapshot-owner protections,
canonical validation and direct legacy-map rejection. RuffPASS; mypy131filesPASS.
The first new test used an invalid `hud_confidence` boolean and correctly failed
schema validation before evaluator execution. Correct the test to inject an
unlisted reserved source scalar, confirming canonical rejection rather than
mistaking schema rejection for relaxed behavior. Preserve the initial test log.

## Evaluation-only replay and Previous / Current / Delta

Verify every terminal artifact hash from the completed full run, then re-adapt
its saved native raw with the updated adapter. Original raw, trace/evaluation,
source/profile/recognizer outputs and native map contents are unchanged. Store
the new trace/evaluation separately. No frame recognition or new full run occurs.

| Metric | Original full trace | Re-adapted trace | Delta |
| --- | ---: | ---: | ---: |
| Confidence shape errors | 720 | 0 | -720 |
| Total failure messages | 779 | 59 | -720 |
| Semantic PASS | 28 | 28 | 0 |
| Semantic FAIL | 50 | 50 | 0 |
| NE | 4 | 4 | 0 |
| Negative assertion failures | 0 | 0 | 0 |

All82assertion results are identical, including failure strings. All nonconfidence
snapshot fields and every other trace group are exactly equal. All720native maps
are retained exactly. Remaining failure messages are exactly the original messages
excluding the corrected representation errors; no semantic failure disappears.
Canonical overall pass remains false because real recognition/association/event
failures remain.

Adaptation1.801seconds; adaptation plus unchanged evaluator6.969seconds. This
reuses terminal-hash-verified raw instead of repeating10.5hours of recognition.
The global recognizer fingerprint stays96c79de…; E2E adapter/orchestration hash
changes and is recorded separately. This is not a new canonical full execution
or an adopted profile release.

## Remaining work

Reclassify the current50semantic failures against actual two-package scope,
investigate source-derived end timing without GT backdating, and review newly
accepted full numeric/owned facts. Current dirty branch WindowsCI/full regression
after this adapter change remain pending. Adopted23/55/4 is retained until the
candidate satisfies its outstanding review/qualification gates.

Machine-readable record: `e2e_reports/match_001/trace_confidence_contract.json`.
Local normalized trace/evaluation:
`outputs/recognition-investigation/trace-confidence-contract-20261014/`.
