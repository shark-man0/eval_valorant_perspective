# Current full-candidate failure classification

## Evidence and status

This supersedes the historical first-blocker table with the completed current-code full run. It does not adopt the candidate as the baseline. Latest main was fetched: `7e480c2f2f7f49aea73e1541d065d78881d2f11c`. Full source execution: `46462336427149764beb8e1fdd94c554e075616e`; production source is byte-identical to S-01 code `6ecab454e35507f1a1e5c677488bb5ece54a7211`. Recognition/profile/qualification, protected assertion/evaluator and terminal artifact hashes are recorded in the sanitized JSON. No source recognition or full rerun is performed by this analysis. The unchanged canonical evaluator reproduces the entire saved 99-message failure list exactly.

| Metric | Adopted | Previous candidate | Current source full |
| --- | ---: | ---: | ---: |
| PASS | 23 | 28 | 28 |
| FAIL | 55 | 50 | 50 |
| NE | 4 | 4 | 4 |
| Negative failures | 0 | 0 | 0 |

All 82 statuses match the historical candidate; adopted PASS regressions = 0. Five candidate improvements versus adopted baseline remain lifecycle assertions, not S-01 accuracy gains. All 20 negative assertions PASS. Full analyzer exit is 0; evaluator exit 1 means semantic failures remain, not a processing crash.

## Exclusive first observed blockers

One assignment per failing assertion. These are blockers, not proven sole causes; multiple secondary predicates can remain. Every guaranteed single-fix PASS gain is currently zero. Snapshot state labels do not imply a particular recognizer correction is sufficient.

| First blocker | FAIL | Share of 50 | Implementation/evidence class |
| --- | ---: | ---: | --- |
| snapshot_current_state_evidence | 15 | 30.0% | source recognition / qualification |
| preparation_scope | 7 | 14.0% | upstream dependency |
| snapshot_player_life_evidence | 5 | 10.0% | source ownership / temporal evidence |
| death_event_contract | 4 | 8.0% | partial implementation |
| remote_state | 4 | 8.0% | recognition failure |
| owned_visual_evidence | 4 | 8.0% | upstream dependency |
| self_ownership | 2 | 4.0% | upstream dependency |
| dead_ownership | 2 | 4.0% | partial implementation |
| map_resolution | 2 | 4.0% | source calibration / assets |
| round_end_time | 1 | 2.0% | partial implementation |
| smoke_state | 1 | 2.0% | recognition failure |
| expanded_map_state | 1 | 2.0% | partial implementation |
| spectator_coverage | 1 | 2.0% | recognition failure |
| teammate_ownership | 1 | 2.0% | upstream dependency |

The old `snapshot_hud_gate = 17` classification is historical. Its present first-blocker count is **0**: qualified global-only snapshots now reach trace. The largest remaining cluster is **15 current-frame state-evidence failures (30%)**. Another five matching snapshots lack player life/death evidence, and two derived snapshots lack map resolution. These numbers describe current failing predicates and cannot be added to the old 17 as new failures.

The preparation first-blocker cluster is now **7**, not 9. The R1 prefix snapshot and its derived location now exist in scope and fail state/life/location evidence instead. Active/post-round R2 failures must not be put back into the historical 29-package cluster. Two early R2 snapshots and their derived location remain outside proven Strict scope; Practical unknown fragments already retain the observations.

## Source and transport audit

Current raw has zero structured killfeed observations and zero combat-report field-reading observations. The absence of victim/killer/damage proof is not a trace adapter dropping an existing qualified death. Remote/expanded-map/smoke failures are source mode/qualification limitations; continuous spectator and self ownership have incomplete coverage. A visible report can persist after respawn. Global timer/score can never promote self-death, shot, weapon, HP or owner.

Missing semantic exports remain **secondary** blockers even where the first predicate is state or life evidence: nonself killfeed visibility, reload animation, muzzle visibility and spectated subject fields. Do not interpret their absence from the exclusive root table as implemented features. FactBuilder already uses per-location source support; the distinct builder-level visual cap is retained, not removed.

The confidence-dedup follow-up independently checked all 357 intermediate suppressed observations and 740 stronger field supports: all already survive final native package and trace. The experimental retention patch was rejected and production restored. See [complete-path audit](s01_snapshot_retention_followup.md). No downstream loss is inferred from an intermediate count.

## Current measured interval coverage

