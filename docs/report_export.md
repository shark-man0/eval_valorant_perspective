# 評価レポート出力

## 目的・既存実装との関係

既存SQLite保存済み評価を非破壊で外部へ取り出す。新しいGOOD/IMPROVE/UNSCORED判定を生成しない。実装: `non_video.features.NonVideoFeatures.report/export_report`。

## 実装・データ形式

HTML/CSV/JSONへ対応。GUIの結果画面「レポート出力」または「履歴・統計ツール」→「レポート出力」からMatch、形式、保存先を指定する。JSONには`export_format_version=1`、Match ID・保存日時・状態・元動画**ファイル名のみ**、評価ID・Round番号・ラベル・ルール・根拠・改善・confidence・不足情報などを含む。欠損はJSONでは`null`、CSVでは空欄で示す。

HTMLはHTMLエスケープ、CSVは先頭の`= + - @`等の式を無害化する。保存先と同じディレクトリに一時ファイルを書いてfsync後`os.replace`する。失敗時は元ファイルを保持する。元動画、画像、APIキー、絶対パスは埋め込まない。自由記述内の典型的な秘密・ローカルパスも伏せる。

## テスト・確認方法

`python -m pytest tests/unit/test_non_video_features.py -q`。日本語、HTML注入、CSV式注入、欠損、UNSCORED、書込失敗、元評価不変を確認する。

## 制約

CSVは平坦化した一部フィールドのみ。JSONは機械処理向けだが正本Round Packageの完全な複製ではない。不可逆な匿名化を保証するものではないため、共有前にユーザーが内容を確認する。