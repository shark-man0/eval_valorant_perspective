# HUD / Video Analyzer v2 統合状況

後続のVisual v2統合は [VISUAL_INTEGRATION.md](VISUAL_INTEGRATION.md) を参照してください。
以下のVisual未接続に関する記述は、HUD統合時点の記録です。

2026-09-28更新。v3本体の正本Schema・評価ルール・既存テストデータは変更せず、追加パッチを統合しました。
レビューで指摘した8項目の修正は [HUD_REVIEW_IMPLEMENTATION_20260928.md](HUD_REVIEW_IMPLEMENTATION_20260928.md) に記録しています。
この記録は実装側の報告です。添付の `HUD_VALIDATION_REPORT.md` は元パッチの記録であり、
今回の実装の実動画検証結果ではありません。

## 実装した経路と変更ファイル

| 範囲 | 主なファイル | 内容 |
| --- | --- | --- |
| HUD | `src/valorant_ai_coach/hud/{layout,models,classifier,readers,templates,temporal,analyzers}.py` | JSON ROI、幾何校正、画素特徴、テンプレート/数字OCR、状態分類、時系列イベント |
| 校正 | `hud/calibrate.py`, `config/hud_templates.example.json` | 参照アンカーのエクスポート、交換可能なreader/signal profile |
| 動画処理 | `video/sampling.py`, `application/hud_video_processor.py` | native解像度の2-pass抽出、観測検証、Visualゲート、Round Package生成 |
| Event / Round | `events/{source_contract,derived}.py`, `rounds/builder.py` | 正本producer契約、非評価の派生状態、時間範囲に基づく品質集約 |
| 本体への接続 | `bootstrap.py`, `application/pipeline.py`, `schema_validation.py`, `facts/builder.py` | 実HUDモード、恒久証拠保存、キャンセル、中断再開、Ultimate Fact |
| 動画・再生 | `video/service.py`, `clips/service.py`, `settings.py`, `ui/{backend,contracts,main_window,settings_dialog}.py` | 全音声ストリームの保持、言語/タイトル/既定音声の取得、選択保存、Qt再生切替、診断表示 |
| 検証 | `tests/unit/test_hud_*.py`, `test_event_source_visual.py`, `test_round_package_builder.py`, `tests/integration/test_hud_*.py`, `test_real_ffmpeg.py` | 添付ロジック、読取器、統合、実FFmpeg、実Qt再生、実録画の任意受入テスト |

### 観測・イベントの安全条件

- live / spectator / remote / buy menu / expanded map / unknownを分離。Astra以外の特殊視点はprofileのテンプレートで追加できます。
- 観戦・特殊視点・マップ・flash/smoke・遷移付近を通常一人称Visual解析へ流しません。
- HP/Armor/Ammo/武器・Abilityはプレイヤー本人へ帰属できない視点では未確定に戻します。
- Killは新規Feed行と唯一の人数減少を結合します。名前OCRは不要。複数死亡や他チーム人数不明ではvictim sideを推測しません。killer sideは色/通常Killの補助証拠がなければunknownです。
- HP/Armorの範囲外数字、OCR/template不一致、低信頼の単独読取を採用しません。
- Buyメニューを閉じただけではround_startにしません。BuyからLiveへの遷移とTimerリセットを要求します。
- HUD confidenceとCoach confidenceは別管理。HUDは0.85以上を単独受理、0.65以上0.85未満は裏付け必須、0.65未満は不採用です。
- 未確定のラウンド境界をラウンド全体と扱わず、timeline completenessを0にします。HUDだけからshot/peek/utility_used等を捏造しません。
- Roundごとの品質は観測confidence中央値と時間カバレッジから集約します。

## まだ実データで完了していないもの

元録画 `Valorant_09-25-2026_0-37-29-379.mp4` と未加工スクリーンショットはこの作業環境にありません。
添付の注釈入りROIプレビューは認識テンプレートとして流用していません。

したがって、実装は「実ファイルを読み処理・保存できる統合経路」であり、
**任意の実VALORANT録画を調整なしに正確に解析できる状態とはまだいえません。**