| Assertion | Covered fraction |
| --- | ---: |
| GT-R1-BUY-FLAG | 0.389593 |
| GT-R1-ASTRAL-1 | 0.000000 |
| GT-R1-ASTRAL-2 | 0.000000 |
| GT-R1-SMOKE | 0.000000 |
| GT-R1-COMBAT-REPORT | 0.993571 |
| GT-R2-BUY-FLAG | 0.014082 |
| GT-R2-BUY-MENU-1 | 0.000000 |
| GT-R2-BUY-MENU-2 | 0.000000 |
| GT-R2-ASTRAL-1 | 0.000000 |
| GT-R2-ASTRAL-2 | 0.000000 |
| GT-R2-EXPANDED-MAP | 0.000000 |
| GT-R2-SPECTATOR | 0.291533 |
| OWN-R1-SELF | 0.089225 |
| OWN-R1-SELF-DEAD | 0.000000 |
| OWN-R2-SELF | 0.057927 |
| OWN-R2-SELF-DEAD | 0.000000 |
| OWN-R2-TEAMMATE | 0.284423 |

Ratios are interval-union coverage over the fixed independent evaluator windows, not recognition accuracy or a reduced threshold. Retain the original requirements. The source SHA-specific unedited contract remains active; real capture duplicates/PTS breaks are still respected. Fresh geometry is 1/6614; effective geometry is 6614/6614. No FAIL is proved solely caused by retained geometry, so no geometry threshold is changed.

## Priorities and required evidence

1. Current-frame state/identity proof and independently qualified subject/death evidence are the next producers. Four independent identity structures, spectator-safe controls and source continuity remain mandatory. A self-death fix has four direct FAIL targets plus ordering dependencies, but actor/subject/attributes/temporal proof all must hold; no automatic PASS gain is claimed.
2. The seven preparation blockers require observed uninterrupted same-segment preparation/lifecycle membership. No GT round IDs or source-break bridges.
3. Remote, smoke, expanded map and spectator need qualified discriminative interfaces/current-frame semantics; previously rejected controls are not retried with looser thresholds. Map assertions additionally need actual source-backed map calibration/assets.
4. R1 end timing is separate: the observed end remains at 74.486003, about 3 ms beyond the fixed acceptance window. No timestamp fitting, backdating, window change or new end candidate is introduced.

The reviewed local input inventory has only match_001. Existing exposed development frames must not be relabeled as blind holdout. Concrete remaining qualification needs are detailed in [S-01 root cause](s01_snapshot_gate_root_cause.md), [transport verification](s01_snapshot_field_transport_verification.md) and the complete-path follow-up. Linux/Windows CI success validates code/contracts and packaged execution; it does not prove the missing source predicates or Windows real-video accuracy.

## All 82 assertions

