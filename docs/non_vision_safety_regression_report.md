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
| production codeの変更 | **2箇所**: §2（ルールエンジン、fail-closed方向のみ）と、D-1b（`application/pipeline.py`の集約呼び出し。§5 D-1b）。D-1のaggregator修正を含む |
| 再現した既知の欠陥 | **D-1**（§5）。**承認を受けて修正済み**（PR #11追加修正）。strict xfail 2件は通常のPASSテストへ変更 |
| D-1b（0.55下限を統合の前に適用） | **承認を受けて実装済み（案B）**（§5 D-1b）。強いGOOD/IMPROVEが弱い同ruleの評価に巻き込まれて失われない |
| 未解決として残す事項 | L-1 / L-2 / L-3 / L-5、およびMatch全体の総合評価。**今回は変更しない**（§5, §8、`match_aggregation_design.md` §9）。L-5はD-1bと相互作用する（§5 D-1b） |
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
- **留意すべき副作用（D-1b実装前の挙動。現在は解消）**:
  パイプラインには既存の下限`_enforce_confidence_policy`（confidence < 0.55 のgood/improveを`unscored`/`low_confidence`に降格）がある。
  旧挙動では、0.50のgoodと0.90のgoodを統合すると強い方の0.90が残り、goodのままだった。
  修正後は統合結果が0.50となり、既存の下限によって`unscored`に降格される（`fact_refs`は保持）。新しいlabelロジックは無く、
  既存の下限が「正直になったconfidence」に作用した結果である。0.55以上のメンバー同士の統合ではlabelは変わらない。
  この副作用は、**D-1b（直後。承認を受けて案Bを実装済み）で解消した**。aggregator単体の挙動（最小値）は変えていない。

### D-1b. 0.55下限を「統合の後」から「統合の前」に移す【**承認を受けて案Bを実装済み**】

**背景**: D-1の修正（案A）後、0.50のGOODと0.90のGOODを統合すると、統合結果（0.50）が既存の下限`_enforce_confidence_policy`
（confidence < 0.55 のgood/improveを`unscored`/`low_confidence`へ降格）に掛かり、**0.90のGOODまで一緒にUNSCOREDとして失われる**。

| | 動作 |
|---|---|
| OLD（D-1以前） | 統合→下限。強い方の0.90が残るためgoodのまま。ただし`fact_refs`に弱いFactが混じり、confidenceが引用Factの最弱値を超える（D-1の欠陥） |
| **A（現在の実装）** | 統合（最小値）→下限。弱いメンバーに引きずられ、統合全体が`unscored`（0.50、`fact_refs`は両方を保持、clip・improvementは失われる） |
| **B（検討案）** | **各evaluationに下限を先に適用**→統合（最小値）。弱いものは単独の`unscored`、強いものはgoodのまま残る |

**例**（AIM-02、GOOD 0.50（F1）と GOOD 0.90（F2）、3秒差）:
- OLD: `b` good 0.90 `[F2, F1]`（上限違反）
- A: `b` **unscored** 0.50 `[F2, F1]`（reason `low_confidence`）
- B: `a` unscored 0.50 `[F1]` ＋ `b` **good** 0.90 `[F2]`

**測定方法**: 合成の乱数評価集合4000通り（各2〜7件、scored側のconfidenceは0.40 / 0.50 / 0.54 / 0.55 / 0.70 / 0.90 / 0.98、
Factは各評価が置いた最強confidenceを上限とする）に、コミット済みの旧aggregator・現在のaggregator・パイプラインの実`_enforce_confidence_policy`を適用。
さらに既存38ケースを実際のmock pipeline経由で比較し、案Bを使い捨てworktree（PR対象外）に仮適用して既存テストを実行した。
**実映像・実APIは使っていない。乱数集合は挙動の差の目安であり、実データでの発生頻度を示すものではない。**

