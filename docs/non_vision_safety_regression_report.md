# Confidence・Provenance・Aggregation 安全性回帰レポート（Task C）

- 起点main: `e9ecaf8f2f0f0dfa1f9433d40a598ec8909e9ce3`
- 追加テスト: `tests/unit/test_non_vision_safety_regressions.py`（収集257件）
- 実画像・実動画・実API・Validation Pack・Vision側コードは使用していない。Fixtureはすべて合成で、実ゲーム映像の証拠ではない。
- 評価基準の意味・44ルール・deterministic labelは変更していない。

## 1. 結論

| 項目 | 状態 |
|---|---|
| 既存の安全条件（confidence上限・scope修復・UNSCORED重複集約・spectator安全性）の維持 | 維持。既存テストはすべて通過 |
| 新規コード（Task Aのmatch集計）にも同じ安全条件を適用 | 適用済み（§3 の4章） |
| production codeの変更 | **1箇所**（§2）。fail-closed方向への厳格化のみ |
| 再現した既知の欠陥 | **D-1**（§5）。**承認を受けて修正済み**（PR #11追加修正）。strict xfail 2件は通常のPASSテストへ変更 |
| 未解決として残す事項 | L-1 / L-2 / L-3 / L-5、およびMatch全体の総合評価。**今回は変更しない**（§5, §8、`match_aggregation_design.md` §9） |
| 既知のsnapshot/fact課題4件（依頼§C-3） | 現状を再現するテストで固定。変更は未実施（§5, L-1〜L-4） |
| negative control | 12件中11件を検出。1件（N7）は等価変異体と確認（§4）。D-1用の4件（N9〜N12）はすべて検出 |

## 2. production codeの変更（1箇所）

`src/valorant_ai_coach/rules/engine.py` — `DeterministicRuleEngine._confidence()`

| | 変更前 | 変更後 |
|---|---|---|
| 実装 | `float(fact["confidence"])`（例外時と非有限値のみ`-inf`） | 既存の`_number()`（bool除外・実数のみ・有限のみ）を再利用、それ以外は`-inf` |
| `True` | `1.0`として0.90のgateを**通過** | `-inf`（高信頼として扱わない） |
| 数値文字列 `"0.95"` | `0.95`として扱われgateに到達し得る | `-inf` |
| `None` / 欠落 / `NaN` / `±Infinity` / list / dict | `-inf` | `-inf`（変わらず） |
| `0.0`と`null` | 区別される | 区別される（`0.0`は実数、`null`は未定義） |
| 有効な数値（`0.9` / `1` など） | gate判定 | 同じ |

- **性質**: 未定義・不正なconfidenceを高信頼として扱わない方向（fail-closed）にだけ厳格化。confidenceの**計算方式や意味は変えていない**。
- **影響**: Round Packageのschema（`deterministic_fact.confidence`は0〜1のnumber必須）を通る実データには影響しない。
  影響し得るのは、schemaを通さずにメモリ上で組み立てたFactのみで、その場合は`unscored`（`low_confidence`）になる。
- **根拠**: `_number()`が既にFact値の判定で同じ規則（bool除外）を使っており、同じ規則に揃えただけ。
- **承認について**: 依頼の「confidenceの意味が変わる実装は承認を得てから」には該当しないと判断した（意味は同一でgateを緩める変更でもない）。
  ただし判断はユーザーに委ねられる。戻す場合は`engine.py`の該当箇所を元の`float()`方式に戻し、対応テスト
  （`test_an_undefined_or_malformed_fact_confidence_never_reaches_the_deterministic_gate`のうち`True`・数値文字列）も合わせて調整する（N8で、戻すとこのテストが落ちることを確認済み）。

## 3. カバレッジ（依頼§C-2の各項目 → テスト）

テスト名は `tests/unit/test_non_vision_safety_regressions.py` のもの。`[M]`は `test_match_aggregation.py`、`[S]`は既存の`test_schema_validation.py`/`test_downstream_contract.py`。

### 3.1 Confidence

