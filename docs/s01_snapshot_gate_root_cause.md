# S-01: Snapshot gate root cause

## Scope and evidence identity

S-01 starts from main `7e480c2f2f7f49aea73e1541d065d78881d2f11c` and existing independent branch HEAD `46462336427149764beb8e1fdd94c554e075616e`. `git fetch origin` confirms main has not advanced. PR #42 is another developer's branch and is not modified. This branch already implements the minimal independent global projection; S-01 audits and extends its diagnostics instead of duplicating it.

Adopted canonical full baseline remains **23 PASS / 55 FAIL / 4 NE**. Historical experimental full is **28 / 50 / 4**. Saved-raw transport replay is not current-code recognition or new image qualification. The 17 fixed targets below come from the historical classification; no claim is made that latest-main independently has exactly 17 identical failures.

## Data flow and first loss

Source native PTS → calibrated readers → HudObservationV2 → RoundPackageBuilder → state_snapshots → FactBuilder → Rule candidates → Evaluation → canonical trace.

`RealHudAnalyzer` assigns aggregate HUD confidence using the minimum of state and participating reader confidences. Reserved `round_timer_value`, `score_ally_value`, and `score_enemy_value` record independent accepted value support; geometry ROI confidence cannot substitute for these. `_state_snapshots()` originally rejects the entire row below 0.65. All 17 nearest observations have primary `unknown`, player-specific HUD invalid, aggregate **0** and state confidence **0**. Thus low identity/state support alone explains their aggregate rejection; the real-data result does **not** establish that a weapon reader alone caused these 17 failures.

The normal player snapshot gate remains 0.65. A separate `_global_snapshot()` projection retains only explicit unknown/unowned calibrated, unobscured observations with existing accepted score/timer proof >=0.90. It does not change reader output or aggregate quality. Values without proof remain null. No HP/armor/weapon/utility/location/alive/death/shot fact is admitted by this path.

## Fixed 17 target audit

The table uses the nearest actual main source PTS, selected by time alone. All rows are in the historical candidate's native package scopes, not provisional promoted events. Round membership derives from native lifecycle windows, not the assertion ID. Field confidences mean **producer acceptance**, not an independently reviewed correct value. Timer below-floor or absent proof is not retained even if a numeric value exists. All targets have unknown player identity and owner; retained fields have global/system scope.

| Assertion | Source PTS | HUD / state confidence | Timer display support | Ally / enemy value support | Secondary missing predicates |
| --- | ---: | --- | --- | --- | --- |
| GT-R1-SNAP-0415 | 4.152669 | 0 / 0 | 0.9607433676719666 | 0.9473333954811096 / 0.9943748712539673 | primary_state, player_alive, location_label_raw |
| GT-R1-SNAP-585 | 58.502669 | 0 / 0 | 0.9316428303718567 | 0.9456049203872681 / 0.9710036516189575 | primary_state, vision_obscured_smoke |
| GT-R1-SNAP-595 | 59.502669 | 0 / 0 | 0.9351649284362793 | 0.9547474384307861 / 0.9662814140319824 | primary_state, vision_obscured_smoke, remote_control_subtype |
| GT-R1-SNAP-733 | 73.302669 | 0 / 0 | 0.9414150714874268 | 0.0 / 0.9689244031906128 | primary_state, player_alive, ammo_mag, ammo_reserve, reload_animation_visible |
| GT-R1-SNAP-734 | 73.402669 | 0 / 0 | 0.9533022046089172 | 0.9510979056358337 / 0.9646438360214233 | primary_state, player_alive, ammo_mag, ammo_reserve, reload_animation_visible |
| GT-R1-SNAP-7425 | 74.252669 | 0 / 0 | 0.9462669491767883 | 0.9489420056343079 / 0.9662814140319824 | primary_state, player_alive, player_hp, muzzle_flash_visible, location_label_raw, spectator_primary_state |
| GT-R1-SNAP-7438 | 74.386003 | 0 / 0 | 0.9610928297042847 | 0.9510506391525269 / 0.9662814140319824 | primary_state, player_alive, muzzle_flash_visible |
| GT-R1-SNAP-7440 | 74.402669 | 0 / 0 | unknown | 0.9400646090507507 / 0.96949303150177 | player_alive |
| GT-R1-SNAP-7445 | 74.452669 | 0 / 0 | 0.9411492943763733 | 0.937731146812439 / 0.964837908744812 | player_alive |
| GT-R2-SNAP-11145 | 111.452669 | 0 / 0 | 0.9361436367034912 | 0.9515504240989685 / 0.9599531292915344 | player_alive |
| GT-R2-SNAP-143 | 143.002669 | 0 / 0 | unknown | 0.0 / 0.965490996837616 | primary_state, player_alive, player_hp |
| GT-R2-SNAP-1475 | 147.502669 | 0 / 0 | unknown | 0.0 / 0.9498803615570068 | primary_state, player_alive, player_hp |
| GT-R2-SNAP-1476 | 147.602669 | 0 / 0 | unknown | 0.0 / 0.9453411102294922 | primary_state, player_alive, player_hp |
| GT-R2-SNAP-1477 | 147.719336 | 0 / 0 | 0.960155725479126 | 0.0 / 0.9661900401115417 | player_alive |
| GT-R2-SNAP-149 | 149.002669 | 0 / 0 | 0.9601021409034729 | 0.9538372755050659 / 0.9664362072944641 | primary_state, player_alive |
| GT-R2-SNAP-151 | 151.002669 | 0 / 0 | 0.9614624381065369 | 0.9412204027175903 / 0.9619362354278564 | primary_state, player_alive, view_owner, spectated_name, spectated_hp, spectated_ammo_mag, spectated_ammo_reserve, spectated_weapon, spectated_location_label_raw |
| GT-R1-SNAP-0415-DERIVED-zone_id | 4.152669 | 0 / 0 | 0.9607433676719666 | 0.9473333954811096 / 0.9943748712539673 | zone_id |

