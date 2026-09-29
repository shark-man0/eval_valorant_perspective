# E2E Validation Pack v3 導入状況（2026-09-29）

## 2026-09-30: Windowsローカル実動画 / Git共有レポート

`run_e2e_windows.ps1` と薄い `scripts/e2e/run_dataset_case.py` を追加。
既存の実動画runner・trace adapter・正本evaluatorを順に呼び出す。
動画SHA、manifest、packの識別情報が不一致ならAnalyzerは起動しない。
詳細データはignoredの `outputs/e2e/<id>/<run-id>/`、共有用の許可項目だけを
`e2e_reports/<id>/` に保存する。画像は明示指定時のみ、最大10枚のHUD crop。
runnerによるcommit/push、動画転送、有料API呼び出しは行わない。

検証結果: **428 passed / 3 skipped**。既存407件と追加21件が通過。
skipは既存の実動画アンカーテスト1件と、このMacにPowerShellがないための
PowerShell実行テスト2件。Ruff成功、mypyは72ソースファイル成功。
正本evaluatorと共有集計の一致は空のSchema適合traceで検証しており、
これを実動画の認識成功とは扱わない。今回、全動画解析は再実行していない。
Windows実機でのbootstrap・PowerShell動作・exeビルドは未確認。
従来の実動画ベースライン65不一致は未解決のまま。

設定・manifest・privacy・履歴・コマンドは [WINDOWS_E2E.md](WINDOWS_E2E.md) を参照。

## 完了範囲

- ZIPをプロジェクトの隣の `valorant_e2e_validation_pack_v3/` に展開。
  GT・参照画像・期待値は本番の `src/` / `config/` に取り込んでいない。
- 付属 `validate_pack.py --project-root <project>/src` 成功。
  GT/negative/inputの付属Schema検証、生成assertionsの一致、75枚の参照画像と
  PTS sidecarの内部整合性、synthetic参照テスト、meta evaluatorを実行。
- `tests/integration/test_e2e_validation_pack_v3.py` を追加。
  既存pytestからパック検証を呼び、本番コードのGT参照も静的検査する。
  別配置の場合は環境変数 `VALORANT_E2E_PACK` に展開先を指定する。
  パック不在の場合はコーパステストを明示的にskipし、静的検査は実行する。

## 元動画確認・初回ベースライン結果

指定動画 `Valorant_09-25-2026_0-37-29-379.mp4` はユーザーからDesktopにあると
回答を受け、再検索で確認できた。SHA-256・PTS sidecar・3音声トラックは一致。
GTから作ったoracleを本体Analyzerの出力として扱う処理は追加していない。

本体ClipServiceで0〜2秒のクリップを作り、付属media transport validatorで
音声3トラック保持を確認済み。これはコーチ根拠クリップではなく輸送検証用。

実動画→HUD→Visual→Map→Round Package→trace→evaluatorを実行した。
**初回ベースラインはFAIL（65件の不一致）**。実行開始後の修正を取り込んだ
全動画E2E再実行はまだ完了していない。ベースラインを最新コードの精度と混同しない。

trace adapterと実動画実行・評価コマンドを `tests/e2e/` に追加。
本体の変更は実PTS抽出、購入フェーズの古い戦闘レポートによる死亡抑制、
指定alias overlayの3件統合。Windows起動手順・exe構成は変更していない。
過去の時刻計算・旧HUD読取によるresumeを避けるためresume contractを7へ更新。

元動画の先頭フレーム（正解画像ではない）から既存校正ツールで
`../outputs/e2e_source_hud_profile/` を生成し実行に使用。同一動画での校正であり、
独立データでの精度証明ではない。初回実行時のprofileはアンカーのみ。
その後、数字readerと日本語文字reader設定を追加したが、状態・アイコンreader等は不足している。

### 実動画の内訳

| 層 | 初回ベースライン |
| --- | --- |
| HUD | 4,634 observations。unknown 3,397、expanded_tactical_map 1,234、remote_control_view 3 |
| 行動イベント | HUD由来0、Visual由来0 |
| Visual | 4,634 observations、確定候補0 |
| Map / Zone | 4,634件すべてzone_id=null。map_definition_unresolved |
| Round Package | 1件（期待は2ラウンド）。期間0.086003〜162.452669秒 |
| trace events | 136件、すべてシステムのstate_snapshot。行動イベントではない |
| trace Schema | 付属Schemaに適合 |
| E2E assertions | 65件の不一致。下記JSONに全件保存 |
| Negative assertions | 20件を実行、違反0。ただしイベント欠落が多く、安全性の実証とは扱わない |
| 内容不連続 | temporal_featuresが0件。境界を越える特徴がないだけで、実検出成功ではない |

結果ファイルはプロジェクト隣の `outputs/e2e_real_run_v3/`:

- `raw_processing.json`: Analyzerからの加工前出力
- `trace_current/e2e_trace.json`: 最新の検証用変換器によるtrace
- `evaluation_report.json`: 不一致一覧・カテゴリ集計

