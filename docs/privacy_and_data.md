# Privacy / Data Guide

この文書は法的なPrivacy Policyではありません。現在の実装が技術的にどのデータを
ローカルへ保存し、どの情報をremote APIへ送信し得るかをユーザー向けに整理したものです。

## まず知っておくこと

- 元動画全体をOpenAI APIへuploadする実装ではありません。
- Mock AIではAI CoachのOpenAI API送信を行いません。
- 実AIでは選択されたtext dataとframe画像がOpenAI APIへ送信され得ます。
- Visual Semanticは別のopt-in画像送信経路です。
- API requestでは `store=False` を指定しています。
- `store=False` を指定している事実を超えて、「外部で絶対に保存されない」とは
  このrepositoryから断定しません。
- selected frameには画面内のprivate informationが映り込む可能性があります。

## Localに保存するもの

標準data directory:

`%LOCALAPPDATA%\ValorantAICoach`

主な内容は次です。

| データ | 目的 |
| --- | --- |
| `settings.json` | アプリ設定。API keyは含みません。 |
| `app.db` | match、round package、evaluation、checkpoint、clip metadata等。 |
| `clips\` | GOOD / IMPROVE等で生成された根拠clip。 |
| `matches\<match-id>\analysis.json` | match単位の保存結果。 |
| `matches\<match-id>\evidence\` | 解析根拠として抽出・保存されたframe。 |
| `cache\ai\` | 検証済みAI結果JSONのcache。画像やAPI keyを保存する目的ではありません。 |
| `logs\` | rotation log。 |
| `temp\` | 一時処理data。既定では解析後に削除する設定です。 |
| `visual-semantic-budget.sqlite` | Semantic Visionを利用する場合のcall/result budget状態。 |

`settings.json` は標準SettingsStore（既定では `%LOCALAPPDATA%\\ValorantAICoach\\settings.json`）に残り、そこに設定された `data_dir` をDB、clip、match/evidence、cache、log、temp等のruntime保存先として使用します。

### 元動画

元動画はユーザーが選んだ元の場所に残ります。アプリは元動画へのpathを記録し、解析のため
読み取りますが、元動画全体をdata directoryへ複製する通常contractではありません。

### API credential

API keyは `settings.json` へ保存しません。

Windowsではkeyringを通してWindows Credential Managerへ保存します。保存済みcredentialが
取得できない場合に限り、`OPENAI_API_KEY` 環境変数をfallbackとして参照します。

API keyをlog、diagnostic、issue、support chatへ貼らないでください。

## Evidence frame

解析では評価根拠として一部frameを
`matches\<match-id>\evidence\` に保存します。

これはraw video全体とは別の抽出画像ですが、gameplay画面そのものなのでplayer name、
chat、minimap、overlay等を含む可能性があります。localで扱う場合もprivacy-sensitiveな
dataとして扱ってください。

履歴削除ではそのmatchのevidence directoryも削除対象になります。

## Remote: AI Coach

Mock AIをOFFにした実AIでは、OpenAI Responses APIへ主に次の情報を送信します。

- local pathを安定化したRound Package
- 選択された候補ruleとそのpolicy情報
- deterministic decisions / Factsに由来する構造化情報
- 選択されたevidence frame画像（AI Coach側は最大32枚）
- Schemaに従うための要求情報

元動画全体を送信しません。text payloadではsource video pathをbasenameへ置き換え、
frame pathもremote用の安定名へ置き換えます。

OpenAI requestには `store=False` を指定します。

## Remote: Semantic Vision

Visual Semanticは既定OFFのopt-in機能です。現在のservice構築では、実HUDを使用し、
Mock AIがOFFで、Visual Semanticを有効にし、API keyとVisual専用modelが設定されている
場合にremote adapterが作られます。

Semantic Visionでは選択されたframe画像、対応timestamp、visible factを返すための
Schema/instructionが送信されます。こちらも `store=False` を指定します。

## Known privacy limitation: SEC-07

Security reviewのSEC-07は現在未解決のaccepted feature/privacy riskです。

**raw video全体を送るわけではありませんが、remote AIへ送られるselected gameplay frame
自体はprivacy-redacted cropを保証していません。**

そのためselected frameに映っている次の情報もremote入力になり得ます。

- player name
- chat
- minimap
- overlay
- その他gameplay画面上の識別情報・表示情報

Mock AIをONにするとAI CoachのOpenAI送信を避けられます。Semantic Visionもremote画像送信を
避けたい場合はOFFのまま使用してください。

この制約の技術的な正本は [Security review](security_review.md) のSEC-07です。

## 自動的には共有しないもの

現在の通常remote AI経路／diagnostic policyから、次を「そのまま自動共有する」設計では
ありません。

- raw source video全体
- `app.db`
- `settings.json`
- OS credential store内のAPI key
- application log全体
- Validation Pack
- arbitrary local files

ただし、selected frame内に視覚的に含まれる情報は前節のSEC-07の対象です。

## Diagnostics

source/support向けdiagnostic bundleはallowlist-onlyです。含み得るのは次です。

- sanitized `manifest.json`
- sanitized `performance.json`
- sanitized `dependency_snapshot.json`
- bounded/redacted `recent.log`

policy上除外するもの:

- raw video
- screenshots / HUD crop
- Validation Pack
- database
- full environment dump
- API credentials
- raw API response
- private profile image
- arbitrary user files

diagnostic生成機能が除外しているfileを手動で追加しないでください。
詳しくは [Observability](observability.md) を参照してください。

## Delete

GUIの **選択した履歴を削除** は、そのmatchのDB data、unshared clip、
`matches\<match-id>` 以下のanalysis/evidenceを削除します。元動画は削除しません。

## Upgrade / Uninstall

Installer upgradeではapplication filesを更新しますが、
`%LOCALAPPDATA%\ValorantAICoach` はInstaller管理外なので保持されます。

Uninstallもapplication binaries / shortcutを削除しますが、user dataは既定では残します。
API credentialもInstallerのuser data削除対象ではありません。

完全削除を行いたい場合、この文書ではrecursive delete commandを提示しません。
まずアプリ内の履歴削除を使い、残っているsettings、DB、clip、evidence、credentialの必要性を
確認してください。組織管理環境では管理者方針に従ってください。

配布contractの正本は [Windows distribution](windows_distribution.md) です。

## Backupの考え方

解析履歴を保持したい場合は、アプリを終了してからdata directory全体をバックアップ対象として
扱うのが最も分かりやすい方法です。ただしAPI keyはdata directoryではなくOS credential
storeにあるため、data directoryのcopyだけでcredentialまでbackupされるわけではありません。
