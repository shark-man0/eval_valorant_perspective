# 非画像解析パイプライン 進捗と今後の方針

> 2026-10-09 completion handoff update
>
> - completion branch: `external/non-vision-completion`
> - completion開始SHA: `80d0d460b8e3a76d3c181e035c72cd10026f4252`（PR #8 merge commit）
> - 詳細: [non_vision_completion_report.md](non_vision_completion_report.md)
> - 既存の下記記録はPR #8までの履歴として保持する
>

- ブランチ: `external/non-vision-pipeline`
- 依頼書: `EXTERNAL_AI_REQUEST.md`（Priority 1〜6）
- 開始commit: `e05c49543ada515530ed3ba6c6f6438f927aebc5`
- `main` を取り込んだ時点の `main`: `fd099fd938830745c749d1a58e9092565bcd7ed3`（開始時から117コミット先）
- 詳細な作業記録: `docs/external_ai_non_vision_report.md`
- 画像解析側（`hud/` `visual/` `maps/` `application/hud_video_processor.py`）の production code は変更していない

## 1. 現在の状態（要約）

| Priority | 内容 | 状態 |
|---|---|---|
| 1 | 後段pipelineの境界の固定 | 完了（責務表は report §1.2、§7.3） |
| 2 | fixture駆動で後段を単独実行 | 完了（`RoundAnalyzer` 経由のspectator end-to-endテストのみ未作成） |
| 3 | Event / Fact / Ruleの責務整理 | 完了 |
| 4 | 評価ロジックの強化（Excel照合・範囲反映） | 完了 |
| 5 | AI Coachの責務整理（出力検証層） | **未着手** |
| 6 | Clip / Result UI | **実施済み（§2.4。実ウィンドウ全体の検証のみ未実施）** |

## 2. 完了したタスク

コミットは時系列順で、後のコミットは前のコミットに依存する。

| commit | 内容 |
|---|---|
| `d48afe2` | spectator視点の `spike_state` がplayer factへ漏れる問題を修正（`rounds/builder.py`）。後段contractテストを追加 |
| `913f3e0` | 同じfactが複数ruleの決定論labelを生む場合（MOV-02 / AIM-03）に両ruleを出力。低confidenceの決定論factは「評価0件」ではなく明示的な `unscored` |
| `3882671` | 評価基準Excel 2本と `valorant_evaluation_rules_v4.json` の差分整理（44ルール一致、rule変更不要） |
| `9f224ae` | 「AIが見る範囲」（`temporal_context`）を評価ロジックに反映。registryの `v1` 参照を `v2` に誤記修正 |
| `04a1a42` | 派生eventのid安定化、player視点限定、不正な時刻の拒否、factのconfidence引き上げ禁止 |
| `15184a0` | `state_snapshot.source_confidence`（schema追加）。snapshot由来factは元観測のconfidenceを超えない |
| （マージ） | `origin/main` を取り込み（rebaseなし） |

### 2.1 安全契約に関わる修正

1. **spectator視点の漏れを2層で修正**: round package の `state_snapshots`（`d48afe2`）と、派生event `state_snapshot` / `objective_state`（`04a1a42`）。視点で意味が変わる `carried_by_player` / `carried_by_ally` / `not_carried` は `unknown` にする。規則は共有ヘルパー `player_scoped_spike_state` に一本化
2. **低confidenceは明示的な `unscored`**（`913f3e0`）。factが存在し0.90未満なら `low_confidence`、factが無ければ従来どおり扱わない
3. **snapshot由来factのconfidence provenance**（`15184a0`）: package集約値の代わりに、フィールド別のsource confidenceを使う。変更前の合成計測では、高信頼な観測が多い分布で snapshot由来factの 23.1% / 7.4% が、観測 < 0.90 なのに fact ≥ 0.90 だった（最大乖離 0.318）。変更後は全分布で0件。詳細は `docs/external_ai_snapshot_source_confidence.md`
4. **factのconfidenceは、参照するeventの最小confidenceを超えない**（`validate_round_package`）
5. **不正な `time_sec`（NaN・欠落など）を黙って 0.0 にしない**（`DerivedEventInputError`）

