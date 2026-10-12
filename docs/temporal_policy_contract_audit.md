# Temporal Policy 契約監査（Task B）

対象: `config/valorant_evaluation_rules_v4.json`（44ルール）と、それを読む実コード。
判定は**ドキュメントではなく実コードの参照箇所**を根拠にした。根拠のコード参照は、
`tests/unit/test_temporal_policy_contract.py::test_runtime_users_of_each_policy_field_match_the_audit`
が機械的に固定している（参照ファイルが変わるとテストが落ち、この文書の更新を促す）。

- 起点main: `e9ecaf8f2f0f0dfa1f9433d40a598ec8909e9ce3`
- 実画像・実動画・実API・Vision側コードは一切使用していない。
- 新しい評価判断（label / score / confidence）は生成していない。

## 1. 分類の凡例

| 分類 | 意味 |
|---|---|
| IMPLEMENTED | 実行時コードが仕様どおり読み、挙動に反映している |
| PARTIAL | 一部の項目・一部の経路にだけ反映されている |
| NOT_IMPLEMENTED | 実行時コードが読んでいない（設定値は存在するだけ） |
| UNDECIDED | 仕様が曖昧で、実装方式の選択にユーザー判断が必要 |

「読んでいるか」と「仕様が決まっているか」は別軸なので、NOT_IMPLEMENTEDかつUNDECIDEDの項目は両方記載する。

## 2. 項目別の対応状況（実コード根拠）

| 項目 | 分類 | 実コードの参照箇所 | 実際の挙動・備考 |
|---|---|---|---|
| `level_code` | IMPLEMENTED | `rules/temporal_scope.py` `TemporalScopeResolver.resolve`(L77〜) | 設定のlevelが候補のlevelより優先される。registry/rules間のlevel一致は今回テストで固定（§5） |
| `event_window_seconds` | IMPLEMENTED | `rules/temporal_scope.py` `_event_windows`(L96〜) | pivot event前後の窓を作り、ラウンド範囲にclampし、重なる窓は結合。pivotが無い・窓が空ならラウンド全体にfallback |
| `requires_previous_round_context` | IMPLEMENTED | `rules/temporal_scope.py` L81〜, `validate_output_scope_payload`(L225〜) | 文脈が無い（無し/None/空object）とき `missing_context` を設定し、good/improveの採点を拒否する。unscoredは許可。今回、判定を `previous_round_context_missing()` に一本化 |
| `requires_round_timeline` | PARTIAL | `ui/backend.py` L42 → `ui/main_window.py` L725 | **UI表示だけ**（「ラウンド全体の文脈を参照」ラベル）。採点のゲートにはなっていない。Round時間軸が不完全でも採点は止まらない。仕様上ゲートにすべきかは未定義 → UNDECIDED（§6-1） |
| `uses_whole_match_aggregation` | NOT_IMPLEMENTED（実行時）/ 報告のみ今回追加 | 実行時の読み取りなし。`rules/temporal_contract.py` と `application/match_aggregation.py` が**報告専用**で読む | 実行時パイプラインはラウンド単位。Match総合の評価ロジックは存在しない。Match全体の評価基準は人間判断を含むため UNDECIDED（§6-2） |
| `display_clip_strategy` | NOT_IMPLEMENTED | 参照なし | 自然言語（例:「代表例8〜15秒を最大3本程度」）。固定秒数へは変換していない。実際のclip窓は別項目 `suggested_clip_window_seconds`（`ai/coach.py` L685）由来で、`display_clip_strategy` とは無関係。→ UNDECIDED（§6-3） |
| `temporal_tolerance_policy`（トップレベル） | NOT_IMPLEMENTED | 参照なし | level別 `evidence_sec` / `clip_sec`。`TemporalScopeResolver` の `_TOLERANCE_SEC = 0.05` とは**別概念**。同じものとして扱っていない |
| `test_tolerance_seconds`（ルール別） | NOT_IMPLEMENTED | 参照なし | 全44ルールで、そのlevelの `temporal_tolerance_policy` と一致していることをテストで固定（データ整合のみ） |
| `automation_policy.candidate_selection` | NOT_IMPLEMENTED（直接参照なし） | 参照なし | 全44ルールが `deterministic_rule_engine`。実際の候補選択は `rules/selector.py`（registry）が行う |
| `automation_policy.final_label_mode` | PARTIAL（間接） | 直接参照なし。`rules/selector.py` L58 が registry の `label_mode` を読む | 全44ルールで registry の `label_mode` と一致していることをテストで固定。値が食い違えば検出できるが、`automation_policy` 自体は実行方式を決めていない |
| `aggregation_policy.deduplicate_same_rule_within_seconds` | IMPLEMENTED | `rules/aggregator.py` L20 | 同一rule・同一label・同一scope（=同一ラウンド）内でのみ重複排除 |
| `aggregation_policy.max_display_exemplars_per_match` | IMPLEMENTED | `rules/aggregator.py` L99〜 | ruleごとにMatch全体で表示上限。**上限超過分は保存結果から消える**ため、保存済み結果の件数は下限値（§4） |
| `aggregation_policy.aggregate_repeated_occurrences` | NOT_IMPLEMENTED | 参照なし | 6ルール(AIM-01〜04, MOV-01, MOV-02)が `true`。「繰り返しを集約」の具体的な出力形式が未定義 |
| `aggregation_policy.summary_required_if_occurrences_at_least` | NOT_IMPLEMENTED | 参照なし | 同じ6ルールが `3`。要約を誰が・何で生成するか未定義（LLM総評は事前承認が必要） |
| `suggested_clip_window_seconds` | IMPLEMENTED | `ai/coach.py` L685 | 実際のclip窓。`event_window_seconds` / `display_clip_strategy` / tolerance とは別概念 |

