# External AI 非画像解析領域 作業レポート（中間）

- branch: `external/non-vision-pipeline`
- 開始commit SHA: `e05c49543ada515530ed3ba6c6f6438f927aebc5`（依頼書記載のHEADと一致）
- 状態: **中間報告**。Priority 1 の精査と、確認できた安全契約違反1件の修正まで。

## 1. これまでに確認した事実

### 1.1 ベースライン（変更前）

- 後段関連テスト（fact builder / rule selector / rule engine / schema validation / storage / ui smoke / clips / round package builder）: 51 passed, 1 skipped（PySide6未導入のUI smokeのみ）
- `tests/cases/TC-001`〜`TC-038` を `RoundAnalyzer` + `MockCoachAdapter` に通した結果: 36件は期待どおり、**2件（TC-005, TC-017）が例外**（後述 §3.2）
- `ruff check .` は変更前から多数の指摘あり（リポジトリ全体、後段コード以外を含む）。本作業の変更ファイルについては指摘0。

### 1.2 層の責務（読んで確認できた範囲）

| 層 | 実装 | 役割 |
|---|---|---|
| direct observation | HUD Observation（vision側） | 画面から読んだ値。`primary_state` / `player_specific_hud_valid` を持つ |
| normalized/derived event | `events/derived.py`（`state_snapshot`, `objective_state` のみ生成） | 非評価的イベント。位置・utility・save判断は作らない設計 |
| round package | `rounds/builder.py` | observationをsnapshot/eventsへ整形。非player視点の `hp/armor/weapon/utility` をここでマスク |
| deterministic fact | `facts/builder.py` | snapshot/eventからfact化。confidenceとprovenanceを付与 |
| deterministic decision | `rules/engine.py`（AIM-02, AIM-03, MOV-02, PEEK-04のみ） | confidence≥0.90、同一key内の一致を要求。不一致・不足は `None` |
| hybrid AI evaluation | `ai/coach.py` / `rules/mock_evaluator.py` | decision無しのruleの評価・文章生成 |
| authority check | `application/round_analyzer.py` | 出力labelがdecisionと一致し、fact_refsを含むことを検証 |

※ UI view model（`ui/`）、storage、clipは未精査。

## 2. 実施した変更

### 2.1 非player視点の spike_state がplayer factへ漏れる問題を修正

- 再現: spectator視点のobservationが `spike_state=carried_by_player` を持つと、`hp/weapon` はマスクされるが `spike_state` は素通しで、`FactBuilder` が `spike_carried_by_player=True` を生成した。`carried_by_ally` / `not_carried` からは偽の否定fact（`False`）も生成されうる。
- 修正: `rounds/builder.py` に `_player_scoped_spike_state` を追加。`player_specific_hud_valid=false` のとき、視点相対の3値（`carried_by_player`, `carried_by_ally`, `not_carried`）を `unknown` にする。`planted` / `dropped` / `defusing` / `resolved` は視点非依存のため維持。
- live視点の挙動は不変（テストで固定）。
- 画像解析コード・player identity判定は変更していない。これはVisionの出力を後段で安全側に倒す変更。
- テスト: `tests/unit/test_downstream_contract.py`（10件）

## 3. ユーザー決定に基づく契約変更（2026-10-07）

### 3.1 同一factが複数ruleの決定論labelを生む場合は両ruleを出力（TC-005 / TC-017）

- 原因: `first_shot_stationary` が MOV-02 と AIM-03 の両方に決定論labelを出すが、mockは片方のみ出力し、`RoundAnalyzer` の権威検証が「評価の欠落」で例外にしていた。実コーチは出力されなかったdecisionを独立評価として合成する実装。
- 変更: `rules/mock_evaluator.py` が、decisionを持つ rule をすべて出力する。
- 結果: 既存 `dedup_groups.movement_shooting`（primary_order: AIM-03 → MOV-02）が最終段で働き、**AIM-03を主・MOV-02を `related_rule_ids` とする1件**になる（重複クリップ回避の既存方針）。
- **TC-005 の主ruleが MOV-02 → AIM-03 に変わる。** TC-005/017 の `expected_assertions.json` を更新（`allowed_related_rule_ids=["MOV-02"]`）。
- 全38ケースが `RoundAnalyzer` + mock を通ることをテストで固定。

### 3.2 低confidenceは「評価0件」ではなく明示的な `unscored`

- 変更: `rules/engine.py`。factが存在し、全て信頼度0.90未満のとき、AIM-02 / AIM-03 / MOV-02 / PEEK-04 は `unscored`（`low_confidence`、confidence ≤ 0.5、`fact_refs` 保持、`missing_information` あり）を返す。
- 変わらない点: fact不在は従来どおり `None`（selector / hybrid側が扱う）。smoke例外は評価対象外のまま。信頼度の高いfactが1つでもあればそれが優先。
- `ai/coach.py` の `_bind_deterministic_evaluation` に `unscored` 分岐を追加（従来は常にclip付きの採点済み形で、スキーマ違反の出力になっていた）。
- 旧契約を前提にした既存テスト2件の期待値を更新: `tests/unit/test_rule_engine.py`、`tests/integration/test_visual_review_regressions.py`（vision側のテストファイル、1パラメータ: 0.86 は `None` → `unscored`）。
- 既知の挙動: `unscored` は `evidence_range` を持たないため集約で統合されず、同一factの MOV-02 / AIM-03 が `unscored` では2件別々に出る。統合するかは未決定。

