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

## 5. 2026-11-17 承認後の対応

統括が実装方針を承認した。決定と対応は次のとおり。

| 項目 | 決定 | 対応 |
|---|---|---|
| 暫定Roundの部分評価（#25） | 既定無効を維持 | 変更なし |
| Round時間軸ゲート | 報告のみ、確実に実行 | `RoundAnalyzer` が常に報告モードで実行する。Match集計（実行中・保存後・GUI・JSON出力）は保存済みの行から同じ報告を再計算する |
| `display_clip_strategy` | 構造化フィールドを実装 | 44ルールに `display_clip_policy` を追加した。秒数は記述から人が転記し、記述と一致しなければ読み込みで拒否する。Match集計の `display_clip_report` でクリップ長を測る（クリップは変えない） |
| Match全体の総合スコア | 追加しない | 変更なし |
| Round区間の重複 | 防止 | 番号が入り組んだ秒は両方のRoundから除き、報告する。窓は半開区間 |
| Fact/Eventの二重所属 | 防止 | 半開区間で1つのRoundにだけ属させ、同じIDが2つのRoundに入ると拒否する |
| 正式解析結果の上書き | 防止 | 開発用評価は `DEV-` で始まるmatch_idだけに保存する。既存の正式解析は上書きを拒否し、開発用評価の置き換えも明示指定を必要とする |
| #155との接続 | 進める | `DerivedSampleFactProvider` が `development_readiness.derive` の出力を受け取る。confidenceは0.0、`development_only` を付けるため採点には使われない。レポートには本番のRuleSelectorが拾った候補ルール数を出す |

### 5.1 実動画由来の共通タイムラインでの検証

対象は、共通タイムライン（`development_application_timeline_v1`）が出力済みの2試合（C003：personal_20261024_003、DEV2：personal_20261108_003）。#155の生成器は、同じ試合のHUD切り出しアーカイブ（36試合分のうち該当2件）から実行した。

| 指標 | C003 | DEV2 |
|---|---:|---:|
| 秒数 | 2,360 | 2,052 |
| 区切ったRound | 24 | 21 |
| Roundに属さない秒 | 824 | 624 |
| 区間の衝突 | 0 | 0 |
| #155のサンプル | 472 | 411 |
| 候補になったルール（種類） | 10 | 9 |
| 評価件数（GOOD/IMPROVE/UNSCORED） | 0/0/0 | 0/0/0 |
| 整合性の問題 | 0 | 0 |

- 評価が0件なのは、境界が暫定のためRoundを「未評価」にしているから（#25は既定無効）。
- GUI（オフスクリーン描画）で2試合を開き、暫定区間24件とMatch集計の表示を確認した。
- GUIのレポート出力（JSON）と、ブリッジのレポートのMatch集計は、Round・ルール・評価・繰り返し集約・ゲート報告・クリップ報告・完全性のすべてで一致した。
- 処理時間はC003で約17秒、最大メモリは約3.3GB。

### 5.2 構造化した表示クリップの確認

- 合成fixture 38件：クリップ32本のうち26本が範囲内、6本が下限未満（POS-04、TEAM-02、OBJ-02、OBJ-03、ROLE-06。いずれも下限15秒のルール）。
- 設定の食い違い：ECO-01、ECO-02、ADV-06、ADV-07は `suggested_clip_window_seconds`（合計28秒）が記述の上限（20秒または25秒）を超える。どちらを正とするかは判断が必要なため、値は変えていない。

## 6. 2026-11-17 統合前の最終修正

| 項目 | 決定 | 対応 |
|---|---|---|
| 表示クリップ長 | ECO-01・ECO-02・ADV-07は10〜20秒、ADV-06は10〜25秒を正とする | `display_clip_policy.max_seconds` を超える表示クリップを、`RoundAnalyzer` が評価後に上限まで短くする。根拠区間は必ずクリップ内に残し、前後の文脈を同じ比率で縮める |
| 解析範囲と表示クリップの分離 | 解析に必要な情報は削減しない | `suggested_clip_window_seconds`（28秒）、根拠区間、解析範囲、フレームは変えない。変わるのは `display_clip` だけで、評価IDも変わらない |
| 正式Factと開発用候補 | 区別する | `dev-` のIDまたは `qualification: development_only` を持つFact/Event（と、それに由来するFact）は、ルール選択・Rule Engine・coach・保存のどれにも入らない。レポートにはRoundごとに正式・開発用候補の件数を出す |
| 部分評価・時間軸ゲート・総合スコア | 現状維持 | 変更なし |

実動画（C003・DEV2）の再実行では、Round数、Roundに属さない秒、区間の衝突、Roundの扱い、評価件数、候補ルール数がすべて前回と一致した。保存されたRound Package 45件に、開発用候補は0件だった（レポート上の開発用候補はC003でEvent 706・Fact 1,682、DEV2でEvent 627・Fact 1,556）。
