# E2E failure analysis

> Latest native-source follow-up: every native frame in two explicit preparation windows is now verified (60frames). Source-crop review after predictions:54correct displayed strings/6unknown/0wrong; this is development evidence, not independent clock/continuity qualification. R1 genuinely displays `0:00→2:25→1:39`, and R2 lacks enough same-segment preparation. Both start simulations remain0 even at native source cadence. Denser input and phase latching alone are therefore insufficient; next separate display reading from clock temporal qualification and source-safe phase context. A prior58-frame cohort failed the new probe-coverage audit and is excluded from continuous acceptance. No production thresholds/GT/sampler or canonical status changed. New16tests/Ruff/mypy100 pass; no unnecessary full run. [Detailed source findings](../e2e_reports/match_001/native_global_preparation_diagnostics.json).

> Latest qualified-source contract follow-up: the opt-in analyzer prevents external signals from replacing source phase/result/continuity evidence or measured reader confidence. The lifecycle requires segment-local phase samples spanning the existing0.05sec minimum; older semantic PTS cannot supply that duration. Before-fix synthetic controls reproduce4proof overwrites and1short-duration start, all rejected after the fix. Related183tests/Ruff/mypy100 pass. Actual-image optimistic projection remains0starts over263samples with identical continuity outcomes. This fixes unsafe contracts, not real boundary coverage; canonical23/55/4 remains historical, with no new measurement or PASS gain. Next inspect contiguous native source support between saved analysis PTS. [Current measurements and remaining blockers](../e2e_reports/match_001/global_source_contract_diagnostics.json).

> Authorized global lifecycle implementation: the user approved qualified identity-independent system events and assertion-fixed numeric development. A profile/code-bound qualification gate and independently attested continuity now guard the opt-in start/end path; native package/trace integration preserves unknown player identity and no self ownership in synthetic tests. Related159 tests, Ruff and mypy pass. No real qualified input profile or runtime continuity producer exists yet; fresh full results and PASS gains remain unmeasured. See [current contract](global_round_start_contract.md) and [implementation verification](../e2e_reports/match_001/global_lifecycle_implementation_diagnostics.json).

> Dense R1 end follow-up: ten consecutive source frames at 74.36–74.52 reveal a one-frame `TEAM ACE` banner at 74.436003, absent from archived full-native PTS but present in an older targeted input. This is a source evidence/transport and corroboration problem, not proven absence of end evidence in the video. Timer/score update after this frame; continuity, safe readers and temporal corroboration remain unqualified. No production or sampler change, new candidate or canonical PASS. See [source diagnostic](../e2e_reports/match_001/r1_end_dense_source_diagnostics.json).

> Legacy contract compatibility: current native builder and trace adapter reproduce the archived profile13 (4634 observations, 37.824 s) and rejected profile16 (4661 observations, 43.489 s) packages, traces and all 82 assertion outcomes exactly. Counts remain 23/55/4, all deltas zero. This is offline reconstruction of archived inputs, not fresh recognition/full E2E or safety qualification of the new phase/display paths. Both traces have zero temporal features, so unchanged discontinuity results are not affirmative cut-safety evidence. See [machine-readable verification](../e2e_reports/match_001/legacy_contract_compatibility.json).

> Global start contract diagnostic: fresh image replay supports diagnostic start proposals at 4.152669 and 111.436003 from independently confirmed phase, timer reset and later strong timer observations, while all 19 primary states remain unknown. Current production still emits zero events because it requires player-live identity and immediate timer availability. Proposals remain outside production/package/trace evaluation; the borrowed existing timer reader belongs to still-rejected profile16. Numeric configuration alone is therefore insufficient. The global system-event contract decision is pending; no assertion status changes. See [proposal and source limits](global_round_start_contract.md).

> Source timer-display follow-up: the reader→HUD→native snapshot→trace path now preserves accepted source text and provenance through optional typed fields; it does not format seconds as text. A diagnostic-only real replay with the still-rejected profile16 verifies `0:33` transport at PTS 70.402669. This fixes a transport gap, not timer qualification or the four display-dependent assertion predicates. No new full result or PASS gain is claimed. See [contract and limits](timer_display_contract.md).

> Latest lifecycle contract follow-up: source-qualified global purchase-phase confidence now reaches the direct start-candidate gate and `pre_round` lifecycle state while player HUD confidence remains zero. Real short-window replay confirms preparation at 3.902669 and 111.352669; accepted boundary timers/live evidence remain missing, so no boundary or canonical PASS is claimed. Fresh targeted remains 0/5/2 and sampled 7/12/11 with unchanged failure sets. Details and current safety limits: [implementation](round_lifecycle_implementation.md), [diagnostics](../e2e_reports/match_001/lifecycle_preparation_confidence_diagnostics.json). The 82 assertion matrix below remains the historical full result, not an evaluation of this working tree.

> Current phase-contract follow-up: the structural text profile and temporal phase tracker produce 64 confirmed global purchase-phase flags on all 224 native frames in 0–9 seconds. The native package remains a partial fragment `[7.369336, 8.502669]`, with no start/end events. Qualified preparation extends an actual detected round's context; it cannot create a missing start. The earlier hypothesis that phase confidence alone would resolve package scope is rejected. Canonical 23/55/4 and all 82 historical assertion classifications remain unchanged. See [phase qualification](phase_reference_qualification.md) and [native package diagnostics](../e2e_reports/match_001/semantic_phase_contract_diagnostics.json).

> Post-analysis follow-up (2026-10-08, main `8e3cf32`): the match lifecycle actor contract is now consistently `system`, with conservative lifecycle/package/trace unit coverage. The historical report below describes the earlier full run; its actor mismatch is no longer an unresolved code-contract gap. Real boundaries remain unqualified and no additional canonical PASS is proven. [Purchase-phase reference qualification](phase_reference_qualification.md) subsequently verified 11 semantic matches over 18 native boundary-window frames, with unchanged unknown states, no accepted score/timer pairs and zero boundary events. This diagnostic profile is not adopted; the 23/55/4 classification and 29 package-scope failures remain authoritative until a new canonical evaluation proves otherwise.

## 1. Executive Summary

**最大の最初の阻害条件はround packageの範囲・所属で、29/55 FAIL（52.73%）です。** 25件はround2の出力がすべて`sample_round_1`に入ること、4件は最初のpackage開始より前のR1 snapshot／derived zoneに対応します。直接のround境界4件を合わせると33件に影響しますが、33件のPASS増加を意味しません。

次に1つだけ着手するなら、**round lifecycleの縦断契約（phase/境界の実画像証拠→native package→traceのactor・round所属）を完成させる**ことです。真の開始2回・終了1回を検出し、actor/time/countを満たす場合、6 FAILと1 NEがPASSになり、**23→30 PASS／49 FAIL／3 NE**が条件付き目標になります。現時点で保証できる実runの増加は0です。round IDだけの照合条件を一時的に外した論理感度診断ではR2の25件がすべて残り、単なるrelabelでは23 PASSのままです。

停滞はrecognizer精度だけではありません。package／snapshotの上流gateと、検出結果を必要なフィールドへ運ぶ未完成の契約が混在しています。11の失敗snapshotは現行producer／adapterにない明示フィールドを要求します。timerの数字を読み取れても、元の表示文字列を保持する経路がないため4 snapshotは通りません。round detectorはactor=`team`、packは`system`を要求し、deathの要求属性も現在の出力にありません。

fresh geometry=1は重大な観測上の弱点ですが、effective geometryは4661/4661で有効、geometry-invalid unknownは0です。現在の55件から**geometryが単独原因と証明できるFAILは0件**です。「影響がない」という意味ではありません。保持calibrationの実画像上の位置誤差と、失敗への因果寄与は未証明です。

round／event／mapのコードパスは呼ばれています。roundはphase・state・score等の証拠不足、eventは属性・ownership・閾値を満たす入力不足、mapは選択／profile不足とeligibility不足です。rawのdomain eventは0ですがtraceには262の`state_snapshot` eventと4のactor不明muzzle observationがあります。

candidate方式は廃止せず、**実装すべき契約と解消対象IDを先に固定する方式へ変更**します。未完成producerを埋めずに数値recognizer候補を増やす方式は止めます。

## 2. Current E2E status

分析開始時に`git fetch origin`、`git checkout main`、`git pull --ff-only`を実行し、開始SHAは`d6d7e5188b9b51c0d8dba2b8afd16b0e9ffa32a1`、origin/mainと一致しました。既存の未コミット`docs/pi_recognition_improvement.md`は保持しています。

最新の正常**処理完了**fullは`outputs/recognition-investigation/timer-only-profile15/full16`、開始2026-10-07 13:19:14 UTC、wall15149.129秒（4時間12分29秒）、4661 analyzed framesです。23 PASS /55 FAIL /4 NE、schema valid、error_code=null、native analyzer exit0、canonical evaluator exit1（既存FAIL）です。処理完了は精度合格を意味しません。profile16はtimer誤読3件で却下済みで、採用していません。採用可能な比較profile13も23/55/4で、82 statusは同じです。

歴史的run metadataは`e05c495…`のdirty tree、code fingerprint`22defc36…`です。最新clean mainのfullを今回新規に走らせたとは扱いません。最新mainのHUD／round／map／visual／E2E producerソースは検証済みcommit3d0dc37から変更されていないことをGit差分で確認しました。後続mainのobservability更新を含む全code fingerprintは一致しません。

入力video SHA256：`71d58558559d6f578433ce9f234bf176f76fd5a86657dbfe3eba1e7d36136b06`。pack fingerprint：`7f0b7798857670f08074adbeea73d24176967ad5bf1f2f7300d2c2f792cf956f`。assertions SHA256：`c5e242b611ce227d1d2633e5e24c00dfe65168d8124ab58fbdea84b1d7f0d820`。terminal raw／trace／evaluation hashを照合し、最新mainのcanonical evaluatorで保存traceを再評価して全82 status／全failure codeの一致を確認しました。history／summaryもこの終了runを記録しています。artifact source hashはJSONにあります。

| 指標 | 値 |
| --- | ---: |
| unknown / live / buy menu / spectator | 3731 /455 /301 /174 |
| identity不足（positive count<3） | 3771 |
| HP / Ability / Weapon identity missing | 794 /2318 /2610 |
| fresh / effective / retained geometry | 1 /4661 /4660 |
| native package | 1、境界未完了fragment |
| round start / end / raw HUD events / raw Visual events | 0 /0 /0 /0 |
| map resolved / held | 0 /0 |
| trace events / snapshots / visual observations | 262 /930 /4 |
| negative violations / discontinuity violations | 0 /0 |

## 3. 82 assertion matrix

この一覧のprimary rootは**最初に観測した阻害条件を一つ選んだ排他的分類**です。下流機能が実装済みと保証する分類ではありません。複数の実装欠落・recognition gateはJSONのsecondary_blockers／upstream_dependenciesと次章に残しています。NE4件はground truth欠落ではなく、必須point eventがないためorderingを評価できません。

| Assertion | Status | Category | Primary root | Direct / Upstream | Fix target |
| --- | --- | --- | --- | --- | --- |
| GT-R1-ROUND-START | FAIL | round start/end | C03 | direct | round phase evidence and temporal lifecycle |
| GT-R1-DEATH | FAIL | kill/death/combat event | C05 | direct | current-frame death evidence plus semantic attribute producer |
| GT-R1-ROUND-END | FAIL | round start/end | C03 | direct | round phase evidence and temporal lifecycle |
| GT-R2-ROUND-START | FAIL | round package | C01 | upstream | round lifecycle / package context / adapter association |
| GT-R2-DEATH | FAIL | round package | C01 | upstream | round lifecycle / package context / adapter association |
| ordering_constraints-000 | NE | evaluator / ordering upstream | point dependency | upstream | point event producers |
| ordering_constraints-001 | NE | evaluator / ordering upstream | point dependency | upstream | point event producers |
| ordering_constraints-002 | NE | evaluator / ordering upstream | point dependency | upstream | point event producers |
| ordering_constraints-003 | NE | evaluator / ordering upstream | point dependency | upstream | point event producers |
| GT-R1-BUY-FLAG | FAIL | buy phase | C08 | direct | qualified phase evidence and stable score inputs |
| GT-R1-ASTRAL-1 | FAIL | remote state | C06 | direct | Astra compound current-frame evidence |
| GT-R1-ASTRAL-2 | FAIL | remote state | C06 | direct | Astra compound current-frame evidence |
| GT-R1-SMOKE | FAIL | smoke state | C09 | direct | smoke structural/temporal evidence |
| GT-R1-COMBAT-REPORT | PASS | combat report | — | - | 維持・回帰保護 |
| GT-R2-BUY-FLAG | FAIL | round package | C01 | upstream | round lifecycle / package context / adapter association |
| GT-R2-BUY-MENU-1 | FAIL | round package | C01 | upstream | round lifecycle / package context / adapter association |
| GT-R2-BUY-MENU-2 | FAIL | round package | C01 | upstream | round lifecycle / package context / adapter association |
| GT-R2-ASTRAL-1 | FAIL | round package | C01 | upstream | round lifecycle / package context / adapter association |
| GT-R2-ASTRAL-2 | FAIL | round package | C01 | upstream | round lifecycle / package context / adapter association |
| GT-R2-EXPANDED-MAP | FAIL | round package | C01 | upstream | round lifecycle / package context / adapter association |
| GT-R2-SPECTATOR | FAIL | round package | C01 | upstream | round lifecycle / package context / adapter association |
| OWN-R1-SELF | FAIL | live identity | C10 | direct | independent current-frame identity and view ownership coverage |
| OWN-R1-SELF-DEAD | FAIL | ownership | C11 | direct | death ownership contract producer and adapter |
| OWN-R2-SELF | FAIL | round package | C01 | upstream | round lifecycle / package context / adapter association |
| OWN-R2-SELF-DEAD | FAIL | round package | C01 | upstream | round lifecycle / package context / adapter association |
| OWN-R2-TEAMMATE | FAIL | round package | C01 | upstream | round lifecycle / package context / adapter association |
| GT-R1-SNAP-0035 | FAIL | round package | C01 | upstream | round lifecycle / package context / adapter association |
| GT-R1-SNAP-0415 | FAIL | round package | C01 | upstream | round lifecycle / package context / adapter association |
| GT-R1-SNAP-475 | FAIL | killfeed / snapshot | C12 | direct | nonself killfeed visibility evidence and trace export |
| GT-R1-SNAP-585 | FAIL | snapshot | C02 | upstream | correct state/identity evidence and snapshot admission contract |
| GT-R1-SNAP-595 | FAIL | snapshot | C02 | upstream | correct state/identity evidence and snapshot admission contract |
| GT-R1-SNAP-705 | PASS | snapshot | — | - | 維持・回帰保護 |
| GT-R1-SNAP-728 | FAIL | snapshot | C02 | upstream | correct state/identity evidence and snapshot admission contract |
| GT-R1-SNAP-733 | FAIL | temporal context | C07 | upstream | temporal input coverage diagnosis under unchanged full sampler |
| GT-R1-SNAP-734 | FAIL | snapshot | C02 | upstream | correct state/identity evidence and snapshot admission contract |
| GT-R1-SNAP-7425 | FAIL | snapshot | C02 | upstream | correct state/identity evidence and snapshot admission contract |
| GT-R1-SNAP-7438 | FAIL | snapshot | C02 | upstream | correct state/identity evidence and snapshot admission contract |
| GT-R1-SNAP-7440 | FAIL | snapshot | C02 | upstream | correct state/identity evidence and snapshot admission contract |
| GT-R1-SNAP-7445 | FAIL | temporal context | C07 | upstream | temporal input coverage diagnosis under unchanged full sampler |
| GT-R2-SNAP-820 | FAIL | round package | C01 | upstream | round lifecycle / package context / adapter association |
| GT-R2-SNAP-1050 | FAIL | round package | C01 | upstream | round lifecycle / package context / adapter association |
| GT-R2-SNAP-11145 | FAIL | round package | C01 | upstream | round lifecycle / package context / adapter association |
| GT-R2-SNAP-143 | FAIL | round package | C01 | upstream | round lifecycle / package context / adapter association |
| GT-R2-SNAP-1475 | FAIL | round package | C01 | upstream | round lifecycle / package context / adapter association |
| GT-R2-SNAP-1476 | FAIL | round package | C01 | upstream | round lifecycle / package context / adapter association |
| GT-R2-SNAP-1477 | FAIL | round package | C01 | upstream | round lifecycle / package context / adapter association |
| GT-R2-SNAP-149 | FAIL | round package | C01 | upstream | round lifecycle / package context / adapter association |
| GT-R2-SNAP-151 | FAIL | round package | C01 | upstream | round lifecycle / package context / adapter association |
| GT-R2-SNAP-170 | FAIL | round package | C01 | upstream | round lifecycle / package context / adapter association |
| GT-R1-SNAP-0035-DERIVED-zone_id | FAIL | round package | C01 | upstream | round lifecycle / package context / adapter association |
| GT-R1-SNAP-0415-DERIVED-zone_id | FAIL | round package | C01 | upstream | round lifecycle / package context / adapter association |
| GT-R2-SNAP-820-DERIVED-zone_id | FAIL | round package | C01 | upstream | round lifecycle / package context / adapter association |
| GT-R1-MUZZLE-1 | FAIL | visual event | C04 | upstream | owned HUD/weapon evidence plus visual observation producer |
| GT-R1-MUZZLE-2 | FAIL | visual event | C04 | upstream | owned HUD/weapon evidence plus visual observation producer |
| GT-R1-MUZZLE-3 | FAIL | visual event | C04 | upstream | owned HUD/weapon evidence plus visual observation producer |
| event_count_constraints-000 | FAIL | round start/end | C03 | direct | round phase evidence and temporal lifecycle |
| event_count_constraints-001 | FAIL | kill/death/combat event | C05 | direct | current-frame death evidence plus semantic attribute producer |
| event_count_constraints-002 | FAIL | round start/end | C03 | direct | round phase evidence and temporal lifecycle |
| event_count_constraints-003 | FAIL | event detection | C13 | upstream | qualified shot inputs and event aggregation |
| event_count_constraints-004 | FAIL | round package | C01 | upstream | round lifecycle / package context / adapter association |
| event_count_constraints-005 | FAIL | round package | C01 | upstream | round lifecycle / package context / adapter association |
| event_count_constraints-006 | PASS | round end | — | - | 維持・回帰保護 |
| NEG-REMOTE-R1A | PASS | safety / negative assertion | — | - | 維持・回帰保護 |
| NEG-REMOTE-R1B | PASS | safety / negative assertion | — | - | 維持・回帰保護 |
| NEG-REMOTE-R2A | PASS | safety / negative assertion | — | - | 維持・回帰保護 |
| NEG-REMOTE-R2B | PASS | safety / negative assertion | — | - | 維持・回帰保護 |
| NEG-ASTRAL-NOT-SMOKE | PASS | safety / negative assertion | — | - | 維持・回帰保護 |
| NEG-SMOKE-NOT-ASTRAL | PASS | safety / negative assertion | — | - | 維持・回帰保護 |
| NEG-SMOKE-WORLD-SPOT | PASS | safety / negative assertion | — | - | 維持・回帰保護 |
| NEG-NONSELF-KILLFEED | PASS | safety / negative assertion | — | - | 維持・回帰保護 |
| NEG-RELOAD-NOT-SHOT | PASS | safety / negative assertion | — | - | 維持・回帰保護 |
| NEG-BUY-MENU-1 | PASS | safety / negative assertion | — | - | 維持・回帰保護 |
| NEG-BUY-MENU-2 | PASS | safety / negative assertion | — | - | 維持・回帰保護 |
| NEG-SPECTATOR-COUNT-TEXT | PASS | safety / negative assertion | — | - | 維持・回帰保護 |
| NEG-DEAD-PLAYER-MECHANICS | PASS | safety / negative assertion | — | - | 維持・回帰保護 |
| NEG-EXPANDED-MAP-MECHANICS | PASS | safety / negative assertion | — | - | 維持・回帰保護 |
| NEG-SPECTATOR-POISON-151 | PASS | safety / negative assertion | — | - | 維持・回帰保護 |
| NEG-SPECTATOR-POISON-170 | PASS | safety / negative assertion | — | - | 維持・回帰保護 |
| NEG-STALE-COMBAT-REPORT | PASS | safety / negative assertion | — | - | 維持・回帰保護 |
| NEG-R2-NO-ROUND-END | PASS | safety / negative assertion | — | - | 維持・回帰保護 |
| NEG-SAME-ZONE-CALLOUT-CHANGE | PASS | safety / negative assertion | — | - | 維持・回帰保護 |
| NEG-CONTENT-JUMP-SPAN | PASS | safety / negative assertion | — | - | 維持・回帰保護 |

## 4. 55 FAIL classification

expectedはpackの定義そのままです。actualの`missing`はフィールド不在でありnull／falseと同一視しません。元の全定義とactualの詳細は`e2e_reports/match_001/failure_analysis.json`に保存しました。各行の同一原因ID、実装状態、fix targetはgroup headingに共通です。各FAILのPASS確度はpossible（全predicateを満たす実画像証拠が必要）、無条件guaranteed増加は0です。

### C01: round_package_scope（29件）

Category: round package。実装状態: upstream依存。Fix target: round lifecycle / package context / adapter association。

1 partial package [7.369336,171.002669] mapped exclusively to sample_round_1; no sample_round_2; pre-window R1 observations excluded。