### 2.2 contractを変更した点

| 変更 | 根拠 |
|---|---|
| MOV-02 / AIM-03 の両方を出力（既存 `dedup_groups` により AIM-03 が主、MOV-02 が `related_rule_ids`）。TC-005 の主ruleは MOV-02 から AIM-03 に変更 | ユーザー決定 |
| 低confidenceの決定論factは `unscored`（`low_confidence`）。旧テスト2件の期待値を更新 | ユーザー決定 |
| 分析範囲（`temporal_context`）の反映: 採点済み評価の `evidence_range` は範囲内、必要な文脈が無いruleは採点不可 | ユーザー承認 |
| `state_snapshot.source_confidence` を任意で追加（`schema_version` 据え置き） | ユーザー指示 |
| `validate_round_package` が、confidence引き上げを拒否 | P3の一環 |
| event_idの形式が `DERIVED-STATE-<ms>` に変更（保存済み結果のidは変わらない） | P3の一環 |
| configの変更は、文字列の誤記修正1行のみ（`rule_trigger_registry_v1.json` → `v2`） | ユーザー承認 |

### 2.3 追加したテスト

`test_downstream_contract.py`（72件）、`test_temporal_scope.py`（20件）、`test_derived_events.py`（28件）、`test_snapshot_source_confidence.py`（30件）。全38 fixtureが `RoundAnalyzer` + mock を通る確認も含む。`facts/` と `rounds/` を変更前に戻すと、`test_snapshot_source_confidence.py` の30件中23件が失敗することを確認済み（依頼の4件を含む）。

### 2.4 Priority 6（Clip / Result UI）

既存のUIには、件数表示、ラベル・カテゴリ・ラウンドのフィルタ、title / situation / reason / improvement / confidence / missing_information / decision_source / 根拠、クリップ再生ボタンが既にあった。不足を次のとおり補った。

- **Qt非依存のview model**（`ui/view_model.py`）: 件数、フィルタ、時刻表示、クリップ有無。フィルタ判定を `main_window.py` から切り出し（動作は同一。未知のlabelは何も表示しない）
- `EvaluationView` に `fact_refs`（使用したfact）と `time_range`（該当時刻）を追加。保存済みの `fact_refs` / `evidence_range` をそのまま写し、無ければ空 / None（推測しない）
- カードに「該当時刻 / 使用したfact / クリップの有無」を表示
- **clip workflow**: 本物の `ClipService` と本物のpipelineをつなぎ、FFmpegだけをprocess境界でmock。評価の `display_clip` の範囲と、FFmpegに渡る範囲が一致すること（clip生成で時刻が動かない）、`unscored` にクリップが付かないこと等を検証
- テスト: `test_result_view_model.py`（25件）、`test_result_cards_ui.py`（5件、実際の描画メソッドを使う最小ハーネス）、`test_clip_workflow.py`（5件）。検証: `main_window.py` を戻すとカード描画のテストが失敗、`ClipService` の開始時刻を1秒ずらすとclipテストが2件失敗することを確認済み

## 3. 未完了のタスク

### 3.1 Priority 5: AI Coach検証層

1. **評価のconfidenceが、引用factのconfidenceを超えうる。** `validate_ai_output` は評価confidenceと `fact_refs` のfact confidenceの関係を検証しない。fixtureの採点済み評価（`fact_refs` あり）31件中2件（TC-014、TC-016）で評価0.98が引用factの最小0.90を超えていた。mockは評価confidenceの上限にpackage集約値を使っている（`mock_evaluator._confidence`）
2. **範囲違反・文脈不足の扱い**: 現在は `ContractValidationError`（修復ループ対象外）。実モデルで起きたときに、修復するか、`unscored` に降格するか未決定
3. **`unscored` の重複表示**: 同一factの MOV-02 / AIM-03 が `unscored` では集約されず2件別々に出る
4. 出力検証の追加項目の洗い出し（timestampやlabelをAIが変えていないこと等）とテスト整備

### 3.2 Priority 6: 残り