| 重点項目 | テスト |
|---|---|
| source confidenceを超えない（最弱の引用Factが上限、引用順に依存しない） | `test_the_cap_is_the_weakest_cited_fact_regardless_of_citation_order` / `test_confidence_exactly_at_the_cap_passes_and_a_visible_excess_does_not` / [S]`test_fact_backed_evaluation_confidence_cannot_exceed_weakest_referenced_fact` / [S]`test_fact_confidence_above_its_cited_event_is_rejected` / [M]`test_confidence_above_the_cited_facts_quarantines_the_round` |
| 未定義confidenceを高信頼として扱わない | `test_an_undefined_or_malformed_fact_confidence_never_reaches_the_deterministic_gate`（11値）/ `test_a_fact_without_any_confidence_never_reaches_the_deterministic_gate` / `test_the_deterministic_gate_edges_use_real_numbers_only` |
| NaN / Infinityを拒否 | `test_non_finite_numbers_are_rejected_wherever_they_appear_in_an_evaluation`（confidence・evidence_range・display_clip・evidence.time_sec × 3値）/ `test_non_finite_fact_confidence_cannot_enter_through_the_round_package` |
| 0.0とnullの区別 | `test_zero_confidence_is_a_real_value_but_null_or_missing_is_not` / `test_zero_and_null_confidence_stay_distinguishable_in_the_match_view` / [M]`test_numeric_helpers_never_turn_null_or_non_finite_values_into_numbers` |
| 集約時にconfidenceを引き上げない（統合後は最弱メンバー以下・引用Factの最弱値以下） | `test_aggregation_never_invents_labels_ids_rules_or_confidence`（60 seed）/ `test_merged_evaluation_keeps_the_confidence_cap_of_every_fact_it_cites`（実validatorを通す。D-1の回帰テスト）/ `test_merged_confidence_is_the_weakest_member_in_every_time_and_input_order` / `test_a_three_member_group_takes_the_weakest_of_all_three` / `test_same_rule_merge_keeps_the_strongest_member_as_representative_and_the_weakest_confidence` / [M]`test_confidence_is_copied_exactly_and_never_aggregated`（Match集計は供給値をそのままコピー） |
| Factなしの画像根拠評価を誤って拒否しない | `test_an_evaluation_with_image_evidence_and_no_fact_refs_is_not_rejected` |
| 不正なFact参照を拒否 | `test_fact_references_must_match_exactly_not_loosely`（`f008`/空白付き/桁違い/空文字）/ `test_duplicate_fact_references_are_rejected_not_double_counted` |

### 3.2 Provenance

| 重点項目 | テスト |
|---|---|
| 存在しないEvent IDを参照しない | [M]`test_event_cited_by_a_fact_but_absent_from_the_package_is_reported` / [M]`test_default_validator_keeps_a_round_with_a_ghost_event_reference_out_of_the_counts` |
| 異なるRoundのEventを所有しない | `test_a_fact_citing_an_event_of_another_round_is_rejected` |
| 異なるMatch/RoundのFactを混在させない | `test_a_fact_id_that_only_exists_in_another_round_is_rejected` / `test_facts_of_different_matches_cannot_be_mixed_in_one_match_view` / `test_an_evaluation_citing_a_fact_that_only_the_neighbouring_round_has_is_quarantined` |
| 集約後も元Rule IDを失わない | `test_rule_identity_survives_merging_in_the_display_aggregator` / `test_match_view_identity_survives_even_when_the_display_aggregator_merged_rules` / `test_every_input_rule_stays_visible_while_no_display_limit_is_hit` |
| 元Roundへの参照を保持 | [M]`test_each_evaluation_ref_keeps_round_fact_and_event_provenance` |
| 根拠なしを根拠ありとして表示しない | [M]`test_evaluation_without_facts_is_evidence_only_or_none_never_fact_backed` / [M]`test_unresolved_fact_ref_is_reported_and_never_shown_as_evidence_backed` |

### 3.3 Aggregation

