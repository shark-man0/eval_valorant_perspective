# VALORANT AI Coach

VALORANTのプレイ録画から、ユーザー定義ルールに基づく `GOOD` / `IMPROVE` /
`UNSCORED` と根拠クリップを作成・保存・再生するWindows 10/11向けデスクトップ
アプリです。Python 3.12、PySide6、FFmpeg / FFprobe、OpenCV、SQLite、OpenAI
Responses APIで構成しています。

HUD / Video Analyzer v2パッチを統合しています。実HUDモードではOpenCVで録画を2段階
サンプリングし、HUD Observation、Event、Round Packageを生成して本体へ渡します。
ROIは同梱の `hud_layout_1080p_v3.json` を使用し、認識用の参照画像とテンプレート設定は
録画環境に合わせて追加します。参照画像がなく校正できない場合は `calibration_required`
で停止します。APIキーや参照画像がない場合もMockモードで本体E2Eを実行できます。
実装・検証範囲と残課題の詳細は [HUD_INTEGRATION.md](HUD_INTEGRATION.md) を参照してください。

Visual Analyzer v2の追加実装・設定・検証範囲は [VISUAL_INTEGRATION.md](VISUAL_INTEGRATION.md) を参照してください。
実HUDモードにVisual処理を接続しましたが、実ゲーム用の認識profile・Mapデータの調整は必要です。
Semantic Visionは既定OFFで、Mock AIがONの間は呼び出しません。

Map / Zone v3も統合済みです。新runtime contract v4だけを位置解決に使用します。
Map選択・画像校正・ZoneResolution・Visualイベントの分離、旧profile移行、確認範囲は
[MAP_ZONE_INTEGRATION.md](MAP_ZONE_INTEGRATION.md) を参照してください。

## 処理フロー

```text
録画 -> ffprobeメタデータ -> HUD/Event Analyzer
     -> Round Package Schema v2 -> Deterministic Fact Builder
     -> Rule Selector（最大12候補） -> Rule Engine
     -> sparseラウンド文脈 + dense候補フレーム -> AI Coach
     -> Output Schema v3検証 -> 重複集約 -> FFmpegクリップ
     -> SQLite + analysis.json -> PySide6 GUI
```

元動画全体はOpenAI APIへ送りません。実APIモードで送るのは、候補判定に必要な
Round Package、選択済みルール、決定論的Fact、最大32枚の抽出フレームです。APIへの
保存は `store=false` で要求します。

## 実装済み

- MP4 / MKV / MOV / AVI / WebM選択、非同期ffprobeメタデータ取得、Qt動画再生
- ラウンド/Event/Factモデル、正本JSON SchemaのDraft 2020-12検証と実行時整合性検証
- 44ルールの候補選定、Role gate、明示された数値・二値条件だけのRule Engine
- ラウンド疎フレームと候補周辺密フレームの分離、最大画像数と解像度の制限
- OpenAI Responses API画像入力、候補ルールだけの送信、最大2回のSchema修復
- 決定論的ラベル/Factのローカル強制、通信再試行とSchema修復の分離
- 検証済みAI結果キャッシュ、修復時の画像再送防止、API通信中のキャンセル
- GOOD / IMPROVE / UNSCORED、低信頼度処理、同一場面・反復評価の集約
- FFmpegによる範囲制限付きMP4クリップ生成と重複クリップの物理ファイル再利用
- SQLiteの原子的migration/結果置換、履歴・チェックポイント・JSON保存
- 削除されない根拠フレームの恒久保存、完了ラウンドを再処理しない中断・再開
- 1ラウンドの障害を後続ラウンドから分離するpartial完了と診断保存
- ホーム、解析進捗、履歴の再開/安全な削除、結果カード、UNSCORED診断、再生、設定画面
- APIキーのOS資格情報ストア保存（設定JSONやログには保存しない）
- ローテーションログ、Mock E2E、PyInstaller onedir spec、Windows CI
- HUD状態分類、テンプレート/OCR境界、2段階サンプリング、時系列差分、Event Source Contract
- 観戦・特殊視点・マップ・視界遮蔽のVisual解析ゲート、HUDと評価confidenceの分離
- Round Package生成、HUD観測診断と採用フレーム保存、校正プロファイル作成コマンド
- 全音声トラックのクリップ保持、既定トラック選択と再生切替・設定保存

## 実データで追加が必要な部分

- 未加工スクリーンショットによるアンカー・数字・アイコンの参照テンプレート
- 元の171秒録画に対するHUD検出精度の検証と調整（ZIPには元録画がありません）
- Cypher/Sova/Skye等のAgent別特殊視点の参照テンプレート
- shot/peek/movement/rotation等の高精度Visual Analyzer、マップ別Zone/ミニマップ認識

HUDだけでは全44ルールを実動画で評価できません。Visual Analyzerは交換可能な
インターフェースとして分離し、未観測のイベントは生成しません。

## Windowsで開発実行

前提:

- Windows 10 version 1809以降またはWindows 11（64-bit）
- Python 3.12.x（3.13以降ではなく3.12を使用）
- FFmpegとFFprobe