- 実ウィンドウ（`MainWindow`）全体の検証。このサンドボックスでは `QAudioOutput` の生成でsegfaultするため構築できない（オーディオサーバが無いコンテナの制約で、変更前のコミットでも同じ）。`test_ui_smoke.py` / `test_main.py` はPySide6が無ければskip、有ればこの環境ではクラッシュするため未実行。Windows CIでの実行結果を確認する必要がある
- `_play_clip`（クリップ再生）のテスト、元動画の該当時刻へのジャンプ機能（未実装）

### 3.3 その他

- `RoundAnalyzer` 経由のspectator end-to-endテスト
- `temporal_context` の未反映項目: `requires_round_timeline`、`uses_whole_match_aggregation`、`display_clip_strategy`、`temporal_tolerance_policy`、`automation_policy`
- 入力の絞り込み（`scope_round_package`）は、実測した38 fixtureで一度も働かない（どのケースにもラウンド全体が必要なruleがあるため）。実効化にはAI呼び出しを窓つき群と全体群に分ける必要があり、API呼び出し回数が増える
- 小さな残件: zone factはpackage集約値を上限として使う既存挙動（下げる方向のみ）、同一状態が続くsnapshotの間引きで後続の高confidenceを記録しない、`hp` / `armor` に `source_confidence` が無い（HPは別経路）

### 3.4 画像解析側に依存して完了できない事項

- 実録画でのconfidence過大評価の頻度（生のobservationがリポジトリに無く、合成分布でしか計測できていない）
- 実動画E2E、実モデル（OpenAI API）での検証

## 4. 今後の方針

### 4.1 進め方

1. 安全契約（証拠不足は `unscored`、推測でfact化しない、deterministic labelをAIが上書きしない、confidenceとprovenanceを失わない）を最優先する
2. **contractを変える変更は、先にユーザーへ方針を確認する**。変更するときは (a) 再現と変更前の計測、(b) テスト先行、(c) 実装を戻したときにテストが落ちるネガティブコントロール、(d) 既存fixture / schema / 後方互換の確認、(e) docsへの記録、をそろえる
3. 画像解析側の production code は変更しない。問題を見つけたら `docs/external_ai_vision_findings.md` に記録する
4. 各タスクの終わりに、コミット・パッチ・docsを更新する。`main` が進んだら、`main` をマージして衝突を確認する（rebaseしない）

### 4.2 順序

1. **Priority 5**（安全契約に最も近い）
   - 評価confidenceの上限化: `evaluation.confidence ≤ 引用factの最小confidence` を出力検証に追加し、mockの上限もpackage集約値から引用factに変える。実モデルの出力が通らなくなる可能性があるため、**修復ループで再生成するか、決定論的に引き下げるか**を実装前に確認する
   - 範囲違反・文脈不足の扱い（修復 / `unscored` への降格）を同じ方針で決める
   - `unscored` の重複表示の扱いを決める
2. ~~**Priority 6**~~: 実施済み（§2.4）。残りは §3.2
3. 残件（§3.3）と、`RoundAnalyzer` 経由のspectator end-to-endテスト
4. 最終成果物の整備（依頼書の「最終成果物」の各項目を `docs/external_ai_non_vision_report.md` に反映）

### 4.3 判断が必要になる点

| 点 | 論点 |
|---|---|
| 評価confidenceの上限超過への対処 | 修復ループで再生成するか、決定論的に引き下げるか |
| 範囲違反・文脈不足への対処 | 修復するか、`unscored` に降格するか |
| 同一factの `unscored` | 統合するか、別々のまま出すか |
| 入力の絞り込みの実効化 | API呼び出し回数を増やすか |

## 5. merge方針

### 5.1 現状の確認

- `origin/main` は `fd099fd`。開始時の `e05c495` から117コミット進み、PR #3〜#6 など（Windows release、pytest修正、security review、user documentation、CI）が取り込まれている
- 使い捨てworktreeでの試行マージは**衝突0**。両側が変更したファイルは `ai/coach.py` と `rounds/builder.py` の2つで、自動マージで解決した
- `main` 側の `rounds/builder.py` の変更はラウンド境界の扱いで、`_state_snapshots` とconfidence生成には触れていない。`hud/` 側は `roi_confidence` に新キーを足したが、`round_timer_value` と `hud_confidence` の意味は変えていない
- ブランチは `origin/main` と、私の66ファイル分だけ異なる。`hud/` `visual/` `maps/` は含まない

