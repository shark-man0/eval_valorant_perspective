# Troubleshooting

問題が起きたら、**症状 → 確認 → 次の行動** の順で切り分けてください。
API key全文、元動画、databaseを安易にsupportへ送らないでください。

## アプリが起動しない

**確認**

- Windows 10 / 11 x64か。
- Installer版なら通常のinstallが完了しているか。
- Portable版ならZIP内から直接ではなく、展開後の `VALORANT-AI-Coach.exe` を起動しているか。
- SmartScreen等のOS警告が出ていないか。

**次の行動**

1. 配布物の入手元と `SHA256SUMS.txt` を確認します。
2. Portableなら別の書込み可能なfolderへ展開して試します。
3. 起動後に設定が原因だった場合は
   **設定を一時的に無効化しました** の警告が出ることがあります。この起動中は安全な
   Mock設定へfallbackするため、設定画面を開いて修正してください。
4. それでも起動できない場合はsupport向けにlog/diagnosticの共有方法を確認します。

## SmartScreenが表示される

現在のWindows Releaseはcode signingを設定していません。署名・reputationの制約により
SmartScreenが表示される可能性があります。

**確認**

- Releaseから取得した想定ファイル名か。
- `SHA256SUMS.txt` とhashが一致するか。

**次の行動**

PowerShellの例:

```powershell
Get-FileHash .\VALORANT-AI-Coach-0.1.0-windows-x64.zip -Algorithm SHA256
Get-FileHash .\VALORANT-AI-Coach-Setup-0.1.0-x64.exe -Algorithm SHA256
```

version部分は入手したReleaseに合わせてください。表示されたSHA-256を同じReleaseの
`SHA256SUMS.txt` と比較します。

警告を無条件に無視する手順はこの文書では案内しません。組織管理PCでは管理者方針を
優先してください。

## FFmpegが見つからない / ffprobeが見つからない

**確認**

- 設定画面の **FFmpeg** / **FFprobe** が正しい `.exe` を指しているか。
- PATHで使う場合は両commandが現在のユーザー環境で実行できるか。

**次の行動**

PATHを整えるか、設定画面の **参照…** から各実行ファイルを指定します。
正式配布物には両binaryを同梱していません。

動画選択時にffprobeが使えないと **動画を開けません** /
**動画メタデータを取得できませんでした** になります。解析失敗時のdialogには
「設定、FFmpeg/FFprobe、ログを確認してください。」と表示されます。

## 動画を開けない

**確認**

- ファイルが現在も存在するか。
- MP4 / MKV / MOV / AVI / WebMか。
- ffprobeが利用できるか。
- 動画にvideo streamと有効なduration / resolutionがあるか。

**次の行動**

別playerでファイル自体を確認し、FFprobe設定を見直してください。
アプリが表示するsanitized error messageとlogを確認します。

## API keyが認識されない

実AIでkeyが取得できないと **APIキーが必要です** /
「設定画面でAPIキーを登録するか、Mock AIを有効にしてください。」と表示されます。

**確認**

- 設定画面でkeyを保存したか。
- Mock AIが意図せずOFFになっていないか。
- Windows Credential Manager / keyringが利用できる環境か。
- Credentialがない場合に限り、`OPENAI_API_KEY` 環境変数がfallbackとして使われます。

**次の行動**

設定画面からkeyを再登録するか、一度Mock AIへ戻してlocal動作を確認します。

**API key全文をlog、issue、diagnostic bundle、chatへ貼らないでください。**

## API通信に失敗する

実AIではnetwork接続が必要です。アプリ側はremote error bodyやAPI keyをそのまま
ユーザー表示／logへ出さない設計です。

**確認**

- network接続
- API key
- model ID
- Mock AI設定
- Visual Semanticを使う場合はVisual専用model

Visual Semanticを有効にして必要情報が不足すると
**Visual SemanticにはAPIキーと専用モデル名が必要です** という設定構築errorになります。

**次の行動**

設定を確認し、必要ならMock AI / Visual Semantic OFFへ戻してlocal経路を切り分けます。

## 実HUDで calibration_required になる

`calibration_required` は「悪いプレイ」ではなく、現在の録画に対して必要なHUD校正を
成立させられなかったdiagnosticです。