| Assertion / 目的 / PTS・範囲 | expected | actual / failure field・reason | upstream / 追加条件 |
| --- | --- | --- | --- |
| GT-R2-ROUND-START<br>round_start<br>[111.38000000000001,111.5] | `{"id":"GT-R2-ROUND-START","round_id":"sample_round_2","type":"round_start","actor":"system","acceptance_window":[111.38000000000001,111.5],"facts":{"score_before":"0-2"},"required_event_attributes":{}}` | {"matching_type_actor_time_count":0}<br>fields: event.round_start<br>missing_point:GT-R2-ROUND-START | round_boundary, round_package_scope<br>missing_point; event_actor_contract |
| GT-R2-DEATH<br>player_death<br>[147.57,147.75] | `{"id":"GT-R2-DEATH","round_id":"sample_round_2","type":"player_death","actor":"player","acceptance_window":[147.57,147.75],"facts":{"victim_name":"sharkman","killer_agent":"Fade","combat_report_damage_received":194},"required_event_attributes":{"victim_name":"sharkman","killer_agent":"Fade","combat_report_damage_received":194}}` | {"matching_type_actor_time_count":0}<br>fields: event.player_death<br>missing_point:GT-R2-DEATH | current_frame_death_evidence, death_attributes, round_package_scope<br>missing_point; event_attribute_contract |
| GT-R2-BUY-FLAG<br>buy_phase_banner<br>[82.0,111.4] | `{"id":"GT-R2-BUY-FLAG","round_id":"sample_round_2","state_class":"flag","state":"buy_phase_banner","subtype":null,"core_interval":[82.0,111.4],"outer_interval":[81.5,111.45],"min_core_coverage":0.9,"exhaustive":false}` | coverage=0.00000 / required=0.9; round-neutral=0.00000<br>fields: coverage.buy_phase_banner<br>state_coverage:GT-R2-BUY-FLAG | state_evidence, round_package_scope<br>state_coverage |
| GT-R2-BUY-MENU-1<br>buy_menu_open<br>[83.352669,91.402669] | `{"id":"GT-R2-BUY-MENU-1","round_id":"sample_round_2","state_class":"primary_state","state":"buy_menu_open","subtype":null,"core_interval":[83.352669,91.402669],"outer_interval":[83.252669,91.452669],"min_core_coverage":0.9,"exhaustive":true,"edge_brackets":{"start":{"last_absent_sec":83.252669,"first_present_sec":83.352669},"end":{"last_present_sec":91.402669,"first_absent_sec":91.452669}}}` | coverage=0.00000 / required=0.9; round-neutral=0.99172<br>fields: coverage.buy_menu_open<br>state_coverage:GT-R2-BUY-MENU-1 | state_evidence, round_package_scope<br>state_overreach,state_start_edge,state_end_edge |
| GT-R2-BUY-MENU-2<br>buy_menu_open<br>[108.052669,110.802669] | `{"id":"GT-R2-BUY-MENU-2","round_id":"sample_round_2","state_class":"primary_state","state":"buy_menu_open","subtype":null,"core_interval":[108.052669,110.802669],"outer_interval":[107.952669,110.852669],"min_core_coverage":0.9,"exhaustive":true,"edge_brackets":{"start":{"last_absent_sec":107.952669,"first_present_sec":108.052669},"end":{"last_present_sec":110.802669,"first_absent_sec":110.852669}}}` | coverage=0.00000 / required=0.9; round-neutral=0.56970<br>fields: coverage.buy_menu_open<br>state_coverage:GT-R2-BUY-MENU-2 | state_evidence, round_package_scope<br>state_coverage,state_start_edge,state_end_edge |
| GT-R2-ASTRAL-1<br>remote_control_view<br>[111.302669,112.402669] | `{"id":"GT-R2-ASTRAL-1","round_id":"sample_round_2","state_class":"primary_state","state":"remote_control_view","subtype":"astra_astral","core_interval":[111.302669,112.402669],"outer_interval":[111.102669,112.502669],"min_core_coverage":0.9,"exhaustive":true,"edge_brackets":{"start":{"last_absent_sec":111.102669,"first_present_sec":111.302669},"end":{"last_present_sec":112.402669,"first_absent_sec":112.502669}}}` | coverage=0.00000 / required=0.9; round-neutral=0.00000<br>fields: coverage.remote_control_view<br>state_coverage:GT-R2-ASTRAL-1 | state_evidence, round_package_scope<br>state_coverage |
| GT-R2-ASTRAL-2<br>remote_control_view<br>[115.602669,120.102669] | `{"id":"GT-R2-ASTRAL-2","round_id":"sample_round_2","state_class":"primary_state","state":"remote_control_view","subtype":"astra_astral","core_interval":[115.602669,120.102669],"outer_interval":[115.502669,120.202669],"min_core_coverage":0.9,"exhaustive":true,"edge_brackets":{"start":{"last_absent_sec":115.502669,"first_present_sec":115.602669},"end":{"last_present_sec":120.102669,"first_absent_sec":120.202669}}}` | coverage=0.00000 / required=0.9; round-neutral=0.00000<br>fields: coverage.remote_control_view<br>state_coverage:GT-R2-ASTRAL-2 | state_evidence, round_package_scope<br>state_coverage |
| GT-R2-EXPANDED-MAP<br>expanded_tactical_map<br>[149.0,150.5] | `{"id":"GT-R2-EXPANDED-MAP","round_id":"sample_round_2","state_class":"primary_state","state":"expanded_tactical_map","subtype":null,"core_interval":[149.0,150.5],"outer_interval":[148.8,150.8],"min_core_coverage":0.7,"exhaustive":true}` | coverage=0.00000 / required=0.7; round-neutral=0.00000<br>fields: coverage.expanded_tactical_map<br>state_coverage:GT-R2-EXPANDED-MAP | state_evidence, round_package_scope<br>state_coverage |
| GT-R2-SPECTATOR<br>spectator_first_person<br>[151.0,171.0] | `{"id":"GT-R2-SPECTATOR","round_id":"sample_round_2","state_class":"primary_state","state":"spectator_first_person","subtype":null,"core_interval":[151.0,171.0],"outer_interval":[150.5,171.019336],"min_core_coverage":0.9,"exhaustive":true}` | coverage=0.00000 / required=0.9; round-neutral=0.29167<br>fields: coverage.spectator_first_person<br>state_coverage:GT-R2-SPECTATOR | state_evidence, round_package_scope<br>state_coverage |
| OWN-R2-SELF<br>self<br>[82.0,147.6] | `{"id":"OWN-R2-SELF","round_id":"sample_round_2","owner":"self","core_interval":[82.0,147.6],"outer_interval":[81.5,147.7],"min_core_coverage":0.9}` | coverage=0.00000 / required=0.9; round-neutral=0.05462<br>fields: coverage.self<br>ownership_coverage:OWN-R2-SELF | state_evidence, round_package_scope<br>ownership_coverage; ownership_contract |
| OWN-R2-SELF-DEAD<br>self_dead_ui<br>[147.7,150.0] | `{"id":"OWN-R2-SELF-DEAD","round_id":"sample_round_2","owner":"self_dead_ui","core_interval":[147.7,150.0],"outer_interval":[147.7,150.5],"min_core_coverage":0.9}` | coverage=0.00000 / required=0.9; round-neutral=0.00000<br>fields: coverage.self_dead_ui<br>ownership_coverage:OWN-R2-SELF-DEAD | state_evidence, round_package_scope<br>ownership_coverage; ownership_contract |
| OWN-R2-TEAMMATE<br>teammate_spectated<br>[150.5,171.0] | `{"id":"OWN-R2-TEAMMATE","round_id":"sample_round_2","owner":"teammate_spectated","core_interval":[150.5,171.0],"outer_interval":[150.0,171.019336],"min_core_coverage":0.9}` | coverage=0.00000 / required=0.9; round-neutral=0.28455<br>fields: coverage.teammate_spectated<br>ownership_coverage:OWN-R2-TEAMMATE | state_evidence, round_package_scope<br>ownership_coverage; ownership_contract |
| GT-R1-SNAP-0035<br>required_snapshots<br>3.5 ±0.05 | `{"primary_state":"live_first_person","buy_phase_banner":true,"player_alive":true,"location_label_raw":"A ロビー"}` | snapshot candidates=0; fields={"primary_state":{"present":false,"value":null},"buy_phase_banner":{"present":false,"value":null},"player_alive":{"present":false,"value":null},"location_label_raw":{"present":false,"value":null}}; native samples=2 / qualified=0<br>fields: primary_state, buy_phase_banner, player_alive, location_label_raw<br>missing_snapshot:GT-R1-SNAP-0035 | round_package_scope, hud_confidence_gate, snapshot_materialization, primary_state, buy_phase_banner, player_alive, location_label_raw<br> |
| GT-R1-SNAP-0415<br>required_snapshots<br>4.15 ±0.05 | `{"primary_state":"live_first_person","buy_phase_banner":false,"player_alive":true,"score_player":0,"score_enemy":1,"game_timer_display":"1:39","location_label_raw":"A メイン"}` | snapshot candidates=0; fields={"primary_state":{"present":false,"value":null},"buy_phase_banner":{"present":false,"value":null},"player_alive":{"present":false,"value":null},"score_player":{"present":false,"value":null},"score_enemy":{"present":false,"value":null},"game_timer_display":{"present":false,"value":null},"location_label_raw":{"present":false,"value":null}}; native samples=2 / qualified=0<br>fields: primary_state, buy_phase_banner, player_alive, score_player, score_enemy, game_timer_display, location_label_raw<br>missing_snapshot:GT-R1-SNAP-0415 | round_package_scope, hud_confidence_gate, snapshot_materialization, primary_state, buy_phase_banner, player_alive, score_player, score_enemy, game_timer_display, location_label_raw<br>missing_trace_fields |
| GT-R2-SNAP-820<br>required_snapshots<br>82.0 ±0.1 | `{"primary_state":"live_first_person","buy_phase_banner":true,"player_alive":true,"player_hp":100,"location_label_raw":"アタック側スポーン","combat_report_visible":true}` | snapshot candidates=0; fields={"primary_state":{"present":false,"value":null},"buy_phase_banner":{"present":false,"value":null},"player_alive":{"present":false,"value":null},"player_hp":{"present":false,"value":null},"location_label_raw":{"present":false,"value":null},"combat_report_visible":{"present":false,"value":null}}; native samples=1 / qualified=0<br>fields: primary_state, buy_phase_banner, player_alive, player_hp, location_label_raw, combat_report_visible<br>missing_snapshot:GT-R2-SNAP-820 | round_package_scope, hud_confidence_gate, snapshot_materialization, primary_state, buy_phase_banner, player_alive, player_hp, location_label_raw, combat_report_visible<br>missing_snapshot |
| GT-R2-SNAP-1050<br>required_snapshots<br>105.0 ±0.1 | `{"primary_state":"live_first_person","buy_phase_banner":true,"player_alive":true,"combat_report_visible":true}` | snapshot candidates=0; fields={"primary_state":{"present":false,"value":null},"buy_phase_banner":{"present":false,"value":null},"player_alive":{"present":false,"value":null},"combat_report_visible":{"present":false,"value":null}}; native samples=4 / qualified=0<br>fields: primary_state, buy_phase_banner, player_alive, combat_report_visible<br>missing_snapshot:GT-R2-SNAP-1050 | round_package_scope, hud_confidence_gate, snapshot_materialization, primary_state, buy_phase_banner, player_alive, combat_report_visible<br>missing_snapshot |
| GT-R2-SNAP-11145<br>required_snapshots<br>111.45 ±0.05 | `{"buy_phase_banner":false,"player_alive":true,"score_player":0,"score_enemy":2,"game_timer_display":"1:40"}` | snapshot candidates=0; fields={"buy_phase_banner":{"present":false,"value":null},"player_alive":{"present":false,"value":null},"score_player":{"present":false,"value":null},"score_enemy":{"present":false,"value":null},"game_timer_display":{"present":false,"value":null}}; native samples=2 / qualified=0<br>fields: buy_phase_banner, player_alive, score_player, score_enemy, game_timer_display<br>missing_snapshot:GT-R2-SNAP-11145 | round_package_scope, hud_confidence_gate, snapshot_materialization, buy_phase_banner, player_alive, score_player, score_enemy, game_timer_display<br>missing_snapshot; missing_trace_fields |
| GT-R2-SNAP-143<br>required_snapshots<br>143.0 ±0.1 | `{"primary_state":"live_first_person","player_alive":true,"player_hp":80}` | snapshot candidates=0; fields={"primary_state":{"present":false,"value":null},"player_alive":{"present":false,"value":null},"player_hp":{"present":false,"value":null}}; native samples=6 / qualified=0<br>fields: primary_state, player_alive, player_hp<br>missing_snapshot:GT-R2-SNAP-143 | round_package_scope, hud_confidence_gate, snapshot_materialization, primary_state, player_alive, player_hp<br>missing_snapshot |
| GT-R2-SNAP-1475<br>required_snapshots<br>147.5 ±0.05 | `{"primary_state":"live_first_person","player_alive":true,"player_hp":80}` | snapshot candidates=0; fields={"primary_state":{"present":false,"value":null},"player_alive":{"present":false,"value":null},"player_hp":{"present":false,"value":null}}; native samples=2 / qualified=0<br>fields: primary_state, player_alive, player_hp<br>missing_snapshot:GT-R2-SNAP-1475 | round_package_scope, hud_confidence_gate, snapshot_materialization, primary_state, player_alive, player_hp<br>missing_snapshot |
| GT-R2-SNAP-1476<br>required_snapshots<br>147.6 ±0.05 | `{"primary_state":"live_first_person","player_alive":true,"player_hp":22}` | snapshot candidates=0; fields={"primary_state":{"present":false,"value":null},"player_alive":{"present":false,"value":null},"player_hp":{"present":false,"value":null}}; native samples=3 / qualified=0<br>fields: primary_state, player_alive, player_hp<br>missing_snapshot:GT-R2-SNAP-1476 | round_package_scope, hud_confidence_gate, snapshot_materialization, primary_state, player_alive, player_hp<br>missing_snapshot |
| GT-R2-SNAP-1477<br>required_snapshots<br>147.7 ±0.05 | `{"player_alive":false,"combat_report_visible":true}` | snapshot candidates=0; fields={"player_alive":{"present":false,"value":null},"combat_report_visible":{"present":false,"value":null}}; native samples=1 / qualified=0<br>fields: player_alive, combat_report_visible<br>missing_snapshot:GT-R2-SNAP-1477 | round_package_scope, hud_confidence_gate, snapshot_materialization, player_alive, combat_report_visible<br>missing_snapshot |
| GT-R2-SNAP-149<br>required_snapshots<br>149.0 ±0.1 | `{"primary_state":"expanded_tactical_map","player_alive":false,"combat_report_visible":true}` | snapshot candidates=0; fields={"primary_state":{"present":false,"value":null},"player_alive":{"present":false,"value":null},"combat_report_visible":{"present":false,"value":null}}; native samples=2 / qualified=0<br>fields: primary_state, player_alive, combat_report_visible<br>missing_snapshot:GT-R2-SNAP-149 | round_package_scope, hud_confidence_gate, snapshot_materialization, primary_state, player_alive, combat_report_visible<br>missing_snapshot |
| GT-R2-SNAP-151<br>required_snapshots<br>151.0 ±0.1 | `{"primary_state":"spectator_first_person","player_alive":false,"view_owner":"teammate_spectated","spectated_name":"チェンバーのおチェンバー","spectated_hp":100,"spectated_ammo_mag":21,"spectated_ammo_reserve":50,"spectated_weapon":"Vandal","combat_report_visible":true,"spectated_location_label_raw":"中央ファウンテン"}` | snapshot candidates=0; fields={"primary_state":{"present":false,"value":null},"player_alive":{"present":false,"value":null},"view_owner":{"present":false,"value":null},"spectated_name":{"present":false,"value":null},"spectated_hp":{"present":false,"value":null},"spectated_ammo_mag":{"present":false,"value":null},"spectated_ammo_reserve":{"present":false,"value":null},"spectated_weapon":{"present":false,"value":null},"combat_report_visible":{"present":false,"value":null},"spectated_location_label_raw":{"present":false,"value":null}}; native samples=5 / qualified=0<br>fields: primary_state, player_alive, view_owner, spectated_name, spectated_hp, spectated_ammo_mag, spectated_ammo_reserve, spectated_weapon, combat_report_visible, spectated_location_label_raw<br>missing_snapshot:GT-R2-SNAP-151 | round_package_scope, hud_confidence_gate, snapshot_materialization, primary_state, player_alive, view_owner, spectated_name, spectated_hp, spectated_ammo_mag, spectated_ammo_reserve, spectated_weapon, combat_report_visible, spectated_location_label_raw<br>missing_snapshot; missing_trace_fields |
| GT-R2-SNAP-170<br>required_snapshots<br>170.0 ±0.1 | `{"primary_state":"spectator_first_person","player_alive":false,"view_owner":"teammate_spectated","spectated_name":"TRIGGER","spectated_hp":85,"spectated_ammo_mag":22,"spectated_ammo_reserve":31,"spectated_weapon":"Vandal","muzzle_flash_visible":true,"combat_report_visible":true,"spectated_location_label_raw":"Bメイン"}` | snapshot candidates=0; fields={"primary_state":{"present":false,"value":null},"player_alive":{"present":false,"value":null},"view_owner":{"present":false,"value":null},"spectated_name":{"present":false,"value":null},"spectated_hp":{"present":false,"value":null},"spectated_ammo_mag":{"present":false,"value":null},"spectated_ammo_reserve":{"present":false,"value":null},"spectated_weapon":{"present":false,"value":null},"muzzle_flash_visible":{"present":false,"value":null},"combat_report_visible":{"present":false,"value":null},"spectated_location_label_raw":{"present":false,"value":null}}; native samples=7 / qualified=6<br>fields: primary_state, player_alive, view_owner, spectated_name, spectated_hp, spectated_ammo_mag, spectated_ammo_reserve, spectated_weapon, muzzle_flash_visible, combat_report_visible, spectated_location_label_raw<br>missing_snapshot:GT-R2-SNAP-170 | round_package_scope, hud_confidence_gate, snapshot_materialization, primary_state, player_alive, view_owner, spectated_name, spectated_hp, spectated_ammo_mag, spectated_ammo_reserve, spectated_weapon, muzzle_flash_visible, combat_report_visible, spectated_location_label_raw<br>player_alive,spectated_name,spectated_hp,spectated_ammo_mag,spectated_ammo_reserve,spectated_weapon,muzzle_flash_visible,spectated_location_label_raw; missing_trace_fields |
| GT-R1-SNAP-0035-DERIVED-zone_id<br>derived_assertions<br>3.5 ±0.05 | `"summit_a_approach"` | snapshot candidates=0; fields={"zone_id":{"present":false,"value":null}}; native samples=2 / qualified=0<br>fields: zone_id<br>missing_derived_snapshot:GT-R1-SNAP-0035-DERIVED-zone_id | round_package_scope, hud_confidence_gate, snapshot_materialization, zone_id<br> |
| GT-R1-SNAP-0415-DERIVED-zone_id<br>derived_assertions<br>4.15 ±0.05 | `"summit_a_approach"` | snapshot candidates=0; fields={"zone_id":{"present":false,"value":null}}; native samples=2 / qualified=0<br>fields: zone_id<br>missing_derived_snapshot:GT-R1-SNAP-0415-DERIVED-zone_id | round_package_scope, hud_confidence_gate, snapshot_materialization, zone_id<br> |
| GT-R2-SNAP-820-DERIVED-zone_id<br>derived_assertions<br>82.0 ±0.1 | `"summit_attacker_spawn"` | snapshot candidates=0; fields={"zone_id":{"present":false,"value":null}}; native samples=1 / qualified=0<br>fields: zone_id<br>missing_derived_snapshot:GT-R2-SNAP-820-DERIVED-zone_id | round_package_scope, hud_confidence_gate, snapshot_materialization, zone_id<br>missing_derived_snapshot |
| event_count_constraints-004<br>round_start<br>sample_round_2全package | `{"type":"round_start","actor":"system","min":1,"max":1,"round_id":"sample_round_2"}` | {"count":0}<br>fields: count.round_start<br>count:sample_round_2:round_start | event_producer, round_package_scope<br>count:round_start; event_actor_contract |
| event_count_constraints-005<br>player_death<br>sample_round_2全package | `{"type":"player_death","actor":"player","min":1,"max":1,"round_id":"sample_round_2"}` | {"count":0}<br>fields: count.player_death<br>count:sample_round_2:player_death | event_producer, round_package_scope<br>count:player_death; event_attribute_contract |

### C02: snapshot_hud_confidence（7件）

Category: snapshot。実装状態: upstream依存。Fix target: correct state/identity evidence and snapshot admission contract。

No HUD observation with hud_confidence>=0.65 inside assertion tolerance; builder admits none。

| Assertion / 目的 / PTS・範囲 | expected | actual / failure field・reason | upstream / 追加条件 |
| --- | --- | --- | --- |
| GT-R1-SNAP-585<br>required_snapshots<br>58.5 ±0.1 | `{"primary_state":"live_first_person","vision_obscured_smoke":false}` | snapshot candidates=0; fields={"primary_state":{"present":false,"value":null},"vision_obscured_smoke":{"present":false,"value":null}}; native samples=6 / qualified=0<br>fields: primary_state, vision_obscured_smoke<br>missing_snapshot:GT-R1-SNAP-585 | round_package_scope, hud_confidence_gate, snapshot_materialization, primary_state, vision_obscured_smoke<br> |
| GT-R1-SNAP-595<br>required_snapshots<br>59.5 ±0.1 | `{"primary_state":"live_first_person","vision_obscured_smoke":true,"remote_control_subtype":null}` | snapshot candidates=0; fields={"primary_state":{"present":false,"value":null},"vision_obscured_smoke":{"present":false,"value":null},"remote_control_subtype":{"present":false,"value":null}}; native samples=10 / qualified=0<br>fields: primary_state, vision_obscured_smoke, remote_control_subtype<br>missing_snapshot:GT-R1-SNAP-595 | round_package_scope, hud_confidence_gate, snapshot_materialization, primary_state, vision_obscured_smoke, remote_control_subtype<br> |
| GT-R1-SNAP-728<br>required_snapshots<br>72.8 ±0.08 | `{"primary_state":"live_first_person","player_alive":true,"ammo_mag":9,"ammo_reserve":36,"reload_animation_visible":true}` | snapshot candidates=0; fields={"primary_state":{"present":false,"value":null},"player_alive":{"present":false,"value":null},"ammo_mag":{"present":false,"value":null},"ammo_reserve":{"present":false,"value":null},"reload_animation_visible":{"present":false,"value":null}}; native samples=1 / qualified=0<br>fields: primary_state, player_alive, ammo_mag, ammo_reserve, reload_animation_visible<br>missing_snapshot:GT-R1-SNAP-728 | round_package_scope, hud_confidence_gate, snapshot_materialization, primary_state, player_alive, ammo_mag, ammo_reserve, reload_animation_visible<br>missing_trace_fields |
| GT-R1-SNAP-734<br>required_snapshots<br>73.4 ±0.08 | `{"primary_state":"live_first_person","player_alive":true,"ammo_mag":12,"ammo_reserve":33,"reload_animation_visible":false}` | snapshot candidates=0; fields={"primary_state":{"present":false,"value":null},"player_alive":{"present":false,"value":null},"ammo_mag":{"present":false,"value":null},"ammo_reserve":{"present":false,"value":null},"reload_animation_visible":{"present":false,"value":null}}; native samples=1 / qualified=0<br>fields: primary_state, player_alive, ammo_mag, ammo_reserve, reload_animation_visible<br>missing_snapshot:GT-R1-SNAP-734 | round_package_scope, hud_confidence_gate, snapshot_materialization, primary_state, player_alive, ammo_mag, ammo_reserve, reload_animation_visible<br>missing_trace_fields |
| GT-R1-SNAP-7425<br>required_snapshots<br>74.25 ±0.05 | `{"primary_state":"live_first_person","player_alive":true,"player_hp":48,"muzzle_flash_visible":true,"location_label_raw":"中央ファウンテン","spectator_primary_state":false}` | snapshot candidates=0; fields={"primary_state":{"present":false,"value":null},"player_alive":{"present":false,"value":null},"player_hp":{"present":false,"value":null},"muzzle_flash_visible":{"present":false,"value":null},"location_label_raw":{"present":false,"value":null},"spectator_primary_state":{"present":false,"value":null}}; native samples=2 / qualified=0<br>fields: primary_state, player_alive, player_hp, muzzle_flash_visible, location_label_raw, spectator_primary_state<br>missing_snapshot:GT-R1-SNAP-7425 | round_package_scope, hud_confidence_gate, snapshot_materialization, primary_state, player_alive, player_hp, muzzle_flash_visible, location_label_raw, spectator_primary_state<br>missing_trace_fields |
| GT-R1-SNAP-7438<br>required_snapshots<br>74.38 ±0.03 | `{"primary_state":"live_first_person","player_alive":true,"muzzle_flash_visible":true,"game_timer_display":"0:29","score_player":0,"score_enemy":1}` | snapshot candidates=0; fields={"primary_state":{"present":false,"value":null},"player_alive":{"present":false,"value":null},"muzzle_flash_visible":{"present":false,"value":null},"game_timer_display":{"present":false,"value":null},"score_player":{"present":false,"value":null},"score_enemy":{"present":false,"value":null}}; native samples=1 / qualified=0<br>fields: primary_state, player_alive, muzzle_flash_visible, game_timer_display, score_player, score_enemy<br>missing_snapshot:GT-R1-SNAP-7438 | round_package_scope, hud_confidence_gate, snapshot_materialization, primary_state, player_alive, muzzle_flash_visible, game_timer_display, score_player, score_enemy<br>missing_trace_fields |
| GT-R1-SNAP-7440<br>required_snapshots<br>74.4 ±0.03 | `{"player_alive":false,"combat_report_visible":true}` | snapshot candidates=0; fields={"player_alive":{"present":false,"value":null},"combat_report_visible":{"present":false,"value":null}}; native samples=1 / qualified=0<br>fields: player_alive, combat_report_visible<br>missing_snapshot:GT-R1-SNAP-7440 | round_package_scope, hud_confidence_gate, snapshot_materialization, player_alive, combat_report_visible<br> |

### C03: round_boundary（4件）

Category: round start/end。実装状態: 部分実装。Fix target: round phase evidence and temporal lifecycle。

No round_start/end HUD events; missing banner/score context for temporal detector。

| Assertion / 目的 / PTS・範囲 | expected | actual / failure field・reason | upstream / 追加条件 |
| --- | --- | --- | --- |
| GT-R1-ROUND-START<br>round_start<br>[4.08,4.2] | `{"id":"GT-R1-ROUND-START","round_id":"sample_round_1","type":"round_start","actor":"system","acceptance_window":[4.08,4.2],"facts":{"score_before":"0-1"},"required_event_attributes":{}}` | {"matching_type_actor_time_count":0}<br>fields: event.round_start<br>missing_point:GT-R1-ROUND-START | round_boundary, round_package_scope<br>event_actor_contract |
| GT-R1-ROUND-END<br>round_end<br>[74.387,74.483] | `{"id":"GT-R1-ROUND-END","round_id":"sample_round_1","type":"round_end","actor":"system","acceptance_window":[74.387,74.483],"facts":{"ace_team":"enemy","score_before":"0-1","score_after_confirmed_after_discontinuity":"0-2"},"required_event_attributes":{}}` | {"matching_type_actor_time_count":0}<br>fields: event.round_end<br>missing_point:GT-R1-ROUND-END | round_boundary, round_package_scope<br>event_actor_contract |
| event_count_constraints-000<br>round_start<br>sample_round_1全package | `{"type":"round_start","actor":"system","min":1,"max":1,"round_id":"sample_round_1"}` | {"count":0}<br>fields: count.round_start<br>count:sample_round_1:round_start | event_producer, round_package_scope<br>event_actor_contract |
| event_count_constraints-002<br>round_end<br>sample_round_1全package | `{"type":"round_end","actor":"system","min":1,"max":1,"round_id":"sample_round_1"}` | {"count":0}<br>fields: count.round_end<br>count:sample_round_1:round_end | event_producer, round_package_scope<br>event_actor_contract |

### C04: weapon_visual_input_guard（3件）