### 5.2 方針

1. **`main` をブランチへマージする（rebaseしない）**。他の `external/*` ブランチも「Merge main into …」の運用だったことに合わせる。報告済みのcommit SHAを保てる
2. **pushするのは `external/non-vision-pipeline` ブランチのみ**。`main` へは直接pushしない。force pushしない
3. `main` へは**Pull Requestでmerge commitとして取り込む**ことを推奨する（squashしない）。タスクごとのcommitを残すと、問題が出たときに戻しやすい
4. `main` がさらに進んだ場合は、同じ手順で `main` を再度マージし、§5.3 の確認をやり直す

### 5.3 マージ後の確認結果（この環境、1CPU、PySide6未導入）

- 全119テストファイル: 1,342 passed / 1 failed / 7 skipped。失敗1件は `test_real_ffmpeg` の `PySide6` import で、`origin/main` 単独でも同じ。skip 7件はUI関連
- `tests/validate_dataset.py`: OK（38ケース）
- `ruff check src tests scripts/e2e`（CIと同じ範囲）: 指摘0
- `mypy src/valorant_ai_coach`: 22件。`origin/main` 単独と同数・同内容でPySide6未導入に起因。マージで増えたエラーなし
- **未確認**: GitHub Actions上の実行結果、カバレッジ75%以上のゲート

pushすると Basic CI と Windows verification が起動する（Windows release はタグ `v*` か手動のときのみ）。

### 5.4 レビューと取り込みの注意

- レビューは §2 の順序（安全修正 → contract変更 → 範囲反映 → schema変更）が読みやすい。ただしコミットは順に依存しており、単独のrevertを検証していない。戻す場合は新しいコミットから順に戻す
- **画像解析側と衝突しうるファイル**: `rounds/builder.py`、`ai/coach.py`（`main` 側でも変更済み）、`schemas/round_package_schema_v2.json`、`tests/cases/TC-*/input.json`（38ファイル、409行追加のみ）
- **画像解析側が守るべき前提**: `source_confidence` は次の意味に依存している。変更するときは、`docs/external_ai_snapshot_source_confidence.md` §2 を再確認する必要がある
  - `quality.hud_confidence` は、そのobservationの受理されたリーダーのconfidenceの最小値である
  - `roi_confidence.round_timer_value` は、タイマーを受理したときだけ非0になる予約済みの値レベルscoreである
  - 視覚observationの `spatial.confidence` と `quality.visual_confidence`、resolverの `zone_confidence` が、それぞれの源の信頼度である
- 画像解析側が追加するfixtureに `source_confidence` が無いと、snapshot由来factは0.0になる
- **保存済みの実データ**: 移行していない。`source_confidence` の無い古いpackageを再解析すると、snapshot由来factは0.0になり、決定論gateを通らない（`PEEK-04` は `unscored`）。保存済みの過去の評価結果自体は変わらない。測定されていないconfidenceを黙って付与するフォールバックは入れていない

## 6. 参照ドキュメント

| ドキュメント | 内容 |
|---|---|
| `docs/external_ai_non_vision_report.md` | 作業記録（変更・決定・テスト・merge注意） |
| `docs/external_ai_snapshot_source_confidence.md` | snapshotのconfidence provenance（設計・計測・後方互換） |
| `docs/external_ai_rules_criteria_diff.md` | Excelと `rules_v4.json` の差分整理 |
| `docs/external_ai_vision_findings.md` | 画像解析側への所見 |
| `docs/external_ai_snapshot_confidence_measurement_{before,after}.json` | 計測の生データ |
| `scripts/measure_snapshot_fact_confidence.py` | 計測スクリプト（変更前後で同じ入力） |
| `scripts/migrate_fixture_snapshot_source_confidence.py` | 合成fixtureの移行（実データには使用不可） |