不一致の内訳: point欠落5、state coverage12、state開始境界1、ownership5、
snapshot欠落20、snapshot値10、derived zone欠落3、visual observation欠落3、
event count6。分母が異なるチェックを合算した「精度%」は算出しない。

### 原因と実施した修正

1. フレーム番号/FPSによる時刻推定を、ffprobeの表示順PTSへ置換。
   元動画10,259フレーム、先頭0.036003秒を確認。近接抽出は順次デコード。
2. 前ラウンドの戦闘レポートが購入フェーズに残っても死亡を生成しない。
3. Visualのenemy_spotted/lost sourceを `world` から契約の `world_view` へ統一。
4. 指定された日本語alias3件を既存calloutへ追加。形状・topology・confidence capは維持。
5. 部分的なAstra形状やbuy gridだけで、独立したHUDアンカーの証拠を抑止しない。
   観戦・remoteの独立した疑いは引き続き保守的に扱う。
6. 画面のエッジ密度だけではexpanded tactical mapを確定せず候補に留める。
   確定には設定したUI detectorが必要。これによる感度低下も未解決事項として扱う。
7. Map位置を本人へ帰属できない視点では高価なSIFT処理を行わない。
   初回プロセスのスタック採取でもSIFTが処理負荷として確認された。
8. OCRへ任意の白文字前処理とreader内部ROI設定を追加。受理閾値は変更しない。
   実フレームで0:04の読取改善を確認。HP100も文字候補は出たがconfidence不足で
   受理されず、正解に見えるという理由だけでconfidenceを上げていない。
9. trace変換がRound Packageの観戦汚染を消さない回帰テスト、confidence異常検査、
   保存済みrawから再変換する経路を追加。
10. 設定可能な文字OCRを追加。language / executable / tessdata_dirを指定可能。
    指定言語不足はunknownと診断情報を返す。Unicodeと最小word confidenceを保持する。
    数字・文字とも不正/非有限/範囲外confidenceは部分的な文字列を採用せず全体を棄却する。
11. `timer_mmss` のOCRでコロン欠落や不正秒表記を棄却する。
    実画像で `1:14` が `1714` と読まれた例を、1714秒として流さない。
12. 途中のレターボックスや位置/サイズ不一致では、アンカー数が少なくても
    過去の校正を失効させる。アンカーが再確認されるまではunknownを維持する。

### 続行時の実動画HUDプローブ

`tests/e2e/diagnose_hud_video.py` を追加し、元動画から30秒間隔で6枚を再抽出した。
時刻は実PTS。GTや参照画像を読まず、各フレームを独立に校正・解析する。
間隔の離れた画像から連続イベントを捏造しないため、これはE2E合否テストではない。
出力は `../outputs/e2e_hud_uniform_probes/hud_diagnostics.json`。

- 0.036003秒: live_first_person。HP100（OCR confidence 0.954）、敵スコア1
  （0.931）、タイマー0:04（0.967）を本体Observationでも受理。
- 残り5枚: insufficient_anchorsのためunknown。読取プローブでは複数画像のHPを
  confidence約0.95で読めたが、校正未成立のObservationへ採用していない。
- 日本語: `tesseract_language_missing:jpn` を実環境で確認。
- full-ROIの参照アンカーは背景・数字・アイコン変化に弱い。安定したアンカーの選定と
  状態別認識の改善が必要。受理閾値を下げて合格扱いにはしていない。

### 未完了・契約上の注意

- HUDのHP/Armor/Ammo/Score/日本語ラベル/Agent UI認識profileは未完成。
  今回の環境のTesseract言語データはeng/osd/snumのみで、日本語データはない。
- 2ラウンドの境界・本人死亡・所有者の実認識、Map同定/校正、実動画のshotは未合格。
- 既知の内容不連続をGT抜きで検出し、全時間特徴を遮断する処理は未完成。
- 中間表現が破棄した観戦HUD値やtimer表示文字列はtraceで推測復元しない。
  必要なら本体Schemaを変えず、view-owned audit sidecarとして保持する設計が必要。
- 非exhaustive区間の未ラベルイベントを一律FPとは扱わない。
  戦術マップ過剰判定の症状は確認したが、未ラベル区間全体のFP数は確定していない。
- supplied shot fixtureには武器名がない発砲例があり、本体では候補数2/1/0/0を確認。
  unknown weaponを確定イベントへ昇格させない既存安全条件を優先した。
- AI Coach・Semantic API呼び出しは今回行っていない。
- Spike設置/解除、self kill/multikill、他Agent remote、統計的confidence校正などは
  付属gap manifestどおり別録画が必要。Windows実行・exe実ビルドは未検証。

### 主な変更ファイル

- `src/valorant_ai_coach/video/service.py`
- `src/valorant_ai_coach/application/pipeline.py`
- `src/valorant_ai_coach/hud/{analyzers,readers,templates,temporal}.py`
- `src/valorant_ai_coach/visual/{core,runtime}.py`
- `config/map_zone_v3/config/maps/summit_callout_registry_v3.json`
- `tests/e2e/{run_real_video,trace_adapter,evaluate_saved_trace,test_trace_adapter}.py`
- `tests/e2e/diagnose_hud_video.py`
- `tests/integration/test_e2e_validation_pack_v3.py`, `test_e2e_shot_contract.py`
- `tests/unit/test_video_pts.py`, `test_hud_templates.py`, `test_hud_temporal_regressions.py`,
  `test_map_resolver_v3.py`, `test_visual_core_v2.py`