## 4. 未実施（次の作業）

- Priority 2: 依頼の6ケースは、good: TC-006、improve: TC-017、unscored(必須fact不足): TC-025、unscored(低confidence): `test_downstream_contract.py`、authority: `test_round_analysis.py`、spectator: builder層テスト、で網羅。`RoundAnalyzer` 経由のspectator end-to-endは未作成。
- Priority 3: 完了（§7）
- Priority 4: 完了。`docs/external_ai_rules_criteria_diff.md` 参照（44ルールすべて一致、rule変更不要。要判断2点）
- Priority 5/6: AI Coach検証層、UI（PySide6未導入のため smoke 未実行）、ClipService
- 全体 `pytest` / `ruff check .` / `mypy src` の最終結果

### 4.1 残る確認事項

- 入力済みfactのconfidenceが、provenanceで参照するeventのconfidenceより高くてもそのまま採用される（TC-006でeventのみ0.3にしても決定論 `good` が維持される）。`FactBuilder` 由来factは元eventから導出されるため、事前計算済みfactを渡すfixture特有の挙動の可能性が高い。本番経路で事前計算済みfactが渡る箇所があるか未確認（`rounds/builder.py` の `_owned_hp_facts` / `_shared_timer_facts` は直接factを生成する）。

## 5. テスト・静的解析（このセッションの環境、1CPU）

- 後段関連の主要14ファイル: 141 passed, 2 skipped（PySide6未導入のUI 2件）
- 全100ファイルを個別実行し、完了した50ファイルは失敗2件のみ: `test_real_ffmpeg`（変更前から失敗、環境起因）、`test_hud_pixels_e2e`（vision側の重いテスト、120秒タイムアウト）
- 残りのvision側テスト（hud / visual系の大半）は未実行。vision側production codeは未変更
- `ruff check`: 変更ファイルは指摘0。リポジトリ全体は変更前から386件の既存指摘
- `mypy src`: 22件、変更前と同数（PySide6未導入、hud側の既存分）。変更ファイルに指摘なし

## 6. 「AIが見る範囲」（temporal_context）の評価ロジックへの反映（ユーザー承認済み）

実装: `src/valorant_ai_coach/rules/temporal_scope.py`、`RoundAnalyzer` に統合。

**方針: 範囲は「絞る」方向にだけ働く。観測を足さず、不足は `unscored` 側へ倒す。**

| レベル | 範囲 |
|---|---|
| micro / local（`event_window_seconds` あり） | トリガeventの時刻の前後（before/after秒）を結合した窓。round windowでクランプ。pivotが無ければ全ラウンド |
| phase / round / match / cross_round | 全ラウンド（phaseの境界情報が無く、推測しないため） |

反映箇所:
1. **入力**: 候補が全てwindowedのときだけ、AIへ渡すpackageの `events` / `state_snapshots` / `frames`（と対応する `frame_paths`）を窓の和集合に絞る。決定論decisionが引くfactと、保持factが引くeventは残す（provenance維持）。観測の追加はしない。
2. **prompt**: 実コーチのpromptにrule別の `analysis_scopes` を含める。
3. **出力検証**（`validate_output_scope`）: 採点済み（good/improve）の `evidence_range` は、関与するruleの分析範囲内であること。`unscored` は対象外。`display_clip` は制約しない（クリップ窓は別定義）。
4. **文脈不足**: `requires_previous_round_context` のruleで `previous_round_context` が無い場合、good/improveは `ContractValidationError`（ECO-01 / ECO-02 / ADV-07）。

副次的な変更:
- `MockEvaluator` の `evidence_range` を表示クリップ窓（±5秒）から**事象時刻±0.75秒**に変更（実コーチと同じ）。`display_clip` は不変。mockの根拠範囲が窓をはみ出して検証に落ちたため。
- `RoundCoach` / `OpenAICoach.evaluate` / `MockCoachAdapter.evaluate` に任意引数 `analysis_scopes` を追加。`RoundAnalysis` に `analysis_scopes` を追加。

**限界（実測）**:
- **入力の絞り込みは、全38fixtureで一度も働かなかった。** どのケースにもラウンド全体が必要なruleが1件以上あり、1回のAI呼び出しでは全体に倒れる。現状で実効があるのは、rule別の範囲検証（29ケースで窓が狭まる）と文脈不足の検証、およびpromptへの範囲提示。入力の絞り込みを実効化するには、windowed群とwhole-round群でAI呼び出しを分ける必要があり、API呼び出し回数（コスト）が増えるため未実施。
- 範囲違反・文脈不足は `ContractValidationError`（修復ループ対象外）。実モデルの出力で起きた場合の扱い（修復／降格）は未決定。
- 窓は `event_window_seconds` とトリガeventのみから決まる。`requires_round_timeline` / `uses_whole_match_aggregation` / `display_clip_strategy` はこの変更の対象外。
- 実モデル（OpenAI API）では未検証。テストはmockとスタブのみ。