| 観点 | OLD | A（現在） | B（案） |
|---|---|---|---|
| **GOOD/IMPROVEの保持**（4000通り、下限適用後の合計） | 6568件 | 6393件（OLD比 **−175、増加0**） | 6583件（OLDにあったscored評価のうち消えたのが14件、OLDに無くBで現れたのが29件） |
| 1集合あたりのGOOD+IMPROVE件数（対A） | — | — | **Aより増えたのが187集合、減ったのは0集合** |
| **UNSCOREDの扱い**（下限適用後の全UNSCORED） | 10575 | 10750 | 10341（弱い評価は単独UNSCOREDとして残る。同一理由・同一根拠のものは既存規則で統合） |
| 統合されたUNSCORED（related ruleを持つ） | 77 | 101 | 159 |
| **Fact参照・confidence上限**: 引用Factの最弱値を超えて出力された件数 | **207** | **0** | **0** |
| 0.55未満の弱いメンバーのFactが、強いgoodの`fact_refs`に混ざるか | 混ざる | 混ざる | **混ざらない**（弱い方は単独UNSCOREDになり、強いgoodは自分のFactだけを引く。0.55以上同士の統合は従来どおり和集合） |
| **重複集約結果**: 出力件数 | 17143 | 17143 | 16924（−219） |
| 生き残る`evaluation_id`がOLDと同一の集合 | — | 4000/4000 | Aと同一は3436/4000 |
| OLDで見えていたruleが見えなくなった集合 | — | 0 | 1 |
| OLDより引用Factが減った集合 | — | 0 | 7 |
| **既存38 fixture**（mock pipeline経由） | — | 出力に差なし | 出力に差なし |
| **既存テスト**（pipeline・floor・rule engine・match集計・安全性、計451件を案Bで実行） | — | 全件成功 | **全件成功**（案Bを仮適用しても落ちるテストは無い） |

**Bで「減る」14集合と、Fact参照が減る7集合の原因**: 新しい誤りではなく、既存のL-5（表示上限が**rule単位でlabelを区別しない**。例: DEC-02・ECO-02は2件）との相互作用である。
Bでは降格したUNSCOREDが単独で残り、同じruleの表示枠を消費する。例: DEC-02にimprove 0.7、improve 0.5、good 0.9があるとき、
0.5が単独UNSCOREDになって3件に増え、枠（2件）から時刻の遅いimprove 0.7が押し出される。**Aに対しては常に悪化しない**（減った集合は0）が、
OLDに対しては14集合で減る。L-5を先に直すか、同時に扱えば解消する見込み（未検証）。
同様に、OLDにもdedup groupの統合で強い方のGOODが隠れる問題があり（primaryが規則順の先頭のconfidenceを持つため）、Bはこれも解消する（例: GOOD 0.54のDEC-02にGOOD 0.98のINFO-03が吸収されるケース）。

**保存形式・既存テストへの影響**:
- 保存形式（`ai_coach_output_schema_v3`）は**変更なし**。降格後の項目は、既存の下限が今も作る形（`label=unscored`、`unscored_reason_code=low_confidence`、clip・improvement無し、`missing_information`あり）と同一。
- 変更箇所は`application/pipeline.py`の集約呼び出しの直前1箇所（各evaluationへ既存の下限を先に適用）のみ。aggregatorの中身は変えない。
- 既存テストは落ちないが、**A/Bの差を固定するテストが既存には存在しない**。案Bを採るなら、パイプライン経由で「0.50のGOODと0.90のGOODを統合してもGOODが残る」ことなどを固定する新規テストが必要。
  
- 既存の「評価0件ではなくunscoredを明示する」方針とは矛盾しない（Bは弱い評価を消さずUNSCOREDとして残す）。

**推奨（実装前の判断。承認済み）**: 案B。**理由**: GOOD/IMPROVEの保持がAより常に悪くならず（増加187・減少0）、強いgoodが弱いメンバーのFactや低いconfidenceに引きずられない。
上限違反は案Aと同じく0件。**留意点**: L-5との相互作用で、OLDに対して14/4000集合ではGOOD/IMPROVEが減る。
この比較の後、ユーザーが案Bを承認し、実装した（上記）。

#### D-1b 実装内容（承認済み・案B）

- **変更箇所**: `application/pipeline.py`のみ。集約呼び出しを`_aggregate_round_evaluations()`に切り出し、
  `EvaluationAggregator.aggregate()`へ渡す前に**各evaluationへ既存の`_enforce_confidence_policy`（0.55下限）を適用**する。
  統合後にも同じ下限を再度適用する（冪等。aggregatorが0.55未満のscored項目を返さない限り何も変えない安全網）。
  **aggregator・下限の判定式・0.55の値・schema・保存形式は変更していない**。
