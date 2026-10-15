# S-01: semantic evidence root-cause matrix

**B — safety repair and source investigation, not completed Strict accuracy improvement.** The 50 rows below are FAILs in the original unadopted 28/50/4 Full. New guard-code Full metrics remain unmeasured. Adopted baseline remains 23/55/4. Existing S-01 transport and rejected retention findings are preserved; no dedup patch is reintroduced.

## Exclusive first-blocker counts

| First blocker | Original candidate FAIL | Share |
|---|---:|---:|
| death_event_contract | 4 | 8.0% |
| round_end_time | 1 | 2.0% |
| preparation_scope | 7 | 14.0% |
| remote_state | 4 | 8.0% |
| smoke_state | 1 | 2.0% |
| expanded_map_state | 1 | 2.0% |
| spectator_coverage | 1 | 2.0% |
| self_ownership | 2 | 4.0% |
| dead_ownership | 2 | 4.0% |
| teammate_ownership | 1 | 2.0% |
| snapshot_current_state_evidence | 15 | 30.0% |
| snapshot_player_life_evidence | 5 | 10.0% |
| map_resolution | 2 | 4.0% |
| owned_visual_evidence | 4 | 8.0% |

These exclusive counts sum to 50. They do not promise 50 single-fix gains. Current-state 15, player-life 5 and preparation 7 are the current counts; historical 17 HUD-gate and 9 preparation classifications are not reused. The companion JSON records all fields requested for every row, including explicit unmeasured source/qualification limitations.

## Fifty assertion rows

