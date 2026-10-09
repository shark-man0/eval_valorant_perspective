# 非動画領域 パフォーマンス計測

## 目的と対象

保存済み評価の検索・履歴走査・統計・JSON/CSV出力のみを対象とする。動画デコード、HUD・Visual解析、実動画測定は対象外。

## 再現方法

```bash
python -m pip install -e .
python scripts/non_video_benchmark.py
```

10・100・1000 Match、各Match 5 Evaluation（合計50/500/5000評価）をSQLiteに合成保存。Match 10件ごとにpartialを設定。旧実装の`list_matches→list_evaluations`によるPython走査と、indexed SQL search / GROUP BY統計を、同一データで各3回ずつ計測し中央値（ms）とtracemalloc peak（byte）をJSONで表示する。

## 変更前後の比較条件

評価ID全件集合とGOOD/IMPROVE/UNSCORED件数の一致をassertし、意味変更がないことを確認。CSV/JSONは同一matchを3回出力して測る。ベンチマークは一時ディレクトリで実施し、元データを変更しない。

## 改善内容

既存match/evaluationの複数テーブル走査を避け、`matches(created_at)`、`evaluations(primary_rule_id,label)`の索引を追加した。検索は50件GUIページ、最大500件DBページ。統計は複数`GROUP BY`で集約し、すべての評価JSONをPythonでロードせずに件数を計算する。

## 計測結果と制約

数値結果は専用GitHub Actionsの`Non-video synthetic benchmark` artifact `non-video-benchmark-results.json`を正として参照する。ここでは未実行の時間・改善率を捏造しない。SQLiteの`LIKE`全文走査、GUI大量行の描画、他プロセスとの同時使用は別途性能検証の対象。合成結果は実運用の保証ではない。