- **満たした要件**:

  | 要件 | 結果 |
  |---|---|
  | 高信頼のGOOD/IMPROVEが低信頼の別評価に巻き込まれて失われない | 弱い方だけが単独`unscored`になり、強い方は自分のFactだけを引いたままGOOD/IMPROVEで残る |
  | 弱い評価のUNSCORED降格を保持 | 0.55未満は従来どおり`unscored`/`low_confidence`（clip・improvement除去、`fact_refs`・`primary_rule_id`保持） |
  | confidence上限違反が発生しない | 4000通りの乱数集合で、引用Factの最弱値を超えた出力は**0件**（OLDは207件）。実validatorを通すテストも追加 |
  | `fact_refs`・Rule identity・provenance保持 | 降格項目も統合項目も保持（テストで固定） |
  | 既存Schemaとの互換性 | 保存形式`ai_coach_output_schema_v3`は変更なし |
  | 既存38 fixtureの結果 | 出力に**差なし**（OLD・案Aとも同一） |
  | D-1の回帰テスト | すべて維持（aggregator単体のテストは無変更で成功） |
  | 0.55前後・複数件統合時の順序のテスト | 追加（下記） |

- **実装後の検証**: 実装した本物の`_aggregate_round_evaluations()`を、乱数4000集合（Round 1/2混在）に適用し、前回比較した案Bの結果と照合 →
  **不一致0 / 4000**。この数値（GOOD+IMPROVEの保持: Aより増えた187集合・減った0集合、上限違反0、38 fixture差なし）は上の比較表のとおり。
- **追加テスト**（`tests/unit/test_non_vision_safety_regressions.py`、実validatorを含む）:
  - 弱い同ruleの近傍にいるgood/improveが失われない（2）
  - 0.55境界: 0.0 / 0.549999 / 0.55−1e-12 は単独UNSCORED、0.55 / 0.55+1e-12 / 0.56 は従来のD-1統合（6）
  - 3メンバー（0.50 / 0.70 / 0.90）の全6入力順で結果が同一（代表は最強、統合confidenceは下限を通った側の最弱0.70）（6）
  - 0.30 / 0.40 / 0.95の全6入力順で、弱い2件は個別に降格し強い1件に混ざらない（6）
  - 同一根拠・同一理由のUNSCOREDは既存規則どおり統合される（1）、Round間は混ざらない（1）、dedup groupでのidentity/上限（1）
  - パイプライン出力を実validatorに通す（2経路 × 弱い側0.40 / 0.55 / 0.70）（6）
  - 下限の冪等性・入力非破壊（1）、aggregator単体のD-1挙動は無変更（1）
  - 特性化: L-5との相互作用（下記）（1）
  - 旧`test_known_consequence_a_weak_member_can_demote_a_merged_good_to_unscored`は、案Aの副作用を固定するテストだったため、上記に置き換えた。
- **負の確認（negative control）**: `**self._enforce_confidence_policy(evaluation)`を元の`**deepcopy(evaluation)`に戻すと、新規テストのうち**19件が失敗**する（戻して全件成功を確認）。
- **L-5との相互作用（L-5は別タスクのまま未変更）**: 表示上限`max_display_exemplars_per_match`はrule単位でlabelを区別しないため、
  降格したUNSCOREDが単独で残ると、その分の表示枠を消費する。例: AIM-02（上限3）で、弱い0.50・強い0.90×3 → 以前は弱い項目が強い項目に統合されて枠を1つしか使わなかったが、
  今は弱い項目がUNSCOREDとして1枠を使い、時刻の最も遅い強いGOODが表示から外れる
  （`test_known_limitation_a_demoted_weak_item_still_uses_up_the_per_rule_display_budget`で固定）。
  乱数4000集合ではOLDに対して14集合でGOOD/IMPROVEが減り、7集合でOLDより引用Factが減り、1集合でOLDで見えていたruleが見えなくなった
  （いずれもAに対しては悪化なし）。**原因はL-5の数え方であり、D-1bの欠陥ではない**。L-5（表示用の件数制限と保存の分離）は承認の指示どおり別タスクとして残す。

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
| `python -m pytest --cov=valorant_ai_coach --cov-fail-under=75`（`tests/unit/test_ui_smoke.py`を除く） | **2943 passed / 9 skipped / 0 xfailed / 0 failed**、coverage **82.92%**（ゲート75%を達成。`Required test coverage of 75.0% reached`） |

