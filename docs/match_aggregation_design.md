# Match単位の集計基盤 設計（Task A）

対象モジュール: `src/valorant_ai_coach/application/match_aggregation.py`
補助: `src/valorant_ai_coach/rules/temporal_contract.py`（Task B、読み取り専用のPolicy表と文脈の不足判定）

- 起点main: `e9ecaf8f2f0f0dfa1f9433d40a598ec8909e9ce3`
- 実画像・実動画・実API・Validation Pack・Vision側コードは使用していない。
- 合成Fixtureは実ゲーム映像の証拠ではない（§7）。

## 1. 目的と、やらないこと

複数Roundの評価結果を**収集・分類・件数化**し、元のRound / Fact / Eventへの参照を失わずに、
決定論的でJSON化できるMatch単位のビューを作る。

**Match全体の評価は作らない。** 設定の6ルール（AIM-01〜04, MOV-01, MOV-02）は
`uses_whole_match_aggregation = true` だが、AIM-01以外はmicroレベルの評価をMatch全体で
集約するものであり、「3Roundでimproveが出たからMatch全体もimprove」という単純な回数規則では
決められない人間的基準を含む。そのため次は**実装していない**（事前承認が必要なもの）。

| 作らないもの | 担保 |
|---|---|
| Match全体のGOOD / IMPROVE判定 | 出力に該当キーが存在しない（`test_no_match_level_verdict_score_or_weight_exists_anywhere_in_the_output`） |
| 総合スコア・評価重み | 同上 |
| 集約confidence（平均・最大・最小など） | 各評価のconfidenceは**供給されたまま**コピー（`test_confidence_is_copied_exactly_and_never_aggregated`） |
| LLMによるMatch総評 / 新規API呼び出し | モジュールはI/Oを持たない純粋関数 |
| 保存形式の非互換変更 | 既存のRoundAnalysis・出力schemaは無変更。新しいJSONは追加の`match_aggregation.v1` |

## 2. 公開API

```python
from valorant_ai_coach.application.match_aggregation import MatchAggregator, RoundInput

result = MatchAggregator().aggregate(
    rounds,                       # Iterable[RoundInput | RoundAnalysis]
    match_id=None,                # 任意。指定時は各Roundと一致が必須
    expected_round_numbers=None,  # 任意。指定時のみ「完全」を検証できる
)
result.to_dict()                  # JSON安全・決定論的（キー順・要素順が固定）
```

- `RoundInput(round_package, output=None, analysis_scopes, candidates, candidate_rule_ids, evaluation_failure)`
  - `RoundInput.from_round_analysis(analysis)` で既存の`RoundAnalysis`をそのまま受け取れる。
  - 保存済みの結果は `round_package` と `output`（AI Coach出力）の組として渡せる。
- `MatchAggregator(rule_config=None, validator=None)`: 既定は同梱の`valorant_evaluation_rules_v4.json`。
- 入力は変更されない（`test_inputs_are_never_modified_and_result_is_deterministic_json`）。

## 3. 結果の構造（`schema_version = "match_aggregation.v1"`）

| キー | 内容 |
|---|---|
| `match_id` | 検証済みのMatch ID。Roundが0件で宣言も無ければ`null` |
| `counting_basis` | 固定値 `evaluation_records_as_supplied`。**供給された評価レコードの件数**であり、ゲーム内の別個の出来事の数ではない |
| `completeness` | 完全性の判定（§5）。`status` / 供給・採用・未評価・除外・時間軸不完全のRound / 欠番 / 期待Roundの欠落 / `blocking_reasons` |
| `rounds[]` | Roundごとの`status`（`included` / `not_evaluated` / `excluded_invalid`）、`round_window`、`timeline`、`timeline_completeness`、評価件数、label別件数、`failure` |
| `rules[]` | Rule IDごとの集計（§4） |
| `evaluations[]` | 供給された評価1件ごとの参照（元Round・label・confidence・根拠の種別・Fact/Eventの出所）。`(round_no, evidence開始時刻, evaluation_id)`順 |
| `issues[]` | 欠損・不整合・注意の一覧。`code` / `round_no` / `rule_id` / `evaluation_id` / `detail` |

### 3.1 `evaluations[]`（provenanceの保持）

各要素は元Roundへの参照（`round_no`）、`primary_rule_id` / `related_rule_ids`、`label`、
`decision_source`、`confidence`（null可）、`unscored_reason_code`、`evidence_range`、`display_clip`、
`evidence_count`、そして**根拠の種別** `provenance_basis` を持つ。