PowerShellでプロジェクト直下から実行します。

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -c constraints-windows.txt -e ".[gui,dev,build]"
.\.venv\Scripts\python.exe tests\validate_dataset.py
.\.venv\Scripts\python.exe -m pytest
.\.venv\Scripts\python.exe -m valorant_ai_coach
```

または `run_windows.ps1` を実行できます。

FFmpeg/FFprobeが `PATH` にない場合は、アプリの設定画面でそれぞれの `.exe` を指定して
ください。Mock HUDの標準ケース `TC-029` は観測が35秒まであるため、デモ用動画は
35秒以上必要です。動画の内容自体はMock評価へ影響しませんが、実際に抽出したフレームと
クリップを通して動画経路を検証します。

## 設定とデータ

初回起動は `Mock AI` + `Mock HUD` なのでAPIキーなしで動作します。実AIを使う場合は
設定画面でAPIキーを入力し、Mock AIを無効にします。モデルIDは設定値で、初期値は
`gpt-5.6-terra` です。

標準データ保存先:

```text
%LOCALAPPDATA%\ValorantAICoach\
├── settings.json        # APIキーを含まない
├── app.db
├── clips\
├── matches\<match-id>\analysis.json
├── matches\<match-id>\evidence\  # 後から検証できる根拠フレーム
├── cache\ai\           # 検証済みAI JSON。画像/APIキーは保存しない
├── logs\valorant-ai-coach.log
└── temp\                # 通常は解析後に削除
```

APIキーはWindows Credential Managerへ保存します。`OPENAI_API_KEY` 環境変数も、資格情報
ストアにキーがない場合のフォールバックとして利用できます。中断または一部失敗の
履歴を選択すると、保存済み動画指紋・設定指紋が一致する場合だけ「選択した解析を再開」
で続行できます。「選択した履歴を削除」はSQLite上の解析結果、生成クリップ、根拠フレームを
削除しますが、元の録画ファイルは保持します。
検証済みAI結果キャッシュは最終アクセス順で最大512件または合計256 MiBに制限されます。

## テスト

```powershell
.\.venv\Scripts\python.exe tests\validate_dataset.py
.\.venv\Scripts\python.exe -m pytest --cov=valorant_ai_coach --cov-report=term-missing --cov-fail-under=75
.\.venv\Scripts\python.exe -m ruff check src tests\unit tests\integration
.\.venv\Scripts\python.exe -m mypy src\valorant_ai_coach
```

同梱の38ケースは、正本Schema、候補ルール、GOOD/IMPROVE/UNSCORED、複数評価、Role、
時間切迫、Utility、低信頼、出力なし、曖昧性、重複集約を検証します。追加テストはキャンセル、
中断再開、根拠フレーム存続、ラウンド障害分離、OpenAI境界/キャッシュ、SQLite、Mock E2E、
実OpenCVを検証します。FFmpegが利用できる環境では合成動画の実クリップ試験も実行します。
カバレッジは75%未満で失敗します。

## `.exe` ビルド

正式な初期配布形式はPyInstaller `onedir` です。

```powershell
.\build_windows.ps1
```

成果物:

```text
dist\VALORANT-AI-Coach\VALORANT-AI-Coach.exe
```

自己完結に近い配布物にする場合は、配布権を確認した `ffmpeg.exe` と `ffprobe.exe` を
ビルド前に `bin\` へ置いてください。specが検出して同梱し、実行時に自動解決します。
置かない場合は、利用者側の `PATH` または設定画面のパスを使用します。

PyInstallerはクロスコンパイルしないため、Windows用 `.exe` はWindows上で作成して
ください。ビルド後は `--smoke-test` で同梱資源とGUI初期化を自動確認します。GitHub
Actionsの `Windows verification` は実FFmpegテスト、カバレッジ、onedir生成、成果物起動を検証します。
`constraints-windows.txt` はWindows/Python 3.12で検証する直接依存関係を固定し、通常起動・
ビルド・CIのすべてで同じ制約を使用します。

## Windows実動画E2EとMacへの結果共有

動画はWindowsローカルだけに置き、既存E2Eの結果を軽量JSONとして共有できます。
初回にValidation Packを別途展開し、`VALORANT_E2E_PACK`を設定してください。

```powershell
.\run_e2e_windows.ps1 -Video 'D:\ValorantData\videos\match_001.mp4' -VideoId match_001
```

`datasets/manifests/match_001.json` は既存v3検証録画をSHA-256で識別します。
別動画を同名にしても一致しなければ解析を開始しません。新規登録は明示的な
`-Register` と、その動画に対応するValidation Packが必要です。
出力はローカル詳細 `outputs/e2e/` と共有用 `e2e_reports/` に分離します。
runnerはGitへのcommit/pushをしません。結果・privacyを確認してから利用者が実行します。
パスの優先順位、環境確認、FAILの解釈、最小5ステップは [WINDOWS_E2E.md](WINDOWS_E2E.md)。

## 実HUDの設定

未加工の1920x1080通常一人称スクリーンショットから、参照用のアンカー画像を作れます。
プレビュー図やROI線を描き込んだ画像は使用しないでください。

```powershell
.\.venv\Scripts\python.exe -m valorant_ai_coach.hud.calibrate `
  C:\captures\reference.png C:\captures\my_hud_profile
```

