# 設定プロファイル管理

## 目的

複数の設定を明示的に保存・切替する。正本設定は既存`SettingsStore`。プロファイルは`settings_profiles.json`に独立保存する。

## 機能とGUI

「履歴・統計ツール」→「設定プロファイル」。作成・名前変更・切替・削除・初期設定へ戻す・JSONエクスポート/インポートが可能。ファイルは`{"version":1,"settings":{...}}`。未知キー・型違い・破損ファイルは拒否。書き込みは一時ファイル+置換で実施する。

## 安全条件

APIキー、Credential Manager内の資格情報、`data_dir`は含めない。切替では既存BackendFacadeの安全なサービス再構築/rollbackを使用。初期化でも現在の`data_dir`とMatch履歴は変更しない。アプリ再起動後も保持。

## テスト・制約

`test_non_video_features.py`。改変JSON、credential非出力、削除、再読込。実HUD設定など有効な外部ファイルを必要とする構成は、切替後の再構築が失敗し得る。その場合既存設定にrollbackする。