- 上記は**最新main（`27c8465`）・D-1b・Windows修正（PR #13）を取り込んだ統合状態**での結果（pytestはmainの新規テストを含む全体）。
- 初回提出時（`e9ecaf8`起点）は2243 passed / 2 xfailed だった。xfail 2件はD-1の修正で通常のPASSになり、0件になった。
- 収集数: 最新main 2496件 → 本ブランチ 2966件（Task A/B/C・D-1・D-1bの追加分: match集計55 / temporal契約77 / 安全性331、ほかPR #13のテスト追加分）。
  2966件 = 実行2943 + skip 9 + 除外した`test_ui_smoke.py` 14件。
- **9 skipped**はすべて既存の環境依存で、今回の変更とは無関係:
  外部Validation Pack未配置（4）、実録画が未供給（1）、Windows固有パス（1）、PowerShell Core無し（3）。
- **`tests/unit/test_ui_smoke.py`を除外した理由**: この開発サンドボックスではQtがセグメンテーションフォールトで落ちる。
  **変更を入れていないmain（`e9ecaf8`）でも同じ箇所で落ちる**ことを確認しており、今回の変更が原因ではない。
  このファイルの検証は**未実施**であり、GitHub ActionsのLinux / Windowsの結果を正とする（PR本文に記載）。
- カバレッジは`pyproject.toml`の`fail_under = 75`（`--cov=src`で実行）でローカルでも確認した。CIの結果も正とする。

## 7. 互換性

- 既存のRoundAnalyzer / AI Coach / 保存形式 / schemaは変更していない。
- 既存の38 fixtureの契約を維持（`validate_dataset.py`で確認）。
- production code変更は§2の1箇所（fail-closed方向のみ）と、Task A/Bで追加した新規モジュール、
  `rules/temporal_scope.py`の判定関数の共有化（結果は同一）。
- Vision側（`hud/` `visual/` `maps/` `application/hud_video_processor.py`）は変更していない。
- 新しいAPI通信・実機・実映像は使っていない。

## 8. 未解決事項（承認が必要で、今回は変更しない）

D-1とD-1bは承認を受けて実装済み（§5）。D-1bはL-5と相互作用する（§5 D-1b）。次の項目は**今回の更新でも変更していない**未解決事項で、いずれも承認が必要。

| ID | 内容 | 推奨 | 影響 |
|---|---|---|---|
| L-1 | zone factのconfidenceをフィールド別source confidenceへ | 承認して修正 | confidenceが上がり得る |
| L-2 | 同一状態の間引きで高confidence観測を残す | 承認して修正（(c)優先） | confidenceが上がり得る |
| L-3 | HP/Armorのprovenance統一（schema変更を伴う） | 承認して修正 | schema・保存形式 |
| L-5 | 表示上限の数え方・保存と表示の分離 | 将来検討 | 保存形式・表示結果 |
| M-1 | Match全体の総合評価（GOOD/IMPROVE・総合スコア） | 作らない（`match_aggregation_design.md` §9-1） | 新しいlabel/confidenceの意味 |

## 9. CI上の既知の不安定性（Linux Qt終了処理）

- **事象**: PR #11の初回Linux Basic CI（pull_request）が、pytestステップでexit code 134（SIGABRT）で失敗した。
  同一コミットのpush側は成功し、再実行（attempt 2）でも成功した。
- **原因**（ユーザー確認）: 全テストが成功した後の**Qt終了処理で発生したプロセスabort**。assertion失敗ではない。
  PR #9で対処された「Linux Qt teardown」問題と同系統の、既存の不安定性として扱う。
- **本PRとの関係**: 本PRはGUI・Qt関連のコードを変更していない（`ui/`・`application/hud_video_processor.py`を含まない）。
  今回の追加修正（`rules/aggregator.py`）は純粋Pythonのルール層で、Qtと接点がない。新たな回帰かどうかは、
  最新main統合状態でのLinux CIの結果（§6）で確認する。
