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

2026-10-10、GitHub Actions Linux runner（Python 3.12）の同一runで3回ずつ計測した中央値。
計測run: [Non-video synthetic benchmark #37966879010](https://github.com/shark-man0/eval_valorant_perspective/actions/runs/37966879010)。
実動画や有料APIは使用しない。

| Match数（評価件数） | 旧検索 ms | 新検索 ms | 旧統計 ms | SQL統計 ms |
|---|---:|---:|---:|---:|
| 10（50） | 7.102 | 2.072 | 7.851 | 1.115 |
| 100（500） | 66.092 | 16.139 | 66.725 | 2.995 |
| 1,000（5,000） | 652.563 | 198.053 | 658.936 | 22.879 |

1,000 Matchでの検索時間は約3.3倍、統計集計は約28.8倍の高速化。
検索対象の評価ID集合とラベル件数は全条件で一致。
ただし全件検索のPython追跡メモリpeakは旧807,800 byte→新1,795,361 byteに増加。
これは結果オブジェクト全件を一度に収集する合成比較の数値であり、
GUIでは50件ずつページングする。大量の全件エクスポートやメモリ削減まで達成したとは主張しない。

`csv_export` / `json_export`は特定の1 Match（5評価）の反復出力であり、
データセット全体の一括エクスポート性能を測定したものではない。
相対的な速度はGitHub runner・負荷・依存バージョンで変動する。
SQLiteの`LIKE`全文走査、GUI大量行の描画、他プロセスとの同時使用は
別途性能検証の対象。合成結果は実運用の保証ではない。

