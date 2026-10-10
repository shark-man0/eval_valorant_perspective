# 成績統計ダッシュボード

## 目的・データモデル

保存済みSQLiteの`matches/evaluations`を集計する読み取り専用機能。Match集計基盤を独自に実装せず、保存済み評価からの独立read modelとして構成した。実装: `NonVideoFeatures.statistics`。

## GUI

「履歴・統計ツール」→「統計」。日付範囲、ルール、カテゴリで絞り込める。Match件数、評価可能Match、不完全Match、評価0件Match、GOOD/IMPROVE/UNSCORED件数、カテゴリ・ルール別件数、日別推移を表示する。ラベル分布・カテゴリ上位8件・直近14観測日の推移・頻出改善ルール上位8件を
Qtバーグラフで描画し、全件の表も残す。データがなければ「該当データなし」を表示する。
GOOD率は`GOOD/(GOOD+IMPROVE)`と明示し、分母ゼロなら表示しない。総合スキルスコアは作らない。

## 実装・性能

`SELECT ... GROUP BY`を用い、評価payload全文を読み出さずに集計する。表示上の棒はQt`QProgressBar`による件数で、video frame処理は実施しない。日付集計は保存時刻のUTC日付文字列を使用する。

## テスト・制約

`test_non_video_features.py`と`test_non_video_dialog.py`。空Match、不完全Match、全UNSCORED、日別集計、カテゴリ表示を確認する。入力源が不完全なら統計も偏るため、結果はプレイスキルの絶対比較を意味しない。別AIの未マージMatch集計基盤に依存しない。