| 重点項目 | テスト |
|---|---|
| 異なる根拠のUNSCOREDを統合しない | `test_unscored_items_merge_only_when_reason_and_fact_basis_are_identical`（原因違い・根拠違い・上位集合・別group・group外 など7パターン）/ `test_unscored_without_fact_refs_is_never_merged_even_with_the_same_reason` |
| 同一根拠の重複集約が安定 | `test_fact_ref_order_does_not_change_whether_unscored_items_are_the_same_basis` / `test_aggregation_is_idempotent`（60 seed） |
| GOODとIMPROVEを混合しない | `test_good_and_improve_in_the_same_scene_are_both_kept` / [M]`test_good_improve_and_unscored_are_never_mixed` |
| UNSCOREDからGOOD/IMPROVEを合成しない | `test_unscored_never_absorbs_or_becomes_a_scored_evaluation_on_the_same_basis` / プロパティテスト内の検査 / [M]`test_all_rounds_unscored_never_synthesises_good_or_improve` |
| 件数が入力順序で変わらない | `test_aggregation_counts_do_not_depend_on_input_order`（60 seed × 全順列）/ `test_match_view_counts_equal_the_supplied_evaluations_and_never_cross_labels`（8 seed） |
| 重複除去でRule identityを失わない | 3.2の`..._rule_identity_...` |

「UNCSORED」は誤記であり、すべて`UNSCORED`で検査している。

## 4. Negative Controls（依頼§C-4）

本番コードを1箇所ずつ壊し、関連テスト（安全性6ファイル）が失敗するかを確認した。実行後は必ず元に戻している（`git diff`で確認）。

| # | 壊した条件 | 結果 | 落ちたテスト数 |
|---|---|---|---|
| N1 | AI評価のconfidence上限チェックを無効化 | **検出** | 5 |
| N2 | 未知`fact_id`参照の検査を無効化 | **検出** | 9 |
| N3 | FactのEvent上限チェックを無効化 | **検出** | 2 |
| N4 | Match ID混在の検査を無効化 | **検出** | 4 |
| N5 | UNSCORED統合で原因コードの一致条件を外す | **検出** | 1 |
| N6 | UNSCORED統合で空の根拠同士の統合を許す | **検出** | 1 |
| N7 | `_same_unscored_basis`のlabelガードを外す | **未検出（等価変異体）** | 0 |
| N8 | `engine._confidence`を`float()`方式に戻す | **検出** | 3 |
| N9 | D-1: 同一ruleの統合で強い方のconfidenceを残す（上限を失う） | **検出** | 32 |
| N10 | D-1: dedup groupの統合で`min`を`max`にする | **検出** | 13 |
| N11 | D-1: 代表の選択に、下げたconfidenceを使う（初稿の退行） | **検出** | 12 |
| N12 | D-1: 統合後にfact_refsの和集合を保持しない（根拠の欠落） | **検出** | 44 |

合計12件中11件を検出。N1の件数は、D-1の回帰テスト追加で4→5になった。

**N7の判断**: `EvaluationAggregator.aggregate()`は呼び出し側で既に`item.get("label") == label`で同一labelの項目だけを比較対象にしており、
`_same_unscored_basis`内のlabelガードは**到達不能な防御的重複**。テストの穴ではなく、挙動が変わらない変異（等価変異体）と判断した。
ガード自体は多重防御として残している（削除は今回の範囲外）。

## 5. 既知の欠陥・制約（再現と改善方針）

「再現」はテストで固定済み。**D-1以外は、confidenceの意味やschema・保存形式に関わるため、承認前は変更していない。**
`test_known_limitation_*` / `test_known_consequence_*`は現状を固定する特性化テスト（承認後に変更する際、意図的に反転させる）。

### D-1. 統合されたevaluationのconfidenceが、統合で増えたfact_refsの最弱値を超え得る【欠陥・**修正済み（承認済み）**】

- **経緯**: 初回提出時はstrict xfail 2件で再現のみ行い、修正はconfidenceの意味が変わるため承認待ちとしていた。
  ユーザーの承認（PR #11追加修正依頼）を受けて修正した。
- **旧挙動**: `EvaluationAggregator`は統合時に`fact_refs`を**和集合**にするが、confidenceは強い方のまま。
  例: F008(0.98)を引く0.98のgoodと、F007(0.90)を引く0.90のgoodを統合すると、`fact_refs=[F008,F007]`でconfidence 0.98 → 最弱Fact(0.90)を超える。
  `application/pipeline.py`は集約後に`validate_ai_output`を再度呼ぶ（L323）ため、上限違反は`ContractValidationError`となりMatchの解析が止まり得た
  （水増しされた値が保存・表示されることは無いfail-closed。コード読解 + 検証器での再現で、パイプラインのE2E実行はしていない）。