### 2.1 evidence窓 0.75 秒について

`rules/mock_evaluator.py` と `ai/coach.py` は evidence を「観測した瞬間 ±0.75 秒」に固定している。
この値は `temporal_tolerance_policy.micro.evidence_sec = 0.75` と数値が同じだが、
**同じ概念であるという根拠はコードにも設定にも無い**。偶然の一致か意図的かはユーザー判断（§6-4）。
今回は変換も統合もしていない。

## 3. 44ルールの対応表

`scripts/audit_temporal_policy.py` が `config/valorant_evaluation_rules_v4.json` から機械生成した表。
テスト `test_audit_document_contains_the_current_44_rule_table` が、この表と設定の一致を検証する
（設定を変えたら `python scripts/audit_temporal_policy.py` の出力で置き換える）。

| Rule | Level | event_window (前/後 秒) | requires_round_timeline | requires_previous_round_context | uses_whole_match_aggregation | display_clip_strategy | automation (candidate_selection / final_label_mode) | aggregation (反復集約 / 重複排除秒 / 表示上限 / 要約閾値) |
|---|---|---|---|---|---|---|---|---|
| ADV-01 | round | - | yes | no | no | 根拠となる場面10〜25秒。必要なら複数クリップ | deterministic_rule_engine / llm_contextual | no / 35 / 2 / - |
| ADV-02 | phase | - | yes | no | no | 核心部分15〜25秒。局面全体は時系列要約を併記 | deterministic_rule_engine / llm_contextual | no / 35 / 2 / - |
| ADV-03 | round | - | yes | no | no | 根拠となる場面10〜25秒。必要なら複数クリップ | deterministic_rule_engine / llm_contextual | no / 35 / 2 / - |
| ADV-04 | round | - | yes | no | no | 根拠となる場面10〜25秒。必要なら複数クリップ | deterministic_rule_engine / llm_contextual | no / 35 / 2 / - |
| ADV-05 | phase | - | yes | no | no | 核心部分15〜25秒。局面全体は時系列要約を併記 | deterministic_rule_engine / llm_contextual | no / 35 / 2 / - |
| ADV-06 | round | - | yes | no | no | 根拠となる場面10〜25秒。必要なら複数クリップ | deterministic_rule_engine / llm_contextual | no / 35 / 2 / - |
| ADV-07 | cross_round | - | yes | yes | no | 購入画面/判断場面10〜20秒＋経済状況テキスト | deterministic_rule_engine / llm_contextual | no / 35 / 2 / - |
| ADV-08 | phase | - | yes | no | no | 核心部分15〜25秒。局面全体は時系列要約を併記 | deterministic_rule_engine / llm_contextual | no / 35 / 2 / - |
| AIM-01 | match | - | yes | no | yes | 代表例8〜15秒を最大3本程度 | deterministic_rule_engine / llm_contextual | yes / 35 / 3 / 3 |
| AIM-02 | micro | 6/4 | no | no | yes | 原則8〜15秒の1クリップ | deterministic_rule_engine / deterministic_if_confident_else_llm | yes / 20 / 3 / 3 |
| AIM-03 | micro | 6/4 | no | no | yes | 原則8〜15秒の1クリップ | deterministic_rule_engine / deterministic_if_confident_else_llm | yes / 20 / 3 / 3 |
| AIM-04 | micro | 6/4 | no | no | yes | 原則8〜15秒の1クリップ | deterministic_rule_engine / llm_contextual | yes / 20 / 3 / 3 |
| DEC-01 | round | - | yes | no | no | 根拠となる場面10〜25秒。必要なら複数クリップ | deterministic_rule_engine / llm_contextual | no / 35 / 2 / - |
| DEC-02 | round | - | yes | no | no | 根拠となる場面10〜25秒。必要なら複数クリップ | deterministic_rule_engine / llm_contextual | no / 35 / 2 / - |
| DEC-03 | local | 15/12 | no | no | no | 原則10〜20秒。必要なら直前情報を説明文で補足 | deterministic_rule_engine / llm_contextual | no / 20 / 2 / - |
| DEC-04 | round | - | yes | no | no | 根拠となる場面10〜25秒。必要なら複数クリップ | deterministic_rule_engine / llm_contextual | no / 35 / 2 / - |
| DEC-05 | round | - | yes | no | no | 根拠となる場面10〜25秒。必要なら複数クリップ | deterministic_rule_engine / llm_contextual | no / 35 / 2 / - |
| ECO-01 | cross_round | - | yes | yes | no | 購入画面/判断場面10〜20秒＋経済状況テキスト | deterministic_rule_engine / llm_contextual | no / 35 / 2 / - |
| ECO-02 | cross_round | - | yes | yes | no | 購入画面/判断場面10〜20秒＋経済状況テキスト | deterministic_rule_engine / llm_contextual | no / 35 / 2 / - |
| INFO-02 | local | 12/15 | no | no | no | 原則10〜20秒。必要なら直前情報を説明文で補足 | deterministic_rule_engine / llm_contextual | no / 20 / 2 / - |
| INFO-03 | round | - | yes | no | no | 根拠となる場面10〜25秒。必要なら複数クリップ | deterministic_rule_engine / llm_contextual | no / 35 / 2 / - |
| INFO-04 | local | 15/12 | no | no | no | 原則10〜20秒。必要なら直前情報を説明文で補足 | deterministic_rule_engine / llm_contextual | no / 20 / 2 / - |
| MOV-01 | micro | 6/4 | no | no | yes | 原則8〜15秒の1クリップ | deterministic_rule_engine / llm_contextual | yes / 20 / 3 / 3 |
| MOV-02 | micro | 6/4 | no | no | yes | 原則8〜15秒の1クリップ | deterministic_rule_engine / deterministic_if_confident_else_llm | yes / 20 / 3 / 3 |
| MOV-03 | local | 15/8 | no | no | no | 原則10〜20秒。必要なら直前情報を説明文で補足 | deterministic_rule_engine / llm_contextual | no / 20 / 2 / - |
| MOV-04 | local | 12/12 | no | no | no | 原則10〜20秒。必要なら直前情報を説明文で補足 | deterministic_rule_engine / llm_contextual | no / 20 / 2 / - |
| OBJ-02 | phase | - | yes | no | no | 核心部分15〜25秒。局面全体は時系列要約を併記 | deterministic_rule_engine / llm_contextual | no / 35 / 2 / - |
| OBJ-03 | phase | - | yes | no | no | 核心部分15〜25秒。局面全体は時系列要約を併記 | deterministic_rule_engine / llm_contextual | no / 35 / 2 / - |
| PEEK-01 | round | - | yes | no | no | 根拠となる場面10〜25秒。必要なら複数クリップ | deterministic_rule_engine / llm_contextual | no / 35 / 2 / - |
| PEEK-02 | micro | 7/5 | no | no | no | 原則8〜15秒の1クリップ | deterministic_rule_engine / llm_contextual | no / 20 / 2 / - |
| PEEK-04 | micro | 6/5 | no | no | no | 原則8〜15秒の1クリップ | deterministic_rule_engine / deterministic_if_confident_else_llm | no / 20 / 2 / - |
| PEEK-05 | local | 15/8 | no | no | no | 原則10〜20秒。必要なら直前情報を説明文で補足 | deterministic_rule_engine / llm_contextual | no / 20 / 2 / - |
| POS-01 | local | 15/10 | no | no | no | 原則10〜20秒。必要なら直前情報を説明文で補足 | deterministic_rule_engine / llm_contextual | no / 20 / 2 / - |
| POS-03 | local | 15/10 | no | no | no | 原則10〜20秒。必要なら直前情報を説明文で補足 | deterministic_rule_engine / llm_contextual | no / 20 / 2 / - |
| POS-04 | phase | - | yes | no | no | 核心部分15〜25秒。局面全体は時系列要約を併記 | deterministic_rule_engine / llm_contextual | no / 35 / 2 / - |
| POS-05 | round | - | yes | no | no | 根拠となる場面10〜25秒。必要なら複数クリップ | deterministic_rule_engine / llm_contextual | no / 35 / 2 / - |
| ROLE-02 | local | 15/12 | no | no | no | 原則10〜20秒。必要なら直前情報を説明文で補足 | deterministic_rule_engine / llm_contextual | no / 20 / 2 / - |
| ROLE-03 | round | - | yes | no | no | 根拠となる場面10〜25秒。必要なら複数クリップ | deterministic_rule_engine / llm_contextual | no / 35 / 2 / - |
| ROLE-06 | phase | - | yes | no | no | 核心部分15〜25秒。局面全体は時系列要約を併記 | deterministic_rule_engine / llm_contextual | no / 35 / 2 / - |
| ROLE-07 | round | - | yes | no | no | 根拠となる場面10〜25秒。必要なら複数クリップ | deterministic_rule_engine / llm_contextual | no / 35 / 2 / - |
| ROLE-08 | round | - | yes | no | no | 根拠となる場面10〜25秒。必要なら複数クリップ | deterministic_rule_engine / llm_contextual | no / 35 / 2 / - |
| TEAM-02 | phase | - | yes | no | no | 核心部分15〜25秒。局面全体は時系列要約を併記 | deterministic_rule_engine / llm_contextual | no / 35 / 2 / - |
| UTL-01 | local | 20/5 | no | no | no | 原則10〜20秒。必要なら直前情報を説明文で補足 | deterministic_rule_engine / llm_contextual | no / 20 / 2 / - |
| WPN-01 | local | 12/8 | no | no | no | 原則10〜20秒。必要なら直前情報を説明文で補足 | deterministic_rule_engine / llm_contextual | no / 20 / 2 / - |