| `provenance_basis` | 意味 |
|---|---|
| `facts` | 引用した全Factが所有Roundのpackageで解決でき、かつそのFactが引くEventもpackageに全て存在する |
| `evidence_only` | Fact参照は無いが、画像等のevidenceを持つ（既存契約で正当。誤って拒否しない） |
| `none` | Factもevidenceも無い。**根拠ありとして扱わない** |
| `unresolved` | Fact参照のいずれかが所有Roundのpackageに無い、または引用Eventがpackageに無い（`fact_ref_unresolved`等で報告） |

`facts[]`には、Factごとに`resolved` / `key` / `confidence` / `source` / `provenance_event_ids`、
そしてpackageに存在しないEventを`missing_event_ids`として保持する。Factの検索は**その評価を所有するRoundの
package内のみ**で行うため、隣のRoundのFactを所有したことにはならない。

### 3.2 `rules[]`（Rule identityの保持）

- `counts`: そのルールが**primary**の評価の件数（good / improve / unscored）。
- `related_counts`: 表示用の`EvaluationAggregator`が別ルールへ統合した結果、**related**として現れた件数。
  `counts`には加算しない。**同じ評価を二重計上せず、かつ統合されたルールの存在も失わない**。
- `primary_evaluation_ids` / `related_evaluation_ids` / `rounds_as_primary` / `rounds_as_related`: 元への参照。
- `unscored_reason_counts`、`evidence_basis_counts`: 原因別・根拠別の内訳。labelは混ぜない。
- 設定由来の項目（そのまま転記、換算なし）: `level` / `uses_whole_match_aggregation` /
  `aggregate_repeated_occurrences` / `summary_required_if_occurrences_at_least` / `display_limit`。
- `needs_match_context`と`match_context_unverified`: Match全体の文脈が要るルールは、
  完全性が`verified_complete`になるまで`match_context_unverified = true`（§5, §6）。
- `context_by_round`: Task Bの`assess_context()`の結果（Round単体で評価可能か、過去Roundが要るか、
  欠けている文脈、時間範囲が特定できているか）。**新しい評価判断は含まない**。

## 4. 既存`EvaluationAggregator`との関係（再利用の判断）

`rules/aggregator.py`の`EvaluationAggregator`は**表示用**（重複排除・同一場面の統合・ルール別表示上限）であり、
保存結果をすでに「間引き」ている場合がある。そこで次の方針とした。

- **件数の計算には再利用しない。** 表示用の統合結果を再度統合すると二重の間引きになるため。
- **出力は読み込める。** 統合済みの評価（`related_rule_ids`を持つ）を`related_counts`で受ける。
- `max_display_exemplars_per_match`に達したルールには`display_limit_reached`を立て、
  「件数は下限値の可能性がある」ことを`issues[]`で明示する（保存結果から超過分は消えているため）。
- 統合された評価のconfidenceは、D-1の修正（承認済み）により**統合した各評価のconfidenceの最小値**になっている。
  Match集計はこの値を**供給されたまま**コピーするだけで、再計算・平均・引き上げはしない。
  詳細は`docs/non_vision_safety_regression_report.md` §5。

## 5. 不完全Roundの扱いと完全性

| 状態 | 扱い |
|---|---|
| 完全なRound | `included` |
| 未評価のRound（評価出力なし / `evaluation_failure`あり） | `not_evaluated`。**どのlabelにも数えない**。`round_not_evaluated`（完全性を妨げる） |
| 契約違反のRound（package/出力がschemaやconfidence上限等に違反） | `excluded_invalid`。そのRoundだけ全件数から除外し`round_contract_violation`で報告。**半分だけ信用することはしない** |
| 時間軸が不完全（`partial` / `unavailable` / `unknown`） | `timeline`にそのまま記録し、`round_timeline_*`を報告。評価自体は消さない |
| 開始・終了が不明なRound | 補完しない。隣接Roundから境界を推測しない |
| Round番号の欠番 | `round_number_gap`として報告するだけで、埋めない |
| Round窓の重なり・逆転 | `round_windows_overlap` / `round_window_order_conflict`として報告するだけで、修復しない |

**可用性と完全性は別物。** Roundが何件か揃っていても、それだけでは「Match全体が揃った」とは言えない。