**確認**

- 録画解像度、crop、letterbox、HUD位置がprofileの前提と合うか。
- 指定したHUD layout / template profileが対象録画用か。

**次の行動**

適合する校正済みprofileを使うか、まずMock HUDでアプリ本体の動作を確認します。
校正作業が必要な場合は [HUD integration](../HUD_INTEGRATION.md) を参照してください。

## HUDが unknown になる

`unknown` は根拠を確定できなかった状態です。推測で値を補完しないfail-closed設計のため、
録画条件やprofileによって増えることがあります。

**確認**

- 実HUD profileが対象環境用か。
- 特殊視点、観戦、map、視界遮蔽等ではないか。
- diagnosticsに校正やreaderの情報があるか。

**次の行動**

unknownを誤ってGOOD/IMPROVEへ読み替えず、必要ならprofile/録画条件を見直してください。

## 結果がUNSCOREDになる

UNSCOREDは失敗や悪いプレイの判定ではありません。

**確認**

結果cardの **不足情報** と **診断コード** を確認します。

**次の行動**

必要なHUD / Visual evidenceを現在の解析が取得できたか確認します。証拠を追加できない場合は
UNSCOREDのまま扱うのが正しい挙動です。

## クリップ生成に失敗する

**確認**

- FFmpegが利用できるか。
- 元動画が移動・削除されていないか。
- data directoryへ書き込めるか。

**次の行動**

設定、FFmpeg、保存先を確認します。clip単位の失敗はmatch全体が `partial` になる場合が
あり、他roundの結果は残ることがあります。

## Audioが期待通りでない

生成clipはvideo trackと存在するaudio trackを保持するようFFmpegへ要求します。

**確認**

- 元動画に複数audio trackがあるか。
- 再生画面のaudio track selectorが表示されているか。
- 保存済みpreferred trackが現在のmediaに存在するか。

**次の行動**

selectorでtrackを切り替えます。Qt multimedia backendがtrack一覧を一致させられない場合、
selectorが無効になることがあります。

## Resumeできない

**確認**

- 履歴statusがresume対象か。
- checkpointにresume identityがあるか。
- 元動画が現在も同じ場所にあるか。
- 動画内容／設定が前回と変わっていないか。

元動画がない場合は **解析を再開できません** /
**元動画が見つかりません。** と表示されます。

**次の行動**

元動画を戻します。source/config fingerprintが変わった場合は、新しい解析として実行する
方が安全です。

## Data directoryへ書き込めない

標準保存先は `%LOCALAPPDATA%\ValorantAICoach` です。

**確認**

- 設定の **データ保存先** が存在し、現在のユーザーが書き込めるか。
- read-only mediaやアクセス権のないfolderを指定していないか。

**次の行動**

ユーザーが書き込めるfolderへ戻します。設定欄が空の場合は
**設定を確認してください / データ保存先が空です** と表示されます。

## Logを確認したい

標準設定では次にあります。

`%LOCALAPPDATA%\ValorantAICoach\logs\valorant-ai-coach.log`

logはrotationされ、secret/pathのredactionが適用されます。ただしredactionは
defense-in-depthなので、共有前に内容を自分でも確認してください。

## Diagnosticを取得したい

### Installer / Portableユーザー

現在のGUIにはdiagnostic bundle生成buttonやpackaged `doctor` commandは公開されて
いません。まず設定、表示されたsanitized message、logを確認してください。

### Source / support環境

source treeとPython環境があるsupport作業では次が利用できます。

```powershell
python -m scripts.diagnostics.doctor
python -m scripts.diagnostics.create_bundle <run-id> --log <log-path>
```

`doctor` はPython、主要imports、FFmpeg、ffprobe、data directory、SQLite、GUI依存を
確認します。

diagnostic bundleはallowlist-onlyで、sanitized manifest、performance JSON、dependency
snapshot、bounded/redacted log tailを含み得ます。raw video、screenshots、HUD crops、
Validation Pack、DB、full environment、API credential、raw API response、private profile
image、arbitrary fileはpolicy上含めません。

**raw video、API key、databaseをbundleへ手動追加しないでください。**

詳細は [Observability](observability.md) を参照してください。
