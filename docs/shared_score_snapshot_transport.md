# Shared score snapshot transport

## Problem and target assertions

The trace adapter exports team scores inside its identity-valid self-HUD branch.
Native snapshots have no corresponding team-score fields. This prevents already
accepted global score pixels from surviving as source-backed facts independently
of player identity. Initial targets include the score predicates of
`GT-R1-SNAP-0415` and `GT-R2-SNAP-11145`; their other predicates and package scope
remain separate requirements, so this change does not guarantee a PASS.

## Evidence and root cause

The current saved R1end producer output has108native rows. Reserved value-reader
confidence>=0.90supports53ally and61enemy scores;67identity-unknown rows have at
least one such score. These are existing development predictions, not a fresh
reader qualification or an independent holdout. Existing snapshot admission
rejects all108rows, so this source window produces0native snapshots even after
the new transport. The missing native/trace contract and admission are distinct
blockers; ownership cannot be used to infer global numeric correctness.

## Change and evidence contract

`shared_score_evidence` preserves an original nonnegative integer only when its
reserved `score_ally_value` or `score_enemy_value` reader confidence is finite and
at least0.90and the source has no reported occluded ROI. Each side is checked
independently; an unknown side is not filled from history or its neighbor.
Geometry/general ROI confidence cannot substitute for value-reader provenance.
Player identity does not enter this global evidence rule. This helper cannot
authorize round boundaries or player-owned HP/weapon/death/shot facts.

Native snapshots add nullable `score_ally` and `score_enemy` and preserve their
original reader confidence in `source_confidence`. Snapshot deduplication includes
both scores, retaining short observed changes. The additive native schema accepts
these fields and confidence entries. Existing HUD snapshot admission is unchanged.

The trace maps accepted native ally score to `score_player` (the existing
POV-team alias), and enemy score to `score_enemy`, independently of ownership.
It rejects a new native/source value or confidence disagreement. Explicit nulls
cannot be overwritten through the old self-HUD alias branch. Archived snapshots
without the new fields retain compatibility; a source's explicit accepted value
can be transported without fabricating identity. This is a team score, not a
player's personal performance statistic. No original source observations change.

## Tests

113related tests PASS in two disjoint groups:70tests in36.19seconds and43builder/
schema/source-confidence tests in26.92seconds. Cases include weak/missing/generic
confidence, bool/NaN/infinite values, invalid integers, occlusion, identity-unknown
transport, deduplication, schema validation, value/confidence mismatch and no
owned-fact promotion. Ruff onsrc/tests/scripts/e2ePASS; mypy121source filesPASS.
The full repository suite was not rerun for this change.

## Previous / Current / Delta

Archived full raw output is replayed through the current adapter and the unchanged
canonical evaluator. All82assertion results are exactly equal to the archived
evaluation, including the negative assertions. This is compatibility validation,
not recognition on new frames or a new full E2E.

| Metric / scope | Previous | Current | Delta |
| --- | ---: | ---: | ---: |
| Archived canonical PASS | 23 | 23 | 0 |
| Archived canonical FAIL | 55 | 55 | 0 |
| Archived canonical NE | 4 | 4 | 0 |
| R1end admitted native snapshots | 0 | 0 | 0 |
| New canonical full E2E | Not run | Not run | Unavailable |

Offline transport/evaluator replay takes6.441925seconds; no comparable previous
runtime is claimed. Actual full baseline remains12995.97seconds, with no new
measurement. Machine evidence is `e2e_reports/match_001/shared_score_snapshot_transport.json`.

## Remaining blockers

Define an explicitly qualified global snapshot admission path, separate from
player-owned snapshot admission. High reader confidence alone is not independent
qualification. Keep current HUD/identity/ownership conditions, minimum support,
negative controls and training/holdout separation. Complete source-assured start
temporal qualification before releasing actual lifecycle events. End result
generalization and timestamp semantics remain unresolved. Neither assertion
target is newly PASS. No Validation Pack, assertion, sampler, threshold, geometry
or ownership policy changes; no full E2E was warranted at this stage.

Shared production changes invalidate historical code-bound qualification; no
historical report is re-signed. Windows hardware remains unverified.
