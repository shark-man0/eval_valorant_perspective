# 評価エンジンの未接続機能の整備（#31・#25・#26）

起点は main `9c76fd3`（2026-11-13）。P0の44ルール認識器（#32、PR #155）とは作業範囲を分けている。この変更はFactを生成せず、Factを受け取る口だけを用意した。

## 1. 棚卸しの結果

| # | 対象 | 変更前 | 変更後 | 状態 |
|---|---|---|---|---|
| 1 | 共通タイムライン → 評価エンジン | 空のパッケージでAIM-02を1回評価する確認のみ | Round分割 → Round Package → `RoundAnalyzer` → `MatchAggregator` → SQLite保存 → GUIの読み出し・JSON/Markdownレポート | 接続済み |
| 2 | 評価の画面表示と保存の整合 | 境界未確定Roundを、実行中の集計は「評価済み・0件」、保存後の集計は「未評価」と扱っていた | どちらも「未評価」に統一 | 修正済み |
| 3 | `aggregate_repeated_occurrences` | 実行時の参照なし | Match集計の `occurrence_summaries`（件数・Round・評価ID・根拠時刻）とGUI要約 | 接続済み |
| 4 | `summary_required_if_occurrences_at_least` | 実行時の参照なし | `summary_required` フラグ。要約文は `null`（承認待ち） | 接続済み |
| 5 | `requires_round_timeline` | UI表示のみ | `RoundTimelineGate`。既定は報告のみで評価は不変 | 接続済み（ゲート有効化は承認待ち） |
| 6 | `uses_whole_match_aggregation` | 報告のみ | #25の分類で `match_aggregated` として使用 | 接続済み |
| 7 | 暫定Roundの部分評価（#25） | 常に評価0件 | 境界非依存17ルールの分類表とオプトイン実装。保存・再開・集計まで対応 | 実装済み（有効化は承認待ち） |
| 8 | `display_clip_strategy` | 参照なし | 変更なし | 承認待ち（§3-3） |
| 9 | `temporal_tolerance_policy` / `test_tolerance_seconds` | テストの整合確認のみ | 変更なし | 現状維持を推奨（§3-4） |
| 10 | `automation_policy` | registryの `label_mode` が実際の決定元 | 変更なし | 現状維持を推奨（§3-5） |
| 11 | Match全体のGOOD/IMPROVE・総合スコア（#26） | なし | 変更なし | 見送りを推奨（§3-6） |

未接続だった11項目のうち、7項目を接続または修正した（うち2項目は有効化に承認が必要）。ポリシー15項目のうち、実行時に誰も読まない項目は9から6に減った（`tests/unit/test_temporal_policy_contract.py` の `RUNTIME_USERS` で固定）。

## 2. 実装の内容

### 2.1 共通タイムラインの評価接続（`application/timeline_evaluation.py`）

```sh
python -m valorant_ai_coach.application.timeline_evaluation evaluate \
  --timeline OUT/timeline_PRIVATE.json --output NEW_DIR --match-id M-dev-001 \
  [--database PRIVATE/app.db] [--source-video VIDEO]
```

- 各秒の `round_number` 候補でRoundを区切る。Round *n* の窓は、*n* を持つ最初の秒から最後の秒まで。窓の中で *n* を持たない秒は `missing_intervals` に入れ、隣のRoundで埋めない。
- 番号が入り組んだ場合（後のRoundが前のRoundの終わりより先に現れる）は、どちらかを選ばずに `segmentation_conflicts` として報告し、Match集計の重なり検出にも渡す。
- 境界はすべて `provisional`（`formal_event_id` なし）。既存のPractical契約どおり、`timeline_completeness` は0とし、実測した割合はレポートの `measured_share_with_round_number` に出す。
- 既定ではFactを作らないので、評価は0件、Roundは「未評価」になる。P0の生成器は `FactProvider` で渡せる。Round窓の外の時刻を返すと拒否する。
- `--database` を付けると、GUIが読むのと同じ行に保存し、`aggregate_saved_match` で読み直して実行中の集計と照合する。
- `check_consistency` が、Roundごとの出力、Round別件数、ルール別件数、Round番号、窓、保存後の集計の一致を確かめる。

### 2.2 `RoundTimelineGate`（#31 §6-1）

`RoundAnalyzer(round_timeline_gate=...)` で使う。`report_only`（既定）は出力を変えず、影響を受ける評価を `RoundAnalysis.timeline_gate` に記録する。`unscore_incomplete` は、`requires_round_timeline` のルールのGOOD/IMPROVEを、Round時間軸が完全でないときにUNSCOREDにする（理由コード `missing_required_fact`、`missing_information` に時間軸の状態、confidenceは変えない）。有効にすると設定の指紋に入るので、既存の再開ジョブとは混ざらない。

### 2.3 繰り返しの集約（#31 §6-6）