| Assertion | First blocker | Secondary failed fields / dependencies | Source / transport status | Next evidence |
|---|---|---|---|---|
| GT-R1-DEATH | death_event_contract | subject/attributes/coverage required by original predicate; no automatic gain | original artifacts; no new per-assertion pixel review | Source-bound self subject, victim/killer roles where available, report lifecycle and independent temporal corroboration; candidate only until qualification. |
| GT-R1-ROUND-END | round_end_time | subject/attributes/coverage required by original predicate; no automatic gain | original artifacts; no new per-assertion pixel review | Independent meaning of clock/score/result timing; no GT backdating or acceptance-window changes. PR42 remains separate. |
| GT-R2-DEATH | death_event_contract | subject/attributes/coverage required by original predicate; no automatic gain | original artifacts; no new per-assertion pixel review | Source-bound self subject, victim/killer roles where available, report lifecycle and independent temporal corroboration; candidate only until qualification. |
| GT-R1-BUY-FLAG | preparation_scope | subject/attributes/coverage required by original predicate; no automatic gain | original artifacts; outside proven Strict preparation | Continuous same-segment qualified preparation evidence overlapping native lifecycle; preserve source breaks and unknown fragments. |
| GT-R1-ASTRAL-1 | remote_state | subject/attributes/coverage required by original predicate; no automatic gain | original artifacts; no new per-assertion pixel review | Discriminative current-frame remote interface and independent negative/holdout qualification; no threshold-only retry. |
| GT-R1-ASTRAL-2 | remote_state | subject/attributes/coverage required by original predicate; no automatic gain | original artifacts; no new per-assertion pixel review | Discriminative current-frame remote interface and independent negative/holdout qualification; no threshold-only retry. |
| GT-R1-SMOKE | smoke_state | subject/attributes/coverage required by original predicate; no automatic gain | original artifacts; no new per-assertion pixel review | Discriminative smoke semantics with independent occlusion/flash/remote controls. |
| GT-R2-BUY-FLAG | preparation_scope | subject/attributes/coverage required by original predicate; no automatic gain | original artifacts; outside proven Strict preparation | Continuous same-segment qualified preparation evidence overlapping native lifecycle; preserve source breaks and unknown fragments. |
| GT-R2-BUY-MENU-1 | preparation_scope | subject/attributes/coverage required by original predicate; no automatic gain | original artifacts; outside proven Strict preparation | Continuous same-segment qualified preparation evidence overlapping native lifecycle; preserve source breaks and unknown fragments. |
| GT-R2-BUY-MENU-2 | preparation_scope | subject/attributes/coverage required by original predicate; no automatic gain | original artifacts; outside proven Strict preparation | Continuous same-segment qualified preparation evidence overlapping native lifecycle; preserve source breaks and unknown fragments. |
| GT-R2-ASTRAL-1 | remote_state | subject/attributes/coverage required by original predicate; no automatic gain | original artifacts; no new per-assertion pixel review | Discriminative current-frame remote interface and independent negative/holdout qualification; no threshold-only retry. |
| GT-R2-ASTRAL-2 | remote_state | subject/attributes/coverage required by original predicate; no automatic gain | original artifacts; no new per-assertion pixel review | Discriminative current-frame remote interface and independent negative/holdout qualification; no threshold-only retry. |
| GT-R2-EXPANDED-MAP | expanded_map_state | subject/attributes/coverage required by original predicate; no automatic gain | original artifacts; no new per-assertion pixel review | Qualified tactical-map structure and temporal state evidence. |
| GT-R2-SPECTATOR | spectator_coverage | subject/attributes/coverage required by original predicate; no automatic gain | original artifacts; no new per-assertion pixel review | Discriminative panel/subject evidence throughout the required interval, retaining unknown for ambiguous frames. |
| OWN-R1-SELF | self_ownership | subject/attributes/coverage required by original predicate; no automatic gain | original artifacts; no new per-assertion pixel review | All current-frame independent identity structures, spectator exclusion and world-view validity over source-continuous intervals. |
| OWN-R1-SELF-DEAD | dead_ownership | subject/attributes/coverage required by original predicate; no automatic gain | original artifacts; no new per-assertion pixel review | Independently established self subject/death; no inference from persistent report or spectator. |
| OWN-R2-SELF | self_ownership | subject/attributes/coverage required by original predicate; no automatic gain | original artifacts; no new per-assertion pixel review | All current-frame independent identity structures, spectator exclusion and world-view validity over source-continuous intervals. |
| OWN-R2-SELF-DEAD | dead_ownership | subject/attributes/coverage required by original predicate; no automatic gain | original artifacts; no new per-assertion pixel review | Independently established self subject/death; no inference from persistent report or spectator. |
| OWN-R2-TEAMMATE | teammate_ownership | subject/attributes/coverage required by original predicate; no automatic gain | original artifacts; no new per-assertion pixel review | Qualified spectator subject and team affiliation with continuous coverage. |
| GT-R1-SNAP-0035 | snapshot_current_state_evidence | primary_state, player_alive, location_label_raw | fresh native PTS; snapshot + trace present | Qualified current-frame HP/ability/weapon structure plus discriminative spectator exclusion and competing-view controls; failed semantic fields still require dedicated producers. |
| GT-R1-SNAP-0415 | snapshot_current_state_evidence | primary_state, player_alive, location_label_raw | fresh native PTS; snapshot + trace present | Qualified current-frame HP/ability/weapon structure plus discriminative spectator exclusion and competing-view controls; failed semantic fields still require dedicated producers. |
| GT-R1-SNAP-475 | snapshot_current_state_evidence | primary_state, player_alive, nonself_killfeed_row_visible | fresh native PTS; snapshot + trace present | Qualified current-frame HP/ability/weapon structure plus discriminative spectator exclusion and competing-view controls; failed semantic fields still require dedicated producers. |
| GT-R1-SNAP-585 | snapshot_current_state_evidence | primary_state | fresh native PTS; snapshot + trace present | Qualified current-frame HP/ability/weapon structure plus discriminative spectator exclusion and competing-view controls; failed semantic fields still require dedicated producers. |
| GT-R1-SNAP-595 | snapshot_current_state_evidence | primary_state, vision_obscured_smoke | fresh native PTS; snapshot + trace present | Qualified current-frame HP/ability/weapon structure plus discriminative spectator exclusion and competing-view controls; failed semantic fields still require dedicated producers. |
| GT-R1-SNAP-728 | snapshot_current_state_evidence | primary_state, player_alive, ammo_mag, ammo_reserve, reload_animation_visible | fresh native PTS; snapshot + trace present | Qualified current-frame HP/ability/weapon structure plus discriminative spectator exclusion and competing-view controls; failed semantic fields still require dedicated producers. |
| GT-R1-SNAP-733 | snapshot_current_state_evidence | primary_state, player_alive, ammo_mag, ammo_reserve, reload_animation_visible | fresh native PTS; snapshot + trace present | Qualified current-frame HP/ability/weapon structure plus discriminative spectator exclusion and competing-view controls; failed semantic fields still require dedicated producers. |
| GT-R1-SNAP-734 | snapshot_current_state_evidence | primary_state, player_alive, ammo_mag, ammo_reserve, reload_animation_visible | fresh native PTS; snapshot + trace present | Qualified current-frame HP/ability/weapon structure plus discriminative spectator exclusion and competing-view controls; failed semantic fields still require dedicated producers. |
| GT-R1-SNAP-7425 | snapshot_current_state_evidence | primary_state, player_alive, player_hp, muzzle_flash_visible, location_label_raw, spectator_primary_state | fresh native PTS; snapshot + trace present | Qualified current-frame HP/ability/weapon structure plus discriminative spectator exclusion and competing-view controls; failed semantic fields still require dedicated producers. |
| GT-R1-SNAP-7438 | snapshot_current_state_evidence | primary_state, player_alive, muzzle_flash_visible | fresh native PTS; snapshot + trace present | Qualified current-frame HP/ability/weapon structure plus discriminative spectator exclusion and competing-view controls; failed semantic fields still require dedicated producers. |
| GT-R1-SNAP-7440 | snapshot_player_life_evidence | player_alive | fresh native PTS; snapshot + trace present | Independent subject-bound alive/death evidence; timer, report presence and spectator are insufficient. |
| GT-R1-SNAP-7445 | snapshot_player_life_evidence | player_alive, score_enemy | fresh native PTS; snapshot + trace present | Independent subject-bound alive/death evidence; timer, report presence and spectator are insufficient. |
| GT-R2-SNAP-820 | preparation_scope | snapshot_hud_gate | original artifacts; outside proven Strict preparation | Continuous same-segment qualified preparation evidence overlapping native lifecycle; preserve source breaks and unknown fragments. |
| GT-R2-SNAP-1050 | preparation_scope | snapshot_hud_gate | original artifacts; outside proven Strict preparation | Continuous same-segment qualified preparation evidence overlapping native lifecycle; preserve source breaks and unknown fragments. |
| GT-R2-SNAP-11145 | snapshot_player_life_evidence | player_alive | fresh native PTS; snapshot + trace present | Independent subject-bound alive/death evidence; timer, report presence and spectator are insufficient. |
| GT-R2-SNAP-143 | snapshot_current_state_evidence | primary_state, player_alive, player_hp | fresh native PTS; snapshot + trace present | Qualified current-frame HP/ability/weapon structure plus discriminative spectator exclusion and competing-view controls; failed semantic fields still require dedicated producers. |
| GT-R2-SNAP-1475 | snapshot_current_state_evidence | primary_state, player_alive, player_hp | fresh native PTS; snapshot + trace present | Qualified current-frame HP/ability/weapon structure plus discriminative spectator exclusion and competing-view controls; failed semantic fields still require dedicated producers. |
| GT-R2-SNAP-1476 | snapshot_current_state_evidence | primary_state, player_alive, player_hp | fresh native PTS; snapshot + trace present | Qualified current-frame HP/ability/weapon structure plus discriminative spectator exclusion and competing-view controls; failed semantic fields still require dedicated producers. |
| GT-R2-SNAP-1477 | snapshot_player_life_evidence | player_alive | fresh native PTS; snapshot + trace present | Independent subject-bound alive/death evidence; timer, report presence and spectator are insufficient. |
| GT-R2-SNAP-149 | snapshot_current_state_evidence | primary_state, player_alive | fresh native PTS; snapshot + trace present | Qualified current-frame HP/ability/weapon structure plus discriminative spectator exclusion and competing-view controls; failed semantic fields still require dedicated producers. |
| GT-R2-SNAP-151 | snapshot_current_state_evidence | primary_state, player_alive, view_owner, spectated_name, spectated_hp, spectated_ammo_mag, spectated_ammo_reserve, spectated_weapon, spectated_location_label_raw | fresh native PTS; snapshot + trace present | Qualified current-frame HP/ability/weapon structure plus discriminative spectator exclusion and competing-view controls; failed semantic fields still require dedicated producers. |
| GT-R2-SNAP-170 | snapshot_player_life_evidence | player_alive, spectated_name, spectated_hp, spectated_ammo_mag, spectated_ammo_reserve, spectated_weapon, muzzle_flash_visible, spectated_location_label_raw | fresh native PTS; snapshot + trace present | Independent subject-bound alive/death evidence; timer, report presence and spectator are insufficient. |
| GT-R1-SNAP-0035-DERIVED-zone_id | map_resolution | map_resolution | original artifacts; no new per-assertion pixel review | Actual map resolver calibration/assets and source-specific field provenance; global snapshot transport does not resolve map. |
| GT-R1-SNAP-0415-DERIVED-zone_id | map_resolution | map_resolution | original artifacts; no new per-assertion pixel review | Actual map resolver calibration/assets and source-specific field provenance; global snapshot transport does not resolve map. |
| GT-R2-SNAP-820-DERIVED-zone_id | preparation_scope | snapshot_hud_gate, map_resolution | original artifacts; outside proven Strict preparation | Continuous same-segment qualified preparation evidence overlapping native lifecycle; preserve source breaks and unknown fragments. |
| GT-R1-MUZZLE-1 | owned_visual_evidence | subject/attributes/coverage required by original predicate; no automatic gain | original artifacts; no new per-assertion pixel review | Current owner plus source-bound visual action semantics and continuous corroboration; do not attribute spectator muzzle to self. |
| GT-R1-MUZZLE-2 | owned_visual_evidence | subject/attributes/coverage required by original predicate; no automatic gain | original artifacts; no new per-assertion pixel review | Current owner plus source-bound visual action semantics and continuous corroboration; do not attribute spectator muzzle to self. |
| GT-R1-MUZZLE-3 | owned_visual_evidence | subject/attributes/coverage required by original predicate; no automatic gain | original artifacts; no new per-assertion pixel review | Current owner plus source-bound visual action semantics and continuous corroboration; do not attribute spectator muzzle to self. |
| event_count_constraints-001 | death_event_contract | subject/attributes/coverage required by original predicate; no automatic gain | original artifacts; no new per-assertion pixel review | Source-bound self subject, victim/killer roles where available, report lifecycle and independent temporal corroboration; candidate only until qualification. |
| event_count_constraints-003 | owned_visual_evidence | subject/attributes/coverage required by original predicate; no automatic gain | original artifacts; no new per-assertion pixel review | Current owner plus source-bound visual action semantics and continuous corroboration; do not attribute spectator muzzle to self. |
| event_count_constraints-005 | death_event_contract | subject/attributes/coverage required by original predicate; no automatic gain | original artifacts; no new per-assertion pixel review | Source-bound self subject, victim/killer roles where available, report lifecycle and independent temporal corroboration; candidate only until qualification. |

