# FAQ

## Pythonは必要？

Installer / Portableの通常利用には不要です。公式配布物はPyInstaller runtimeを含みます。
source開発ではPython 3.12を使用します。

## FFmpegは必要？

実動画のmetadata取得やclip生成にはFFmpeg / ffprobeが必要です。正式配布物には同梱しないため、
PATHへ用意するか設定画面でexeを指定してください。

## API keyは必須？

Mock AIなら不要です。Mock AIをOFFにした実AIではOpenAI API keyが必要です。

## 無料で使える？

Mock AIはOpenAI API通信を行わないため、その経路でOpenAI API利用料は発生しません。
実AIやSemantic VisionではAPI利用料が発生する場合があります。最新料金をrepository内の
固定値としては扱いません。

## 動画全体をOpenAIへ送る？

いいえ。元動画全体をuploadする実装ではありません。ただし実AI / Semantic Visionでは
選択されたframe画像が送信され、そのframe内のplayer name、chat、minimap、overlay等も
見える可能性があります。詳細は [Privacy / Data Guide](privacy_and_data.md) を参照してください。

## プレイ動画はどこに保存される？

元動画は選択した元の場所に残ります。標準data directory
`%LOCALAPPDATA%\ValorantAICoach` にはDB、clip、analysis JSON、evidence frame等を保存します。

## Uninstallすると解析結果も消える？

既定では消えません。Installerはapplication filesとshortcutを削除しますが、
`%LOCALAPPDATA%\ValorantAICoach` は保持します。

## PortableとInstallerの違いは？

Installerはper-user install、Start Menu shortcut、upgrade/uninstallを提供します。
PortableはZIPを展開してそのままexeを起動します。どちらも同じPyInstaller onedir runtimeを
元に作られ、Pythonは別途不要です。

## Windows 10は使える？

公式Release対象はWindows 10 / 11 x64です。

## Windows ARMは？

ARM-native buildは公式対象ではありません。Windowsのx64 emulationで動く可能性はありますが、
このrepositoryの公式配布contractでは保証しません。

## Mac版 / Linux版は？

現在の正式なend-user配布対象はWindowsです。source/E2Eにはcross-platform作業がありますが、
Mac/Linux向けの公式GUI配布物としては定義していません。

## UNSCOREDとは？

必要な証拠が不足または曖昧で採点しなかった状態です。悪いプレイという意味ではありません。

## 実HUDでunknownが多いのはなぜ？

実HUDはprofile、解像度、crop、視点、表示条件等に依存します。根拠を安全に確定できない場合は
推測せずunknownにする設計です。

## API keyはどこに保存される？

`settings.json` ではなく、Windowsではkeyring経由でWindows Credential Managerへ保存します。
stored credentialがない場合は `OPENAI_API_KEY` がfallbackになります。

## Diagnosticを共有して大丈夫？

source/support向けdiagnostic bundleはallowlistとredactionを備えていますが、共有前に内容を
自分でも確認してください。raw video、API key、DBを手動追加しないでください。
詳しくは [Troubleshooting](troubleshooting.md#diagnosticを取得したい) を参照してください。

## GOODは「完璧なプレイ」という意味？

いいえ。候補ルールについて、現在の観測根拠から肯定的な判定を出せたという意味です。
プレイ全体の完全性やプロコーチ相当の理解を保証するラベルではありません。