Match集計に `occurrence_summaries` を追加した。対象は `aggregate_repeated_occurrences` が真の6ルールだけ。件数（ラベル別）、閾値、`summary_required`、Round番号、評価ID、根拠の開始時刻を持つ。文章（`text`）は `null`、`text_status` は `requires_approval`。GUIのMatch要約に「繰り返し集約の対象」として件数を表示する。

### 2.4 暫定Roundの部分評価（#25）

`ProvisionalAdmissionTable` が44ルールを分類する。次のどれかに当たるルールは対象外（理由つき）。

- levelがmicro/local以外、イベント窓なし
- `requires_round_timeline` / `requires_previous_round_context` / match level
- Round全体で決まるFact（side、numbers_state、残り時間、Spike、購入、clutch等）を条件や補助に使う
- Roundの局面そのもの（round_start、buy_phase、site_state等）をトリガーにする

対象は17ルール：AIM-02/03/04、DEC-03、INFO-02/04、MOV-01/02/03/04、PEEK-02/04/05、POS-01/03、UTL-01、WPN-01。

`ProvisionalEvaluationPolicy(enabled=True)` を `RoundAnalyzer` に渡したときだけ、境界未確定Roundで次をすべて満たす候補を評価する。

1. ルールが対象17件に入っている
2. ピボットイベントの窓がある（Round全体へのフォールバックではない）
3. 窓が観測の欠落区間と重ならない
4. 決定論的判定が引用するFactがすべて窓の中にあり、時刻を持つ

保存時はチェックポイントに `provisional_evaluation: boundary_independent_v1` を記録する。この印があり、保存された評価がすべて対象ルールのときだけ、保存後の集計が受け入れる。印がなければ従来どおり契約違反として拒否する。

## 3. 承認が必要な項目

### 3-1. 暫定Roundの部分評価を有効にするか（#25）

- 根拠: 合成fixture 38件を境界未確定に変えて比べた。

| 指標 | 現状（無効） | 有効にした場合 |
|---|---:|---:|
| 暫定Roundの評価件数 | 0 | 16（確定Roundでは36） |
| うちGOOD/IMPROVE | 0 | 13（確定Roundでは32） |
| 確定Roundと異なるラベル | – | 0 |
| 対象ルールの評価のうち出力されたもの | – | 16/16 |

- 変更案: 当面は無効のまま、P0のFact生成器が実動画で境界非依存の観測を出せるようになった時点で、DEVELOPMENTの試合だけで有効化して比較する。
- 影響: 有効化は評価の意味の変更（暫定Roundの採点）にあたる。Strict Modeの意味は変わらない。

### 3-2. Round時間軸ゲートを有効にするか（#31 §6-1）

- 根拠: 同じ38件で時間軸を不完全（完全性0.6、欠落1秒）にすると、`unscore_incomplete` ではGOOD/IMPROVEが32件から14件に減る（18件がUNSCORED）。`report_only` では出力は38件すべて不変だった。
- 変更案: `report_only` のまま運用し、どの程度の欠落で拒否するかの閾値を決めてから有効化する。今の実装は「完全でなければすべて」なので、そのまま有効にすると影響が大きい。

### 3-3. `display_clip_strategy` の構造化

- 変更案: ルールJSONに構造化フィールド（例：`clip_length_seconds: [8, 15]`、`max_clips: 3`）を人が追加し、自然言語からは変換しない。変換すると仕様を作ってしまうため、今回は実装していない。

### 3-4. `temporal_tolerance_policy`

- 推奨: テスト用の許容値として現状維持。実行時の許容（0.05秒）と根拠の±0.75秒は別の概念として残す。

### 3-5. `automation_policy`

- 推奨: registryの `label_mode` を正とし、整合テストで固定する現状を維持。

### 3-6. Match全体の判定・総合スコア（#26）

- 推奨: 追加しない。Match集計は件数・分類・完全性・繰り返し集約までとする。
- 理由: AIM-01の基準は人の総合判断で、回数からは決まらない。共通タイムラインの境界は開発候補で、Match全体の完全性を `verified_complete` にできる試合がまだない。
- 追加する場合に決めること: 判定主体（決定論かLLMか）、入力するFact、時刻とRoundの文脈、confidence、UNSCOREDの条件、引用、UIと履歴の保存形式。

## 4. 検証

- 追加テスト: `test_policy_runtime.py`（16件）、`test_timeline_evaluation_bridge.py`（10件）
- 既存テストの期待値の変更: `test_practical_evaluation_integration.py` の1件（§1の2番。実行中の集計を保存後の集計に合わせた）
- `test_temporal_policy_contract.py` の `RUNTIME_USERS` を更新した
- 実動画の共通タイムラインでの実行: 未実施（非公開の出力がこの環境にないため）。Mac上で上記コマンドを `timeline_PRIVATE.json` に対して実行すれば測れる。