## Preparation scope: seven remaining blockers

Existing native lifecycle and Practical unknown-fragment retention are reused unchanged. Proven R1 package starts at 2.502669, leaving the earlier prefix outside Strict support. R2 starts its preparation scope at 110.986003; the earlier buy/menu observations around 82 and 105 seconds are not in that proven package. Capture duplicate/source breaks at 81.786003/81.836003 prevent treating the whole inter-round span as one uninterrupted preparation episode. After the break, a menu/report observation is not by itself proof of which upcoming round owns it. The current overlap-based episode extension already transports qualified same-segment support; there is no demonstrated unconnected qualified episode to attach without weakening membership. No GT round number, duration-only attachment or inferred R2 end is added. A new continuous qualification showing same-segment preparation → native start is required; unrelated isolated frames cannot prove it.

## Other independent failures

Original raw contains zero structured killfeed readings and zero combat-report field readings. Source candidates cannot supply missing victim/killer/self binding. Remote/smoke/expanded-map semantics lack qualified discriminative current-frame evidence; map resolution needs actual map assets/calibration. Owned visual assertions additionally require self ownership; spectator muzzle evidence is not self firing. Existing source-confidence/location caps remain intact. R1 end remains the first observed score change, outside the fixed canonical window: this follow-up does not backdate it and leaves PR #42 untouched. No further safe positive promotion was proved from these assets.