- **その後の調査**: 原因は「`MainWindow`を明示破棄しないままインタプリタ終了処理に入り、PySide6のfinalizeがC++ツリーを破棄してヒープを壊す」
  ことだった。`main()`と`test_ui_smoke.py`の1テストが該当していた。再現条件・根拠・修正・修正前後の比較は
  `docs/qt_shutdown_abort_analysis.md`を参照（独立PR `fix/qt-shutdown-lifecycle`）。本PRの時点ではこの修正は含まれていない。
  CI失敗時は、ログのテスト結果（passed件数）とexit codeを併せて確認し、assertion失敗かprocess abortかを区別すること。

## 10. Windows CI: エンコーディング指定漏れの修正（Qt abortとは別問題）

**混同しないこと**: §9のQt終了処理のabort（Linux、exit code 134、全テスト成功後）とは**別の問題**で、原因も修正も独立している。

- **症状**（ユーザーの実ログ）: Windows verificationのpytestが131件失敗。`UnicodeDecodeError`。
- **原因**: `tests/unit/test_unedited_ui_start.py`の`make_contract()`が、UTF-8の`datasets/input_contracts/match_001.unedited.json`
  （非ASCII文字を含む）を**エンコーディング指定なし**で`read_text()`していた。WindowsのCIの既定はcp1252のため、デコードに失敗する。
  `tests/unit/test_native_assured_start.py`は同じ`make_contract()`を取り込んでおり、同じ原因で落ちる。
- **修正**: 該当の`read_text` / `write_text`に`encoding="utf-8"`を明示（次の6ファイル。実行コードの挙動は変更なし）。
  `test_unedited_ui_start.py`、`test_unedited_ui_end.py`、`test_e2e_dataset_runner.py`、`test_native_system_input.py`、
  `test_e2e_runtime_summary.py`、`tests/integration/test_map_zone_v3.py`。
  - **skipは追加していない**。**CI全体のUTF-8強制（`PYTHONUTF8`等）もしていない**（`.github/`は無変更）。
  - 参考: 既存の`.github/workflows/basic-ci.yml`（Linux）は以前から`PYTHONUTF8: "1"`を設定しており、`windows.yml`には無い。
    このため、エンコーディング指定漏れはLinux CIでは顕在化せず、Windows CIでだけ失敗する。今回この差はそのままにした（Windows側にUTF-8を強制しない）。
- **再現と確認**（Linux上でWindowsの既定エンコーディング=cp1252を再現: エンコーディング未指定のテキストモードopenだけをcp1252にする。
  明示指定とバイナリモードは対象外で、Windowsと同じ）:

  | | 結果 |
  |---|---|
  | 修正前（再現） | **126 failed** / 2779 passed / 9 skipped。内訳: `test_native_assured_start` 70、`test_unedited_ui_end` 29、`test_unedited_ui_start` 26、`test_e2e_dataset_runner` 1。すべて`UnicodeDecodeError: 'charmap' codec can't decode` |
  | 修正後（同じ再現） | **0 failed** / 2905 passed / 9 skipped |
  | 修正後（さらに改行を`\r\n`化・symlink権限なしを再現） | 2 failed / 2901 passed / 11 skipped。失敗は`test_e2e_frame_cache.py::test_symlink_cache_directory_and_source_are_rejected`と`test_scene_source_binding.py::...[escaped_asset]`のsymlink作成のみ（エンコーディングとは無関係。skipは禁止のため手を付けていない）。改行変換による失敗は無し |

  - **ユーザーの実ログは131件、再現は126件で、5件の差は再現環境では説明できていない**。差は未解明。Windows CIの再実行結果で最終確認する（§6）。
- **残る指定漏れ（潜在）**: ASTで走査すると220箇所（`tests/unit` 119、`tests/integration` 9、`scripts` 84、`src/.../visual` 7、`src/.../observability/pi.py` 1）。
  すべて、上記の再現環境で全テストが通る＝**現時点では非ASCIIの内容を読んでおらず、失敗していない**。他のブランチと並行して編集されている
  ファイルが多く、競合を避けるため今回は**失敗経路のファイルだけ**を修正した。`src/.../visual`はVision側のため変更禁止。
  再発防止には、残り全体への`encoding="utf-8"`の追加（機械的で安全）を別途行うのがよい。