### 3.1 表から読める事実

- level内訳: round 14 / local 11 / phase 8 / micro 7 / cross_round 3 / match 1。
- `uses_whole_match_aggregation=yes` は6ルール（AIM-01〜04, MOV-01, MOV-02）。**match levelはAIM-01だけ**で、
  他の5ルールはmicro levelの評価をMatch全体で集約する。この違いは `RuleTemporalPolicy.needs_match_context`
  と `MatchAggregation` の両方で保持される。
- `requires_previous_round_context=yes` は3ルール（ECO-01, ECO-02, ADV-07）で、すべて cross_round。
- 全ルールの `candidate_selection` は `deterministic_rule_engine`。`final_label_mode` は
  `llm_contextual` 40件、`deterministic_if_confident_else_llm` 4件（AIM-02, AIM-03, MOV-02, PEEK-04）。
- `event_window_seconds` を持つのは micro / local の18ルール。round / phase / cross_round / match は持たない
  （持たせようとするとテストが拒否する）。

## 4. 実装したもの（仕様から一意に決まるもの）

| 追加物 | 内容 |
|---|---|
| `rules/temporal_contract.py` | 44ルールの政策値を読み取り専用のテーブルとして検証・公開する（`TemporalPolicyTable` / `RuleTemporalPolicy`）。形の不正（bool以外、NaN/Inf、負の窓、幅0、未知level、whole-round levelへの窓、重複id）は rule id 付きで拒否 |
| `assess_context()` | ルール×Round Package に対し「必要な文脈」「欠けている文脈」「Round時間軸の観測状況」「時間範囲が特定できているか」を返す。**labelもconfidenceも生成しない** |
| `round_timeline_status()` | `observation_quality` だけから complete / partial / unavailable / unknown を返す。欠落・不正値は推測せず unknown。completeness 0 は「測定された割合」ではなく unavailable |
| `previous_round_context_missing()` | `rules/temporal_scope.py` に追加。Resolverと下流が同じ定義（None/空objectは欠落）を使う |
| `TemporalPolicyTable.validate_registry_alignment` | rules JSON と trigger registry のlevel・ルール集合の不一致を検出 |
| `scripts/audit_temporal_policy.py` | §3の表の生成 |