## Previous / Current / Delta

| Metric | Previous unadopted Full | New guard-code Full | Delta |
|---|---:|---|---|
| Canonical PASS | 28 | Unmeasured | Unmeasured |
| Canonical FAIL | 50 | Unmeasured | Unmeasured |
| NOT_EVALUATED | 4 | Unmeasured | Unmeasured |
| Negative violations | 0 (20 negative assertions PASS) | Unmeasured | Unmeasured |
| Discontinuity violations | 0 | Unmeasured | Unmeasured |
| Current-state first blockers | 15 | Unmeasured | Unmeasured |
| Player-life first blockers | 5 | Unmeasured | Unmeasured |
| Preparation first blockers | 7 | Unmeasured | Unmeasured |
| Death first blockers | 4 | Unmeasured | Unmeasured |

No assertion is claimed newly PASS. The one-condition fix suppresses unowned legacy Death candidates; it has no demonstrated positive semantic gain. A 10.5-hour Full with unchanged readers and no positive qualification would not test a new PASS hypothesis, so none was launched. Older raw is used only to describe its original evaluator result and transport, never retagged as new recognition.

## Review and merge scope

PR #44 remains the transport-only Draft PR, separate from this follow-up. Its last checked source review branch is a067f34 with successful Linux/Windows CI; main remains 7e480c2. It is technically mergeable, but requires reviewer acceptance of its limited B scope and private-source evidence limitations; no main merge is authorized here. This follow-up enforces an existing player-owned predicate on a previously omitted Death path and adds diagnostics/tests/reports. It changes no schema, threshold or identity criterion.

For measured per-frame detail see [State/Identity](state_identity_source_investigation.md), [Death](death_subject_evidence_investigation.md), and [machine-readable matrix](../e2e_reports/match_001/s01_semantic_evidence_followup.json).