Category: visual event。実装状態: upstream依存。Fix target: owned HUD/weapon evidence plus visual observation producer。

No eligible player muzzle observation in required time; HUD identity unknown and visual evidence insufficient。

| Assertion / 目的 / PTS・範囲 | expected | actual / failure field・reason | upstream / 追加条件 |
| --- | --- | --- | --- |
| GT-R1-MUZZLE-1<br>muzzle_flash<br>73.95 ±0.08 | `{"id":"GT-R1-MUZZLE-1","round_id":"sample_round_1","observation":"muzzle_flash","actor":"player","time_sec":73.95,"tolerance_sec":0.08}` | {"matching_count":0}<br>fields: visual.muzzle_flash<br>missing_visual_observation:GT-R1-MUZZLE-1 | player_mechanics_eligibility, weapon_visual_evidence, round_package_scope<br> |
| GT-R1-MUZZLE-2<br>muzzle_flash<br>74.25 ±0.08 | `{"id":"GT-R1-MUZZLE-2","round_id":"sample_round_1","observation":"muzzle_flash","actor":"player","time_sec":74.25,"tolerance_sec":0.08}` | {"matching_count":0}<br>fields: visual.muzzle_flash<br>missing_visual_observation:GT-R1-MUZZLE-2 | player_mechanics_eligibility, weapon_visual_evidence, round_package_scope<br> |
| GT-R1-MUZZLE-3<br>muzzle_flash<br>74.38 ±0.08 | `{"id":"GT-R1-MUZZLE-3","round_id":"sample_round_1","observation":"muzzle_flash","actor":"player","time_sec":74.38,"tolerance_sec":0.08}` | {"matching_count":0}<br>fields: visual.muzzle_flash<br>missing_visual_observation:GT-R1-MUZZLE-3 | player_mechanics_eligibility, weapon_visual_evidence, round_package_scope<br> |

### C05: player_death_semantics（2件）

Category: kill/death/combat event。実装状態: 部分実装。Fix target: current-frame death evidence plus semantic attribute producer。

No player_death event; death transition evidence and victim/killer/report attributes unavailable。

| Assertion / 目的 / PTS・範囲 | expected | actual / failure field・reason | upstream / 追加条件 |
| --- | --- | --- | --- |
| GT-R1-DEATH<br>player_death<br>[74.35,74.45] | `{"id":"GT-R1-DEATH","round_id":"sample_round_1","type":"player_death","actor":"player","acceptance_window":[74.35,74.45],"facts":{"victim_name":"sharkman","killer_agent":"Fade","combat_report_damage_received":130},"required_event_attributes":{"victim_name":"sharkman","killer_agent":"Fade","combat_report_damage_received":130}}` | {"matching_type_actor_time_count":0}<br>fields: event.player_death<br>missing_point:GT-R1-DEATH | current_frame_death_evidence, death_attributes, round_package_scope<br>event_attribute_contract |
| event_count_constraints-001<br>player_death<br>sample_round_1全package | `{"type":"player_death","actor":"player","min":1,"max":1,"round_id":"sample_round_1"}` | {"count":0}<br>fields: count.player_death<br>count:sample_round_1:player_death | event_producer, round_package_scope<br>event_attribute_contract |

### C06: astra_evidence（2件）

Category: remote state。実装状態: 認識失敗。Fix target: Astra compound current-frame evidence。

remote_control_view/astra_astral absent; existing feature/classifier evidence not qualified。

| Assertion / 目的 / PTS・範囲 | expected | actual / failure field・reason | upstream / 追加条件 |
| --- | --- | --- | --- |
| GT-R1-ASTRAL-1<br>remote_control_view<br>[10.202669,12.102669] | `{"id":"GT-R1-ASTRAL-1","round_id":"sample_round_1","state_class":"primary_state","state":"remote_control_view","subtype":"astra_astral","core_interval":[10.202669,12.102669],"outer_interval":[10.102669,12.202669],"min_core_coverage":0.9,"exhaustive":true,"edge_brackets":{"start":{"last_absent_sec":10.102669,"first_present_sec":10.202669},"end":{"last_present_sec":12.102669,"first_absent_sec":12.202669}}}` | coverage=0.00000 / required=0.9; round-neutral=0.00000<br>fields: coverage.remote_control_view<br>state_coverage:GT-R1-ASTRAL-1 | state_evidence, round_package_scope<br> |
| GT-R1-ASTRAL-2<br>remote_control_view<br>[16.502669,28.402669] | `{"id":"GT-R1-ASTRAL-2","round_id":"sample_round_1","state_class":"primary_state","state":"remote_control_view","subtype":"astra_astral","core_interval":[16.502669,28.402669],"outer_interval":[16.402669,28.502669],"min_core_coverage":0.9,"exhaustive":true,"edge_brackets":{"start":{"last_absent_sec":16.402669,"first_present_sec":16.502669},"end":{"last_present_sec":28.402669,"first_absent_sec":28.502669}}}` | coverage=0.00000 / required=0.9; round-neutral=0.00000<br>fields: coverage.remote_control_view<br>state_coverage:GT-R1-ASTRAL-2 | state_evidence, round_package_scope<br> |

### C07: native_sample_tolerance（2件）

Category: temporal context。実装状態: upstream依存。Fix target: temporal input coverage diagnosis under unchanged full sampler。

No analyzed native HUD sample inside required tolerance; cannot fix by changing returned recognition value alone。

| Assertion / 目的 / PTS・範囲 | expected | actual / failure field・reason | upstream / 追加条件 |
| --- | --- | --- | --- |
| GT-R1-SNAP-733<br>required_snapshots<br>73.3 ±0.08 | `{"primary_state":"live_first_person","player_alive":true,"ammo_mag":9,"ammo_reserve":36,"reload_animation_visible":true}` | snapshot candidates=0; fields={"primary_state":{"present":false,"value":null},"player_alive":{"present":false,"value":null},"ammo_mag":{"present":false,"value":null},"ammo_reserve":{"present":false,"value":null},"reload_animation_visible":{"present":false,"value":null}}; native samples=0 / qualified=0<br>fields: primary_state, player_alive, ammo_mag, ammo_reserve, reload_animation_visible<br>missing_snapshot:GT-R1-SNAP-733 | round_package_scope, hud_confidence_gate, snapshot_materialization, primary_state, player_alive, ammo_mag, ammo_reserve, reload_animation_visible<br>missing_trace_fields |
| GT-R1-SNAP-7445<br>required_snapshots<br>74.45 ±0.03 | `{"player_alive":false,"combat_report_visible":true,"game_timer_display":"0:06","score_player":0,"score_enemy":2}` | snapshot candidates=0; fields={"player_alive":{"present":false,"value":null},"combat_report_visible":{"present":false,"value":null},"game_timer_display":{"present":false,"value":null},"score_player":{"present":false,"value":null},"score_enemy":{"present":false,"value":null}}; native samples=0 / qualified=0<br>fields: player_alive, combat_report_visible, game_timer_display, score_player, score_enemy<br>missing_snapshot:GT-R1-SNAP-7445 | round_package_scope, hud_confidence_gate, snapshot_materialization, player_alive, combat_report_visible, game_timer_display, score_player, score_enemy<br>missing_trace_fields |

### C08: buy_phase_evidence（1件）

Category: buy phase。実装状態: 部分実装。Fix target: qualified phase evidence and stable score inputs。

buy_phase_banner absent on all4661 observations; profile lacks buy-phase template and score readers。

| Assertion / 目的 / PTS・範囲 | expected | actual / failure field・reason | upstream / 追加条件 |
| --- | --- | --- | --- |
| GT-R1-BUY-FLAG<br>buy_phase_banner<br>[0.0,4.1] | `{"id":"GT-R1-BUY-FLAG","round_id":"sample_round_1","state_class":"flag","state":"buy_phase_banner","subtype":null,"core_interval":[0.0,4.1],"outer_interval":[0.0,4.15],"min_core_coverage":0.8,"exhaustive":false}` | coverage=0.00000 / required=0.8; round-neutral=0.00000<br>fields: coverage.buy_phase_banner<br>state_coverage:GT-R1-BUY-FLAG | state_evidence, round_package_scope<br> |

### C09: smoke_evidence（1件）

Category: smoke state。実装状態: 認識失敗。Fix target: smoke structural/temporal evidence。

vision_obscured_smoke absent; conservative existing smoke feature conditions not satisfied。

| Assertion / 目的 / PTS・範囲 | expected | actual / failure field・reason | upstream / 追加条件 |
| --- | --- | --- | --- |
| GT-R1-SMOKE<br>vision_obscured_smoke<br>[59.502669,70.202669] | `{"id":"GT-R1-SMOKE","round_id":"sample_round_1","state_class":"flag","state":"vision_obscured_smoke","subtype":null,"core_interval":[59.502669,70.202669],"outer_interval":[59.402669,70.302669],"min_core_coverage":0.9,"exhaustive":true,"edge_brackets":{"start":{"last_absent_sec":59.402669,"first_present_sec":59.502669},"end":{"last_present_sec":70.202669,"first_absent_sec":70.302669}}}` | coverage=0.00000 / required=0.9; round-neutral=0.00000<br>fields: coverage.vision_obscured_smoke<br>state_coverage:GT-R1-SMOKE | state_evidence, round_package_scope<br> |

### C10: live_ownership_coverage（1件）

Category: live identity。実装状態: 認識失敗。Fix target: independent current-frame identity and view ownership coverage。

455 identified live frames cannot cover90% of required R1 self interval。

| Assertion / 目的 / PTS・範囲 | expected | actual / failure field・reason | upstream / 追加条件 |
| --- | --- | --- | --- |
| OWN-R1-SELF<br>self<br>[0.036003,74.38] | `{"id":"OWN-R1-SELF","round_id":"sample_round_1","owner":"self","core_interval":[0.036003,74.38],"outer_interval":[0.0,74.4],"min_core_coverage":0.9}` | coverage=0.08855 / required=0.9; round-neutral=0.08855<br>fields: coverage.self<br>ownership_coverage:OWN-R1-SELF | state_evidence, round_package_scope<br>ownership_contract |

### C11: self_dead_owner_export（1件）

Category: ownership。実装状態: 未実装。Fix target: death ownership contract producer and adapter。

trace adapter emits self/teammate_spectated/unknown only; self_dead_ui has no emission path。

| Assertion / 目的 / PTS・範囲 | expected | actual / failure field・reason | upstream / 追加条件 |
| --- | --- | --- | --- |
| OWN-R1-SELF-DEAD<br>self_dead_ui<br>[74.4,81.5] | `{"id":"OWN-R1-SELF-DEAD","round_id":"sample_round_1","owner":"self_dead_ui","core_interval":[74.4,81.5],"outer_interval":[74.4,82.0],"min_core_coverage":0.9}` | coverage=0.00000 / required=0.9; round-neutral=0.00000<br>fields: coverage.self_dead_ui<br>ownership_coverage:OWN-R1-SELF-DEAD | state_evidence, round_package_scope<br>ownership_contract |

### C12: nonself_killfeed_snapshot_field（1件）

Category: killfeed / snapshot。実装状態: 未実装。Fix target: nonself killfeed visibility evidence and trace export。

Matching snapshot lacks nonself_killfeed_row_visible; current snapshot/adapter has no producer for this field。

| Assertion / 目的 / PTS・範囲 | expected | actual / failure field・reason | upstream / 追加条件 |
| --- | --- | --- | --- |
| GT-R1-SNAP-475<br>required_snapshots<br>47.5 ±0.1 | `{"primary_state":"live_first_person","player_alive":true,"nonself_killfeed_row_visible":true}` | snapshot candidates=6; fields={"primary_state":{"present":true,"value":"live_first_person"},"player_alive":{"present":true,"value":true},"nonself_killfeed_row_visible":{"present":false,"value":null}}; native samples=11 / qualified=6<br>fields: nonself_killfeed_row_visible<br>snapshot:GT-R1-SNAP-475:nonself_killfeed_row_visible | round_package_scope, hud_confidence_gate, snapshot_materialization, primary_state, player_alive, nonself_killfeed_row_visible<br>missing_trace_fields |

### C13: shot_evidence（1件）

Category: event detection。実装状態: upstream依存。Fix target: qualified shot inputs and event aggregation。

No shot in required window; visual candidate path exists but all14 candidates suppressed below threshold。

| Assertion / 目的 / PTS・範囲 | expected | actual / failure field・reason | upstream / 追加条件 |
| --- | --- | --- | --- |
| event_count_constraints-003<br>shot<br>[73.9,74.39] | `{"type":"shot","actor":"player","window":[73.9,74.39],"min":1,"max":3,"note":"Visual contract uses burst/trigger-start granularity; three muzzle flashes are observed but exact event count is intentionally a range.","round_id":"sample_round_1"}` | {"count":0}<br>fields: count.shot<br>count:sample_round_1:shot | event_producer, round_package_scope<br> |

## 5. Root cause summary

| Root cause | FAIL | 全55に占める割合 | 修正可能性と制約 |
| --- | ---: | ---: | --- |
| C01 round_package_scope | 29 | 52.73% | 高・縦断契約の実装。ただし下流も必要 |
| C02 snapshot_hud_confidence | 7 | 12.73% | 中・独立証拠と契約完成が必要 |
| C03 round_boundary | 4 | 7.27% | 中・独立証拠と契約完成が必要 |
| C04 weapon_visual_input_guard | 3 | 5.45% | 中・独立証拠と契約完成が必要 |
| C05 player_death_semantics | 2 | 3.64% | 中・独立証拠と契約完成が必要 |
| C06 astra_evidence | 2 | 3.64% | 中・独立証拠と契約完成が必要 |
| C07 native_sample_tolerance | 2 | 3.64% | 中・独立証拠と契約完成が必要 |
| C08 buy_phase_evidence | 1 | 1.82% | 中・独立証拠と契約完成が必要 |
| C09 smoke_evidence | 1 | 1.82% | 中・独立証拠と契約完成が必要 |
| C10 live_ownership_coverage | 1 | 1.82% | 中・独立証拠と契約完成が必要 |
| C11 self_dead_owner_export | 1 | 1.82% | 中・独立証拠と契約完成が必要 |
| C12 nonself_killfeed_snapshot_field | 1 | 1.82% | 中・独立証拠と契約完成が必要 |
| C13 shot_evidence | 1 | 1.82% | 中・独立証拠と契約完成が必要 |

合計55件。round/package29と直接境界4は互いに重ならず33件（60%）。map／timer／identityの影響タグは重複するため、この排他的集計に加算しません。修正可能性の高／中は工学上の優先判断で、PASS転換確率を測定した数値ではありません。

検討したcategoryはprimary分類と依存タグを分離しました。次の件数は**要求または依存に関係するFAIL行数**で、原因別に加算しません。

| Category / tag | 関係するFAIL行数 |
| --- | ---: |
| HP reader | 5 |
| ally score | 4 |
| buy menu | 2 |
| buy phase | 1 |
| enemy score | 4 |
| event detection | 1 |
| kill/death/combat event | 4 |
| killfeed / snapshot | 1 |
| live identity | 1 |
| map detection | 4 |
| map resolution | 3 |
| ownership | 1 |
| remote state | 2 |
| round end | 2 |
| round package | 29 |
| round start | 4 |
| round start/end | 4 |
| smoke state | 1 |
| snapshot | 25 |
| spectator detection | 4 |
| temporal context | 2 |
| timer reader | 4 |
| upstream dependency failure | 42 |
| visual event | 3 |
| 未実装field / export | 12 |
| HUD geometry（直接のinvalid-effective gate） | 0 |
| map trajectory（positive assertion） | 0 |
| validation data（不正と証明済み） | 0 |

combat reportはpositive intervalがPASSで、death/window関連snapshotで追加の意味解釈が必要です。既存のreport-visible検出自体を全未実装と分類しません。

## 6. Dependency graph

```mermaid
flowchart TD
  V[実動画 / decode / PTS] --> G[anchors / fresh geometry]
  P[共通profile / masks / reader binding] --> G
  G --> C[effective calibration / retained policy]
  C --> R[current-frame ROI readers]
  C --> I[HP + Ability + Weapon structure + spectator exclusion]
  P --> R
  I --> S[HUD primary state / flags / view context]
  R --> O[HUD observations / accepted numeric values]
  S --> O
  O --> D[phase + timer + score + death evidence / direct HUD events]
  O --> W[native round windows]
  D --> W
  W --> PK[RoundPackage / native snapshots / events]
  O --> PK
  O --> E[player-mechanics eligibility]
  E --> VA[visual observations / thresholded candidates]
  VA --> VE[confirmed visual events]
  VE --> PK
  E --> MA[map selection + calibration + marker/location]
  MC[map registry / visual profile / client build] --> MA
  MA --> Z[zone timeline / resolver]
  Z --> PK
  PK --> TS[trace events + snapshots / package-order round ID]
  O --> TI[state + ownership intervals over adjacent observed PTS]
  W --> TI
  VA --> TV[trace muzzle observations + actor gate]
  W --> TV
  TS --> TF[limited explicit temporal features]
  TS --> EV[canonical evaluator]
  TI --> EV
  TV --> EV
  TF --> EV
```

state／ownership intervalsはpackageのsnapshotから作るものではありません。raw observationsにpackage window/round所属を適用して作ります。visual observationsもrawから直接変換し、packageが所属範囲を制限します。resolved zoneは独立map timelineからsnapshotへmergeします。HUDのexpanded-map stateとmap-zone resolutionは別の機能です。したがって、mapだけ直してexpanded-map intervalがPASSになるとは扱いません。

実装参照：`hud/analyzers.py:259–368,466–476,585–635`、`hud/temporal.py:77–225,336–407`、`rounds/builder.py:276–396,451–579`、`tests/e2e/trace_adapter.py:35–220`、`visual/runtime.py:138`、`visual/map_pipeline.py`、`maps/calibration.py`、`maps/resolver.py`。詳細行・source hashはJSON内の調査evidenceに保存しました。

## 7. Missing implementation analysis

| 第一阻害条件の種類 | FAIL | 割合 |
| --- | ---: | ---: |
| 未実装 | 2 | 3.64% |
| 部分実装 | 7 | 12.73% |
| 認識失敗 | 4 | 7.27% |
| upstream依存 | 42 | 76.36% |
| evaluator / validation | 0 | 0.00% |

上流依存42件（76.36%）は「下流は完成済み」を意味しません。最初のgateに隠れている欠落も確認しました。

| 不足する明示trace field | そのfieldを要求するFAIL数 | 現行コードの不足 |
| --- | ---: | --- |
| game_timer_display | 4 | source/producerからsnapshot/adapterへ渡す経路がない |
| muzzle_flash_visible | 3 | source/producerからsnapshot/adapterへ渡す経路がない |
| nonself_killfeed_row_visible | 1 | source/producerからsnapshot/adapterへ渡す経路がない |
| reload_animation_visible | 3 | source/producerからsnapshot/adapterへ渡す経路がない |
| spectated_name | 2 | source/producerからsnapshot/adapterへ渡す経路がない |
| spectator_primary_state | 1 | source/producerからsnapshot/adapterへ渡す経路がない |

この6fieldの件数は重複し、対象は**11 distinct FAIL snapshots**です。検出器の一部（reload/visualなど）が存在しても、必要なboolean/name/display fieldを出力できる完全実装ではありません。数値secondsから表示文字列を推測して埋めることは禁止し、OCRの原文とprovenanceを保持する契約が必要です。`nonself_killfeed_row_visible`は現在matching snapshotがあり他のpredicateが通るため、正しいfieldを加えられれば条件付きで+1になる最小課題です。

`self_dead_ui`のownership出力経路がないことはR1/R2の2件に関係します（排他的集計ではR1の1件、R2はpackage scopeに分類）。`self`も現在liveだけへ写像するため、GTが含むremote／buy UIのcontroller ownershipを将来どう証明・保持するかを完成させる必要があります。player-specific HUDをremote/menuへ許可する修正とは分けます。

round boundaryのactorはnative=`team`、pack=`system`です。deathは現行`cause_known`だけで、`victim_name`／`killer_agent`／`combat_report_damage_received`がありません。これはproducer→traceの契約不足で、packを変更すべき証拠ではありません。map registry/resolver自体は実装済みです。現在のmap設定不足を「map全体未実装」と分類しません。evaluator／validation不良をprimary原因と断定できるFAILは0件で、canonical再評価も保存reportと一致しています。

## 8. Recognition accuracy analysis

unknown数という単独KPIでは採否を決めません（最新は3731）。current-frameの独立証拠、元のreader値、所有者と正解をPTS/hashで対応付け、`unknown→correct`、`unknown→wrong`、`correct→wrong`、`wrong→unknown`、`wrong→correct`を別々に記録します。全フレームについて独立GTがあるとは限らず、未レビューのunknownをwrong/正解に換算しません。unknown→wrong、correct→wrongを増やす変更は原則却下します。

profile16はtimer3411件を出力しても高confidence誤読3件で却下。profile17もsampled27 correct/2 unknown/1 wrongで却下しました。aggregate PASS増加とfieldの正確性は別です。HPはidentified live455件中444に値があり11 unknownで、非owned値はクリアされています。score_ally/enemyは全4661 nullで、profileにreaderがないというconfiguration不足です。NCCやacceptanceを緩める根拠にはしません。

positive/zero-count/negativeのPASS内訳を取り違えません：20 negative＋R1 combat-report interval＋R1 SNAP-705＋R2 round-end count0=23です。20 negative PASSは安全性の必要条件であり、空のイベント出力でも成立するものがあるためpositive認識の証明ではありません。NE4の理由はすべてpoint欠落です。

## 9. Geometry impact analysis

| Anchor | mask | accepted / rejected | min / median / max |
| --- | --- | ---: | --- |
| round_timer | 無 | 2 /4659 | 0.3130 /0.7708 /0.9995 |
| top_match_bar | 有 | 4661 /0 | 0.9577 /0.9958 /0.9983 |
| player_hp_armor | 無 | 1 /4660 | 0.0000 /0.5245 /0.9995 |
| abilities | 無 | 1 /4660 | 0.0000 /0.4328 /0.9993 |

閾値はすべて0.90、4候補中minimum3 anchorが必要です。top_match_barだけが全件受理され、timer／HP／Abilityがほぼ毎回棄却されるためfresh failure4660件はすべて`insufficient_anchors`です。HP／Ability／timerのraw referenceは動的な画素を含みmaskがなく、temporal-generationの構造referenceもtraining support不足でinvalidです。既存のvariance／edge-persistence／median／共同translation試験はsupportを満たさず却下済みです。maskの不足と低NCCは直接観測できますが、それだけで全失敗の因果説明とはしません。

現在の制御フローは最初の実画像でinitial calibrationを作り、loop index0はそのcalibrationを使います。effective全4661、fresh1という集計と合わせると、唯一freshはframe0/PTS0.036003と推論できます。保存済みper-frame timestampではなくコードからの推論です。保持フレームは0.202669〜171.002669（span170.8秒）、最後のcalibration age170.966666秒。後続4660 fresh failureが同じinsufficient原因なので、その間の置換0回もコードからの推論です。

| 新鮮さ | frames | unknown | nonunknown | timer value present / absent | live / HP-present |
| --- | ---: | ---: | ---: | ---: | ---: |
| fresh（frame0） | 1 | 1 | 0 | 1 /0 | 0 /0 |
| retained | 4660 | 3730 | 930 | 3410 /1250 | 455 /444 |

retainedのunknown率は80.04%ですが、fresh側が1点しかなく因果比較はできません。geometry-invalid unknownは0、geometry-valid unknown3731。geometryがretainedでも455 liveと444 HPが成立します。HPの欠落はownership clearが混ざるためOCR失敗とは同義ではなく、score欠落はreader未設定です。full13も同じanchor assetでfresh1/effective4634、unknown3715、owned HP444/455で、timer0に対してfull16 timer3411でも55 FAILは不変でした。

raw primary-state transitionは319回（unknown↔live264、unknown↔spectator49、unknown↔menu6）。state transition自体をcalibration reset条件にはしておらず、これらもretainedの区間にあります。camera transitionが認識されないunknown→unknownの場面はこの319回に含まれません。spectator／combat report／menu／content jump後に同じcalibrationを保持することは確認できますが、物理的にROIが外れたかはaggregate telemetryからは証明できません。top barは全件NCC>=0.9577で保たれています。必要な追加診断はper-frame anchor confidence、effective transform、age、reset理由と現ROIの独立位置誤差であり、今回acceptance policyは変更していません。

R1 SNAP-733（73.3±0.08）とSNAP-7445（74.45±0.03）にはnative analyzed sample自体が0件です。read valueだけ直しても通りません。これは動画のPTSが存在しないという意味ではなく、full samplerの実際の入力coverageの問題です。今後も現行full samplerを変更せず、連続性を保つ診断から必要証拠を確かめます。

## 10. Round / Event / Map analysis