既存の `TemporalScopeResolver` の挙動は変えていない（共通関数への置き換えのみ。既存テストはすべて通過）。

### 4.1 Task A（Match集計）への受け渡し

`MatchAggregator` は各ルール・各Roundについて `ContextAssessment` を保持し、次を伝える。

| 伝える情報 | フィールド |
|---|---|
| Match全体の文脈が必要か | `needs_match_context` / `RuleAggregate.needs_match_context` |
| Round単体で評価可能か | `needs_match_context == false` かつ `missing_context == ()` |
| 過去Roundの情報が必要か | `needs_previous_round_context` |
| 必要な文脈が欠けているか | `missing_context` |
| Match文脈が未検証か | `match_context_unverified`（`expected_round_numbers` を与えて完全性が検証されるまで true） |
| 時間範囲が特定できているか | `time_scope`（event_windows / whole_round_by_policy / whole_round_fallback / unknown） |
| Round時間軸の観測状況 | `round_timeline` / `round_timeline_shortfall` |

不足は**明示するだけ**で、評価の置き換え・補完・再判定はしない。

## 5. 追加したテスト（`tests/unit/test_temporal_policy_contract.py`）

既存の `test_temporal_scope.py` / `test_schema_validation.py` が既にカバーしているもの
（Round境界外のevent/fact/frame時刻の拒否、無限・NaNの拒否、窓のclamp、scope外evidenceの拒否など）は重複させていない。