Exact local observations and reader provenance are in the private diagnostic output. The private source-field audit records each required predicate and source-image review; only sanitized metrics are published here. Sixteen targets require snapshots and one requires a derived zone. The first loss of eligible globals is `_state_snapshots()`; on this branch those fields can reach snapshots, score/timer facts and trace. The secondary predicates still fail. Never use the assertion's expected state to promote the observation.

## Hypotheses

| Hypothesis | Result | Evidence and limit |
| --- | --- | --- |
| H1: unrelated confidence lowers aggregate | Structurally supported; specific 17 attribution limited | `min(state, readers)` couples fields; nearest state support is already zero, so a particular low reader is not proved causal. A synthetic weak-reader control isolates the structural coupling. |
| H2: accepted globals discarded at snapshot gate | Supported | Hash-bound saved raw has valid score/timer support below aggregate gate; same-input projection retains them. |
| H3: snapshot source support unnecessarily lowered | Supported for aggregate-backed legacy fields; not permission to raise it | Legacy ally/enemy-alive, weapon, spike and utility use conservative aggregate support. No qualified per-value proof for those fields is invented. Global score/timer use existing reserved support. |
| H4: high confidence is not qualification | Supported as a distinction | Geometry or arbitrary high numeric input alone never qualifies a value; current code-bound component admission and source reviews are separate evidence. A frozen/cohort recheck is not new independent holdout. |
| H5: retained snapshots still fail ownership/fields | Supported | Every fixed target requires at least one unproved non-global predicate; canonical saved-raw result stays 28/50/4. |
| H6: gate affects round scope/completeness | Supported in code; causal PASS impact unproved | `_round_windows()` and `aggregate_observation_quality()` also consume aggregate admission. Keep them unchanged; global retention must not imply complete player coverage. |

## Downstream contracts and rejected designs

`FactBuilder` already uses `source_confidence.player_location` for snapshot-derived zone facts. The builder's direct zone-fact path separately caps support with package visual confidence. These are different producers; neither cap is removed. The independent global projection cannot widen visual/map association: those merge entrances retain the normal aggregate gate.

Score facts append after legacy facts so old fact IDs stay stable; the existing independent timer-fact producer is reused, with duplicate value/time keys suppressed by FactBuilder. Timer display provenance and current PTS survive snapshot and trace. Trace stores exact field support in `source_confidence_by_field`, with a conservative scalar minimum for the canonical schema. Per-fact arbitrary image/profile provenance is not added to existing schema: original source/run/code/profile binding remains in hash-bound inputs. Lack of richer per-fact provenance must not be presented as a newly solved contract.

Nullable existing fields express unknown. No Schema v2/v3 migration or confidence semantic change is made. JSON round-trip is tested; SQLite/checkpoint/GUI integration acceptance remains a separate verification gate. Rule Engine/AI evaluation is not made eligible by additional global snapshots; package completeness and ownership remain unchanged.

Rejected: removing 0.65 globally; replacing aggregate with max reader confidence; using ROI geometry as numeric qualification; inheriting nearby values; promoting unknown to live; fabricating round membership; claiming 17 PASS gain. None can establish missing player evidence.

## Validation concern

`GT-R1-SNAP-7445` still fails: reviewed source images inside its unchanged window show enemy score 1; the first reviewed score 2 is outside. Preserve original GT, acceptance window and FAIL. Do not copy a later value backward.

## Remaining work and acceptance

See [transport verification](s01_snapshot_field_transport_verification.md). Current-branch Linux/Windows CI, coverage >=75%, packaged smoke and SQLite/checkpoint controls passed at the recorded code commit (see verification report). Those checks do not establish independent correctness of every retained source field or qualify missing player/context predicates. No new reader, threshold, qualification pack, GT or assertion change is authorized by this report.