| 機能 | 実装・呼び出し | 0となる観測された理由 |
| --- | --- | --- |
| round start | HudDirectEventBuilder実行済み | timer resetはあるがbuy/banner→liveの両フレームconfidence>=0.65とstate証拠が不足 |
| round end | 同上 | round_end_banner0、score全null、corroboration不足 |
| death | 同上 | combat reportだけでは死を確定しない。第二cueとrequired semantic attrs不足 |
| round package | builder実行済み、診断require_detected_rounds=False | 1 partial fragment[7.369336,171.002669]。境界不在で2roundへ分かれない |
| HUD events | builder呼び出し済み | 必須入力／確信度を満たすeventなし。trace262件はderived state_snapshot |
| Visual events | analyzer実行済み | eligibility455/4661、shot candidate14全件below_candidate_thresholdでsuppressed |
| map resolution | registry/calibrator/timeline/resolver実行済み | visual profile/manual map/build未指定、eligible455でauto selection455失敗、残4206はeligibilityでskip |
| map trajectory | map timelineコードあり | marker/map/zoneの入力未成立。専用positive trajectory assertionは82件内にない |
| temporal context | 内容不連続の保護あり | trace temporal_features0。negative span0違反はpositive continuityの証明ではない |

visual traceは4件、actor全unknown（59.402669、59.552669、75.786003、75.802669）。要求は73.95／74.25／74.38±0.08、actor playerです。要求窓の近傍ではplayer_mechanics=falseかつmuzzle最大0.4266<adapter0.5で、ownershipだけを直しても3 visual FAILは通りません。実shot candidateのconfidenceは約0.503〜0.64、独立sourceはweapon cueのみ、tier Aの0.65/0.85等の条件を緩めません。

## 11. Estimated PASS gain by fix

「保証」は現runへ実装した場合の保証を意味し、全targetとも0です。以下のpossibleは明記した全契約が成立した場合の有限なassertion ID集合で、期待確率や実測予測ではありません。重複するaffected件数を足してPASS目標にしません。

| 改善対象 | affected FAIL（重複あり） | 単独・縦断taskでの条件付きFAIL→PASS | NE→PASS | 条件・注意 |
| --- | ---: | ---: | ---: | --- |
| round lifecycle/package/actor contract | 33 | 6 | 1 | Three true boundary point events, exact actor/time/count contract and correct native package scope; includes P1 IDs; not ID-only relabeling |
| death event producer + required event attributes | 26 | 4 | 3 | Correct point times, exactly one death per round, victim/killer/report attributes and round lifecycle already qualified |
| nonself killfeed snapshot export | 1 | 1 | 0 | Only failed field corrected from actual current-frame evidence; existing snapshot and fields unchanged |
| numeric timer + original display preservation | 4 | 0（他契約込みmax 4） | 0 | Timer alone insufficient: package, identity/snapshot, scores and original display-string provenance must also qualify |
| ally/enemy score readers | 4 | 0（他契約込みmax 4） | 0 | Complete snapshot predicates plus phase/round detector corroboration; never implicit score fallback with demonstrated errors |
| owned HP reader | 5 | 0（他契約込みmax 5） | 0 | HP already works444/455 live frames; requested frames are mostly upstream unknown; identity/package and other expected fields also required |
| spectator state/ownership and spectated values | 4 | 0（他契約込みmax 4） | 0 | Round2 scope,90% state/ownership coverage, separate spectated-player value/name fields; no player-value poisoning |
| map selection/calibration/zone resolver | 3 | 0（他契約込みmax 3） | 0 | Eligible correctly located snapshots exist and correct zone is independently resolved; expanded-map state is separate |
| owned muzzle/shot pipeline | 7 | 0（他契約込みmax 4） | 0 | P6 outputs qualified; snapshot fields require additional contract work |
| fresh geometry anchors | 0 | 0 | 0 | No direct geometry assertion and zero invalid-effective frames; causal gain unproven. May support future recognition, cannot assign arbitrary55 gains |

root単位の現在件数と全IDは第5章／JSONにあります。原子的なround ID変更、timer数値、map resolver、spectator存在判定だけではguaranteed増加0です。round lifecycle taskの+6はdirect-boundary4とR2 startのpoint/count2を合わせた**別の縦断taskの契約目標**で、package29をPASSへ置き換えた値ではありません。R1 ordering(start<end)1 NEはその3point窓が正しく満たされればPASSになります。

各root causeの解消可能数も排他的メンバーを使って記録します。右列は**他のpredicateもすべて完成した場合の上限**で、単独修正の増加ではありません。現実runで保証できる数は全rootで0。C01のlabel-only感度試験は0、nonself_killfeed_snapshot_fieldだけは既存matching snapshot上の唯一の不一致なので条件付き単独+1です。

| Root | 現FAIL | 無条件保証 | 全他条件成立後のprimaryメンバー上限 | 確度 |
| --- | ---: | ---: | ---: | --- |
| C01 round_package_scope | 29 | 0 | 29 | possible |
| C02 snapshot_hud_confidence | 7 | 0 | 7 | possible |
| C03 round_boundary | 4 | 0 | 4 | possible |
| C04 weapon_visual_input_guard | 3 | 0 | 3 | possible |
| C05 player_death_semantics | 2 | 0 | 2 | possible |
| C06 astra_evidence | 2 | 0 | 2 | possible |
| C07 native_sample_tolerance | 2 | 0 | 2 | possible |
| C08 buy_phase_evidence | 1 | 0 | 1 | possible |
| C09 smoke_evidence | 1 | 0 | 1 | possible |
| C10 live_ownership_coverage | 1 | 0 | 1 | possible |
| C11 self_dead_owner_export | 1 | 0 | 1 | possible |
| C12 nonself_killfeed_snapshot_field | 1 | 0 | 1 | possible |
| C13 shot_evidence | 1 | 0 | 1 | possible |

## 12. Recommended priority

### Priority 1: round lifecycleとproducer→trace契約を完成させる

33 FAILへ影響。最初の明示受入IDはR1 start/endとR2 startのpoint/count6＋ordering1です。現画像からphase／timer reset／score/bannerを独立に証明し、current ownershipとconfidence条件を保ったまま境界を作ります。actor=team/systemの意味をevent contractに合わせて解決し、buy/pre-round contextを含むpackage所属を仕様として明確化します。時刻やround数をGTから注入しません。targeted isolated PTSはreader診断だけに使い、境界検証は実際の連続区間・temporal integration＋採用前fullが必要です。難度高、誤境界・discontinuity越えのリスク高、packに正解窓あり。

### Priority 2: snapshotの未完成field契約とownership契約

11 distinct snapshotにfieldの欠落、self_dead ownership2に未実装写像があります。最初の小さな受入IDはGT-R1-SNAP-475で、matching snapshotの唯一の失敗fieldを正しいnonself killfeed観測で出力することです（条件付き+1）。動的な値や名前をidentityへ使いません。timer原文、reload/muzzle boolean、spectated name/value等はsource別に所有者を保持する設計へ進み、unknownなplayer_aliveをfalseで埋めません。targeted/sampleでreader/sourceとfieldの回帰を確認でき、snapshot cadence／owner timelineの採用はfullが必要。難度中〜高、誤ownerリスク高。

### Priority 3: IDを指定したstate/identity coverage

直接11 state＋5 ownership、さらにsnapshot admissionに影響。Astra4、buy phase2、menu2、smoke1、expanded-map1、spectator1の必須interval・edge・個別coverage条件（70/80/90%）を順に診断し、identity3独立構造とspectator exclusionを保ちます。menuは存在301件でもedge/overreach不合格、spectatorは174件でも90% coverage不足です。unknown低下を合格指標にしません。targeted/sampleでcurrent-frame誤認を除き、interval・edgeは連続区間またはfullで検証。難度高、GT intervalあり。

### Priority 4: map選択・calibration設定と入力の完成

3 derived zoneの明示目標。registryはあるが選択0で、正しいmap/profileの独立証拠を用意する必要があります。手動設定を使う場合も実動画から正当に確認したsource metadataを使い、GT zoneをruntime入力へコピーしません。snapshotとownershipが成立してからzoneを比較します。targetedで選択／calibration／境界errorを診断、held trajectoryとnegativeはfull。難度中〜高、誤zoneリスク高。

### Priority 5: owned visual/shot pipeline

3 muzzle＋1 shot-count、関連snapshot3に影響。eligibilityとammo/weapon、muzzle cueの実画像を順に確認し、単にactorをplayerへ書き換えません。採用には連続PTSのburst/reload/discontinuity検証とfull。難度高、false shotリスク高。

geometryは上記と独立した**診断優先課題**としてper-frame age/transformを観測します。55件の主原因という未証明な前提でreferenceを再生成し続けません。今回の調査ではgeometry policyやprofileを変更していません。

## 13. PASS milestone plan

均等な+10ではなく、現assertion IDを排他的に割り当てた契約上の目標です。phaseは検証集合の区切りであり実装作業の厳密な順序ではありません。P1のstate入力、P4のmuzzle sourceなど、後phaseに数える機能でも前phaseの必須依存は先に実装・資格確認します。実装成功を保証する予定ではありません。phaseより早く別のIDがPASSした場合は同じIDを再加算しません。NE→PASSもFAIL減少と区別します。

| Phase | 対象 | FAIL→PASS / NE→PASS | 条件付き累積 PASS / FAIL / NE | 必要実装・検証 |
| --- | --- | ---: | --- | --- |
| P1 | Round lifecycle + producer/trace contract | +6 /+1 | 30 /49 /3 | phase入力、境界actor/time/count、native package契約。temporal unit＋連続実画像＋full |
| P2 | Death evidence + required semantics | +4 /+3 | 37 /45 /0 | 独立death cue、名前/agent/report attrs、round所属、R1 death<endのstrict ordering。semantic targeted＋temporal regression＋full |
| P3 | State/ownership coverage + nonself killfeed export | +17 /+0 | 54 /28 /0 | 11 state/5 ownershipのinterval/edge、nonself field1。targeted/sample＋interval replay＋full |
| P4 | Remaining source-backed snapshot contracts | +21 /+0 | 75 /7 /0 | 残21 snapshotのreader/原文/actor/boolean/location/cadence。field targeted＋native integration＋full |
| P5 | Map selection/calibration/resolver + eligible snapshots | +3 /+0 | 78 /4 /0 | map/profile選択、calibration、zone解決とsnapshot merge。map targeted＋negative/full |
| P6 | Owned weapon visual observation + confirmed shot | +4 /+0 | 82 /0 /0 | owned visual muzzle3、shot count1。連続burst/reload/discontinuity＋full |

P4は21件の複合snapshot契約を含む大きな最終目標で、一つのrecognizer変更ではありません。全機能・個々の証拠が揃わなければ75は成立しません。全82 PASSの最後にも20 negative、R2 round_end=0、discontinuity保護を維持します。各phaseの全IDリスト、累積計算、非重複確認はJSONにあります。

## 14. Next recommended implementation task

**「round lifecycleの入力・イベント契約・package所属を一つの縦断featureとして完成させる」**を次の依頼にします。受入条件を先に固定します。

1. 実動画のR1開始[4.08,4.20]、R1終了[74.387,74.483]、R2開始[111.38,111.50]にsource evidenceを持つtrue境界。R2終了は生成しない。
2. raw event、native package、trace eventのtype/actor/time/countとpre-round contextの所属が一致。`system`を検出失敗の代替ラベルとして注入しない。
3. 全6 event/point/count IDとordering_constraints-001をcanonical evaluatorで確認。29 blocked downstreamを同時にPASSと主張しない。
4. 既存のidentity/ownership/spectator/geometry/OCR threshold、NCC0.90、GT/pack/assertion/full samplerを維持。判定に使うtraining/holdoutを分離し、未資格なら原因を診断。
5. unit→対象reader targeted→固定sampled→連続実画像temporal validation→候補だけ全回帰/full。4時間fullを全局所candidateへ要求しない。

この分析中は新しいcandidate、targeted/sample/full、production instrumentationを起動・追加していません。canonical保存traceの評価は軽量なoffline分析で、実動画fullの再実行ではありません。raw/trace/pack/GTやreport/historyを書き換えませんでした。成果物はこのMarkdownとfailure_analysis.jsonです。

### Verification

機械検証：82 unique IDs、23/55/4、canonical status/failure code一致、primary cause合計55、milestoneのFAIL ID55とNE ID4が非重複、宣言terminal hash一致。既存history/summary/geometry reportのmetadata・countsもterminalと一致。Ruff PASS、mypy PASS（96 source files）、関連runner/adapter/summary test28 PASS・1 SKIP（任意のsibling-pack fixture未配置）。production source変更0、新しいfull/targeted/sample起動0、pack/GT/trace/report/history変更0です。既存の作業記録以外の変更は本MarkdownとJSONのみ。source/GT hash保持とGit差分を最終確認しました。

### Authorized timer-input follow-up