テスト: `tests/unit/test_temporal_scope.py`（20件）。全38 fixtureが範囲検証を通ることを確認済み。

## 7. Event / Fact / Rule の責務整理（Priority 3）

### 7.1 見つけて修正した問題

| 問題 | 実測 | 対応 |
|---|---|---|
| `DerivedEventBuilder` のevent_idが**動画全体のobservation位置**由来 | 先頭に低confidenceのobservationを1件足すだけで、同じ観測のidが `...000000` → `...000001` に変わる | idを観測時刻（ms）由来に変更（`DERIVED-STATE-000005000`）。同一ms衝突は決定論的ソート順で `-02` を付与 |
| 同時刻observationの出力が入力順に依存しうる | — | 時刻＋正規化JSONで安定ソート。任意順で同一出力をテストで固定 |
| spectator視点で、派生event（`state_snapshot` / `objective_state`）に `spike_state=carried_by_player` が出る（イベントログはAIにも渡る） | 再現確認 | 視点相対の3値を `unknown` に。`rounds/builder.py` と**同じ規則を共有ヘルパー `player_scoped_spike_state` に一本化**（重複実装を削除） |
| 他プレイヤーのhp/armor変化がplayerの `state_snapshot` event を生む | — | 非player視点ではhp/armorを変化検知から除外 |
| `time_sec` がNaN→黙って0.0秒、欠落→0.0秒 | 再現確認 | `DerivedEventInputError` で明示的に拒否（NaN/inf/負/非数値/bool/欠落、valuesが無いobservation）。`hud_confidence` が使えない値のときは従来どおり安全側（0扱いで除外） |
| factのconfidenceが、provenanceで参照するeventより高くても通る | 本番の事前計算fact（`_shared_timer_facts` / `_owned_hp_facts`）はeventを参照せず問題なし。fixture 65件・`FactBuilder` 生成66件で違反0 | `validate_round_package` に「factのconfidence ≤ 参照eventの最小confidence」を追加（引き上げ禁止） |

テスト: `tests/unit/test_derived_events.py`（28件）、`test_downstream_contract.py` に confidence ガードのテストを追加。

### 7.2 契約への影響

- **event_idの形式が変わった。** 既存の保存済み結果のidは変わらない（移行なし）。AI結果キャッシュはpackage内容をキーにするため、派生eventを含むpackageは1回キャッシュミスになる。
- `validate_round_package` が厳しくなった（confidence引き上げ、`DerivedEventInputError` は組み立て時）。
- schema / config は未変更。

### 7.3 責務の整理（読んで確認）

| 概念 | 生成層 |
|---|---|
| direct observation | HUD / Visual（vision側） |
| normalized event | HUD / Visual のevent（`EventSourceContract` で検証） |
| derived event | `DerivedEventBuilder`（`state_snapshot` / `objective_state` のみ。位置・utility・save判断は作らない） |
| deterministic fact | `FactBuilder`（snapshot / eventから）、`rounds/builder.py`（HP・タイマーのROI信頼度から直接） |
| deterministic decision | `DeterministicRuleEngine` |

- `state_snapshot` eventと `state_snapshots` はどちらも ally/enemy/spike を持つ。前者は変化点、後者は時系列という役割分担で、意図的な重複と判断し統合していない。

### 7.4 未解決（要判断・contract変更を伴う）

- **snapshot由来factのconfidenceが、package全体の集約値（受理observationの集約）になる。** snapshotにconfidence欄が無いためで、0.65〜0.90のobservationから作られたfactが、集約値によって決定論の信頼度ゲート（0.90）を超えうる。直すにはstate_snapshotのschemaにper-snapshotのconfidenceを足す必要があり、未実施。発生頻度は未測定。
- 画像解析側の `aggregate_observation_quality` の集約方法は変更していない。

## 8. merge時の注意

- 変更ファイル: `events/derived.py`、`schema_validation.py`、`rules/temporal_scope.py`（新規）、`application/round_analyzer.py`、`rules/__init__.py`、`config/valorant_evaluation_rules_v4.json`（誤記1行）、`rounds/builder.py`、`rules/engine.py`、`rules/mock_evaluator.py`、`ai/coach.py`、`tests/cases/TC-005,TC-017/expected_assertions.json`、`tests/unit/test_rule_engine.py`、`tests/integration/test_visual_review_regressions.py`（1パラメータ）、`tests/unit/test_downstream_contract.py`（新規）、docs
- `rounds/builder.py` と `test_visual_review_regressions.py` はvision側が触る可能性がある隣接ファイル。前者は `_state_snapshots` 内1箇所とヘルパー追加のみ、後者は1行。
- 既存contractを変更した（§3.1、§3.2、§6）。schema・registry・評価ロジックのconfig semanticsは未変更（configの変更は文字列の誤記修正1行のみ）。