| Assertion | Adopted | Current | First blocker / dependency |
| --- | --- | --- | --- |
| GT-R1-ROUND-START | fail | pass | — |
| GT-R1-DEATH | fail | fail | death_event_contract |
| GT-R1-ROUND-END | fail | fail | round_end_time |
| GT-R2-ROUND-START | fail | pass | — |
| GT-R2-DEATH | fail | fail | death_event_contract |
| ordering_constraints-000 | ne | not_evaluated | unmatched point dependency |
| ordering_constraints-001 | ne | not_evaluated | unmatched point dependency |
| ordering_constraints-002 | ne | not_evaluated | unmatched point dependency |
| ordering_constraints-003 | ne | not_evaluated | unmatched point dependency |
| GT-R1-BUY-FLAG | fail | fail | preparation_scope |
| GT-R1-ASTRAL-1 | fail | fail | remote_state |
| GT-R1-ASTRAL-2 | fail | fail | remote_state |
| GT-R1-SMOKE | fail | fail | smoke_state |
| GT-R1-COMBAT-REPORT | pass | pass | — |
| GT-R2-BUY-FLAG | fail | fail | preparation_scope |
| GT-R2-BUY-MENU-1 | fail | fail | preparation_scope |
| GT-R2-BUY-MENU-2 | fail | fail | preparation_scope |
| GT-R2-ASTRAL-1 | fail | fail | remote_state |
| GT-R2-ASTRAL-2 | fail | fail | remote_state |
| GT-R2-EXPANDED-MAP | fail | fail | expanded_map_state |
| GT-R2-SPECTATOR | fail | fail | spectator_coverage |
| OWN-R1-SELF | fail | fail | self_ownership |
| OWN-R1-SELF-DEAD | fail | fail | dead_ownership |
| OWN-R2-SELF | fail | fail | self_ownership |
| OWN-R2-SELF-DEAD | fail | fail | dead_ownership |
| OWN-R2-TEAMMATE | fail | fail | teammate_ownership |
| GT-R1-SNAP-0035 | fail | fail | snapshot_current_state_evidence |
| GT-R1-SNAP-0415 | fail | fail | snapshot_current_state_evidence |
| GT-R1-SNAP-475 | fail | fail | snapshot_current_state_evidence |
| GT-R1-SNAP-585 | fail | fail | snapshot_current_state_evidence |
| GT-R1-SNAP-595 | fail | fail | snapshot_current_state_evidence |
| GT-R1-SNAP-705 | pass | pass | — |
| GT-R1-SNAP-728 | fail | fail | snapshot_current_state_evidence |
| GT-R1-SNAP-733 | fail | fail | snapshot_current_state_evidence |
| GT-R1-SNAP-734 | fail | fail | snapshot_current_state_evidence |
| GT-R1-SNAP-7425 | fail | fail | snapshot_current_state_evidence |
| GT-R1-SNAP-7438 | fail | fail | snapshot_current_state_evidence |
| GT-R1-SNAP-7440 | fail | fail | snapshot_player_life_evidence |
| GT-R1-SNAP-7445 | fail | fail | snapshot_player_life_evidence |
| GT-R2-SNAP-820 | fail | fail | preparation_scope |
| GT-R2-SNAP-1050 | fail | fail | preparation_scope |
| GT-R2-SNAP-11145 | fail | fail | snapshot_player_life_evidence |
| GT-R2-SNAP-143 | fail | fail | snapshot_current_state_evidence |
| GT-R2-SNAP-1475 | fail | fail | snapshot_current_state_evidence |
| GT-R2-SNAP-1476 | fail | fail | snapshot_current_state_evidence |
| GT-R2-SNAP-1477 | fail | fail | snapshot_player_life_evidence |
| GT-R2-SNAP-149 | fail | fail | snapshot_current_state_evidence |
| GT-R2-SNAP-151 | fail | fail | snapshot_current_state_evidence |
| GT-R2-SNAP-170 | fail | fail | snapshot_player_life_evidence |
| GT-R1-SNAP-0035-DERIVED-zone_id | fail | fail | map_resolution |
| GT-R1-SNAP-0415-DERIVED-zone_id | fail | fail | map_resolution |
| GT-R2-SNAP-820-DERIVED-zone_id | fail | fail | preparation_scope |
| GT-R1-MUZZLE-1 | fail | fail | owned_visual_evidence |
| GT-R1-MUZZLE-2 | fail | fail | owned_visual_evidence |
| GT-R1-MUZZLE-3 | fail | fail | owned_visual_evidence |
| event_count_constraints-000 | fail | pass | — |
| event_count_constraints-001 | fail | fail | death_event_contract |
| event_count_constraints-002 | fail | pass | — |
| event_count_constraints-003 | fail | fail | owned_visual_evidence |
| event_count_constraints-004 | fail | pass | — |
| event_count_constraints-005 | fail | fail | death_event_contract |
| event_count_constraints-006 | pass | pass | — |
| NEG-REMOTE-R1A | pass | pass | — |
| NEG-REMOTE-R1B | pass | pass | — |
| NEG-REMOTE-R2A | pass | pass | — |
| NEG-REMOTE-R2B | pass | pass | — |
| NEG-ASTRAL-NOT-SMOKE | pass | pass | — |
| NEG-SMOKE-NOT-ASTRAL | pass | pass | — |
| NEG-SMOKE-WORLD-SPOT | pass | pass | — |
| NEG-NONSELF-KILLFEED | pass | pass | — |
| NEG-RELOAD-NOT-SHOT | pass | pass | — |
| NEG-BUY-MENU-1 | pass | pass | — |
| NEG-BUY-MENU-2 | pass | pass | — |
| NEG-SPECTATOR-COUNT-TEXT | pass | pass | — |
| NEG-DEAD-PLAYER-MECHANICS | pass | pass | — |
| NEG-EXPANDED-MAP-MECHANICS | pass | pass | — |
| NEG-SPECTATOR-POISON-151 | pass | pass | — |
| NEG-SPECTATOR-POISON-170 | pass | pass | — |
| NEG-STALE-COMBAT-REPORT | pass | pass | — |
| NEG-R2-NO-ROUND-END | pass | pass | — |
| NEG-SAME-ZONE-CALLOUT-CHANGE | pass | pass | — |
| NEG-CONTENT-JUMP-SPAN | pass | pass | — |

Machine report: [s01_current_failure_classification.json](../e2e_reports/match_001/s01_current_failure_classification.json). It contains measured source-frame/snapshot/event counts and failure field names, without private GT definitions or expected values. Historical evidence remains in original local artifacts; it has not been re-signed as current recognition.

This analysis changes documentation and sanitized diagnostic data only. Production source, qualification assets, thresholds, GT, schema, assertions, full sampler and adopted baseline remain unchanged.