| `completeness.status` | 条件 |
|---|---|
| `verified_complete` | 呼び出し側が`expected_round_numbers`を渡し、かつ完全性を妨げるissueが無い |
| `incomplete` | 完全性を妨げるissue（`COMPLETENESS_BLOCKING`）が1件でもある |
| `unverifiable` | 妨げるissueは無いが、期待Round番号が与えられていない。**「完全」とは言わない** |

空のMatchは`no_rounds`が立ち`incomplete`（`test_empty_match_is_explicitly_empty_not_complete`）。

## 6. 整合性の検証

| 検査 | 結果 |
|---|---|
| Round packageの`match_id` / `round_no`が不正・欠落 | `MatchAggregationError`（例外） |
| 評価出力の`match_id` / `round_no`がpackageと不一致 | `MatchAggregationError` |
| 異なる`match_id`の混入（宣言値との不一致を含む） | `MatchAggregationError`。部分結果は返さない |
| 同じ`round_no`が**同一内容**で重複 | 2件目以降を無視し`duplicate_round_input_ignored`（二重計上しない） |
| 同じ`round_no`が**異なる内容** | `MatchAggregationError` |
| 別Roundで同じ`evaluation_id`が再利用された | `MatchAggregationError` |
| 同一Round内の`evaluation_id`重複 | そのRoundを`excluded_invalid`として全件数から除外し`duplicate_evaluation_id`を報告（どちらが正しいか推測しない。二重計上もしない） |
| 未知のRule ID | 集計はするが`known_rule = false`で`unknown_rule_id`を報告（設定由来の項目は`null`） |

「Match / Roundの身元が食い違う」＝Match単位のビュー自体が無意味、として**例外**。
「Round内容が契約違反」＝そのRoundのみを**隔離**。この区別を維持している。

## 7. 合成Fixture（依頼§A-5との対応）

Fixtureは`tests/unit/match_fixtures.py`が、既存の合成`tests/cases`（`match_id`が`MOCK-`始まり）から
生成する。期待値は既存の`expected_assertions.json`の契約と既存schema検証から導いており、
新しい主観的な正解は作っていない。**実ゲーム映像の証拠としては扱わない。**

| 依頼のFixture | テスト（`tests/unit/test_match_aggregation.py`） |
|---|---|
| 正常な3Round | `test_three_round_match_is_collected_in_round_order_with_expected_labels` |
| 同一Match内の複数Rule評価 | `test_one_evaluation_is_counted_once_and_merged_rules_keep_their_identity` / `test_good_improve_and_unscored_are_never_mixed` |
| 異なるMatch IDの混入 | `test_rounds_from_different_matches_are_refused_not_merged` / `test_declared_match_id_must_agree_with_the_rounds` |
| 同一Round IDの重複 | `test_same_round_supplied_twice_with_same_content_is_counted_once` / `test_same_round_id_with_different_content_is_refused` |
| Round順序の入れ替わり | `test_all_input_orderings_give_the_identical_result` |
| 不完全Roundを含むMatch | `test_partially_observed_round_is_flagged_but_its_evaluations_stay_visible` / `test_round_without_an_evaluation_is_not_evaluated_and_never_scored` ほか |
| 全RoundがUNSCORED | `test_all_rounds_unscored_never_synthesises_good_or_improve` |
| 一部Roundだけ評価成功 | `test_one_successful_round_among_failures_keeps_only_that_rounds_counts` |
| Fact参照が欠落 | `test_unresolved_fact_ref_is_reported_and_never_shown_as_evidence_backed` |
| イベント参照が存在しない | `test_event_cited_by_a_fact_but_absent_from_the_package_is_reported` / `test_default_validator_keeps_a_round_with_a_ghost_event_reference_out_of_the_counts` |
| 同じ評価の重複 | `test_duplicate_evaluation_id_inside_a_round_never_double_counts` |
| 空のMatch | `test_empty_match_is_explicitly_empty_not_complete` / `test_empty_match_with_expectations_lists_every_expected_round_as_missing` |

## 8. Task Bとの接続

`rules/temporal_contract.py`の`assess_context()`が、ルール×Roundごとに次を**報告だけ**する（判断はしない）。

- Match全体の文脈が必要か（`needs_match_context`）
- Round単体で評価可能か
- 過去Roundの情報（`previous_round_context`）が必要か、欠けているか
- Round時間軸が完全か（`complete` / `partial` / `unavailable` / `unknown`）
- 時間範囲を特定できているか（pinned policy / whole round / fallback）