## 11. Windows CI: 残っていた4失敗の修正（PR #12と同一のhunkを取り込み）

**混同しないこと**: §9（Linux Qt abort）、§10（エンコーディング）とは別の原因。本PRのD-1/D-1bとも無関係。

- **症状**（ユーザーがGitHub Actionsの実ログで確認、HEAD `a28b39a`）: 2914 passed / 10 skipped / **4 failed**。
  1. `test_native_source_input.py::test_explicit_eof_preserves_every_remaining_native_pts[0]` — `VideoProbeError: native probe must cover both sides of interior window`
     （push側では`test_budgeted_pipe_preserves_complete_native_source_data`が同じエラー）
  2. `test_native_source_input.py::test_budget_overflow_never_yields_partial_frames_and_removes_files` — `PermissionError: WinError 32`（`decode.log`が別プロセスに使用中）
  3. `test_scene_chain_cohort.py::test_optional_joint_audit_requires_frozen_code_and_strict_options` — `KeyError: src/valorant_ai_coach/hud/scene_domains.py`
  4. `test_scene_chain_cohort.py::test_observer_reservation_requires_profile_assets_code_and_decoded_exposure` — `KeyError: scripts/diagnostics/observed_scene_chain.py`
- **原因と修正**は、PR #12で別の作業者（Codex）が既に整理したものと同一で、そのhunkをそのまま取り込んだ（**独自の別実装はしていない**）:

  | 失敗 | 原因 | 修正 |
  |---|---|---|
  | 1 | `-read_intervals`の終端省略（`start%`）がffprobeの一部のバージョンで内部状態を初期化せず、先頭フレーム前にprobeが終わる | EOF読み取りでは区間指定を付けない（ffprobe既定の全体読み取り）。`-threads 1`を付与。エラー文にprobeの診断情報（件数・先頭/末尾PTS・stderr）を追加 |
  | 2 | Chocolateyのshimをkillすると、子のFFmpegが`decode.log`を握ったまま残る | `windows.yml`で、shimではなくパッケージ内の実`ffmpeg.exe`（`ffprobe.exe`と同じディレクトリ）をPATHへ置く。見つからない・複数ある場合は`throw` |
  | 3, 4 | 辞書キーが`/`区切り固定のリテラルで、Windowsの`str(Path(...))`（`\`区切り）と一致しない | テスト側のキーを`str(Path(...))`にしてOS標準の表記に合わせる |

  - 対象: `src/valorant_ai_coach/video/native.py`、`tests/unit/test_native_source_input.py`、`tests/unit/test_scene_chain_cohort.py`、`tests/unit/test_unedited_ui_start.py`（§10と同じ1箇所）、`.github/workflows/windows.yml`。
    **`hud/` `visual/` `maps/` `hud_video_processor.py`は変更していない**。
  - **skipの追加・安全性チェックの削除はしていない**（`native.py`の検証条件は同じ。エラー文の情報を増やしたのみ）。
- **PRの関係**:
  - PR #12（`codex/practical-round-boundaries-20261011`、最新HEAD `3f88b1a`、Windows CI成功）は別の作業者が継続中の可能性があるため、**PR #12のブランチ・内容には触れていない**。
  - Windows修正だけを、PR #12の該当hunkと**逐行で同一**の小さな独立PR **#13**（`fix/windows-ci-native-probe-20261012`、mainを起点）として切り出した。
    同一hunkなので、**PR #11・#12・#13のどれを先にmainへ入れても競合しない**。`git merge-tree`で、本ブランチとPR #12の合成が衝突なしであることを確認した。
  - 本ブランチにはPR #13のコミットをマージして取り込んだ（`f93b26f`）。mainへ先にPR #12または#13が入った場合、同一hunkは重複せず自動的に解消される。
- **エンコーディング修正との関係**: §10で直した`make_contract()`は、PR #12・#13にも同じ修正（`read_text(encoding='utf-8')`）が入っている。
  書き方だけが違う（本ブランチは変数を介し、PR #12/#13は1式）ため、マージではPR #12/#13の形に揃えた（挙動は同一）。