- **修正**（`rules/aggregator.py`）: 統合した各evaluationの**confidenceの最小値**を、統合後のevaluationのconfidenceにする。
  同一ruleの重複排除（時間窓）とdedup group（同一場面）の両方に適用。
  - 各evaluationは自分のFactの最弱値以下なので、`min`は和集合の最弱値以下になる（上限条件を必ず満たす）。
  - **代表の選び方は変えていない。** どのevaluationが代表（evaluation_id・clip・evidence窓）になるかは従来どおり「元のconfidenceが最も強いもの」。
    confidenceの最小値と、代表選択に使う最大値は別々に保持する（初稿の実装は、下げた値を次メンバーとの比較に使い、3件以上の統合で
    代表が中間メンバーに入れ替わる退行を起こした。新規テストで再現し、修正した）。
- **変更前後の影響確認**（コミット済みの旧aggregatorと比較）:
  | 比較 | 結果 |
  |---|---|
  | 既存38ケース（実際のmock pipeline経由、評価36件） | 出力に**差なし** |
  | ランダム3000通りの評価集合 | confidenceが下がったのは297通り、**上がったのは0通り**。confidence以外（evaluation_id・label・fact_refs・primary/related rule・evidence・clip）の差は**0通り** |
  | `validate_dataset.py` | 38 cases OK |
- **保たれる性質**: confidenceの不正昇格なし / `fact_refs`は和集合のまま保持 / Rule identity（primary + related）保持 / label（GOOD・IMPROVE・UNSCORED）は変わらず、UNSCOREDは統合しても`unscored_reason_code`を保つ。
- **テスト**: strict xfail 2件を通常のPASSテストに変更（`test_merged_evaluation_keeps_the_confidence_cap_of_every_fact_it_cites`。実validatorを通す。
  入力は列挙順・逆順の両方）。加えて、時間順×入力順（`test_merged_confidence_is_the_weakest_member_in_every_time_and_input_order`）、
  3メンバー全順列、代表の安定性（24通り）、等しいconfidence、UNSCORED統合、修正前の統合結果が実際に上限理由で拒否されること
  （`test_the_unfixed_merge_really_fails_the_validator_for_the_cap_reason`）を追加。`test_rule_engine`の期待値は0.9→0.8
  （0.8 / 0.9 / 0.8を統合した結果は最弱メンバーの0.8）に更新。
- **留意すべき副作用（`test_known_consequence_a_weak_member_can_demote_a_merged_good_to_unscored`）**:
  パイプラインには既存の下限`_enforce_confidence_policy`（confidence < 0.55 のgood/improveを`unscored`/`low_confidence`に降格）がある。
  旧挙動では、0.50のgoodと0.90のgoodを統合すると強い方の0.90が残り、goodのままだった。
  修正後は統合結果が0.50となり、既存の下限によって`unscored`に降格される（`fact_refs`は保持）。新しいlabelロジックは無く、
  既存の下限が「正直になったconfidence」に作用した結果である。0.55以上のメンバー同士の統合ではlabelは変わらない。
  この副作用をどう扱うか（例: 弱いメンバーを統合せず別件として残す）は、今回は変更していない。**将来の判断事項**として残す。

### L-1. zone factのconfidenceにpackage aggregateが上限として使われる【特性化】

- **再現**: `test_known_limitation_zone_fact_is_capped_by_the_package_aggregate_never_raised`
- **現状**: zone factは`min(zone_confidence, package.visual_confidence)`。snapshotには解像器自身の`zone_confidence`（例0.90）が記録されるが、
  factは視覚の集約値が低いと下がる（visual観測が無ければ0.0 → zone factが0.0）。**引き上げる方向には動かない**（安全側）。
- **選択肢**: (a)現状維持 (b)snapshotの`source_confidence.player_location`をfactのconfidenceとして使う（フィールド別provenance）
- **推奨**: (b)。`docs/external_ai_snapshot_source_confidence.md`が導入したフィールド別`state_snapshot.source_confidence`（zoneは解像器の`zone_confidence`）の設計の延長であり、同docも本件を既存の限界として記録している。
- **影響**: zone factのconfidenceが上がり得る（0.90 gateを超え得る）＝**意味が変わるため承認が必要**。上限は解像器自身の値を超えない。

