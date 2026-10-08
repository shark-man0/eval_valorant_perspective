# User Guide

このガイドは、配布版VALORANT AI CoachのGUI操作を説明します。開発用コマンドやE2E検証は
通常利用には必要ありません。

## ホーム画面

ホーム画面には主に次の操作があります。

- **録画を選択**: 解析する動画を選択します。
- **解析を開始**: 選択済み動画の解析を開始します。metadata取得成功後に有効になります。
- **選択した解析を再開**: 履歴で再開可能な項目を選んだ場合に有効になります。
- **選択した履歴を削除**: 選択した解析結果を削除します。
- **解析履歴（ダブルクリックで開く）**: 保存済み結果を開きます。
- **再生 / 一時停止** とseek bar: 選択した元動画をホーム画面で再生します。
- mode表示: `Mock AI / Mock HUD`、または現在のOpenAI model / 実HUDを表示します。
- メニューバーの **設定**: API、HUD、FFmpeg、data directory等を変更します。

## 動画選択と動画情報

**録画を選択** からMP4 / MKV / MOV / AVI / WebMを選択できます。

選択後、ffprobeが動画を確認します。成功すると次の情報が表示されます。

- 解像度
- fps
- 長さ
- video codec
- 音声の有無
- ファイルサイズ

確認中は別の解析開始はできません。失敗すると **動画を開けません** ダイアログと
**動画メタデータを取得できませんでした** が表示されます。

## 解析を開始する

**解析を開始** を押すと進捗画面に移動します。

実AI設定でAPI keyを取得できない場合は **APIキーが必要です** と表示され、
解析は始まりません。Mock AIならAPI keyは不要です。

進捗画面には次が表示されます。

- 現在の処理説明
- 0〜100%のprogress bar
- 最大200件までの画面内処理ログ
- **キャンセル** ボタン

キャンセルすると安全な区切りで停止を試みます。アプリ終了時に動画確認または解析が
動作中の場合も、終了確認後にbackground workerを止めてから閉じます。

## 履歴

履歴には作成時刻、元動画ファイル名、動画長、statusが表示されます。

ダブルクリックで保存済み結果を開きます。

### Resume

**選択した解析を再開** は、保存済みcheckpointとresume identityがあり、statusが
`analyzing`、`generating_clips`、`cancelled`、`failed`、`partial` のいずれか
である場合に有効になります。

再開時には元動画が現在も存在する必要があります。また、保存されたsource fingerprintと
設定fingerprintが現在の動画・設定と一致することが前提です。元動画が見つからない場合は
**解析を再開できません** と表示されます。

完了済み解析は通常resume対象ではありません。

### Delete

**選択した履歴を削除** は確認後に次を削除します。

- SQLite上のそのmatchの解析データ
- そのmatchだけが参照している生成クリップ
- `matches\<match-id>` 配下の `analysis.json` と根拠フレーム等

**元の録画ファイルは削除しません。** UIにも
「元の録画ファイルは削除しません。この操作は取り消せません。」と表示されます。

## 結果画面

結果画面の見出しにはGOOD / 改善 / UNSCOREDの件数が表示されます。partial / failedでは
その状態も表示されます。

表示filterは次です。

- 評価（GOOD / 改善）
- GOOD
- 改善
- 要確認（低信頼）
- 診断: UNSCORED
- すべて
- category
- round

各cardには、利用可能な範囲でrule ID、category、round、decision source、confidence、
状況、根拠、理由、改善案、不足情報、UNSCORED診断code等が表示されます。

GOOD / IMPROVEでもconfidenceが0.75未満の場合は
**要確認: 信頼度0.75未満の参考評価です** と表示されます。

## GOOD / IMPROVE / UNSCORED

### GOOD

候補ルールについて、現在のevidence contractで肯定的な判定を出せた項目です。
「プレイ全体が完璧」という意味ではありません。

### IMPROVE

候補ルールについて、観測根拠から改善対象として判定された項目です。cardには改善案が
表示されます。

### UNSCORED

候補にはなったものの採点に必要な根拠を確定できなかった項目です。
**IMPROVEより悪い評価ではなく、採点しなかった状態**です。

現在のschemaではUNSCOREDに不足情報とreason codeが必要で、表示clipや改善案は持ちません。
reason codeには、たとえばvisual/HUD evidence不足、required Fact不足、曖昧な例外、
low confidence等があります。

### UNKNOWN / calibration_requiredとの違い

`unknown` はHUD / Visual等で値や状態を確定できなかった観測状態です。
`calibration_required` は実HUDの校正条件が満たされていないdiagnosticです。
どちらもGOOD / IMPROVE / UNSCOREDという評価ラベルそのものではありません。

## Evidence

cardの **根拠** は、評価が参照した時刻・Fact等を人が読める形にした表示です。

解析中には、AI/評価の再現性のため選択されたframeがlocalの
`matches\<match-id>\evidence` に保存されます。これは元動画全体とは別の抽出画像です。
画面情報を含むためprivacy-sensitiveになり得ます。

remote送信との関係は [Privacy / Data Guide](privacy_and_data.md) を参照してください。

## Clipと動画再生

GOOD / IMPROVEでclip生成が成功した項目には **根拠クリップを再生** が表示されます。
押すと結果画面のplayerでclipを再生します。

clipが見つからない場合は **クリップを再生できません** /
**クリップファイルが見つかりません** と表示されます。

生成clipは元動画のvideo trackと、存在するaudio trackを保持するようFFmpegへ要求します。
containerやQt backendの対応状況により再生可能trackは異なる場合があります。

## Audio track

動画に複数のaudio trackがある場合、再生画面にtrack選択が表示されます。選択したstream
indexは設定へ保存されます。

優先順位は概ね次です。

1. 保存済みpreferred trackが現在のmediaに存在する
2. container default
3. 先頭track

利用可能なtrack情報をplayer側で一致させられない場合、選択UIは無効になることがあります。

## 設定

メニューバーの **設定** では現在次を変更できます。

- OpenAI APIキー
- OpenAIモデル
- Mock AI
- HUD解析（Mock Round Package / 実HUD）
- Mockケース
- Visualプロファイル
- Visual Semantic
- Map選択
- Map検証用build
- Visual専用モデル
- HUDレイアウト
- FFmpeg
- FFprobe
- データ保存先
- 一時フレームを削除
- デバッグログ
- 再生する音声トラック（複数track等で必要な場合）

API key欄はpassword表示です。登録済みkeyを変更しない場合は空欄のまま保存できます。

### 実HUD

実HUDは校正済みlayout/templateや録画条件に依存します。設定画面で実HUDを選んだからと
いって全VALORANT動画が認識できるわけではありません。unsupported evidenceは推測で埋めず、
unknownとして扱う設計です。

詳細な校正作業は一般ユーザー向け必須手順ではありません。必要な場合のみ
[HUD integration](../HUD_INTEGRATION.md) を参照してください。

### Visual Semantic

Visual Semanticは候補画像をremote Vision APIへ送るopt-in機能で、既定OFFです。
現在のservice構築では、**実HUDかつMock AI OFF** の場合にのみadapterが有効になり、
API keyとVisual専用modelが必要です。

privacy制約は [Privacy / Data Guide](privacy_and_data.md) を確認してください。