| テスト群 | 固定する不変条件 |
|---|---|
| 44ルールテーブル | 44件・id昇順、rules JSON と registry のルール集合/levelの一致、drift検出（negative control付き） |
| 設定内の整合 | `test_tolerance_seconds` = levelの `temporal_tolerance_policy`、`final_label_mode` = registry `label_mode`、`trigger.temporal_level` = `level_code` |
| 概念の分離 | 6ルールのwhole-match flagとmatch levelは別（AIM-01のみmatch）、previous-round必須はECO-01/ECO-02/ADV-07のみ、whole-roundレベルは窓を持たない、`display_clip_strategy` は自然言語のまま、行にtoleranceが混ざらない |
| 形の検証 | 24通りの不正値をrule id付きで拒否、whole-round level×窓、重複id、`rules` 配列欠落 |
| previous_round_context | 欠落/None/空object/空配列/内容ありを Resolver と `assess_context` が同じ判定にする。不要なルールは欠落扱いにならない |
| Scope | Round外pivotが窓を作らない、境界上のpivot、event順序に依存しない・入力を変更しない、設定にないルールの扱い、設定levelが優先、包含判定の許容 0.05 秒を超えて広げない（0.75 秒の別概念と混ざらない） |
| assess_context / timeline | time_scopeの4状態、17通りの observation_quality からの状態判定（不正値でcompleteにならない）、shortfallは必要なルールだけ、`requires_round_timeline` が採点ゲートにならないこと、純粋・JSON安全・判断語を含まない |
| 監査の固定 | 各ポリシー項目を読む実コードの集合（§2）と、この文書の表の同期 |

## 6. ユーザー判断が必要な点

各項目に「現状 / 選択肢 / 推奨案 / 理由 / 既存コードへの影響」を記載する。**いずれも未実装・変更なし**。

### 6-1. `requires_round_timeline` を採点のゲートにするか