- `README.md`, `config/hud_templates.example.json`
- この報告書と `../outputs/e2e_source_hud_profile/` の実験用設定

## 検証結果の解釈と仕様上の注意

### 精査後の修正

- Visualの観測間隔>0.5秒、観戦・remote・buy menuで交戦終了時刻もリセット。
  peek/utility/siteの抑制履歴・前フレーム・alignment confidenceも区間内に限定。
  通常の連続再交戦は維持し、途切れを越える再交戦を防ぐ4ケースを追加。
- 標準タイマー経路にも文字列の分:秒検証を適用。`1714`、`1:4`、`1:99`等を棄却し、
  専用readerが返した数値秒は維持。通常/異常7ケースを追加。
- 校正profileへanchor maskを追加。`--anchor-regions` JSONから動的領域を除外できる。
  閾値0.90は維持し、マスクの欠損/サイズ不一致/情報不足、非有限NCCは不一致とする。
  maskの実データもfingerprintへ含める。動的画素置換、位置ズレ、blank、破損を検証。
- 同一元動画の目視から選定した実験用領域は
  `../outputs/e2e_anchor_regions_experimental.json`、profileは
  `../outputs/e2e_masked_hud_profile/`。元profileは保持し、標準設定へ自動採用しない。
  均等6枚で幾何校正成立は1枚から3枚（0/60/120秒付近）へ改善したが、独立精度ではない。
- 初期実験では特殊視点の120秒フレームもliveと判定されたため、マスク付きanchorの
  一致を通常視点確定の証拠から除外。幾何校正と本人視点分類を分離した。
  `e2e_masked_hud_uniform_probes/` はこの修正前の中間結果。
  最終再検証は `../outputs/e2e_masked_hud_safe_probes/hud_diagnostics.json` を参照する。
  視点の証拠不足はunknownで保持するため、マスク導入だけで実用認識が完成したとは扱わない。
- 最終独立プローブ6枚は全てunknown。幾何校正成立は3枚だが、masked anchorを本人視点の
  証拠から除外した結果であり、通常/特殊視点分類の精度向上とは主張しない。
- 修正後の全pytest: **407 passed / 1 skipped / 0 failed**（33.14秒）。
  結果: `../outputs/e2e_post_audit_tests.xml`。Ruff成功、mypy本体72ファイル成功。

全動画E2E・元の13時刻アンカーの合格は依然未確認。今回の修正は上記2不具合の解消と
校正機構の改善であり、状態別テンプレート/所有者検出器の完成とは分けて扱う。

- 精査修正前のpytest: **395 passed / 1 skipped / 0 failed**（34.05秒）。
  skipは環境変数で明示的に有効化するHUD実動画アンカーテスト。
  元録画自体は存在する。通常pytestでは動画パスを指定していないためskip。
  JUnit結果は `../outputs/e2e_unit_integration_latest.xml`。
  Ruffはsrc/testsで成功、mypyは本体72ファイルで成功。
- 付属shotテストは4ケース、Mapテストは5ケース、aliasは3レコードを検査。
  continuous combatは参照値の算術検証。いずれも実装側の知覚精度を示さない。
- metaテストのメッセージは「13 corruption modes」だが、コードには
  spectator HUD/location追加を含め14種類の破損ケースがある。
  元ファイルは変更せず、実際に実行されたassertionを正とする。
- output trace Schemaは各レコードで `additionalProperties: true`、
  confidenceも必須ではない。ユーザーの厳格なconfidence要件は
  Schema検証だけでは保証されないため、統合時に別の意味検証が必要。
- source sidecarの内部整合性検証は、元動画のPTSとの照合とは別。
- 付属SchemaがないJSONについて「全JSONのSchema検証完了」とは扱わない。

## 再実行

プロジェクトディレクトリから:

```text
python -m pytest tests/integration/test_e2e_validation_pack_v3.py -q
python ../valorant_e2e_validation_pack_v3/tests/validate_pack.py --project-root src
```

```text
python tests/e2e/diagnose_hud_video.py --source-video <video> --layout <layout.json> --output <new-probe-dir>
python tests/e2e/run_real_video.py --source-video <video> --layout <layout.json> --output <new-run-dir>
python tests/e2e/evaluate_saved_trace.py --pack ../valorant_e2e_validation_pack_v3 --trace <new-run-dir>/e2e_trace.json --output <new-run-dir>/evaluation_report.json
```

元動画の同一性は付属validatorの `--source-video <path>` で確認済み。
最新修正後の全動画E2E再実行・65不一致の解消は未完了。
今回のOCR拡張に新たなPython依存はない。Windows起動・PyInstallerの既存手順は維持し、
Tesseractと言語データは別途設定する。Windows/.exe実行はこのMac環境では未検証。