### L-2. 同一状態のsnapshot間引きで、後続の高confidence観測が失われる【特性化】

- **再現**: `test_known_limitation_thinning_keeps_the_first_reading_of_an_unchanged_state`
- **現状**: 状態が変わらない間は最初の観測のsnapshotを残す。先が0.70・後が0.99だと0.70が残り、0.99の観測では上げられない（逆順なら0.99が残る）。
  confidenceは元の観測のものを保持し、**水増しはしない**。
- **選択肢**: (a)現状維持 (b)同一状態では高い方のsource confidenceを残す (c)最大値を記録しつつ代表時刻は維持
- **推奨**: (b)または(c)。ただし根拠となる観測時刻との対応を失わない(c)を優先。
- **影響**: factのconfidenceが上がり得る＝**承認が必要**。

### L-3. HP / Armorのconfidence provenanceが統一されていない【特性化】

- **再現**: `test_known_limitation_hp_fact_uses_its_own_value_score_and_snapshot_hp_has_no_source`
- **現状**: HP factは`roi_confidence.hp_value`（0.90以上のときのみ）を使い、観測の`hud_confidence`より高くなり得る。
  snapshotの`hp`/`armor`には`source_confidence`のエントリが無く、armorにはfact自体が無い。
- **選択肢**: (a)現状維持 (b)`hp`/`armor`にもsnapshotの`source_confidence`を持たせ、factの出所を統一
- **推奨**: (b)（L-1と同じschema側の方針）。
- **影響**: schema変更を伴う**ユーザー承認が必要**な変更（既存の保存形式との互換性に注意）。

### L-4. `source_confidence`の無い古いPackageは保守的に扱われる【期待どおり・固定】

- **再現**: `test_legacy_package_without_source_confidence_is_conservative_not_high`
- **現状**: `source_confidence`が無い旧snapshot由来のfactは**0.0**になる。高信頼として扱われることは無い。
- **推奨**: 現状維持。旧Packageを再評価したい場合のみ、再生成で`source_confidence`を付与する。
- **影響**: なし（変更しない）。

### L-5. 表示上限が「ruleごと」で「labelごと」ではない【特性化】

- **再現**: `test_known_limitation_display_limit_counts_per_rule_so_early_good_can_hide_improve`
- **現状**: `max_display_exemplars_per_match`（例: 3）はrule単位。AIM-02で早い時刻のgoodが3件で上限に達すると、後のimproveが保存結果から消える。
  labelの混同や捏造は無いが、保存結果はimproveを過小に表すことがある。
- **選択肢**: (a)現状維持 (b)label別に上限を数える (c)表示用の間引きと保存を分離する
- **推奨**: (c)（`docs/match_aggregation_design.md` §9-3）。
- **影響**: 保存形式・表示結果が変わる**承認が必要**な変更。Match集計側は`display_limit_reached`で下限値の可能性を警告している。

### L-6. 時刻とconfidenceが完全に同点のとき、残るevaluation_idが入力順に依存する【特性化】

- **再現**: `test_known_limitation_an_exact_time_and_confidence_tie_keeps_the_first_supplied_id`
- **現状**: 件数は入力順に依存しないが、完全な同点（同時刻・同confidence）でのみ、残る`evaluation_id`は先に渡した方。
- **推奨**: 現状維持（実害は表示上のIDのみ）。決定論性が必要になった場合のみtie-breakを追加する。
- **影響**: 軽微。

## 6. テスト結果

実行環境: Linux, Python 3.12（プロジェクト指定）。`QT_QPA_PLATFORM=offscreen`。

| コマンド | 結果 |
|---|---|
| `python tests/validate_dataset.py` | `OK: 38 cases; schemas + candidate selection contract valid`（既存38 fixtureの契約を維持） |
| `python -m ruff check src tests scripts/e2e` | All checks passed |
| `python -m mypy src/valorant_ai_coach` | Success: no issues found in 127 source files |
| `python -m pytest --cov=valorant_ai_coach --cov-fail-under=75`（`tests/unit/test_ui_smoke.py`を除く） | **2905 passed / 9 skipped / 0 xfailed / 0 failed**、coverage **82.91%**（ゲート75%を達成） |