出力の `hud_layout.templates.json` に `config/hud_templates.example.json` を参考に
数字・Spike・Ability等のreaderを設定します。数字templateを優先し、任意のTesseract
digits-only OCRをfallbackとして利用できます。Tesseractを使用する場合は利用者の環境へ
別途導入し、profileの実行ファイル設定またはPATHから解決してください。
参照画像を抽出しただけでは精度検証済みにはなりません。

数字・背景が変わる部分を校正から除外するには、校正コマンドへ
`--anchor-regions C:\captures\anchor_regions.json` を追加できます。
JSONはアンカー名をキーとし、親ROI内の正規化矩形の配列を指定します。
例: `{"player_hp_armor": [[0.78, 0.49, 0.99, 0.68]]}`。
これは形式例であり汎用の推奨座標ではありません。各録画の固定HUD形状を確認してください。
指定部分だけを採用する同寸法のPNGマスクが生成され、位置/サイズの校正条件と
一致度閾値は維持されます。既存profileではanchorに `mask` の相対パスも指定可能です。
欠損・サイズ不一致・情報不足のマスクは校正失敗として扱い、マスクなしに戻しません。
マスク付きアンカーは幾何校正専用です。特殊視点にも残る固定線を使って
通常一人称と誤認しないよう、これだけでは本人視点を確定しません。
独立した視点分類の証拠がない場合はunknownとなります。

日本語の位置ラベルは `location_label` readerの `kind: "text"`、
`language: "jpn+eng"` で設定できます。Tesseract本体に加えて対応言語データが必要です。
`tessdata_dir` は任意で指定でき、相対パスはprofile JSONの場所から解決します。
必要な言語がない場合はunknownと診断情報を返し、英語OCRへ勝手に置き換えません。
Tesseract本体・言語データはexeへ自動同梱されません。

数字readerの `white_text_threshold`（0〜255の整数）は任意の白文字前処理です。
`subregion_norm: [x1,y1,x2,y2]` で親ROI内の読取範囲を絞れます。
どちらもconfidenceの加点や受理閾値の変更はしません。
`timer_mmss` のOCR結果はコロンを含む分:秒形式のみ受理し、欠けた文字を推測しません。

アプリ設定で「実HUD」を選び、生成された `hud_layout.json` を指定します。
同じ場所の `<layout名>.templates.json` を自動読込します。レイアウト欄を空にすると
保存先の `hud_layout.json`、なければ同梱1080pレイアウトを使います。
解像度・クロップ・レターボックス・アンカーの位置/サイズが不一致なら校正を要求します。

元の検証録画とprofileがある場合は、同梱の13時刻アンカーを実行できます。

```powershell
$env:VALORANT_HUD_TEST_VIDEO = 'C:\captures\Valorant_09-25-2026_0-37-29-379.mp4'
$env:VALORANT_HUD_TEST_LAYOUT = 'C:\captures\my_hud_profile\hud_layout.json'
.\.venv\Scripts\python.exe -m pytest tests\integration\test_hud_real_video_anchors.py
```

未指定の場合、この実録画試験だけは明示的にskipします。通常のテストでは合成画像・動画で
校正、reader、分類、時系列差分、Round Package、本体との接続を検証します。

## 正本ファイル

- `CODEX_MASTER_SPEC.md`
- `REVIEW_FIXES.md`
- `schemas/round_package_schema_v2.json`
- `schemas/ai_coach_output_schema_v3.json`
- `schemas/event_type_registry_v2.json`
- `schemas/test_assertion_schema_v1.json`
- `config/valorant_evaluation_rules_v4.json`
- `config/rule_trigger_registry_v2.json`
- `config/deterministic_rule_engine_v1.json`
- `config/role_contract_v1.json`
- `config/map_zone_contract_v1.json`
- `tests/manifest.json`, `tests/cases/*`, `tests/validate_dataset.py`
- `VIDEO_HUD_ANALYZER_SPEC.md`, `HUD_VALIDATION_REPORT.md`, `HUD_REVIEW_FIXES.md`
- `schemas/hud_observation_schema_v2.json`
- `config/hud_layout_1080p_v3.json`, `config/event_source_contract_v1.json`
- `config/ability_slot_contract_v1.json`, `config/weapon_visual_registry_contract_v1.json`
- `tests/hud_logic_cases_v1.json`, `tests/hud_state_samples_v2.json`

これらのSchema・ルール・テストデータは、アプリ固有の別形式へ置き換えず直接使用しています。

## Cross-platform source E2E

Windows and Linux/Pi use the same `scripts/e2e/run_dataset_case.py`.
See [Windows E2E](WINDOWS_E2E.md), [Raspberry Pi setup](RASPBERRY_PI_E2E.md),
and [migration audit](docs/cross_platform_e2e_migration.md).
Linux/Pi real-device execution remains unverified; Analyzer improvements are paused
until that result is reviewed. Desktop installation requires the `gui` extra.
