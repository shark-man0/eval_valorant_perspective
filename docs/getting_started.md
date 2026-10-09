# Getting Started

このページは、WindowsでVALORANT AI Coachを初めて起動し、最初の解析結果を見るまでの
手順です。開発用Python環境は不要です。

## 1. 配布物を選ぶ

公式Windows配布はWindows 10 / 11 x64向けです。

### Installer

ファイル名:

`VALORANT-AI-Coach-Setup-<version>-x64.exe`

Inno Setupによるper-user installです。通常のインストール先は次です。

`%LOCALAPPDATA%\Programs\VALORANT-AI-Coach`

通常利用ではadministrator権限を要求しません。Start Menu shortcutが作成され、
desktop shortcutはInstallerで任意選択です。

### Portable ZIP

ファイル名:

`VALORANT-AI-Coach-<version>-windows-x64.zip`

任意のフォルダへ展開し、展開したフォルダ内の `VALORANT-AI-Coach.exe` を起動します。
Pythonを別途インストールする必要はありません。

Installer / Portableの正本は
[Windows distribution](windows_distribution.md)です。

## 2. SmartScreenが表示された場合

現在のReleaseはWindows code signingを設定していません。そのため、入手経路や
reputationによってSmartScreen等の警告が表示される場合があります。

警告が出たことだけを根拠に安全／危険を断定せず、入手元、Releaseのファイル名、
必要に応じて `SHA256SUMS.txt` を確認してください。組織管理PCでは所属組織の
セキュリティ方針を優先してください。

詳しくは [Troubleshooting](troubleshooting.md#smartscreenが表示される) を参照してください。

## 3. FFmpeg / ffprobeを準備する

正式配布物には `ffmpeg.exe` と `ffprobe.exe` を同梱しません。

次のどちらかで準備します。

1. FFmpeg / ffprobeをインストールし、両方がPATHから実行できるようにする。
2. アプリを起動し、メニューバーの **設定** から **FFmpeg** と **FFprobe** に
   それぞれの `.exe` を指定する。

Mock画面を開くだけなら即座にFFmpegを使用しない場合がありますが、動画metadataの
取得にはffprobe、フレーム処理・クリップ生成を含む実際の動画経路にはFFmpeg /
ffprobeが必要です。

## 4. 最初はMock設定で確認する

初回設定は次の状態です。

- Mock AI: ON
- HUD解析: Mock Round Package
- Mockケース: `TC-029`
- Visual Semantic: OFF

この状態ではOpenAI API keyは不要です。まずこの構成でGUI、動画読み取り、結果表示、
クリップ経路を確認してください。

既定のMockケースは35秒までの観測を含むため、最初の確認には**35秒以上の動画**を
選んでください。Mock評価の内容は動画内容そのものには依存しませんが、実際の動画から
フレーム・クリップを扱う経路は通ります。

## 5. 動画を選ぶ

ホーム画面で **録画を選択** を押します。選択できる形式は次です。

- MP4
- MKV
- MOV
- AVI
- WebM

ffprobeによる確認が成功すると、解像度、fps、長さ、codec、音声の有無、ファイルサイズが
表示され、**解析を開始** が有効になります。

## 6. 最初の解析を実行する

**解析を開始** を押すと進捗画面へ移動します。処理中は進捗率と処理ログが表示されます。

必要なら **キャンセル** を押せます。キャンセル後は履歴にcheckpointが残り、条件が
満たされていれば後から **選択した解析を再開** が使えます。

解析が完了すると結果画面へ移動します。

## 7. 結果を読む

結果には次のラベルがあります。

- **GOOD**: 根拠から肯定的に評価できたもの。
- **IMPROVE**: 根拠から改善対象として評価できたもの。
- **UNSCORED**: 必要な証拠を確定できず採点しなかったもの。悪いプレイを意味しません。

GOOD / IMPROVEには根拠、理由、信頼度等が表示され、生成に成功した項目には
**根拠クリップを再生** ボタンが表示されます。UNSCOREDでは不足情報や診断コードを確認
できます。

詳しくは [User Guide](user_guide.md) を参照してください。

## 8. 保存済み結果を使う

最初の結果を保存したら、メニューバーの **履歴・統計ツール** から統計、
検索・比較、HTML/CSV/JSON出力、評価への意見保存などを利用できます。
動画を再解析せず、保存済みSQLite結果を読む機能です。
詳しくは [User Guide](user_guide.md) にまとめています。

## 9. 実AIを使う場合

Mock動作を確認してから設定を変更してください。

1. **設定** を開く。
2. **OpenAI APIキー** を入力する。
3. **Mock AI** をOFFにする。
4. **OpenAIモデル** を確認する。初期値は `gpt-5.6-terra` ですが、設定欄の値が
   実際に利用されます。
5. 保存して解析する。

実AIではネットワーク接続が必要で、OpenAI API利用料が発生する場合があります。
料金額はこのrepositoryでは固定しません。

API keyは `settings.json` には保存されません。Windowsではkeyring経由でWindows
Credential Managerへ保存します。保存済みcredentialがない場合のみ
`OPENAI_API_KEY` 環境変数がfallbackとして使われます。

## 9. 実HUD / Semantic Visionは必要なときだけ有効にする

実HUDは録画条件に合う校正済みprofileが必要です。すべてのVALORANT録画を自動で完全認識
する機能ではありません。根拠を確定できない場合は `unknown` や
`calibration_required` になり得ます。

Visual Semanticは既定OFFです。現在は実HUD構成で、Mock AIをOFFにし、API keyと
Visual専用modelを設定した場合にのみremote画像解析adapterが有効になります。

実AI / Semantic Visionの送信内容と既知のprivacy制約は、利用前に
[Privacy / Data Guide](privacy_and_data.md) を確認してください。

## 10. 保存先、upgrade、uninstall

標準ユーザーデータ保存先は次です。

`%LOCALAPPDATA%\ValorantAICoach`

Installerのupgradeはapplication filesを更新しますが、このdata directoryはInstallerの
管理対象外なので通常保持されます。API credentialもInstaller管理外です。

Uninstallではapplication binariesとshortcutを削除しますが、このuser data directoryは
既定では削除しません。解析結果を消したい場合は、まずアプリ内の履歴削除を使うか、
保持データを確認してから対応してください。

詳細は [Privacy / Data Guide](privacy_and_data.md) と
[Windows distribution](windows_distribution.md) を参照してください。

## 次に読む

- 日常操作: [User Guide](user_guide.md)
- 問題が起きた: [Troubleshooting](troubleshooting.md)
- privacy: [Privacy / Data Guide](privacy_and_data.md)
- 短い疑問: [FAQ](faq.md)