- 実HUDの数字・アイコン・観戦/死亡パネル・特殊視点テンプレートの採集と精度調整が必要です。
- アンカーexportは出発点です。数字やスコアの変化に対して安定して照合できる参照画像へ調整する必要があります。解像度一致だけで校正済みにしません。
- Feed行の画素特徴、ロスター彩度、マップ・Astra・smoke/flash特徴は保守的な候補検出です。実ゲーム映像での適合率・再現率は未測定です。
- Kill Feedの名前/武器OCR、色の行単位照合、復活/複数同時死亡などの高精度照合は差し替えreaderの追加・調整が必要です。証拠が足りない陣営はunknownのままです。
- Abilityの利用可否とUltimate slotを読めますが、Agent別能力名、残チャージ数の高精度認識は未実装です。
- Zone/位置、敵視認、射撃、移動、preaim、peek、engagement、rotation、utility使用判定は`VisualAnalyzer`実装の追加が必要です。既定の`NullVisualAnalyzer`は未観測を明示します。
- Windows実機での再生・OCR導入・`.exe`生成、実OpenAI API呼出しはこのMacでは未検証です。

## 実画像取得後の作業

1. ROI線や拡大縮小のない1920x1080通常一人称画像と、各特殊状態の画像、元録画を用意します。
2. `python -m valorant_ai_coach.hud.calibrate reference.png NEW_PROFILE_DIR` でprofileを作ります。既存フォルダは上書きしません。
3. `hud_layout.templates.json` に数字/アイコン/状態テンプレートを追加します。パスはprofileからの相対パスです。数値fieldやAbility slotの座標は親ROI内の正規化座標です。exampleの小領域座標は説明用であり実測確定値ではありません。
4. 任意のTesseractを導入する場合、PATHまたは各readerの`executable`を設定します。Tesseractは同梱していません。数字templateとOCRが一致すれば裏付け、矛盾すればunknownです。
5. アプリ設定で実HUDと生成された`hud_layout.json`を選びます。まずMock AIで観測とイベントを検証してください。
6. 元録画を `VALORANT_HUD_TEST_VIDEO`、profileを `VALORANT_HUD_TEST_LAYOUT` に指定し、`test_hud_real_video_anchors.py` の13時刻を検証します。必要なら`VALORANT_FFPROBE`も指定します。
7. 保存された`matches/<id>/hud-analysis.json`と証拠画像を確認し、誤検出があるreaderだけを調整します。評価ルール・テスト期待値を変更して通す運用はしません。

## 検証した範囲

- 最終結果: **222 passed / 1 skipped**。分岐を含む全体カバレッジ **78.62%**（要求75%以上）。
- 正本dataset: **38 cases OK**。元ZIPとconfig/schemas/testsの**95ファイルがbyte一致**。
- Ruff / mypy: 成功。GUI `--smoke-test`: 終了コード0。音声デバイスに関するMac環境の警告は出ましたが、起動は成功しました。
- macOS / Python 3.12.14で全体テスト、正本dataset検証、Ruff、mypy、GUI初期化を実行する構成です。
- 合成1080p動画を実FFmpegでencodeし、OpenCV→テンプレート校正→実HUD→Round Package→SQLiteのE2Eを実行。
- 3音声トラックの動画から実クリップ生成、ストリーム数/言語/既定音声の保持、Qtでの再生と音声切替を実行。
- 12件の添付HL判定データを直接使用。GOOD/IMPROVE/UNSCORED、Rule Engine、Fact、Role、時間切迫、同時評価等は本体回帰テストで検証。
- 元録画による13時刻の受入テストは録画未提供のためskipします。合成動画の成功を実ゲーム精度の証明とは扱いません。

## Windows起動・ビルドへの影響

Python依存の追加はありません。`README.md`のPython 3.12 / PySide6手順を引き続き使用します。

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -c constraints-windows.txt -e ".[dev,build]"
.\.venv\Scripts\python.exe -m valorant_ai_coach
# 品質チェック + Windows onedir生成 + 起動確認
.\build_windows.ps1
```

既存PyInstaller specはconfig/schemas全体を同梱するので追加契約JSONも含まれます。
利用者固有のHUD profileと画像は外部設定としてまとめて配布・選択してください。
Tesseractを使う場合は別途導入が必要です。FFmpeg/FFprobeの任意同梱方式は変更していません。
Windowsの成果物は`dist\VALORANT-AI-Coach\VALORANT-AI-Coach.exe`です。フォルダごと配布します。