- 上記は**最新main（`27c8465`）を取り込んだ統合状態**での結果（pytestはmainの新規テストを含む全体）。
- 初回提出時（`e9ecaf8`起点）は2243 passed / 2 xfailed だった。xfail 2件はD-1の修正で通常のPASSになり、0件になった。
- 収集数: 最新main 2496件 → 本ブランチ 2928件（**+432件**: match集計55 / temporal契約77 / 安全性300）。
  2928件 = 実行2905 + skip 9 + 除外した`test_ui_smoke.py` 14件。
- **9 skipped**はすべて既存の環境依存で、今回の変更とは無関係:
  外部Validation Pack未配置（4）、実録画が未供給（1）、Windows固有パス（1）、PowerShell Core無し（3）。
- **`tests/unit/test_ui_smoke.py`を除外した理由**: この開発サンドボックスではQtがセグメンテーションフォールトで落ちる。
  **変更を入れていないmain（`e9ecaf8`）でも同じ箇所で落ちる**ことを確認しており、今回の変更が原因ではない。
  このファイルの検証は**未実施**であり、GitHub ActionsのLinux / Windowsの結果を正とする（PR本文に記載）。
- カバレッジゲート（`--cov-fail-under=75`）はローカルでは実行していない。CIの結果を正とする。

## 7. 互換性

- 既存のRoundAnalyzer / AI Coach / 保存形式 / schemaは変更していない。
- 既存の38 fixtureの契約を維持（`validate_dataset.py`で確認）。
- production code変更は§2の1箇所（fail-closed方向のみ）と、Task A/Bで追加した新規モジュール、
  `rules/temporal_scope.py`の判定関数の共有化（結果は同一）。
- Vision側（`hud/` `visual/` `maps/` `application/hud_video_processor.py`）は変更していない。
- 新しいAPI通信・実機・実映像は使っていない。

## 8. 未解決事項（承認が必要で、今回は変更しない）

D-1は承認を受けて修正済み（§5）。次の項目は**今回の更新でも変更していない**未解決事項で、いずれも承認が必要。

| ID | 内容 | 推奨 | 影響 |
|---|---|---|---|
| L-1 | zone factのconfidenceをフィールド別source confidenceへ | 承認して修正 | confidenceが上がり得る |
| L-2 | 同一状態の間引きで高confidence観測を残す | 承認して修正（(c)優先） | confidenceが上がり得る |
| L-3 | HP/Armorのprovenance統一（schema変更を伴う） | 承認して修正 | schema・保存形式 |
| L-5 | 表示上限の数え方・保存と表示の分離 | 将来検討 | 保存形式・表示結果 |
| M-1 | Match全体の総合評価（GOOD/IMPROVE・総合スコア） | 作らない（`match_aggregation_design.md` §9-1） | 新しいlabel/confidenceの意味 |
| D-1付随 | 統合で弱いメンバーのconfidenceが0.55未満になると、既存の下限で`unscored`に降格される（§5） | 現状維持。扱いは将来判断 | goodの表示件数が減り得る |

## 9. CI上の既知の不安定性（Linux Qt終了処理）

- **事象**: PR #11の初回Linux Basic CI（pull_request）が、pytestステップでexit code 134（SIGABRT）で失敗した。
  同一コミットのpush側は成功し、再実行（attempt 2）でも成功した。
- **原因**（ユーザー確認）: 全テストが成功した後の**Qt終了処理で発生したプロセスabort**。assertion失敗ではない。
  PR #9で対処された「Linux Qt teardown」問題と同系統の、既存の不安定性として扱う。
- **本PRとの関係**: 本PRはGUI・Qt関連のコードを変更していない（`ui/`・`application/hud_video_processor.py`を含まない）。
  今回の追加修正（`rules/aggregator.py`）は純粋Pythonのルール層で、Qtと接点がない。新たな回帰かどうかは、
  最新main統合状態でのLinux CIの結果（§6）で確認する。
- **未解決**: abortの根本原因（Qt終了処理の順序）は本PRの範囲外であり、修正していない。CI失敗時は、ログのテスト結果（passed件数）と
  exit codeを併せて確認し、assertion失敗かprocess abortかを区別すること。