- 現状: 26ルールが `true`。UI表示にだけ使われ、Round時間軸が不完全（`timeline_completeness<1` や `missing_intervals`あり）でも採点は止まらない。
- 選択肢: (a) 現状維持（報告のみ） (b) 不完全時は good/improve を拒否し unscored（`missing_information` に理由）にする (c) 不完全時はconfidenceに上限を設ける
- 推奨: まず (a) を維持し、Match集計側の `round_timeline_shortfall` で可視化。(b) は「どの程度の欠損で拒否するか」の閾値が決まってから。
- 理由: 閾値が仕様に無く、決めると評価の意味が変わる。(c) は新しいconfidence計算方式にあたり事前承認が必要。
- 影響: (b)(c) は `temporal_scope.validate_output_scope_payload` と既存fixture期待値に影響。

### 6-2. Match全体の評価（`uses_whole_match_aggregation`）

- 現状: 実行時はラウンド単位。Match集約は報告専用（件数・分類・参照・欠損）で、Match全体のGOOD/IMPROVE判定は存在しない。
- 選択肢: (a) 現状維持 (b) 件数閾値に基づく機械的な傾向ラベル (c) LLMによるMatch総評
- 推奨: (a)。AIM-01の評価基準は「毎回合っていないことを指摘されても仕方ないので全体通してどうだったか」という人間的評価で、回数では決まらない。
- 理由: (b)(c) は独自の評価重み・総合判定・新たなAPI呼び出しを意味し、依頼上すべて事前承認が必要。
- 影響: (b)(c) は新しい出力スキーマと保存形式が必要。

### 6-3. `display_clip_strategy`（自然言語）の扱い

- 現状: 実際のclip窓は `suggested_clip_window_seconds`（前後秒）。`display_clip_strategy` は誰も読まない。
- 選択肢: (a) 説明文として保持するだけ (b) 構造化フィールドへ移行（例: 長さの範囲・最大本数）
- 推奨: (b) を行うならルールJSONに構造化フィールドを**別途追加**し、自然言語を秒数へ自動変換しない。
- 理由: 「必要なら複数クリップ」等は機械変換できず、変換すると仕様を捏造する。
- 影響: ルールJSONのschema追加、`ai/coach.py` のclip窓決定。

### 6-4. `temporal_tolerance_policy` の用途

- 現状: 実行時未使用。`_TOLERANCE_SEC = 0.05` と evidence ±0.75 秒（ハードコード）は別系統。
- 選択肢: (a) テスト用許容値としてのみ扱う（現状と同じ） (b) 実行時の検証許容へ反映 (c) ±0.75秒の出所として設定へ接続
- 推奨: (a)。
- 理由: `test_tolerance_seconds` という名前からテスト用の許容値と読める。(b)(c) は既存fixtureの契約に影響し、意味の確認が必要。
- 影響: (b)(c) は `schema_validation` / `mock_evaluator` / `ai/coach.py` の許容判定が変わる。

### 6-5. `automation_policy`

- 現状: 全44ルールが `deterministic_rule_engine`。実際の方式選択は registry の `label_mode`（`final_label_mode` と全件一致）。
- 選択肢: (a) registryを正とし `automation_policy` は説明用 (b) `automation_policy` を単一の正とし registry を生成物にする
- 推奨: (a)＋整合性テスト（実装済み）。
- 理由: 実行方式の変更は Rule Engine と AI Coach の責務境界に関わり、現状の仕様は十分に明確ではない。
- 影響: (b) は `selector.py` と registry 生成手順の変更。

### 6-6. `aggregate_repeated_occurrences` / `summary_required_if_occurrences_at_least`

- 現状: 実行時未使用（6ルールが true / 3）。
- 選択肢: (a) 件数・分類・参照だけをMatch集計で提供（実装済み） (b) 閾値超過時に決定論の「発生回数サマリ」を出す (c) LLM要約
- 推奨: (a) を維持し、(b) は文面を決定論にし判定語を含めない形で別途承認を得る。
- 理由: 要約は評価の言い換えになり得る。
- 影響: (b)(c) は出力スキーマ追加。

## 7. 今後必要な実装（承認後）

1. §6-1〜§6-6 の判断が出た項目の実装。
2. `max_display_exemplars_per_match` で消えた評価を保存結果に残す（件数の下限を真値へ近づけるため）。現状、保存済み結果から集計すると下限値になる。
3. Match集計をUI / 保存形式へ接続（今回は集計基盤のみ。互換性維持のため既存保存形式・UIは未変更）。
