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

## 3. 要判断事項（未変更）

### 3.1 なし（上記2.1は安全契約に直接反するため修正済み）

### 3.2 同一factが複数ruleの決定論的labelを生む（TC-005 / TC-017）

- 現象: `first_shot_stationary` が MOV-02 と AIM-03 の両方で決定論的labelを生む。TC-017では両方 `improve`、TC-005では両方 `good`。MockEvaluatorは片方のみ出力するため、`RoundAnalyzer._validate_deterministic_authority` が「決定論的評価が出力から欠落」で例外にする。
- 実コーチ（`ai/coach.py`）は全decisionを出力にbindする実装に見えるため、**mockと実コーチで挙動が食い違っている**可能性が高い（実コーチの実行は未確認）。
- 直し方によって契約が変わるため、未変更:
  - A. mock / 実コーチとも両ruleを出力する → TC-005/017 の `expected_assertions.json` 変更が必要
  - B. 二つのruleの関係（排他・統合）を config 側で定義する → `deterministic_rule_engine_v1.json` 等の変更が必要
  - C. mockで `related_rule_ids` に寄せる → `test_dataset_contract.py` が `allowed_related_rule_ids=[]` を要求しており既存テストが落ちる
- 評価基準Excelで MOV-02 / AIM-03 の定義をどう分けているかの確認が先に必要（未実施）。

## 4. 未実施（次の作業）

- Priority 2: 依頼の6ケースのうち、1〜4は既存 `TC-*` で概ねカバー（good: TC-006, improve: TC-017※, unscored: TC-025, authority: `test_round_analysis.py`）。6（spectator混入）はbuilder層で追加済み、`RoundAnalyzer` 経由のend-to-endは未作成。5（低confidence）は §4.1 の観察があり、仕様判断が必要。
- Priority 3: `DerivedEventBuilder` のevent_idが入力indexに依存する点（入力順序・間引きで変わる）、confidence propagationの精査
- Priority 4: Excel2本と `valorant_evaluation_rules_v4.json` の差分整理
- Priority 5/6: AI Coach検証層、UI（PySide6未導入のため smoke 未実行）、ClipService
- 全体 `pytest` / `ruff check .` / `mypy src` の最終結果

### 4.1 低confidenceの扱い（TC-006 を改変して `RoundAnalyzer` + mock で観察。コードは未変更）

| 改変 | 候補rule | 決定論decision | 評価出力 |
|---|---|---|---|
| `deterministic_facts` のconfidenceのみ0.3 | 7件（変化なし） | なし | **0件**（`unscored` ではない） |
| `events` のconfidenceのみ0.3 | 7件 | AIM-02 | AIM-02 `good`（維持） |
| `observation_quality` のみ0.3 | 7件 | AIM-02 | AIM-02 `good`（維持） |

- (a) factの証拠が弱いとき、候補ruleが残るのに `unscored` ではなく「評価なし」になる。false positiveは作らないが、依頼の「`unscored` を正常系として扱う」とどちらが正しいか要判断。
- (b) 入力済みfactのconfidenceが、provenanceで参照するeventのconfidenceより高くても、そのまま採用される。実運用の `FactBuilder` 由来factは元eventのconfidenceから導出されるため、これはfixtureのように事前計算済みfactを渡した場合の挙動の可能性が高い。本番経路で事前計算済みfactが渡る箇所があるか未確認（`rounds/builder.py` の `_owned_hp_facts` / `_shared_timer_facts` は直接factを生成する）。

## 5. merge時の注意

- 変更ファイル: `src/valorant_ai_coach/rounds/builder.py`（+14/-1）、`tests/unit/test_downstream_contract.py`（新規）、本docs
- `rounds/builder.py` は vision側が触る可能性がある隣接ファイル。変更箇所は `_state_snapshots` 内の1箇所と、モジュール先頭付近のヘルパー追加のみ。
- 既存contract（schema / config / expected assertions）は変更していない。
