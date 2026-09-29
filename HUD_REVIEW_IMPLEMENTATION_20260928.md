# HUDレビュー修正記録（2026-09-28）

既存の8項目の指摘を修正しました。これは実装・回帰テストの記録であり、実VALORANT録画での認識精度を保証するものではありません。

## 修正内容と主な変更ファイル

ファイルパスは `src/valorant_ai_coach/` からの相対パスです。

| 指摘 | 修正 | ファイル |
| --- | --- | --- |
| round_start欠落で後続ラウンドが消える | 境界を時系列に走査し、開始/終了不足の区間も部分ラウンドとして保持。完全性は0とし全体文脈を捏造しない | `rounds/builder.py` |
| スコア/バナー、Feed/人数更新のずれ | 双方向の時間窓で証拠を結合。スコア/バナーは3秒、Feed/人数減少は0.75秒。Killは一対一に確定できる組だけ陣営を解決 | `hud/timeline.py`, `hud/temporal.py` |
| 単色壁・暗い画面をsmokeと断定 | 低詳細特徴だけでは曖昧として扱う。確認済みテンプレート等の裏付けがない場合、smokeイベントを生成しない | `hud/readers.py`, `hud/classifier.py`, `hud/templates.py`, `hud/analyzers.py` |
| 長時間録画がフレーム上限で拒否される | Pass Aを連続した時刻グリッドのまま分割計画・抽出。区切りでサンプルを重複・欠落させない | `video/sampling.py`, `application/hud_video_processor.py` |
| 死亡・状態異常イベントが毎フレーム重複 | 死亡はラウンド/復活でリセットするラッチ、状態異常は観測エピソード単位。観測欠落時は継続時間を推測しない | `hud/temporal.py` |
| 共有ラウンド境界で二重収録 | 隣接区間は半開区間で所属を一意化。round_endは直前ラウンドへ所属 | `rounds/builder.py` |
| 古いHUD観測がVisual解析を許可 | 通常一人称に依存するイベントは既定0.5秒を超える古い観測では許可しない | `visual/analyzer.py` |
| 数値読取の裏付け情報が失われる | 複合数値の出典・cross_checkedを保持。他の弱い未裏付けfieldを巻き込んで受理しない | `hud/templates.py` |

再開時に旧判定のキャッシュを流用しないよう `application/pipeline.py` の再開契約バージョンも3へ更新しました。正本JSON形式・AI評価閾値は変更していません。

## 追加した回帰テスト

- `tests/unit/test_review_safety_regressions.py`: 長時間/端点サンプリング、単色画面、数値裏付け、HUD鮮度。
- `tests/unit/test_hud_temporal_regressions.py`: 更新順序の逆転、曖昧な人数差分、死亡・状態異常の重複、実HUDクラスへの接続。
- `tests/unit/test_round_boundary_regressions.py`: 境界欠落、共有時刻、メニュー区間。
- `tests/integration/test_long_hud_processing.py`: 1時間の時刻計画・抽出インターフェース、バッチ上限、キャンセル。

## 検証結果

- macOS / Python 3.12.14: **222 passed / 1 skipped**。カバレッジ **78.62%**。
- 実FFmpegを使う合成動画のHUD→Round Package→SQLite経路、複数音声クリップ、Qt再生を含む全体テストが成功。
- 正本dataset **38 cases OK**。添付2 ZIP内のconfig/schemas/tests **95ファイルがbyte一致**。既存テスト期待値の変更なし。
- Ruff成功、mypy成功（56 source files）、GUI `--smoke-test` 終了コード0。Mac音声デバイス・代替フォントの警告あり。

## 残る制約・実機確認

- 元のVALORANT録画が未提供のため実録画受入テスト1件はskip。実ゲームでの適合率・再現率は未測定です。
- 1時間ケースは抽出インターフェースを置き換えたテストです。1時間の実動画デコード・処理時間・メモリ/ディスク消費は未測定です。抽出計画は分割していますが、観測メタデータ全体は保持するため定数メモリ処理ではありません。
- smokeを確定するには実画像で検証したsignal profile（`smoke_template_confirmed`）等の裏付けが必要です。低詳細画面のみではVisual解析も保守的に停止します。
- Agent別高精度認識とVisual Analyzerの追加項目は `HUD_INTEGRATION.md` のとおりです。
- Windows起動・PyInstaller `.exe` 生成・実OpenAI API呼出しは未検証です。依存追加やビルド手順変更はありません。Windowsでは `README.md` と `build_windows.ps1` を使用してください。