`requires_round_timeline`は**採点のゲートにしていない**（既存の実行時挙動を変えない。§9-1）。
時間軸が不足していても評価は消さず、`context_by_round`と`round_timeline_*`で不足を明示する。

## 9. 未決定事項（ユーザー判断が必要）

実装は保留しており、いずれも既存コードへの影響は無い（新規の追加機能に閉じている）。

### 9-1. Match全体の評価（GOOD / IMPROVE・総合スコア）
- **現状**: 作っていない。回数・割合・Round別labelの一覧までを提供。
- **選択肢**: (a) 作らない。人間（またはコーチUI）が件数と根拠から読む (b) ルールごとに明示的な基準を定義して判定 (c) LLMに総評を作らせる
- **推奨**: (a)を維持し、(b)は6ルールのうち基準を文章で確定できたものから個別に承認する。
- **理由**: 「回数で決められない人間的基準」を含み、勝手な閾値は評価基準の意味変更になるため。
- **影響**: (b)(c)は新しいlabel/confidenceの意味を作るため、事前承認が必要。(a)は影響なし。

### 9-2. 完全性の既定値
- **現状**: `expected_round_numbers`が無ければ`unverifiable`。
- **選択肢**: (a)現状 (b)連番`1..最大`を期待値とみなして`verified_complete`にする
- **推奨**: (a)。
- **理由**: (b)は「最終Roundまで揃っている」ことを推測で補うことになり、Round lifecycleの実映像の境界問題（未解決）と衝突する。

### 9-3. `max_display_exemplars_per_match`による間引き後の件数
- **現状**: 保存済みの結果は上限超過分が消えており、件数は下限値。`display_limit_reached`で警告のみ。
- **選択肢**: (a)警告のみ (b)表示用の間引きを保存前の全件と分離して保存する
- **推奨**: (b)を将来検討（ただし保存形式の変更になるため承認が必要）。
- **関連**: `docs/non_vision_safety_regression_report.md`のL-5。**今回も変更していない（未解決）。**

### 9-4. `aggregate_repeated_occurrences` / `summary_required_if_occurrences_at_least`
- **現状**: 設定値を`rules[]`へ**そのまま転記**するだけ。要約は生成しない。
- **選択肢**: 要約の出力形式と生成主体（コード / LLM）の定義
- **推奨**: 形式の定義を先に決める。LLM要約は事前承認が必要。

### 9-5. snapshot由来factのconfidence / provenance（L-1 / L-2 / L-3）
- **現状**: 3件とも**変更していない（未解決）**。現状を再現するテストで固定済みで、いずれも水増しはせず安全側に倒れている。
  zone factのpackage aggregate上限（L-1）、snapshot間引きで後続の高confidence観測が消える（L-2）、HP/Armorのprovenanceの不統一（L-3）。
- **選択肢・推奨・理由・影響**: `docs/non_vision_safety_regression_report.md` §5を参照。
- **Match集計との関係**: Match集計はFactのconfidenceを再計算せず、`evaluations[].facts[]`に供給されたまま保持する。
  上記の承認・修正が入った場合は、Factのconfidenceが変わるだけで、Match集計側のコードは変更不要。

### 9-6. Match全体の総合評価
- §9-1のとおり。**今回も作っていない（未解決）。**

## 10. 互換性

- 既存の`RoundAnalyzer` / AI Coach / 保存形式 / schemaは**変更していない**（追加モジュールのみ）。
- 変更した既存コード: `rules/temporal_scope.py`は`previous_round_context_missing()`を共有関数として切り出しただけで、
  既存の判定結果は同じ（空のplaceholderをresolverと下流で同一に扱うため）。
- `rules/__init__.py`に新規モジュールのexportを追加（既存exportは維持）。
- `rules/engine.py`のconfidence判定の厳格化と、`rules/aggregator.py`の統合confidence（D-1、承認済み）は別件
  （`docs/non_vision_safety_regression_report.md`§2・§5）。Match集計モジュール自体は`aggregator.py`を呼ばない。

## 11. テスト結果

| 項目 | 結果 |
|---|---|
| `tests/unit/test_match_aggregation.py` | 55件（収集時） |
| `tests/unit/test_temporal_policy_contract.py`（Task B） | 77件（収集時） |
| 全体 | 結果は`docs/non_vision_safety_regression_report.md`§6を参照 |
