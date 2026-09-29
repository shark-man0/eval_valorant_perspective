# 実装計画と受入基準

## 方針

- ZIP内の `schemas/`、`config/`、`tests/cases/` を正本として保持する。
- HUD座標だけを未確定とし、Mock Round Packageで本番と同じパイプラインを通す。
- 観測、Fact生成、候補選定、評価、クリップ、保存、UIを相互に交換できる境界へ分離する。
- 候補外と通常行動は出力せず、候補に残った証拠不足だけをUNSCOREDにする。

## 実装段階

1. 正本Schema/設定のロードとruntime検証
2. Deterministic Fact Builder / Rule Selector / Rule Engine
3. Mock Evaluatorによる38ケース評価
4. FFprobe / OpenCV / FFmpeg、HUD adapter、SQLite
5. OpenAI Responses API + 画像入力 + Schema修復
6. Round単位の統合パイプライン、重複集約、クリップ生成
7. PySide6 UI、設定、ログ、エラー表示
8. PyInstaller onedirとWindows手順

## 完了時の検証

- `tests/validate_dataset.py` の38ケース
- 38ケースの期待評価（件数、label、concept tags、clip有無、UNSCORED理由）
- 実FFmpegによるテスト動画のprobe / frame / clip
- SQLite保存、再読込、再実行時の置換
- Mock E2E（Round PackageからUI向け結果まで）
- ruff / mypy / pytest / compileall
- PyInstaller specの正本リソース同梱確認

Windows上での最終GUI起動とexe実行確認はWindows環境で行う。macOSで生成したexeは正式成果物としない。

