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
| 再現した既知の欠陥 | **D-1**（§5）。strict xfailでピン留め。修正はconfidenceの意味が変わるため**承認待ち** |
| 既知のsnapshot/fact課題4件（依頼§C-3） | 現状を再現するテストで固定。変更は未実施（§5, L-1〜L-4） |
| negative control | 8件中7件を検出。1件は等価変異体と確認（§4） |

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
| 集約時にconfidenceを引き上げない | `test_aggregation_never_invents_labels_ids_rules_or_confidence`（60 seed）/ `test_merging_never_lowers_the_cap_below_what_the_representative_already_had` / [M]`test_confidence_is_copied_exactly_and_never_aggregated` ／ **例外: D-1（§5）** |
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
| N1 | AI評価のconfidence上限チェックを無効化 | **検出** | 4 |
| N2 | 未知`fact_id`参照の検査を無効化 | **検出** | 9 |
| N3 | FactのEvent上限チェックを無効化 | **検出** | 2 |
| N4 | Match ID混在の検査を無効化 | **検出** | 4 |
| N5 | UNSCORED統合で原因コードの一致条件を外す | **検出** | 1 |
| N6 | UNSCORED統合で空の根拠同士の統合を許す | **検出** | 1 |
| N7 | `_same_unscored_basis`のlabelガードを外す | **未検出（等価変異体）** | 0 |
| N8 | `engine._confidence`を`float()`方式に戻す | **検出** | 3 |

**N7の判断**: `EvaluationAggregator.aggregate()`は呼び出し側で既に`item.get("label") == label`で同一labelの項目だけを比較対象にしており、
`_same_unscored_basis`内のlabelガードは**到達不能な防御的重複**。テストの穴ではなく、挙動が変わらない変異（等価変異体）と判断した。
ガード自体は多重防御として残している（削除は今回の範囲外）。

## 5. 既知の欠陥・制約（再現と改善方針）

「再現」はテストで固定済み。**いずれもconfidenceの意味に関わるため、承認前は変更していない。**
`test_known_limitation_*`は現状を固定する特性化テスト（承認後に変更する際、意図的に反転させる）、
`xfail(strict=True)`は欠陥の再現（修正されると失敗し、xfailの除去を促す）。

### D-1. 統合されたevaluationのconfidenceが、統合で増えたfact_refsの最弱値を超え得る【欠陥】

- **再現**: `test_merged_evaluation_keeps_the_confidence_cap_of_every_fact_it_cites[same_rule|dedup_group]`（strict xfail）
- **現状**: `EvaluationAggregator._merge_same_label()`は`fact_refs`を**和集合**にするが、confidenceは代表（primary）の値のまま。
  例: F008(0.98)を引く0.98のgoodと、F007(0.90)を引く0.90のgoodを統合すると、`fact_refs=[F008,F007]`でconfidence 0.98 → 最弱Fact(0.90)を超える。
- **実際の影響**（コード読解 + 検証器での再現。パイプライン全体のE2E実行はしていない）:
  `application/pipeline.py`は集約後に`validate_ai_output`を再度呼ぶ（L323）。上限違反は`ContractValidationError`となり、
  Matchの解析が失敗する。つまり**水増しされた値が保存・表示されることは無い（fail-closed）が、解析全体が止まり得る**。
  `_enforce_confidence_policy`は0.55未満の降格のみで上限は掛けない。
- **選択肢**:
  1. 統合時のconfidenceを`min(統合した各evaluationのconfidence)`にする
  2. 統合してもfact_refsを和集合にせず、代表のfact_refsだけを保持する
  3. 現状維持（失敗を許容）
- **推奨**: 1。
- **理由**: 各evaluationは自分のFactの最弱値以下なので、`min(各confidence)`は和集合の最弱値以下になる（上限条件を必ず満たす）。
  fact_refs（根拠の保持）を失わず、confidenceを上げることもない。
- **影響**: 統合された評価のconfidenceが（下がる方向に）変わる。表示上のconfidenceが変わるため**承認が必要**。
  既存38 fixtureの期待値への影響は**未確認**。承認後に修正する際、`validate_dataset.py`と既存テストで確認する。

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
| `python -m mypy src/valorant_ai_coach` | Success: no issues found in 106 source files |
| `python -m pytest`（`tests/unit/test_ui_smoke.py`を除く） | **2243 passed / 9 skipped / 2 xfailed / 0 failed** |

- main（`e9ecaf8`）の収集数1879 → 本ブランチ2268（+389: match集計55 / temporal契約77 / 安全性257）。
- **2 xfailed** = D-1（`same_rule` / `dedup_group`）。strictなので、修正されると失敗して除去を促す。
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

## 8. 承認が必要な事項のまとめ

| ID | 内容 | 推奨 | 影響 |
|---|---|---|---|
| D-1 | 統合evaluationのconfidenceを`min(各confidence)`にする | 承認して修正 | 統合結果のconfidenceが下がる方向に変わる |
| L-1 | zone factのconfidenceをフィールド別source confidenceへ | 承認して修正 | confidenceが上がり得る |
| L-2 | 同一状態の間引きで高confidence観測を残す | 承認して修正（(c)優先） | confidenceが上がり得る |
| L-3 | HP/Armorのprovenance統一（schema変更を伴う） | 承認して修正 | schema・保存形式 |
| L-5 | 表示上限の数え方・保存と表示の分離 | 将来検討 | 保存形式・表示結果 |
