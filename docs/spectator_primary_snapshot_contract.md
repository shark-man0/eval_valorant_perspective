# Spectator primary-state snapshot contract

## Problem / target

`GT-R1-SNAP-7425` requires `spectator_primary_state=false`. The producer already
has a primary-state enum, but the native snapshot/trace lacked this explicit
field. The assertion also needs a matching admitted snapshot, HP/location and
muzzle evidence; adding the field alone cannot make it PASS.

## Contract change

The shared HUD model exposes a nullable boolean from the established source
observation. It uses the existing 0.65 snapshot admission confidence floor:
accepted `spectator_first_person` maps to true; `live_first_person` with explicit
current player-specific HUD validity maps to false. Unknown, other views,
insufficient confidence and live without identity validity map to null. Absence
of a spectator flag does not prove exclusion. This does not classify pixels,
change primary state, alter thresholds or confer player ownership.

RoundPackageBuilder carries the field in native snapshots and includes it in
snapshot deduplication so a state change with identical values is preserved.
The production package schema adds an optional boolean/null property; existing
packages remain valid. The trace adapter verifies a new native field against
its exact source observation and rejects disagreement. Legacy packages derive
the same field from their existing source observation. GT, Validation Pack and
assertion semantics are unchanged. No HP/name/weapon values are invented.

## Tests / evidence

61related unit/E2E-adapter tests pass in26.39sec, with the actual external
validation-pack path configured (no skipped missing-pack test). Ruff passes;
mypy passes on121source files. Tests cover live/spectator/unknown, low confidence,
identity-invalid live, unchanged player facts, native package schema, state-change
deduplication, trace transport and rejection of contradictory native fields.

Saved full-profile13 raw observations are passed through the current trace
adapter and the unchanged canonical evaluator. The archived original trace is
evaluated with the same evaluator for comparison. Original raw/trace input hashes
are rechecked. This is a saved-source compatibility replay, not new recognition,
independent holdout, a new native full run or proof that the lifecycle gate passed.

| Metric | Previous | Current | Delta |
| --- | ---: | ---: | ---: |
| PASS | 23 | 23 | 0 |
| FAIL | 55 | 55 | 0 |
| NE | 4 | 4 | 0 |
| Snapshots | 919 | 919 | 0 |
| Explicit spectator primary field | 0 | 919 | +919 |
| Negative assertion failures | 0 | 0 | 0 |

All82assertion statuses are identical. Twenty negative assertions remain PASS
in this archived trace replay. The field is false on455live snapshots, true on
163spectator snapshots and null on301other-view snapshots. It does not increase
state recognition coverage or establish new canonical acceptance. Replay of both
traces and report generation takes9.394810sec; no comparable previous runtime is
available. New full E2E Current/Delta remains unavailable.

Artifacts: `e2e_reports/match_001/spectator_snapshot_archived_trace.json` and
`spectator_snapshot_archived_evaluation.json`. Production code changes invalidate
historical code-bound qualifications; no report is re-signed or qualification
fabricated. Windows hardware execution remains unverified.

## Remaining blockers / next action

`GT-R1-SNAP-7425` still lacks an admitted snapshot and muzzle/owned-field evidence;
no assertion is marked solved. Other missing fields (reload, spectated name,
nonself killfeed) need their own qualified source contracts, not aliases inferred
from missing values. Round lifecycle/qualification remains the largest upstream
blocker. Complete independent temporal qualification and independently justified
end timestamp semantics before gated targeted/sampled/full lifecycle acceptance.