Subsequent authorized development adds an opt-in strict glyph comparison representation; the original analysis and its 82 canonical statuses above remain historical and unchanged. A frozen candidate passes training support for all ten digits with NCC 0.90 and class margin 0.04 unchanged. Fresh same-video frame holdout: 25 correct / 7 unknown / 0 wrong; previously reviewed error controls: 0 correct / 4 unknown / 0 wrong; eight spatial source-field type negatives: zero false positives. These are reference-coordinate reader diagnostics, not temporal or calibrated analyzer acceptance. Natural timer-absent controls, qualified continuity, same-segment end evidence and canonical full remain outstanding; no profile adoption or PASS gain is claimed. Related146 tests, Ruff and mypy99 pass. See [implementation and scope](round_lifecycle_implementation.md#frozen-timer-representation-and-fresh-frame-holdout) and [hashed diagnostic report](../e2e_reports/match_001/timer_glyph_training_holdout_diagnostics.json).

### Source correspondence follow-up

Descriptive camera-region bidirectional optical flow/NCC on the same 130 previously measured source pairs adds evidence about the continuity blocker. R1 start has two high-NCC tracks across two spatial cells, R2 start three within one cell, and the reviewed content jump two across two cells. Sparse matching alone cannot distinguish these contexts; texture support cannot be reduced to force qualification. No confidence/segment producer, qualification, new canonical result or production behavior change is claimed. Diagnostic tests8 and Ruff pass. See [exact measurements and source hashes](../e2e_reports/match_001/source_correspondence_diagnostics.json).


### Composite continuity producer follow-up

The qualified global path now has an opt-in internal source producer: distributed camera-grid NCC, accepted timer-pair physics and prior confirmed purchase phase for reset. Unknown/weak inputs, gaps, invalid geometry and explicit cuts break segments; external continuity tokens are ignored. No real qualification report exists, so default profiles and canonical statuses remain unchanged. Training-only135-frame simulation proposes63links; 56timer-unavailable,11spatial-support failures,4gaps and1initial frame. This does not qualify continuity or prove boundaries. Related168 tests21.91s, Ruff and mypy100 PASS. Next fresh composite holdout/negative qualification. [Exact scope and binding](../e2e_reports/match_001/composite_source_continuity_diagnostics.json).


### Composite positive holdout follow-up

Fixed16 four-frame contexts (64 disjoint heldoutsourceframes) were selected after candidate freeze and manually reviewed before predictions. Actual calibrated analyzer67frames includingprefix: timer center27correct/5unknown/0wrong; separate composite simulation5proposedlinks/11abstentions (8camera/3timer). Positive-only visible-continuity review does not measure false-positive rate; independent cuts/phase-reset negatives remain incomplete. No qualification/adoption/canonical-status change. Analyzer135.131sec; no comparable prior run. Source/archive/frame/code/profile bindings verified. [Holdout scope and hashes](../e2e_reports/match_001/composite_continuity_holdout_diagnostics.json).


### Stale-source qualification defect and v2 follow-up

Nine counterfactual repeated-source controls exposev1 falsecontinuity9/9: identical image/timer with test PTS advanced0.1s was accepted. V1 is rejected; v2 exactdecodedpixel SHA equality breakssegment, preserveshashprovenance and reducesstaleattestations9→0. Priorpositive regression5links/11abstentions staysunchanged. These are test-only simulations, not natural-cut/freshv2 qualification; no canonical status or profileadoption change. Related170tests23.15s,Ruff/mypy100PASS. Freshv2 holdout/cut/reset/end evidence remain. [Defect evidence and fix](../e2e_reports/match_001/composite_stale_source_diagnostics.json).
### Global lifecycle source-pair gate follow-up

The latest opt-in composite v2 diagnostic rejects all three correlated frame pairs across one previously reviewed native content cut (zero false links; 1.177 seconds). This is regression evidence, not independent qualification. An optimistic replay of saved calibrated source inputs still produces zero starts: R1 has 75 unobserved / 3 pre-round samples, and R2 has 185 unobserved samples. Missing continuity clears preparation before the accepted timer reset; the consumer also does not consume the semantic producer's temporal source PTS. See [pipeline gate diagnostics](../e2e_reports/match_001/composite_pipeline_gate_diagnostics.json) for scope, hashes and assumptions. Canonical 23 PASS / 55 FAIL / 4 NE remains historical, with no new canonical measurement or PASS gain.

The next implementation must carry genuine phase/source-pair provenance without joining unsupported continuity segments. Code inspection additionally finds that the final `{**row_evidence, **supplemental}` merge can overwrite an internally produced `global_continuity` mapping; a qualified route must protect this producer contract before activation. This is an inspected trust-boundary concern, not yet an end-to-end reproduced exploit or a fixed defect. No thresholds, Validation Pack, assertions, source sampler or player ownership policy changed in this diagnostic follow-up. The existing semantic source PTS are present in intermediate signals; the missing consumer use and continuity binding, rather than complete producer omission, need correction.


### Active round latch: phase jitter regression

The qualified global consumer could overwrite `round_active` with `pre_round` after two sufficiently separated purchase-phase observations. A later reset then emits another start without a qualified end. A phase observation at a genuine qualified score/result end also overwrites active state before the end predicate runs, hiding that end. This is a consumer state-machine defect, independent of OCR accuracy.

A before-fix synthetic control through the real `HudDirectEventBuilder` reproduces two starts and zero ends. The consumer now ignores phase as new preparation while the round is active. A qualified end or a source reset must close that lifecycle before new preparation can arm it. Existing confidence/duration requirements remain. Phase is still available to the end predicate; observations and player facts are unchanged. After the fix the same synthetic sequence emits one system start and one system end. A separate source-cut case rejects old preparation, then accepts a start only after new-segment preparation. Existing R1-to-R2 package/trace contract tests pass. These fixtures supply synthetic qualified proofs; they do not establish real-image continuity or boundary acceptance.

| Synthetic contract metric | Previous | Current | Delta |
| --- | ---: | ---: | ---: |
| Starts in one active lifecycle | 2 | 1 | -1 |
| Qualified ends retained during phase reappearance | 0 | 1 | +1 |

Related151tests PASS in23.86sec with the local Validation Pack path; Ruff PASS; mypy100 PASS. This is a focused regression suite, not full regression. Target assertions remain `GT-R1-ROUND-START`, `GT-R1-ROUND-END`, `GT-R2-ROUND-START`, event counts000/002/004 and ordering001. No new canonical assertion is claimed PASS. The accepted23/55/4 is historical; current/delta are unmeasured. No new targeted/sampled/full run is justified while native clock/phase/continuity evidence and end qualification remain unsupported. No threshold, geometry, identity/ownership, GT, assertion or sampler changed.

The recognizer fingerprint changes to `e9cd7c81e972a3e548b0da40819b31bef99f8329366c1be58ab216c9454bca9e`; older qualification bindings must not be reused. No real report is installed or profile adopted. Next: obtain independent qualified global clock/phase/continuity evidence; accurately read transient display values are not automatically lifecycle clocks. Windows remains unverified. [Synthetic contract diagnostics](../e2e_reports/match_001/global_active_round_diagnostics.json).


### Opt-in global score reader: development evidence, not qualification

The result/score end path lacks a qualified score producer. Under the user's explicit fixed-assertion timer/score authorization, `StrictScoreGlyphReader` and profile kind `strict_score_glyphs` now support only `ally_score` / `enemy_score`. They reuse the complete ten-class binary-reference validation and optional symmetric gaussian3x3 comparison, with fixed NCC0.90 and competitor margin0.04. Score grammar is independent of timer grammar: one or two aligned digits, no leading zero, colon, extra components or clipped foreground. Invalid explicit profiles stay present as unknown readers and cannot fall back to OCR or supply HP/timer roles. Success preserves source display/confidence; it neither establishes player identity nor emits a boundary. Default profiles and geometry are unchanged.

The first local development sidecar borrows the already reviewed timer glyph assets, keeping all ten competing digits rather than limiting classes to observed scores. Inner ROI bounds follow the visible score field, not GT values. An initial development crop probe reads ally0 but rejects enemy1 for border foreground. That rejection is retained, not filled. The frozen sidecar then evaluates all60previously extracted/hash-bound native frames (120score readings), with the original integer PTS, source/video/profile/assets/code/script binding. This cohort overlaps existing timer/phase development and is not independent holdout. Manual review of both source contact sheets occurs after prediction. Source PNG hashes are checked again after review.

| Development source result | Ally | Enemy | Total |
| --- | ---: | ---: | ---: |
| Correct displayed strings | 60 | 24 | 84 |
| Unknown | 0 | 36 | 36 |
| Wrong displayed strings | 0 | 0 | 0 |

All30visible enemy1 readings in the first window remain unknown. In the second window24enemy2 readings are correct and the first6unknown. All36abstentions are foreground-border failures. In an inspected first-window crop Otsu chooses140, includes score-card background/edge pixels and triggers the unchanged border guard. Do not treat those source-visible labels as runtime values, remove competitor classes or relax the border/NCC/margin guards. Next investigate value-invariant foreground extraction on explicit training frames, then fresh disjoint holdout/negative controls. The current sidecar is development-only and is not copied into the runtime HUD profile.

Runtime8.265sec,60frames,7.259frames/sec: this is score-only source diagnostics, not E2E. Previous comparable run and runtime delta are unavailable. Related194tests PASS24.49sec, Ruff PASS and mypy101 PASS; full regression was not run. The measured diagnostic harness is preserved privately with its frozen hash; a subsequent explicit-reader-kind validation affects only invalid configurations, and its current hash is separately recorded. Recognition code/profile did not change after this measured run.

No qualification report, adoption, canonical event or new PASS is claimed. Canonical23/55/4 remains historical; current/delta are unmeasured. Targeted/sampled/full are gated because starts remain unqualified, enemy score coverage is incomplete, and R1 end still lacks corroborated same-segment result/score evidence. New code fingerprint invalidates earlier qualification bindings. Validation Pack/GT/assertions, sampler and player-owned policies remain fixed. Windows is unverified. [Source statistics and bindings](../e2e_reports/match_001/score_glyph_development_diagnostics.json).


### Score foreground extraction and same-video heldout source comparison

The first reader's Otsu partition mixes bright score-card backgrounds with thin white glyphs. The opt-in `foreground_preprocessing: white200_v1` now extracts only fixed bright uint8 text above200 after the same resizing. This is a preprocessing threshold, not a lower acceptance threshold. Default `otsu_v1`, NCC0.90, competitor gap0.04, all ten classes, source-display output and the structural border/layout guards remain. There is no retry or alternate-reader fallback after rejection. Invalid foreground modes fail closed; profile fingerprints include the explicit mode. Unit controls cover all ten digits, two-digit scores, dim text, bright backgrounds, clipping and extra components. No generic timer/HP preprocessing changed.

The same60developmentframes improve120readings from84correct/36unknown/0wrong to114correct/6unknown/0wrong. This is training/development evidence, not qualification. Code and sidecar are then frozen before heldout selection. Fixed whole-video fractions generate six short native windows; intervals within0.12sec of any source in the frozen128frame glyph cohort,12additional seven-training frames or60score-development frames are rejected before extraction. Three heldout contexts (27frames) and three separate spatial-negative source contexts (27frames) preserve every source PTS inside their explicit windows, checked with the existing exact native extraction contract. Source-video/profile/code/input hashes are checked before and after; all54PNG/pixel hashes are checked again after evaluation. No Validation Pack is loaded and no GT window chooses inputs. Manual source labels are recorded **before** predictions; neither recognizer nor candidate selector loads them.

| Same heldout54score reads | Previous Otsu | Current white200 | Delta |
| --- | ---: | ---: | ---: |
| Correct | 19 | 36 | +17 |
| Unknown | 35 | 18 | -17 |
| Wrong | 0 | 0 | 0 |
| Wall-clock seconds | 5.561358 | 5.560424 | -0.000934 |

The per-reading transitions are17unknown→correct,19correct→correct and18unknown→unknown. No unknown→wrong or correct→wrong occurs. The tiny runtime difference is measurement variation, not a speed claim. Baseline Otsu is reevaluated on the same frozen source set after labeling solely for comparison; labels remain evaluator inputs. Development runtime8.265→8.807sec (+0.541sec,+6.55%); heldout and development runtimes measure score-only diagnostics, not E2E. Source extraction54frames takes46.697sec.

Spatial controls use54fixed non-score crops from the separate27sourceframes, reviewed before prediction. False acceptance0/54; negative-reader runtime3.473sec. These are field-type controls, **not** natural absent-score UI, content-cut or round-event negatives. Heldout evidence covers three correlated short contexts of the same video and displayed classes0/1/2; it does not establish independent-video/all-score qualification. The18heldout abstentions still reject bright background/particles at the ROI border. Keep them unknown; do not use source labels to fill values or lower guards.

Related217tests PASS25.14sec, Ruff PASS, mypy101 PASS. No complete runtime qualification, profile adoption, canonical boundary or new PASS is claimed. Historical canonical23/55/4 remains; current/delta unmeasured. No targeted/sampled/full/full-regression run is warranted while starts and same-segment R1-end corroboration remain unsupported. GT/assertions, full sampler, identity/player ownership and geometry thresholds are unchanged. The changed code fingerprint invalidates older qualification bindings; Windows is unverified. Next investigate source-safe foreground/absent-UI negatives and carry qualified global evidence without bridging rejected clock/camera links. [Frozen comparison and provenance](../e2e_reports/match_001/score_white_holdout_diagnostics.json).


### Score reader → actual calibrated analyzer source verification

Reader-only holdout does not prove that the production analyzer retains accepted scores after geometry/state/identity handling. A separate development sidecar combines the unchanged existing template/anchor/timer profile with the frozen opt-in score readers. It is not installed as the runtime profile. Three actual `RealHudAnalyzer` instances each process the three historically source-associated calibration prefix frames and all nine native source frames of one heldout window:36inputs including27heldout. No injected anchors, reader objects, signals, Validation Pack or qualification object are supplied. The historical prefix only establishes geometry under the existing retained policy; its long gap cannot corroborate temporal events. Source video, profile/assets, current code, diagnostic script and every input frame are hash-checked before and after.

| Same27source frames /54score reads | Reader-only previous | Actual analyzer current | Delta |
| --- | ---: | ---: | ---: |
| Correct | 36 | 36 | 0 |
| Unknown | 18 | 18 | 0 |
| Wrong | 0 | 0 | 0 |

All27heldout primary states stay unknown. No player-specific HUD-valid, HP, armor, weapon-text or populated ability-slot fact is released. Accepted score integers and their reader ROI confidence reach actual observations while unknown identity stays unknown; no global proof is borrowed for player facts. All18score abstentions remain null. Each12-input instance has1fresh geometry/12effective/11retained; aggregate3fresh/36effective/33retained includes the repeated prefix. This is not a full-video geometry-rate improvement and does not prove scene continuity across the prefix gap. The analyzer emits zero events, because actual global qualification remains absent and no boundary evidence is injected. Production package/trace/evaluator acceptance is still unverified.

Actual-analyzer runtime85.399sec for36inputs (0.422processedframes/sec). Reader-only holdout5.560sec processes27inputs without template/identity/state/calibration/HP OCR; these runtimes are not comparable and no speed conclusion follows. Previous comparable analyzer run/runtime delta is unavailable. No production code changed in this diagnostic; prior217relatedtests25.14sec, Ruff PASS and mypy101 PASS remain valid for that unchanged source. No new regression suite, targeted/sampled/full or canonical result is claimed. Historical23/55/4 remains; current/delta are unmeasured. No profile adoption, threshold/geometry/identity/ownership/GT/assertion/full-sampler change. Windows is unverified. Next: qualify absent-score/UI controls and genuine same-segment phase/clock/result evidence, preserving current abstentions and player ownership gates. [Actual source analyzer contract measurements](../e2e_reports/match_001/score_source_analyzer_diagnostics.json).


### R1 result qualification gap: current numeric source inputs rechecked

Current frozen score/timer readers were replayed against the10previously reviewed native R1-end images. The raw source images and original integer PTS are hash-bound to the prior source review; the video SHA is verified at the terminal of this short replay and every PNG hash is checked again. No labels are passed to readers. Post-prediction review gives score18correct/2unknown/0wrong (20reads), timer4correct/6unknown/0wrong (10reads). In the previously reviewed TEAM ACE frame the timer reader abstains and scores read0/1. Later source0/2reads are correct. An optimistic actual-camera composite simulation with assumed geometry and a never-installed test-only qualification object still attests0links:1initial,8accepted-timer-pair-unavailable and1insufficient-spatial-camera-support. These are development/archived-source measurements, not fresh qualification or real events. Runtime5.161sec; no comparable previous run/delta.

The available verified result-positive support is1frame **in this10frame local reviewed window**, not a proved whole-video count. It cannot establish the required semantic reference's3supported independent training images plus separate reviewed holdout/negative controls. The source score update after the recorded content discontinuity cannot corroborate or backdate the earlier result. Better score reading alone therefore does not satisfy the current end contract. Do not duplicate/synthetically perturb the single image and count it as independent support, copy review labels into runtime, bridge the cut or relax acceptance.

Asked for the Pi path of another unedited source video with phase→start or result→score continuity. Additional source data may qualify shared recognizers; it does not remove the need for independent same-segment evidence on the target video. No reply is assumed, and another genuinely qualified global cue remains a possible source-backed alternative. There is still no real qualification report, production boundary, profile adoption or canonical PASS change. Historical23/55/4 remains; current/delta unmeasured. No production source changed; prior217relatedtests/Ruff/mypy101 remain historical checks on unchanged source. No new full E2E is warranted. [Current inputs and exact qualification gap](../e2e_reports/match_001/round_result_qualification_gap.json).


### Roster source investigation and source-link safety repair

The ten archived native R1-end frames were inspected for an alternative global cue. The first two images visibly show one ally portrait and five enemy portraits; the remaining eight show no ally portraits and five enemy portraits. This is a source-visible UI description, not a qualified alive-count or player death. Existing fixed-slot saturation/contrast heuristics mark all five ally slots alive in frame7 despite no visible ally portraits. Other frames are ambiguous. Color-only roster is therefore rejected as independent boundary evidence; no threshold, identity gate or detector is relaxed and no new round/death fact is generated. Existing camera witness measurements also fail to establish continuous corroboration across this window.

A separate safety defect was reproduced in the existing roster debounce: both endpoints of duplicate-PTS, reversed-PTS and explicit-cut pairs could receive corroborated counts. Six synthetic invalid endpoint acceptances fall from6 to0 (delta−6), using the exact HEAD helper as the comparison without rolling back tracked source. The helper now requires finite strictly increasing adjacent PTS, the existing maximum1second gap and no content_jump/discontinuity at the later frame. The analyzer supplies cut indices from extracted and supplemental signals so look-ahead cannot bridge a supplied cut. Two new agreeing frames within the new segment remain eligible under the unchanged five-slot/confidence policy. This repairs a source contract; it does not qualify the underlying color heuristic or add a new global roster route.

Six new parameterized unit cases cover duplicate/backward times, feature cuts, post-cut recovery and both supplemental cut markers through the actual analyzer. Related198tests pass in28.71sec; one trace test initially skips without its external pack path, then all9trace-adapter tests pass in0.29sec with the installed pack, zero skips (199unique related cases pass across these runs). Ruff passes; mypy passes101source files. Production code fingerprint changes from6011f168… to8ea9523e…; earlier image measurements remain historical and cannot be rebound as current runtime qualification. Validation Pack, GT, assertion semantics, full sampler, NCC0.90, geometry/OCR acceptance and player-owned fact gates remain unchanged. No targeted/sampled/full E2E is run because the three boundary acceptance points still lack real qualified continuous evidence. Canonical23/55/4 remains historical; current/delta unmeasured, no newly accepted assertion. Windows remains unverified. The pending additional-source question has no assumed answer. [Source rows, synthetic comparison and bindings](../e2e_reports/match_001/roster_source_link_diagnostics.json).


### Archived context expansion and natural-absence control inventory

The three fixed first/middle/last buy-menu review images (PTS83.419336,88.786003,110.019336) still display timer and both scores. They cannot serve as absent-score/timer negatives. All64images from the prior uniformly ranked unknown review were then inspected using four topbar sheets, with every decoded pixel hash verified against the source manifest. All64show timer and scores. This is an inventory of this cohort only, not a whole-video absence claim. Spatial field-type negatives remain useful but do not replace natural absent-UI or content-cut controls.

For broader score coverage, the frozen Otsu/white readers were evaluated on50of those64archived frames after excluding14within0.12sec of the full128glyph cohort, additional12seven-training frames,60development frames and54previous heldout/negative-source frames. Source selection is fixed before predictions and uses no GT/Validation Pack values or windows. Manual topbar review precedes predictions; source label JSON is serialized afterward solely for evaluation and never loaded by readers/selector. Input hashes, code, profile, script and exclusion bindings are verified at terminal; source-video SHA is rechecked. The archived timestamps are rounded observation PTS, not a fresh native continuous extraction. Reference-size ROI geometry is assumed, not calibrated analyzer verification. This is supplementary same-video positive evidence, not independent lifecycle qualification.

| Same50source frames /100score readings | Previous Otsu | Current white200 | Delta |
| --- | ---: | ---: | ---: |
| Correct | 55 | 76 | +21 |
| Unknown | 45 | 24 | −21 |
| Wrong | 0 | 0 | 0 |
| Wall-clock seconds | 3.677137 | 3.646539 | −0.030598 |

Transitions:55correct→correct,21unknown→correct,24unknown→unknown, zero new wrongs. Runtime−0.83%is short-run variation; no E2E speed claim. The24abstentions remain unknown. These sources still cover displayed classes0/1/2of one video. No natural absent-UI controls were obtained and no qualification report/profile adoption is created. Existing source interruptions and R1 result support gaps still prevent the three actual boundary acceptances. Canonical23/55/4 is historical; current/delta unmeasured, no new assertion PASS. No targeted/sampled/full E2E is justified before these gates pass. Production/test/shared-script source is unchanged during this diagnostic, so the prior199unique related cases/Ruff/mypy101 checks remain applicable. GT, thresholds, ownership, geometry and full sampler stay fixed; Windows unverified. [Source inventory, comparison and bindings](../e2e_reports/match_001/score_archived_context_diagnostics.json).


### Later result reference development: support exists, target transfer fails

The prior75.802669source image was rechecked and visibly contains TEAM ACE. Inspecting25hash-bound archived source images in75.2–76.4shows the same result text in all25. This clarifies the earlier gap: one positive was verified in the short74.36–74.52window; it was never a whole-video count. Later reference-development images do exist. They are correlated frames of one result episode **after** the target content discontinuity, not25independent events or evidence of when R1 ended. They cannot corroborate/backdate the earlier boundary.

A single fixed reference hypothesis uses three actual distinct images at75.402669,75.802669and76.269336. Training-only foreground intersection above210(uint8), a one-pixel contrast ring, median grayscale reference and three spatial groups feed the existing SemanticTextReference with unchanged per-group NCC0.90. No numerical/GT value, boundary time or ID goes into the matcher. Reference/mask are frozen before predictions; no retry or tuning occurs. All three training examples meet0.90, so the existing constructor succeeds. Eleven other source images remain after0.12sec training-neighbourhood exclusion:3correct accepts,8unknown,0wrong. All were reviewed before predictions. These are same-episode heldout frames, not independent event qualification. Three actual canonical banner-ROI controls (purchase-phase text and two ordinary world views) have0false positives; they do not qualify content-cut or false-round safety.

The already-reviewed early ten-frame source window is then tested as a regression transfer control. The TEAM ACE at74.436002604sec scores0.3876 and stays unknown; the other nine source frames have0false acceptances. The hypothesis is rejected as a sufficient R1-end input. Do not tune on this target control, lower0.90, or count copies/perturbations of its one image as new support. Broader independent training/holdout and qualified same-segment corroboration remain necessary. Existing geometry, player ownership and source-discontinuity policy are unchanged.

Reference development/evaluation runtime1.446sec; no comparable previous runtime/delta. Production/test/shared-script code is unchanged; prior199unique related cases/Ruff/mypy101 checks remain applicable. No runtime sidecar/profile adoption, global qualification report, generated boundary, targeted/sampled/full or canonical PASS change. Historical23/55/4 remains; current/delta unmeasured. Reference images stay Pi-local; hashes/counts/PTS/NCC/reasons are shared in [result-reference diagnostics](../e2e_reports/match_001/round_result_reference_development.json). Windows unverified. This is component source investigation, not lifecycle completion.


### Latest main synchronization and accepted-source contract replay

Read-only remote verification found87upstream commits after the earlier9bb50abd work baseline. Fetched origin and fast-forwarded local main to **fd099fd938830745c749d1a58e9092565bcd7ed3** while preserving the existing uncommitted tracked/untracked source and report files. A private recovery snapshot is kept locally. Only builder.py and test_round_boundary_regressions.py overlap: builder merges cleanly; equivalent boundary filtering uses upstream style, retaining the additional local partial-fragment safety test. Unaffected local changes are byte-verified after synchronization. No new commit or push is made.

Main adds a partial-fragment rule that retains later observed-but-unusable timestamps within the observed fragment; it does not use them as gameplay continuity. Existing local timer-display and global-boundary work remains. Related199tests pass with the installed Validation Pack, zero skips31.44sec; package-builder3tests pass1.90sec. Ruff and mypy101source files pass, as does diff checking. This updates verification to current main; earlier runs keep their original code/commit bindings.

The adopted profile13terminal archive is then replayed through the actual latest builder, trace adapter and unchanged canonical evaluator. All4634saved observations, events, visual observations and zone resolutions are supplied unchanged. No image recognition is rerun, no qualification/GT/round ID/time is injected. Input archive/evaluator assertion hashes and source-video SHA are verified before and after; production-source hashes are frozen through processing. The native packages, trace, all82assertion outcomes and failure set are exactly equal to the archived result:23PASS/55FAIL/4NE, delta0/0/0. One partial package remains at7.369336–171.002669, with no round boundaries. Negative assertion failures remain0in this archived compatibility replay, which does not establish fresh recognition or temporal detection safety. Replay runtime34.047sec; no directly comparable previous run, since the earlier replay used rejected profile16 rather than accepted13. Full video recognition still requires about3h36m36for the historical accepted run; no new full E2E is executed.

This confirms that main synchronization and package scope changes do not repair the real boundary source gap or alter historical assertion statuses. Real lifecycle qualification and all three continuous boundary acceptances remain unmet; fresh full result/delta are unmeasured. No new PASS or feature completion is claimed. Next priority remains source-qualified global lifecycle evidence, with fixed GT/thresholds/identity/ownership/discontinuity policy. Windows unverified. [Latest-main compatibility evidence](../e2e_reports/match_001/latest_main_contract_compatibility.json).


### R1 independent scene investigation (2026-10-09)

The native R1 phase disappearance and both timer-anomaly links now have timer/phase-independent distributed crop NCC and bidirectional feature tracking. At the reset, all six NCC values exceed0.995 and135accepted patches span six regions; the following display drop has minimum NCC0.946 and137accepted patches in five regions. This supports scene continuity/UI transition rather than whole-camera replacement, but cannot exclude edits preserving the same view or prove uninterrupted gameplay time. Every raw display is retained. An actual discontinuity control retains55patch tracks, so LK alone cannot authorize continuity. Excluded-pixel mutation leaves all metrics unchanged. ORB support is insufficient and explicitly inconclusive.

R2 receives the same frozen method; full-view purple occlusion and teammate overlays make R1 crops unsuitable as universal background evidence. It stays inconclusive rather than being declared a cut or qualified continuous. The proposed contract separates image scene status, raw clock/display semantics and content-time vetoes with an explicit pending transient UI state. Production adoption is not enabled; no thresholds, discontinuity/ownership policies, GT, assertions, sampler or runtime source are changed. Related95unit tests pass6.88sec, Ruff passes and mypy101files passes. No targeted/sampled/full is justified without qualification; canonical historical23/55/4 stays the baseline, current/delta unmeasured. No assertion is relabelled. See [full investigation and contract specification](r1_scene_transition_investigation.md) and [source-bound measurements](../e2e_reports/match_001/r1_independent_scene_diagnostics.json). Next priority is the qualified transient-UI evidence contract, with scene-preserving-edit and occlusion negatives; R1-end reference transfer remains separate.


### Transient UI diagnostic temporal prototype

The independent-scene investigation now has an executable diagnostic state machine that retains every raw timer display, models confirmed preparation and pending UI transition, and refuses all event/clock authorization. Cuts, duplicate pixels, gaps, uncertain scene support and phase jitter clear context. Eleven targeted unit cases pass; current106related tests passed before the final state-label correction, with the11prototype cases rerun afterward. Production source and policies remain unchanged.

A frozen all-six-crop NCC0.90 + distributed LK/affine descriptive predicate is insufficient across actual continuous source motion: the preparation span resets before R1 phase loss, producing6phase candidates and24unobserved outputs; R2 gives2and28. No transient state or boundary is declared. This is a rejected automated evidence hypothesis, not a reason to reduce thresholds or invalidate the separate critical-link image finding. The next source-producer work is motion-compensated correspondence and occlusion validity with real cut/duplicate/occlusion controls. Canonical23/55/4is historical, current/delta unmeasured. [Contract, results and limitations](r1_scene_transition_investigation.md#diagnostic-temporal-contract-prototype-follow-up); [source-bound replay](../e2e_reports/match_001/transient_ui_contract_replay.json).


### Crop-local affine scene diagnostics

Source-only affine compensation now supplements the scene diagnostic, with crop-local warping and valid masks to prevent excluded UI entering transformed ROIs. All previous raw R1/R2metrics remain exactly equal; original code SHA is preserved in a private version1snapshot and new diagnostics have separate bindings. At4.302669,2raw high-NCC crops become5compensated ones, indicating motion rather than an automatic cut; the remaining0.899crop is not rounded into acceptance. Weak-texture crops remain unknown. A real cut still has one compensated0.915crop, reinforcing that single-ROI similarity cannot authorize continuity. The different-scene control has no usable affine transform.

All107related cases pass7.31sec, Ruff passes and mypy101production files passes. Production source, thresholds, canonical statuses, full sampler and GT remain unchanged. No qualification or event is created; R2occlusion and R1clock semantics remain blockers. Next work is explicit background/occlusion validity and independent qualification; no full E2E is justified by these descriptive metrics. [Source evidence and controls](../e2e_reports/match_001/scene_motion_compensation_diagnostics.json).


### Opt-in production camera evidence excludes phase/result pixels

The actual CompositeSourceContinuity camera grid overlapped the phase/result panel, violating separation of phase and camera witnesses. Camera-cell NCC now removes a padded canonical panel rectangle from its inputs instead of zero-filling it; OpenCV receives explicit2Dvalid vectors. NCC0.90, variance/support/spatial minima, timer/reset semantics, duplicate/gap/geometry/content-cut vetoes remain unchanged. Method provenance is versioned and the shared code fingerprint changes, so stale qualification reports cannot be reused. No new real qualification or profile is adopted. This is limited panel exclusion, not full semantic-background or occlusion recognition.

All60native R1/R2images and58adjacent pairs are compared against the original HEAD camera method, with terminal video/report/image/pixel/code bindings. R1spatial-quorum links remain25/29; R2falls24→23/29. At111.386002604the old3witnesses become2after panel exclusion, removing an occluded link's camera quorum. This is not a content-cut label or canonical gain. Timer-dependent R1breaks remain fail-closed. Four new unit cases and the complete135related tests pass8.71sec; Ruff and mypy101files pass. Canonical23/55/4is historical, current/delta unmeasured; no full E2E is justified before actual qualification and three continuous boundary acceptances. [Implementation and limitations](r1_scene_transition_investigation.md#production-camera-evidence-phase-contamination-removed); [actual camera comparison](../e2e_reports/match_001/phase_excluded_camera_diagnostics.json).


### Frozen scene-only holdout: static crops are insufficient

A predecode reservation freezes production/scene fingerprints and three explicit source intervals, separate from the60scene-development images. All90native frames and87adjacent pairs are decoded/verified; frame hashes are disjoint from that scene development set. All90contact-sheet panels are reviewed with timer/top HUD and phase/result pixels masked in the visualization only. Ordinary camera/knife/teammate motion is visible, with no obvious whole-scene replacement; uninterrupted game time is not certified.

Phase-excluded production camera quorum covers5/29,1/29and17/29links respectively:23/87total,64abstentions. All-six raw crop NCC succeeds0/87, while LK covers≥3regions on87/87. Fixed crops visibly include foreground/teammates in these withheld contexts, so distributed tracks are not sufficient world-background evidence. Universal fixed-ROI qualification is rejected; neither missing NCC nor motion is labelled a cut, and no threshold is reduced. The next source requirement is region visibility/foreground validity plus motion-aware correspondence. The cohort now supplies development evidence and must not be reused as qualification holdout after method redesign.

Runtime63.483sec includes decode/hashes/measurements; no comparable previous timing. Production code is unchanged in this follow-up and terminal fingerprints match the prior135tests/Ruff/mypy101checks. No new runtime qualification, event, canonical assertion result or full run. Historical23/55/4stays the baseline; current/delta unmeasured. [Decision and source scope](scene_continuity_qualification.md); [withheld measurements](../e2e_reports/match_001/scene_holdout_diagnostics.json); [review provenance](../e2e_reports/match_001/scene_holdout_review.json).


### Cross-region motion diagnostic removes self-fit support

The accepted source patches now have a leave-one-region-out affine diagnostic. The tested region does not fit its own prediction model, and missing peer support stays unknown. This identifies a concrete distinction missed by raw patch counts: the known discontinuity's55patches have peer residual medians10.023/9.671/2.776px in their three supported regions, whereas R1timer reset/drop medians are below0.56px in available groups. Duplicate images fit perfectly and still need an explicit pixel veto.

Ordinary-motion former-holdout spans have high residual in at least one group on70/87links, so error cannot itself label foreground or cuts; parallax/model mismatch also contributes. The150frames/145pairs and three controls are source/hash-bound. Old scene outputs remain exactly equal with an optional track sink; the prior code version is preserved. These cohorts are development now, not new qualification. Six new cases and141related tests pass9.27sec; Ruff and mypy101source files pass. Production, safety thresholds, geometry, GT and assertion statuses remain unchanged; no proof/event/profile/full or canonical gain is claimed. [Results and limits](scene_continuity_qualification.md#out-of-region-motion-consensus-development-follow-up); [model evidence](../e2e_reports/match_001/out_of_region_motion_diagnostics.json).


### Qualified transient UI contract (2026-10-09)

The independent R1 image investigation supports visible scene continuity at phase disappearance and the two anomalous clock links, while scene-preserving edits remain unresolved. An opt-in production `transient_ui_transition` contract now requires separately qualified current-frame scene/UI evidence, preserves every original clock display and source linkage, and confirms an active clock without GT timing/value constants. Synthetic native→package→trace tests cover two rounds, preparation association and no inferred second end; external supplemental proof remains filtered.

No real scene/UI producer or paired qualification is installed, so actual R1/R2 start detection remains incomplete. Historical canonical23/55/4 is unchanged as the baseline; Current/Delta are unmeasured, not synthetic-unit results. No full E2E is justified before qualified source inputs and the three-boundary acceptance gate. Prior diagnostic fingerprints are historical version bindings and cannot qualify changed production code. [Current contract and verification](transient_ui_lifecycle_contract.md) details the remaining background/occlusion and positive UI-evidence producer task. R1-end result reference remains a separate blocker; thresholds, GT, assertions, sampler, geometry and ownership are fixed.

Current follow-up verification: **200 related unit tests PASS (24.97sec), Ruff PASS, mypy102source files PASS**. No fresh canonical E2E or real-source qualification is claimed.


### Reviewed-world feature development follow-up

Restricting background labels to actually linked reviewed reference features raises R1descriptive support21→26of29native links and establishes diagnostic pre_round→transient_ui_transition while retaining every display. Whole-crop matching and a three-reference bank had failed the existing preparation-duration gate. No qualification or runtime event follows from training data; R2remains unsupported and canonical Current/Delta unmeasured. The prototype also no longer counts an initially unattested image toward phase duration. All219related cases pass26.05sec, Ruff passes, and production fingerprint matches the earlier mypy102file check. A prospective same-video holdout is frozen before decode. [Evidence, alternative hypotheses, tests and next gate](scene_world_feature_development.md).

## Frozen scene-world reference holdout result

The subsequent [native holdout investigation](scene_world_feature_holdout.md) measured36previously reserved frames /30adjacent links. The frozen method supported0links, including no distributed adjacent support in nearby R1 camera poses. All36masked panels were reviewed. This rejects production qualification of the current reference bank; missing support remains unknown, not a content-cut label. The original R1 critical-link evidence still favours visible scene continuity with a transient UI display change, while uninterrupted game time remains unproven. No scene/UI qualification or runtime boundary was created, no canonical E2E was rerun, and the82assertion statuses remain unchanged. Reference coverage and trusted producer qualification precede production activation.

## Wider world-patch search: insufficient remedy

The [96-native-image comparison](scene_patch_search_investigation.md) tests whether crop-local search range alone caused the failed scene qualification. Unique reciprocal NCC≥0.90search across existing non-UI crops reduces R1support26→19/29; R2stays0/29and the30former-holdout links remain unsupported. Rejection-stage diagnostics expose repeated-wall ambiguity and missing appearance support. Wider search is rejected as a sufficient remedy; no threshold relaxation, cut inference, qualification or event follows. Production and the82assertion matrix are unchanged; canonical Current/Delta is unmeasured. Next work needs distinctive world-feature structure/reference coverage and independent qualification, not looser patch acceptance.

## Joint feature translation trial

The [four-pose constellation investigation](scene_constellation_investigation.md) retains ambiguous patch alternatives and rejects competing distributed motions. Real poses yield0accepted tracks: either the finite peak budget cannot assess all alternatives, or the changed pose supplies no coherent distributed translation. Static reference-only eligibility removes21/114patches but does not establish support. This implementation is rejected for qualification; neither all spatial methods nor visible scene continuity is disproved. Production and all82assertions are unchanged; no qualification/event/full run or canonical gain is claimed. Next work is distinguishable reviewed background structure and reference pose coverage, preserving the source/producer qualification gate.


## Continuous reviewed-world chain checkpoint

The [continuous tracking investigation](scene_world_chain_investigation.md) preserves reviewed source feature identities without reseeding. Prefix support is0/35; separate stable-input feature support4/29 stops despite86tracks because spatial witnesses occupy one row. Dense source-world crops support3/29; adding a manually reviewed seventh background region leaves3/29 unchanged. Upper and added lower crop NCC values are below0.90 despite full valid warp coverage. These methods remain diagnostic-only and unqualified; missing support is not a cut label. Seven focused tests and Ruff pass. Production fingerprints and all82assertion rows are unchanged; no fresh canonical run, qualification or real boundary is claimed. Work pauses at the requested checkpoint with trusted scene/UI producer qualification still unfinished.


## Native-resolution world-chain hypothesis (2026-10-09)

The [latest-main R1 diagnostic](scene_world_resolution_investigation.md) tests original1920×1080grayscale while preserving normalized spatial limits, NCC0.90and the existing reviewed source footprints. Prefix support remains0/35; separate stable support changes4→0/29despite more initial features141→162. Removing downscaling alone is rejected as a remedy. Failure remains unknown rather than a cut label; production/qualification/events/82assertion rows are unchanged. Ten unit tests, Ruff and fresh mypy102files pass. Canonical Current/Delta remain unmeasured; no full E2E was run.


## Passive R1 world-chain rejection-stage follow-up

[Per-region evidence](scene_world_stage_investigation.md) identifies the missing source-world row: native upper regions lose all35tracks below unchanged OpenCV conditioning, while95original-world-supported points remain in one row. Canonical support loses its final upper witness as an affine outlier after earlier conditioning losses. A proposed lower ROI is rejected before matching because hands/charm and faint ability UI enter it. Instrumented results exactly match preserved behavior on128links;12tests/Ruff/mypy102files pass. Production, qualification, events and82assertion rows are unchanged. Canonical Current/Delta remain unmeasured; no full E2E was run. Next source work needs distinctive, reviewed world-only structure and pose coverage, rather than looser acceptance.


## Adjacent source-world photometry follow-up

[The declared alternative diagnostic](scene_adjacent_world_investigation.md) retains original world-feature identities and their seed NCC while measuring adjacent whole-crop appearance. Stable support3→5/29 confirms cumulative seed comparison explains two early abstentions, but the chain still stops at4.002669 before the timer transition: upper warped NCC0.833926, independent raw NCC0.896447, and the other upper crop's interior texture below1. Prefix remains0/35; no unknown is relabelled as a cut. Existing-mode dictionaries are unchanged on116links;15tests/Ruff/mypy102files pass. Production, qualification, events and82assertion rows are unchanged; canonical Current/Delta remain unmeasured. Strict full-footprint signal assessment is the next untested hypothesis, not a margin/threshold fallback.


## Complete source-footprint diagnostic follow-up

[The explicitly declared full-valid footprint](scene_full_footprint_investigation.md) excludes every sampled padding contribution while using complete reviewed crop support. Stable links5→11/29 reach the last purchase-phase image; all six photometric regions are strong there. At phase disappearance4.102669, all five remaining seed-region1tracks are original-seed partial-affine outliers, leaving only two seed regions, so no chain/event is bridged. Existing defaults are exact on174links;18tests/Ruff/mypy102files pass. Production, qualification and82assertion rows are unchanged; canonical Current/Delta are unmeasured. Next diagnose the source-camera projection residual, preserving the third-region requirement and HUD geometry policy.


## R1 camera-model membership follow-up

[The source-camera audit](scene_camera_model_investigation.md) finds that the original similarity RANSAC mask contains63/68points at phase disappearance, whereas the final same-matrix2pixel forward error includes66. An explicitly declared diagnostic keeps original consensus>=0.90and adds bidirectional final-model membership, original-seed/adjacent NCC>=0.90and distributed world-only crop photometry. Training support11→22/29now spans both2:25frames and the1:39transition; it stops at4.286003without reacquisition. Visible scene continuity is supported on these development frames; uninterrupted game time and independent qualification remain unproven. Existing defaults are exact on203links; exposed cut/duplicate controls reject,26unit tests/Ruff/mypy102files pass. Production and all82assertion rows are unchanged; canonical Current/Delta are unmeasured. No full E2E was run. Next freeze the method and qualify independent world-only scene/UI evidence before activation, preserving the separate R2/result gates.


## Frozen final-membership cohort result

[The pre-reserved camera cohort](scene_final_membership_cohort_investigation.md) yields0/33supported links on36native images, with0PNG-byte overlaps against2098previously stored images. The first wall seed retains94identities in6regions but fails unchanged0.90valid crop coverage; two other poses contain players/knife/UI in the fixed footprints and lack world-only seed attestation. Reviewed panels show continuous-looking motion rather than proving a cut. No qualification or runtime event follows; no code is tuned to this result.28tests/Ruff pass, production and82assertion rows remain unchanged, canonical Current/Delta are unmeasured. The next source contract must separate reviewed seed eligibility, current occlusion and motion-dependent appearance footprint; changing camera models or OCR thresholds does not resolve this blocker.


## Frame-bound world review eligibility contract

[The offline review gate](scene_world_review_contract.md) separates reviewed world-only seed/current footprints from matching scores. It pins canonical pixels/native PTS/video/epoch/provenance, rejects unreviewed or occluded footprints and terminates on missing review, gap, duplicate or cut without reacquisition. Three real seed examples change3hypothetical initializations→1reviewed; two unsafe/unattested seeds are rejected before extraction. The valid wall seed still abstains at the original coverage predicate, so no real support or boundary is invented.38related tests/Ruff/fresh mypy102files pass; production and82assertion statuses remain unchanged, canonical Current/Delta unmeasured. This wrapper is diagnostic only: offline annotations are not runtime truth or producer qualification. Next address projected-world appearance coverage and current occlusion without lowering0.90floors.


## Reviewed projected-world appearance development

[The declared projected-footprint diagnostic](scene_projected_world_investigation.md) reuses the exact existing adjacent source-camera transform on the exposed wall pair. Current bilinear taps must all lie in explicitly reviewed world; complete-source coverage>=0.90/NCC>=0.90are unchanged. Appearance support0→6regions, minimum NCC0.974528, explains fixed-crop coverage loss while94original identities remain. This is one-link development evidence; the original tracker still abstains and is not revived. Default decisions are exact on203links, exposed cut/duplicate controls reject,44tests/Ruff/fresh mypy102files pass. Production and82assertion rows remain unchanged; canonical Current/Delta unmeasured. Next integrate continuous source/current world eligibility and projected appearance before independent qualification, never copy offline per-frame annotations into runtime truth.


## Continuous reviewed projected-world checkpoint

[The integrated diagnostic](scene_projected_chain_implementation.md) preserves original world identities/current flow-footprint review while using projected appearance at unchanged0.90coverage/NCC floors. The exposed12native-frame wall episode changes0→4/11supported links; at2.586003hand/unknown lower-footprint review terminates tracking and no later image rejoins. An initially overlapping unknown annotation was correctly rejected; consistent positive-mask encoding leaves all first5rows unchanged. Existing defaults are exact on203links, exposed cut/duplicate controls reject,53tests/Ruff/fresh mypy102files pass. Production and82assertion rows are unchanged, canonical Current/Delta unmeasured. No qualification/event/full E2E is claimed. Next verify the actual R1transient episode, then independently qualify source/current semantic evidence before runtime activation.


## Actual R1 projected-world transient replay

[The frozen30-native-frame replay](r1_projected_chain_investigation.md) supports22/29links, unchanged count versus the previous final-membership diagnostic. Phase disappearance/both2:25frames/first1:39all have six distributed projected world regions with minimum NCC0.995367/0.995436/0.943096/0.952934. At4.286003the unchanged original model-consensus gate fails and tracking never rejoins. This directly reinforces visible scene continuity with transient UI, not uninterrupted hidden game time or runtime qualification. Shared replay CLI verifies code/source/PNG/pixels/coverage terminal bindings in9.819518seconds. Core bytes remain those with53tests/mypy102files passing; fresh Ruff passes. Production and82assertions remain unchanged, canonical Current/Delta unmeasured, no full E2E. Next implement image-derived world reference bootstrap/current occlusion with independent qualification; offline per-frame masks are not runtime truth.


## Image-only reviewed-landmark bootstrap result

[The strict diagnostic reference entrance](scene_world_bootstrap_contract.md) consumes current pixels without PTS/GT/per-frame world annotations. The unchanged unique reciprocal matcher supports only its own reference image, 1/7 exposed frames; all four actual R1 start-transition queries lack distributed quorum. This is rejected as a qualification remedy, not interpreted as a content cut. Matched patches do not authorize whole-ROI background masks. 62 related tests pass in14.84seconds, Ruff passes, and fresh mypy passes104source files on main80d0d46. Production and82assertion rows are unchanged; canonical Current/Delta remain unmeasured, with no full E2E. Next retain image-qualified source-world identities and reject current footprint occlusion without manual runtime masks before independent qualification; do not repeat reference-bank/threshold tuning.


## R1 tracked footprint scope audit

[The passive 15/21/31-pixel audit](scene_track_footprint_audit.md) finds complete projected original-source appearance support across the timer transient, but every critical all-size witness remains in one spatial row (0/6 distributed queries). Synthetic controls demonstrate both surrounding occlusion hidden by a matching central patch and small foreground hidden by mean NCC. These scores cannot authorize whole-ROI semantic masks or replace the missing distributed runtime producer. The unchanged diagnostic still supports22/29links; no production/qualification/event/canonical gain is claimed. All82assertions remain unchanged; canonical Current/Delta are unmeasured and no full E2E is run. Next source work must provide image-derived distributed background-domain evidence with explicit footprint/ambiguity/occlusion handling, preserving all floors.


## Distributed scene-domain ambiguity follow-up

[The frozen five-link domain audit](scene_domain_ambiguity_investigation.md) identifies distinctive upper-wall structure: domain0supports every transient link with NCC>=0.943096and no competing displacement in the declared17×17local lattice. Other high-NCC domains have5–39competing positions, so independently localized domain quorum remains0/5. Source-only tracking decisions stay22/29; no semantic mask, runtime proof, qualification, event or canonical improvement is claimed. Four focused tests pass; source/PNG/pixel/code bindings match terminal hashes. All82assertions are unchanged. Next test joint distributed camera hypotheses, preserving explicit competitors and complete footprints, rather than counting each repeated domain as independent evidence.


## Joint background-domain camera hypothesis checkpoint

[The complete local-lattice audit](scene_joint_domains_investigation.md) supports the fixed camera projection jointly on5/5critical native R1links with three-cell/two-row/two-column source/current witnesses and no surviving/unresolved local translation competitor. Per-domain independence remains0/5; it is not relabelled. Optional offset instrumentation preserves all five old domain dictionaries exactly; the tracker remains22/29. Eight new joint tests plus four domain tests pass, Ruff passes, and production/all82assertions are unchanged. This is exposed local appearance, not foreground-free semantic masks, hidden-time proof, qualification or canonical gain. Next freeze continuous source/limited witness scope and verify unexposed holdout/negative controls before runtime activation. No full E2E was run.


## Frozen joint source cohort: qualification withheld

[The36-frame native cohort](scene_joint_cohort_investigation.md) finds15previously exposed decoded images and no evaluated joint links. All three first-link original camera consensuses are below0.90(74.36%,84.21%,83.64%); the chain terminates without rejoining. Joint accuracy is not evaluated, rather than0/33wrong. Full-context review finds moving players/arms/knife/barrier/UI in fixed source footprints, so hypothetical seeds are not world-attested. No qualification/runtime event follows.15focused tests/Ruff pass; production and82assertions are unchanged, canonical Current/Delta unmeasured, no full E2E. Next complete image-only source-world seed eligibility before arbitrary-pose positive qualification; do not tune joint/consensus floors to this cohort.


## Stateless reference-domain initialization contract

[The image-only source initializer diagnostic](scene_domain_bootstrap_contract.md) explicitly distinguishes reviewed reference assets from previously observed native frames and rejects landmark-scope promotion/competing reference selection. Eight exposed images yield only the self-reference proposal; all actual R1transition queries fail unchanged global model consensus before joint appearance. The static route is rejected as a sufficient reacquisition/qualification remedy; no threshold/bank tuning follows.22related tests/Ruff pass; production and82assertions are unchanged, canonical Current/Delta unmeasured and no full E2E. Next preserve the measured continuous source-world chain from an actual image-supported seed, with explicit current/temporal scope and independent qualification; a reference asset cannot supply a prior native observation.


## Observed source seed to continuous image-derived scene links

[The complete observed-source diagnostic](observed_scene_chain_contract.md) binds the first actually observed native PTS/pixels without counting reference assets as a previous source frame. No manual current-frame masks are supplied. Original identities plus fixed joint appearance reproduce22/29native R1links including all5critical transient links; at4.286003original model consensus fails and the episode never rejoins. Four protocol and two image-only synthetic controls reject all links/rejoin.13related tests/Ruff pass; production and82assertions are unchanged, canonical Current/Delta unmeasured, no full E2E. This is exposed limited-scope appearance, not semantic foreground absence/hidden-time proof/runtime qualification. Next freeze independent continuous acquisition/holdout/negative assessment and source-confidence provenance before production integration.


## Observed-source decoder boundary safety

[The observer input contract](observed_scene_chain_contract.md) now terminates and clears observed state for non-array decoder outputs and non-boolean discontinuity metadata. Nine new regression cases verify that neither stale state nor reference reacquisition survives; 22 related tests, Ruff and 104-file mypy pass. Production/82 assertion statuses are unchanged; canonical Current/Delta unmeasured. No E2E was run. Independent qualification and source-confidence provenance remain the next blocker.


## Observed-source measured witness provenance

[The frozen native replay](observed_scene_chain_contract.md) now retains profile/reference, source-domain boxes, fixed camera transform and measured NCC on all22successful links. Same30native frames produce22/29links and5/5critical links, unchanged from the previous observer. Frozen source/profile/code/input terminal hashes match; minimum accepted witness NCC is0.909788072.30related tests/Ruff pass. This adds traceable appearance evidence, not hidden-time confidence or runtime qualification. Canonical Current/Delta remain unmeasured; production and82assertions unchanged. Next independently assess the complete acquisition/continuous source route and paired UI-transition evidence before activation.


## Non-self native acquisition through R1 transient

[Near-seed acquisition evidence](scene_near_seed_acquisition.md) contradicts an exact-self-reference-only assumption:6/12exposed images support unchanged image-only initialization, including3.886003with151tracks/147inliers. A frozen continuous replay from that different observed image preserves5/5critical transient links;19/30total links end safely at4.219336without rejoining. Shared later endpoints retain18/29versus22/29with the original seed, a measured shorter lifetime rather than hidden reseeding. No thresholds/code/production/assertions change; qualifications remain0and canonical Current/Delta unmeasured. Next reserve disjoint acquisition-plus-continuous holdout/negative episodes; these exposed observations cannot qualify runtime.


## Complete observed acquisition path in native cohort orchestration

[The native runner integration](observed_scene_cohort_runner.md) freezes reviewed profile/assets/code before decode and evaluates the actual image-supported observer, with one non-restarting source episode per explicit window. It reproduces19/30R1links and5/5critical links. A preselected, known-exposure-disjoint12frame context never initializes;0joint links are evaluated, so this is coverage failure rather than wrong continuity.37related tests/Ruff pass; production/82assertions unchanged. Canonical Current/Delta remain unmeasured; no full E2E. The source route now has reproducible independent-cohort orchestration, but no qualified positives or runtime activation.


## Fixed-crop reference acquisition failure isolated

[The new source-pose experiment](scene_acquisition_flow_failure.md) rejects adding static references as a sufficient remedy. A reviewed13-second source context self-matches78tracks, but the pre-reserved12-frame near-context interval cannot initialize. Passive stage counts show136source features:107invalid flow/status,29forward/backward rejection,0features reaching NCC. Default two-image bootstrap outputs remain exact after instrumentation;45related tests/Ruff pass. This is current-view acquisition under displacement, not NCC failure or a proven content cut. New profile stays private/unadopted, qualifications remain0, production/82assertions unchanged and canonical Current/Delta unmeasured. Next redesign current search/projection with explicit ambiguity/UI/source eligibility safeguards before fresh independent acquisition qualification; do not enlarge a reference bank or tune thresholds.


## Displaced source/current support hypothesis rejected on development

[The optional displaced matcher](displaced_reference_acquisition.md) separates reviewed source crops from permitted current candidate domains, retaining NCC0.90/unique reciprocal/90%model and complete projected tap/joint requirements. Synthetic motion works; actual13.202669acquisition remains0correspondences/proposals.78patches partition into40no qualified peak,33forward ambiguity,5reverse ambiguity. Merely widening destination search is rejected as sufficient; no runtime/profile deployment or new holdout/full E2E.55related tests plus six final bootstrap tests/Ruff pass; default two-image outputs, production and82assertions unchanged. Next investigate motion/appearance-normalized correspondence with unchanged final photometric/current-eligibility safeguards; do not accept competing peaks or lower thresholds.


## Descriptor geometry proposal lacks distributed real source support

[The descriptor-proposed camera audit](descriptor_reference_acquisition.md) keeps descriptor scores separate from NCC and requires90%model/photometric support plus3source regions and complete current/joint appearance. Synthetic translation/rotation/scale works, but all5exposed real pairs fail3-region descriptor support before model formation: original R1self/phasegone matches are confined toregion2; arch self supports onlyregions0/2and displaced context onlyregion0.0/5proposals; no independent holdout or full E2E.19related tests/Ruff pass; orientations cannot inflate physical-witness count. Method is diagnostic/unadopted; production/82assertions and canonical Current/Delta remain unchanged/unmeasured. Next reassess independently observable source-world structure/eligibility rather than lowering regional support or launching another matcher from synthetic success.


## Source eligibility separates descriptor loss from absent background structure

[The frozen source audit](source_structure_eligibility.md) finds eligible existing corners in all6R1regions(180)and3arch regions(78), while canonical/native SIFT remains confined to1/2regions. Native resolution does not recover distributed descriptor support; this is method-specific detector/representation eligibility, not proof that reviewed source images have no usable background structures. No code/profile/threshold changes or new qualification/canonical result. Next describe the existing eligible reviewed corners without losing their regional support, then test actual displaced correspondence at all unchanged final safety gates; do not rebuild references or lower support based solely on SIFT absence.


## Existing corner descriptors recover source support but not actual acquisition

[The explicit corner-to-descriptor integration](corner_descriptor_acquisition.md) preserves GFTT100/0.01/5and all final reciprocal/3-region/model/NCC/current-domain/joint gates. Arch self-query now produces16verified correspondences across3regions and a diagnostic proposal; actual displaced arch and R1phasegone still fail3-region support.0/5→1/5is self calibration only, not a runtime/canonical gain. R1source candidates span6regions but current matching staysregion2/5, implicating current spatial candidate eligibility/correspondence.24tests/Ruff pass; five default outputs and terminal inputs match, production/82assertions unchanged, canonical Current/Delta unmeasured. Next assess source/current spatial candidate eligibility at unchanged conditions before fresh qualification, not another matcher or weaker support.


## Same-image current-candidate loss quantified

[Crop-context calibration](corner_crop_context_analysis.md) isolates a source-route failure without camera/clock/phase changes: 249/264 context-eligible R1 source candidates fall below the existing current crop-relative corner quality, and only15/295 have a current candidate within1pixel. Forced same-point descriptors also differ with crop context. This supports spatial candidate/context redesign, not threshold relaxation or a content-cut verdict. Read-only diagnostic/Ruff pass; production and all82assertions unchanged, qualification0, canonical Current/Delta unmeasured. No full E2E.


## Spatial candidate/context recovery: real camera consensus still fails

[The explicit diagnostic representation](spatial_descriptor_acquisition.md) preserves final gates while describing local GFTT proposals from identical19pxcontexts. R1phasegone16/2regions→52/4regions, but only26/52support one camera; arch displaced7/21also fails original90%consensus. Actual acquisition remains0, self proposals1unchanged. R1self286camera matches reaches only170available photometric witnesses, safely rejected. Old five corner outputs remain exact; production/all82assertions unchanged, no qualification or canonical gain. Next partition source texture/current availability before matching, without pruning failed camera/photometric evidence afterward.


## Actual camera mismatch separated from self-source texture defect

[Passive photometry partition](descriptor_photometry_partition.md) attributes all116R1self unavailable points to source std<1. Actual R1phasegone has only1such point among26camera outliers, so source eligibility alone cannot repair actual consensus(26/51at best without refitting).17camera-outlier endpoints nevertheless show NCC>=0.90at the saved camera projection, reinforcing that appearance is not localization proof. Old decisions/production/all82assertions unchanged;3diagnostic tests/RuffPASS, qualification0, canonical Current/Delta unmeasured. Next investigate endpoint ambiguity with frozen competing locations, not source-only self calibration or another full run.


## R1endpoint appearance ambiguity confirmed

[The frozen competitor audit](descriptor_endpoint_ambiguity.md) finds53–1441qualified integer positions outside2pxof the fixed camera projection for each of17appearance-supported camera-outlier tracks.16/17descriptor endpoints also showNCC>=0.90, proving local appearance is not unique localization. Counts are positions, not independent peaks/camera hypotheses. Original26/52consensus rejection, production andall82assertions remain unchanged;3tests/RuffPASS, qualification0andcanonicalCurrent/Deltaunmeasured. No E2E. Next require coupled distributed-domain evidence and explicit competitors, not a favorable point subset or threshold relaxation.


## Full-domain evidence also rejects displaced descriptor camera

[The frozen five-pair full-domain audit](fixed_camera_domain_audit.md) finds actual R1witnesses1/2/5only, inadequate source/current spatial distribution and5joint competing offsets. Upper/right NCC0.749/0.732and current texture<1prevent independent support; whole-domain appearance cannot override26/52camera rejection. Original decisions/production/all82assertions unchanged;13tests/RuffPASS, qualification0, canonicalCurrent/Deltaunmeasured. Stop isolated descriptor tuning; next inspect delayed image-supported initialization of the existing observed native source route, preserving no prior history/no silent rejoin and independent qualification.


## Explicit pending acquisition preserves no-history/no-rejoin distinction

[The deferred observer diagnostic](deferred_observed_initialization.md) starts only after image-supported acquisition; five unknown prefix images retain metadata but no scene history. Exposed36native frames0default→19opt-in links, including5/5critical links; acquisition at3.886003and permanent stop4.219336match the earlier non-self replay. Original30default outputs remain exact22links.30tests/Ruff/mypy104filesPASS; production/all82assertions unchanged, qualification0, canonicalCurrent/Deltaunmeasured. Next freeze this opt-in in native cohort orchestration and independently assess the complete path, not another isolated matcher or threshold change.


## Frozen delayed-acquisition cohort: exposure gate correctly withholds qualification

[Native runner integration](deferred_observer_cohort.md) forwards strictly frozen observer options and retains default schema.54native frames reproduce19exposed R1links and permanent stop, but the reserved18frame acquisition context is18/18known PNG/native overlap. It cannot qualify holdout; no new correct/wrong continuity claim follows.45tests/RuffPASS, production/all82assertions unchanged, qualification0, canonicalCurrent/Deltaunmeasured. Next select disjoint contexts from provenance PTS ranges before decode rather than repeatedly treating nearby frames as new holdout.


## PTS-gap-reserved frames are known-disjoint but cannot initialize

[Source qualification assessment](pts_gap_source_qualification.md) inventories304known native ticks before decode and reserves two genuine gaps.9/9frames have0known PNG/native-pixel overlap, but all9initializers have0accepted reference tracks, so0scene links are evaluated and qualification stays withheld. Do not report0wrong or recycle this now-exposed cohort as fresh holdout.2inventorytests/RuffPASS; production/all82assertions unchanged, canonicalCurrent/Deltaunmeasured. Reassess observable source acquisition scope before more arbitrary holdouts; no full E2E or new recognizer profile follows.


## Runtime source producer readiness is a separate blocker

[Current-main contract audit](lifecycle_runtime_readiness.md) confirms analyzer emits only legacy composite proof while paired lifecycle requires source-owned scene/UI proofs; external tokens are correctly filtered. Valid paired qualification now gets an explicit startup missing-producer diagnostic, without recognition/qualification/threshold changes. Existing timer-display transport is already implemented; anonymous killfeed cannot establish nonself facts.102relatedtests/Ruff/mypy104filesPASS, all82assertions unchanged andcanonicalCurrent/Deltaunmeasured. Next build the qualified native producer-to-analyzer path with independent source/world/UI gates, rather than further isolated appearance variants or unnecessary full E2E.

## Phase disappearance also requires an independent source contract

[Optional group measurements](r1_phase_rejection_evidence.md) preserve actual crop/frame/PTS bindings and distinguish contrast-unavailable input from mismatching text. All30saved native R1outputs remain identical;12presence matches followed by18unknowns with54low-contrast groups. The current semantic matcher proves presence only: neither missing flags nor flat masks authorize disappearance or scene continuity.134relatedtests/Ruff/mypy104filesPASS; no qualification/boundary/canonical result added, all82assertions unchanged. The paired runtime producer needs independent phase-absence qualification as well as source-world continuity; do not convert diagnostic dictionaries into trusted proofs.

## Shared scene measurement layer extracted for native producer integration

[The common image engine](shared_scene_domain_engine.md) removes production's future dependency on diagnostic-only domain implementations. Old diagnostic imports re-export shared code; all six native R1 domain outputs,1,734offset measurements and joint result are exact before/after. Frozen cohort bindings now require the common engine before decode.64initial relatedtests/Ruff/mypy105filesPASS; real qualification/installed sceneUIproducer remain0. All82assertions and canonical baseline remain historical/unmodified. Next extract observed source ownership/acquisition into the same production package, retaining termination/qualification gates; no appearance result becomes an attestation.

## Original-identity and projected-appearance tracking is now shared

[Common tracking extraction](shared_scene_tracking_engine.md) preserves the normalized algorithm AST for six functions/classes and all30actual native observed-source outputs exactly. Descriptive links remain22and terminated frames never rejoin.155relatedtests/Ruff/mypy106filesPASS; native replay49.030276→48.654446seconds is a one-run fluctuation, not a claimed speed or recognition gain. Frozen cohort/projected replay bindings require both common engines. All82assertions stay unchanged; no qualification, installed paired producer or canonical result is added. Next extract image-derived acquisition and actual native episode ownership into the shared package before qualified analyzer integration; do not promote descriptive output to trusted world/UI evidence.

## Observed native ownership is common; source acquisition qualification is still absent

[The common episode owner](shared_native_scene_episode.md) separates a typed image-only initializer factory from actual observed PTS/pixel/epoch history. It validates cadence before asset loading and preserves metadata-only pending acquisition, original identities and permanent termination. All30R1results/bindings remain exact and22links unchanged; three method bodies match after typing/import normalization.160relatedtests/Ruff/mypy107filesPASS. Native runtime48.654446→49.293477seconds is a fluctuation, not a gain. All82assertions remain unchanged and canonical Current/Delta unmeasured. The analyzer still has no qualified scene/UI source entrance; next extract validated reference loading/acquisition, then independently qualify source/world/current phase absence before releasing any proof.

## Common reference/acquisition path no longer imports diagnostics

[Common source acquisition](shared_scene_acquisition.md) preserves seven normalized calculation/validation definitions, profile-relative reviewed assets, hashes/provenance and reference-ambiguity rejection. A direct common-package-only30native R1replay matches every preceding frame output/source binding exactly, retains22links and verifies reference assets at completion.197relatedtests/Ruff/mypy109filesPASS; runtime49.293477→48.918016seconds is a fluctuation. All82assertion entries remain unchanged; qualified analyzer entrance and independently qualified source/world/current phase-absence inputs are still absent. Next bind the source profile/assets to qualification and deliver actual native lifecycle input without altering full sampler; common appearance output alone cannot become an attestation.

## Configured source assets now invalidate stale qualification; native delivery is distinct

[Source binding](scene_source_binding.md) joins explicitly configured reviewed source JSON and validated image assets to the analyzer base fingerprint. Mutated, missing or escaped assets fail before observation; HUD-only reports cannot authorize a different source configuration.69 related tests/Ruff/mypy110filesPASS. The archived full cadence audit finds2,253/4,633observation pairs beyond one native step and omission of the phase-disappearance/transient frames around R1. These are sampling gaps, not content-cut evidence. Preserve the full sampler and deliver separately owned native system lifecycle inputs; do not relabel native previousPTS/pixels to fit sampled observations. All82assertions remain unchanged; qualified scene/UI producer0 and canonical Current/Delta unmeasured. No E2E launched without an independently qualified candidate.

## Native decoder input reaches the common scene episode through production APIs

[The verified native entrance](native_source_entrance.md) joins explicit interior source-window decode, integer-PTS coverage and video/pixel integrity to the analyzer's common observed episode. One real R1decode preserves all30native ticks/pixels and all preceding scene outputs except the newly owned decoder epoch; links remain22.178unit/integrationtests/Ruff/mypy112filesPASS. Verification70.662816seconds includes decode/integrity work and is not comparable to the48.918016second saved-image replay as a speed change. Source/world/currentphaseabsence qualification remains unavailable; no proof, boundary or player-owned fact is released. Native whole-video streaming and qualified lifecycle/event merge remain incomplete. All82assertions remain unchanged, canonical Current/Delta unmeasured, no full E2E.

## R1 first transient also changes foreground; timer-only interpretation is unsupported

[Native UI localization](native_ui_localization.md) measures all29saved R1pairs with explicit timer/panel exclusion and six independent background regions. At the first transient, background minimum NCC0.995074 contrasts with whole non-UI NCC0.345489 and389,399changed non-UI pixels, concentrated in lower hand/knife presentation. Native full-image review confirms foreground pose changes. This is compatible with a normal view-model transition or a background-preserving content jump; neither is proved. Preserve fail-closed qualification rather than using matching backgrounds to authorize a pure timer transient.6diagnostic unit tests/RuffPASS; production andall82assertions unchanged, canonical Current/Delta unmeasured. Next investigate independent foreground temporal/animation controls in the current video before paired scene/UI authorization; no R2/banner threshold adjustment or full E2E.

## Exposed foreground comparison does not qualify normal animation

[The native control comparison](native_foreground_control_analysis.md) covers 126 development frames and a separately decoded five-frame pair. An inspect-like pose switch also lowers whole non-UI NCC to 0.524857, but the best three-crop post-pose minimum is 0.842172 and control background minimum is 0.833593. Neither meets all-region 0.90 support. Static pre-pose crops include background, and the control has no independent no-edit label. Thus whole-screen NCC alone cannot classify a cut, and this comparison cannot authorize an animation whitelist or R1 continuity. Eleven diagnostic tests and Ruff pass; production and all 82 assertion entries are unchanged. Canonical Current/Delta remain unmeasured. Next separate distributed camera evidence from view-model presentation and independently qualify phase disappearance; no full E2E candidate exists.

## Separate non-text phase structures establish image-change ordering

[Native phase-panel structure measurements](native_phase_structure_analysis.md) verify all30saved frames and show upper/lower panel edges plus purchase-button contrast weakening together at4.102669seconds, one native frame before the transient timer/view-model change. This corroborates panel removal in exposed imagery without converting a nonmatch into absence. Opaque obstruction or source replacement remain unexcluded; all phase-absence outputs remain unknown. Production and82assertions are unchanged, qualification0 andcanonicalCurrent/Deltaunmeasured. Next independently test background reveal versus obscuration and source continuity before scene/UI producer authorization. No full E2E.

## Background color agreement is corroboration, not phase-absence proof

[Current-image reveal assessment](phase_background_reveal_analysis.md) measures all30native source images and four explicitly synthetic sensitivity controls. Panel-target residuals fall25.725/24.688/58.985 to1.945/1.167/0.871 at disappearance, while independently excluded context regions remain supported. Black/white/text-only covers differ, but a surrounding-color full cover also has low residuals. Reject color-fit-only absence authorization; this does not prove an edit in the actual video. Qualification0, production/all82assertions unchanged, canonicalCurrent/Deltaunmeasured. Next use qualified temporal source structure rather than more residual-threshold variants. No full E2E.

## Production native API cohort exposes acquisition coverage limitation

[The frozen independent-context source cohort](native_scene_entrance_cohort.md) uses updated433known ticks/1961pixel exclusions and complete production native decode/scene APIs. All12frames have0known overlap but remain acquisition-pending, so0continuity pairs can be evaluated and no zero-wrong or holdout qualification follows. Native first/last image review shows a different background from the close-wall reference.15relatedtests/RuffPASS; production/all82assertions unchanged, qualification0andcanonicalCurrent/Deltaunmeasured. Next reassess source acquisition coverage and independent controls separately from tracking/UI absence, rather than arbitrary reference banks or another full E2E.

## A matching source reference alone does not repair independent acquisition

[One fixed doorway development proposal](doorway_source_coverage_assessment.md) yields1self initialization and0observed links on12now-exposed frames, failing the predeclared minimum3development support. At the next frame,15/15reference correspondences are coherent and two domains exceed0.90, but the upper-left projected footprint crosses phase exclusion and three-region joint support fails. The observed chain separately stops at insufficient reviewed-world tracks and never rejoins. Reject this proposal; no favorable reference bank/crop retuning or new holdout follows. Production/all82assertions unchanged, qualification0, canonicalCurrent/Deltaunmeasured. Next require source-profile multi-frame eligibility and projected exclusion diagnostics before native producer qualification.

## Bound development screen rejects reference-self-only coverage

[The standalone source training screen](scene_training_support_screen.md) validates existing profile/code/native bindings, distinct native cadence, episode no-rejoin and non-reference temporal support. It rejects the doorway case with exit2:1self match/0non-reference matches/0scene links;124of3720upper-left projected pixels touch exclusion at the next frame.10relatedtests/RuffPASS. It is not integrated into a generator or production and provides no qualification. All82assertions unchanged, canonicalCurrent/Deltaunmeasured. Next actual source acquisition must retain distributed eligible footprints under motion before independent scene/UI qualification and native lifecycle integration; diagnostic completion is not producer completion.

## Explicit production native scene transport remains qualification-gated

[The production entrance](qualified_native_scene_transport.md) now joins configured source assets, matching paired qualification and decoder-owned native measurements to the lifecycle scene-only proof schema. Spatial-cell collisions retain the lowest domain NCC; terminal report/reference/native/code changes withhold buffered proofs.65contract/relatedtests/Ruff/113-filemypyPASS. Positive transport tests use synthetic qualification and mocked scene calculations; actual saved-frame guard has no qualification and releases0proofs/events. No complete paired UI producer, native lifecycle merge or canonical activation exists yet. All82assertions unchanged, canonicalCurrent/Deltaunmeasured. Next independently qualify source/current-world and UI disappearance, then integrate native system observations; the new code fingerprint invalidates old qualification rather than grandfathering it.


## Continuous R1 context exposes long-term model limitation

[The full 3–6 s native development window](r1_continuous_source_analysis.md) covers 180 frames without skipping. Initialization at3.886003s yields19links and stops at4.219336s: original seed partial-affine support52/58(89.6552%) fails the unchanged90%floor, while the same candidates from the preceding native image fit58/58withmaximumresidual0.322081px. An observational sink replay preserves all21productionoutputs exactly. The earlier short window stops4.286003s, so source-history dependence must be distinguished from a content cut. No threshold/policy/GT/sampler is changed; no continuity qualification or canonical result follows. Next separate original identity/acquisition from adjacent source motion under independently reviewed controls; foreground/UI qualification and native lifecycle integration remain blockers.


## Independent background appearance corroborates adjacent tracking at the stop

[The R1 stop-link follow-up](r1_continuous_source_analysis.md#follow-up-independent-appearance-at-the-stop) evaluates the frozen adjacent motion model on six background domains with the unchanged complete displacement lattice. All sixNCCs≥0.973564 and nojointalternative corroborate58/58adjacentpoints at4.219336s; long-termseedfailure is not itselfcontent-cut evidence. A separate180-frame client-graphcolorprobe is rejected after nativeimage review shows transparent world/weapon contamination. No productionpolicy/threshold/profile/GT/assertionchange or qualification; all82assertions unchanged, canonicalCurrent/Deltaunmeasured. Initialforeground/UI qualification and native lifecycle/package/trace delivery remain incomplete.


## Near-flat revealed background cannot supply a supported UI absence reference

[The fixed panel-background feasibility probe](r1_phase_background_reference_feasibility.md) measures180existingnativeframes with three fixed groups. The reviewed first panel-gone image has groupcontrast0.850787/1.650267/0.530326, below the existingmaskedNCCfloor5, so the specific proposal has0supportingframes and is rejected before any asset/profile/qualification generation. Highwhole-cropNCCdoesnotoverride unavailablegroupstructure.29semanticunit tests/RuffPASS; production thresholds/policies/source unchanged, all82assertion records unchanged andcanonicalCurrent/Deltaunmeasured. Next examine otherpositiveglobal image/temporalstructures for qualifiedUItransitions; native lifecycle/package/trace work remains incomplete.


## Foreground pose correspondence does not qualify a normal-animation whitelist

[The fixed three-region correspondence investigation](r1_foreground_correspondence_analysis.md) compares four consecutive earlier/R1post-pose pairs plus two visibly different-pose controls. NativeBGRconversion, reciprocalLK≤1px, patchNCC≥0.90/contrast5 andpartial-affine2px/consensus0.90 produce first-pair74/85inliers(87.06%)and0/4geometricquorums. All6results remain unqualified; no ROI/threshold retuning or animation whitelist follows.3diagnostic tests/RuffPASS; production/all82assertions unchanged, canonicalCurrent/Deltaunmeasured. Existing-video provenance question is pending; source/world/UI qualification and native lifecycle/event/package/trace integration remain incomplete.


## Native global observation entrance separates measurement from authorization

[Native system observation transport](native_system_observation_transport.md) now passes decoder-owned frames through verified image reads and the existing analyzer, preserving actual PTS/hash, accepted original timer display/provenance, phase/score confidence and incompatible-state guards. The global projection excludes player-owned facts and does not build events or issue proofs. Terminal native/profile/code mutation or stale cached profile rejects buffered output. 81 related tests, Ruff and 114-file mypy pass. A four-frame exposed R1 transport check takes 3.545511 seconds but all four frames require calibration and release no timer display, proof or event. This early-window blocker does not reclassify canonical geometry failures. No qualification or default sampler/threshold/GT/assertion change; all 82 assertion records unchanged, canonical Current/Delta unmeasured. Independent source/foreground/UI qualification and native lifecycle/package/trace delivery remain incomplete; no full E2E candidate exists.


## Continuous native prefix resolves acquisition-context rejection

[Native prefix validation](native_system_prefix_validation.md) now processes all256source frames from the first probed video PTS through R1 in one decoder epoch, with the existing production analyzer and no supplied anchors. Geometry acquires once and remains effective on256frames under the unchanged retention policy. Of256timer displays234are accepted and22unknown; accuracy for all234is not claimed. The same four formerly calibration-required images now preserve4/4displays, and24same-pixel prior reviewed predictions agree exactly. Runtime500.588115seconds,0proofs/events, no qualification. This resolves the isolated-window acquisition-context blocker without changing geometry/recognition policy; foreground/source/UI qualification is still missing.18native-input tests/RuffPASS, production fingerprint unchanged since114-filemypyPASS. All82assertion records unchanged, canonicalCurrent/Deltaunmeasured. Next independently qualify continuity/UI and integrate lifecycle/package/trace; no fullE2E candidate exists.


## Qualified native join now reaches system events, package and trace contracts

[The explicit native lifecycle entrance](native_qualified_lifecycle_pipeline.md) joins analyzer-owned global observations, native scene witnesses and positively matched opt-in phase-absence/result references under matching paired qualification. Native source bindings and terminal hashes are checked; missing presence matches never become absence, and player-owned facts are excluded. Synthetic start/end/next-start yield two schema-valid packages with upcoming-round preparation and actor/time/provenance preserved through trace. Testing fixed leaked private candidate event fields.150relatedtests/Ruff/115-filemypyPASS. An actual four-frame source guard rejects missing qualification with0proofs/events; no positive R1 absence reference or paired real-image qualification was generated/adopted. All82assertionrecords unchanged, canonicalCurrent/Deltaunmeasured. Standard full orchestration/native streaming merge remains incomplete; next qualify real source/UI inputs before activation or another fullE2E. Historical code-bound reports were not resigned.


## Standard processor can receive qualified native boundaries without changing sampled facts

[Native event merge](native_event_merge.md) adds an explicit in-memory native result argument to the shared processor. Current qualification/code/profile and terminal video hashes are checked, source-bound lifecycle replay must reproduce events, conflicts are rejected and sampled observations/frame count remain unchanged. Native preparation provenance now prevents an extra leading partial package and assigns upcoming-round context without inventing sampled state.227relatedunit/integrationtests/Ruff/116-filemypyPASS. An actual saved-image negative receiver guard rejects an unqualified fixture with0events/packages; no real source/UI reference or qualification was adopted. All82assertionrecords unchanged, canonicalCurrent/Deltaunmeasured. Automatic native streaming/provider/EOF continuity and standard CLI activation remain incomplete; real qualification is still the principal blocker, so no fullE2E was run.


## R1 complete adjacent appearance sweep remains unqualified

[The fixed-region native sweep](r1_adjacent_region_analysis.md) evaluates all179adjacent pairs across180existing frames. At the first transient image, six candidate background regions have sceneNCC≥0.995074 while three mixed foreground regions change by69.43%/78.02%/100%. Scene contrast floor1 and masked-reference floor5 are reported separately: six versus two usable background regions at that link. This is neither a timer-only change nor independent source-cut/normal-animation qualification.5diagnostic tests/RuffPASS; production safety/thresholds/GT/all82assertions unchanged, canonicalCurrent/Deltaunmeasured. No fullE2E or qualification was produced; positive UI absence and source/foreground continuity remain blockers.


## Explicit native source origin and EOF are supported

[The endpoint contract](native_source_endpoint_contract.md) separates physical source edges from interior-window coverage. start0preserves a nonzero firstPTS; explicitendNoneverifies probe/decodeEOF; numericinterior endpoints remain guarded, and negative source origins are rejected rather than skipped.22decoder tests/64related tests/Ruff/116-filemypyPASS, with verification scope detailed in the document. An actual7-frame prefix preserves allarchivedpixels and firsttick553; actualEOF/fullE2Ewasnotrun. No qualification/defaultsampler/GT/assertionchange or canonicalgain. Automatic incremental processing and independently qualified R1source/UI remain unfinished; all82assertions unchanged.


## Whole native PNG buffering lacks a storage guarantee

[The fixed lossless codec assessment](native_full_source_storage_assessment.md) verifies48outputs across8exposed source frames and6serialencoder runs. Level9saves9.43%bytes but increases encodewall63.72%; cohort extrapolation to10259frames remains19.70GB versus17.26GBobservedfree. Extrapolation is not measured all-source storage. Reject compression changes and unbounded all-native PNG decoding; preserve oneepoch/state/terminal verification while designing bounded storage. No provider/qualification/defaultsampler/GT/assertionchange or canonicalgain; all82assertions unchanged. RuffPASS, no unnecessary fullE2E.


## Raw XOR/zlib native cache rejected after exact reconstruction

[The native pixel-cache experiment](native_pixel_archive_rejection.md) preserves180actual frames/pixels/PTS/epoch across two reading passes, but increases storage from377191642to475393177bytes(+26.03%). Construction86.34s/tworeadpasses125.25s do not establish a speed comparison. The production prototype was removed and retained only as diagnostics;54finaltests/Ruff/116-filemypyPASS. No adopted cache/qualification/defaultsampler/GT/assertionchange or canonicalgain; all82assertions unchanged. Next separately test existing PNG spatial prediction rather than repeat rawdelta variants, and retain singleepoch/state/terminal/budget requirements. R1source/UI qualification remains missing.


## Optional lossless PNG up prediction preserves native input

[PNG spatial prediction](native_png_prediction.md) supports explicitupencoding while retainingnonedefault. The fixed8-frame cohort reduces bytes18.34%/encodewall8.25%;96encoded outputs matchsource pixels. Two actual7-frame source-prefix decodes matchpixels/PTS/timebase exactly, with19.32%fewerbytes.91relatedtests/Ruff/116-filemypyPASS. Extrapolated17.76GBstilllacks capacity assurance, so total-byte enforcement/automaticprovider remain unfinished. No actualqualification/defaultsampler/GT/assertionchange or canonicalgain; all82assertions unchanged. R1source/UI qualification remains the primaryacceptanceblocker; no fullE2Ewasrun.


## Native PNG writes can enforce an explicit aggregate limit

[The native PNG budget](native_png_budget.md) streams oneencoder into bounded chunk writes and withholds all frames until exit/nativePTS/pixel/sourcehash verification. Overflow/timeout/truncation reject and clean up, withno frame skip or epoch concatenation. Actual7-frame prefix fits20MBwith14926335bytes and unchangedpixels/PTS;50byteattempt neverentersconsumer.101relatedtests/Ruff/116-filemypyPASS. DefaultbudgetNone/predictionnone preserve priorroute. Automaticqualifiedprovider and actualR1source/UI remain incomplete; no fullE2E or canonicalgain, all82assertions unchanged.


## Explicit processor collection of qualified native lifecycle

[Whole-source provider](native_lifecycle_provider.md) adds opt-in automatic source-origin-to-EOF collection with a mandatory PNG budget and unchanged default sampling. Paired current qualification/assets are checked before decode; one producer call must cover every actual decoded pixel/PTS in one epoch. Decoder terminal verification and lifecycle replay precede publication; errors do not fall back to sampled boundaries. Actual R1 source/UI qualification remains unavailable, so no full E2E or canonical gain is claimed. CLI activation and incremental streaming remain incomplete; all82assertion records are unchanged.


## Shared full runner exposes native provider explicitly

The [provider's shared runner interface](native_lifecycle_provider.md) now requires paired scene-profile/positive-byte-budget options for full-source input, propagates scene binding through production settings and uses configured FFmpeg. Dataset settings hash scene assets and budget at start/end; raw mode records source scope. Default commands and bounded modes retain previous semantics. Actual R1 source/UI qualification is still absent, no new full E2E or canonical assertion gain is claimed. Incremental buffering remains unfinished; this closes CLI reachability, not real-image qualification.


## User-assured unedited source removes the edit-exclusion blocker

The user explicitly guarantees no editing/reordering/intentional deletion or speed change for the SHA-bound current video. [Contracted UI-start analysis](unedited_input_lifecycle.md) therefore excludes scene-preserving edit without repeating image proofs. Default video assumptions stay unchanged. A contracted qualification-loader branch retains timer/phase/UI holdout and negative controls while removing mandatory edit/paired-scene components. Fresh current-reader analysis over256nativeframes finds one start candidate at4.102669s, corroborated at4.202669s; both2:25frames remain in the evidence.112relatedtests/Ruff/118-filemypyPASS; native diagnostic499.209010s,0releasedevents. Production provider/receiver activation and actual reader/UI qualification remain unfinished. All82canonical assertion records remain unchanged; no full E2E or PASSgain is claimed. Foreground edit-exclusion is no longer a blocker for this source; do not re-prove the user input guarantee.


## Assured native start reaches qualified event/package/trace and shared CLI

[The assured production connection](unedited_input_lifecycle.md) collects producer-owned phase scans and global observations under an explicit source-hash-bound no-edit contract and current timer/phase/UI qualification. It verifies before decode and after collection, then receiver replay rejects source/contract/scan/event/owned-field tampering. Native system actor/PTS/provenance and preparation context reach package/trace without replacing sampled facts. Shared full CLI now accepts contract+byte-budget instead of scene assets for this source; defaults remain unchanged.161relatedtestsPASS/1Windows-hostskip/Ruff/119-filemypyPASS. This is start-only, no real qualification adopted or new full/canonicalgain. The previous fresh256-frame candidate report remains historical; it was not resigned after source changes. Next actual holdout/negative UI+reader qualification, then continuous/sampled/canonical acceptance.

## R1 start candidate remains stable through six seconds

Fresh actual native analysis under the explicit no-edit contract extends the
development interval from4.3to6seconds: frames256→358(+102), candidates1→1(0),
released events0→0(0), wall499.209→723.760seconds(+224.551; different input
duration). Candidate4.102669s/confirmation4.202669s are unchanged; both2:25
observations remain in the recorded evidence. No duplicate candidate appears
through5.986003s. This supports temporal stability and does not qualify an
actual production event or establish canonical improvement. Current unit85PASS,
Ruff/mypy120filesPASS; all82assertion records remain unchanged. No full E2E was
run. Reader and joint temporal holdout qualification, plus actual R1 end inputs,
remain the upstream release gates. Intentional-edit exclusion is already given
by the source-specific contract. See [continuous evidence](unedited_input_lifecycle.md)
and `e2e_reports/match_001/r1_unedited_native_start_through6.json`.

## R1 end producer input shortage confirmed

Current analyzer diagnostics on ten source-bound native end frames confirm
timer4correct/6unknown/0wrong, no score pairs and no semantic result input. The
profile configures neither score reader nor result signal. Eight combat-report
flags also exposed an unnecessary player-context veto in the assured global end
wrapper: it now permits combat-report context only when independent qualified
result/score evidence satisfies every existing end predicate. Player facts,
source discontinuity, occlusion and conflicting-state guards remain unchanged.
139relatedtests/Ruff/120-filemypyPASS. No real end or qualification, package split,
full E2E or canonical gain is claimed. All82assertions remain unchanged. See
[evidence and remaining blockers](unedited_input_lifecycle.md) and
`e2e_reports/match_001/r1_end_actual_global_inputs.json`.

## Accepted score confidence was lost at both end consumers

Actual analyzer replay with the existing frozen score sidecar yields18correct/
2unknown/0wrong and8complete pairs on the ten end frames, vs0pairs under the
default profile. Both boundary consumers incorrectly read reversed confidence
key names and therefore rejected producer-accepted values. They now use exact
`score_ally_value`/`score_enemy_value`, with no generic/legacy fallback. An actual
analyzer-to-consumer regression test closes the fixture-only blind spot;
187relatedtests/Ruff/mypyPASS. This fixes an upstream contract defect, not the
remaining result recognition/qualification or temporal simultaneity problem.
No profile adoption, real end, full E2E, package gain or canonical PASS gain is
claimed; all82assertion records remain unchanged. See
[evidence](unedited_input_lifecycle.md) and
`e2e_reports/match_001/r1_end_existing_score_analyzer.json`.

## R1 end numeric temporal evidence, without event qualification

Fresh explicit native end input extends10→23frames and score pairs8→14; the
original overlapping observations are identical. Accepted0:06clocks span only
0.016667sec and subsequent clocks remain unknown. Updated0/2scores span nine
accepted frames/0.133333sec. A generic descriptive rule finds one conditional
clock-change/score-step pattern; three previously exposed archived analyzer
controls (27frames) find0. This does not establish active round state, end
semantics or independent qualification and emits0events.7diagnostic tests and
RuffPASS; production behavior and82assertions are unchanged. No full E2E or
canonical gain is claimed. See [actual sequence and limits](unedited_input_lifecycle.md)
and `e2e_reports/match_001/r1_end_numeric_temporal_pattern_validated.json`.

## Fresh menu-transition negative numeric evidence

The known83.419336buy-menu entry is checked on27fresh native frames with the
unchanged opt-in score/timer profile. All27score pairs remain0/2; the descriptive
end hypothesis finds0patterns. Post-prediction image review reports score54
correct/0wrong, timer26correct/1unknown/0wrong. A composited0:15display occurs at
83.302669between0:28frames and is rejected by the reader, not repaired or used
as accepted evidence. This exposed development control is not independent end
qualification or canonical negative-assertion validation.11diagnostic tests and
RuffPASS, including source epoch/timebase, repeated pixels and PTS guards.
No production/GT/threshold change or full E2E; all82assertions remain unchanged.
See [limits and source review](unedited_input_lifecycle.md) and
`e2e_reports/match_001/numeric_end_menu_entry_review.json`.

## Assured lifecycle source-break contract repair

Explicit source break markers were lost between analyzer measurements and native
assured replay. They are now preserved; timer anomalies alone do not create
markers. Native segment provenance now uses the integer type expected by the
package builder. Because break-time fragment transport remains incomplete, the
receiver rejects a source reset after the first emitted start before publishing
packages.100relatedtests, Ruff and mypyPASS. No new canonical run or changed
assertion status is claimed;23PASS/55FAIL/4NE remains the archived baseline.
Reader/joint temporal qualification and actual end evidence remain blockers.
See [source contract and limits](unedited_input_lifecycle.md).

## Source-break fragment builder contract

The optional builder source-break entrance now splits package/context and
derived state by source segment without generating round events.11new cases;
105relatedtests/Ruff/mypyPASS. Native automatic transport and HUD/Visual temporal
resets remain incomplete, so the receiver's fail-closed publication guard stays.
No actual-video qualification or new canonical gain is claimed. Archived82
assertions remain23PASS/55FAIL/4NE. Details:
[fragment contract and limits](unedited_input_lifecycle.md).

## Visual continuity consumer integration

The optional Visual source-break entrance resets pixel/map tracking, event and
trigger history and bounds semantic input to one source segment. Break markers
survive unreadable frames; stale pre-cut HUD state is excluded. Visual modules
now participate in native pipeline qualification fingerprints.14newcases and
72Visual regression tests/Ruff/mypyPASS. Automatic application/HUD/builder
transport remains pending and the receiver guard stays active. No new canonical
run or assertion relabeling; archived23PASS/55FAIL/4NE remains the reference.
See [consumer contract and blockers](unedited_input_lifecycle.md).

## Native source cuts connected to common processing

The assured-input common pipeline now sends replay-verified native cuts to HUD
Pass A/final state resets, Visual trigger/final state resets and package fragments.
Terminal checks compare both events and cuts against preflight. Unsupported
consumers and mismatched cut lists fail closed.7new cases;108relatedtests,
Ruff/mypyPASS. This completes automatic cut transport for the assured route,
without qualifying real reader/temporal evidence. No new canonical run;
82assertion statuses remain23PASS/55FAIL/4NE. Return next to actual qualification
and R1 end evidence. See [integration](unedited_input_lifecycle.md).

## Fresh frozen numeric input coverage

A fixed122.10–122.55second native window, outside the saved585-tick inventory,
is processed once with the frozen existing profile/current code. Post-prediction
image review: timer15correct/12unknown/0wrong; score10correct/44unknown/0wrong,
only2complete pairs among27frames. Source/profile/code/input hashes verify.
The actual active-context system replay produces0start candidates and0owned
facts. This same-video check does not prove exhaustive training separation,
natural field-absence safety or independent positive temporal qualification.
Runtime77.194884seconds; no comparable context or canonical delta. No source
code/threshold/GT change or new canonical run. See
[actual evidence and limits](unedited_input_lifecycle.md) and
`e2e_reports/match_001/frozen_numeric_reader_holdout_review.json`.

## Score unknowns localized to foreground segmentation

Frozen production score replay exactly reproduces all54fields on the saved27
active-context frames. Of44unknowns,40fail border-foreground validation,3fail
component count and1fails digit layout;0fail NCC/margin. Source/mask comparison
shows bright background merged into the enemy2mask. Removing border components
would remove connected digit pixels, so that shortcut is not justified. No
profile/ROI/threshold/code change, candidate adoption or canonical improvement.
The next score task is structurally separate text/background with new training
and independent holdout; this exposed cohort is excluded as untouched holdout
for that future change. R1 result/UI qualification blockers remain separate.
See [evidence and comparison](unedited_input_lifecycle.md) and
`e2e_reports/match_001/frozen_score_rejection_stages.json`.

## Local-opening score hypothesis rejected before holdout

A single frozen training-only foreground hypothesis uses9x9elliptical opening
and minimum local contrast12before the unchanged strict score reader. On60known
source frames, accepted fields fall114→53;61becomeunknown,0previousunknowns are
recovered. Reject before holdout/full E2E.5diagnostic unit controls, Ruff and
120-filemypyPASS; production/profile/threshold/GT remain unchanged. Stored
baseline agreement is not independent correctness proof: the older development
report's manual review flag is false. Next seek independent background support
that preserves digit strokes; do not sweep thresholds on the exposed27frames.
See [fixed hypothesis, result and limits](unedited_input_lifecycle.md).

## Border-supported background hypothesis rejected at training

The fixed four-column row-background hypothesis also regresses: on the same
60development frames/120fields, accepted114→86(-28), unknown6→34(+28),
unknown→accepted0 and accepted value changes0. It is rejected without a new
holdout or canonical run. Six diagnostic controls, Ruff and120-filemypyPASS.
Production/profile/threshold/GT are unchanged; all82assertion statuses retain
their archived baseline. All28accepted→unknown fields lose zero native pixels
above200, yet their enlarged foreground changes. Setting low-intensity native
background to zero changes cubic interpolation, so preserving native bright
stroke pixels alone is insufficient. Next investigate reference-compatible
segmentation in the existing enlarged comparison domain, rather than tuning
NCC or treating the exposed27active frames as fresh holdout. See
`e2e_reports/match_001/score_border_background_training_results.json` and
`score_border_background_mask_effect.json` in the same directory.


## Score foreground preserves interpolation: bounded progress

Moving background separation after unchanged cubic enlargement preserves all114
accepted training reads. On exposed27frame development, correct10→50, unknown
44→4, wrong0→0. A frozen new125.10–125.55native window yields correct46→47,
unknown8→7, wrong0→0, with all46previous correct preserved. Source pixels are
reviewed after predictions, no GT selection. This same-video/same-score-class
check is limited; no natural field-absence negatives or full qualification yet.
Default score mask extraction is behavior-preserving, verified120stored outputs
and96unit cases; Ruff/mypyPASS. Code fingerprint changes; old qualification is
not reusable. No production profile adoption or canonical run;82assertion states
remain their archived baseline. Next test frozen foreground on natural negatives;
R1 result/UI qualification remains separate. Details and comparison are in
[implementation evidence](unedited_input_lifecycle.md).


## Score foreground reaches opt-in production producer

54source-reviewed non-HUD background crops yield0false numeric for bothreaders.
They do not prove absence safety at the actual score field; existing64frame
review has0naturally absent fields. Explicit production
`white200_rowcontrast_v1` reproduces frozen diagnostic output on108fields, with
preprocessing provenance. ActualHUD analyzer on27native frames produces
47correct/7unknown/0wrong score fields, matching nominal replay54/54; unknown
identity retains0owned numeric facts. Opt-in profile changes onlyscore
preprocessing and is not adopted/qualified.82relatedtests, Ruff/mypyPASS.
No canonical run/status changes. Next evaluate boundary/control intervals using
this fixed profile and complete real qualification; result/UI gates remain.
See [producer evidence and limitations](unedited_input_lifecycle.md).


## R1 end replay: score gain, result configuration unavailable

Same10native frames with the frozen rowcontrast profile yield score19correct/
1unknown/0wrong versus18/2/0; pairs8→9, timer4→4. Result0→0is NOT a measured
NCCfailure: the two score pipeline sidecars omit`round_end_template`, required
by actualproducer result measurements. The separate historical early-banner
NCC≈0.388diagnostic is a different blocker. Diagnostic setup now distinguishes
missing/configured-unavailable/loaded reference.3unitcontrols, Ruff/mypyPASS;
no production change or canonical relabeling. Next configure the existing
late reference in an explicit diagnostic profile and measure actualproducer
result/score temporal alignment. Details are in
[updated evidence](unedited_input_lifecycle.md).


## Existing result reference now reaches producer; temporal input still missing

A diagnostic-only sidecar loads original frozen late-result assets and3verified
training crops without modifyingNCC/reference/defaultprofile. Actual producer
accepts3/3training,3/11reusedsame-episodeholdout,0/3negative and0/10earlynative
frames, equal to direct reference measurements. Early TEAM ACE staysNCC0.388.
Configuration transport is proven, while same-frame result/score-step input
conjunction remains0: score step74.486003, accepted result samples75.402669and
later. Archived gaps cannot validate delayed corroboration. No realqualification
or canonical status change. Next collect continuous native evidence through both
changes and assess a bounded temporal contract with independent controls.
See [producer and alignment evidence](unedited_input_lifecycle.md).


## Result/score time mismatch verified on108continuous native frames

Fixed74.20–76.00input yields47score pairs,17timer reads and29result matches.
Exact cadence/epoch with0adjacent repeated pixels or explicit break markers.
Score step74.486003, stable75.369336result after0.883333seconds; same-frame
conjunction0. First result run27frames hasminimumNCC0.924868.17accepted timer
fields reviewedcorrect/0wrong; no blanket score/result correctness claim.
200MBtemporaryPNGbudget failed before analyzer; explicit500MBretry succeeds
without skipping/changinginput. Wall297.784433sec, no comparable previousrun.
14relatedtests/Ruff/mypyPASS. No production predicate/defaultprofile/GT change,
qualification or canonical status update. Next specify a bounded pending-end
corroboration contract with negative/reset controls, then validate complete
active lifecycle context. See [continuous evidence](unedited_input_lifecycle.md).


## Pending-end training prototype; no production event gain yet

Frozen1second clock-origin hypothesis combines stable prior/new accepted score
with later stable qualified-format result evidence, preserving current unknowns.
Native R1training replay gives1conditional pattern; reused menu-entry/active
reports0each. Current-profile independent negatives, complete active lifecycle
and realqualification remain unproved. Batch source/context rejection, timeout,
contradiction and jitter controls are tested:26relatedcases/Ruff/mypyPASS.
No production behavior or82assertion status change; released events stay0.
Same-frame conjunction0vsconditional pattern1are different metrics, notPASSgain.
Next validate the fixed hypothesis on current-profile controls before streaming
production integration. See [contract and limits](unedited_input_lifecycle.md).


## Frozen pending-end hypothesis survives current-profile native controls

Current result/score profile on reused27menu-entry native frames yields0patterns/
0result false positives; all81timer-display/score values preserved. New fixed
130.00–131.20window processes72native frames,0patterns/0result false positives;
all72result ROI crops reviewedabsent after predictions. No current unknowns
or player ownership filled. Same-video/history-exposure limits prevent a full
independent qualification claim. Actual run times66.943425sec and156.645030sec;
no comparable runtime deltas. No production change/canonicalstatus update.
Next implement a streaming collector with explicit independent qualification
gate, then verify complete active lifecycle and tiered canonical behavior.
See [controls and gates](unedited_input_lifecycle.md).

## Separately qualified streaming end; assertion results unchanged

The bounded production collector now supports delayed result corroboration only
with a NEW `ui_end_transition` qualification and explicit source assurance.
Existing qualifications retain their same-frame predicate. Unit/native package/
trace tests cover source reset, jitter, duplicate suppression, partial-score
contradictions, timeouts, rearm, system actor, provenance and pre-round context:
191related tests PASS; RuffPASS; mypy121filesPASS.

Historical producer replay preserves1R1end pattern and0menu/active patterns;
released events0→0. Timestamp uses the first observed score change,
74.48600260416667sec, outside the fixed R1end window. This is no PASS improvement
and cannot be backdated to satisfy GT. Actual phase scans on358native R1 rows
preserve one start candidate at4.102669270833333sec without edit-only proof.
Qualification and complete active lifecycle remain unproved. Original82assertion
digest unchanged; canonical Previous23PASS/55FAIL/4NE, Current/Delta unavailable.
No unnecessary canonical run was started. Next qualify assured start/UI evidence
and independently resolve end timestamp semantics, then run the tiered gates.
See [implementation and source contract audit](unedited_input_lifecycle.md).

## Raw phase presence is separate from the debounced flag

Actual-analyzer holdouts preserve timer25correct/7unknown/0wrong and raw phase
8correct/0unknown/0negative false accepts. Four isolated positive images lack
temporal flags after source gaps; this is not a reader regression. The assured
producer now carries current raw phase presence/confidence separately, preventing
unconfirmed positive text from authorizing disappearance or a qualified end.
All21source markers agree with raw matches. Current30native R1development frames
preserve one start candidate at4.102669270833333sec.168relatedtests/Ruff/mypyPASS.
No real qualification, canonical result or82assertion status change. See
[contract, runtime comparison and qualification limits](current_frame_phase_contract.md).

## Early result text is not recovered by shared translation

All108existing native R1end images are tested with unchanged reference/masks/NCC
and one common translation per three-group match. Accepted frames29→29; early
NCC0.387553→0.387553; first result75.319336unchanged. Hypothesis rejected, no
production promotion. First32source ROI images show only1complete early word
with red display overlapping the glyph masks; this does not supply3distinct
supported early training frames.33relatedtests/RuffPASS; unchanged production
source retains prior mypyPASS. No canonical run or82assertion status update.
Next investigate independently accepted timer-reset/score-transition semantics,
without inventing a word or choosing time from GT. See
[source evidence and qualification limits](result_translation_feasibility.md).

## Numeric end correlation remains diagnostic

A separate frozen timer-reset/one-point-score-step/coherent-clock hypothesis finds
one correlation in the saved 108 native R1 end frames and zero in the exposed R1
start, R2 start, menu and active controls. Missing timer readings do not count as
support. Historical end measurements lack current raw phase presence, so this is
not current-producer or independent temporal qualification. No event timestamp
or round association is generated; clock reset and score transition times remain
distinct observed facts. 19 related tests and Ruff pass; production is unchanged.
Released events 0→0; canonical Current/Delta unavailable; all82 assertion statuses
remain unchanged. Next obtain current-producer raw phase measurements on the
existing source archive and independently resolve end timing semantics. See
[numeric feasibility and limitations](numeric_end_feasibility.md).

## Current end producer measurements and accepted score review

Current actual analyzer replays all108unchanged native end images; all108original
observations remain identical. Raw phase presence/confidence now exists on every
frame, with0positive matches. Timer17/score-pairs47/result29remain unchanged;
numeric and delayed-result conditional patterns remain1each. Source review finds
114correct accepted individual score fields,0wrong,102unknown; it is explicitly
post-prediction development review, not independent holdout. Producer229.458303sec
versus297.784433previous includes archive-versus-fresh-decode workload difference.
No production/event/assertion changes or canonical run. The former missing
raw-phase measurement blocker is resolved for this interval; independent end-time
semantics and temporal qualification remain. See the current-producer section of
[numeric feasibility](numeric_end_feasibility.md).

## Native timer snapshot transport and source-time binding

Qualified native clocks now have an exact-PTS processor/package/trace join,
preserving identity and player facts. 28relevant tests/Ruff/mypyPASS. However,
actual archived sampled timestamps have six-decimal ffprobe precision and the
108native end rows have exact rational tick-derived times: exact overlaps0,
formatted overlaps31. No nearest/rounded fallback is adopted, so actual full
benefit remains unproven. Next preserve decoder frame/tick identity through
sampled extraction and cache, then validate the actual source join without
changing sampler behavior. New production code invalidates historical code-bound
qualification; previous reports are not re-signed. All82assertion statuses remain
unchanged; canonical Current/Delta unavailable. See
[transport implementation and actual-source blocker](native_timer_snapshot_transport.md).

## Actual decoder ticks now resolve sampled/native precision differences

Common sampled extraction preserves ffprobe integer ticks and timebase, binds
them to video/JPEG hashes, and keeps existing decimal timestamps and selection.
Cache format2 preserves this optional identity with versioned keys. Processor
native timer joins require verified frame identity, abstain for legacy frames and
recheck image hashes before publication. Actual fixed31frame extraction yields
31native source joins versus0with timestamp equality, while all31sample times
remain unchanged; all31cache hits retain identity. Three matched native rows have
original accepted clock displays. This is actual source binding, not qualification
or canonical improvement.62relatedtests/Ruff/mypyPASS. Canonical Current/Delta
unavailable; all82assertion states remain unchanged. Next resolve independent
lifecycle/reader qualification and end timing, then evaluate source-backed timer
snapshots through the unchanged tiered gates. See
[decoder identity and actual-video verification](native_timer_snapshot_transport.md).

## Spectator primary state is preserved as a nullable snapshot field

The established source primary state now reaches native package snapshots and
trace as `spectator_primary_state`: qualified spectator=true, identity-valid
live=false, unknown/unsupported views=null. No flag-absence exclusion or owned
fact is inferred. Native/source disagreement fails closed.61relatedtests with
the real validation-pack path/Ruff/mypyPASS. Archived full raw/trace replay through
the unchanged canonical evaluator preserves23PASS/55FAIL/4NE, all82statuses,
919snapshots and20negative PASS. New field455false/163true/301null; no new detection
or full acceptance claim. `GT-R1-SNAP-7425` still has snapshot-admission and muzzle/
owned-field blockers. Original assertion matrix/digest is unchanged. See
[native/trace contract and archived replay](spectator_primary_snapshot_contract.md).

## Fixed result reference fails newly reserved late source frames

Current unchanged profile on12native frames at76.35–76.55sec yields0result accepts.
Known native/training/reviewed/full-decoded exposures exclude8frames;4were fixed
before predictions for review. Source text is visiblyTEAMACE in all4but their
NCC0.814–0.856falls below0.90: correct0/unknown4/wrong0. No reference, threshold,
production or qualification changes. This exposes a real result-reference
generalization blocker beyond missing qualification paperwork. The cohort is now
exposed development data; investigate representation/background dependence from
original training only and reserve different validation before adoption. No
canonical run or82assertion status change. See
[protocol, source evidence and rejected qualification](result_late_fixed_cohort_failure.md).

## Training-derived result representation rejected on fixed new source frames

Grayscale stable trimming loses required contrast; fixed Canny fails training.
A frozen persistent min-channel white/contrast mask passes training by
construction but improves no acceptances on12new native source frames. Eight
were reserved before prediction with known exposure exclusion: correct2/unknown6/
wrong0for both representations; three existing negatives remain rejected. All12
show readable TEAM ACE. No threshold, production or qualification changes;
all82assertion states remain unchanged. Stop tuning this representation and
return to source-assured start qualification/upstream contracts. See
[training hypotheses, new source comparison and rejection](result_persistent_feature_rejection.md).

## Combined production contract regression verified; Visual fixture repaired

The complete repository pytest run yields2459PASS/1FAIL/9SKIP. The sole failure
is an integration mock missing the new source-break keyword; it is repaired
with an explicit empty-break assertion. Related Visual and supplied-pack
integration modules then yield13PASS/0FAIL/0SKIP. Ruff onsrc/tests/scripts/e2e
and mypy121source filesPASS. The full suite was not repeated after the test-only
repair; overlapping runs are not summed. No production/qualification/canonical
status change. See
[execution scope, fixture fix and remaining qualification gates](production_contract_regression_check.md).

## Shared team scores now have a native/source/trace contract

Accepted score values and their reserved value-reader confidence now survive
as nullable native fields with source-checked trace aliases independently of
player identity.113relatedtests/Ruff/mypyPASS. Archived canonical replay preserves
all82results23PASS/55FAIL/4NE. In the108row R1end development window,53ally/61enemy
scores have accepted reader confidence and67identity-unknown rows have global
score evidence, but existing admission still yields0snapshots. No PASS increase
or new qualification is claimed. Next define a separately qualified global
snapshot admission contract; retain existing player admission and ownership.
See [implementation, actual source coverage and remaining admission blocker](shared_score_snapshot_transport.md).

## Fixed new shared-score source check: correct accepts, incomplete qualification

The unchanged production profile processes18native frames with16reserved before
prediction. Reviewed source showsally0/enemy2: reserved ally16correct/0unknown/
0wrong, enemy4correct/12unknown/0wrong. All14enemy unknowns across18frames reject
foreground touching the ROI border before glyph matching; nominal reader
acceptance parity is18/18with the actual analyzer. No neighbor filling, cutoff
change, qualification or admission promotion. Training provenance and genuine
negative controls remain gates. No canonical assertion status change. See
[fixed selection, source review and rejection-stage evidence](shared_score_fixed_source_validation.md).

## Shared score training provenance and current background controls

All ten current score glyph assets have exact frozen training ancestry and meet
the prior three-physical-frame/80% support rule under unchanged Gaussian/NCC0.90.
Current ally/enemy core readers each reject all54 fixed background crops from
three physical frames, false accepts0; previous/current changes0. This is neither
natural nominal score absence nor independent new holdout or temporal lifecycle
qualification. No production/admission/profile change or canonical rerun; all82
statuses remain unchanged. See
[scope, provenance, controls and admission blocker](shared_score_training_background_audit.md).

## Assured start qualification support clarified

The current loader permits shared physical frames across components within one
split; it rejects cross-component training/holdout/control leakage. Its minimum
is three physical hashes per split, not three round episodes or videos. Four
focused regression testsPASS; no production or canonical result change. Source
assurance removes edit-only checks, while independently reviewed joint temporal
UI qualification remains required. The previously exposed R1/R2 development
sequences are not fresh holdout. See
[qualification support and exact start acceptance targets](unedited_input_lifecycle.md).
