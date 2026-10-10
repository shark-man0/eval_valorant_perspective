# 履歴検索・Match比較

## 目的・データアクセス

保存済み評価を索引・ページング付きで検索する。正本SQLiteの既存`evaluations/matches`から共通`NonVideoFeatures.search`で取得し、評価ラベル・confidence等は再計算しない。

## GUI

「履歴・統計ツール」→「検索・比較」。Match ID、日付、Rule、Category、GOOD/IMPROVE/UNSCORED、自由記述キーワードを複合指定し、50件ずつページング。Rule/Categoryは評価設定JSONから表示名を得る。Matchを2つ選びGOOD/IMPROVE/UNSCORED、Rule別件数、不完全ステータスを比較する。総合的な優劣を判定しない。

## 安全性・テスト

SQLはパラメータ化し、`LIKE`の`%`と`_`もエスケープ。MatchやEvaluation IDは一意キーに従う。大量評価の比較は500件ごとの走査で欠落を防ぐ。

`test_non_video_features.py`の結合検索、SQLインジェクション風入力、順序・ページング・比較検証。キーワード検索はSQLite`LIKE`（全文検索エンジンではない）。検索条件次第で時間がかかることがある。